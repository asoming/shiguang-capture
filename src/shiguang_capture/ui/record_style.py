"""Quiet white recording desk with a single blue control hierarchy."""
RECORD_STYLE = '''
QWidget {color:#273446; font-family:'Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC',sans-serif; font-size:13px;}
QWidget#workspace, QWidget#recordFields {background:#FFFFFF;}
QWidget#scopeSegments {background:#F0F3F7; border:1px solid #E9EDF2; border-radius:8px;}
QWidget#scopeSegments QPushButton {background:transparent; color:#718093; border:1px solid transparent; border-radius:5px; padding:4px 10px;}
QWidget#scopeSegments QPushButton:checked {background:#FFFFFF; color:#2875F6; border-color:#E0E8F2; font-weight:600;}
QWidget#scopeSegments QPushButton:hover {color:#2875F6; background:#F8FAFD;}
QLabel#fieldLabel {color:#788597; font-size:12px; font-weight:500;}
QLabel#monitorTitle {color:#2875F6; font-size:12px;}
QLabel#muted {color:#8491A2; font-size:11px;}
QFrame#liveMonitor {background:#F3F6FA; border:1px solid #E5EAF1; border-radius:10px;}
QLabel#livePicture {background:transparent; color:#8291A7; border:0;}
QFrame#recordFooter {border:0; border-top:1px solid #E9EDF2;}
QLabel#recordStatus {color:#6E7D91; font-size:12px;}
QLabel#recordClock {font-family:'DejaVu Sans Mono','Consolas',monospace; font-size:26px; color:#34445B;}
QPushButton {background:#FFFFFF; border:1px solid #E0E6EE; border-radius:7px; padding:8px 11px;}
QPushButton:hover {background:#F5F8FD; border-color:#B4CCF0;}
QPushButton:pressed {background:#EAF2FF;}
QPushButton:focus {border:1px solid #2875F6;}
QPushButton:disabled {background:#F7F9FC; color:#A3ADBB; border-color:#E9EDF3;}
QPushButton#primary {background:#2875F6; color:#FFFFFF; border:1px solid #2875F6; border-radius:8px; padding:0; font-weight:600;}
QPushButton#primary:hover {background:#1766E8; border-color:#1766E8;}
QPushButton#primary:disabled {background:#ADC8F4; border-color:#ADC8F4;}
QPushButton#stopRecord {background:#FFFFFF; border-color:#E5EAF0; border-radius:8px; padding:0;}
QPushButton#stopRecord:hover {background:#FFF3F5; border-color:#E9BFC7;}
QPushButton#stopRecord:disabled {background:#F8FAFC; border-color:#EFF2F6;}
QPushButton#quiet {color:#7B8BA0; font-size:11px; padding:7px 10px;}
QComboBox, QLineEdit {background:#FFFFFF; color:#3A4B62; border:1px solid #E0E6EE; padding:8px 10px; border-radius:7px; selection-background-color:#DBE9FF;}
QComboBox {padding-right:24px;}
QComboBox:focus, QLineEdit:focus {border-color:#2875F6;}
QComboBox:disabled, QLineEdit:disabled {color:#98A4B5; background:#F8FAFC; border-color:#E8EDF3;}
QComboBox::drop-down {border:0; width:22px;}
QComboBox::down-arrow {image:none;}
QComboBox QAbstractItemView {background:#FFFFFF; color:#34445B; selection-background-color:#EAF2FF;}
QToolButton {background:transparent; border:0; color:#7B8BA0; padding:4px 0; font-size:11px;}
QToolButton:hover {color:#2875F6;}
QTabBar::tab {padding:13px 4px; margin-right:28px; color:#8590A1; background:transparent; border:0;}
QTabBar::tab:selected {color:#2875F6; border-bottom:3px solid #2875F6; font-weight:600;}
QToolTip {background:#293B55; color:#FFFFFF; border:0; padding:6px;}
'''

LIBRARY_STYLE = '''
QWidget {font-family:'Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC',sans-serif; font-size:12px; color:#526178;}
QLineEdit {background:#FFFFFF; border:1px solid #E1E7EF; border-radius:7px; padding:9px 12px; selection-background-color:#DBE9FF;}
QLineEdit:focus {border-color:#2875F6;}
QPushButton {background:#FFFFFF; border:1px solid #E1E7EF; border-radius:7px; padding:8px 12px; color:#75849A;}
QPushButton:hover {background:#F5F8FD; border-color:#ADC8F4; color:#2875F6;}
QPushButton:focus {border-color:#2875F6;}
QTreeWidget {background:#FFFFFF; alternate-background-color:#FFFFFF; color:#42536C; border:0; outline:0;}
QTreeWidget::item {height:78px; border-bottom:1px solid #EDF0F5; padding:0 8px;}
QTreeWidget::item:selected {background:#EDF4FF; color:#243C5C;}
QTreeWidget::item:hover {background:#F7FAFE;}
QHeaderView::section {background:#F7F9FC; color:#8A98AB; border:0; padding:11px 12px; font-size:11px;}
QToolButton {border:0; border-radius:6px; font-size:23px; background:transparent; color:#8A98AB;}
QToolButton:hover {background:#EAF2FF; color:#2875F6;}
QToolButton::menu-indicator {image:none;}
QMenu {background:#FFFFFF; color:#42536C; border:1px solid #E0E7F0; padding:5px;}
QMenu::item {padding:9px 24px; border-radius:4px;}
QMenu::item:selected {background:#EAF2FF;}
QLabel#muted {color:#91A0B3; font-size:11px;}
'''
