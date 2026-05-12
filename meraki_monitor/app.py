"""Main application window and entry point."""

import csv
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QModelIndex, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableView,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from meraki_monitor.alerts_tab import AlertsTab
from meraki_monitor.column_chooser import ColumnChooserDialog
from meraki_monitor.constants import (
    BASE_COLUMNS,
    CADENCE_OPTIONS,
    COLUMNS,
    DEFAULT_COLUMN_WIDTHS,
    EXTRA_COLUMNS,
    PRODUCT_TYPES,
    status_col_index,
)
from meraki_monitor.delegates import StatusDelegate
from meraki_monitor.health_dialog import HealthDialog
from meraki_monitor.models import DeviceProxyModel, DeviceTableModel
from meraki_monitor.styles import DARK_STYLESHEET, LIGHT_STYLESHEET
from meraki_monitor.timeline_dialog import TimelineDialog
from meraki_monitor.utils import format_timestamp
from meraki_monitor.workers import FetchWorker


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
        self._alerts_tab.show_timeline_requested.connect(
            self._on_show_timeline_requested
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
        self._cadence_combo.setCurrentIndex(1)
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

        self._timeline_btn = QPushButton("Timeline\u2026")
        self._timeline_btn.setToolTip("Show alert history for the selected devices")
        self._timeline_btn.clicked.connect(self._show_device_timeline)
        h.addWidget(self._timeline_btn)

        self._columns_btn = QPushButton("Columns\u2026")
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
            status_col_index(), StatusDelegate(self)
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
        self._alerts_tab.update_data(devices)

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
        if not serials:
            return
        self._proxy_model.set_serials_filter(set(serials))
        self._filter_pill.setText(f"\u2715  Filtered by alert ({len(serials)} devices)")
        self._filter_pill.setVisible(True)
        self._tabs.setCurrentIndex(0)
        self._update_count_label()

    def _on_show_timeline_requested(self, devices: list):
        if not devices:
            return
        dialog = TimelineDialog(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            devices,
            self,
        )
        dialog.exec()

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
        if not devices:
            self._alert_count_label.setText("")
            return
        total_alerts = sum(len(d.get("alerts", [])) for d in devices)
        offline = sum(1 for d in devices if d.get("status", "").lower() == "offline")
        alerting = sum(1 for d in devices if d.get("status", "").lower() == "alerting")

        if total_alerts == 0 and offline == 0 and alerting == 0:
            self._alert_count_label.setText(
                "<span style='color:#4CAF50; font-weight:bold;'>\u2713 All healthy</span>"
            )
            return
        parts = []
        if total_alerts:
            parts.append(
                f"<span style='color:#FFC107; font-weight:bold;'>"
                f"\u26a0 {total_alerts} alert{'s' if total_alerts != 1 else ''}</span>"
            )
        if offline:
            parts.append(
                f"<span style='color:#F44336; font-weight:bold;'>"
                f"\u25cf {offline} offline</span>"
            )
        if alerting:
            parts.append(
                f"<span style='color:#FFC107;'>\u25cf {alerting} alerting</span>"
            )
        self._alert_count_label.setText(" &nbsp;|&nbsp; ".join(parts))

    def _update_controls_state(self):
        can_fetch = not self._is_fetching
        self._fetch_btn.setEnabled(can_fetch)
        self._refresh_btn.setEnabled(can_fetch and self._has_data)
        self._health_btn.setEnabled(self._has_data)
        self._timeline_btn.setEnabled(self._has_data)
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
        COLUMNS.clear()
        COLUMNS.extend(BASE_COLUMNS)
        for key, label in EXTRA_COLUMNS:
            if key in self._enabled_extra_cols:
                COLUMNS.append((key, label))

        self._table_model.beginResetModel()
        self._table_model.endResetModel()

        for i in range(len(COLUMNS)):
            self._table_view.setItemDelegateForColumn(i, None)
        self._table_view.setItemDelegateForColumn(
            status_col_index(), StatusDelegate(self)
        )

        header = self._table_view.horizontalHeader()
        for i, (key, _) in enumerate(COLUMNS):
            if i < len(DEFAULT_COLUMN_WIDTHS) and i < len(BASE_COLUMNS):
                header.resizeSection(i, DEFAULT_COLUMN_WIDTHS[i])
            else:
                header.resizeSection(i, 140)
        header.setStretchLastSection(True)

    # ---- Health / Timeline ----

    def _get_selected_devices(self) -> list[dict]:
        selection = self._table_view.selectionModel().selectedRows()
        if not selection:
            return []
        devices = []
        for proxy_idx in selection:
            source_idx = self._proxy_model.mapToSource(proxy_idx)
            row_dict = self._table_model._rows[source_idx.row()]
            devices.append(row_dict)
        return devices

    def _get_visible_devices(self) -> list[dict]:
        devices = []
        for i in range(self._proxy_model.rowCount()):
            source_idx = self._proxy_model.mapToSource(
                self._proxy_model.index(i, 0)
            )
            devices.append(self._table_model._rows[source_idx.row()])
        return devices

    def _show_health_details(self):
        devices = self._get_selected_devices() or self._get_visible_devices()
        if not devices:
            QMessageBox.information(self, "No Devices", "No devices to check. Fetch devices first.")
            return
        dialog = HealthDialog(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            devices,
            self,
        )
        dialog.exec()

    def _show_device_timeline(self):
        devices = self._get_selected_devices() or self._get_visible_devices()
        if not devices:
            QMessageBox.information(self, "No Devices", "No devices to check. Fetch devices first.")
            return
        network_count = len({d.get("networkId", "") for d in devices if d.get("networkId")})
        if network_count > 20:
            reply = QMessageBox.question(
                self, "Large Query",
                f"This will fetch alert history from {network_count} networks, "
                "which may take a while and consume API quota. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        dialog = TimelineDialog(
            self._api_key_input.text().strip(),
            self._org_id_input.text().strip(),
            devices,
            self,
        )
        dialog.exec()

    def _on_table_double_clicked(self, index: QModelIndex):
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
            self, "Export to CSV", default_name,
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
                            row_out.append(format_timestamp(val))
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
