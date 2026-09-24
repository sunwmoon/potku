import unittest

import numpy as np

from modules.tofe_report import build_theory_report_rows
from modules.tofe_report import format_theory_report_tsv
from modules.tofe_theory import ChannelLocus


class TestTofeReport(unittest.TestCase):
    def test_report_contains_both_endpoints_and_prediction_state(self):
        locus = ChannelLocus(
            label="16O",
            tof_channel=np.array([950.25, 500.5, 320.125]),
            energy_channel=np.array([100.0, 600.0, 1200.75]),
            maximum_recoil_energy_mev=12.5,
            tof_resolution_fwhm_channel=4.2,
            energy_resolution_fwhm_channel=25.0,
            prediction_mode="Foil-corrected",
        )

        row = build_theory_report_rows([locus])[0]

        self.assertEqual(row.element, "16O")
        self.assertEqual(row.mode, "Foil-corrected")
        self.assertEqual(row.low_tof_channel, 950.25)
        self.assertEqual(row.low_energy_channel, 100.0)
        self.assertEqual(row.surface_tof_channel, 320.125)
        self.assertEqual(row.surface_energy_channel, 1200.75)
        self.assertEqual(row.maximum_recoil_energy_mev, 12.5)

    def test_report_preserves_fallback_reason_and_blank_resolutions(self):
        locus = ChannelLocus(
            label="2H",
            tof_channel=np.array([100.0, 50.0]),
            energy_channel=np.array([25.0, 200.0]),
            maximum_recoil_energy_mev=2.0,
            prediction_mode="Ideal",
            prediction_warning="jibaltool unavailable\nusing ideal",
        )

        text = format_theory_report_tsv(build_theory_report_rows([locus]))

        self.assertIn("2H\tIdeal\t100\t25\t50\t200\t2\t\t\t", text)
        self.assertIn('"jibaltool unavailable\nusing ideal"', text)

    def test_report_rejects_mismatched_or_nonfinite_channels(self):
        invalid_loci = (
            ChannelLocus(
                "1H", np.array([1.0]), np.array([1.0, 2.0]), 1.0
            ),
            ChannelLocus(
                "1H", np.array([np.nan]), np.array([1.0]), 1.0
            ),
        )
        for locus in invalid_loci:
            with self.subTest(locus=locus):
                with self.assertRaises(ValueError):
                    build_theory_report_rows([locus])

    def test_empty_report_still_has_header(self):
        text = format_theory_report_tsv(build_theory_report_rows([]))

        self.assertTrue(text.startswith("element\tmode\t"))
        self.assertEqual(len(text.splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
