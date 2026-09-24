import unittest

import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import build_candidate_histogram
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

    def test_builds_energy_row_tof_column_histogram_from_events(self):
        grid = build_candidate_histogram(
            tof_channels=[0.0, 0.2, 1.0, 1.2],
            energy_channels=[10.0, 10.2, 11.0, 11.2],
            tof_compression=0.5,
            energy_compression=0.5,
        )

        self.assertEqual(grid.counts.shape, (2, 2))
        np.testing.assert_allclose(grid.counts, [[2.0, 0.0], [0.0, 2.0]])
        self.assertEqual(grid.tof_edges.size, 3)
        self.assertEqual(grid.energy_edges.size, 3)
        self.assertEqual(np.sum(grid.counts), 4)

    def test_histogram_builder_caps_bins_and_handles_constant_axis(self):
        grid = build_candidate_histogram(
            tof_channels=[0.0, 100.0],
            energy_channels=[5.0, 5.0],
            tof_compression=0.01,
            energy_compression=1.0,
            max_bin_count=20,
        )

        self.assertEqual(grid.counts.shape, (1, 20))
        self.assertEqual(np.sum(grid.counts), 2)

    def test_histogram_builder_rejects_invalid_raw_events(self):
        invalid_arguments = (
            ([1.0], [1.0, 2.0], 1.0, 1.0),
            ([1.0, np.nan], [1.0, 2.0], 1.0, 1.0),
            ([1.0], [1.0], 0.0, 1.0),
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    build_candidate_histogram(*arguments)

    def test_raw_events_to_candidate_end_to_end(self):
        rng = np.random.default_rng(42)
        tof = np.repeat(np.linspace(20.0, 80.0, 61), 20)
        tof = tof + rng.normal(0.0, 0.3, tof.size)
        energy = 0.6 * tof + 10.0 + rng.normal(0.0, 1.0, tof.size)
        tof = np.concatenate((tof, rng.uniform(10.0, 90.0, 300)))
        energy = np.concatenate((
            energy, rng.uniform(10.0, 70.0, 300)
        ))
        grid = build_candidate_histogram(tof, energy, 1.0, 1.0)

        candidates = propose_banana_candidates(
            grid.counts,
            grid.tof_edges,
            grid.energy_edges,
            [self.locus],
            CandidateSearchSettings(
                sample_count=31, minimum_confidence=0.15
            ),
        )

        self.assertEqual(len(candidates), 1)
        self.assertGreater(candidates[0].confidence, 0.8)
        self.assertGreater(candidates[0].coverage, 0.9)


if __name__ == "__main__":
    unittest.main()
