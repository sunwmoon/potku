"""Explicit adapter from a reviewed banana proposal to a Potku selection.

The adapter has no automatic entry point.  A caller must invoke it from an
explicit Accept action, normally through ``CandidateReviewSession.accept``.
It keeps the candidate in canonical (ToF, Energy) coordinates and maps those
coordinates to the current display orientation only while constructing the
Potku ``Selection``.
"""

from pathlib import Path
from typing import Callable

import numpy as np


def accept_candidate_as_selection(
        candidate, confirmed_element, selector,
        selection_factory: Callable = None):
    """Create and persist one accepted ERD selection transactionally.

    ``confirmed_element`` must be the element or isotope approved by the user.
    The candidate is appended only after a complete closed Selection has been
    created.  If Potku's update/save step fails, the selector list and its
    previous selection file are restored before the exception is re-raised.
    """
    symbol, isotope = _validated_element(confirmed_element)
    points = candidate_polygon_points(
        candidate,
        transposed=bool(getattr(selector, "is_transposed", False)),
    )
    if selection_factory is None:
        # Keep this import local so the physics/review core remains usable in
        # environments without Qt. Potku's GUI environment supplies it.
        from modules.selection import Selection
        selection_factory = Selection
    if not callable(selection_factory):
        raise TypeError("Selection factory must be callable")

    selection = selection_factory(
        selector.axes,
        selector.element_colormap,
        selector.measurement,
        element=symbol,
        isotope=isotope,
        element_type="ERD",
        transposed=bool(getattr(selector, "is_transposed", False)),
    )
    try:
        for point in points:
            result = selection.add_point(point)
            if result not in (0, None):
                raise ValueError("Potku rejected a candidate polygon point")
        if not selection.end_selection(canvas=None):
            raise ValueError("Potku did not complete the candidate selection")
    except Exception:
        _delete_selection(selection)
        raise

    previous_file = _SelectionFileSnapshot.capture(
        getattr(selector, "selection_file", None)
    )
    selector.selections.append(selection)
    try:
        selector.update_selections()
    except Exception:
        if selection in selector.selections:
            selector.selections.remove(selection)
        _delete_selection(selection)
        previous_file.restore()
        raise
    return selection


def candidate_polygon_points(candidate, transposed=False):
    """Return closed-proposal vertices as integer Potku selection points."""
    polygon = np.asarray(candidate.polygon, dtype=float)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or polygon.shape[0] < 4:
        raise ValueError("Candidate polygon must have shape (n, 2)")
    if not np.all(np.isfinite(polygon)):
        raise ValueError("Candidate polygon must be finite")
    if not np.allclose(polygon[0], polygon[-1]):
        raise ValueError("Candidate polygon must be closed")

    rounded = np.rint(polygon[:-1]).astype(int)
    if transposed:
        rounded = rounded[:, ::-1]
    points = []
    for row in rounded:
        point = (int(row[0]), int(row[1]))
        if not points or point != points[-1]:
            points.append(point)
    if len(points) > 1 and points[-1] == points[0]:
        points.pop()
    if len(set(points)) < 3:
        raise ValueError(
            "Candidate polygon needs three distinct integer vertices"
        )
    return tuple(points)


def _validated_element(element):
    symbol = getattr(element, "symbol", None)
    isotope = getattr(element, "isotope", None)
    if not isinstance(symbol, str) or not symbol or symbol == "Select":
        raise ValueError("A confirmed recoil element is required")
    if isotope is not None:
        if (not isinstance(isotope, (int, np.integer)) or
                isinstance(isotope, bool) or isotope <= 0):
            raise ValueError("Confirmed isotope must be a positive integer")
        isotope = int(isotope)
    return symbol, isotope


def _delete_selection(selection):
    delete = getattr(selection, "delete", None)
    if callable(delete):
        delete()


class _SelectionFileSnapshot:
    def __init__(self, path, existed, contents):
        self.path = path
        self.existed = existed
        self.contents = contents

    @classmethod
    def capture(cls, path):
        if path is None:
            return cls(None, False, None)
        path = Path(path)
        if path.exists():
            return cls(path, True, path.read_bytes())
        return cls(path, False, None)

    def restore(self):
        if self.path is None:
            return
        if self.existed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.contents)
        elif self.path.exists():
            self.path.unlink()
