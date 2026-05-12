"""Qt table models and proxy models for the device table."""

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor, QFont

from meraki_monitor.constants import COLUMNS
from meraki_monitor.utils import format_timestamp


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
                return format_timestamp(raw)
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
