"""Application controller for reviewing transient ToF-E candidates.

The controller contains no Qt dependency.  It exposes table rows and polygon
text for the GUI while keeping all selector access behind the explicit
``accept`` method.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from modules.tofe_candidate_review import CandidateReviewSession
from modules.tofe_candidate_review import CandidateReviewStatus
from modules.tofe_selection_adapter import accept_candidate_as_selection


@dataclass(frozen=True)
class CandidateReviewRow:
    candidate_id: str
    label: str
    confidence: float
    coverage: float
    status: CandidateReviewStatus


class CandidateReviewController:
    """Coordinate proposal editing and explicit selection acceptance."""

    def __init__(
            self, candidates, selector, element_parser: Callable,
            selection_factory: Callable = None):
        if not callable(element_parser):
            raise TypeError("Element parser must be callable")
        self.session = CandidateReviewSession(candidates)
        self.selector = selector
        self.element_parser = element_parser
        self.selection_factory = selection_factory
        self.accepted_count = 0

    @property
    def rows(self):
        return tuple(
            CandidateReviewRow(
                candidate_id=item.candidate_id,
                label=item.working.label,
                confidence=float(item.working.confidence),
                coverage=float(item.working.coverage),
                status=item.status,
            )
            for item in self.session.items
        )

    @property
    def active_candidates(self):
        """Return proposals that should remain on the transient overlay."""
        return tuple(
            item.working
            for item in self.session.items
            if item.status in (
                CandidateReviewStatus.PENDING,
                CandidateReviewStatus.EDITING,
            )
        )

    def polygon_text(self, candidate_id):
        polygon = self.session.get(candidate_id).working.polygon
        return "\n".join(
            f"{tof:.3f}\t{energy:.3f}" for tof, energy in polygon
        )

    def begin_edit(self, candidate_id):
        return self.session.begin_edit(candidate_id)

    def apply_polygon_text(self, candidate_id, text):
        item = self.session.get(candidate_id)
        if item.status != CandidateReviewStatus.EDITING:
            raise ValueError("Candidate must be in editing state")
        polygon = parse_polygon_text(text)
        self.session.replace_polygon(candidate_id, polygon)
        return self.session.finish_edit(candidate_id)

    def cancel_edit(self, candidate_id):
        return self.session.cancel_edit(candidate_id)

    def reject(self, candidate_id):
        return self.session.reject(candidate_id)

    def accept(self, candidate_id, element_text):
        """Persist a proposal only after the GUI's final confirmation."""
        element_text = str(element_text).strip()
        if not element_text:
            raise ValueError("Confirm an element or isotope before accepting")
        confirmed_element = self.element_parser(element_text)
        result = self.session.accept(
            candidate_id,
            lambda candidate: accept_candidate_as_selection(
                candidate,
                confirmed_element,
                self.selector,
                self.selection_factory,
            ),
        )
        self.accepted_count += 1
        return result


def parse_polygon_text(text):
    """Parse editable ``ToF Energy`` rows and return a closed polygon."""
    points = []
    for line_number, line in enumerate(str(text).splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        fields = line.replace(",", " ").split()
        if len(fields) != 2:
            raise ValueError(
                f"Polygon line {line_number} must contain ToF and Energy"
            )
        try:
            point = (float(fields[0]), float(fields[1]))
        except ValueError as error:
            raise ValueError(
                f"Polygon line {line_number} contains a non-number"
            ) from error
        if not np.all(np.isfinite(point)):
            raise ValueError(
                f"Polygon line {line_number} must contain finite values"
            )
        points.append(point)
    if len(points) < 3:
        raise ValueError("Polygon needs at least three vertices")
    if not np.allclose(points[0], points[-1]):
        points.append(points[0])
    polygon = np.asarray(points, dtype=float)
    if np.unique(polygon[:-1], axis=0).shape[0] < 3:
        raise ValueError("Polygon needs three distinct vertices")
    return polygon
