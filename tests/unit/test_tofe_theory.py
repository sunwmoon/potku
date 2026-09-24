import unittest
from types import SimpleNamespace

import numpy as np

from modules.tofe_theory import calculate_loci_for_measurement
from modules.tofe_theory import LinearCalibration
from modules.tofe_theory import calculate_ideal_locus
from modules.tofe_theory import recoil_kinematic_factor
from modules.tofe_theory import time_of_flight


class TestTofeTheory(unittest.TestCase):
    def test_equal_mass_forward_recoil_transfers_all_energy(self):
        self.assertAlmostEqual(recoil_kinematic_factor(4, 4, 0), 1.0)

    def test_recoil_factor_rejects_nonphysical_angle(self):
        with self.assertRaises(ValueError):
            recoil_kinematic_factor(127, 16, 90)

    def test_time_of_flight_scales_with_inverse_square_root_energy(self):
        times = time_of_flight(np.array([1.0, 4.0]), 1.0, 1.0)
        self.assertAlmostEqual(times[0] / times[1], 2.0)

    def test_locus_ends_at_surface_recoil_energy(self):
        locus = calculate_ideal_locus(4, 10, 4, 0, 1, point_count=5)
        self.assertAlmostEqual(locus.maximum_recoil_energy_mev, 10.0)
        self.assertAlmostEqual(locus.energy_mev[-1], 10.0)
        self.assertTrue(np.all(np.diff(locus.tof_seconds) < 0))

    def test_channel_conversion_uses_detector_calibrations(self):
        locus = calculate_ideal_locus(4, 10, 4, 0, 1, point_count=2)
        tof_channel, energy_channel = locus.as_channels(
            LinearCalibration(1e-9, 0), LinearCalibration(0.01, 0)
        )
        np.testing.assert_allclose(energy_channel, [80, 1000])
        self.assertEqual(tof_channel.shape, (2,))

    def test_measurement_adapter_reads_existing_potku_settings(self):
        beam_ion = FakeElement("127I", 126.904_473)
        detector = FakeDetector(
            detector_theta=40, tof_slope=1e-10, tof_offset=2e-9,
            tof_length=0.623,
        )
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(ion=beam_ion, energy=30)
            ),
            detector=detector,
        )

        loci = calculate_loci_for_measurement(
            measurement,
            [FakeElement("1H", 1.007_825),
             FakeElement("16O", 15.994_915)],
            LinearCalibration(0.01, 0.5),
            minimum_energy_fraction=0.5,
            point_count=3,
        )

        self.assertEqual([locus.label for locus in loci], ["1H", "16O"])
        self.assertEqual(loci[0].tof_channel.shape, (3,))
        expected = calculate_ideal_locus(
            beam_mass_u=beam_ion.get_mass(),
            beam_energy_mev=30,
            recoil_mass_u=15.994_915,
            recoil_angle_deg=40,
            flight_length_m=detector.calculate_tof_length(),
            minimum_energy_fraction=0.5,
            point_count=3,
        )
        expected_tof, expected_energy = expected.as_channels(
            LinearCalibration(1e-10, 2e-9),
            LinearCalibration(0.01, 0.5),
        )
        np.testing.assert_allclose(loci[1].tof_channel, expected_tof)
        np.testing.assert_allclose(loci[1].energy_channel, expected_energy)

    def test_measurement_adapter_rejects_unknown_recoil_mass(self):
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(
                    ion=FakeElement("127I", 126.904_473), energy=30
                )
            ),
            detector=FakeDetector(),
        )
        with self.assertRaisesRegex(ValueError, "Recoil element mass"):
            calculate_loci_for_measurement(
                measurement, [FakeElement("Xx", None)],
                LinearCalibration(0.01)
            )


class FakeElement:
    """Minimal implementation of the Element interface used by the adapter."""

    def __init__(self, prefix, mass):
        self.prefix = prefix
        self.mass = mass

    def get_mass(self):
        return self.mass

    def get_prefix(self):
        return self.prefix


class FakeDetector:
    """Minimal implementation of settings read from Potku's Detector."""

    def __init__(self, detector_theta=41, tof_slope=5.8e-11,
                 tof_offset=-1e-9, tof_length=0.623):
        self.detector_theta = detector_theta
        self.tof_slope = tof_slope
        self.tof_offset = tof_offset
        self.tof_length = tof_length

    def calculate_tof_length(self):
        return self.tof_length


if __name__ == "__main__":
    unittest.main()
