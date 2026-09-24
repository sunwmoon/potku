"""Matplotlib helpers for non-persistent ToF-E theory overlays."""

from typing import Iterable


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
        else:
            x_values = locus.tof_channel
            y_values = locus.energy_channel

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

    return tuple(artists)
