"""Optional NumPy baseline for correcting ToF-E candidate confidence.

The model is deliberately small and independent of Qt and scikit-learn.  A
missing, malformed, or schema-incompatible model never blocks Potku: callers
receive the original heuristic confidence with an explicit fallback reason.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from modules.tofe_training_data import TrainingFeatureRow


MODEL_FORMAT_VERSION = 1
EXCLUDED_FIELDS = (
    "measurement_id", "selection_id", "label", "target_accepted",
)
FEATURE_NAMES = tuple(
    name for name in TrainingFeatureRow.__dataclass_fields__
    if name not in EXCLUDED_FIELDS
)
FEATURE_SCHEMA = sha256("\n".join(FEATURE_NAMES).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BaselineCorrectionModel:
    means: np.ndarray
    scales: np.ndarray
    weights: np.ndarray
    bias: float
    feature_names: tuple = FEATURE_NAMES
    format_version: int = MODEL_FORMAT_VERSION
    feature_schema: str = FEATURE_SCHEMA

    def predict_probability(self, rows):
        rows = tuple(rows)
        if not rows:
            return np.empty(0, dtype=float)
        _validate_model(self)
        matrix = _feature_matrix(rows)
        standardized = (matrix - self.means) / self.scales
        scores = np.clip(standardized @ self.weights + self.bias, -30, 30)
        return 1 / (1 + np.exp(-scores))

    def as_dict(self):
        _validate_model(self)
        return {
            "format_version": self.format_version,
            "feature_schema": self.feature_schema,
            "feature_names": list(self.feature_names),
            "means": self.means.tolist(),
            "scales": self.scales.tolist(),
            "weights": self.weights.tolist(),
            "bias": float(self.bias),
        }


@dataclass(frozen=True)
class OptionalModelResult:
    model: object
    fallback_reason: str


@dataclass(frozen=True)
class ConfidenceCorrection:
    confidence: float
    source: str
    fallback_reason: str = ""


def fit_baseline_correction_model(
        rows, l2_penalty=1.0, iterations=800, learning_rate=0.2):
    """Fit deterministic regularized logistic regression using NumPy."""
    rows = tuple(rows)
    if len(rows) < 2:
        raise ValueError("Baseline model needs at least two training rows")
    targets = np.asarray([row.target_accepted for row in rows], dtype=float)
    if not np.all(np.isin(targets, (0, 1))):
        raise ValueError("Training targets must be binary")
    if np.unique(targets).size != 2:
        raise ValueError("Baseline model needs accepted and rejected rows")
    l2_penalty = _nonnegative_finite(l2_penalty, "L2 penalty")
    learning_rate = _positive_finite(learning_rate, "Learning rate")
    if not isinstance(iterations, (int, np.integer)) or iterations < 1:
        raise ValueError("Iterations must be a positive integer")

    matrix = _feature_matrix(rows)
    means = np.mean(matrix, axis=0)
    scales = np.std(matrix, axis=0)
    scales = np.where(scales > 1e-12, scales, 1.0)
    standardized = (matrix - means) / scales
    weights = np.zeros(standardized.shape[1], dtype=float)
    prevalence = float(np.clip(np.mean(targets), 1e-6, 1 - 1e-6))
    bias = float(np.log(prevalence / (1 - prevalence)))
    row_count = float(len(rows))

    for iteration in range(iterations):
        scores = np.clip(standardized @ weights + bias, -30, 30)
        probabilities = 1 / (1 + np.exp(-scores))
        errors = probabilities - targets
        gradient_weights = (
            standardized.T @ errors / row_count +
            l2_penalty * weights / row_count
        )
        gradient_bias = float(np.mean(errors))
        step = learning_rate / np.sqrt(1 + iteration / 100)
        weights -= step * gradient_weights
        bias -= step * gradient_bias

    model = BaselineCorrectionModel(
        means=_readonly(means),
        scales=_readonly(scales),
        weights=_readonly(weights),
        bias=float(bias),
    )
    _validate_model(model)
    return model


def save_baseline_correction_model(model, path):
    """Atomically save a validated baseline model as portable JSON."""
    _validate_model(model)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(model.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_optional_baseline_correction_model(path):
    """Load a model or return a safe fallback result without raising."""
    if path is None:
        return OptionalModelResult(None, "model path is not configured")
    path = Path(path)
    if not path.is_file():
        return OptionalModelResult(None, "model file is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = _model_from_dict(payload)
        _validate_model(model)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        return OptionalModelResult(None, f"model is incompatible: {error}")
    return OptionalModelResult(model, "")


def corrected_candidate_confidence(candidate, row, optional_model=None):
    """Return ML confidence when valid, otherwise the heuristic unchanged."""
    heuristic = float(candidate.confidence)
    if not np.isfinite(heuristic) or not 0 <= heuristic <= 1:
        raise ValueError("Candidate confidence must be in [0, 1]")
    model = optional_model
    fallback_reason = "model is not available"
    if isinstance(optional_model, OptionalModelResult):
        model = optional_model.model
        fallback_reason = optional_model.fallback_reason
    if model is None:
        return ConfidenceCorrection(heuristic, "heuristic", fallback_reason)
    try:
        probability = float(model.predict_probability([row])[0])
    except (TypeError, ValueError, AttributeError) as error:
        return ConfidenceCorrection(
            heuristic, "heuristic", f"model prediction failed: {error}"
        )
    if not np.isfinite(probability) or not 0 <= probability <= 1:
        return ConfidenceCorrection(
            heuristic, "heuristic", "model prediction was outside [0, 1]"
        )
    return ConfidenceCorrection(probability, "ml")


def _model_from_dict(payload):
    if not isinstance(payload, dict):
        raise TypeError("Model JSON root must be an object")
    return BaselineCorrectionModel(
        means=_readonly(payload["means"]),
        scales=_readonly(payload["scales"]),
        weights=_readonly(payload["weights"]),
        bias=float(payload["bias"]),
        feature_names=tuple(payload["feature_names"]),
        format_version=int(payload["format_version"]),
        feature_schema=str(payload["feature_schema"]),
    )


def _feature_matrix(rows):
    matrix = []
    for row in rows:
        if not isinstance(row, TrainingFeatureRow):
            raise TypeError("Model rows must be TrainingFeatureRow objects")
        values = row.as_dict()
        vector = [float(values[name]) for name in FEATURE_NAMES]
        matrix.append(vector)
    result = np.asarray(matrix, dtype=float)
    if not np.all(np.isfinite(result)):
        raise ValueError("Model features must be finite")
    return result


def _validate_model(model):
    if not isinstance(model, BaselineCorrectionModel):
        raise TypeError("Expected BaselineCorrectionModel")
    if model.format_version != MODEL_FORMAT_VERSION:
        raise ValueError("unsupported model format version")
    if tuple(model.feature_names) != FEATURE_NAMES:
        raise ValueError("feature names do not match current schema")
    if model.feature_schema != FEATURE_SCHEMA:
        raise ValueError("feature schema fingerprint does not match")
    feature_count = len(FEATURE_NAMES)
    for name in ("means", "scales", "weights"):
        values = np.asarray(getattr(model, name), dtype=float)
        if values.shape != (feature_count,) or not np.all(np.isfinite(values)):
            raise ValueError(f"model {name} are invalid")
    if np.any(np.asarray(model.scales) <= 0):
        raise ValueError("model scales must be positive")
    if not np.isfinite(model.bias):
        raise ValueError("model bias must be finite")


def _readonly(values):
    result = np.asarray(values, dtype=float).copy()
    result.setflags(write=False)
    return result


def _nonnegative_finite(value, description):
    value = float(value)
    if not np.isfinite(value) or value < 0:
        raise ValueError(f"{description} must be finite and non-negative")
    return value


def _positive_finite(value, description):
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{description} must be finite and positive")
    return value
