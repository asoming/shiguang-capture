"""Shared white surfaces, neutral dividers, and the capture blue accent."""

STYLE = """
QWidget { color:#202630; font-family:'Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC',sans-serif; font-size:13px; }
QWidget#workspace, QDialog { background:#FFFFFF; }
QWidget#paper, QFrame#paper { background:#FFFFFF; border:1px solid #E1E6ED; border-radius:10px; }
QLabel#brand { color:#2875F6; font-size:14px; font-weight:700; }
QLabel#title { color:#202630; font-size:22px; font-weight:600; }
QLabel#muted { color:#788596; }
QLabel#status { color:#39669B; background:#EDF4FF; padding:7px 12px; border-radius:6px; }
QLabel#section { font-size:14px; font-weight:600; }
QPushButton { background:#FFFFFF; border:1px solid #E1E6ED; border-radius:7px; padding:8px 13px; min-height:18px; }
QPushButton:hover { background:#F4F8FE; border-color:#BCD2F2; }
QPushButton:pressed, QPushButton:checked { background:#EDF4FF; border-color:#8BB8FF; color:#2875F6; }
QPushButton:focus { border:1px solid #2875F6; }
QPushButton#primary { background:#2875F6; color:white; border-color:#2875F6; font-weight:600; }
QPushButton#primary:hover { background:#1765E8; }
QPushButton:disabled { color:#A1ADBC; background:#F5F7FA; border-color:#E9EDF3; }
QToolButton { color:#66778D; background:transparent; border:1px solid transparent; border-radius:6px; padding:6px; }
QToolButton:hover, QToolButton:checked { background:#EDF4FF; color:#2875F6; }
QToolButton:focus { border-color:#2875F6; }
QPlainTextEdit, QLineEdit, QComboBox { background:#FFFFFF; border:1px solid #E1E6ED; border-radius:7px; padding:8px; selection-background-color:#DCEBFF; selection-color:#202630; }
QPlainTextEdit { padding:14px; font-size:14px; }
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus { border:1px solid #8BB8FF; }
QComboBox::drop-down { border:0; width:23px; }
QComboBox QAbstractItemView { background:white; color:#202630; selection-background-color:#EDF4FF; selection-color:#2875F6; }
QTabWidget::pane { background:white; border:1px solid #E1E6ED; border-radius:8px; }
QTabBar::tab { padding:12px 17px; margin-right:4px; color:#788596; background:transparent; border:0; }
QTabBar::tab:selected { color:#2875F6; background:white; border-bottom:3px solid #2875F6; }
QCheckBox { spacing:9px; padding:5px; }
QCheckBox::indicator { width:17px; height:17px; }
QScrollArea { border:0; background:transparent; }
QSplitter::handle { background:#F4F6F9; }
QTableWidget { background:white; alternate-background-color:#F8FAFD; gridline-color:#E9ECF0; border:1px solid #E1E6ED; selection-background-color:#EDF4FF; selection-color:#202630; }
QHeaderView::section { background:#F7F9FC; color:#788596; border:0; border-bottom:1px solid #E9ECF0; padding:8px; }
QMenu { color:#202630; background:#FFFFFF; border:1px solid #DFE6EF; padding:5px; }
QMenu::item { padding:8px 24px 8px 12px; border-radius:4px; }
QMenu::item:selected { background:#EDF4FF; color:#2875F6; }
QMenu::item:disabled { color:#A1ADBC; }
QMenu::separator { height:1px; background:#E9ECF0; margin:4px 8px; }
QToolTip { background:#243249; color:white; border:0; padding:6px; }
"""
