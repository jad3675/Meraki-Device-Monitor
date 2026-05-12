"""Health details dialog showing alerts per device."""

import csv
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor
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

from meraki_monitor.constants import STATUS_COLORS
from meraki_monitor.delegates import StatusDelegate
from meraki_monitor.utils import format_timestamp
from meraki_monitor.workers import HealthAlertWorker

HEALTH_COLUMNS: list[tuple[str, str]] = [
    ("name", "Device Name"),
    ("serial", "Serial"),
    ("model", "Model"),
    ("status", "Status"),
    ("alert_count", "Alerts"),
    ("alert_summary", "Alert Details"),
]


class HealthTableModel(QAbstractTableModel):
    """Model for the health details dialog table."""

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
        return len(HEALTH_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEALTH_COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        key = HEALTH_COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "status":
                return str(row.get("status", "")).capitalize()
            if key == "alert_count":
                alerts = row.get("alerts", [])
                return str(len(alerts))
            if key == "alert_summary":
                alerts = row.get("alerts", [])
                if not alerts:
                    return "No active alerts"
                summaries = []
                for a in alerts:
                    category = a.get("category", "")
                    alert_type = a.get("type", "")
                    severity = a.get("severity", "")
                    label = alert_type or category or "Unknown alert"
                    if severity:
                        label = f"[{severity}] {label}"
                    summaries.append(label)
                return " | ".join(summaries)
            return str(row.get(key, "") or "")

        if role == Qt.ItemDataRole.UserRole:
            if key == "status":
                return str(row.get("status", "")).lower()
            return str(row.get(key, "") or "").lower()

        if role == Qt.ItemDataRole.BackgroundRole:
            status = row.get("status", "").lower()
            alerts = row.get("alerts", [])
            if status == "offline":
                return QColor("#3D1F1F")
            if status == "alerting" or alerts:
                return QColor("#3D3520")
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("alert_count", "status"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None


class HealthDialog(QDialog):
    """Dialog showing health status and alerts for selected devices."""

    def __init__(self, api_key: str, org_id: str, devices: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Device Health Details - {len(devices)} device(s)")
        self.resize(1000, 500)
        self.setMinimumSize(700, 300)

        self._api_key = api_key
        self._org_id = org_id
        self._devices = devices
        self._worker: HealthAlertWorker | None = None

        self._setup_ui()
        self._start_fetch()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._progress_label = QLabel("Fetching health alerts...")
        layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        layout.addWidget(self._progress_bar)

        self._model = HealthTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.setItemDelegateForColumn(3, StatusDelegate(self))

        widths = [180, 140, 100, 90, 60, 400]
        header = self._table.horizontalHeader()
        for i, w in enumerate(widths):
            header.resizeSection(i, w)

        layout.addWidget(self._table, stretch=1)

        btn_layout = QHBoxLayout()
        self._export_btn = QPushButton("Export Health Report")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(self._export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _start_fetch(self):
        self._worker = HealthAlertWorker(
            self._api_key, self._org_id, self._devices, self
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
            f"Fetching health alerts... ({current}/{total} networks)"
        )

    def _on_data_ready(self, results: list[dict]):
        self._model.reset_data(results)
        total_alerts = sum(len(r.get("alerts", [])) for r in results)
        alerting = sum(1 for r in results if r.get("alerts"))
        self._progress_label.setText(
            f"Health check complete: {len(results)} devices, "
            f"{alerting} with alerts, {total_alerts} total alerts"
        )
        self._export_btn.setEnabled(True)

    def _on_error(self, message: str):
        self._progress_label.setText(f"Error: {message}")
        self._progress_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")

    def _on_finished(self):
        self._progress_bar.hide()
        self._worker = None

    def _export_csv(self):
        default_name = f"meraki_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Health Report", default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "Device Name", "Serial", "Model", "Status",
                    "Network ID", "LAN IP", "Public IP", "Last Reported",
                    "Alert Count", "Alert Severity", "Alert Type",
                    "Alert Category", "Alert Details",
                ])
                for row in self._model._rows:
                    alerts = row.get("alerts", [])
                    if not alerts:
                        writer.writerow([
                            row.get("name", ""), row.get("serial", ""),
                            row.get("model", ""),
                            str(row.get("status", "")).capitalize(),
                            row.get("networkId", ""), row.get("lanIp", ""),
                            row.get("publicIp", ""),
                            format_timestamp(row.get("lastReportedAt")),
                            "0", "", "", "", "No active alerts",
                        ])
                    else:
                        for alert in alerts:
                            writer.writerow([
                                row.get("name", ""), row.get("serial", ""),
                                row.get("model", ""),
                                str(row.get("status", "")).capitalize(),
                                row.get("networkId", ""), row.get("lanIp", ""),
                                row.get("publicIp", ""),
                                format_timestamp(row.get("lastReportedAt")),
                                str(len(alerts)),
                                alert.get("severity", ""),
                                alert.get("type", ""),
                                alert.get("category", ""),
                                str(alert.get("scope", {}).get("peers", "")),
                            ])
            self._progress_label.setText(f"Exported to {Path(path).name}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()
