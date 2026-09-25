"""ML-ready feature rows from accepted Potku ToF-E selections.

The extractor is independent of Qt and scikit-learn.  Existing Potku
``Selection`` objects are adapted into canonical (ToF, Energy) polygons, then
combined with enclosed event statistics, polygon shape, theory offset, and
neighbour overlap features.  It does not create, edit, or save selections.
"""

from dataclasses import asdict
from dataclasses import dataclass
from math import pi
from typing import Iterable
from typing import Tuple

import numpy as np

from modules.tofe_candidate_metrics import points_inside_polygon


@dataclass(frozen=True)
class AcceptedSelection:
    selection_id: str
    label: str
    polygon: np.ndarray
    target_accepted: int = 1


@dataclass(frozen=True)
class TrainingFeatureRow:
    measurement_id: str
    selection_id: str
    label: str
    target_accepted: int
    event_count: int
    event_fraction: float
    tof_mean: float
    energy_mean: float
    tof_std: float
    energy_std: float
    tof_energy_correlation: float
    polygon_area: float
    polygon_perimeter: float
    polygon_compactness: float
    polygon_tof_width: float
    polygon_energy_height: float
    polygon_centroid_tof: float
    polygon_centroid_energy: float
    has_theory: int
    theory_centroid_dx_fwhm: float
    theory_centroid_dy_fwhm: float
    theory_centroid_distance_fwhm: float
    event_theory_distance_median_fwhm: float
    max_neighbor_event_iou: float
    max_neighbor_shared_fraction: float

    def as_dict(self):
        return asdict(self)


def accepted_selections_from_potku(
        selections: Iterable, transposed=False) -> Tuple[AcceptedSelection, ...]:
    """Adapt completed ERD selections without importing Potku GUI modules."""
    accepted = []
    for selection in selections:
        if getattr(selection, "type", None) != "ERD":
            continue
        if not bool(getattr(selection, "is_completed", False)):
            continue
        element = getattr(selection, "element", None)
        symbol = getattr(element, "symbol", None)
        isotope = getattr(element, "isotope", None)
        if not isinstance(symbol, str) or not symbol or symbol == "Select":
            raise ValueError("Completed ERD selection needs an element")
        if isotope is not None:
            if (not isinstance(isotope, (int, np.integer)) or
                    isinstance(isotope, bool) or isotope <= 0):
                raise ValueError("Selection isotope must be a positive integer")
            label = f"{int(isotope)}{symbol}"
        else:
            label = symbol
        get_points = getattr(selection, "get_points", None)
        if not callable(get_points):
            raise TypeError("Selection must provide get_points()")
        polygon = np.asarray(get_points(), dtype=float)
        if transposed:
            polygon = polygon[:, ::-1]
        polygon = _validated_closed_polygon(polygon)
        accepted.append(AcceptedSelection(
            selection_id=str(getattr(selection, "id", len(accepted))),
            label=label,
            polygon=polygon,
        ))
    return tuple(accepted)


def reviewed_candidates_as_training_selections(review_items):
    """Convert final review decisions into positive and negative polygons.

    Pending and actively edited proposals are omitted because they have no
    final user decision.  A rejected working polygon becomes one negative
    example.  An accepted polygon becomes positive; if the user edited it,
    the original proposal is also retained as a negative example.  This
    function only copies transient NumPy data and never accesses a selector.
    """
    selections = []
    for item in review_items:
        status = getattr(getattr(item, "status", None), "value", None)
        candidate_id = str(getattr(item, "candidate_id", "")).strip()
        original = getattr(item, "original", None)
        working = getattr(item, "working", None)
        if status not in ("accepted", "rejected"):
            continue
        if not candidate_id or original is None or working is None:
            raise ValueError("Final review item is incomplete")
        original_polygon = _validated_closed_polygon(original.polygon)
        working_polygon = _validated_closed_polygon(working.polygon)
        if status == "accepted":
            if not _same_polygon(original_polygon, working_polygon):
                selections.append(AcceptedSelection(
                    selection_id=f"{candidate_id}:original",
                    label=str(original.label),
                    polygon=original_polygon,
                    target_accepted=0,
                ))
            selections.append(AcceptedSelection(
                selection_id=f"{candidate_id}:accepted",
                label=str(working.label),
                polygon=working_polygon,
                target_accepted=1,
            ))
        else:
            selections.append(AcceptedSelection(
                selection_id=f"{candidate_id}:rejected",
                label=str(working.label),
                polygon=working_polygon,
                target_accepted=0,
            ))
    return tuple(selections)


def build_training_feature_rows(
        tof_channel, energy_channel, selections: Iterable, loci=(),
        measurement_id="") -> Tuple[TrainingFeatureRow, ...]:
    """Build one finite ML feature row per accepted selection."""
    tof, energy = _validated_events(tof_channel, energy_channel)
    selections = tuple(_validated_selection(selection) for selection in selections)
    loci_by_label = _loci_by_label(loci)
    all_points = np.column_stack((tof, energy))
    masks = tuple(
        points_inside_polygon(all_points, selection.polygon)
        for selection in selections
    )
    centroids = tuple(
        _polygon_geometry(selection.polygon)[4]
        for selection in selections
    )
    rows = []
    for index, (selection, mask) in enumerate(zip(selections, masks)):
        selected_points = all_points[mask]
        event_count = int(selected_points.shape[0])
        if event_count:
            tof_mean = float(np.mean(selected_points[:, 0]))
            energy_mean = float(np.mean(selected_points[:, 1]))
            tof_std = float(np.std(selected_points[:, 0]))
            energy_std = float(np.std(selected_points[:, 1]))
            if tof_std > 0 and energy_std > 0:
                correlation = float(np.corrcoef(
                    selected_points[:, 0], selected_points[:, 1]
                )[0, 1])
            else:
                correlation = 0.0
        else:
            tof_mean = energy_mean = tof_std = energy_std = 0.0
            correlation = 0.0

        area, perimeter, compactness, widths, centroid = _polygon_geometry(
            selection.polygon
        )
        locus = loci_by_label.get(selection.label)
        physics = _theory_features(centroid, selected_points, locus)
        neighbor_iou, neighbor_shared = _neighbor_features(index, masks)
        row = TrainingFeatureRow(
            measurement_id=str(measurement_id),
            selection_id=selection.selection_id,
            label=selection.label,
            target_accepted=int(selection.target_accepted),
            event_count=event_count,
            event_fraction=float(event_count / tof.size),
            tof_mean=tof_mean,
            energy_mean=energy_mean,
            tof_std=tof_std,
            energy_std=energy_std,
            tof_energy_correlation=correlation,
            polygon_area=area,
            polygon_perimeter=perimeter,
            polygon_compactness=compactness,
            polygon_tof_width=widths[0],
            polygon_energy_height=widths[1],
            polygon_centroid_tof=centroid[0],
            polygon_centroid_energy=centroid[1],
            has_theory=physics[0],
            theory_centroid_dx_fwhm=physics[1],
            theory_centroid_dy_fwhm=physics[2],
            theory_centroid_distance_fwhm=physics[3],
            event_theory_distance_median_fwhm=physics[4],
            max_neighbor_event_iou=neighbor_iou,
            max_neighbor_shared_fraction=neighbor_shared,
        )
        _require_finite_row(row)
        rows.append(row)
    return tuple(rows)


def training_rows_tsv(rows):
    """Return a deterministic tab-separated representation."""
    rows = tuple(rows)
    field_names = tuple(TrainingFeatureRow.__dataclass_fields__)
    lines = ["\t".join(field_names)]
    for row in rows:
        if not isinstance(row, TrainingFeatureRow):
            raise TypeError("Training rows must be TrainingFeatureRow objects")
        values = row.as_dict()
        lines.append("\t".join(_format_value(values[name]) for name in field_names))
    return "\n".join(lines) + "\n"


def _validated_selection(selection):
    if not isinstance(selection, AcceptedSelection):
        raise TypeError("Selections must be AcceptedSelection objects")
    if not selection.selection_id or not selection.label:
        raise ValueError("Selection id and label must be non-empty")
    if selection.target_accepted not in (0, 1):
        raise ValueError("target_accepted must be 0 or 1")
    return AcceptedSelection(
        selection_id=str(selection.selection_id),
        label=str(selection.label),
        polygon=_validated_closed_polygon(selection.polygon),
        target_accepted=int(selection.target_accepted),
    )


def _same_polygon(first, second):
    return first.shape == second.shape and np.allclose(first, second)


def _validated_closed_polygon(polygon):
    polygon = np.array(polygon, dtype=float, copy=True)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or polygon.shape[0] < 3:
        raise ValueError("Selection polygon must have shape (n, 2)")
    if not np.all(np.isfinite(polygon)):
        raise ValueError("Selection polygon must be finite")
    if not np.allclose(polygon[0], polygon[-1]):
        polygon = np.vstack((polygon, polygon[0]))
    if np.unique(polygon[:-1], axis=0).shape[0] < 3:
        raise ValueError("Selection polygon needs three distinct vertices")
    polygon.setflags(write=False)
    return polygon


def _validated_events(tof_channel, energy_channel):
    tof = np.asarray(tof_channel, dtype=float)
    energy = np.asarray(energy_channel, dtype=float)
    if tof.ndim != 1 or energy.ndim != 1 or tof.size == 0:
        raise ValueError("Event channels must be non-empty 1D arrays")
    if tof.shape != energy.shape:
        raise ValueError("ToF and Energy events must have equal length")
    if not np.all(np.isfinite(tof)) or not np.all(np.isfinite(energy)):
        raise ValueError("Event channels must be finite")
    return tof, energy


def _loci_by_label(loci):
    result = {}
    for locus in loci:
        label = str(locus.label)
        if label in result:
            raise ValueError(f"Duplicate theory locus label: {label}")
        result[label] = locus
    return result


def _polygon_geometry(polygon):
    vertices = polygon[:-1]
    next_vertices = polygon[1:]
    cross = (
        vertices[:, 0] * next_vertices[:, 1] -
        next_vertices[:, 0] * vertices[:, 1]
    )
    signed_twice_area = float(np.sum(cross))
    area = abs(signed_twice_area) / 2
    if area <= 0:
        raise ValueError("Selection polygon area must be positive")
    perimeter = float(np.sum(np.linalg.norm(
        next_vertices - vertices, axis=1
    )))
    if signed_twice_area == 0 or perimeter <= 0:
        raise ValueError("Selection polygon geometry is degenerate")
    centroid = (
        np.sum((vertices + next_vertices) * cross[:, None], axis=0) /
        (3 * signed_twice_area)
    )
    widths = np.ptp(vertices, axis=0)
    compactness = float(4 * pi * area / perimeter ** 2)
    return (
        float(area), perimeter, compactness,
        (float(widths[0]), float(widths[1])),
        (float(centroid[0]), float(centroid[1])),
    )


def _theory_features(centroid, selected_points, locus):
    if locus is None:
        return 0, 0.0, 0.0, 0.0, 0.0
    theory_tof = np.asarray(locus.tof_channel, dtype=float)
    theory_energy = np.asarray(locus.energy_channel, dtype=float)
    if (theory_tof.ndim != 1 or theory_tof.size < 2 or
            theory_tof.shape != theory_energy.shape or
            not np.all(np.isfinite(theory_tof)) or
            not np.all(np.isfinite(theory_energy))):
        raise ValueError(f"Invalid theory locus for {locus.label}")
    tof_scale = _positive_scale(
        getattr(locus, "tof_resolution_fwhm_channel", None)
    )
    energy_scale = _positive_scale(
        getattr(locus, "energy_resolution_fwhm_channel", None)
    )
    dx = (centroid[0] - theory_tof) / tof_scale
    dy = (centroid[1] - theory_energy) / energy_scale
    nearest = int(np.argmin(dx ** 2 + dy ** 2))
    centroid_dx = float(dx[nearest])
    centroid_dy = float(dy[nearest])
    centroid_distance = float(np.hypot(centroid_dx, centroid_dy))
    event_distance = _median_event_theory_distance(
        selected_points, theory_tof, theory_energy, tof_scale, energy_scale
    )
    return 1, centroid_dx, centroid_dy, centroid_distance, event_distance


def _median_event_theory_distance(
        points, theory_tof, theory_energy, tof_scale, energy_scale,
        maximum_points=2048):
    if points.size == 0:
        return 0.0
    if points.shape[0] > maximum_points:
        indexes = np.linspace(
            0, points.shape[0] - 1, maximum_points, dtype=int
        )
        points = points[indexes]
    distances = []
    for start in range(0, points.shape[0], 256):
        chunk = points[start:start + 256]
        dx = (chunk[:, None, 0] - theory_tof[None, :]) / tof_scale
        dy = (chunk[:, None, 1] - theory_energy[None, :]) / energy_scale
        distances.append(np.sqrt(np.min(dx ** 2 + dy ** 2, axis=1)))
    return float(np.median(np.concatenate(distances)))


def _positive_scale(value):
    if value is None:
        return 1.0
    value = float(value)
    return value if np.isfinite(value) and value > 0 else 1.0


def _neighbor_features(index, masks):
    own = masks[index]
    own_count = int(np.count_nonzero(own))
    max_iou = 0.0
    max_shared = 0.0
    for other_index, other in enumerate(masks):
        if other_index == index:
            continue
        intersection = int(np.count_nonzero(own & other))
        union = int(np.count_nonzero(own | other))
        if union:
            max_iou = max(max_iou, intersection / union)
        if own_count:
            max_shared = max(max_shared, intersection / own_count)
    return float(max_iou), float(max_shared)


def _require_finite_row(row):
    for name, value in row.as_dict().items():
        if isinstance(value, float) and not np.isfinite(value):
            raise ValueError(f"Training feature {name} must be finite")


def _format_value(value):
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)
