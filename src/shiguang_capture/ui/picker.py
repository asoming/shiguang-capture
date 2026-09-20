"""ui/picker.py — 全屏取色器（FR：像素级放大镜 + 格式复制）。

单击复制当前像素色值（格式由配置决定：hex / rgb / hsv），Esc 退出。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..colors import format_color
from ..capture.grabber import capture_frames
from ..geometry import Rect, union


class ColorPickerOverlay(QWidget):
    color_picked = Signal(str)   # 已按格式渲染好的色值字符串
    cancelled = Signal()

    def __init__(self, fmt: str = "hex") -> None:
        super().__init__()
        self._fmt = fmt
        self._frames = capture_frames()
        rects = []
        for s in QGuiApplication.screens():
            g = s.geometry()
            rects.append(Rect(g.x(), g.y(), g.width(), g.height()))
        bounds = union(rects)
        self.setGeometry(bounds.x, bounds.y, bounds.width, bounds.height)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._pos = None
        self._label = ""

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        self._pos = e.globalPosition().toPoint()
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._pos is not None:
            frame = next((f for f in self._frames if
                          f.bounds.x <= self._pos.x() < f.bounds.right and
                          f.bounds.y <= self._pos.y() < f.bounds.bottom), None)
            if frame is None:
                return
            x = min(frame.image.width()-1, int((self._pos.x()-frame.bounds.x)*frame.dpr))
            y = min(frame.image.height()-1, int((self._pos.y()-frame.bounds.y)*frame.dpr))
            c = frame.image.pixelColor(x, y)
            value = format_color(c.red(), c.green(), c.blue(), self._fmt)
            self.hide()
            self.color_picked.emit(value)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()

    def paintEvent(self, _e) -> None:  # noqa: N802
        if self._pos is None:
            return
        p = QPainter(self)
        origin = self.geometry().topLeft()
        x, y = self._pos.x() - origin.x(), self._pos.y() - origin.y()
        p.setPen(QPen(QColor(125, 155, 255), 1))
        p.drawLine(0, y, self.width(), y)
        p.drawLine(x, 0, x, self.height())
        p.setPen(QColor(233, 237, 243))
        p.drawText(x + 12, y - 10, f"({self._pos.x()}, {self._pos.y()})  单击取色 / Esc 退出")
        p.end()
