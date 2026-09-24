"""Non-persistent banana candidates guided by theoretical ToF-E loci."""

from dataclasses import dataclass
from math import exp
from typing import Iterable
from typing import Optional
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class CandidateSearchSettings:
    """Controls local ridge detection around a theoretical locus."""

    sample_count: int = 60
    search_radius_fwhm: float = 2.0
    polygon_half_width_fwhm: float = 1.0
    fallback_width_bins: float = 3.0
    minimum_peak_sigma: float = 2.5
    minimum_coverage: float = 0.4
    minimum_confidence: float = 0.25

    def __post_init__(self):
        if self.sample_count < 3:
            raise ValueError("Candidate search requires at least three samples")
        for name in (
                "search_radius_fwhm", "polygon_half_width_fwhm",
                "fallback_width_bins", "minimum_peak_sigma"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("minimum_coverage", "minimum_confidence"):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in the range [0, 1]")


@dataclass(frozen=True)
class BananaCandidate:
    """Editable polygon proposal that has not been accepted or saved."""

    label: str
    polygon: np.ndarray
    ridge: np.ndarray
    confidence: float
    coverage: float
    contrast: float
    theory_adherence: float


def propose_banana_candidates(
        histogram, x_edges, y_edges, loci: Iterable,
        settings=CandidateSearchSettings()) -> Tuple[BananaCandidate, ...]:
    """Return qualifying proposals for several theory loci.

    ``histogram`` uses image convention ``histogram[y_bin, x_bin]``. The
    returned objects are plain NumPy data and are never added to Potku's
    selector. A later GUI layer must require explicit acceptance before
    converting a proposal into a real selection.
    """
    histogram, x_centers, y_centers, x_bin_width, y_bin_width = \
        _validated_histogram(histogram, x_edges, y_edges)
    candidates = []
    for locus in loci:
        candidate = _propose_for_locus(
            histogram, x_centers, y_centers, x_bin_width, y_bin_width,
            locus, settings,
        )
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _propose_for_locus(
        histogram, x_centers, y_centers, x_bin_width, y_bin_width,
        locus, settings) -> Optional[BananaCandidate]:
    theory_x = _validated_locus_axis(locus.tof_channel, "ToF", locus.label)
    theory_y = _validated_locus_axis(
        locus.energy_channel, "Energy", locus.label
    )
    if theory_x.shape != theory_y.shape:
        raise ValueError(
            f"{locus.label} ToF and Energy channel arrays must match"
        )

    sample_indexes = np.unique(np.linspace(
        0, theory_x.size - 1,
        min(settings.sample_count, theory_x.size),
        dtype=int,
    ))
    if sample_indexes.size < 3:
        return None
    anchors_x = theory_x[sample_indexes]
    anchors_y = theory_y[sample_indexes]

    fwhm_x = _search_width(
        getattr(locus, "tof_resolution_fwhm_channel", None),
        x_bin_width, settings.fallback_width_bins,
    )
    fwhm_y = _search_width(
        getattr(locus, "energy_resolution_fwhm_channel", None),
        y_bin_width, settings.fallback_width_bins,
    )
    radius_x = settings.search_radius_fwhm * fwhm_x
    radius_y = settings.search_radius_fwhm * fwhm_y
    tangent_x = np.gradient(anchors_x) / fwhm_x
    tangent_y = np.gradient(anchors_y) / fwhm_y
    tangent_magnitude = np.hypot(tangent_x, tangent_y)
    if np.any(tangent_magnitude == 0):
        return None
    tangent_x /= tangent_magnitude
    tangent_y /= tangent_magnitude

    detected_x = np.full(sample_indexes.size, np.nan)
    detected_y = np.full(sample_indexes.size, np.nan)
    contrasts = np.zeros(sample_indexes.size)
    shifts = np.full(sample_indexes.size, np.nan)
    valid = np.zeros(sample_indexes.size, dtype=bool)

    for index, (anchor_x, anchor_y) in enumerate(
            zip(anchors_x, anchors_y)):
        x_indexes = np.flatnonzero(
            np.abs(x_centers - anchor_x) <= radius_x
        )
        y_indexes = np.flatnonzero(
            np.abs(y_centers - anchor_y) <= radius_y
        )
        if not x_indexes.size or not y_indexes.size:
            continue

        xx, yy = np.meshgrid(
            x_centers[x_indexes], y_centers[y_indexes]
        )
        offset_x = (xx - anchor_x) / fwhm_x
        offset_y = (yy - anchor_y) / fwhm_y
        along_tangent = (
            offset_x * tangent_x[index] + offset_y * tangent_y[index]
        )
        across_normal = (
            -offset_x * tangent_y[index] + offset_y * tangent_x[index]
        )
        inside = (
            (np.abs(along_tangent) <= 0.75) &
            (np.abs(across_normal) <= settings.search_radius_fwhm)
        )
        if not np.any(inside):
            continue

        window = histogram[np.ix_(y_indexes, x_indexes)]
        values = window[inside]
        background = float(np.median(values))
        threshold = background + settings.minimum_peak_sigma * np.sqrt(
            background + 1
        )
        # Penalize motion along the banana so adjacent anchors do not all
        # select the same equally high ridge bin. Motion normal to the theory
        # line remains free within the configured search radius.
        peak_score = window * np.exp(-0.5 * (along_tangent / 0.5) ** 2)
        masked_score = np.where(inside, peak_score, -np.inf)
        flat_peak = int(np.argmax(masked_score))
        peak_y, peak_x = np.unravel_index(flat_peak, masked_score.shape)
        peak = float(window[peak_y, peak_x])
        if peak <= threshold:
            continue

        ridge_x = x_centers[x_indexes[peak_x]]
        ridge_y = y_centers[y_indexes[peak_y]]
        detected_x[index] = ridge_x
        detected_y[index] = ridge_y
        contrasts[index] = (peak - background) / (peak + background + 1)
        shifts[index] = np.hypot(
            (ridge_x - anchor_x) / fwhm_x,
            (ridge_y - anchor_y) / fwhm_y,
        )
        valid[index] = True

    coverage = float(np.mean(valid))
    valid_indexes = np.flatnonzero(valid)
    if valid_indexes.size < 3 or coverage < settings.minimum_coverage:
        return None

    first, last = valid_indexes[0], valid_indexes[-1]
    proposal_indexes = np.arange(first, last + 1)
    ridge_x = np.interp(proposal_indexes, valid_indexes, detected_x[valid])
    ridge_y = np.interp(proposal_indexes, valid_indexes, detected_y[valid])
    ridge = np.column_stack((ridge_x, ridge_y))

    contrast = float(np.mean(contrasts[valid]))
    theory_adherence = exp(-0.5 * float(np.median(shifts[valid] ** 2)))
    confidence = float(np.clip(
        coverage * (0.65 * contrast + 0.35 * theory_adherence), 0, 1
    ))
    if confidence < settings.minimum_confidence:
        return None

    polygon = _ridge_polygon(
        ridge_x, ridge_y,
        fwhm_x * settings.polygon_half_width_fwhm / 2,
        fwhm_y * settings.polygon_half_width_fwhm / 2,
    )
    if polygon is None:
        return None
    return BananaCandidate(
        label=str(locus.label),
        polygon=polygon,
        ridge=ridge,
        confidence=confidence,
        coverage=coverage,
        contrast=contrast,
        theory_adherence=theory_adherence,
    )


def _validated_histogram(histogram, x_edges, y_edges):
    histogram = np.asarray(histogram, dtype=float)
    x_edges = np.asarray(x_edges, dtype=float)
    y_edges = np.asarray(y_edges, dtype=float)
    if histogram.ndim != 2:
        raise ValueError("Histogram must be a 2D array")
    if histogram.shape != (y_edges.size - 1, x_edges.size - 1):
        raise ValueError(
            "Histogram shape must match (y bins, x bins)"
        )
    if not np.all(np.isfinite(histogram)) or np.any(histogram < 0):
        raise ValueError("Histogram counts must be finite and non-negative")
    for edges, axis in ((x_edges, "x"), (y_edges, "y")):
        if edges.ndim != 1 or edges.size < 2:
            raise ValueError(f"{axis} edges must be a 1D array")
        if not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
            raise ValueError(f"{axis} edges must be finite and increasing")
    return (
        histogram,
        (x_edges[:-1] + x_edges[1:]) / 2,
        (y_edges[:-1] + y_edges[1:]) / 2,
        float(np.median(np.diff(x_edges))),
        float(np.median(np.diff(y_edges))),
    )


def _validated_locus_axis(values, axis, label):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size < 3:
        raise ValueError(f"{label} {axis} locus needs at least three points")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{label} {axis} locus must be finite")
    return values


def _search_width(resolution, bin_width, fallback_width_bins):
    if resolution is None:
        return fallback_width_bins * bin_width
    resolution = float(resolution)
    if not np.isfinite(resolution) or resolution <= 0:
        return fallback_width_bins * bin_width
    return max(resolution, bin_width)


def _ridge_polygon(x_values, y_values, half_x, half_y):
    if x_values.size < 3:
        return None
    tangent_x = np.gradient(x_values) / half_x
    tangent_y = np.gradient(y_values) / half_y
    magnitude = np.hypot(tangent_x, tangent_y)
    if np.any(magnitude == 0):
        return None
    offset_x = half_x * (-tangent_y / magnitude)
    offset_y = half_y * (tangent_x / magnitude)
    upper = np.column_stack((x_values + offset_x, y_values + offset_y))
    lower = np.column_stack((x_values - offset_x, y_values - offset_y))
    return np.vstack((upper, lower[::-1], upper[0]))
