"""Custom item delegates for table views."""

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

from meraki_monitor.constants import STATUS_COLORS


class StatusDelegate(QStyledItemDelegate):
    """Paints a colored circle indicator next to the status text."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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
