import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from modules.tofe_candidate import BananaCandidate
from modules.tofe_candidate_review import CandidateReviewStatus
from modules.tofe_review_controller import CandidateReviewController
from modules.tofe_review_controller import parse_polygon_text


def candidate(label="16O"):
    return BananaCandidate(
        label=label,
        polygon=np.array([
            [10.2, 20.4], [30.1, 20.3], [31.0, 40.2],
            [10.4, 41.0], [10.2, 20.4],
        ]),
        ridge=np.array([[12.0, 25.0], [20.0, 30.0], [28.0, 35.0]]),
        confidence=0.8,
        coverage=0.9,
        contrast=0.75,
        theory_adherence=0.85,
    )


class FakeSelection:
    def __init__(self, _axes, _colormap, _measurement, **kwargs):
        self.kwargs = kwargs
        self.points = []
        self.deleted = False

    def add_point(self, point):
        self.points.append(point)
        return 0

    def end_selection(self, canvas=None):
        return True

    def delete(self):
        self.deleted = True


class FakeSelector:
    def __init__(self, directory):
        self.axes = object()
        self.element_colormap = {"O": "blue"}
        self.measurement = object()
        self.is_transposed = False
        self.selections = []
        self.selection_file = Path(directory, "measurement.selections")
        self.update_calls = 0

    def update_selections(self):
        self.update_calls += 1
        self.selection_file.write_text("saved")


class TestCandidateReviewController(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.selector = FakeSelector(self.temp_directory.name)
        self.parsed = []

        def parse_element(text):
            self.parsed.append(text)
            return SimpleNamespace(symbol="O", isotope=16)

        self.controller = CandidateReviewController(
            [candidate()], self.selector, parse_element, FakeSelection
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_rows_expose_metrics_without_selector_mutation(self):
        row = self.controller.rows[0]

        self.assertEqual(row.candidate_id, "16O#1")
        self.assertEqual(row.confidence, 0.8)
        self.assertEqual(row.coverage, 0.9)
        self.assertEqual(row.status, CandidateReviewStatus.PENDING)
        self.assertEqual(self.selector.update_calls, 0)

    def test_edit_and_reject_do_not_save(self):
        self.controller.begin_edit("16O#1")
        self.controller.apply_polygon_text(
            "16O#1", "14 20\n30 20\n31 40\n14 41"
        )
        self.controller.reject("16O#1")

        self.assertEqual(self.selector.update_calls, 0)
        self.assertFalse(self.selector.selection_file.exists())
        self.assertEqual(self.controller.active_candidates, ())

    def test_accept_parses_element_and_saves_exactly_once(self):
        selection = self.controller.accept("16O#1", " 16O ")

        self.assertEqual(self.parsed, ["16O"])
        self.assertEqual(self.selector.update_calls, 1)
        self.assertEqual(self.controller.accepted_count, 1)
        self.assertEqual(selection.kwargs["element"], "O")
        self.assertEqual(selection.kwargs["isotope"], 16)
        self.assertEqual(self.controller.active_candidates, ())

    def test_empty_element_is_rejected_without_calling_parser(self):
        with self.assertRaisesRegex(ValueError, "Confirm"):
            self.controller.accept("16O#1", "  ")

        self.assertEqual(self.parsed, [])
        self.assertEqual(self.selector.update_calls, 0)

    def test_polygon_text_round_trip_closes_open_input(self):
        text = self.controller.polygon_text("16O#1")
        parsed = parse_polygon_text(text)
        open_polygon = parse_polygon_text("1, 2\n4, 3\n5, 6")

        np.testing.assert_allclose(parsed, candidate().polygon)
        np.testing.assert_allclose(open_polygon[0], open_polygon[-1])
        self.assertEqual(open_polygon.shape, (4, 2))

    def test_invalid_polygon_text_keeps_editing_state(self):
        self.controller.begin_edit("16O#1")

        with self.assertRaises(ValueError):
            self.controller.apply_polygon_text("16O#1", "1 2\n3 bad")

        self.assertEqual(
            self.controller.rows[0].status,
            CandidateReviewStatus.EDITING,
        )
        self.assertEqual(self.selector.update_calls, 0)


if __name__ == "__main__":
    unittest.main()
