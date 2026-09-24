import unittest

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

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


if __name__ == "__main__":
    unittest.main()
