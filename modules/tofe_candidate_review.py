"""Safe review state for transient ToF-E banana candidates.

This module deliberately has no dependency on Potku's ``Selector``.  A
candidate can reach an accepted state only through an explicit callback that
the GUI will later provide.  Editing and rejection therefore cannot create or
save a selection by accident.
"""

from dataclasses import dataclass
from dataclasses import replace
from enum import Enum
from typing import Callable
from typing import Iterable
from typing import Tuple

import numpy as np

from modules.tofe_candidate import BananaCandidate


class CandidateReviewStatus(str, Enum):
    """Lifecycle states for a transient automatic proposal."""

    PENDING = "pending"
    EDITING = "editing"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


@dataclass(frozen=True)
class CandidateReviewItem:
    """One proposal and its non-persistent review state."""

    candidate_id: str
    original: BananaCandidate
    working: BananaCandidate
    status: CandidateReviewStatus = CandidateReviewStatus.PENDING


class CandidateReviewSession:
    """Manage proposal review without direct access to saved selections."""

    def __init__(self, candidates: Iterable[BananaCandidate]):
        items = []
        label_counts = {}
        for candidate in candidates:
            original = _copy_candidate(candidate)
            label_counts[original.label] = label_counts.get(
                original.label, 0
            ) + 1
            candidate_id = (
                f"{original.label}#{label_counts[original.label]}"
            )
            items.append(CandidateReviewItem(
                candidate_id=candidate_id,
                original=original,
                working=_copy_candidate(original),
            ))
        self._order = tuple(item.candidate_id for item in items)
        self._items = {item.candidate_id: item for item in items}

    @property
    def items(self) -> Tuple[CandidateReviewItem, ...]:
        return tuple(self._items[candidate_id] for candidate_id in self._order)

    def get(self, candidate_id: str) -> CandidateReviewItem:
        try:
            return self._items[candidate_id]
        except KeyError as error:
            raise KeyError(f"Unknown candidate: {candidate_id}") from error

    def begin_edit(self, candidate_id: str) -> CandidateReviewItem:
        item = self._require_status(
            candidate_id, CandidateReviewStatus.PENDING
        )
        return self._store(replace(
            item, status=CandidateReviewStatus.EDITING
        ))

    def replace_polygon(
            self, candidate_id: str, polygon) -> CandidateReviewItem:
        item = self._require_status(
            candidate_id, CandidateReviewStatus.EDITING
        )
        candidate = replace(
            item.working,
            polygon=_validated_polygon(polygon),
        )
        return self._store(replace(item, working=candidate))

    def finish_edit(self, candidate_id: str) -> CandidateReviewItem:
        item = self._require_status(
            candidate_id, CandidateReviewStatus.EDITING
        )
        return self._store(replace(
            item, status=CandidateReviewStatus.PENDING
        ))

    def cancel_edit(self, candidate_id: str) -> CandidateReviewItem:
        item = self._require_status(
            candidate_id, CandidateReviewStatus.EDITING
        )
        return self._store(replace(
            item,
            working=_copy_candidate(item.original),
            status=CandidateReviewStatus.PENDING,
        ))

    def reject(self, candidate_id: str) -> CandidateReviewItem:
        item = self.get(candidate_id)
        if item.status not in (
                CandidateReviewStatus.PENDING,
                CandidateReviewStatus.EDITING):
            raise ValueError(
                f"Cannot reject a {item.status.value} candidate"
            )
        return self._store(replace(
            item, status=CandidateReviewStatus.REJECTED
        ))

    def accept(
            self, candidate_id: str,
            acceptor: Callable[[BananaCandidate], object]):
        """Commit one pending proposal through an explicit user-action hook.

        The acceptor is called before the state changes.  If conversion to a
        Potku selection raises an exception, the candidate remains pending.
        No other transition receives or invokes the callback.
        """
        item = self._require_status(
            candidate_id, CandidateReviewStatus.PENDING
        )
        if not callable(acceptor):
            raise TypeError("Candidate acceptor must be callable")
        result = acceptor(_copy_candidate(item.working))
        self._store(replace(
            item, status=CandidateReviewStatus.ACCEPTED
        ))
        return result

    def _require_status(self, candidate_id, expected):
        item = self.get(candidate_id)
        if item.status != expected:
            raise ValueError(
                f"Candidate {candidate_id} is {item.status.value}; "
                f"expected {expected.value}"
            )
        return item

    def _store(self, item):
        self._items[item.candidate_id] = item
        return item


def _copy_candidate(candidate: BananaCandidate) -> BananaCandidate:
    if not isinstance(candidate, BananaCandidate):
        raise TypeError("Review items must be BananaCandidate objects")
    polygon = _validated_polygon(candidate.polygon)
    ridge = _validated_points(candidate.ridge, "Candidate ridge", 2)
    return replace(candidate, polygon=polygon, ridge=ridge)


def _validated_polygon(polygon):
    polygon = _validated_points(polygon, "Candidate polygon", 4)
    if not np.allclose(polygon[0], polygon[-1]):
        raise ValueError("Candidate polygon must be closed")
    if np.unique(polygon[:-1], axis=0).shape[0] < 3:
        raise ValueError("Candidate polygon needs three distinct vertices")
    return polygon


def _validated_points(points, description, minimum_count):
    points = np.array(points, dtype=float, copy=True)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"{description} must have shape (n, 2)")
    if points.shape[0] < minimum_count:
        raise ValueError(
            f"{description} needs at least {minimum_count} points"
        )
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{description} must be finite")
    points.setflags(write=False)
    return points
