"""Runtime settings dialog for the non-persistent ToF-E theory overlay."""

from PyQt5 import QtWidgets

from modules.tofe_theory import TheoryPredictionSettings


class TheoryPredictionDialog(QtWidgets.QDialog):
    """Collect inputs that Potku does not yet persist in detector settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ToF-E theory prediction")

        explanation = QtWidgets.QLabel(
            "Beam, energy, recoil angle and flight length are read from the "
            "current measurement. The overlay is not saved as a selection."
        )
        explanation.setWordWrap(True)

        self.element_edit = QtWidgets.QLineEdit("1H, 2H, 12C, 16O, 28Si")
        self.element_edit.setToolTip(
            "Comma- or space-separated symbols, optionally with isotope mass"
        )

        self.energy_slope = QtWidgets.QDoubleSpinBox()
        self.energy_slope.setDecimals(9)
        self.energy_slope.setRange(-1e6, 1e6)
        self.energy_slope.setValue(0.001)
        self.energy_slope.setSuffix(" MeV/channel")

        self.energy_offset = QtWidgets.QDoubleSpinBox()
        self.energy_offset.setDecimals(6)
        self.energy_offset.setRange(-1e6, 1e6)
        self.energy_offset.setValue(0.0)
        self.energy_offset.setSuffix(" MeV")

        self.minimum_fraction = QtWidgets.QDoubleSpinBox()
        self.minimum_fraction.setDecimals(3)
        self.minimum_fraction.setRange(0.001, 1.0)
        self.minimum_fraction.setSingleStep(0.01)
        self.minimum_fraction.setValue(0.08)

        form = QtWidgets.QFormLayout()
        form.addRow("Recoil isotopes/elements:", self.element_edit)
        form.addRow("Energy calibration slope:", self.energy_slope)
        form.addRow("Energy calibration offset:", self.energy_offset)
        form.addRow("Minimum energy fraction:", self.minimum_fraction)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def prediction_settings(self):
        """Return validated, Qt-independent settings for the calculator."""
        return TheoryPredictionSettings.from_text(
            self.element_edit.text(),
            self.energy_slope.value(),
            self.energy_offset.value(),
            self.minimum_fraction.value(),
        )
