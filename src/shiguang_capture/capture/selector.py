"""capture/selector.py — 全屏取景框（FR-1.5 ~ FR-1.10）。

无边框半透明置顶窗口覆盖虚拟桌面：
- 拖拽框选，实时显示尺寸（FR-1.5）
- 方向键逐像素微调（FR-1.10）
- 放大镜：像素级放大 + 光标坐标 + 当前色值（FR-1.9）
- Enter 确认 / Esc 取消
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..colors import rgb_to_hex
from ..geometry import Rect
from .grabber import virtual_desktop_rect


class RegionSelector(QWidget):
    region_selected = Signal(object)   # geometry.Rect
    cancelled = Signal()

    MAG_SIZE = 120      # 放大镜边长（屏幕像素）
    MAG_ZOOM = 8        # 放大倍数
    MAG_CELLS = 15      # 放大镜覆盖的物理像素数

    def __init__(self) -> None:
        super().__init__()
        bounds = virtual_desktop_rect()
        self._bounds = bounds
        self.setGeometry(bounds.x, bounds.y, bounds.width, bounds.height)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._origin: QPoint | None = None
        self._current: Rect | None = None
        self._cursor: QPoint | None = None

    # ---------- 鼠标 ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin = e.globalPosition().toPoint()
            self._current = None
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        gp = e.globalPosition().toPoint()
        self._cursor = gp
        if self._origin is not None:
            self._current = Rect.from_corners(
                self._origin.x(), self._origin.y(), gp.x(), gp.y()
            )
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._origin = None
        if self._current and self._current.is_valid:
            rect = self._current
            self.hide()
            self.region_selected.emit(rect)
        else:
            self._current = None
            self.update()

    # ---------- 键盘 ----------
    def keyPressEvent(self, e: QKeyEvent) -> None:
        key = e.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._current and self._current.is_valid:
                rect = self._current
                self.hide()
                self.region_selected.emit(rect)
            return
        nudge = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }.get(key)
        if nudge and self._current:
            self._current = self._current.nudged(*nudge, self._bounds)
            self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt 命名)
        p = QPainter(self)
        origin = self.rect().topLeft()
        # 遮罩
        p.fillRect(self.rect(), QColor(10, 12, 16, 110))
        if self._current and self._current.width > 0:
            local = self._current.translated(-origin.x(), -origin.y())
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.fillRect(local.x, local.y, local.width, local.height, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(125, 155, 255), 2))
            p.drawRect(local.x, local.y, local.width, local.height)
            # 尺寸标签
            p.setPen(QColor(233, 237, 243))
            p.drawText(local.x + 6, local.y - 8,
                       f"{self._current.width} × {self._current.height}")
        if self._cursor:
            self._draw_magnifier(p, origin)
        p.end()

    def _draw_magnifier(self, p: QPainter, origin: QPoint) -> None:
        cx, cy = self._cursor.x() - origin.x(), self._cursor.y() - origin.y()
        screen = QGuiApplication.screenAt(self._cursor) or QGuiApplication.primaryScreen()
        n = self.MAG_CELLS
        grab = screen.grabWindow(
            0,
            self._cursor.x() - screen.geometry().x() - n // 2,
            self._cursor.y() - screen.geometry().y() - n // 2,
            n, n,
        ).toImage()
        mag_x = min(cx + 24, self.width() - self.MAG_SIZE - 8)
        mag_y = min(cy + 24, self.height() - self.MAG_SIZE - 40)
        p.drawImage(mag_x, mag_y, grab.scaled(self.MAG_SIZE, self.MAG_SIZE))
        p.setPen(QPen(QColor(125, 155, 255), 2))
        p.drawRect(mag_x, mag_y, self.MAG_SIZE, self.MAG_SIZE)
        # 中心十字
        mid = self.MAG_SIZE // 2
        p.setPen(QPen(QColor(255, 107, 110), 1))
        p.drawLine(mag_x + mid, mag_y, mag_x + mid, mag_y + self.MAG_SIZE)
        p.drawLine(mag_x, mag_y + mid, mag_x + self.MAG_SIZE, mag_y + mid)
        # 坐标 + 色值
        center = grab.scaled(1, 1).pixelColor(0, 0) if not grab.isNull() else QColor(0, 0, 0)
        p.setPen(QColor(233, 237, 243))
        p.drawText(
            mag_x, mag_y + self.MAG_SIZE + 18,
            f"({self._cursor.x()}, {self._cursor.y()})  "
            f"{rgb_to_hex(center.red(), center.green(), center.blue())}",
        )
