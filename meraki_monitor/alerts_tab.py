"""Alerts tab widget — shows active alert conditions and affected devices."""

import csv
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from meraki_monitor.constants import SEVERITY_COLORS, SEVERITY_ORDER
from meraki_monitor.delegates import StatusDelegate

ALERT_GROUP_COLUMNS: list[tuple[str, str]] = [
    ("severity", "Severity"),
    ("type", "Alert Type"),
    ("category", "Category"),
    ("device_count", "Devices"),
    ("network_count", "Networks"),
]

AFFECTED_DEVICE_COLUMNS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("serial", "Serial"),
    ("model", "Model"),
    ("productType", "Product Type"),
    ("status", "Status"),
    ("networkId", "Network ID"),
    ("lanIp", "LAN IP"),
]


def _alert_key(alert: dict) -> tuple[str, str, str]:
    """Group alerts by (severity, type, category)."""
    return (
        (alert.get("severity") or "").lower(),
        alert.get("type") or "Unknown",
        alert.get("category") or "",
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AlertGroupsModel(QAbstractTableModel):
    """Lists distinct alert conditions across the org, with per-alert counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def reset_data(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def group_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(ALERT_GROUP_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ALERT_GROUP_COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        key = ALERT_GROUP_COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "severity":
                return str(row.get("severity", "") or "").capitalize() or "\u2014"
            if key == "device_count":
                return str(row.get("device_count", 0))
            if key == "network_count":
                return str(row.get("network_count", 0))
            return str(row.get(key, "") or "")

        if role == Qt.ItemDataRole.UserRole + 1:
            if key == "severity":
                return SEVERITY_ORDER.get(row.get("severity", ""), 99)
            if key in ("device_count", "network_count"):
                return row.get(key, 0)
            return str(row.get(key, "") or "").lower()

        if role == Qt.ItemDataRole.ForegroundRole and key == "severity":
            color_hex = SEVERITY_COLORS.get(row.get("severity", ""), None)
            if color_hex:
                return QColor(color_hex)

        if role == Qt.ItemDataRole.FontRole and key == "severity":
            f = QFont()
            f.setBold(True)
            return f

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("device_count", "network_count"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None


class AlertGroupsProxyModel(QSortFilterProxyModel):
    """Sorts alert groups; supports text search across all columns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text_filter: str = ""
        self._severity_filter: str = ""

    def set_text_filter(self, text: str):
        self._text_filter = text.lower().strip()
        self.invalidateFilter()

    def set_severity_filter(self, severity: str):
        self._severity_filter = severity.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: AlertGroupsModel = self.sourceModel()
        row = model._rows[source_row]

        if self._severity_filter and row.get("severity", "") != self._severity_filter:
            return False

        if self._text_filter:
            blob = " ".join(
                str(row.get(k, "") or "")
                for k in ("severity", "type", "category")
            ).lower()
            if self._text_filter not in blob:
                return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        sort_role = Qt.ItemDataRole.UserRole + 1
        lv = left.data(sort_role)
        rv = right.data(sort_role)
        if lv is None:
            lv = ""
        if rv is None:
            rv = ""
        try:
            return lv < rv
        except TypeError:
            return str(lv) < str(rv)


class AffectedDevicesModel(QAbstractTableModel):
    """Lists the devices affected by a selected alert group."""

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
        return len(AFFECTED_DEVICE_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return AFFECTED_DEVICE_COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = AFFECTED_DEVICE_COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "status":
                return str(row.get("status", "") or "").capitalize()
            return str(row.get(key, "") or "")

        if role == Qt.ItemDataRole.UserRole:
            if key == "status":
                return str(row.get("status", "") or "").lower()
            return str(row.get(key, "") or "").lower()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key == "status":
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class AlertsTab(QWidget):
    """Tab showing active alert conditions and affected devices."""

    show_in_devices_requested = pyqtSignal(list)  # list of serials
    show_timeline_requested = pyqtSignal(list)  # list of device dicts

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups_model = AlertGroupsModel(self)
        self._groups_proxy = AlertGroupsProxyModel(self)
        self._groups_proxy.setSourceModel(self._groups_model)
        self._devices_model = AffectedDevicesModel(self)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_row.addWidget(QLabel("Severity:"))
        self._severity_combo = QComboBox()
        self._severity_combo.addItem("All", "")
        self._severity_combo.addItem("Critical", "critical")
        self._severity_combo.addItem("Warning", "warning")
        self._severity_combo.addItem("Informational", "informational")
        self._severity_combo.currentIndexChanged.connect(self._on_severity_changed)
        filter_row.addWidget(self._severity_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search alert type or category...")
        self._search.setMinimumWidth(220)
        self._search.textChanged.connect(self._groups_proxy.set_text_filter)
        filter_row.addWidget(self._search)

        filter_row.addStretch()

        self._summary_label = QLabel("No alerts loaded.")
        self._summary_label.setStyleSheet("color: #9e9e9e;")
        filter_row.addWidget(self._summary_label)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        filter_row.addWidget(self._export_btn)

        layout.addLayout(filter_row)

        # Splitter: alerts list | affected devices
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: groups table
        left = QWidget()
        left_lo = QVBoxLayout(left)
        left_lo.setContentsMargins(0, 0, 0, 0)
        left_lo.setSpacing(4)
        left_lo.addWidget(QLabel("Alert Conditions"))

        self._groups_view = QTableView()
        self._groups_view.setModel(self._groups_proxy)
        self._groups_view.setSortingEnabled(True)
        self._groups_view.setAlternatingRowColors(True)
        self._groups_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._groups_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._groups_view.verticalHeader().setVisible(False)
        self._groups_view.setShowGrid(False)
        self._groups_view.horizontalHeader().setStretchLastSection(True)
        self._groups_view.horizontalHeader().setHighlightSections(False)
        self._groups_view.selectionModel().selectionChanged.connect(
            self._on_group_selected
        )
        self._groups_view.doubleClicked.connect(self._on_group_double_clicked)

        header = self._groups_view.horizontalHeader()
        for i, w in enumerate([90, 240, 160, 80, 80]):
            header.resizeSection(i, w)

        left_lo.addWidget(self._groups_view, stretch=1)

        # Right: affected devices
        right = QWidget()
        right_lo = QVBoxLayout(right)
        right_lo.setContentsMargins(0, 0, 0, 0)
        right_lo.setSpacing(4)

        self._affected_label = QLabel("Affected Devices")
        right_lo.addWidget(self._affected_label)

        self._devices_view = QTableView()
        self._devices_view.setModel(self._devices_model)
        self._devices_view.setAlternatingRowColors(True)
        self._devices_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._devices_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._devices_view.verticalHeader().setVisible(False)
        self._devices_view.setShowGrid(False)
        self._devices_view.horizontalHeader().setStretchLastSection(True)
        self._devices_view.horizontalHeader().setHighlightSections(False)
        status_col = next(
            (i for i, (k, _) in enumerate(AFFECTED_DEVICE_COLUMNS) if k == "status"), -1
        )
        if status_col >= 0:
            self._devices_view.setItemDelegateForColumn(status_col, StatusDelegate(self))

        header = self._devices_view.horizontalHeader()
        for i, w in enumerate([200, 140, 110, 110, 100, 200, 110]):
            header.resizeSection(i, w)

        right_lo.addWidget(self._devices_view, stretch=1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._timeline_btn = QPushButton("Show Timeline\u2026")
        self._timeline_btn.setEnabled(False)
        self._timeline_btn.setToolTip(
            "Show alert history for the devices affected by the selected alert"
        )
        self._timeline_btn.clicked.connect(self._show_timeline)
        btn_row.addWidget(self._timeline_btn)
        self._show_in_devices_btn = QPushButton("Show in Devices Tab \u2192")
        self._show_in_devices_btn.setEnabled(False)
        self._show_in_devices_btn.clicked.connect(self._emit_show_in_devices)
        btn_row.addWidget(self._show_in_devices_btn)
        right_lo.addLayout(btn_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([500, 700])

        layout.addWidget(splitter, stretch=1)

    # ---- Slots ----

    def _on_severity_changed(self, idx: int):
        value = self._severity_combo.itemData(idx) or ""
        self._groups_proxy.set_severity_filter(value)

    def _on_group_selected(self, *_):
        group = self._current_group()
        if not group:
            self._devices_model.reset_data([])
            self._affected_label.setText("Affected Devices")
            self._show_in_devices_btn.setEnabled(False)
            self._timeline_btn.setEnabled(False)
            return

        devices = group.get("devices", [])
        self._devices_model.reset_data(devices)
        label = group.get("type") or group.get("category") or "Alert"
        self._affected_label.setText(
            f"Affected Devices \u2014 {label} ({len(devices)})"
        )
        self._show_in_devices_btn.setEnabled(bool(devices))
        self._timeline_btn.setEnabled(bool(devices))

    def _on_group_double_clicked(self, _index: QModelIndex):
        self._emit_show_in_devices()

    def _current_group(self) -> dict | None:
        sel = self._groups_view.selectionModel().selectedRows()
        if not sel:
            return None
        source_idx = self._groups_proxy.mapToSource(sel[0])
        return self._groups_model.group_at(source_idx.row())

    def _emit_show_in_devices(self):
        group = self._current_group()
        if not group:
            return
        serials = [d.get("serial", "") for d in group.get("devices", []) if d.get("serial")]
        if serials:
            self.show_in_devices_requested.emit(serials)

    def _show_timeline(self):
        sel = self._devices_view.selectionModel().selectedRows()
        if sel:
            rows = [self._devices_model._rows[i.row()] for i in sel]
        else:
            group = self._current_group()
            rows = group.get("devices", []) if group else []
        if rows:
            self.show_timeline_requested.emit(rows)

    # ---- Public ----

    def update_data(self, devices: list[dict]):
        """Rebuild the alert groups from the device list."""
        groups: dict[tuple, dict] = {}
        for device in devices:
            for alert in device.get("alerts", []) or []:
                key = _alert_key(alert)
                sev, atype, cat = key
                g = groups.setdefault(key, {
                    "severity": sev,
                    "type": atype,
                    "category": cat,
                    "devices": [],
                    "_serials": set(),
                    "_networks": set(),
                })
                serial = device.get("serial", "")
                if serial and serial not in g["_serials"]:
                    g["_serials"].add(serial)
                    g["devices"].append(device)
                net = device.get("networkId", "")
                if net:
                    g["_networks"].add(net)

        rows = []
        for g in groups.values():
            rows.append({
                "severity": g["severity"],
                "type": g["type"],
                "category": g["category"],
                "device_count": len(g["devices"]),
                "network_count": len(g["_networks"]),
                "devices": g["devices"],
            })

        rows.sort(key=lambda r: (
            SEVERITY_ORDER.get(r["severity"], 99),
            -r["device_count"],
        ))

        self._groups_model.reset_data(rows)

        total_alerts = sum(len(d.get("alerts", [])) for d in devices)
        unique = len(rows)
        if total_alerts == 0:
            self._summary_label.setText("No active alerts.")
            self._summary_label.setStyleSheet("color: #4CAF50;")
        else:
            crit = sum(1 for r in rows if r["severity"] == "critical")
            warn = sum(1 for r in rows if r["severity"] == "warning")
            self._summary_label.setText(
                f"{unique} alert conditions, {total_alerts} alerts "
                f"(crit: {crit}, warn: {warn})"
            )
            color = "#F44336" if crit else "#FFC107" if warn else "#2196F3"
            self._summary_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        self._devices_model.reset_data([])
        self._affected_label.setText("Affected Devices")
        self._show_in_devices_btn.setEnabled(False)
        self._timeline_btn.setEnabled(False)
        self._export_btn.setEnabled(bool(rows))

    # ---- Export ----

    def _export_csv(self):
        """Export one row per (alert condition x affected device) pair."""
        rows = self._groups_model._rows
        if not rows:
            return

        default_name = (
            f"meraki_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Alerts Report", default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        headers = [
            "Severity", "Alert Type", "Category",
            "Device Count", "Network Count",
            "Device Name", "Serial", "Model", "Product Type",
            "Device Status", "Network ID", "LAN IP",
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(headers)
                for group in rows:
                    severity = str(group.get("severity", "") or "").capitalize()
                    gtype = group.get("type", "") or ""
                    cat = group.get("category", "") or ""
                    dev_count = group.get("device_count", 0)
                    net_count = group.get("network_count", 0)
                    devices = group.get("devices", [])

                    if not devices:
                        writer.writerow([
                            severity, gtype, cat,
                            dev_count, net_count,
                            "", "", "", "", "", "", "",
                        ])
                        continue

                    for device in devices:
                        writer.writerow([
                            severity, gtype, cat,
                            dev_count, net_count,
                            device.get("name", ""),
                            device.get("serial", ""),
                            device.get("model", ""),
                            device.get("productType", ""),
                            str(device.get("status", "") or "").capitalize(),
                            device.get("networkId", ""),
                            device.get("lanIp", ""),
                        ])
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

        QToolTip.showText(
            self._export_btn.mapToGlobal(self._export_btn.rect().bottomLeft()),
            f"Exported to {Path(path).name}",
            self._export_btn,
        )
