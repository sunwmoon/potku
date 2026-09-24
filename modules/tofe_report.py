"""Inspection and export helpers for transient ToF-E theory overlays."""

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable
from typing import Optional
from typing import Tuple

import numpy as np


REPORT_HEADERS = (
    "element",
    "mode",
    "low_tof_channel",
    "low_energy_channel",
    "surface_tof_channel",
    "surface_energy_channel",
    "maximum_recoil_energy_mev",
    "tof_fwhm_channel",
    "energy_fwhm_channel",
    "fallback_reason",
)


@dataclass(frozen=True)
class TheoryReportRow:
    """One inspectable summary row for a calculated channel locus."""

    element: str
    mode: str
    low_tof_channel: float
    low_energy_channel: float
    surface_tof_channel: float
    surface_energy_channel: float
    maximum_recoil_energy_mev: float
    tof_fwhm_channel: Optional[float]
    energy_fwhm_channel: Optional[float]
    fallback_reason: str


def build_theory_report_rows(loci: Iterable) -> Tuple[TheoryReportRow, ...]:
    """Summarize locus endpoints without creating or changing selections.

    Loci are generated from low recoil energy to the surface recoil edge, so
    index zero is the displayed low-energy endpoint and index minus one is the
    predicted surface endpoint.
    """
    rows = []
    for locus in loci:
        tof = _validated_channels(locus.tof_channel, "ToF", locus.label)
        energy = _validated_channels(
            locus.energy_channel, "Energy", locus.label
        )
        if tof.shape != energy.shape:
            raise ValueError(
                f"{locus.label} ToF and Energy channel arrays must match"
            )

        rows.append(TheoryReportRow(
            element=str(locus.label),
            mode=str(locus.prediction_mode),
            low_tof_channel=float(tof[0]),
            low_energy_channel=float(energy[0]),
            surface_tof_channel=float(tof[-1]),
            surface_energy_channel=float(energy[-1]),
            maximum_recoil_energy_mev=_finite_float(
                locus.maximum_recoil_energy_mev,
                f"{locus.label} maximum recoil energy",
            ),
            tof_fwhm_channel=_optional_finite_float(
                locus.tof_resolution_fwhm_channel,
                f"{locus.label} ToF resolution",
            ),
            energy_fwhm_channel=_optional_finite_float(
                locus.energy_resolution_fwhm_channel,
                f"{locus.label} energy resolution",
            ),
            fallback_reason=str(locus.prediction_warning or ""),
        ))
    return tuple(rows)


def format_theory_report_tsv(rows: Iterable[TheoryReportRow]) -> str:
    """Return a deterministic, spreadsheet-ready TSV report."""
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(REPORT_HEADERS)
    for row in rows:
        writer.writerow((
            row.element,
            row.mode,
            _format_float(row.low_tof_channel),
            _format_float(row.low_energy_channel),
            _format_float(row.surface_tof_channel),
            _format_float(row.surface_energy_channel),
            _format_float(row.maximum_recoil_energy_mev),
            _format_optional_float(row.tof_fwhm_channel),
            _format_optional_float(row.energy_fwhm_channel),
            row.fallback_reason,
        ))
    return output.getvalue()


def _validated_channels(values, axis_name, label):
    channels = np.asarray(values, dtype=float)
    if channels.ndim != 1 or channels.size == 0:
        raise ValueError(
            f"{label} {axis_name} channels must be a non-empty 1D array"
        )
    if not np.all(np.isfinite(channels)):
        raise ValueError(f"{label} {axis_name} channels must be finite")
    return channels


def _finite_float(value, description):
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"{description} must be finite")
    return value


def _optional_finite_float(value, description):
    if value is None:
        return None
    return _finite_float(value, description)


def _format_float(value):
    return format(value, ".12g")


def _format_optional_float(value):
    return "" if value is None else _format_float(value)
