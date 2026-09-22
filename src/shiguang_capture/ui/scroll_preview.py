"""Live scrolling aperture, compact action bar and growing image thumbnail."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal, QSize, QRectF
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..geometry import Rect
from .icon import make_icon
from .scroll_frame import ScrollCaptureFrame
from .tool_icons import tool_icon


def preview_position(selection: Rect, screen: Rect, width: int, height: int) -> QPoint:
    """Prefer below the action bar, then left; fullscreen uses the top left."""
    margin, gap = 12, 10
    if selection.bottom+50+height <= screen.bottom-margin:
        x, y = selection.right-width, selection.bottom+50
    elif selection.x-width-gap >= screen.x+margin:
        x, y = selection.x-width-gap, selection.y
    else:
        x, y = screen.x+margin, screen.y+margin+32
    return QPoint(max(screen.x, min(x, screen.right-width-margin)),
                  max(screen.y, min(y, screen.bottom-height-margin)))


def toolbar_position(selection: Rect, screen: Rect, width: int, height: int) -> QPoint:
    x = max(screen.x, min(selection.right-width, screen.right-width-8))
    if selection.bottom+height+6 <= screen.bottom:
        y = selection.bottom+6
    elif selection.y-height-6 >= screen.y:
        y = selection.y-height-6
    else:
        y = min(selection.bottom-height-8, screen.bottom-height-8)
    return QPoint(x, max(screen.y, y))


class _SurfaceWindow(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#CCD4DC'), 1))
        painter.setBrush(QColor('#FBFCFE'))
        painter.drawRoundedRect(QRectF(.5, .5, self.width()-1, self.height()-1), 6, 6)


class ScrollPreviewWindow(_SurfaceWindow):
    abort_requested = Signal()
    save_requested = Signal()
    edit_requested = Signal()
    export_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                 | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.X11BypassWindowManagerHint)
        self.setWindowTitle('拾光 · 长截图')
        self.setWindowIcon(make_icon())
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('scrollPreview')
        self.setFixedSize(176, 246)
        self.selection_frame = ScrollCaptureFrame(self)
        self._selection = None
        self._closed = False
        self._capture_width = 0
        self.finish_action = 'edit'
        self.setStyleSheet('''
            QWidget#scrollPreview {background:#FBFCFE;border:1px solid #CCD4DC;border-radius:5px;}
            QLabel {background:transparent;color:#59636F;border:0;font-size:11px;}
            QLabel#thumbnail {background:#FFFFFF;}
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        self.thumb = QLabel(objectName='thumbnail')
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.thumb.setFixedSize(164, 212)
        layout.addWidget(self.thumb)
        self.dimensions = QLabel('')
        self.dimensions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dimensions)

        self.toolbar = _SurfaceWindow(None, flags)
        self.toolbar.setObjectName('scrollActions')
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.toolbar.setFixedSize(292, 40)
        self.toolbar.setStyleSheet('''
            QWidget#scrollActions {background:#FBFCFE;border:1px solid #CCD4DC;border-radius:7px;}
            QLabel {background:transparent;color:#424C58;border:0;font-size:12px;padding:0 6px;}
            QToolButton {background:transparent;border:0;border-radius:4px;}
            QToolButton:hover {background:#EAF0F7;}
            QToolButton:focus {border:1px solid #729FC1;}
        ''')
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(7, 3, 7, 3)
        bar.setSpacing(4)
        self.status = QLabel('手动滚动')
        self.status.setMinimumWidth(102)
        bar.addWidget(self.status)
        bar.addStretch()
        self.edit_btn = self._button('pen', '完成并编辑', self.edit_requested.emit)
        self.export_btn = self._button('save', '完成并保存到文件', self.export_requested.emit)
        self.abort_btn = self._button('cancel', '取消长截图', self.abort_requested.emit, '#E66B72')
        self.save_btn = self._button('copy', '完成并复制', self.save_requested.emit, '#19A976')
        for button in (self.edit_btn, self.export_btn, self.abort_btn, self.save_btn):
            bar.addWidget(button)

    def _button(self, icon, text, callback, color='#424C58'):
        button = QToolButton(self.toolbar)
        button.setIcon(tool_icon(icon, color))
        button.setIconSize(QSize(21, 21))
        button.setFixedSize(32, 32)
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.clicked.connect(callback)
        return button

    def anchor_to(self, selection: Rect, screen: Rect, screens=None):
        self._selection = selection
        below = screen.bottom-12-(selection.bottom+50)
        height = min(326, below) if below >= 160 else 246
        self.setFixedHeight(height)
        self.thumb.setFixedHeight(height-34)
        self.selection_frame.anchor_to(selection, screen, screens)
        self.move(preview_position(selection, screen, self.width(), self.height()))
        self.toolbar.move(toolbar_position(selection, screen, self.toolbar.width(), self.toolbar.height()))

    @property
    def capture_exclusions(self):
        frame = self.selection_frame
        return [*frame.rectangles, *([frame.badge_rect] if frame.badge_rect else []),
                Rect(self.toolbar.x(), self.toolbar.y(), self.toolbar.width(), self.toolbar.height())]

    def prepare_capture(self):
        self.selection_frame.prepare_capture()
        for window in (self, self.toolbar):
            bounds = Rect(window.x(), window.y(), window.width(), window.height())
            if self._selection is None or bounds.intersects(self._selection):
                window.hide()

    def restore_after_capture(self):
        if not self._closed:
            self.selection_frame.show()
            self.show()
            self.raise_()
            self.toolbar.show()
            self.toolbar.raise_()

    def closeEvent(self, event) -> None:
        self._closed = True
        self.selection_frame.close()
        self.toolbar.close()
        self.abort_requested.emit()
        super().closeEvent(event)

    def update_image(self, image: QImage):
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            self.thumb.setPixmap(pixmap.scaled(self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def update_progress(self, height: int, frames: int, image: QImage | None = None) -> None:
        self.status.setText('手动滚动')
        if frames == 1 and self._selection:
            self._capture_width = round(self._selection.width*height/self._selection.height)
        self.dimensions.setText(f'{height:,} px')
        if self._capture_width:
            self.selection_frame.set_size(self._capture_width, height)
        if image is not None:
            self.update_image(image)

    def mark_done(self, height: int, frames: int) -> None:
        self.update_progress(height, frames)
        self.status.setText('已完成')
        self.abort_btn.setEnabled(False)
