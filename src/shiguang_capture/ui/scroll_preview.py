"""Small anchored thumbnail for an active scrolling screenshot."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..geometry import Rect
from .icon import make_icon
from .tool_icons import tool_icon


def preview_position(selection: Rect, screen: Rect, width: int, height: int) -> QPoint:
    """Prefer the selection's left edge; fall back to this screen's top left."""
    margin, gap = 12, 10
    left = selection.x-width-gap
    full_screen = (selection.x <= screen.x and selection.y <= screen.y
                   and selection.right >= screen.right and selection.bottom >= screen.bottom)
    x, y = (screen.x+margin, screen.y+margin) if full_screen or left < screen.x+margin else (left, selection.y)
    x = max(screen.x, min(x, screen.right-width-margin))
    y = max(screen.y, min(y, screen.bottom-height-margin))
    return QPoint(x, y)


class ScrollPreviewWindow(QWidget):
    abort_requested = Signal()
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('拾光 · 长截图')
        self.setWindowIcon(make_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setObjectName('scrollPreview')
        self.setFixedSize(176, 270)
        self._selection = None
        self._closed = False
        self.setStyleSheet('''
            QWidget#scrollPreview {background:#FFFFFF;border:1px solid #D7E4F4;border-radius:9px;}
            QLabel {background:transparent;color:#536D8A;border:0;font-size:11px;}
            QLabel#previewTitle {color:#243D58;font-size:12px;font-weight:600;}
            QLabel#thumbnail {background:#EEF4FC;border:1px solid #E0E9F4;border-radius:4px;}
            QToolButton {background:transparent;border:0;border-radius:5px;padding:4px;}
            QToolButton:hover {background:#E9F2FF;}
            QToolButton:focus {border:1px solid #378BFA;}
        ''')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 8)
        lay.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel('长截图', objectName='previewTitle')
        header.addWidget(title)
        header.addStretch()
        self.status = QLabel('准备中')
        header.addWidget(self.status)
        lay.addLayout(header)
        self.thumb = QLabel(objectName='thumbnail')
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setFixedSize(154, 184)
        lay.addWidget(self.thumb)
        footer = QHBoxLayout()
        self.dimensions = QLabel('')
        footer.addWidget(self.dimensions)
        footer.addStretch()
        self.abort_btn = QToolButton()
        self.abort_btn.setIcon(tool_icon('cancel', '#EB5967'))
        self.abort_btn.setIconSize(QSize(20, 20))
        self.abort_btn.setFixedSize(28, 28)
        self.abort_btn.setToolTip('停止并保留已截部分')
        self.abort_btn.setAccessibleName('停止并保留已截部分')
        self.abort_btn.clicked.connect(self.abort_requested.emit)
        self.save_btn = QToolButton()
        self.save_btn.setIcon(tool_icon('copy', '#16A479'))
        self.save_btn.setIconSize(QSize(20, 20))
        self.save_btn.setFixedSize(28, 28)
        self.save_btn.setToolTip('完成长截图')
        self.save_btn.setAccessibleName('完成长截图')
        self.save_btn.clicked.connect(self.save_requested.emit)
        footer.addWidget(self.abort_btn)
        footer.addWidget(self.save_btn)
        lay.addLayout(footer)

    def anchor_to(self, selection: Rect, screen: Rect):
        self._selection = selection
        self.move(preview_position(selection, screen, self.width(), self.height()))

    def prepare_capture(self):
        bounds = Rect(self.x(), self.y(), self.width(), self.height())
        if self._selection is None or bounds.intersects(self._selection):
            self.hide()

    def restore_after_capture(self):
        if not self._closed:
            self.show()

    def closeEvent(self, event) -> None:
        self._closed = True
        self.abort_requested.emit()
        super().closeEvent(event)

    def update_image(self, image: QImage):
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            self.thumb.setPixmap(pixmap.scaled(self.thumb.size()-QSize(8, 8),
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def update_progress(self, height: int, frames: int, image: QImage | None = None) -> None:
        self.status.setText('向下滚动')
        self.dimensions.setText(f'{height:,} px')
        if image is not None:
            self.update_image(image)

    def mark_done(self, height: int, frames: int) -> None:
        self.update_progress(height, frames)
        self.status.setText('已完成')
        self.abort_btn.setEnabled(False)
