import unittest
from types import SimpleNamespace

import numpy as np

from modules.tofe_candidate import CandidateSearchSettings
from modules.tofe_candidate import build_candidate_histogram
from modules.tofe_candidate import propose_banana_candidates
from modules.tofe_synthetic import generate_synthetic_events
from modules.tofe_training_data import AcceptedSelection
from modules.tofe_training_data import accepted_selections_from_potku
from modules.tofe_training_data import build_training_feature_rows
from modules.tofe_training_data import training_rows_tsv


SQUARE = np.array([
    [0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]
])


class FakePotkuSelection:
    def __init__(
            self, selection_id, points, symbol="O", isotope=16,
            selection_type="ERD", completed=True):
        self.id = selection_id
        self._points = points
        self.element = SimpleNamespace(symbol=symbol, isotope=isotope)
        self.type = selection_type
        self.is_completed = completed

    def get_points(self):
        return self._points


class TestTofeTrainingData(unittest.TestCase):
    def test_adapts_completed_erd_and_filters_other_selections(self):
        selections = accepted_selections_from_potku([
            FakePotkuSelection(3, SQUARE[:-1].tolist()),
            FakePotkuSelection(4, SQUARE, selection_type="RBS"),
            FakePotkuSelection(5, SQUARE, completed=False),
        ])

        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0].selection_id, "3")
        self.assertEqual(selections[0].label, "16O")
        np.testing.assert_allclose(
            selections[0].polygon[0], selections[0].polygon[-1]
        )

    def test_adapter_restores_canonical_coordinates_when_transposed(self):
        displayed = SQUARE[:, ::-1] + np.array([100.0, 10.0])

        selection = accepted_selections_from_potku([
            FakePotkuSelection(1, displayed)
        ], transposed=True)[0]

        np.testing.assert_allclose(
            selection.polygon, SQUARE + np.array([10.0, 100.0])
        )

    def test_builds_shape_and_event_features(self):
        selection = AcceptedSelection("s1", "16O", SQUARE)
        rows = build_training_feature_rows(
            [2.0, 8.0, 20.0],
            [2.0, 8.0, 20.0],
            [selection],
            measurement_id="synthetic",
        )

        row = rows[0]
        self.assertEqual(row.event_count, 2)
        self.assertAlmostEqual(row.event_fraction, 2 / 3)
        self.assertAlmostEqual(row.polygon_area, 100.0)
        self.assertAlmostEqual(row.polygon_perimeter, 40.0)
        self.assertAlmostEqual(row.polygon_centroid_tof, 5.0)
        self.assertAlmostEqual(row.polygon_centroid_energy, 5.0)
        self.assertEqual(row.has_theory, 0)

    def test_neighbor_overlap_features_are_event_based(self):
        first = AcceptedSelection("a", "12C", SQUARE)
        second = AcceptedSelection("b", "16O", SQUARE + [5.0, 0.0])
        rows = build_training_feature_rows(
            [2.0, 6.0, 8.0, 12.0, 20.0],
            [5.0, 5.0, 5.0, 5.0, 5.0],
            [first, second],
        )

        self.assertAlmostEqual(rows[0].max_neighbor_event_iou, 0.5)
        self.assertAlmostEqual(rows[0].max_neighbor_shared_fraction, 2 / 3)
        self.assertAlmostEqual(rows[1].max_neighbor_shared_fraction, 2 / 3)

    def test_theory_features_use_detector_fwhm_scaling(self):
        locus = SimpleNamespace(
            label="16O",
            tof_channel=np.array([0.0, 5.0, 10.0]),
            energy_channel=np.array([5.0, 5.0, 5.0]),
            tof_resolution_fwhm_channel=2.0,
            energy_resolution_fwhm_channel=4.0,
        )
        shifted = AcceptedSelection("s", "16O", SQUARE + [0.0, 4.0])

        row = build_training_feature_rows(
            [4.0, 6.0], [8.0, 10.0], [shifted], [locus]
        )[0]

        self.assertEqual(row.has_theory, 1)
        self.assertAlmostEqual(row.theory_centroid_dx_fwhm, 0.0)
        self.assertAlmostEqual(row.theory_centroid_dy_fwhm, 1.0)
        self.assertAlmostEqual(row.theory_centroid_distance_fwhm, 1.0)
        self.assertGreater(row.event_theory_distance_median_fwhm, 0.5)

    def test_empty_selection_event_features_remain_finite(self):
        row = build_training_feature_rows(
            [20.0], [20.0], [AcceptedSelection("s", "O", SQUARE)]
        )[0]

        self.assertEqual(row.event_count, 0)
        self.assertEqual(row.tof_mean, 0.0)
        self.assertEqual(row.event_theory_distance_median_fwhm, 0.0)
        for value in row.as_dict().values():
            if isinstance(value, float):
                self.assertTrue(np.isfinite(value))

    def test_synthetic_candidates_convert_to_four_ml_rows(self):
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
            dataset.tof_channel, dataset.energy_channel, 2.0, 8.0,
            max_bin_count=1200,
        )
        candidates = propose_banana_candidates(
            grid.counts, grid.tof_edges, grid.energy_edges, dataset.loci,
            CandidateSearchSettings(
                sample_count=60, search_radius_fwhm=2.0,
                polygon_half_width_fwhm=1.6, minimum_peak_sigma=2.0,
                minimum_coverage=0.35, minimum_confidence=0.18,
            ),
        )
        selections = tuple(
            AcceptedSelection(candidate.label, candidate.label, candidate.polygon)
            for candidate in candidates
        )

        rows = build_training_feature_rows(
            dataset.tof_channel, dataset.energy_channel, selections,
            dataset.loci, measurement_id="synthetic-kist"
        )

        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row.event_count > 500 for row in rows))
        self.assertTrue(all(row.has_theory == 1 for row in rows))
        self.assertTrue(all(
            row.event_theory_distance_median_fwhm < 1.5 for row in rows
        ))

    def test_tsv_has_stable_header_and_finite_values(self):
        row = build_training_feature_rows(
            [2.0], [2.0], [AcceptedSelection("s", "O", SQUARE)]
        )[0]
        text = training_rows_tsv([row])

        self.assertTrue(text.startswith("measurement_id\tselection_id\tlabel"))
        self.assertIn("\ts\tO\t1\t1\t", text)
        self.assertNotIn("nan", text.lower())

    def test_rejects_invalid_selection_polygon_or_event_arrays(self):
        with self.assertRaises(ValueError):
            build_training_feature_rows(
                [1.0], [1.0, 2.0], [AcceptedSelection("s", "O", SQUARE)]
            )
        with self.assertRaisesRegex(ValueError, "area"):
            build_training_feature_rows(
                [1.0], [1.0], [AcceptedSelection(
                    "s", "O", [[0, 0], [1, 0], [2, 0], [0, 0]]
                )]
            )


if __name__ == "__main__":
    unittest.main()
