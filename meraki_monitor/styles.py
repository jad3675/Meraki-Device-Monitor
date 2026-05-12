"""Dark and light Qt stylesheets."""

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
