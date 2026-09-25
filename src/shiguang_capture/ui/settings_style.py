"""White desktop settings with quiet dividers and blue interaction states."""

SETTINGS_STYLE = """
QDialog#settingsWindow { background:#FFFFFF; }
QWidget#settingsHeader { background:#FFFFFF; border-bottom:1px solid #E9ECF0; }
QLabel#settingsBrand { color:#202630; font-size:18px; font-weight:700; }
QLabel#settingsCaption { color:#98A2B1; font-size:11px; }
QPushButton#settingsQuick { color:#607089; border:0; background:transparent; padding:8px 13px; }
QPushButton#settingsQuick:hover { color:#2875F6; background:#F1F6FF; }
QWidget#settingsSidebar { background:#FFFFFF; border-right:1px solid #E9ECF0; }
QPushButton#settingsCategory { text-align:left; color:#7D899A; background:transparent; border:0; border-left:2px solid transparent; border-radius:6px; padding:10px 14px; }
QPushButton#settingsCategory:hover { background:#F6F8FC; color:#53657F; }
QPushButton#settingsCategory:checked { background:#EDF4FF; color:#2875F6; border-left:2px solid #2875F6; font-weight:600; }
QPushButton#settingsCategory:focus { border:1px solid #A7C7FD; border-left:2px solid #2875F6; }
QScrollArea#settingsPage, QWidget#settingsPageContent { background:#FFFFFF; border:0; }
QLabel#settingsPageTitle { font-size:17px; font-weight:600; color:#202630; }
QLabel#settingsPageDescription, QLabel#settingsNote { font-size:11px; color:#909BAC; }
QWidget#settingsRow { border-bottom:1px solid #EDF0F5; }
QLabel#settingsLabel { font-size:12px; color:#526078; border:0; }
QLabel#settingsValue { font-size:12px; color:#6B7D96; }
QLabel#settingsReady { font-size:11px; color:#48856A; }
QLabel#settingsWarning { font-size:11px; color:#A07843; }
QLabel#settingsError { font-size:11px; color:#CE5668; }
QPushButton#settingsLink { border:0; color:#6381A9; background:transparent; padding:7px 0; text-align:left; font-size:11px; }
QPushButton#settingsLink:hover { color:#2875F6; }
QDialog#settingsWindow QLineEdit, QDialog#settingsWindow QComboBox { font-size:12px; border:1px solid #E0E6EF; background:#FFFFFF; padding:7px 10px; border-radius:6px; selection-background-color:#DCEBFF; selection-color:#263952; }
QDialog#settingsWindow QLineEdit:focus, QDialog#settingsWindow QComboBox:focus { border:1px solid #2875F6; }
QDialog#settingsWindow QLineEdit#settingsHotkey { color:#687D99; }
QDialog#settingsWindow QComboBox:disabled { color:#7C8DA5; background:#F8FAFC; }
QDialog#settingsWindow QComboBox QAbstractItemView { border:1px solid #DFE6EF; background:white; color:#526078; selection-background-color:#EDF4FF; selection-color:#2875F6; padding:4px; }
QWidget#settingsFooter { background:#FFFFFF; border-top:1px solid #E9ECF0; }
QDialog#settingsWindow QPushButton#primary { background:#2875F6; color:white; border:1px solid #2875F6; border-radius:7px; padding:8px 18px; }
QDialog#settingsWindow QPushButton#primary:hover { background:#1A68E9; border-color:#1A68E9; }
QDialog#settingsWindow QSlider::groove:horizontal { height:4px; background:#E7EDF5; border-radius:2px; }
QDialog#settingsWindow QSlider::sub-page:horizontal { background:#2875F6; border-radius:2px; }
QDialog#settingsWindow QSlider::handle:horizontal { width:12px; margin:-4px 0; background:white; border:1px solid #80ACF4; border-radius:6px; }
QDialog#settingsWindow QScrollBar:vertical { background:transparent; width:7px; margin:4px 0; }
QDialog#settingsWindow QScrollBar::handle:vertical { background:#DCE4EF; border-radius:3px; min-height:28px; }
QDialog#settingsWindow QScrollBar::add-line:vertical, QDialog#settingsWindow QScrollBar::sub-line:vertical { height:0; }
QDialog#settingsWindow QScrollBar::add-page:vertical, QDialog#settingsWindow QScrollBar::sub-page:vertical { background:transparent; }
"""
