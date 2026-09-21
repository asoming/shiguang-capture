"""ui/tray.py — 系统托盘（常驻入口，截图工具的标准形态）。"""
from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icon import make_icon
from ..shortcuts import shortcut_label


class TrayIcon(QObject):
    action_open = Signal()
    action_workspace = Signal()
    action_capture = Signal()
    action_record = Signal()
    action_scroll = Signal()
    action_pick = Signal()
    action_ocr = Signal()
    action_hide_pins = Signal()
    action_restore_pins = Signal()
    action_settings = Signal()
    action_check_update = Signal()
    action_quit = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(make_icon(), self.parent())
        self._tray.setToolTip("拾光 Capture")
        menu = QMenu()
        menu.addAction("打开拾光", self.action_workspace.emit)
        menu.addAction("打开图片…", self.action_open.emit)
        menu.addSeparator()
        self._hotkey_actions = {}
        for action, label, signal in [
            ('capture_region', '区域截图', self.action_capture),
            ('record_toggle', '录屏', self.action_record),
            ('capture_scroll', '滚动长截图', self.action_scroll),
            ('color_picker', '取色器', self.action_pick),
            ('ocr_recognize', 'OCR 识别', self.action_ocr),
            ('hide_all_pins', '隐藏 / 恢复全部贴图', self.action_hide_pins),
            ('restore_all_pins', '找回全部贴图 / 退出穿透', self.action_restore_pins),
        ]:
            self._hotkey_actions[action] = (menu.addAction(label, signal.emit), label)
        menu.addSeparator()
        menu.addAction("⚙️ 设置…", self.action_settings.emit)
        menu.addAction("🔄 检查更新", self.action_check_update.emit)
        menu.addSeparator()
        menu.addAction("退出", self.action_quit.emit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        # 双击托盘图标直接打开设置。
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.action_workspace.emit()

    def update_hotkeys(self, config) -> None:
        for name, (action, label) in self._hotkey_actions.items():
            value = getattr(config, name)
            action.setText(f'{label} ({shortcut_label(value)})' if value else label)
        self._tray.setToolTip(f'拾光 Capture — 截图 {shortcut_label(config.capture_region)} / 录屏 {shortcut_label(config.record_toggle)}')

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2400)
