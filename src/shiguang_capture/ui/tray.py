"""ui/tray.py — 系统托盘（常驻入口，截图工具的标准形态）。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_icon(size: int = 64) -> QIcon:
    """程序内绘制的简易图标：紫蓝渐变圆角方块 + 剪刀符号。"""
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(95, 128, 245))
    p.setPen(Qt.GlobalColor.transparent if hasattr(Qt, "GlobalColor") else QColor(0, 0, 0, 0))
    p.drawRoundedRect(2, 2, size - 4, size - 4, size // 4, size // 4)
    p.setPen(QColor(255, 255, 255))
    font = p.font()
    font.setPixelSize(int(size * 0.5))
    font.setBold(True)
    p.setFont(font)
    p.drawText(pix.rect(), 0x0084, "S")  # AlignCenter
    p.end()
    return QIcon(pix)


class TrayIcon(QObject):
    action_capture = Signal()
    action_scroll = Signal()
    action_pick = Signal()
    action_hide_pins = Signal()
    action_quit = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(make_icon(), self.parent())
        self._tray.setToolTip("拾光 Capture — F1 截图 / F2 取色 / F3 贴图")
        menu = QMenu()
        menu.addAction("✂️ 区域截图 (F1)", self.action_capture.emit)
        menu.addAction("📜 滚动长截图 (Ctrl+F1)", self.action_scroll.emit)
        menu.addAction("🎨 取色器 (F2)", self.action_pick.emit)
        menu.addSeparator()
        menu.addAction("🙈 隐藏全部贴图 (Shift+F3)", self.action_hide_pins.emit)
        menu.addSeparator()
        menu.addAction("退出", self.action_quit.emit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.action_capture.emit()

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2400)
