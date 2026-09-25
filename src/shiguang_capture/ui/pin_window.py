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
from PySide6.QtWidgets import QLabel, QMenu, QMessageBox

MIN_OPACITY, MAX_OPACITY = 0.1, 1.0
MIN_SCALE, MAX_SCALE = 0.2, 4.0


class PinWindow(QLabel):
    closed = Signal(object)  # self
    recognize_requested = Signal(QImage)
    edit_requested = Signal(QImage)

    def __init__(self, image: QImage, opacity: float = 1.0, restore_shortcut='ctrl+shift+f3') -> None:
        super().__init__()
        self._image = image.copy()
        self._passthrough = False
        self._locked = False
        self._restore_shortcut = restore_shortcut
        self._scale = 1.0
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(max(MIN_OPACITY, min(MAX_OPACITY, opacity)))
        self._render()
        self.setToolTip("拖动移动 · 滚轮调透明度 · Ctrl+滚轮缩放 · 右键菜单 · 双击关闭")

    def set_passthrough(self, enabled):
        self._passthrough = enabled
        position = self.pos()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        self.move(position)
        self.show()

    def set_locked(self, locked):
        self._locked = locked
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.ArrowCursor if locked else Qt.CursorShape.SizeAllCursor)

    def restore(self):
        self.set_passthrough(False)
        self.show()
        self.raise_()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy = menu.addAction('复制图片')
        recognize = menu.addAction('识别文字')
        edit = menu.addAction('编辑图片')
        menu.addSeparator()
        lock = menu.addAction('锁定位置')
        lock.setCheckable(True)
        lock.setChecked(self._locked)
        opacity = menu.addMenu('透明度')
        for percent in (25, 50, 75, 100):
            action = opacity.addAction(f'{percent}%')
            action.setCheckable(True)
            action.setChecked(round(self.windowOpacity()*100) == percent)
            action.triggered.connect(lambda checked=False, value=percent: self.setWindowOpacity(value/100))
        zoom = menu.addMenu('缩放')
        for percent in (50, 100, 150, 200):
            action = zoom.addAction(f'{percent}%')
            action.triggered.connect(lambda checked=False, value=percent: self.set_scale(value/100))
        passthrough = menu.addAction('鼠标穿透…')
        hide = menu.addAction('隐藏贴图')
        close = menu.addAction('关闭贴图')
        chosen = menu.exec(event.globalPos())
        if chosen == copy:
            from ..clipboard import write_image
            try:
                write_image(self._image)
            except RuntimeError as exc:
                QMessageBox.warning(self, '复制失败', str(exc))
        elif chosen == recognize:
            self.recognize_requested.emit(self._image.copy())
        elif chosen == edit:
            self.edit_requested.emit(self._image.copy())
        elif chosen == lock:
            self.set_locked(lock.isChecked())
        elif chosen == hide:
            self.hide()
        elif chosen == passthrough:
            answer = QMessageBox.question(self, '鼠标穿透',
                f'开启后鼠标会穿过此贴图。\n按 {self._restore_shortcut}，或在托盘菜单选“找回全部贴图”，可退出穿透。',
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Ok:
                self.set_passthrough(True)
        elif chosen == close:
            self.close()

    def set_scale(self, scale):
        self._scale = max(MIN_SCALE, min(MAX_SCALE, scale))
        self._render()

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
        if e.button() == Qt.MouseButton.LeftButton and not self._locked:
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
            self.set_scale(self._scale * (1.1 ** delta))
        else:
            self.setWindowOpacity(
                max(MIN_OPACITY, min(MAX_OPACITY, self.windowOpacity() + 0.05 * delta))
            )

    def closeEvent(self, e) -> None:  # noqa: N802
        self.closed.emit(self)
        super().closeEvent(e)
