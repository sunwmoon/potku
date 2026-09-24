import unittest
from unittest import mock

import numpy as np

from modules.tofe_stopping import CarbonStoppingInterpolator
from modules.tofe_stopping import MEV_TO_JOULE
from modules.tofe_stopping import StoppingCalculationError


class TestCarbonStoppingInterpolator(unittest.TestCase):
    def test_interpolates_scalar_backend_into_vector_loss(self):
        backend = FakeStoppingBackend(lambda energy: 0.01 * energy)
        stopping = CarbonStoppingInterpolator(
            "O", 16, 13.0, 2.27, sample_count=5, backend=backend
        )

        energy = np.geomspace(1.0, 9.0, 9)
        loss = stopping(energy)

        np.testing.assert_allclose(loss, 0.01 * energy)
        self.assertEqual(backend.call_count, 5)
        self.assertEqual(loss.shape, energy.shape)

    def test_reuses_grid_for_repeated_and_narrower_ranges(self):
        backend = FakeStoppingBackend(lambda energy: 0.02)
        stopping = CarbonStoppingInterpolator(
            "H", 1, 10.0, 2.0, sample_count=4, backend=backend
        )

        stopping(np.array([1.0, 10.0]))
        first_call_count = backend.call_count
        stopping(np.array([2.0, 5.0, 8.0]))

        self.assertEqual(first_call_count, 4)
        self.assertEqual(backend.call_count, first_call_count)

    def test_preserves_scalar_and_multidimensional_shapes(self):
        backend = FakeStoppingBackend(lambda energy: 0.01)
        stopping = CarbonStoppingInterpolator(
            "He", 4, 10.0, 2.0, sample_count=3, backend=backend
        )

        self.assertEqual(stopping(2.0).shape, ())
        np.testing.assert_allclose(stopping.sampled_energies_mev, [2.0])
        self.assertEqual(stopping(np.ones((2, 3)) * 2).shape, (2, 3))

    def test_default_backend_requests_quiet_strict_jibal_result(self):
        with mock.patch(
                "modules.tofe_stopping.gf.carbon_stopping",
                return_value=0.01 * MEV_TO_JOULE) as backend:
            stopping = CarbonStoppingInterpolator(
                "O", 16, 13.0, 2.27, sample_count=2
            )
            np.testing.assert_allclose(stopping(1.0), 0.01)

        backend.assert_called_once_with(
            "O", 16, 1.0, 13.0, 2.27, verbose=False, strict=True
        )

    def test_wraps_backend_failure_with_energy_context(self):
        def failing_backend(*args):
            raise OSError("jibaltool is unavailable")

        stopping = CarbonStoppingInterpolator(
            "O", 16, 13.0, 2.27, backend=failing_backend
        )

        with self.assertRaisesRegex(
                StoppingCalculationError,
                r"failed at 1 MeV: jibaltool is unavailable"):
            stopping(np.array([1.0, 2.0]))

    def test_rejects_invalid_or_energy_exhausting_loss(self):
        invalid_losses = (np.nan, -0.1, 2.0)
        for loss in invalid_losses:
            with self.subTest(loss=loss):
                backend = FakeStoppingBackend(lambda energy, value=loss: value)
                stopping = CarbonStoppingInterpolator(
                    "O", 16, 13.0, 2.27, sample_count=2,
                    backend=backend,
                )
                with self.assertRaises(StoppingCalculationError):
                    stopping(np.array([1.0, 2.0]))


class FakeStoppingBackend:
    def __init__(self, loss_mev):
        self.loss_mev = loss_mev
        self.call_count = 0

    def __call__(self, element, isotope, energy, thickness, density):
        self.call_count += 1
        return self.loss_mev(energy) * MEV_TO_JOULE


if __name__ == "__main__":
    unittest.main()
