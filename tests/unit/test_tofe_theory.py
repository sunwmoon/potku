import unittest
from types import SimpleNamespace

import numpy as np

from modules.tofe_theory import calculate_loci_for_measurement
from modules.tofe_theory import calculate_loci_from_settings
from modules.tofe_theory import LinearCalibration
from modules.tofe_theory import TheoryPredictionSettings
from modules.tofe_theory import calculate_ideal_locus
from modules.tofe_theory import calculate_foil_aware_locus
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

    def test_foil_aware_locus_separates_flight_and_detector_energy(self):
        locus = calculate_foil_aware_locus(
            beam_mass_u=4,
            beam_energy_mev=10,
            recoil_mass_u=4,
            recoil_angle_deg=0,
            flight_length_m=1,
            first_foil_loss=lambda energy: np.full_like(energy, 0.5),
            downstream_loss=lambda energy: np.full_like(energy, 1.0),
            minimum_energy_fraction=0.5,
            point_count=3,
        )

        np.testing.assert_allclose(locus.recoil_energy_mev, [5.0, 7.5, 10.0])
        np.testing.assert_allclose(locus.flight_energy_mev, [4.5, 7.0, 9.5])
        np.testing.assert_allclose(locus.energy_mev, [3.5, 6.0, 8.5])
        np.testing.assert_allclose(
            locus.tof_seconds,
            time_of_flight(locus.flight_energy_mev, 4, 1),
        )

    def test_zero_foil_loss_matches_ideal_locus(self):
        ideal = calculate_ideal_locus(127, 30, 16, 40, 0.623, point_count=4)
        foil_aware = calculate_foil_aware_locus(
            127, 30, 16, 40, 0.623, point_count=4
        )

        np.testing.assert_allclose(foil_aware.energy_mev, ideal.energy_mev)
        np.testing.assert_allclose(
            foil_aware.tof_seconds, ideal.tof_seconds
        )

    def test_foil_loss_rejects_nonphysical_results(self):
        invalid_losses = (
            lambda energy: -np.ones_like(energy),
            lambda energy: energy,
            lambda energy: np.full_like(energy, np.nan),
        )
        for loss_function in invalid_losses:
            with self.subTest(loss_function=loss_function):
                with self.assertRaises(ValueError):
                    calculate_foil_aware_locus(
                        4, 10, 4, 0, 1,
                        first_foil_loss=loss_function,
                        point_count=3,
                    )

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
        self.assertAlmostEqual(
            loci[1].tof_resolution_fwhm_channel, 5.0
        )
        self.assertAlmostEqual(
            loci[1].energy_resolution_fwhm_channel, 2.5
        )

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

    def test_prediction_settings_parse_elements_and_calibration(self):
        settings = TheoryPredictionSettings.from_text(
            "1H, 2H 16O", 0.002, -0.1, 0.2, 25
        )

        self.assertEqual(settings.element_tokens, ("1H", "2H", "16O"))
        self.assertEqual(settings.energy_calibration.slope, 0.002)
        self.assertEqual(settings.energy_calibration.offset, -0.1)
        self.assertEqual(settings.minimum_energy_fraction, 0.2)
        self.assertEqual(settings.point_count, 25)

    def test_prediction_settings_reject_invalid_or_duplicate_elements(self):
        for element_text in ("", "oxygen", "16O, 16O", "0H"):
            with self.subTest(element_text=element_text):
                with self.assertRaises(ValueError):
                    TheoryPredictionSettings.from_text(element_text, 0.001)

    def test_prediction_settings_reject_zero_energy_slope(self):
        with self.assertRaises(ValueError):
            TheoryPredictionSettings.from_text("1H", 0.0)

    def test_measurement_adapter_rejects_negative_resolution(self):
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(
                    ion=FakeElement("127I", 126.904_473), energy=30
                )
            ),
            detector=FakeDetector(timeres=-1),
        )

        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            calculate_loci_for_measurement(
                measurement,
                [FakeElement("16O", 15.994_915)],
                LinearCalibration(0.01),
            )

    def test_calculate_loci_from_settings_uses_element_factory(self):
        beam_ion = FakeElement("127I", 126.904_473)
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(ion=beam_ion, energy=30)
            ),
            detector=FakeDetector(
                detector_theta=40, tof_slope=1e-10,
                tof_offset=2e-9, tof_length=0.5,
            ),
        )
        settings = TheoryPredictionSettings.from_text(
            "1H, 16O", 0.001, point_count=4
        )
        elements = {
            "1H": FakeElement("1H", 1.0078),
            "16O": FakeElement("16O", 15.995),
        }

        loci = calculate_loci_from_settings(
            measurement, settings, elements.__getitem__
        )

        self.assertEqual([locus.label for locus in loci], ["1H", "16O"])
        self.assertEqual(loci[0].tof_channel.shape, (4,))

    def test_measurement_adapter_uses_foil_losses_when_available(self):
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(
                    ion=FakeElement("127I", 126.904_473), energy=30
                )
            ),
            detector=FakeDetector(),
        )
        recoil = FakeElement("16O", 15.994_915)

        loci = calculate_loci_for_measurement(
            measurement,
            [recoil],
            LinearCalibration(0.01),
            minimum_energy_fraction=0.5,
            point_count=3,
            foil_loss_factory=lambda detector, element: (
                lambda energy: np.full_like(energy, 0.1),
                lambda energy: np.full_like(energy, 0.2),
            ),
        )

        self.assertEqual(loci[0].prediction_mode, "Foil-corrected")
        self.assertIsNone(loci[0].prediction_warning)

    def test_measurement_adapter_falls_back_to_ideal_on_stopping_error(self):
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(
                    ion=FakeElement("127I", 126.904_473), energy=30
                )
            ),
            detector=FakeDetector(),
        )
        recoil = FakeElement("16O", 15.994_915)

        loci = calculate_loci_for_measurement(
            measurement,
            [recoil],
            LinearCalibration(0.01),
            point_count=3,
            foil_loss_factory=lambda detector, element: (_ for _ in ()).throw(
                RuntimeError("jibaltool unavailable")
            ),
        )

        self.assertEqual(loci[0].prediction_mode, "Ideal")
        self.assertEqual(
            loci[0].prediction_warning, "jibaltool unavailable"
        )

    def test_settings_can_disable_detector_foil_correction(self):
        measurement = SimpleNamespace(
            run=SimpleNamespace(
                beam=SimpleNamespace(
                    ion=FakeElement("127I", 126.904_473), energy=30
                )
            ),
            detector=FakeDetector(),
        )
        settings = TheoryPredictionSettings.from_text(
            "16O", 0.001, point_count=3, use_detector_foils=False
        )
        factory = unittest.mock.Mock()

        loci = calculate_loci_from_settings(
            measurement,
            settings,
            lambda token: FakeElement(token, 15.994_915),
            foil_loss_factory=factory,
        )

        factory.assert_not_called()
        self.assertEqual(loci[0].prediction_mode, "Ideal")


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
                 tof_offset=-1e-9, tof_length=0.623, timeres=500,
                 energyres=25):
        self.detector_theta = detector_theta
        self.tof_slope = tof_slope
        self.tof_offset = tof_offset
        self.tof_length = tof_length
        self.timeres = timeres
        self.energyres = energyres

    def calculate_tof_length(self):
        return self.tof_length


if __name__ == "__main__":
    unittest.main()
