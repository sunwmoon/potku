import unittest

import numpy as np

from modules.tofe_candidate import BananaCandidate
from modules.tofe_candidate_review import CandidateReviewSession
from modules.tofe_candidate_review import CandidateReviewStatus


def candidate(label="16O", shift=0.0):
    polygon = np.array([
        [1.0, 2.0 + shift],
        [4.0, 3.0 + shift],
        [5.0, 6.0 + shift],
        [2.0, 5.0 + shift],
        [1.0, 2.0 + shift],
    ])
    ridge = np.array([
        [2.0, 3.0 + shift],
        [3.0, 4.0 + shift],
        [4.0, 5.0 + shift],
    ])
    return BananaCandidate(
        label=label,
        polygon=polygon,
        ridge=ridge,
        confidence=0.8,
        coverage=0.9,
        contrast=0.7,
        theory_adherence=0.85,
    )


class TestCandidateReviewSession(unittest.TestCase):
    def test_initializes_pending_items_with_stable_duplicate_ids(self):
        session = CandidateReviewSession([
            candidate("16O"), candidate("16O", 1.0), candidate("12C")
        ])

        self.assertEqual(
            [item.candidate_id for item in session.items],
            ["16O#1", "16O#2", "12C#1"],
        )
        self.assertTrue(all(
            item.status == CandidateReviewStatus.PENDING
            for item in session.items
        ))

    def test_edit_requires_explicit_finish_and_preserves_new_polygon(self):
        session = CandidateReviewSession([candidate()])
        edited = candidate(shift=2.0).polygon

        session.begin_edit("16O#1")
        item = session.replace_polygon("16O#1", edited)
        self.assertEqual(item.status, CandidateReviewStatus.EDITING)
        np.testing.assert_allclose(item.working.polygon, edited)
        item = session.finish_edit("16O#1")

        self.assertEqual(item.status, CandidateReviewStatus.PENDING)
        np.testing.assert_allclose(item.working.polygon, edited)

    def test_cancel_edit_restores_original_polygon(self):
        original = candidate()
        session = CandidateReviewSession([original])
        session.begin_edit("16O#1")
        session.replace_polygon("16O#1", candidate(shift=3.0).polygon)

        item = session.cancel_edit("16O#1")

        self.assertEqual(item.status, CandidateReviewStatus.PENDING)
        np.testing.assert_allclose(item.working.polygon, original.polygon)

    def test_reject_never_invokes_an_acceptor(self):
        calls = []
        session = CandidateReviewSession([candidate()])

        item = session.reject("16O#1")

        self.assertEqual(item.status, CandidateReviewStatus.REJECTED)
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            session.accept("16O#1", calls.append)

    def test_accept_is_the_only_transition_that_invokes_callback(self):
        calls = []
        session = CandidateReviewSession([candidate()])
        session.begin_edit("16O#1")
        session.finish_edit("16O#1")

        result = session.accept(
            "16O#1", lambda proposal: calls.append(proposal) or "selection"
        )

        self.assertEqual(result, "selection")
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            session.get("16O#1").status,
            CandidateReviewStatus.ACCEPTED,
        )

    def test_failed_acceptor_leaves_candidate_pending(self):
        session = CandidateReviewSession([candidate()])

        def fail(_proposal):
            raise RuntimeError("conversion failed")

        with self.assertRaisesRegex(RuntimeError, "conversion failed"):
            session.accept("16O#1", fail)

        self.assertEqual(
            session.get("16O#1").status,
            CandidateReviewStatus.PENDING,
        )

    def test_invalid_transitions_and_polygons_are_rejected(self):
        session = CandidateReviewSession([candidate()])
        with self.assertRaises(ValueError):
            session.replace_polygon("16O#1", candidate().polygon)

        session.begin_edit("16O#1")
        with self.assertRaisesRegex(ValueError, "closed"):
            session.replace_polygon(
                "16O#1", candidate().polygon[:-1]
            )

    def test_session_copies_input_arrays(self):
        source = candidate()
        session = CandidateReviewSession([source])
        source.polygon[0] = [99.0, 99.0]

        np.testing.assert_allclose(
            session.get("16O#1").working.polygon[0], [1.0, 2.0]
        )
        self.assertFalse(
            session.get("16O#1").working.polygon.flags.writeable
        )


if __name__ == "__main__":
    unittest.main()
