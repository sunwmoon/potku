import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from modules.tofe_ml import FEATURE_NAMES
from modules.tofe_ml import corrected_candidate_confidence
from modules.tofe_ml import fit_baseline_correction_model
from modules.tofe_ml import load_optional_baseline_correction_model
from modules.tofe_ml import save_baseline_correction_model
from modules.tofe_training_data import TrainingFeatureRow


def training_row(row_id, target, event_fraction, theory_distance, overlap):
    return TrainingFeatureRow(
        measurement_id="synthetic",
        selection_id=row_id,
        label="16O",
        target_accepted=target,
        event_count=int(event_fraction * 10000),
        event_fraction=event_fraction,
        tof_mean=600.0,
        energy_mean=1500.0,
        tof_std=100.0,
        energy_std=300.0,
        tof_energy_correlation=-0.95,
        polygon_area=30000.0,
        polygon_perimeter=4000.0,
        polygon_compactness=0.03,
        polygon_tof_width=500.0,
        polygon_energy_height=1800.0,
        polygon_centroid_tof=700.0,
        polygon_centroid_energy=1300.0,
        has_theory=1,
        theory_centroid_dx_fwhm=theory_distance / 2,
        theory_centroid_dy_fwhm=theory_distance / 2,
        theory_centroid_distance_fwhm=theory_distance,
        event_theory_distance_median_fwhm=theory_distance / 10,
        max_neighbor_event_iou=overlap,
        max_neighbor_shared_fraction=overlap,
    )


def separable_rows():
    return (
        training_row("p1", 1, 0.18, 0.5, 0.0),
        training_row("p2", 1, 0.15, 0.8, 0.02),
        training_row("p3", 1, 0.12, 1.0, 0.05),
        training_row("n1", 0, 0.01, 5.0, 0.6),
        training_row("n2", 0, 0.02, 7.0, 0.8),
        training_row("n3", 0, 0.00, 9.0, 0.9),
    )


class TestTofeMl(unittest.TestCase):
    def test_schema_has_twenty_one_numeric_predictors(self):
        self.assertEqual(len(FEATURE_NAMES), 21)
        self.assertNotIn("measurement_id", FEATURE_NAMES)
        self.assertNotIn("target_accepted", FEATURE_NAMES)

    def test_deterministic_baseline_separates_simple_training_rows(self):
        rows = separable_rows()
        first = fit_baseline_correction_model(rows)
        second = fit_baseline_correction_model(rows)
        probabilities = first.predict_probability(rows)

        np.testing.assert_allclose(first.weights, second.weights)
        self.assertTrue(np.all(probabilities[:3] > 0.75))
        self.assertTrue(np.all(probabilities[3:] < 0.25))

    def test_model_json_round_trip_preserves_predictions(self):
        rows = separable_rows()
        model = fit_baseline_correction_model(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "model.json")
            save_baseline_correction_model(model, path)
            loaded = load_optional_baseline_correction_model(path)

            self.assertEqual(loaded.fallback_reason, "")
            np.testing.assert_allclose(
                loaded.model.predict_probability(rows),
                model.predict_probability(rows),
            )

    def test_missing_or_corrupt_model_returns_safe_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = load_optional_baseline_correction_model(
                Path(directory, "missing.json")
            )
            corrupt_path = Path(directory, "corrupt.json")
            corrupt_path.write_text("{bad json", encoding="utf-8")
            corrupt = load_optional_baseline_correction_model(corrupt_path)

        self.assertIsNone(missing.model)
        self.assertIn("missing", missing.fallback_reason)
        self.assertIsNone(corrupt.model)
        self.assertIn("incompatible", corrupt.fallback_reason)

    def test_schema_mismatch_returns_safe_fallback(self):
        rows = separable_rows()
        model = fit_baseline_correction_model(rows)
        payload = model.as_dict()
        payload["feature_schema"] = "old-schema"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "old.json")
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_optional_baseline_correction_model(path)

        self.assertIsNone(loaded.model)
        self.assertIn("schema", loaded.fallback_reason)

    def test_confidence_uses_model_or_preserves_heuristic(self):
        rows = separable_rows()
        candidate = SimpleNamespace(confidence=0.42)
        fallback = corrected_candidate_confidence(candidate, rows[0], None)
        model = fit_baseline_correction_model(rows)
        corrected = corrected_candidate_confidence(candidate, rows[0], model)

        self.assertEqual(fallback.confidence, 0.42)
        self.assertEqual(fallback.source, "heuristic")
        self.assertEqual(corrected.source, "ml")
        self.assertGreater(corrected.confidence, 0.75)

    def test_training_requires_both_decision_classes(self):
        with self.assertRaisesRegex(ValueError, "accepted and rejected"):
            fit_baseline_correction_model(separable_rows()[:3])


if __name__ == "__main__":
    unittest.main()
