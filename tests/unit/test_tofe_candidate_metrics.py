import unittest
from types import SimpleNamespace

import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import build_candidate_histogram
from modules.tofe_candidate import propose_banana_candidates
from modules.tofe_candidate_metrics import evaluate_candidate_truth
from modules.tofe_candidate_metrics import points_inside_polygon
from modules.tofe_candidate_metrics import summarize_candidate_metrics
from modules.tofe_synthetic import calculate_synthetic_loci
from modules.tofe_synthetic import generate_synthetic_events


def candidate(label, polygon):
    return SimpleNamespace(label=label, polygon=np.asarray(polygon, dtype=float))


SQUARE = np.array([
    [0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]
])


class TestTofeCandidateMetrics(unittest.TestCase):
    @staticmethod
    def detect(dataset, loci=None):
        grid = build_candidate_histogram(
            dataset.tof_channel,
            dataset.energy_channel,
            tof_compression=2.0,
            energy_compression=8.0,
            max_bin_count=1200,
        )
        return propose_banana_candidates(
            grid.counts,
            grid.tof_edges,
            grid.energy_edges,
            dataset.loci if loci is None else loci,
            CandidateSearchSettings(
                sample_count=60,
                search_radius_fwhm=2.0,
                polygon_half_width_fwhm=1.6,
                minimum_peak_sigma=2.0,
                minimum_coverage=0.35,
                minimum_confidence=0.18,
            ),
        )

    def test_point_mask_handles_inside_and_outside_events(self):
        mask = points_inside_polygon(
            [[5.0, 5.0], [-1.0, 5.0], [11.0, 5.0]], SQUARE
        )

        np.testing.assert_array_equal(mask, [True, False, False])

    def test_perfect_polygon_has_unit_metrics(self):
        rows = evaluate_candidate_truth(
            [candidate("16O", SQUARE)],
            [2.0, 8.0, 20.0],
            [2.0, 8.0, 20.0],
            ["16O", "16O", "background"],
            expected_labels=["16O"],
        )

        row = rows[0]
        self.assertTrue(row.detected)
        self.assertEqual(row.true_positive, 2)
        self.assertEqual(row.false_positive, 0)
        self.assertEqual(row.false_negative, 0)
        self.assertEqual(row.precision, 1.0)
        self.assertEqual(row.recall, 1.0)
        self.assertEqual(row.event_iou, 1.0)

    def test_overlap_contamination_reduces_precision(self):
        rows = evaluate_candidate_truth(
            [candidate("12C", SQUARE), candidate("16O", SQUARE)],
            [2.0, 4.0, 6.0, 8.0],
            [2.0, 4.0, 6.0, 8.0],
            ["12C", "12C", "16O", "16O"],
            expected_labels=["12C", "16O"],
        )

        for row in rows:
            self.assertEqual(row.recall, 1.0)
            self.assertEqual(row.precision, 0.5)
            self.assertAlmostEqual(row.event_iou, 0.5)

    def test_overlapping_synthetic_bananas_expose_cross_contamination(self):
        species = (("12C", 12.0), ("12C-overlap", 12.0))
        dataset = generate_synthetic_events(
            recoil_species=species,
            events_per_locus=2500,
            background_events=0,
            seed=9,
        )
        candidates = self.detect(dataset)
        rows = evaluate_candidate_truth(
            candidates,
            dataset.tof_channel,
            dataset.energy_channel,
            dataset.truth_label,
            expected_labels=[locus.label for locus in dataset.loci],
        )

        self.assertEqual(len(candidates), 2)
        for row in rows:
            self.assertGreater(row.recall, 0.8)
            self.assertLess(row.precision, 0.55)
            self.assertLess(row.event_iou, 0.5)

    def test_missing_candidate_has_zero_recall(self):
        rows = evaluate_candidate_truth(
            [candidate("12C", SQUARE)],
            [2.0, 4.0, 20.0, 22.0],
            [2.0, 4.0, 20.0, 22.0],
            ["12C", "12C", "16O", "16O"],
            expected_labels=["12C", "16O"],
        )

        missing = rows[1]
        self.assertFalse(missing.detected)
        self.assertEqual(missing.truth_events, 2)
        self.assertEqual(missing.false_negative, 2)
        self.assertEqual(missing.recall, 0.0)
        self.assertEqual(missing.precision, 0.0)

    def test_absent_synthetic_element_is_reported_as_not_detected(self):
        dataset = generate_synthetic_events(
            recoil_species=(("12C", 12.0),),
            events_per_locus=2500,
            background_events=1000,
            seed=10,
        )
        expected_loci = calculate_synthetic_loci(
            recoil_species=(("12C", 12.0), ("16O", 15.994_915))
        )
        candidates = self.detect(dataset, loci=expected_loci)
        rows = evaluate_candidate_truth(
            candidates,
            dataset.tof_channel,
            dataset.energy_channel,
            dataset.truth_label,
            expected_labels=["12C", "16O"],
        )

        by_label = {row.label: row for row in rows}
        self.assertTrue(by_label["12C"].detected)
        self.assertFalse(by_label["16O"].detected)
        self.assertEqual(by_label["16O"].truth_events, 0)
        self.assertEqual(by_label["16O"].selected_events, 0)

    def test_micro_summary_counts_detected_labels_and_events(self):
        rows = evaluate_candidate_truth(
            [candidate("12C", SQUARE)],
            [2.0, 4.0, 20.0, 22.0],
            [2.0, 4.0, 20.0, 22.0],
            ["12C", "12C", "16O", "16O"],
            expected_labels=["12C", "16O"],
        )

        summary = summarize_candidate_metrics(rows)

        self.assertEqual(summary.detected_labels, 1)
        self.assertEqual(summary.expected_labels, 2)
        self.assertEqual(summary.true_positive, 2)
        self.assertEqual(summary.false_negative, 2)
        self.assertEqual(summary.recall, 0.5)

    def test_rejects_duplicate_candidate_labels(self):
        with self.assertRaisesRegex(ValueError, "Duplicate candidate"):
            evaluate_candidate_truth(
                [candidate("16O", SQUARE), candidate("16O", SQUARE)],
                [2.0], [2.0], ["16O"], expected_labels=["16O"]
            )

    def test_rejects_open_or_degenerate_polygon(self):
        with self.assertRaisesRegex(ValueError, "closed"):
            points_inside_polygon([[1.0, 1.0]], SQUARE[:-1])
        with self.assertRaisesRegex(ValueError, "distinct"):
            points_inside_polygon(
                [[1.0, 1.0]],
                [[0.0, 0.0], [1.0, 1.0], [1.0, 1.0], [0.0, 0.0]],
            )


if __name__ == "__main__":
    unittest.main()
