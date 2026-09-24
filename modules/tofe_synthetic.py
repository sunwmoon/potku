"""Synthetic ToF-ERD data for physics-guided selection development.

The generator is deliberately independent of Qt and Potku measurement files.
It provides a reproducible substitute while measured ``.asc`` data are not
available, and keeps every assumed geometry value explicit.
"""

from dataclasses import dataclass
from typing import Mapping
from typing import Sequence
from typing import Tuple

import numpy as np

from modules.tofe_theory import ChannelLocus
from modules.tofe_theory import LinearCalibration
from modules.tofe_theory import calculate_ideal_locus


DEFAULT_RECOILS = (
    ("1H", 1.007_825),
    ("12C", 12.0),
    ("16O", 15.994_915),
    ("28Si", 27.976_927),
)


@dataclass(frozen=True)
class TofeGeometry:
    """Configurable geometry and calibration for a synthetic ToF-ERD run.

    Incidence and exit angles are measured from the sample surface normal.
    With both angles at 75 degrees in a coplanar reflection geometry, the
    angle between the incident beam direction and outgoing recoil direction
    is 30 degrees.
    """

    terminal_voltage_mv: float = 1.9
    output_charge_state: int = 5
    injected_ion_charge_magnitude: int = 1
    injection_energy_mev: float = 0.0
    beam_label: str = "35Cl5+"
    beam_mass_u: float = 34.968_853
    recoil_angle_deg: float = 30.0
    incidence_angle_deg: float = 75.0
    exit_angle_deg: float = 75.0
    flight_length_m: float = 0.5
    tof_slope_seconds_per_channel: float = 0.1e-9
    tof_offset_seconds: float = 0.0
    energy_slope_mev_per_channel: float = 0.0025
    energy_offset_mev: float = 0.0
    time_resolution_fwhm_ns: float = 0.7
    energy_resolution_fwhm_mev: float = 0.08

    def __post_init__(self):
        positive = (
            ("terminal voltage", self.terminal_voltage_mv),
            ("beam mass", self.beam_mass_u),
            ("flight length", self.flight_length_m),
            ("ToF calibration slope", self.tof_slope_seconds_per_channel),
            ("energy calibration slope", self.energy_slope_mev_per_channel),
            ("time resolution", self.time_resolution_fwhm_ns),
            ("energy resolution", self.energy_resolution_fwhm_mev),
        )
        for name, value in positive:
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.output_charge_state < 1:
            raise ValueError("Output charge state must be positive")
        if self.injected_ion_charge_magnitude < 1:
            raise ValueError("Injected ion charge magnitude must be positive")
        if not np.isfinite(self.injection_energy_mev) or \
                self.injection_energy_mev < 0:
            raise ValueError("Injection energy must be finite and non-negative")
        if not 0 <= self.recoil_angle_deg < 90:
            raise ValueError("Recoil angle must be in the range [0, 90)")
        for name in ("incidence_angle_deg", "exit_angle_deg"):
            angle = getattr(self, name)
            if not np.isfinite(angle) or not 0 <= angle < 90:
                raise ValueError(
                    f"{name} must be finite and in the range [0, 90)"
                )

    @property
    def beam_energy_mev(self):
        """Nominal tandem output energy.

        A singly negative injected ion gains one terminal-voltage increment
        before stripping and ``q`` increments after stripping.  Injection
        energy is retained as a separate term because accelerator settings may
        provide it independently.
        """
        charge_gain = (
            self.injected_ion_charge_magnitude + self.output_charge_state
        )
        return (
            charge_gain * self.terminal_voltage_mv + self.injection_energy_mev
        )

    @property
    def geometry_closure_deg(self):
        """Coplanar reflection recoil angle implied by incidence and exit."""
        return 180.0 - self.incidence_angle_deg - self.exit_angle_deg

    @property
    def geometry_mismatch_deg(self):
        return self.geometry_closure_deg - self.recoil_angle_deg


@dataclass(frozen=True)
class SyntheticDataset:
    """Generated event channels and their simulation-only truth labels."""

    tof_channel: np.ndarray
    energy_channel: np.ndarray
    truth_label: np.ndarray
    loci: Tuple[ChannelLocus, ...]
    geometry: TofeGeometry


def calculate_synthetic_loci(
        geometry=TofeGeometry(), recoil_species=DEFAULT_RECOILS,
        minimum_energy_fraction=0.12, point_count=400):
    """Calculate ideal channel-space loci for explicit recoil species."""
    tof_calibration = LinearCalibration(
        geometry.tof_slope_seconds_per_channel,
        geometry.tof_offset_seconds,
    )
    energy_calibration = LinearCalibration(
        geometry.energy_slope_mev_per_channel,
        geometry.energy_offset_mev,
    )
    loci = []
    for label, mass_u in recoil_species:
        locus = calculate_ideal_locus(
            beam_mass_u=geometry.beam_mass_u,
            beam_energy_mev=geometry.beam_energy_mev,
            recoil_mass_u=float(mass_u),
            recoil_angle_deg=geometry.recoil_angle_deg,
            flight_length_m=geometry.flight_length_m,
            minimum_energy_fraction=minimum_energy_fraction,
            point_count=point_count,
        )
        tof_channel, energy_channel = locus.as_channels(
            tof_calibration, energy_calibration
        )
        loci.append(ChannelLocus(
            label=str(label),
            tof_channel=tof_channel,
            energy_channel=energy_channel,
            maximum_recoil_energy_mev=locus.maximum_recoil_energy_mev,
            tof_resolution_fwhm_channel=(
                geometry.time_resolution_fwhm_ns * 1e-9 /
                geometry.tof_slope_seconds_per_channel
            ),
            energy_resolution_fwhm_channel=(
                geometry.energy_resolution_fwhm_mev /
                geometry.energy_slope_mev_per_channel
            ),
            prediction_mode="Synthetic ideal",
        ))
    return tuple(loci)


def generate_synthetic_events(
        geometry=TofeGeometry(), recoil_species=DEFAULT_RECOILS,
        events_per_locus=5000, background_events=5000, seed=20260925,
        channel_shifts: Mapping[str, Tuple[float, float]] = None,
        minimum_energy_fraction=0.12) -> SyntheticDataset:
    """Generate broadened banana events plus uniform detector background.

    ``channel_shifts`` maps an isotope label to ``(ToF, Energy)`` offsets in
    channels.  They mimic calibration and stopping-model mismatch so the
    selector must follow the measured ridge instead of copying the theory line.
    """
    if not isinstance(events_per_locus, (int, np.integer)) or \
            events_per_locus < 1:
        raise ValueError("Events per locus must be a positive integer")
    if not isinstance(background_events, (int, np.integer)) or \
            background_events < 0:
        raise ValueError("Background event count cannot be negative")
    loci = calculate_synthetic_loci(
        geometry, recoil_species, minimum_energy_fraction
    )
    rng = np.random.default_rng(seed)
    shifts = {} if channel_shifts is None else dict(channel_shifts)
    tof_parts = []
    energy_parts = []
    label_parts = []
    for locus in loci:
        # Bias the distribution mildly toward the surface endpoint while
        # retaining events along the full displayed banana.
        position = rng.beta(1.2, 0.9, events_per_locus)
        source_axis = np.linspace(0.0, 1.0, locus.tof_channel.size)
        center_tof = np.interp(position, source_axis, locus.tof_channel)
        center_energy = np.interp(
            position, source_axis, locus.energy_channel
        )
        shift_tof, shift_energy = shifts.get(locus.label, (0.0, 0.0))
        sigma_tof = locus.tof_resolution_fwhm_channel / 2.354_82
        sigma_energy = locus.energy_resolution_fwhm_channel / 2.354_82
        tof_parts.append(
            center_tof + float(shift_tof) +
            rng.normal(0.0, sigma_tof, events_per_locus)
        )
        energy_parts.append(
            center_energy + float(shift_energy) +
            rng.normal(0.0, sigma_energy, events_per_locus)
        )
        label_parts.append(np.full(events_per_locus, locus.label, dtype="U16"))

    all_theory_tof = np.concatenate([l.tof_channel for l in loci])
    all_theory_energy = np.concatenate([l.energy_channel for l in loci])
    tof_margin = max(l.tof_resolution_fwhm_channel for l in loci) * 5
    energy_margin = max(l.energy_resolution_fwhm_channel for l in loci) * 5
    if background_events:
        tof_parts.append(rng.uniform(
            np.min(all_theory_tof) - tof_margin,
            np.max(all_theory_tof) + tof_margin,
            background_events,
        ))
        energy_parts.append(rng.uniform(
            max(0.0, np.min(all_theory_energy) - energy_margin),
            np.max(all_theory_energy) + energy_margin,
            background_events,
        ))
        label_parts.append(np.full(background_events, "background", dtype="U16"))

    tof = np.concatenate(tof_parts)
    energy = np.concatenate(energy_parts)
    labels = np.concatenate(label_parts)
    order = rng.permutation(tof.size)
    return SyntheticDataset(
        tof_channel=tof[order],
        energy_channel=energy[order],
        truth_label=labels[order],
        loci=loci,
        geometry=geometry,
    )
