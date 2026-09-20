"""Frozen native-pixel color sampling; output assumes SDR/sRGB."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from ..colors import format_color
from ..capture.grabber import capture_frames
from ..geometry import union


class ColorPickerOverlay(QWidget):
    color_picked = Signal(str)
    sampled = Signal(int, int, int)
    cancelled = Signal()

    def __init__(self, fmt='hex', frames=None, history=()):
        super().__init__()
        self._fmt = fmt
        self._frames = capture_frames() if frames is None else frames
        bounds = union([frame.bounds for frame in self._frames])
        self.setGeometry(bounds.x, bounds.y, bounds.width, bounds.height)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._pos = QCursor.pos()
        if history:
            recent = QWidget(self)
            recent.setStyleSheet('background:#20374b;color:white;border-radius:4px;')
            row = QHBoxLayout(recent)
            row.addWidget(QLabel('最近'))
            for rgb in history[:12]:
                button = QPushButton('')
                button.setFixedSize(24, 24)
                button.setStyleSheet(f'background:{format_color(*rgb)};border:1px solid #8193a1;')
                button.setToolTip(format_color(*rgb, self._fmt))
                button.clicked.connect(lambda checked=False, color=rgb: self._choose(QColor(*color)))
                row.addWidget(button)
            recent.adjustSize()
            recent.move(12, 12)

    def _sample(self):
        frame = next((f for f in self._frames if
                      f.bounds.x <= self._pos.x() < f.bounds.right and
                      f.bounds.y <= self._pos.y() < f.bounds.bottom), None)
        if frame is None:
            return None
        x = min(frame.image.width()-1, int((self._pos.x()-frame.bounds.x)*frame.dpr))
        y = min(frame.image.height()-1, int((self._pos.y()-frame.bounds.y)*frame.dpr))
        return frame, x, y, frame.image.pixelColor(x, y)

    def _choose(self, color):
        self.hide()
        self.sampled.emit(color.red(), color.green(), color.blue())
        self.color_picked.emit(format_color(color.red(), color.green(), color.blue(), self._fmt))

    def mouseMoveEvent(self, event):
        self._pos = event.globalPosition().toPoint()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pos = event.globalPosition().toPoint()
            sample = self._sample()
            if sample:
                self._choose(sample[3])
        elif event.button() == Qt.MouseButton.RightButton:
            self.hide()
            self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        origin = self.geometry().topLeft()
        for frame in self._frames:
            bounds = frame.bounds
            painter.drawImage(QRect(bounds.x-origin.x(), bounds.y-origin.y(), bounds.width, bounds.height), frame.image)
        sample = self._sample()
        if sample is None:
            return
        frame, px, py, color = sample
        cursor = self._pos-origin
        painter.setPen(QPen(QColor('#DA704C'), 1))
        painter.drawLine(cursor.x(), 0, cursor.x(), self.height())
        painter.drawLine(0, cursor.y(), self.width(), cursor.y())
        # Integer native pixels, nearest-neighbour magnification. Clipping near a
        # display edge preserves the selected pixel's position in the loupe.
        left = max(0, min(px-7, frame.image.width()-15))
        top = max(0, min(py-7, frame.image.height()-15))
        source = QRect(left, top, min(15, frame.image.width()), min(15, frame.image.height()))
        x = max(0, min(cursor.x()+24, self.width()-254))
        y = max(0, min(cursor.y()+24, self.height()-172))
        painter.fillRect(QRect(x-4, y-4, 252, 168), QColor('#20374b'))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRect(x, y, source.width()*8, source.height()*8), frame.image, source)
        painter.setPen(QPen(QColor('#DA704C'), 2))
        painter.drawRect(QRect(x+(px-left)*8, y+(py-top)*8, 8, 8))
        painter.setPen(QColor('white'))
        painter.drawText(x, y+140, format_color(color.red(), color.green(), color.blue(), self._fmt))
        painter.drawText(x, y+156, 'sRGB · Esc 退出' + (' · α=1 输出值' if self._fmt == 'rgba' else ''))
