import unittest

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from modules.tofe_candidate import BananaCandidate
from modules.tofe_overlay import PROPOSAL_COLOR
from modules.tofe_overlay import draw_candidate_proposals
from modules.tofe_overlay import draw_theory_loci
from modules.tofe_theory import ChannelLocus


class TestTofeOverlay(unittest.TestCase):
    def setUp(self):
        self.figure, self.axes = plt.subplots()
        self.locus = ChannelLocus(
            label="16O",
            tof_channel=np.array([1200.0, 900.0]),
            energy_channel=np.array([300.0, 700.0]),
            maximum_recoil_energy_mev=7.0,
        )

    def tearDown(self):
        plt.close(self.figure)

    def test_draws_dashed_line_and_element_label(self):
        artists = draw_theory_loci(self.axes, [self.locus])

        self.assertEqual(len(artists), 2)
        line, annotation = artists
        np.testing.assert_allclose(line.get_xdata(), [1200.0, 900.0])
        np.testing.assert_allclose(line.get_ydata(), [300.0, 700.0])
        self.assertEqual(line.get_linestyle(), "--")
        self.assertEqual(annotation.get_text(), "16O")
        self.assertEqual(annotation.xy, (900.0, 700.0))

    def test_transposed_overlay_swaps_axes(self):
        line, annotation = draw_theory_loci(
            self.axes, [self.locus], transposed=True
        )

        np.testing.assert_allclose(line.get_xdata(), [300.0, 700.0])
        np.testing.assert_allclose(line.get_ydata(), [1200.0, 900.0])
        self.assertEqual(annotation.xy, (700.0, 900.0))

    def test_empty_overlay_creates_no_artists(self):
        self.assertEqual(draw_theory_loci(self.axes, []), ())

    def test_draws_two_dimensional_detector_resolution_band(self):
        locus = ChannelLocus(
            label="16O",
            tof_channel=np.array([1200.0, 1050.0, 900.0]),
            energy_channel=np.array([300.0, 480.0, 700.0]),
            maximum_recoil_energy_mev=7.0,
            tof_resolution_fwhm_channel=10.0,
            energy_resolution_fwhm_channel=20.0,
        )

        line, annotation, band = draw_theory_loci(self.axes, [locus])

        self.assertEqual(annotation.get_text(), "16O")
        self.assertEqual(band.get_zorder(), 3)
        self.assertLess(band.get_alpha(), line.get_alpha())
        self.assertEqual(len(band.get_xy()), 7)

    def test_transposed_resolution_band_swaps_widths(self):
        locus = ChannelLocus(
            label="16O",
            tof_channel=np.array([1200.0, 1050.0, 900.0]),
            energy_channel=np.array([300.0, 480.0, 700.0]),
            maximum_recoil_energy_mev=7.0,
            tof_resolution_fwhm_channel=10.0,
            energy_resolution_fwhm_channel=20.0,
        )

        normal_band = draw_theory_loci(self.axes, [locus])[2]
        normal_vertices = normal_band.get_xy()
        self.axes.clear()
        transposed_band = draw_theory_loci(
            self.axes, [locus], transposed=True
        )[2]
        transposed_vertices = transposed_band.get_xy()

        normal_swapped = normal_vertices[:-1, ::-1]
        transposed_open = transposed_vertices[:-1]
        normal_swapped = normal_swapped[
            np.lexsort((normal_swapped[:, 1], normal_swapped[:, 0]))
        ]
        transposed_open = transposed_open[
            np.lexsort((transposed_open[:, 1], transposed_open[:, 0]))
        ]
        np.testing.assert_allclose(
            normal_swapped, transposed_open
        )

    def test_draws_visually_distinct_candidate_with_confidence(self):
        candidate = self._candidate()

        fill, outline, ridge, annotation = draw_candidate_proposals(
            self.axes, [candidate]
        )

        self.assertEqual(fill.get_alpha(), 0.18)
        self.assertEqual(outline.get_color(), PROPOSAL_COLOR)
        self.assertEqual(outline.get_linestyle(), ":")
        self.assertEqual(ridge.get_linestyle(), "-.")
        self.assertEqual(annotation.get_text(), "16O 83% proposed")
        self.assertEqual(annotation.xy, (3.0, 4.0))
        np.testing.assert_allclose(
            outline.get_xydata(), candidate.polygon
        )
        np.testing.assert_allclose(ridge.get_xydata(), candidate.ridge)

    def test_transposed_candidate_swaps_polygon_and_ridge_axes(self):
        candidate = self._candidate()

        _, outline, ridge, annotation = draw_candidate_proposals(
            self.axes, [candidate], transposed=True
        )

        np.testing.assert_allclose(
            outline.get_xydata(), candidate.polygon[:, ::-1]
        )
        np.testing.assert_allclose(
            ridge.get_xydata(), candidate.ridge[:, ::-1]
        )
        self.assertEqual(annotation.xy, (4.0, 3.0))

    def test_empty_candidate_overlay_creates_no_artists(self):
        self.assertEqual(draw_candidate_proposals(self.axes, []), ())

    def test_candidate_overlay_rejects_nonfinite_coordinates(self):
        candidate = self._candidate()
        invalid = BananaCandidate(
            label=candidate.label,
            polygon=np.array([[0.0, 0.0], [np.nan, 1.0], [0.0, 0.0]]),
            ridge=candidate.ridge,
            confidence=candidate.confidence,
            coverage=candidate.coverage,
            contrast=candidate.contrast,
            theory_adherence=candidate.theory_adherence,
        )

        with self.assertRaisesRegex(ValueError, "finite"):
            draw_candidate_proposals(self.axes, [invalid])

    def test_candidate_overlay_rejects_invalid_confidence(self):
        candidate = self._candidate()
        invalid = BananaCandidate(
            label=candidate.label,
            polygon=candidate.polygon,
            ridge=candidate.ridge,
            confidence=1.1,
            coverage=candidate.coverage,
            contrast=candidate.contrast,
            theory_adherence=candidate.theory_adherence,
        )

        with self.assertRaisesRegex(ValueError, "confidence"):
            draw_candidate_proposals(self.axes, [invalid])

    @staticmethod
    def _candidate():
        return BananaCandidate(
            label="16O",
            polygon=np.array([
                [0.0, 0.0], [2.0, 3.0], [3.0, 5.0],
                [2.0, 5.0], [1.0, 2.0], [0.0, 0.0],
            ]),
            ridge=np.array([[0.5, 1.0], [2.0, 3.0], [3.0, 4.0]]),
            confidence=0.834,
            coverage=0.9,
            contrast=0.8,
            theory_adherence=0.7,
        )


if __name__ == "__main__":
    unittest.main()
