"""Viewer and TSV export dialog for a transient theory overlay."""

from pathlib import Path

from PyQt5 import QtWidgets

from modules.tofe_report import build_theory_report_rows
from modules.tofe_report import format_theory_report_tsv


class TheoryReportDialog(QtWidgets.QDialog):
    """Show calculated endpoints, modes, and fallback reasons."""

    def __init__(self, loci, default_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ToF-E theory overlay report")
        self.resize(1050, 420)
        self.default_path = Path(default_path)
        self.report_text = format_theory_report_tsv(
            build_theory_report_rows(loci)
        )

        explanation = QtWidgets.QLabel(
            "The surface columns are the predicted high-energy endpoint. "
            "This report describes the transient overlay only; it does not "
            "create or save a selection."
        )
        explanation.setWordWrap(True)

        report = QtWidgets.QPlainTextEdit(self.report_text)
        report.setReadOnly(True)
        report.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close
        )
        copy_button = buttons.addButton(
            "Copy TSV", QtWidgets.QDialogButtonBox.ActionRole
        )
        save_button = buttons.addButton(
            "Save TSV…", QtWidgets.QDialogButtonBox.ActionRole
        )
        copy_button.clicked.connect(self.copy_report)
        save_button.clicked.connect(self.save_report)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(report)
        layout.addWidget(buttons)

    def copy_report(self):
        QtWidgets.QApplication.clipboard().setText(self.report_text)

    def save_report(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save ToF-E theory overlay report",
            str(self.default_path),
            "Tab-separated values (*.tsv);;All files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".tsv")
        try:
            path.write_text(self.report_text, encoding="utf-8")
        except OSError as error:
            QtWidgets.QMessageBox.warning(
                self, "Theory report", str(error), QtWidgets.QMessageBox.Ok
            )
