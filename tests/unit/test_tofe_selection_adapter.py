import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from modules.tofe_candidate import BananaCandidate
from modules.tofe_candidate_review import CandidateReviewSession
from modules.tofe_candidate_review import CandidateReviewStatus
from modules.tofe_selection_adapter import accept_candidate_as_selection
from modules.tofe_selection_adapter import candidate_polygon_points


def candidate():
    return BananaCandidate(
        label="16O",
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
    def __init__(self, axes, element_colormap, measurement, **kwargs):
        self.axes = axes
        self.element_colormap = element_colormap
        self.measurement = measurement
        self.kwargs = kwargs
        self.points = []
        self.closed = False
        self.deleted = False

    def add_point(self, point):
        self.points.append(point)
        return 0

    def end_selection(self, canvas=None):
        self.closed = True
        return True

    def delete(self):
        self.deleted = True


class FakeSelector:
    def __init__(self, directory, transposed=False):
        self.axes = object()
        self.element_colormap = {"O": "blue"}
        self.measurement = object()
        self.is_transposed = transposed
        self.selections = []
        self.selection_file = Path(directory, "measurement.selections")
        self.update_calls = 0
        self.fail_after_write = False

    def update_selections(self):
        self.update_calls += 1
        self.selection_file.write_text(
            "\n".join(str(selection.points) for selection in self.selections)
        )
        if self.fail_after_write:
            raise RuntimeError("save failed")


class TestTofeSelectionAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.selector = FakeSelector(self.temp_directory.name)
        self.element = SimpleNamespace(symbol="O", isotope=16)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_builds_closed_erd_selection_and_persists_once(self):
        selection = accept_candidate_as_selection(
            candidate(), self.element, self.selector, FakeSelection
        )

        self.assertEqual(self.selector.selections, [selection])
        self.assertEqual(self.selector.update_calls, 1)
        self.assertTrue(selection.closed)
        self.assertEqual(selection.kwargs["element"], "O")
        self.assertEqual(selection.kwargs["isotope"], 16)
        self.assertEqual(selection.kwargs["element_type"], "ERD")
        self.assertTrue(self.selector.selection_file.exists())

    def test_candidate_stays_canonical_until_transposed_conversion(self):
        normal = candidate_polygon_points(candidate(), transposed=False)
        transposed = candidate_polygon_points(candidate(), transposed=True)

        self.assertEqual(normal[0], (10, 20))
        self.assertEqual(transposed[0], (20, 10))
        self.assertEqual(
            transposed,
            tuple((energy, tof) for tof, energy in normal),
        )

    def test_review_reject_does_not_touch_selector_or_file(self):
        session = CandidateReviewSession([candidate()])

        session.reject("16O#1")

        self.assertEqual(self.selector.selections, [])
        self.assertEqual(self.selector.update_calls, 0)
        self.assertFalse(self.selector.selection_file.exists())

    def test_review_edit_does_not_touch_selector_until_accept(self):
        session = CandidateReviewSession([candidate()])
        edited = candidate().polygon.copy()
        edited[:, 0] += 4.0
        session.begin_edit("16O#1")
        session.replace_polygon("16O#1", edited)
        session.finish_edit("16O#1")

        self.assertEqual(self.selector.selections, [])
        self.assertEqual(self.selector.update_calls, 0)
        selection = session.accept(
            "16O#1",
            lambda proposal: accept_candidate_as_selection(
                proposal, self.element, self.selector, FakeSelection
            ),
        )

        self.assertEqual(selection.points[0], (14, 20))
        self.assertEqual(self.selector.update_calls, 1)
        self.assertEqual(
            session.get("16O#1").status,
            CandidateReviewStatus.ACCEPTED,
        )

    def test_failed_save_restores_selector_file_and_pending_state(self):
        self.selector.selection_file.write_text("existing selection\n")
        self.selector.fail_after_write = True
        session = CandidateReviewSession([candidate()])

        with self.assertRaisesRegex(RuntimeError, "save failed"):
            session.accept(
                "16O#1",
                lambda proposal: accept_candidate_as_selection(
                    proposal, self.element, self.selector, FakeSelection
                ),
            )

        self.assertEqual(self.selector.selections, [])
        self.assertEqual(
            self.selector.selection_file.read_text(),
            "existing selection\n",
        )
        self.assertEqual(
            session.get("16O#1").status,
            CandidateReviewStatus.PENDING,
        )

    def test_failed_first_save_removes_partial_new_file(self):
        self.selector.fail_after_write = True

        with self.assertRaises(RuntimeError):
            accept_candidate_as_selection(
                candidate(), self.element, self.selector, FakeSelection
            )

        self.assertFalse(self.selector.selection_file.exists())
        self.assertEqual(self.selector.selections, [])

    def test_rejects_unconfirmed_or_invalid_element(self):
        invalid = (
            SimpleNamespace(symbol="", isotope=16),
            SimpleNamespace(symbol="Select", isotope=None),
            SimpleNamespace(symbol="O", isotope=0),
        )
        for element in invalid:
            with self.subTest(element=element):
                with self.assertRaises(ValueError):
                    accept_candidate_as_selection(
                        candidate(), element, self.selector, FakeSelection
                    )

    def test_rejects_polygon_collapsed_by_integer_rounding(self):
        collapsed = candidate()
        object.__setattr__(collapsed, "polygon", np.array([
            [1.1, 1.1], [1.2, 1.2], [1.3, 1.3], [1.1, 1.1]
        ]))

        with self.assertRaisesRegex(ValueError, "distinct integer"):
            accept_candidate_as_selection(
                collapsed, self.element, self.selector, FakeSelection
            )


if __name__ == "__main__":
    unittest.main()
