"""Column chooser dialog for toggling extra table columns."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from meraki_monitor.constants import EXTRA_COLUMNS


class ColumnChooserDialog(QDialog):
    """Lets the user toggle extra columns on or off."""

    def __init__(self, enabled_keys: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Columns")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        info = QLabel("Select additional columns to display:")
        layout.addWidget(info)

        self._checkboxes: list[tuple[str, QCheckBox]] = []
        for key, label in EXTRA_COLUMNS:
            cb = QCheckBox(label)
            cb.setChecked(key in enabled_keys)
            layout.addWidget(cb)
            self._checkboxes.append((key, cb))

        layout.addSpacing(8)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_keys(self) -> set[str]:
        return {key for key, cb in self._checkboxes if cb.isChecked()}
