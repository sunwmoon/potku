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
from typing import Callable
from typing import Optional
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
    recoil_energy_mev: Optional[np.ndarray] = None
    flight_energy_mev: Optional[np.ndarray] = None

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
    tof_resolution_fwhm_channel: float = None
    energy_resolution_fwhm_channel: float = None


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
    return IdealLocus(
        energy_mev=energies,
        tof_seconds=times,
        maximum_recoil_energy_mev=maximum_energy,
        recoil_energy_mev=energies,
        flight_energy_mev=energies,
    )


def calculate_foil_aware_locus(
        beam_mass_u, beam_energy_mev, recoil_mass_u, recoil_angle_deg,
        flight_length_m,
        first_foil_loss: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        downstream_loss: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        minimum_energy_fraction=0.08, point_count=300):
    """Calculate a locus with separate recoil, flight, and detector energies.

    ``first_foil_loss`` receives the recoil energy before the upstream timing
    foil. ``downstream_loss`` receives the energy after that foil and covers
    material between the ToF section and the active energy detector. Both
    callbacks return a positive energy loss in MeV for every input energy.

    ToF is calculated from the energy between the timing foils, whereas the
    histogram energy axis uses the energy reaching the active detector. This
    distinction is required before a JIBAL-backed foil stopping model can be
    connected without conflating the two histogram coordinates.
    """
    ideal = calculate_ideal_locus(
        beam_mass_u=beam_mass_u,
        beam_energy_mev=beam_energy_mev,
        recoil_mass_u=recoil_mass_u,
        recoil_angle_deg=recoil_angle_deg,
        flight_length_m=flight_length_m,
        minimum_energy_fraction=minimum_energy_fraction,
        point_count=point_count,
    )
    recoil_energy = ideal.recoil_energy_mev
    first_loss = _evaluate_energy_loss(
        first_foil_loss, recoil_energy, "First timing-foil energy loss"
    )
    flight_energy = recoil_energy - first_loss
    _validate_remaining_energy(
        flight_energy, "First timing-foil energy loss"
    )

    later_loss = _evaluate_energy_loss(
        downstream_loss, flight_energy, "Downstream energy loss"
    )
    detector_energy = flight_energy - later_loss
    _validate_remaining_energy(detector_energy, "Downstream energy loss")

    return IdealLocus(
        energy_mev=detector_energy,
        tof_seconds=time_of_flight(
            flight_energy, recoil_mass_u, flight_length_m
        ),
        maximum_recoil_energy_mev=ideal.maximum_recoil_energy_mev,
        recoil_energy_mev=recoil_energy,
        flight_energy_mev=flight_energy,
    )


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
    tof_resolution_fwhm_channel = _resolution_in_channels(
        getattr(detector, "timeres", None),
        1e-12,
        tof_calibration,
        "Time resolution",
    )
    energy_resolution_fwhm_channel = _resolution_in_channels(
        getattr(detector, "energyres", None),
        1e-3,
        energy_calibration,
        "Energy resolution",
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
            tof_resolution_fwhm_channel=(
                tof_resolution_fwhm_channel
            ),
            energy_resolution_fwhm_channel=(
                energy_resolution_fwhm_channel
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


def _resolution_in_channels(value, unit_to_physical, calibration,
                            description):
    """Convert an optional detector FWHM to an absolute channel width."""
    if value is None:
        return None
    resolution = _number(value, description)
    if resolution < 0:
        raise ValueError(f"{description} cannot be negative")
    return abs(resolution * unit_to_physical / calibration.slope)


def _number(value, description):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{description} must be a finite number") from error
    if not np.isfinite(number):
        raise ValueError(f"{description} must be a finite number")
    return number


def _evaluate_energy_loss(loss_function, incident_energy, description):
    """Evaluate and validate an optional vectorized energy-loss callback."""
    if loss_function is None:
        return np.zeros_like(incident_energy)
    try:
        loss = np.asarray(loss_function(incident_energy), dtype=float)
        loss = np.broadcast_to(loss, incident_energy.shape)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{description} must return one finite value per energy"
        ) from error
    if not np.all(np.isfinite(loss)):
        raise ValueError(f"{description} must be finite")
    if np.any(loss < 0):
        raise ValueError(f"{description} cannot be negative")
    return loss


def _validate_remaining_energy(energy, description):
    if np.any(energy <= 0):
        raise ValueError(
            f"{description} must leave positive particle energy"
        )
