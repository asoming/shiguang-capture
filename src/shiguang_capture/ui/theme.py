"""Shared desktop palette: mist, paper, ink, teal, and amber."""
STYLE = """
QWidget { color:#24394B; font-family:'Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC',sans-serif; font-size:13px; }
QWidget#workspace, QDialog { background:#EDF3F7; }
QWidget#paper, QFrame#paper { background:#FFFFFF; border:1px solid #D5E1E9; border-radius:12px; }
QLabel#brand { color:#136A79; font-size:14px; font-weight:700; letter-spacing:2px; }
QLabel#title { color:#20374B; font-size:26px; font-weight:700; }
QLabel#muted { color:#657D8E; }
QLabel#status { color:#136A79; background:#E0F0EF; padding:7px 12px; border-radius:6px; }
QLabel#section { font-size:14px; font-weight:700; }
QPushButton { background:#FFFFFF; border:1px solid #CFDDE6; border-radius:7px; padding:8px 13px; min-height:18px; }
QPushButton:hover { background:#E5EFF4; border-color:#8CACBB; }
QPushButton:pressed, QPushButton:checked { background:#D6ECEC; border-color:#16808B; color:#126572; }
QPushButton:focus { border:2px solid #16808B; }
QPushButton#primary { background:#167D8D; color:white; border-color:#167D8D; font-weight:600; }
QPushButton#primary:hover { background:#116A7A; }
QPushButton:disabled { color:#93A5AF; background:#EEF2F5; border-color:#E0E7EC; }
QPlainTextEdit, QLineEdit, QComboBox { background:#FFFFFF; border:1px solid #CFDDE6; border-radius:7px; padding:8px; selection-background-color:#C3E4E7; selection-color:#20374B; }
QPlainTextEdit { padding:14px; font-size:14px; }
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus { border:1px solid #167D8D; }
QComboBox::drop-down { border:0; width:23px; }
QTabWidget::pane { background:white; border:1px solid #D5E1E9; border-radius:8px; }
QTabBar::tab { padding:12px 17px; margin-right:4px; color:#657D8E; background:transparent; border:0; }
QTabBar::tab:selected { color:#136A79; background:white; border-bottom:3px solid #167D8D; }
QCheckBox { spacing:9px; padding:5px; }
QCheckBox::indicator { width:17px; height:17px; }
QScrollArea { border:0; background:transparent; }
QSplitter::handle { background:#EDF3F7; }
QToolTip { background:#20374B; color:white; border:0; padding:6px; }
"""
