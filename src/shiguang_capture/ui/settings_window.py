"""Settings sidebar, real application preferences, and immediate tool entry points."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QPushButton, QScrollArea,
    QSlider, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __app_name__, __version__
from ..config import AppConfig, HotkeyConfig
from ..shortcuts import normalize_shortcut
from ..updater import RELEASES_PAGE
from .hotkey_edit import HotkeyEdit
from .icon import make_icon
from .settings_style import SETTINGS_STYLE
from .theme import STYLE
from .tool_icons import tool_icon

_HOTKEY_FIELDS = [
    ("capture_region", "区域截图"),
    ("capture_fullscreen", "全屏截图"),
    ("capture_scroll", "滚动长截图"),
    ("pin_last", "贴图（剪贴板图像）"),
    ("color_picker", "取色器"),
    ("restore_all_pins", "找回全部贴图 / 退出穿透"),
    ("hide_all_pins", "隐藏 / 恢复全部贴图"),
    ("ocr_recognize", "OCR 识别（剪贴板 / 上次截图）"),
    ("record_toggle", "录屏 / 暂停 / 继续"),
    ("record_stop", "停止录屏并保存"),
]


class SettingsComboBox(QComboBox):
    """Keep the disclosure arrow visible with native and offscreen Qt styles."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isEnabled():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#899BB5'), 1.5))
        x, y = self.width() - 15, self.height() / 2
        painter.drawLine(QPointF(x - 3, y - 1), QPointF(x, y + 2))
        painter.drawLine(QPointF(x, y + 2), QPointF(x + 3, y - 1))


class SettingsToggle(QCheckBox):
    """A compact switch retaining QCheckBox keyboard and accessibility behavior."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setFixedSize(38, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, position) -> bool:
        return self.rect().contains(position)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = '#2875F6' if self.isChecked() else '#D8E0EB'
        if not self.isEnabled():
            color = '#E7ECF3'
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(2, 3, 34, 18), 9, 9)
        painter.setBrush(QColor('#FFFFFF'))
        painter.drawEllipse(QRectF(21 if self.isChecked() else 4, 5, 14, 14))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#99BFFA'), 1))
            painter.drawRoundedRect(QRectF(0.5, 1.5, 37, 21), 10, 10)


class SettingsWindow(QDialog):
    settings_saved = Signal(object)
    check_update_requested = Signal()
    capture_requested = Signal()
    record_requested = Signal()
    recognize_requested = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = deepcopy(config)
        self.setObjectName('settingsWindow')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE + SETTINGS_STYLE)
        self.setWindowTitle(f'{__app_name__} · 设置')
        self.setWindowIcon(make_icon())
        self.setMinimumSize(780, 540)
        self.resize(940, 660)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        body = QHBoxLayout()
        body.setSpacing(0)
        self.pages = QStackedWidget()
        sidebar = QWidget(objectName='settingsSidebar')
        sidebar.setFixedWidth(176)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(14, 24, 14, 20)
        navigation.setSpacing(5)
        self._nav_group = QButtonGroup(self)
        self._nav_buttons: list[QPushButton] = []
        for index, (label, builder) in enumerate((
            ('常规', self._build_general),
            ('快捷键', self._build_hotkeys),
            ('贴图与取色', self._build_pin_picker),
            ('识别与翻译', self._build_ocr),
            ('关于与更新', self._build_about),
        )):
            button = QPushButton(label, objectName='settingsCategory')
            button.setCheckable(True)
            button.setMinimumHeight(40)
            self._nav_group.addButton(button, index)
            self._nav_buttons.append(button)
            navigation.addWidget(button)
            self.pages.addWidget(builder())
        self._nav_group.idClicked.connect(self._switch_to_tab)
        navigation.addStretch()
        version = QLabel(f'v{__version__}', objectName='settingsCaption')
        version.setContentsMargins(16, 0, 0, 0)
        navigation.addWidget(version)
        body.addWidget(sidebar)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_footer())
        self._switch_to_tab(0)

    def _build_header(self) -> QWidget:
        header = QWidget(objectName='settingsHeader')
        header.setFixedHeight(68)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 0, 24, 0)
        layout.setSpacing(12)
        layout.addWidget(QLabel('拾光', objectName='settingsBrand'))
        layout.addWidget(QLabel('设置', objectName='settingsCaption'))
        layout.addStretch()
        for label, icon, signal, primary in (
            ('截图', 'rect', self.capture_requested, True),
            ('录屏', 'play', self.record_requested, False),
            ('识别', 'ocr', self.recognize_requested, False),
        ):
            button = QPushButton(label, objectName='primary' if primary else 'settingsQuick')
            button.setIcon(tool_icon(icon, '#FFFFFF' if primary else '#6883A8'))
            button.setIconSize(QSize(17, 17))
            button.setAccessibleName('开始区域截图' if primary else '打开录屏' if icon == 'play' else '打开识别工作台')
            button.setAutoDefault(False)
            button.clicked.connect(signal.emit)
            layout.addWidget(button)
        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget(objectName='settingsFooter')
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(26, 15, 24, 15)
        layout.setSpacing(12)
        self.status = QLabel('', objectName='settingsError')
        self.status.setWordWrap(True)
        layout.addWidget(self.status, 1)
        self.cancel_button = QPushButton('取消')
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton('保存设置', objectName='primary')
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.save_button)
        return footer

    def _page(self, title: str, description: str = '') -> tuple[QScrollArea, QVBoxLayout]:
        content = QWidget(objectName='settingsPageContent')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 27, 32, 24)
        layout.setSpacing(0)
        layout.addWidget(QLabel(title, objectName='settingsPageTitle'))
        if description:
            hint = QLabel(description, objectName='settingsPageDescription')
            hint.setWordWrap(True)
            layout.addSpacing(7)
            layout.addWidget(hint)
        layout.addSpacing(23)
        scroll = QScrollArea(objectName='settingsPage')
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll, layout

    def _row(self, layout: QVBoxLayout, label: str, control: QWidget | QLayout) -> None:
        row = QWidget(objectName='settingsRow')
        row.setMinimumHeight(61)
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 11, 0, 11)
        line.setSpacing(18)
        caption = QLabel(label, objectName='settingsLabel')
        caption.setWordWrap(True)
        line.addWidget(caption, 1)
        if isinstance(control, QLayout):
            wrapper = QWidget()
            wrapper.setLayout(control)
            control.setContentsMargins(0, 0, 0, 0)
            control = wrapper
        line.addWidget(control)
        if isinstance(control, (QLineEdit, QComboBox)):
            control.setMinimumWidth(190)
            control.setMaximumWidth(265)
            caption.setBuddy(control)
        layout.addWidget(row)

    def _note(self, layout: QVBoxLayout, text: str) -> None:
        note = QLabel(text, objectName='settingsNote')
        note.setWordWrap(True)
        layout.addSpacing(18)
        layout.addWidget(note)

    def _build_general(self) -> QWidget:
        page, layout = self._page('常规')
        directory = QHBoxLayout()
        directory.setSpacing(8)
        self.save_dir_edit = QLineEdit(self._config.save_dir)
        self.save_dir_edit.setAccessibleName('截图保存目录')
        self.save_dir_edit.setMinimumWidth(180)
        self.save_dir_edit.setMaximumWidth(245)
        browse = QPushButton('浏览…')
        browse.setAutoDefault(False)
        browse.clicked.connect(self._pick_dir)
        directory.addWidget(self.save_dir_edit, 1)
        directory.addWidget(browse)
        self._row(layout, '截图保存目录', directory)
        self.format_combo = SettingsComboBox()
        self.format_combo.addItems(['png', 'jpg'])
        self.format_combo.setCurrentText(self._config.image_format)
        self.format_combo.setAccessibleName('图片格式')
        self._row(layout, '图片格式', self.format_combo)
        self.clipboard_check = QCheckBox(self)
        self.clipboard_check.setChecked(self._config.copy_to_clipboard)
        self.clipboard_check.hide()
        self.sound_check = QCheckBox(self)
        self.sound_check.setChecked(self._config.play_shutter_sound)
        self.sound_check.hide()
        self.autostart_check = SettingsToggle('开机自动启动')
        self.autostart_check.setChecked(self._config.launch_at_login)
        self._row(layout, '开机自动启动', self.autostart_check)
        self._note(layout, '截图默认只复制，点击保存才会写入文件。')
        layout.addStretch()
        return page

    def _pick_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, '选择截图保存目录', self.save_dir_edit.text())
        if directory:
            self.save_dir_edit.setText(directory)

    def _build_hotkeys(self) -> QWidget:
        page, layout = self._page('快捷键', '点击后按键。Backspace 清除，Esc 取消；保存后立即生效。')
        self._hotkey_edits: dict[str, HotkeyEdit] = {}
        for attr, label in _HOTKEY_FIELDS:
            edit = HotkeyEdit(getattr(self._config.hotkeys, attr))
            edit.setObjectName('settingsHotkey')
            edit.setAccessibleName(label + '快捷键')
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hotkey_edits[attr] = edit
            self._row(layout, label, edit)
        self.hotkey_warn = QLabel('', objectName='settingsError')
        self.hotkey_warn.setWordWrap(True)
        layout.addSpacing(14)
        layout.addWidget(self.hotkey_warn)
        reset = QPushButton('恢复默认快捷键', objectName='settingsLink')
        reset.setAutoDefault(False)
        reset.clicked.connect(self._reset_hotkeys)
        layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return page

    def _reset_hotkeys(self) -> None:
        defaults = HotkeyConfig()
        for attr, edit in self._hotkey_edits.items():
            edit.setText(getattr(defaults, attr))
        self.hotkey_warn.clear()
        self.status.clear()

    def _build_pin_picker(self) -> QWidget:
        page, layout = self._page('贴图与取色')
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setAccessibleName('贴图默认透明度')
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setFixedWidth(180)
        self.opacity_slider.setValue(round(self._config.pin_default_opacity * 100))
        self.opacity_label = QLabel(f'{self.opacity_slider.value()}%', objectName='settingsValue')
        self.opacity_label.setMinimumWidth(37)
        self.opacity_slider.valueChanged.connect(lambda value: self.opacity_label.setText(f'{value}%'))
        opacity = QHBoxLayout()
        opacity.setSpacing(12)
        opacity.addWidget(self.opacity_slider)
        opacity.addWidget(self.opacity_label)
        self._row(layout, '贴图默认透明度', opacity)
        self.picker_combo = SettingsComboBox()
        self.picker_combo.addItems(['hex', 'rgb', 'hsv', 'hsl', 'rgba'])
        self.picker_combo.setCurrentText(self._config.picker_format)
        self.picker_combo.setAccessibleName('取色复制格式')
        self._row(layout, '取色复制格式', self.picker_combo)
        self._note(layout, '贴图：滚轮调节透明度，Ctrl + 滚轮缩放。')
        layout.addStretch()
        return page

    def _build_ocr(self) -> QWidget:
        page, layout = self._page('识别与翻译')
        self.ocr_combo = SettingsComboBox()
        self.ocr_combo.addItem('本地 OCR', 'local')
        self.ocr_combo.setCurrentIndex(0)
        self.ocr_combo.setEnabled(False)
        self.ocr_combo.setAccessibleName('识别引擎')
        self._row(layout, '识别引擎', self.ocr_combo)
        self.lang_combo = SettingsComboBox()
        for label, value in [('自动（中英互译）', 'auto'), ('中文', 'zh'), ('英文', 'en')]:
            self.lang_combo.addItem(label, value)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(self._config.target_lang)))
        self.lang_combo.setAccessibleName('翻译目标语言')
        self._row(layout, '翻译目标语言', self.lang_combo)
        self.cloud_translate_check = QCheckBox(self)
        self.cloud_translate_check.setChecked(self._config.allow_cloud_translate)
        self.cloud_translate_check.hide()
        self.translate_status = QLabel('', objectName='settingsValue')
        self.translate_status.setWordWrap(True)
        self.translate_status.setMinimumWidth(230)
        self.translate_status.setMaximumWidth(275)
        self.translate_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._row(layout, '离线翻译模型', self.translate_status)
        refresh = QPushButton('检测离线翻译能力', objectName='settingsLink')
        refresh.setAutoDefault(False)
        refresh.clicked.connect(self._refresh_translate_status)
        layout.addSpacing(14)
        layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)
        self._note(layout, '识别与中英翻译在本机完成，不上传图像或文本。')
        layout.addStretch()
        self._refresh_translate_status()
        return page

    def _refresh_translate_status(self) -> None:
        try:
            from ..offline_translation import available
            from ..translate import argos_available
            if available():
                message = '离线中英翻译已就绪'
            elif argos_available():
                message = '离线神经翻译已就绪'
            else:
                message = '未检测到离线模型，当前仅支持术语词典'
        except Exception:  # Optional native backends can fail during import.
            message = '无法检测离线模型，请重试'
        self.translate_status.setText(message)

    def _build_about(self) -> QWidget:
        page, layout = self._page(__app_name__)
        self._row(layout, '当前版本', QLabel(f'v{__version__}', objectName='settingsValue'))
        self._row(layout, '许可证', QLabel('MIT', objectName='settingsValue'))
        project = QLabel('<a style="color:#2875F6;text-decoration:none" href="https://github.com/asoming/shiguang-capture">GitHub ↗</a>')
        project.setOpenExternalLinks(True)
        project.setAccessibleName('GitHub 项目主页')
        self._row(layout, '项目主页', project)
        releases = QLabel(f'<a style="color:#2875F6;text-decoration:none" href="{RELEASES_PAGE}">版本下载 ↗</a>')
        releases.setOpenExternalLinks(True)
        releases.setAccessibleName('GitHub 版本下载')
        self._row(layout, '下载安装包', releases)
        self.update_btn = QPushButton('检查更新', objectName='settingsLink')
        self.update_btn.setAutoDefault(False)
        self.update_btn.clicked.connect(self._on_check_update)
        self.update_status = QLabel('尚未检查', objectName='settingsValue')
        self.update_status.setWordWrap(True)
        self.update_status.setMaximumWidth(225)
        updates = QHBoxLayout()
        updates.setSpacing(18)
        updates.addWidget(self.update_btn)
        updates.addWidget(self.update_status)
        self._row(layout, '新版本', updates)
        layout.addStretch()
        return page

    def _on_check_update(self) -> None:
        self.update_btn.setEnabled(False)
        self.update_status.setText('正在检查…')
        self.check_update_requested.emit()

    def set_update_result(self, text: str) -> None:
        self.update_btn.setEnabled(True)
        self.update_status.setText(text)

    def _on_save(self) -> None:
        cfg = deepcopy(self._config)
        cfg.save_dir = self.save_dir_edit.text().strip() or cfg.save_dir
        cfg.image_format = self.format_combo.currentText()
        cfg.copy_to_clipboard = self.clipboard_check.isChecked()
        cfg.play_shutter_sound = self.sound_check.isChecked()
        cfg.launch_at_login = self.autostart_check.isChecked()
        cfg.pin_default_opacity = self.opacity_slider.value() / 100
        cfg.picker_format = self.picker_combo.currentText()
        cfg.ocr_engine = self.ocr_combo.currentData()
        cfg.target_lang = self.lang_combo.currentData()
        cfg.allow_cloud_translate = False
        for attr, edit in self._hotkey_edits.items():
            try:
                setattr(cfg.hotkeys, attr, normalize_shortcut(edit.text()))
            except ValueError:
                self.hotkey_warn.setText(f'{dict(_HOTKEY_FIELDS)[attr]}：请重新按下快捷键。')
                self.status.setText('设置未保存，原快捷键仍可使用。')
                self._switch_to_tab(1)
                edit.setFocus()
                self.pages.currentWidget().ensureWidgetVisible(edit)
                return
        conflicts = cfg.hotkeys.conflicts()
        if conflicts:
            labels = dict(_HOTKEY_FIELDS)
            names = '、'.join(f'{labels[a]} ↔ {labels[b]}' for a, b in conflicts)
            self.hotkey_warn.setText(f'热键冲突：{names}。请修改后重新保存。')
            self.status.setText('设置未保存，原快捷键仍可使用。')
            self._switch_to_tab(1)
            self.pages.currentWidget().ensureWidgetVisible(self.hotkey_warn)
            return
        self.hotkey_warn.clear()
        self.status.clear()
        self.settings_saved.emit(cfg)

    def _switch_to_tab(self, index: int) -> None:
        """Keep the controller/test-facing page switch stable after the sidebar change."""
        if 0 <= index < self.pages.count():
            self.pages.setCurrentIndex(index)
            self._nav_buttons[index].setChecked(True)
