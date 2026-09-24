import unittest

import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import propose_banana_candidates
from modules.tofe_theory import ChannelLocus


class TestTofeCandidate(unittest.TestCase):
    def setUp(self):
        self.x_edges = np.arange(0.0, 101.0, 1.0)
        self.y_edges = np.arange(0.0, 101.0, 1.0)
        self.x_centers = (self.x_edges[:-1] + self.x_edges[1:]) / 2
        self.y_centers = (self.y_edges[:-1] + self.y_edges[1:]) / 2
        theory_x = np.linspace(20.0, 80.0, 61)
        theory_y = 0.6 * theory_x + 10.0
        self.locus = ChannelLocus(
            label="16O",
            tof_channel=theory_x,
            energy_channel=theory_y,
            maximum_recoil_energy_mev=10.0,
            tof_resolution_fwhm_channel=4.0,
            energy_resolution_fwhm_channel=6.0,
        )
        self.settings = CandidateSearchSettings(
            sample_count=31,
            minimum_confidence=0.2,
        )

    def synthetic_histogram(self, y_shift=0.0):
        xx, yy = np.meshgrid(self.x_centers, self.y_centers)
        ridge_y = 0.6 * xx + 10.0 + y_shift
        return 2.0 + 80.0 * np.exp(-0.5 * ((yy - ridge_y) / 1.4) ** 2)

    def test_detects_ridge_and_returns_closed_editable_polygon(self):
        candidates = propose_banana_candidates(
            self.synthetic_histogram(),
            self.x_edges,
            self.y_edges,
            [self.locus],
            self.settings,
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.label, "16O")
        self.assertGreater(candidate.confidence, 0.5)
        self.assertGreater(candidate.coverage, 0.9)
        self.assertEqual(candidate.ridge.shape[1], 2)
        self.assertEqual(candidate.polygon.shape[1], 2)
        np.testing.assert_allclose(candidate.polygon[0], candidate.polygon[-1])
        expected_y = 0.6 * candidate.ridge[:, 0] + 10.0
        np.testing.assert_allclose(
            candidate.ridge[:, 1], expected_y, atol=1.0
        )

    def test_ridge_follows_shifted_measured_banana(self):
        shifted_candidates = propose_banana_candidates(
            self.synthetic_histogram(y_shift=4.0),
            self.x_edges,
            self.y_edges,
            [self.locus],
            self.settings,
        )

        self.assertEqual(len(shifted_candidates), 1)
        candidate = shifted_candidates[0]
        measured_y = 0.6 * candidate.ridge[:, 0] + 14.0
        np.testing.assert_allclose(
            candidate.ridge[:, 1], measured_y, atol=1.0
        )
        self.assertLess(candidate.theory_adherence, 1.0)
        aligned = propose_banana_candidates(
            self.synthetic_histogram(),
            self.x_edges,
            self.y_edges,
            [self.locus],
            self.settings,
        )[0]
        self.assertLess(candidate.confidence, aligned.confidence)

    def test_flat_background_produces_no_candidate(self):
        candidates = propose_banana_candidates(
            np.full((100, 100), 5.0),
            self.x_edges,
            self.y_edges,
            [self.locus],
            self.settings,
        )

        self.assertEqual(candidates, ())

    def test_missing_resolution_uses_bin_based_fallback(self):
        locus = ChannelLocus(
            label="12C",
            tof_channel=self.locus.tof_channel,
            energy_channel=self.locus.energy_channel,
            maximum_recoil_energy_mev=8.0,
        )

        candidates = propose_banana_candidates(
            self.synthetic_histogram(),
            self.x_edges,
            self.y_edges,
            [locus],
            self.settings,
        )

        self.assertEqual(len(candidates), 1)

    def test_rejects_histogram_shape_mismatch(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            propose_banana_candidates(
                np.zeros((99, 100)),
                self.x_edges,
                self.y_edges,
                [self.locus],
            )


if __name__ == "__main__":
    unittest.main()
