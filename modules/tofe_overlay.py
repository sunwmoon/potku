"""Matplotlib helpers for non-persistent ToF-E theory overlays."""

from typing import Iterable

import numpy as np


def draw_theory_loci(axes, loci: Iterable, transposed=False):
    """Draw labeled theory loci without creating Potku selections.

    Args:
        axes: Matplotlib axes receiving the artists.
        loci: Iterable of ``ChannelLocus``-compatible objects.
        transposed: Swap the time and energy axes when ``True``.

    Returns:
        A tuple containing the created line and annotation artists. Keeping
        the artists separate from Potku's selector makes the overlay purely
        visual and prevents it from being saved as an accepted selection.
    """
    artists = []
    for locus in loci:
        if transposed:
            x_values = locus.energy_channel
            y_values = locus.tof_channel
            x_fwhm = getattr(
                locus, "energy_resolution_fwhm_channel", None
            )
            y_fwhm = getattr(locus, "tof_resolution_fwhm_channel", None)
        else:
            x_values = locus.tof_channel
            y_values = locus.energy_channel
            x_fwhm = getattr(locus, "tof_resolution_fwhm_channel", None)
            y_fwhm = getattr(
                locus, "energy_resolution_fwhm_channel", None
            )

        line, = axes.plot(
            x_values,
            y_values,
            linestyle="--",
            linewidth=1.4,
            alpha=0.9,
            zorder=4,
        )
        annotation = axes.annotate(
            locus.label,
            xy=(x_values[-1], y_values[-1]),
            xytext=(4, 4),
            textcoords="offset points",
            color=line.get_color(),
            fontsize=9,
            fontweight="bold",
            zorder=5,
        )
        artists.extend((line, annotation))

        resolution_polygon = _resolution_polygon(
            x_values, y_values, x_fwhm, y_fwhm
        )
        if resolution_polygon is not None:
            polygon_x, polygon_y = resolution_polygon
            band, = axes.fill(
                polygon_x,
                polygon_y,
                color=line.get_color(),
                alpha=0.16,
                linewidth=0,
                zorder=3,
            )
            artists.append(band)

    return tuple(artists)


def _resolution_polygon(x_values, y_values, x_fwhm, y_fwhm):
    """Return a one-half-FWHM ribbon normal to a parametric center line.

    The normal is calculated after scaling each axis by its detector
    resolution. This produces a two-dimensional uncertainty ribbon instead
    of showing only the energy or only the time contribution.
    """
    if x_fwhm is None or y_fwhm is None:
        return None
    if not np.isfinite(x_fwhm) or not np.isfinite(y_fwhm):
        return None
    if x_fwhm <= 0 or y_fwhm <= 0:
        return None

    x_values = np.asarray(x_values, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    if x_values.size < 2 or y_values.shape != x_values.shape:
        return None

    half_x = x_fwhm / 2
    half_y = y_fwhm / 2
    tangent_x = np.gradient(x_values) / half_x
    tangent_y = np.gradient(y_values) / half_y
    magnitude = np.hypot(tangent_x, tangent_y)
    if np.any(magnitude == 0):
        return None

    offset_x = half_x * (-tangent_y / magnitude)
    offset_y = half_y * (tangent_x / magnitude)
    upper_x = x_values + offset_x
    upper_y = y_values + offset_y
    lower_x = x_values - offset_x
    lower_y = y_values - offset_y
    return (
        np.concatenate((upper_x, lower_x[::-1])),
        np.concatenate((upper_y, lower_y[::-1])),
    )
