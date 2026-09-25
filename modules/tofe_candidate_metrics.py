"""Truth-event metrics for synthetic ToF-E banana selections.

Synthetic events carry element labels, so proposal polygons can be evaluated
without inventing a unique geometric truth boundary for Gaussian detector
broadening.  Events from the target label inside the polygon are true
positives; background and other elements inside it are false positives.
"""

from dataclasses import dataclass
from typing import Iterable
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class CandidateTruthMetrics:
    label: str
    detected: bool
    truth_events: int
    selected_events: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    event_iou: float


@dataclass(frozen=True)
class CandidateMetricSummary:
    expected_labels: int
    detected_labels: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    event_iou: float


def evaluate_candidate_truth(
        candidates: Iterable, tof_channel, energy_channel, truth_label,
        expected_labels=None, background_label="background"
        ) -> Tuple[CandidateTruthMetrics, ...]:
    """Compare candidate polygons with labeled synthetic events.

    ``expected_labels`` should normally come from the calculated loci.  A
    label without a candidate is returned as ``detected=False`` with zero
    recall, making missing bananas explicit rather than silently omitting them.
    """
    tof, energy, labels = _validated_events(
        tof_channel, energy_channel, truth_label
    )
    candidates = tuple(candidates)
    by_label = {}
    for candidate in candidates:
        label = str(candidate.label)
        if label in by_label:
            raise ValueError(f"Duplicate candidate label: {label}")
        by_label[label] = candidate

    if expected_labels is None:
        label_order = sorted(
            (set(str(value) for value in labels) - {background_label}) |
            set(by_label)
        )
    else:
        label_order = []
        seen = set()
        for value in expected_labels:
            label = str(value)
            if not label or label == background_label:
                raise ValueError("Expected labels must be non-background")
            if label in seen:
                raise ValueError(f"Duplicate expected label: {label}")
            seen.add(label)
            label_order.append(label)
        unexpected = set(by_label) - seen
        if unexpected:
            raise ValueError(
                "Candidate labels missing from expected labels: " +
                ", ".join(sorted(unexpected))
            )

    rows = []
    points = np.column_stack((tof, energy))
    for label in label_order:
        truth_mask = labels == label
        candidate = by_label.get(label)
        if candidate is None:
            selected_mask = np.zeros(labels.size, dtype=bool)
        else:
            selected_mask = points_inside_polygon(points, candidate.polygon)
        true_positive = int(np.count_nonzero(selected_mask & truth_mask))
        false_positive = int(np.count_nonzero(selected_mask & ~truth_mask))
        false_negative = int(np.count_nonzero(~selected_mask & truth_mask))
        precision = _safe_ratio(
            true_positive, true_positive + false_positive
        )
        recall = _safe_ratio(
            true_positive, true_positive + false_negative
        )
        rows.append(CandidateTruthMetrics(
            label=label,
            detected=candidate is not None,
            truth_events=int(np.count_nonzero(truth_mask)),
            selected_events=int(np.count_nonzero(selected_mask)),
            true_positive=true_positive,
            false_positive=false_positive,
            false_negative=false_negative,
            precision=precision,
            recall=recall,
            f1=_harmonic_mean(precision, recall),
            event_iou=_safe_ratio(
                true_positive,
                true_positive + false_positive + false_negative,
            ),
        ))
    return tuple(rows)


def summarize_candidate_metrics(rows) -> CandidateMetricSummary:
    """Aggregate label rows using micro-averaged event counts."""
    rows = tuple(rows)
    true_positive = sum(row.true_positive for row in rows)
    false_positive = sum(row.false_positive for row in rows)
    false_negative = sum(row.false_negative for row in rows)
    precision = _safe_ratio(true_positive, true_positive + false_positive)
    recall = _safe_ratio(true_positive, true_positive + false_negative)
    return CandidateMetricSummary(
        expected_labels=len(rows),
        detected_labels=sum(row.detected for row in rows),
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=_harmonic_mean(precision, recall),
        event_iou=_safe_ratio(
            true_positive,
            true_positive + false_positive + false_negative,
        ),
    )


def points_inside_polygon(points, polygon):
    """Vectorized even-odd test for finite points and a closed polygon."""
    points = np.asarray(points, dtype=float)
    polygon = np.asarray(polygon, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Points must have shape (n, 2)")
    if not np.all(np.isfinite(points)):
        raise ValueError("Points must be finite")
    if polygon.ndim != 2 or polygon.shape[1] != 2 or polygon.shape[0] < 4:
        raise ValueError("Polygon must have shape (n, 2)")
    if not np.all(np.isfinite(polygon)):
        raise ValueError("Polygon must be finite")
    if not np.allclose(polygon[0], polygon[-1]):
        raise ValueError("Polygon must be closed")
    vertices = polygon[:-1]
    if np.unique(vertices, axis=0).shape[0] < 3:
        raise ValueError("Polygon needs three distinct vertices")

    x = points[:, 0]
    y = points[:, 1]
    inside = np.zeros(points.shape[0], dtype=bool)
    previous = vertices[-1]
    for current in vertices:
        x_current, y_current = current
        x_previous, y_previous = previous
        crosses_y = (y_current > y) != (y_previous > y)
        denominator = y_previous - y_current
        if denominator != 0:
            crossing_x = (
                (x_previous - x_current) * (y - y_current) /
                denominator + x_current
            )
            inside ^= crosses_y & (x < crossing_x)
        previous = current
    return inside


def _validated_events(tof_channel, energy_channel, truth_label):
    tof = np.asarray(tof_channel, dtype=float)
    energy = np.asarray(energy_channel, dtype=float)
    labels = np.asarray(truth_label)
    if tof.ndim != 1 or energy.ndim != 1 or labels.ndim != 1:
        raise ValueError("Event arrays and truth labels must be one-dimensional")
    if tof.size == 0 or tof.shape != energy.shape or tof.shape != labels.shape:
        raise ValueError("Event arrays and truth labels must have equal length")
    if not np.all(np.isfinite(tof)) or not np.all(np.isfinite(energy)):
        raise ValueError("Event channels must be finite")
    labels = labels.astype(str)
    if np.any(np.char.str_len(labels) == 0):
        raise ValueError("Truth labels must be non-empty")
    return tof, energy, labels


def _safe_ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else 0.0


def _harmonic_mean(first, second):
    return _safe_ratio(2 * first * second, first + second)
