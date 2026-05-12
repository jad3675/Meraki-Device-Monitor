"""Alert timeline dialog showing historical alert events."""

import csv
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from meraki_monitor.utils import format_timestamp, summarize_alert_data
from meraki_monitor.workers import TimelineWorker

TIMELINE_COLUMNS: list[tuple[str, str]] = [
    ("occurredAt", "Occurred"),
    ("deviceName", "Device"),
    ("serial", "Serial"),
    ("alertType", "Alert Type"),
    ("details", "Details"),
]


class TimelineTableModel(QAbstractTableModel):
    """Chronological alert timeline for a selection of devices."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def reset_data(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(TIMELINE_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return TIMELINE_COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = TIMELINE_COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "occurredAt":
                return format_timestamp(row.get("occurredAt", ""))
            if key == "details":
                return summarize_alert_data(row.get("alertData", {}))
            return str(row.get(key, "") or "")

        if role == Qt.ItemDataRole.UserRole + 1:
            if key == "occurredAt":
                return str(row.get("occurredAt", "") or "")
            return str(row.get(key, "") or "").lower()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None


class TimelineDialog(QDialog):
    """Shows alert history for the selected devices."""

    def __init__(
        self,
        api_key: str,
        org_id: str,
        devices: list[dict],
        alert_type_ids: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._devices = devices
        self._alert_type_ids = set(alert_type_ids) if alert_type_ids else None
        self._serial_to_name = {
            d.get("serial", ""): d.get("name", "") for d in devices if d.get("serial")
        }
        self._worker: TimelineWorker | None = None

        title = f"Alert Timeline \u2014 {len(devices)} device(s)"
        if self._alert_type_ids:
            types_str = ", ".join(sorted(self._alert_type_ids)[:3])
            if len(self._alert_type_ids) > 3:
                types_str += f" (+{len(self._alert_type_ids) - 3} more)"
            title += f" \u2014 {types_str}"
        self.setWindowTitle(title)
        self.resize(1050, 550)
        self.setMinimumSize(700, 360)

        self._setup_ui()
        self._start_fetch()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._progress_label = QLabel("Fetching alert history...")
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        layout.addWidget(self._progress_bar)

        self._model = TimelineTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setHighlightSections(False)

        widths = [170, 180, 140, 220, 320]
        header = self._table.horizontalHeader()
        for i, w in enumerate(widths):
            header.resizeSection(i, w)

        layout.addWidget(self._table, stretch=1)

        btns = QHBoxLayout()
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        btns.addWidget(self._export_btn)
        btns.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        layout.addLayout(btns)

    def _start_fetch(self):
        network_ids = list({
            d.get("networkId", "") for d in self._devices if d.get("networkId")
        })
        serials = {d.get("serial", "") for d in self._devices if d.get("serial")}

        if not network_ids:
            self._progress_label.setText("No networks to query.")
            self._progress_bar.hide()
            return

        self._worker = TimelineWorker(
            self._api_key, self._org_id, network_ids, serials,
            alert_type_ids=self._alert_type_ids, parent=self
        )
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._progress_label.setText(
            f"Fetching alert history... ({current}/{total} networks)"
        )

    def _on_data_ready(self, entries: list[dict]):
        for e in entries:
            e["deviceName"] = self._serial_to_name.get(e.get("serial", ""), "")
        self._model.reset_data(entries)

        if not entries:
            self._progress_label.setText(
                "No alert history found for the selected devices in the "
                "available timeframe."
            )
            self._progress_label.setStyleSheet("color: #9e9e9e;")
        else:
            earliest = entries[-1].get("occurredAt", "")
            latest = entries[0].get("occurredAt", "")
            self._progress_label.setText(
                f"{len(entries)} alert event(s) \u2014 "
                f"{format_timestamp(earliest)} to {format_timestamp(latest)}"
            )
            self._progress_label.setStyleSheet("")
            self._export_btn.setEnabled(True)

        self._table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _on_error(self, message: str):
        self._progress_label.setText(f"Error: {message}")
        self._progress_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")

    def _on_finished(self):
        self._progress_bar.hide()
        self._worker = None

    def _export_csv(self):
        default_name = (
            f"meraki_alert_timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Alert Timeline", default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "Occurred", "Device Name", "Serial", "Network ID",
                    "Alert Type", "Alert Type ID", "Details",
                ])
                for row in self._model._rows:
                    writer.writerow([
                        format_timestamp(row.get("occurredAt", "")),
                        row.get("deviceName", ""),
                        row.get("serial", ""),
                        row.get("networkId", ""),
                        row.get("alertType", ""),
                        row.get("alertTypeId", ""),
                        summarize_alert_data(row.get("alertData", {})),
                    ])
            self._progress_label.setText(f"Exported to {Path(path).name}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()
