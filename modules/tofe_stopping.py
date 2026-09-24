"""Efficient stopping adapters for the theoretical ToF-E overlay.

The existing :func:`general_functions.carbon_stopping` interface launches
``jibaltool`` for one energy at a time.  A full locus contains hundreds of
points, so this module samples a small grid and interpolates it.  It is kept
separate from the GUI so failures can leave the existing ideal overlay intact.
"""

from typing import Callable
from typing import Optional

import numpy as np

from . import general_functions as gf


MEV_TO_JOULE = 1.602_176_634e-13


class StoppingCalculationError(RuntimeError):
    """Raised when a stopping backend cannot produce a usable loss table."""


class CarbonStoppingInterpolator:
    """Vectorized, cached interpolation over scalar JIBAL calculations.

    The scalar backend follows ``carbon_stopping`` and returns joules.  The
    callable adapter accepts and returns MeV arrays, making it directly usable
    as a loss callback for ``calculate_foil_aware_locus``.
    """

    def __init__(self, element_symbol: str, isotope: int,
                 thickness_nm: float, density_g_cm3: float,
                 sample_count: int = 24,
                 backend: Optional[Callable] = None):
        if not element_symbol:
            raise ValueError("Element symbol is required")
        if isotope is None or int(isotope) <= 0:
            raise ValueError("A positive isotope mass number is required")
        if not np.isfinite(thickness_nm) or thickness_nm <= 0:
            raise ValueError("Carbon foil thickness must be positive")
        if not np.isfinite(density_g_cm3) or density_g_cm3 <= 0:
            raise ValueError("Carbon foil density must be positive")
        if sample_count < 2:
            raise ValueError("At least two stopping samples are required")

        self.element_symbol = element_symbol
        self.isotope = int(isotope)
        self.thickness_nm = float(thickness_nm)
        self.density_g_cm3 = float(density_g_cm3)
        self.sample_count = int(sample_count)
        self._backend = backend or self._quiet_jibal_stopping
        self._sample_cache = {}
        self._grid_energy_mev = None
        self._grid_loss_mev = None

    def __call__(self, energy_mev):
        """Return interpolated carbon-foil energy loss in MeV."""
        energy = np.asarray(energy_mev, dtype=float)
        if not np.all(np.isfinite(energy)) or np.any(energy <= 0):
            raise ValueError("Incident energy must be finite and positive")

        original_shape = energy.shape
        flat_energy = energy.reshape(-1)
        minimum = float(np.min(flat_energy))
        maximum = float(np.max(flat_energy))
        self._ensure_grid(minimum, maximum)

        loss = np.interp(
            flat_energy, self._grid_energy_mev, self._grid_loss_mev
        )
        if np.any(loss >= flat_energy):
            raise StoppingCalculationError(
                "Carbon stopping must leave positive particle energy"
            )
        return loss.reshape(original_shape)

    @property
    def sampled_energies_mev(self):
        """Return a copy of the currently cached interpolation grid."""
        if self._grid_energy_mev is None:
            return np.array([], dtype=float)
        return self._grid_energy_mev.copy()

    def _ensure_grid(self, minimum, maximum):
        if self._grid_energy_mev is not None and \
                self._grid_energy_mev[0] <= minimum and \
                self._grid_energy_mev[-1] >= maximum:
            return

        if minimum == maximum:
            grid = np.array([minimum], dtype=float)
        else:
            grid = np.geomspace(minimum, maximum, self.sample_count)

        losses = np.array(
            [self._sample_loss(sample) for sample in grid], dtype=float
        )
        self._grid_energy_mev = grid
        self._grid_loss_mev = losses

    def _sample_loss(self, energy_mev):
        key = float(energy_mev)
        if key in self._sample_cache:
            return self._sample_cache[key]
        try:
            loss_joule = self._backend(
                self.element_symbol,
                self.isotope,
                key,
                self.thickness_nm,
                self.density_g_cm3,
            )
            loss_mev = float(loss_joule) / MEV_TO_JOULE
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            raise StoppingCalculationError(
                f"Carbon stopping failed at {key:.6g} MeV: {error}"
            ) from error

        if not np.isfinite(loss_mev) or loss_mev < 0:
            raise StoppingCalculationError(
                f"Carbon stopping returned an invalid loss at "
                f"{key:.6g} MeV"
            )
        if loss_mev >= key:
            raise StoppingCalculationError(
                f"Carbon stopping exhausts the particle energy at "
                f"{key:.6g} MeV"
            )
        self._sample_cache[key] = loss_mev
        return loss_mev

    @staticmethod
    def _quiet_jibal_stopping(element, isotope, energy, thickness, density):
        return gf.carbon_stopping(
            element, isotope, energy, thickness, density,
            verbose=False, strict=True,
        )
