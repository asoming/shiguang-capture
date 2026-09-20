"""Inline annotation surface inside a frozen screenshot selection."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLineEdit
from .canvas import ImageCanvas, Mark


class SelectionCanvas(ImageCanvas):
    def __init__(self, parent):
        super().__init__(parent)
        self.setMinimumSize(0, 0)
        self.text_input = None
        self.text_point = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def image_rect(self):
        return QRectF(self.rect())

    def set_tool(self, tool):
        self.commit_text()
        self.tool = tool
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, tool == 'view')
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, event):
        if self.image.isNull():
            return
        painter = QPainter(self)
        painter.drawImage(self.rect(), self.image)
        painter.scale(self.width()/self.image.width(), self.height()/self.image.height())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_marks(painter, self.marks + ([self.draft] if self.draft else []))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.parent().reset_selection()
            return
        if self.tool != 'text' or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.commit_text()
        point = self.point_on_image(event.position())
        size = max(18, round(max(2, self.image.width()/450)*7))
        self.text_point = point + QPointF(0, size)
        self.text_input = QLineEdit(self)
        self.text_input.setPlaceholderText('输入文字，回车确认')
        self.text_input.setStyleSheet('QLineEdit {background:white;color:#263D4C;border:1px solid #167D8D;padding:3px;}')
        self.text_input.setGeometry(round(event.position().x()), round(event.position().y()),
                                    min(240, self.width()), 32)
        self.text_input.returnPressed.connect(self.commit_text)
        self.text_input.editingFinished.connect(self.commit_text)
        self.text_input.show()
        self.text_input.setFocus()

    def commit_text(self):
        editor, self.text_input = self.text_input, None
        if editor is None:
            return
        value = editor.text()
        editor.deleteLater()
        if value:
            self.marks.append(Mark('text', [self.text_point], value, self.color, self.line_width))
            self.undone.clear()
            self.changed.emit()
            self.update()
        self.parent().setFocus()

    def mouseDoubleClickEvent(self, event):
        if self.tool != 'text' and event.button() == Qt.MouseButton.LeftButton:
            self.parent()._on_action('copy')

    def wheelEvent(self, event):
        event.ignore()
