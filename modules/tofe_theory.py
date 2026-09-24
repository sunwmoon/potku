"""Theoretical recoil loci for a ToF-E histogram.

This module intentionally has no Qt dependencies.  It provides the ideal
two-body ERD kinematics used by the first theory-overlay prototype.  Stopping
in the target and detector foils will be layered on top of these calculations
instead of being hidden in the plotting code.
"""

from dataclasses import dataclass
from math import cos
from math import pi
import re
from typing import Sequence
from typing import Tuple

import numpy as np


ATOMIC_MASS_UNIT_KG = 1.660_539_066_60e-27
MEV_TO_JOULE = 1.602_176_634e-13
_ELEMENT_TOKEN = re.compile(r"^(?:[1-9][0-9]{0,2})?[A-Z][a-z]?$")


@dataclass(frozen=True)
class LinearCalibration:
    """Linear mapping ``physical = slope * channel + offset``."""

    slope: float
    offset: float = 0.0

    def physical_to_channel(self, values):
        if self.slope == 0:
            raise ValueError("Calibration slope cannot be zero")
        return (np.asarray(values, dtype=float) - self.offset) / self.slope


@dataclass(frozen=True)
class IdealLocus:
    """One recoil isotope's ideal ToF-E center line."""

    energy_mev: np.ndarray
    tof_seconds: np.ndarray
    maximum_recoil_energy_mev: float

    def as_channels(self, tof_calibration, energy_calibration):
        """Return ``(tof_channel, energy_channel)`` arrays."""
        return (
            tof_calibration.physical_to_channel(self.tof_seconds),
            energy_calibration.physical_to_channel(self.energy_mev),
        )


@dataclass(frozen=True)
class ChannelLocus:
    """Plot-ready theoretical locus with a Potku element label."""

    label: str
    tof_channel: np.ndarray
    energy_channel: np.ndarray
    maximum_recoil_energy_mev: float


@dataclass(frozen=True)
class TheoryPredictionSettings:
    """User-controlled inputs that are not stored in a Potku measurement."""

    element_tokens: Tuple[str, ...]
    energy_calibration: LinearCalibration
    minimum_energy_fraction: float = 0.08
    point_count: int = 300

    def __post_init__(self):
        if not self.element_tokens:
            raise ValueError("At least one recoil element is required")
        if not np.isfinite(self.energy_calibration.slope) or \
                self.energy_calibration.slope == 0:
            raise ValueError(
                "Energy calibration slope must be finite and non-zero"
            )
        if not np.isfinite(self.energy_calibration.offset):
            raise ValueError("Energy calibration offset must be finite")
        if not 0 < self.minimum_energy_fraction <= 1:
            raise ValueError(
                "Minimum energy fraction must be in the range (0, 1]"
            )
        if self.point_count < 2:
            raise ValueError("At least two locus points are required")

    @classmethod
    def from_text(cls, element_text, energy_slope_mev_per_channel,
                  energy_offset_mev=0.0, minimum_energy_fraction=0.08,
                  point_count=300):
        """Parse comma/whitespace-separated isotope symbols into settings."""
        tokens = tuple(filter(None, re.split(r"[\s,]+", element_text.strip())))
        invalid = [
            token for token in tokens
            if not _ELEMENT_TOKEN.fullmatch(token)
        ]
        if invalid:
            raise ValueError(
                "Invalid recoil element notation: " + ", ".join(invalid)
            )
        if len(tokens) != len(set(tokens)):
            raise ValueError("Recoil element list contains duplicates")
        return cls(
            element_tokens=tokens,
            energy_calibration=LinearCalibration(
                float(energy_slope_mev_per_channel),
                float(energy_offset_mev),
            ),
            minimum_energy_fraction=float(minimum_energy_fraction),
            point_count=int(point_count),
        )


def recoil_kinematic_factor(beam_mass_u, recoil_mass_u, recoil_angle_deg):
    """Return the ideal ERD recoil factor ``E_recoil / E_beam``."""
    if beam_mass_u <= 0 or recoil_mass_u <= 0:
        raise ValueError("Ion masses must be positive")
    if not 0 <= recoil_angle_deg < 90:
        raise ValueError("Recoil angle must be in the range [0, 90) degrees")
    angle = recoil_angle_deg * pi / 180
    return (4 * beam_mass_u * recoil_mass_u * cos(angle) ** 2 /
            (beam_mass_u + recoil_mass_u) ** 2)


def time_of_flight(energy_mev, mass_u, flight_length_m):
    """Calculate non-relativistic flight time in seconds."""
    energy_mev = np.asarray(energy_mev, dtype=float)
    if np.any(energy_mev <= 0):
        raise ValueError("Particle energy must be positive")
    if mass_u <= 0 or flight_length_m <= 0:
        raise ValueError("Mass and flight length must be positive")
    velocity = np.sqrt(
        2 * energy_mev * MEV_TO_JOULE /
        (mass_u * ATOMIC_MASS_UNIT_KG)
    )
    return flight_length_m / velocity


def calculate_ideal_locus(beam_mass_u, beam_energy_mev, recoil_mass_u,
                          recoil_angle_deg, flight_length_m,
                          minimum_energy_fraction=0.08, point_count=300):
    """Calculate an ideal recoil center line from low energy to the surface edge.

    ``minimum_energy_fraction`` only defines the displayed lower end.  It does
    not represent a target-depth or detector-efficiency calculation.
    """
    if beam_energy_mev <= 0:
        raise ValueError("Beam energy must be positive")
    if not 0 < minimum_energy_fraction <= 1:
        raise ValueError("Minimum energy fraction must be in the range (0, 1]")
    if point_count < 2:
        raise ValueError("At least two locus points are required")

    factor = recoil_kinematic_factor(
        beam_mass_u, recoil_mass_u, recoil_angle_deg
    )
    maximum_energy = factor * beam_energy_mev
    energies = np.linspace(
        maximum_energy * minimum_energy_fraction,
        maximum_energy,
        point_count,
    )
    times = time_of_flight(energies, recoil_mass_u, flight_length_m)
    return IdealLocus(energies, times, maximum_energy)


def calculate_loci_for_measurement(
        measurement, recoil_elements: Sequence,
        energy_calibration: LinearCalibration,
        minimum_energy_fraction=0.08, point_count=300
) -> Tuple[ChannelLocus, ...]:
    """Build plot-ready ideal loci from a Potku ``Measurement``.

    Beam ion, beam energy, detector angle, timing-foil distance, and ToF
    calibration are read from the measurement's existing settings. Potku does
    not currently persist an energy-channel calibration, so callers must pass
    that calibration explicitly.

    The returned labels use :meth:`Element.get_prefix`, for example ``16O``.
    No selections are created or saved by this function.
    """
    try:
        beam = measurement.run.beam
        detector = measurement.detector
    except AttributeError as error:
        raise ValueError(
            "Measurement must provide run.beam and detector settings"
        ) from error

    beam_mass_u = _element_mass(beam.ion, "beam ion")
    beam_energy_mev = _positive_number(beam.energy, "Beam energy")
    flight_length_m = _positive_number(
        detector.calculate_tof_length(), "ToF flight length"
    )
    recoil_angle_deg = _number(detector.detector_theta, "Detector angle")
    tof_calibration = LinearCalibration(
        _number(detector.tof_slope, "ToF calibration slope"),
        _number(detector.tof_offset, "ToF calibration offset"),
    )

    loci = []
    for element in recoil_elements:
        recoil_mass_u = _element_mass(element, "recoil element")
        try:
            label = element.get_prefix()
        except AttributeError as error:
            raise ValueError(
                "Recoil elements must provide get_prefix()"
            ) from error

        ideal_locus = calculate_ideal_locus(
            beam_mass_u=beam_mass_u,
            beam_energy_mev=beam_energy_mev,
            recoil_mass_u=recoil_mass_u,
            recoil_angle_deg=recoil_angle_deg,
            flight_length_m=flight_length_m,
            minimum_energy_fraction=minimum_energy_fraction,
            point_count=point_count,
        )
        tof_channel, energy_channel = ideal_locus.as_channels(
            tof_calibration, energy_calibration
        )
        loci.append(ChannelLocus(
            label=label,
            tof_channel=tof_channel,
            energy_channel=energy_channel,
            maximum_recoil_energy_mev=(
                ideal_locus.maximum_recoil_energy_mev
            ),
        ))

    return tuple(loci)


def calculate_loci_from_settings(measurement, settings, element_factory):
    """Create elements from validated settings and calculate channel loci.

    ``element_factory`` is explicit so this Qt-independent module does not
    load Potku's JIBAL-backed mass tables at import time. Production callers
    pass ``Element.from_string``; tests can use lightweight element objects.
    """
    elements = tuple(
        element_factory(token) for token in settings.element_tokens
    )
    return calculate_loci_for_measurement(
        measurement,
        elements,
        settings.energy_calibration,
        minimum_energy_fraction=settings.minimum_energy_fraction,
        point_count=settings.point_count,
    )


def _element_mass(element, description):
    try:
        mass = element.get_mass()
    except AttributeError as error:
        raise ValueError(
            f"{description.capitalize()} must provide get_mass()"
        ) from error
    return _positive_number(mass, f"{description.capitalize()} mass")


def _positive_number(value, description):
    number = _number(value, description)
    if number <= 0:
        raise ValueError(f"{description} must be positive")
    return number


def _number(value, description):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{description} must be a finite number") from error
    if not np.isfinite(number):
        raise ValueError(f"{description} must be a finite number")
    return number
