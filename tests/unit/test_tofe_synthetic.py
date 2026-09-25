import unittest

import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import build_candidate_histogram
from modules.tofe_candidate import propose_banana_candidates
from modules.tofe_candidate_metrics import evaluate_candidate_truth
from modules.tofe_candidate_metrics import summarize_candidate_metrics
from modules.tofe_synthetic import TofeGeometry
from modules.tofe_synthetic import generate_synthetic_events


class TestTofeSynthetic(unittest.TestCase):
    def test_tandem_energy_and_geometry_closure(self):
        geometry = TofeGeometry()

        self.assertAlmostEqual(geometry.beam_energy_mev, 11.4)
        self.assertAlmostEqual(geometry.geometry_closure_deg, 30.0)
        self.assertAlmostEqual(geometry.geometry_mismatch_deg, 0.0)

    def test_injection_energy_is_kept_as_parameter(self):
        geometry = TofeGeometry(injection_energy_mev=0.03)

        self.assertAlmostEqual(geometry.beam_energy_mev, 11.43)

    def test_invalid_angles_are_rejected(self):
        with self.assertRaises(ValueError):
            TofeGeometry(recoil_angle_deg=90.0)
        with self.assertRaises(ValueError):
            TofeGeometry(incidence_angle_deg=-1.0)

    def test_synthetic_events_are_reproducible_and_include_background(self):
        first = generate_synthetic_events(
            events_per_locus=20, background_events=17, seed=3
        )
        second = generate_synthetic_events(
            events_per_locus=20, background_events=17, seed=3
        )

        self.assertEqual(first.tof_channel.size, 97)
        self.assertEqual(np.sum(first.truth_label == "background"), 17)
        np.testing.assert_array_equal(first.tof_channel, second.tof_channel)
        np.testing.assert_array_equal(first.energy_channel, second.energy_channel)

    def test_default_synthetic_spectrum_yields_all_element_candidates(self):
        dataset = generate_synthetic_events(
            events_per_locus=5000,
            background_events=5000,
            seed=20260925,
            channel_shifts={
                "1H": (2.0, -5.0),
                "12C": (-1.5, 7.0),
                "16O": (1.0, 5.0),
                "28Si": (-2.0, -6.0),
            },
        )
        grid = build_candidate_histogram(
            dataset.tof_channel,
            dataset.energy_channel,
            tof_compression=2.0,
            energy_compression=8.0,
            max_bin_count=1200,
        )
        candidates = propose_banana_candidates(
            grid.counts,
            grid.tof_edges,
            grid.energy_edges,
            dataset.loci,
            CandidateSearchSettings(
                sample_count=60,
                search_radius_fwhm=2.0,
                polygon_half_width_fwhm=1.6,
                minimum_peak_sigma=2.0,
                minimum_coverage=0.35,
                minimum_confidence=0.18,
            ),
        )

        self.assertEqual(
            {candidate.label for candidate in candidates},
            {"1H", "12C", "16O", "28Si"},
        )
        for candidate in candidates:
            self.assertGreater(candidate.coverage, 0.5)
            self.assertGreater(candidate.confidence, 0.3)
            np.testing.assert_allclose(
                candidate.polygon[0], candidate.polygon[-1]
            )
        metrics = evaluate_candidate_truth(
            candidates,
            dataset.tof_channel,
            dataset.energy_channel,
            dataset.truth_label,
            expected_labels=[locus.label for locus in dataset.loci],
        )
        summary = summarize_candidate_metrics(metrics)
        self.assertEqual(summary.detected_labels, 4)
        self.assertGreater(summary.precision, 0.98)
        self.assertGreater(summary.recall, 0.80)
        self.assertGreater(summary.event_iou, 0.80)


if __name__ == "__main__":
    unittest.main()
