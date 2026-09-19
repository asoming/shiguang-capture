"""ui/pin_window.py — 贴图窗口（FR-1.20 ~ FR-1.28）。

无边框置顶窗口承载一张截图：
- 始终置顶（FR-1.21）
- 滚轮调节透明度（FR-1.23）
- Ctrl+滚轮等比缩放（FR-1.24）
- 双击关闭；贴图为临时对象，不落盘（FR-1.28）
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel

MIN_OPACITY, MAX_OPACITY = 0.1, 1.0
MIN_SCALE, MAX_SCALE = 0.2, 4.0


class PinWindow(QLabel):
    closed = Signal(object)  # self

    def __init__(self, image: QImage, opacity: float = 1.0) -> None:
        super().__init__()
        self._image = image
        self._scale = 1.0
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowOpacity(max(MIN_OPACITY, min(MAX_OPACITY, opacity)))
        self._render()
        self.setToolTip("拖动移动 · 滚轮调透明度 · Ctrl+滚轮缩放 · 双击关闭")

    # ---------- 渲染 ----------
    def _render(self) -> None:
        pix = QPixmap.fromImage(self._image)
        w = max(1, int(pix.width() * self._scale))
        h = max(1, int(pix.height() * self._scale))
        self.setPixmap(pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation))
        self.resize(self.pixmap().size())

    # ---------- 交互 ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _e: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, _e: QMouseEvent) -> None:
        self.close()

    def wheelEvent(self, e: QWheelEvent) -> None:
        delta = 1 if e.angleDelta().y() > 0 else -1
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._scale = max(MIN_SCALE, min(MAX_SCALE, self._scale * (1.1 ** delta)))
            self._render()
        else:
            self.setWindowOpacity(
                max(MIN_OPACITY, min(MAX_OPACITY, self.windowOpacity() + 0.05 * delta))
            )

    def closeEvent(self, e) -> None:  # noqa: N802
        self.closed.emit(self)
        super().closeEvent(e)
