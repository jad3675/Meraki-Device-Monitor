"""Meraki Device Monitor - PyQt6 GUI application for monitoring Cisco Meraki devices."""

import csv
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableView,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MERAKI_BASE_URL = "https://api.meraki.com/api/v1"

BASE_COLUMNS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("serial", "Serial"),
    ("model", "Model"),
    ("productType", "Product Type"),
    ("networkId", "Network ID"),
    ("mac", "MAC"),
    ("lanIp", "LAN IP"),
    ("publicIp", "Public IP"),
    ("firmware", "Firmware"),
    ("status", "Status"),
    ("lastReportedAt", "Last Reported"),
]

# Extra columns that can be toggled on/off via the Columns dialog.
# These fields come from the existing API responses at no extra cost.
EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("alertCount", "Alerts"),
    ("address", "Location"),
    ("notes", "Notes"),
    ("tags", "Tags"),
    ("gateway", "Gateway"),
    ("ipType", "IP Type"),
    ("primaryDns", "Primary DNS"),
    ("secondaryDns", "Secondary DNS"),
    ("lat", "Latitude"),
    ("lng", "Longitude"),
    ("lastBootedAt", "Last Boot"),
]

# Active column list — starts with base only; mutated at runtime.
COLUMNS: list[tuple[str, str]] = list(BASE_COLUMNS)

def _status_col_index() -> int:
    """Return the current column index of the 'status' field."""
    for i, (key, _) in enumerate(COLUMNS):
        if key == "status":
            return i
    return -1

PRODUCT_TYPES = [
    "wireless",
    "appliance",
    "switch",
    "camera",
    "cellularGateway",
    "sensor",
]

STATUS_COLORS: dict[str, str] = {
    "online": "#4CAF50",
    "alerting": "#FFC107",
    "offline": "#F44336",
    "dormant": "#9E9E9E",
}

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#F44336",
    "warning": "#FFC107",
    "informational": "#2196F3",
    "info": "#2196F3",
}

SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "informational": 2,
    "info": 2,
}

CADENCE_OPTIONS: list[tuple[str, int]] = [
    ("30s", 30_000),
    ("1m", 60_000),
    ("2m", 120_000),
    ("5m", 300_000),
]

DEFAULT_COLUMN_WIDTHS = [200, 140, 110, 110, 200, 140, 110, 110, 150, 100, 160]

# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
}
QFrame#connection_panel, QFrame#controls_bar {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 8px;
}
QLineEdit, QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 5px 8px;
    color: #e0e0e0;
    selection-background-color: #0078d7;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0078d7;
}
QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #094771;
    border: 1px solid #555555;
}
QPushButton {
    background-color: #0e639c;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    color: #ffffff;
    font-weight: bold;
    min-height: 22px;
}
QPushButton:hover { background-color: #1177bb; }
QPushButton:pressed { background-color: #0a4f7e; }
QPushButton:disabled { background-color: #3c3c3c; color: #6e6e6e; }
QPushButton#clear_btn {
    background-color: #5a5a5a;
}
QPushButton#clear_btn:hover { background-color: #6e6e6e; }
QPushButton#theme_btn {
    background-color: #3c3c3c;
    padding: 6px 12px;
}
QPushButton#theme_btn:hover { background-color: #4e4e4e; }
QTableView {
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    color: #e0e0e0;
    gridline-color: transparent;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    selection-background-color: #094771;
    selection-color: #ffffff;
    outline: none;
}
QTableView::item {
    padding: 4px 6px;
    border-bottom: 1px solid #2a2a2a;
}
QTableView::item:selected {
    background-color: #094771;
}
QHeaderView::section {
    background-color: #2d2d2d;
    color: #cccccc;
    border: none;
    border-right: 1px solid #3c3c3c;
    border-bottom: 2px solid #3c3c3c;
    padding: 6px 8px;
    font-weight: bold;
}
QHeaderView::section:hover { background-color: #333333; }
QHeaderView::section:pressed { background-color: #094771; }
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #777777; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background-color: #777777; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QStatusBar {
    background-color: #007acc;
    color: #ffffff;
    font-size: 12px;
}
QStatusBar QLabel {
    color: #ffffff;
}
QCheckBox { color: #e0e0e0; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #555555;
    border-radius: 3px;
    background-color: #2d2d2d;
}
QCheckBox::indicator:checked {
    background-color: #0078d7;
    border-color: #0078d7;
}
QLabel { color: #e0e0e0; }
QToolTip {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 4px;
}
"""

LIGHT_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #f5f5f5;
    color: #1e1e1e;
}
QFrame#connection_panel, QFrame#controls_bar {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 8px;
}
QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 3px;
    padding: 5px 8px;
    color: #1e1e1e;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0078d7;
}
QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1e1e1e;
    selection-background-color: #cce8ff;
    selection-color: #000000;
    border: 1px solid #cccccc;
}
QPushButton {
    background-color: #0078d7;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    color: #ffffff;
    font-weight: bold;
    min-height: 22px;
}
QPushButton:hover { background-color: #1084e0; }
QPushButton:pressed { background-color: #005fa3; }
QPushButton:disabled { background-color: #cccccc; color: #888888; }
QPushButton#clear_btn {
    background-color: #888888;
}
QPushButton#clear_btn:hover { background-color: #999999; }
QPushButton#theme_btn {
    background-color: #e0e0e0;
    color: #333333;
    padding: 6px 12px;
}
QPushButton#theme_btn:hover { background-color: #d0d0d0; }
QTableView {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    color: #1e1e1e;
    gridline-color: transparent;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    selection-background-color: #cce8ff;
    selection-color: #000000;
    outline: none;
}
QTableView::item {
    padding: 4px 6px;
    border-bottom: 1px solid #eeeeee;
}
QTableView::item:selected {
    background-color: #cce8ff;
}
QHeaderView::section {
    background-color: #f0f0f0;
    color: #333333;
    border: none;
    border-right: 1px solid #d0d0d0;
    border-bottom: 2px solid #d0d0d0;
    padding: 6px 8px;
    font-weight: bold;
}
QHeaderView::section:hover { background-color: #e8e8e8; }
QHeaderView::section:pressed { background-color: #cce8ff; }
QScrollBar:vertical {
    background-color: #f5f5f5;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #a0a0a0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal {
    background-color: #f5f5f5;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #c0c0c0;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background-color: #a0a0a0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QStatusBar {
    background-color: #007acc;
    color: #ffffff;
    font-size: 12px;
}
QStatusBar QLabel {
    color: #ffffff;
}
QCheckBox { color: #1e1e1e; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #cccccc;
    border-radius: 3px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #0078d7;
    border-color: #0078d7;
}
QLabel { color: #1e1e1e; }
QToolTip {
    background-color: #ffffff;
    color: #1e1e1e;
    border: 1px solid #cccccc;
    padding: 4px;
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_next_link(link_header: str) -> str | None:
    """Parse RFC 5988 Link header and return the 'next' URL, or None."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part or "rel=next" in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def _format_timestamp(iso_str: str | None) -> str:
    """Convert ISO 8601 timestamp to local human-friendly string."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(iso_str)


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class MerakiAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MerakiClient:
    """Handles Meraki Dashboard API v1 requests with pagination and rate-limit retry."""

    def __init__(self, api_key: str, org_id: str):
        self._org_id = org_id
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def _get_with_retry(
        self, url: str, params: dict | None = None, retries: int = 3
    ) -> requests.Response:
        for attempt in range(retries):
            try:
                resp = self._session.get(url, params=params, timeout=30)
            except requests.ConnectionError:
                raise MerakiAPIError(
                    "Cannot reach api.meraki.com. Check your network connection."
                )
            except requests.Timeout:
                raise MerakiAPIError("Request timed out (30s). Check connectivity.")

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                time.sleep(retry_after + 0.1)
                continue

            if resp.status_code == 401:
                raise MerakiAPIError(
                    "Authentication failed: invalid API key.", 401
                )
            if resp.status_code == 403:
                raise MerakiAPIError(
                    "Access denied: check your Org ID and API key permissions.", 403
                )
            if resp.status_code == 404:
                raise MerakiAPIError(
                    "Organization not found. Verify your Org ID.", 404
                )
            if not resp.ok:
                body = resp.text[:300] if resp.text else "No details"
                raise MerakiAPIError(
                    f"API error {resp.status_code}: {body}", resp.status_code
                )

            return resp

        raise MerakiAPIError("Rate limited after multiple retries.", 429)

    def _get_paginated(
        self,
        url: str,
        per_page: int,
        stop_event: threading.Event,
    ) -> list[dict]:
        results: list[dict] = []
        params: dict = {"perPage": per_page}
        current_url = url

        while current_url:
            if stop_event.is_set():
                return results

            resp = self._get_with_retry(current_url, params)
            page_data = resp.json()

            if isinstance(page_data, list):
                results.extend(page_data)
            else:
                results.append(page_data)

            current_url = _parse_next_link(resp.headers.get("Link", ""))
            params = {}  # next URL already has query params encoded

        return results

    def fetch_devices(self, stop_event: threading.Event) -> list[dict]:
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices"
        return self._get_paginated(url, 1000, stop_event)

    def fetch_statuses(self, stop_event: threading.Event) -> list[dict]:
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices/statuses"
        return self._get_paginated(url, 1000, stop_event)

    def fetch_boot_history(self, stop_event: threading.Event) -> list[dict]:
        """Fetch most recent boot per device (beta, MS-only)."""
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices/boots/history"
        try:
            return self._get_paginated(url, 1000, stop_event)
        except MerakiAPIError:
            # Beta endpoint — may 404 on some orgs; silently degrade.
            return []

    def fetch_health_alerts(
        self,
        network_id: str,
        stop_event: threading.Event,
    ) -> list[dict]:
        """Fetch health alerts for a specific network."""
        if stop_event.is_set():
            return []
        url = f"{MERAKI_BASE_URL}/networks/{network_id}/health/alerts"
        resp = self._get_with_retry(url)
        data = resp.json()
        return data if isinstance(data, list) else []

    def fetch_all(
        self,
        stop_event: threading.Event,
        progress_cb=None,
    ) -> dict:
        """Fetch devices, statuses, boot history, and health alerts.

        Returns a dict:
            {
                "devices": [...],                # each device has "alerts": [...]
                "alerts_by_network": {netId: [alerts]},
            }
        """
        if progress_cb:
            progress_cb("Fetching devices...")
        devices = self.fetch_devices(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        if progress_cb:
            progress_cb(f"Found {len(devices)} devices. Fetching statuses...")
        statuses = self.fetch_statuses(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        status_map = {s["serial"]: s for s in statuses}
        for device in devices:
            entry = status_map.get(device.get("serial", ""), {})
            device["status"] = entry.get("status", "")
            device["publicIp"] = entry.get("publicIp", "")
            device["lastReportedAt"] = entry.get("lastReportedAt", "")
            device["gateway"] = entry.get("gateway", "")
            device["ipType"] = entry.get("ipType", "")
            device["primaryDns"] = entry.get("primaryDns", "")
            device["secondaryDns"] = entry.get("secondaryDns", "")
            # Normalise tags list to comma-separated string for display
            tags = device.get("tags")
            if isinstance(tags, list):
                device["tags"] = ", ".join(tags)

        # Fetch boot history (best-effort, beta endpoint)
        if progress_cb:
            progress_cb("Fetching boot history...")
        boots = self.fetch_boot_history(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        boot_map: dict[str, str] = {}
        for entry in boots:
            serial = entry.get("serial", "")
            booted_at = (entry.get("start") or {}).get("bootedAt", "")
            if serial and booted_at and serial not in boot_map:
                boot_map[serial] = booted_at
        for device in devices:
            device["lastBootedAt"] = boot_map.get(device.get("serial", ""), "")

        # Fetch health alerts per unique network
        network_ids = list({d.get("networkId", "") for d in devices if d.get("networkId")})
        alerts_by_network: dict[str, list[dict]] = {}
        total_nets = len(network_ids)
        for i, net_id in enumerate(network_ids):
            if stop_event.is_set():
                return {"devices": [], "alerts_by_network": {}}
            if progress_cb:
                progress_cb(f"Fetching alerts... ({i + 1}/{total_nets} networks)")
            try:
                alerts_by_network[net_id] = self.fetch_health_alerts(net_id, stop_event)
            except MerakiAPIError:
                alerts_by_network[net_id] = []

        # Attach matching alerts to each device
        for device in devices:
            net_id = device.get("networkId", "")
            serial = device.get("serial", "")
            mac = device.get("mac", "")
            net_alerts = alerts_by_network.get(net_id, [])
            matched: list[dict] = []
            for alert in net_alerts:
                scope = alert.get("scope", {}) or {}
                scope_devices = scope.get("devices", []) or []
                if not scope_devices:
                    matched.append(alert)
                    continue
                for sd in scope_devices:
                    if sd.get("serial") == serial or (mac and sd.get("mac") == mac):
                        matched.append(alert)
                        break
            device["alerts"] = matched
            device["alertCount"] = len(matched)

        if progress_cb:
            progress_cb(f"Loaded {len(devices)} devices.")

        return {"devices": devices, "alerts_by_network": alerts_by_network}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class FetchWorker(QThread):
    """Fetches Meraki device data on a background thread."""

    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str, int)
    progress = pyqtSignal(str)

    def __init__(self, api_key: str, org_id: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            client = MerakiClient(self._api_key, self._org_id)
            payload = client.fetch_all(self._stop, self.progress.emit)
            if not self._stop.is_set():
                self.data_ready.emit(payload)
        except MerakiAPIError as exc:
            if not self._stop.is_set():
                self.error.emit(str(exc), exc.status_code or -1)
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Unexpected error: {exc}", -1)


class HealthAlertWorker(QThread):
    """Fetches health alerts for selected devices on a background thread."""

    # Emits list of dicts: [{device_info + "alerts": [...]}]
    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # (current, total)

    def __init__(self, api_key: str, org_id: str, devices: list[dict], parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._devices = devices
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            client = MerakiClient(self._api_key, self._org_id)
            results = []
            # Deduplicate network IDs and fetch alerts per network
            network_alerts: dict[str, list[dict]] = {}
            network_ids = list({d.get("networkId", "") for d in self._devices if d.get("networkId")})
            total = len(network_ids)

            for i, net_id in enumerate(network_ids):
                if self._stop.is_set():
                    return
                self.progress.emit(i + 1, total)
                try:
                    alerts = client.fetch_health_alerts(net_id, self._stop)
                    network_alerts[net_id] = alerts
                except MerakiAPIError:
                    network_alerts[net_id] = []

            for device in self._devices:
                serial = device.get("serial", "")
                net_id = device.get("networkId", "")
                status = device.get("status", "")
                all_net_alerts = network_alerts.get(net_id, [])

                # Filter alerts relevant to this specific device
                device_alerts = []
                for alert in all_net_alerts:
                    scope = alert.get("scope", {})
                    scope_devices = scope.get("devices", [])
                    # Match if alert references this device's serial/mac, or
                    # if alert has no device scope (network-wide)
                    device_match = False
                    if not scope_devices:
                        device_match = True
                    else:
                        for sd in scope_devices:
                            if sd.get("serial") == serial or sd.get("mac") == device.get("mac"):
                                device_match = True
                                break
                    if device_match:
                        device_alerts.append(alert)

                results.append({
                    "name": device.get("name", ""),
                    "serial": serial,
                    "model": device.get("model", ""),
                    "status": status,
                    "networkId": net_id,
                    "lanIp": device.get("lanIp", ""),
                    "publicIp": device.get("publicIp", ""),
                    "lastReportedAt": device.get("lastReportedAt", ""),
                    "alerts": device_alerts,
                })

            if not self._stop.is_set():
                self.data_ready.emit(results)
        except MerakiAPIError as exc:
            if not self._stop.is_set():
                self.error.emit(str(exc))
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Table Model
# ---------------------------------------------------------------------------


class DeviceTableModel(QAbstractTableModel):
    """Table model backed by a list of device dicts."""

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
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row_dict = self._rows[index.row()]
        key = COLUMNS[index.column()][0]
        raw = row_dict.get(key)

        if role == Qt.ItemDataRole.DisplayRole:
            if key in ("lastReportedAt", "lastBootedAt"):
                return _format_timestamp(raw)
            if key == "status":
                return str(raw or "").capitalize()
            if key == "alertCount":
                return str(raw) if raw else "0"
            return str(raw) if raw else ""

        if role == Qt.ItemDataRole.UserRole:
            return str(raw or "").lower()

        if role == Qt.ItemDataRole.UserRole + 1:
            if key in ("lastReportedAt", "lastBootedAt"):
                return str(raw or "")
            if key == "alertCount":
                return int(raw or 0)
            return str(raw or "").lower()

        if role == Qt.ItemDataRole.ForegroundRole and key == "alertCount":
            count = int(raw or 0)
            if count > 0:
                return QColor("#FFC107")

        if role == Qt.ItemDataRole.FontRole and key == "alertCount":
            count = int(raw or 0)
            if count > 0:
                f = QFont()
                f.setBold(True)
                return f

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("status", "lanIp", "publicIp", "alertCount"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None


# ---------------------------------------------------------------------------
# Proxy Model (filtering + sorting)
# ---------------------------------------------------------------------------


class DeviceProxyModel(QSortFilterProxyModel):
    """Filters by product type and supports custom sorting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._type_filter: str = ""
        self._text_filter: str = ""
        self._alerts_only: bool = False
        self._serials_filter: set[str] = set()

    def set_type_filter(self, product_type: str):
        self._type_filter = product_type
        self.invalidateFilter()

    def set_text_filter(self, text: str):
        self._text_filter = text.lower().strip()
        self.invalidateFilter()

    def set_alerts_only(self, enabled: bool):
        self._alerts_only = enabled
        self.invalidateFilter()

    def set_serials_filter(self, serials: set[str] | None):
        self._serials_filter = set(serials) if serials else set()
        self.invalidateFilter()

    def clear_serials_filter(self):
        self._serials_filter = set()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        row_dict = model._rows[source_row]

        if self._serials_filter:
            if row_dict.get("serial", "") not in self._serials_filter:
                return False

        if self._type_filter:
            if row_dict.get("productType", "") != self._type_filter:
                return False

        if self._alerts_only:
            if not row_dict.get("alerts"):
                return False

        if self._text_filter:
            searchable = " ".join(
                str(v or "") for v in row_dict.values()
            ).lower()
            if self._text_filter not in searchable:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        sort_role = Qt.ItemDataRole.UserRole + 1
        lv = left.data(sort_role) or ""
        rv = right.data(sort_role) or ""
        return str(lv) < str(rv)


# ---------------------------------------------------------------------------
# Status Delegate
# ---------------------------------------------------------------------------


class StatusDelegate(QStyledItemDelegate):
    """Paints a colored circle indicator next to the status text."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw selection / hover background
        style = QApplication.style()
        opt.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter)

        raw_status = index.data(Qt.ItemDataRole.UserRole) or ""
        display = index.data(Qt.ItemDataRole.DisplayRole) or ""
        color_hex = STATUS_COLORS.get(raw_status, "#9E9E9E")

        rect = option.rect
        circle_size = 10
        x = rect.left() + 10
        y = rect.top() + (rect.height() - circle_size) // 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color_hex))
        painter.drawEllipse(x, y, circle_size, circle_size)

        text_x = x + circle_size + 8
        text_rect = rect.adjusted(text_x - rect.left(), 0, 0, 0)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, display)
        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setHeight(max(hint.height(), 28))
        return hint


# ---------------------------------------------------------------------------
# Health Details Dialog
# ---------------------------------------------------------------------------

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

        # Progress area
        self._progress_label = QLabel("Fetching health alerts...")
        layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate initially
        layout.addWidget(self._progress_bar)

        # Table
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

        # Column widths
        widths = [180, 140, 100, 90, 60, 400]
        header = self._table.horizontalHeader()
        for i, w in enumerate(widths):
            header.resizeSection(i, w)

        layout.addWidget(self._table, stretch=1)

        # Bottom buttons
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
                            _format_timestamp(row.get("lastReportedAt")),
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
                                _format_timestamp(row.get("lastReportedAt")),
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


# ---------------------------------------------------------------------------
# Column Chooser Dialog
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Alerts Tab
# ---------------------------------------------------------------------------


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


class AlertGroupsModel(QAbstractTableModel):
    """Lists distinct alert conditions across the org, with per-alert counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Each row: {severity, type, category, device_count, network_count, devices: [dict]}
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
                return str(row.get("severity", "") or "").capitalize() or "—"
            if key == "device_count":
                return str(row.get("device_count", 0))
            if key == "network_count":
                return str(row.get("network_count", 0))
            return str(row.get(key, "") or "")

        if role == Qt.ItemDataRole.UserRole + 1:
            # Sort role: severity sorts by SEVERITY_ORDER, counts sort numeric
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


class AlertsTab(QWidget):
    """Tab showing active alert conditions and affected devices."""

    # Emitted when the user asks to jump to the Devices tab filtered by a group
    show_in_devices_requested = pyqtSignal(list)  # list of serials

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
        # Status is column 4 in AFFECTED_DEVICE_COLUMNS
        status_col = next(
            (i for i, (k, _) in enumerate(AFFECTED_DEVICE_COLUMNS) if k == "status"), -1
        )
        if status_col >= 0:
            self._devices_view.setItemDelegateForColumn(status_col, StatusDelegate(self))

        header = self._devices_view.horizontalHeader()
        for i, w in enumerate([200, 140, 110, 110, 100, 200, 110]):
            header.resizeSection(i, w)

        right_lo.addWidget(self._devices_view, stretch=1)

        # Jump-to-devices button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._show_in_devices_btn = QPushButton("Show in Devices Tab →")
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

    def _on_severity_changed(self, idx: int):
        value = self._severity_combo.itemData(idx) or ""
        self._groups_proxy.set_severity_filter(value)

    def _on_group_selected(self, *_):
        group = self._current_group()
        if not group:
            self._devices_model.reset_data([])
            self._affected_label.setText("Affected Devices")
            self._show_in_devices_btn.setEnabled(False)
            return

        devices = group.get("devices", [])
        self._devices_model.reset_data(devices)
        label = group.get("type") or group.get("category") or "Alert"
        self._affected_label.setText(
            f"Affected Devices — {label} ({len(devices)})"
        )
        self._show_in_devices_btn.setEnabled(bool(devices))

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

        # Sort by severity first, then device count desc
        rows.sort(key=lambda r: (
            SEVERITY_ORDER.get(r["severity"], 99),
            -r["device_count"],
        ))

        self._groups_model.reset_data(rows)

        # Update summary label
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

        # Clear right pane
        self._devices_model.reset_data([])
        self._affected_label.setText("Affected Devices")
        self._show_in_devices_btn.setEnabled(False)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meraki Device Monitor")
        self.resize(1400, 800)

        self._is_fetching = False
        self._has_data = False
        self._is_dark = True
        self._worker: FetchWorker | None = None
        self._enabled_extra_cols: set[str] = set()

        self._setup_models()
        self._setup_ui()
        self._setup_timer()
        self._apply_theme(self._is_dark)
        self._update_controls_state()

    # ---- Models ----

    def _setup_models(self):
        self._table_model = DeviceTableModel(self)
        self._proxy_model = DeviceProxyModel(self)
        self._proxy_model.setSourceModel(self._table_model)

    # ---- UI ----

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 4)

        layout.addWidget(self._build_connection_panel())

        # Tabs: Devices | Alerts
        self._tabs = QTabWidget()

        devices_tab = QWidget()
        dv_lo = QVBoxLayout(devices_tab)
        dv_lo.setContentsMargins(0, 6, 0, 0)
        dv_lo.setSpacing(8)
        dv_lo.addWidget(self._build_controls_bar())
        dv_lo.addWidget(self._build_table(), stretch=1)
        self._tabs.addTab(devices_tab, "Devices")

        self._alerts_tab = AlertsTab()
        self._alerts_tab.show_in_devices_requested.connect(
            self._on_show_in_devices_requested
        )
        self._tabs.addTab(self._alerts_tab, "Alerts")

        layout.addWidget(self._tabs, stretch=1)
        self._build_status_bar()

    def _build_connection_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("connection_panel")
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        h.addWidget(QLabel("API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Enter Meraki API key")
        self._api_key_input.setMinimumWidth(260)
        h.addWidget(self._api_key_input)

        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setFixedWidth(55)
        self._show_key_btn.setObjectName("theme_btn")
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        h.addWidget(self._show_key_btn)

        h.addSpacing(16)
        h.addWidget(QLabel("Org ID:"))
        self._org_id_input = QLineEdit()
        self._org_id_input.setPlaceholderText("e.g. 123456")
        self._org_id_input.setMinimumWidth(160)
        h.addWidget(self._org_id_input)

        h.addSpacing(16)
        self._fetch_btn = QPushButton("Fetch Devices")
        self._fetch_btn.clicked.connect(self._on_fetch_clicked)
        h.addWidget(self._fetch_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("clear_btn")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        h.addWidget(self._clear_btn)

        h.addStretch()
        return frame

    def _build_controls_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("controls_bar")
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(10)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_fetch_clicked)
        h.addWidget(self._refresh_btn)

        self._auto_refresh_cb = QCheckBox("Auto-refresh")
        self._auto_refresh_cb.toggled.connect(self._on_auto_refresh_toggled)
        h.addWidget(self._auto_refresh_cb)

        self._cadence_combo = QComboBox()
        for label, _ in CADENCE_OPTIONS:
            self._cadence_combo.addItem(label)
        self._cadence_combo.setCurrentIndex(1)  # default 1m
        self._cadence_combo.currentIndexChanged.connect(self._on_cadence_changed)
        h.addWidget(self._cadence_combo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #555555;")
        h.addWidget(sep)

        h.addWidget(QLabel("Filter:"))
        self._type_combo = QComboBox()
        self._type_combo.addItem("All Types")
        for pt in PRODUCT_TYPES:
            self._type_combo.addItem(pt)
        self._type_combo.currentIndexChanged.connect(self._on_type_filter_changed)
        h.addWidget(self._type_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search devices...")
        self._search_input.setMinimumWidth(180)
        self._search_input.textChanged.connect(self._on_text_filter_changed)
        h.addWidget(self._search_input)

        self._alerts_only_cb = QCheckBox("Only with alerts")
        self._alerts_only_cb.toggled.connect(self._on_alerts_only_toggled)
        h.addWidget(self._alerts_only_cb)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #555555;")
        h.addWidget(sep2)

        self._health_btn = QPushButton("Health Details")
        self._health_btn.clicked.connect(self._show_health_details)
        h.addWidget(self._health_btn)

        self._columns_btn = QPushButton("Columns…")
        self._columns_btn.clicked.connect(self._show_column_chooser)
        h.addWidget(self._columns_btn)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._export_csv)
        h.addWidget(self._export_btn)

        h.addStretch()

        self._theme_btn = QPushButton("Light Mode")
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.clicked.connect(self._toggle_theme)
        h.addWidget(self._theme_btn)

        return frame

    def _build_table(self) -> QTableView:
        self._table_view = QTableView()
        self._table_view.setModel(self._proxy_model)
        self._table_view.setSortingEnabled(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._table_view.verticalHeader().setVisible(False)
        self._table_view.setShowGrid(False)
        self._table_view.horizontalHeader().setHighlightSections(False)
        self._table_view.horizontalHeader().setSortIndicatorShown(True)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setItemDelegateForColumn(
            _status_col_index(), StatusDelegate(self)
        )

        self._table_view.doubleClicked.connect(self._on_table_double_clicked)

        header = self._table_view.horizontalHeader()
        for i, w in enumerate(DEFAULT_COLUMN_WIDTHS):
            if i < len(COLUMNS):
                header.resizeSection(i, w)

        return self._table_view

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Ready")
        self._status_label.setMinimumWidth(300)
        sb.addWidget(self._status_label, stretch=1)

        # "Filtered by alert" pill — shown only when a serial filter is active
        self._filter_pill = QPushButton("")
        self._filter_pill.setVisible(False)
        self._filter_pill.setFlat(True)
        self._filter_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self._filter_pill.setStyleSheet(
            "QPushButton { background-color: #FFC107; color: #000000; "
            "padding: 2px 8px; border-radius: 8px; font-weight: bold; } "
            "QPushButton:hover { background-color: #FFD54F; }"
        )
        self._filter_pill.clicked.connect(self._clear_serial_filter)
        sb.addPermanentWidget(self._filter_pill)

        self._alert_count_label = QLabel("")
        sb.addPermanentWidget(self._alert_count_label)

        self._count_label = QLabel("")
        sb.addPermanentWidget(self._count_label)

        self._updated_label = QLabel("")
        sb.addPermanentWidget(self._updated_label)

    # ---- Timer ----

    def _setup_timer(self):
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(False)
        self._refresh_timer.timeout.connect(self._trigger_auto_fetch)
        ms = CADENCE_OPTIONS[self._cadence_combo.currentIndex()][1]
        self._refresh_timer.setInterval(ms)

    # ---- Actions ----

    def _toggle_key_visibility(self):
        if self._api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")

    def _validate_inputs(self) -> bool:
        key = self._api_key_input.text().strip()
        org = self._org_id_input.text().strip()

        if not key:
            QToolTip.showText(
                self._api_key_input.mapToGlobal(self._api_key_input.rect().bottomLeft()),
                "API key is required.",
            )
            self._api_key_input.setFocus()
            return False

        if not org:
            QToolTip.showText(
                self._org_id_input.mapToGlobal(self._org_id_input.rect().bottomLeft()),
                "Organization ID is required.",
            )
            self._org_id_input.setFocus()
            return False

        return True

    def _on_fetch_clicked(self):
        if not self._validate_inputs():
            return
        self._start_fetch()

    def _start_fetch(self):
        if self._is_fetching:
            return

        self._is_fetching = True
        self._update_controls_state()
        self._status_label.setStyleSheet("")
        self._status_label.setText("Connecting to Meraki API...")

        self._worker = FetchWorker(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            self,
        )
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.start()

    def _trigger_auto_fetch(self):
        if self._is_fetching:
            return
        if not self._api_key_input.text().strip() or not self._org_id_input.text().strip():
            return
        self._start_fetch()

    def _on_data_ready(self, payload: dict):
        devices = payload.get("devices", []) if isinstance(payload, dict) else []
        self._table_model.reset_data(devices)
        self._has_data = True
        self._update_count_label()
        self._update_alert_count_label(devices)

        # Push alerts to the Alerts tab
        self._alerts_tab.update_data(devices)

        # Update the Alerts tab badge
        total_alerts = sum(len(d.get("alerts", [])) for d in devices)
        if total_alerts:
            self._tabs.setTabText(1, f"Alerts ({total_alerts})")
        else:
            self._tabs.setTabText(1, "Alerts")

        now = datetime.now().strftime("%H:%M:%S")
        self._updated_label.setText(f"Updated: {now}")
        self._status_label.setStyleSheet("")
        self._status_label.setText(f"Loaded {len(devices)} devices.")

    def _on_fetch_error(self, message: str, status_code: int):
        self._status_label.setText(f"Error: {message}")
        self._status_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")

        if status_code in (401, 403):
            self._auto_refresh_cb.setChecked(False)
            self._refresh_timer.stop()
            QMessageBox.warning(self, "Authentication Error", message)

    def _on_progress(self, text: str):
        self._status_label.setText(text)

    def _on_fetch_finished(self):
        self._is_fetching = False
        self._worker = None
        self._update_controls_state()

    def _on_clear_clicked(self):
        if self._worker is not None:
            self._worker.cancel()

        self._auto_refresh_cb.setChecked(False)
        self._refresh_timer.stop()
        self._table_model.reset_data([])
        self._alerts_tab.update_data([])
        self._tabs.setTabText(1, "Alerts")
        self._has_data = False
        self._api_key_input.clear()
        self._org_id_input.clear()
        self._type_combo.setCurrentIndex(0)
        self._search_input.clear()
        self._alerts_only_cb.setChecked(False)
        self._proxy_model.clear_serials_filter()
        self._filter_pill.setVisible(False)
        self._status_label.setText("Ready")
        self._status_label.setStyleSheet("")
        self._count_label.setText("")
        self._alert_count_label.setText("")
        self._updated_label.setText("")
        self._update_controls_state()

    def _on_type_filter_changed(self, index: int):
        type_str = "" if index == 0 else PRODUCT_TYPES[index - 1]
        self._proxy_model.set_type_filter(type_str)
        self._update_count_label()

    def _on_text_filter_changed(self, text: str):
        self._proxy_model.set_text_filter(text)
        self._update_count_label()

    def _on_alerts_only_toggled(self, checked: bool):
        self._proxy_model.set_alerts_only(checked)
        self._update_count_label()

    def _on_show_in_devices_requested(self, serials: list):
        """Called when the Alerts tab asks to jump to devices filtered by serial."""
        if not serials:
            return
        self._proxy_model.set_serials_filter(set(serials))
        self._filter_pill.setText(f"✕  Filtered by alert ({len(serials)} devices)")
        self._filter_pill.setVisible(True)
        self._tabs.setCurrentIndex(0)  # switch to Devices tab
        self._update_count_label()

    def _clear_serial_filter(self):
        self._proxy_model.clear_serials_filter()
        self._filter_pill.setVisible(False)
        self._update_count_label()

    def _on_auto_refresh_toggled(self, checked: bool):
        if checked and self._has_data:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def _on_cadence_changed(self, index: int):
        ms = CADENCE_OPTIONS[index][1]
        was_active = self._refresh_timer.isActive()
        self._refresh_timer.setInterval(ms)
        if was_active:
            self._refresh_timer.start()

    def _update_count_label(self):
        if not self._has_data:
            self._count_label.setText("")
            return
        visible = self._proxy_model.rowCount()
        total = self._table_model.rowCount()
        if visible == total:
            self._count_label.setText(f"{total} devices")
        else:
            self._count_label.setText(f"{visible} / {total} devices")

    def _update_alert_count_label(self, devices: list[dict]):
        """Compose a colored alerts summary for the status bar."""
        if not devices:
            self._alert_count_label.setText("")
            return

        total_alerts = sum(len(d.get("alerts", [])) for d in devices)
        offline = sum(1 for d in devices if d.get("status", "").lower() == "offline")
        alerting = sum(1 for d in devices if d.get("status", "").lower() == "alerting")

        if total_alerts == 0 and offline == 0 and alerting == 0:
            self._alert_count_label.setText(
                "<span style='color:#4CAF50; font-weight:bold;'>✓ All healthy</span>"
            )
            return

        parts = []
        if total_alerts:
            parts.append(
                f"<span style='color:#FFC107; font-weight:bold;'>"
                f"⚠ {total_alerts} alert{'s' if total_alerts != 1 else ''}</span>"
            )
        if offline:
            parts.append(
                f"<span style='color:#F44336; font-weight:bold;'>"
                f"● {offline} offline</span>"
            )
        if alerting:
            parts.append(
                f"<span style='color:#FFC107;'>● {alerting} alerting</span>"
            )
        self._alert_count_label.setText(" &nbsp;|&nbsp; ".join(parts))

    def _update_controls_state(self):
        can_fetch = not self._is_fetching
        self._fetch_btn.setEnabled(can_fetch)
        self._refresh_btn.setEnabled(can_fetch and self._has_data)
        self._health_btn.setEnabled(self._has_data)
        self._export_btn.setEnabled(self._has_data)

    # ---- Column Chooser ----

    def _show_column_chooser(self):
        dlg = ColumnChooserDialog(self._enabled_extra_cols, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_keys = dlg.selected_keys()
            if new_keys != self._enabled_extra_cols:
                self._enabled_extra_cols = new_keys
                self._rebuild_columns()

    def _rebuild_columns(self):
        """Rebuild the global COLUMNS list and refresh the table."""
        COLUMNS.clear()
        COLUMNS.extend(BASE_COLUMNS)
        for key, label in EXTRA_COLUMNS:
            if key in self._enabled_extra_cols:
                COLUMNS.append((key, label))

        # Re-apply model so column count updates
        self._table_model.beginResetModel()
        self._table_model.endResetModel()

        # Re-assign the status delegate to the (possibly shifted) status column
        # First clear any old delegate
        for i in range(len(COLUMNS)):
            self._table_view.setItemDelegateForColumn(i, None)
        self._table_view.setItemDelegateForColumn(
            _status_col_index(), StatusDelegate(self)
        )

        # Resize columns to sensible defaults
        header = self._table_view.horizontalHeader()
        for i, (key, _) in enumerate(COLUMNS):
            if i < len(DEFAULT_COLUMN_WIDTHS) and i < len(BASE_COLUMNS):
                header.resizeSection(i, DEFAULT_COLUMN_WIDTHS[i])
            else:
                header.resizeSection(i, 140)
        header.setStretchLastSection(True)

    # ---- Health Details ----

    def _get_selected_devices(self) -> list[dict]:
        """Get device dicts for all selected rows in the table."""
        selection = self._table_view.selectionModel().selectedRows()
        if not selection:
            return []
        devices = []
        for proxy_idx in selection:
            source_idx = self._proxy_model.mapToSource(proxy_idx)
            row_dict = self._table_model._rows[source_idx.row()]
            devices.append(row_dict)
        return devices

    def _show_health_details(self):
        devices = self._get_selected_devices()
        if not devices:
            # If nothing selected, use all visible devices
            devices = []
            for i in range(self._proxy_model.rowCount()):
                source_idx = self._proxy_model.mapToSource(
                    self._proxy_model.index(i, 0)
                )
                devices.append(self._table_model._rows[source_idx.row()])

        if not devices:
            QMessageBox.information(
                self, "No Devices",
                "No devices to check. Fetch devices first."
            )
            return

        dialog = HealthDialog(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            devices,
            self,
        )
        dialog.exec()

    def _on_table_double_clicked(self, index: QModelIndex):
        """Double-click a row to show health details for that device."""
        source_idx = self._proxy_model.mapToSource(index)
        row_dict = self._table_model._rows[source_idx.row()]
        dialog = HealthDialog(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            [row_dict],
            self,
        )
        dialog.exec()

    # ---- Export ----

    def _export_csv(self):
        default_name = f"meraki_devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        col_keys = [c[0] for c in COLUMNS]
        col_headers = [c[1] for c in COLUMNS]
        proxy = self._proxy_model
        source = self._table_model

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(col_headers)
                for proxy_row in range(proxy.rowCount()):
                    source_idx = proxy.mapToSource(proxy.index(proxy_row, 0))
                    row_dict = source._rows[source_idx.row()]
                    row_out = []
                    for k in col_keys:
                        val = row_dict.get(k)
                        if k in ("lastReportedAt", "lastBootedAt"):
                            row_out.append(_format_timestamp(val))
                        else:
                            row_out.append(str(val) if val else "")
                    writer.writerow(row_out)

            self._status_label.setStyleSheet("")
            self._status_label.setText(
                f"Exported {proxy.rowCount()} rows to {Path(path).name}"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    # ---- Theme ----

    def _toggle_theme(self):
        self._apply_theme(not self._is_dark)

    def _apply_theme(self, dark: bool):
        self._is_dark = dark
        QApplication.instance().setStyleSheet(
            DARK_STYLESHEET if dark else LIGHT_STYLESHEET
        )
        self._theme_btn.setText("Light Mode" if dark else "Dark Mode")
        self._table_view.viewport().update()

    # ---- Lifecycle ----

    def closeEvent(self, event):
        self._refresh_timer.stop()
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
