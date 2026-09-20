"""Inline annotations with re-editable text and transactional undo."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QLineEdit
from .canvas import ImageCanvas, Mark


class TextEditor(QLineEdit):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.returnPressed.emit()
            event.accept()  # Commit text without triggering the selector's copy action.
        else:
            super().keyPressEvent(event)


class SelectionCanvas(ImageCanvas):
    def __init__(self, parent):
        super().__init__(parent)
        self.setMinimumSize(0, 0)
        self.text_input = None
        self.text_point = None
        self.edit_index = None
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
        visible = [mark for index, mark in enumerate(self.marks) if index != self.edit_index]
        self.paint_marks(painter, visible + ([self.draft] if self.draft else []))

    def edit_text_at(self, position):
        if not self.rect().contains(position.toPoint()) or self.image.isNull():
            return False
        point = self.point_on_image(position)
        for index in range(len(self.marks)-1, -1, -1):
            mark = self.marks[index]
            if mark.tool == 'text' and self.text_bounds(mark).contains(point):
                self.commit_text()
                self._open_text(mark.points[0], index)
                return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.parent().reset_selection()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.edit_text_at(event.position()):
            return
        if self.tool != 'text' or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.commit_text()
        size = max(18, round(max(2, self.image.width()/450)*7))
        self._open_text(self.point_on_image(event.position()) + QPointF(0, size))

    def _open_text(self, point, index=None):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.text_point, self.edit_index = point, index
        self.text_input = TextEditor(self)
        self.text_input.setPlaceholderText('输入文字，回车确认')
        self.text_input.setStyleSheet('QLineEdit {background:white;color:#263D4C;border:1px solid #378BFA;padding:3px;}')
        scale = self.width()/self.image.width()
        font = QFont('Noto Sans CJK SC')
        size = max(18, round(max(2, self.image.width()/450)*7))
        font.setPixelSize(max(12, round(size*scale)))
        self.text_input.setFont(font)
        x = max(0, min(round(point.x()*scale), self.width()-80))
        y = max(0, min(round((point.y()-size)*scale), self.height()-32))
        self.text_input.setGeometry(x, y, min(280, self.width()-x), 32)
        if index is not None:
            self.text_input.setText(self.marks[index].text)
        self.text_input.returnPressed.connect(self.commit_text)
        self.text_input.editingFinished.connect(self.commit_text)
        self.text_input.show()
        self.text_input.setFocus()
        self.text_input.selectAll()
        self.update()

    def commit_text(self):
        editor, self.text_input = self.text_input, None
        if editor is None:
            return
        value, index = editor.text(), self.edit_index
        self.edit_index = None
        editor.hide()
        editor.deleteLater()
        if index is not None:
            if self.marks[index].text != value:
                self.checkpoint()
                if value:
                    self.marks[index].text = value
                else:
                    self.marks.pop(index)
                self.changed.emit()
        elif value:
            self.checkpoint()
            self.marks.append(Mark('text', [self.text_point], value, self.color, self.line_width))
            self.changed.emit()
        self.update()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self.tool == 'view')
        self.parent().setFocus()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.edit_text_at(event.position()) and self.tool != 'text':
            self.parent()._on_action('copy')

    def wheelEvent(self, event):
        event.ignore()
