"""Review dialog for transient ToF-E automatic selection candidates."""

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from modules.element import Element
from modules.tofe_candidate_review import CandidateReviewStatus
from modules.tofe_review_controller import CandidateReviewController


class CandidateReviewDialog(QtWidgets.QDialog):
    """Expose proposal editing without saving until final confirmation."""

    def __init__(self, candidates, selector, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review automatic banana candidates")
        self.resize(900, 560)
        self.controller = CandidateReviewController(
            candidates, selector, Element.from_string
        )

        explanation = QtWidgets.QLabel(
            "Candidates are temporary. Edit and Reject do not change saved "
            "selections. Accept asks for final confirmation and then writes "
            "one Potku selection."
        )
        explanation.setWordWrap(True)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Candidate", "Element", "Confidence", "Coverage", "Status"
        ])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.currentCellChanged.connect(self._selection_changed)

        self.element_edit = QtWidgets.QLineEdit()
        self.element_edit.setToolTip(
            "Confirm an isotope such as 16O, or a natural element such as O"
        )
        self.polygon_edit = QtWidgets.QPlainTextEdit()
        self.polygon_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.polygon_edit.setPlaceholderText("ToF channel    Energy channel")
        self.polygon_edit.setReadOnly(True)

        form = QtWidgets.QFormLayout()
        form.addRow("Confirmed element/isotope:", self.element_edit)
        form.addRow("Polygon vertices (ToF, Energy):", self.polygon_edit)

        self.edit_button = QtWidgets.QPushButton("Edit polygon")
        self.apply_button = QtWidgets.QPushButton("Apply edit")
        self.cancel_button = QtWidgets.QPushButton("Cancel edit")
        self.reject_button = QtWidgets.QPushButton("Reject")
        self.accept_button = QtWidgets.QPushButton("Accept selection…")
        close_button = QtWidgets.QPushButton("Close")
        self.edit_button.clicked.connect(self._begin_edit)
        self.apply_button.clicked.connect(self._apply_edit)
        self.cancel_button.clicked.connect(self._cancel_edit)
        self.reject_button.clicked.connect(self._reject_candidate)
        self.accept_button.clicked.connect(self._accept_candidate)
        close_button.clicked.connect(self.accept)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self.reject_button)
        buttons.addWidget(self.accept_button)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self._refresh()

    @property
    def active_candidates(self):
        return self.controller.active_candidates

    @property
    def accepted_count(self):
        return self.controller.accepted_count

    def _refresh(self, candidate_id=None):
        rows = self.controller.rows
        selected_id = candidate_id or self._current_candidate_id()
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        selected_row = 0 if rows else -1
        for row_index, row in enumerate(rows):
            values = (
                row.candidate_id,
                row.label,
                f"{row.confidence:.3f}",
                f"{row.coverage:.3f}",
                row.status.value,
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setData(QtCore.Qt.UserRole, row.candidate_id)
                self.table.setItem(row_index, column, item)
            if row.candidate_id == selected_id:
                selected_row = row_index
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        if selected_row >= 0:
            self.table.selectRow(selected_row)
            self.table.setCurrentCell(selected_row, 0)
        else:
            self._update_editor(None)

    def _selection_changed(self, *_args):
        candidate_id = self._current_candidate_id()
        self._update_editor(candidate_id)

    def _current_candidate_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(QtCore.Qt.UserRole) if item else None

    def _update_editor(self, candidate_id):
        if candidate_id is None:
            self.element_edit.clear()
            self.polygon_edit.clear()
            for button in (
                    self.edit_button, self.apply_button, self.cancel_button,
                    self.reject_button, self.accept_button):
                button.setEnabled(False)
            return
        item = self.controller.session.get(candidate_id)
        self.element_edit.setText(item.working.label)
        self.polygon_edit.setPlainText(
            self.controller.polygon_text(candidate_id)
        )
        editing = item.status == CandidateReviewStatus.EDITING
        pending = item.status == CandidateReviewStatus.PENDING
        self.polygon_edit.setReadOnly(not editing)
        self.edit_button.setEnabled(pending)
        self.apply_button.setEnabled(editing)
        self.cancel_button.setEnabled(editing)
        self.reject_button.setEnabled(pending or editing)
        self.accept_button.setEnabled(pending)
        self.element_edit.setEnabled(pending)

    def _begin_edit(self):
        candidate_id = self._current_candidate_id()
        if candidate_id:
            self.controller.begin_edit(candidate_id)
            self._refresh(candidate_id)
            self.polygon_edit.setFocus()

    def _apply_edit(self):
        candidate_id = self._current_candidate_id()
        if not candidate_id:
            return
        try:
            self.controller.apply_polygon_text(
                candidate_id, self.polygon_edit.toPlainText()
            )
        except (TypeError, ValueError) as error:
            self._warn(str(error))
            return
        self._refresh(candidate_id)

    def _cancel_edit(self):
        candidate_id = self._current_candidate_id()
        if candidate_id:
            self.controller.cancel_edit(candidate_id)
            self._refresh(candidate_id)

    def _reject_candidate(self):
        candidate_id = self._current_candidate_id()
        if candidate_id:
            self.controller.reject(candidate_id)
            self._refresh(candidate_id)

    def _accept_candidate(self):
        candidate_id = self._current_candidate_id()
        if not candidate_id:
            return
        element_text = self.element_edit.text().strip()
        answer = QtWidgets.QMessageBox.question(
            self,
            "Accept automatic selection",
            f"Accept {candidate_id} as {element_text or '(unconfirmed)'}?\n\n"
            "This action adds the polygon to Potku selections and updates "
            "the selection file.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.controller.accept(candidate_id, element_text)
        except Exception as error:
            self._warn(str(error))
            return
        self._refresh(candidate_id)

    def _warn(self, message):
        QtWidgets.QMessageBox.warning(
            self, "Automatic selection review", message,
            QtWidgets.QMessageBox.Ok,
        )
