"""Recording desk: white desk, blue controls and ice-blue highlights."""
RECORD_STYLE = '''
QWidget {color:#294461; font-family:'Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC',sans-serif; font-size:13px;}
QWidget#workspace {background:#FFFFFF;}
QWidget#recordFields {background:#FFFFFF; border:1px solid #D9E5F3; border-radius:16px;}
QFrame#liveMonitor {background:#F0F5FC; border:1px solid #D3E2F3; border-radius:16px;}
QLabel#monitorTitle {color:#2276D6; font-size:12px; font-weight:600;}
QLabel#muted {color:#6B83A0;}
QLabel#recordStatus {color:#617D9F; padding:2px;}
QLabel#recordClock {font-family:'DejaVu Sans Mono','Consolas',monospace; font-size:34px; color:#2875D3;}
QPushButton {background:#EDF5FF; border:1px solid #D0E1F6; border-radius:9px; padding:9px 12px;}
QPushButton:hover {background:#DFEEFF; border-color:#6FB8EE;}
QPushButton:pressed {background:#CBE2FF;}
QPushButton:focus {border:2px solid #3E9FE8;}
QPushButton:disabled {background:#EFF3F9; color:#91A2B9; border-color:#DDE6F2;}
QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #56C8FF,stop:1 #3561EF); color:white; border:1px solid #94DFFF; border-radius:32px; padding:0;}
QPushButton#primary:hover {background:#4BAAFB; border:2px solid #B7EDFF;}
QPushButton#primary:disabled {background:#C2D7F2; border-color:#B6CDEB;}
QPushButton#stopRecord {background:#FFF1F4; border-color:#F1CDD6; border-radius:24px; padding:0;}
QPushButton#stopRecord:hover {background:#FFE0E9;}
QPushButton#stopRecord:disabled {background:#EDF3FA; border-color:#D4E0EF;}
QComboBox, QLineEdit {background:#F8FBFF; color:#294461; border:1px solid #D7E3F2; padding:10px; border-radius:8px; selection-background-color:#BFDFFF;}
QComboBox:focus, QLineEdit:focus {border-color:#3E9FE8;}
QComboBox:disabled, QLineEdit:disabled {color:#8DA0B8; border-color:#DAE4F1;}
QComboBox::drop-down {border:0; width:22px;}
QComboBox::down-arrow {image:none;}
QComboBox QAbstractItemView {background:#FFFFFF; color:#294461; selection-background-color:#D8EBFF;}
QTabBar::tab {padding:12px 24px; margin-right:8px; color:#748AA6; background:transparent; border:0;}
QTabBar::tab:selected {color:#217BDD; border-bottom:2px solid #368FEE;}
QToolTip {background:#244369; color:#F1F8FF; border:1px solid #6286B0; padding:6px;}
'''

LIBRARY_STYLE = '''
QTreeWidget {background:#FFFFFF; color:#294461; border:0; outline:0;}
QTreeWidget::item {height:56px; border-bottom:1px solid #E5EDF7;}
QTreeWidget::item:selected {background:#DAECFF; color:#244369;}
QHeaderView::section {background:#F0F5FC; color:#6D84A1; border:0; padding:10px;}
QToolButton {border:0; border-radius:6px; font-size:24px; background:transparent; color:#397ECA;}
QToolButton:hover {background:#E1EFFF;}
QToolButton::menu-indicator {image:none;}
QMenu {background:#FFFFFF; color:#294461; border:1px solid #D3E1F2; padding:5px;}
QMenu::item {padding:9px 24px;}
QMenu::item:selected {background:#DCEEFF;}
'''
