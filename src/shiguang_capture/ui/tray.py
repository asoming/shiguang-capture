"""ui/tray.py — 系统托盘（常驻入口，截图工具的标准形态）。"""
from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icon import make_icon


class TrayIcon(QObject):
    action_open = Signal()
    action_workspace = Signal()
    action_capture = Signal()
    action_record = Signal()
    action_scroll = Signal()
    action_pick = Signal()
    action_ocr = Signal()
    action_hide_pins = Signal()
    action_settings = Signal()
    action_check_update = Signal()
    action_quit = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(make_icon(), self.parent())
        self._tray.setToolTip("拾光 Capture — F1 截图 / F2 取色 / F3 贴图")
        menu = QMenu()
        menu.addAction("打开图片工作台", self.action_workspace.emit)
        menu.addAction("打开图片…", self.action_open.emit)
        menu.addSeparator()
        menu.addAction("✂️ 区域截图 (F1)", self.action_capture.emit)
        menu.addAction("录屏 (F6)", self.action_record.emit)
        menu.addAction("📜 滚动长截图 (Ctrl+F1)", self.action_scroll.emit)
        menu.addAction("🎨 取色器 (F2)", self.action_pick.emit)
        menu.addAction("🔍 OCR 识别 (F4)", self.action_ocr.emit)
        menu.addAction("🙈 隐藏全部贴图 (Shift+F3)", self.action_hide_pins.emit)
        menu.addSeparator()
        menu.addAction("⚙️ 设置…", self.action_settings.emit)
        menu.addAction("🔄 检查更新", self.action_check_update.emit)
        menu.addSeparator()
        menu.addAction("退出", self.action_quit.emit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        # 双击托盘图标打开设置（单击留给截图）
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.action_workspace.emit()

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2400)
