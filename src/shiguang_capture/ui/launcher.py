"""Small application entry; recognition opens only after an explicit action."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel
from .theme import STYLE
from .tool_icons import tool_icon


class Launcher(QWidget):
    capture = Signal()
    record = Signal()
    recognize = Signal()
    settings = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('拾光 Capture')
        self.setStyleSheet(STYLE)
        self.setObjectName('workspace')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 22)
        title = QLabel('拾光 Capture')
        title.setStyleSheet('font-size:18px;font-weight:600;')
        layout.addWidget(title)
        row = QHBoxLayout()
        for icon, text, signal in [('rect', '截图  F1', self.capture), ('record', '录屏  F6', self.record), ('ocr', '识别  F4', self.recognize)]:
            button = QPushButton(text)
            button.setIcon(tool_icon(icon))
            button.setMinimumSize(125, 64)
            button.clicked.connect(signal.emit)
            row.addWidget(button)
        layout.addLayout(row)
        settings = QPushButton('设置')
        settings.clicked.connect(self.settings.emit)
        layout.addWidget(settings)


class ImageEditor(QWidget):
    recognize = Signal(object, str)
    save = Signal(object)
    pin = Signal(object)

    def __init__(self, image):
        super().__init__()
        from .canvas import ImageCanvas
        self.setWindowTitle('拾光 · 图片')
        self.setStyleSheet(STYLE)
        self.resize(940, 650)
        layout = QVBoxLayout(self)
        self.canvas = ImageCanvas()
        self.canvas.set_image(image)
        layout.addWidget(self.canvas, 1)
        tools = QHBoxLayout()
        from PySide6.QtWidgets import QToolButton, QButtonGroup
        group = QButtonGroup(self)
        for name, title in [('view', '移动'), ('rect', '矩形'), ('arrow', '箭头'), ('pen', '画笔'), ('text', '文字'), ('redact', '遮盖')]:
            button = QToolButton()
            button.setIcon(tool_icon(name))
            button.setToolTip(title)
            button.setCheckable(True)
            button.setChecked(name == 'view')
            button.clicked.connect(lambda checked=False, value=name: setattr(self.canvas, 'tool', value))
            group.addButton(button)
            tools.addWidget(button)
        from ..clipboard import write_image
        actions = [('undo', '撤销', self.canvas.undo), ('redo', '重做', self.canvas.redo),
                   ('save', '保存', lambda: self.save.emit(self.canvas.rendered_image())),
                   ('copy', '复制', lambda: write_image(self.canvas.rendered_image())),
                   ('ocr', '识别文字', lambda: self.recognize.emit(self.canvas.rendered_image(), 'ocr')),
                   ('table', '识别表格', lambda: self.recognize.emit(self.canvas.rendered_image(), 'table'))]
        for name, title, callback in actions:
            button = QToolButton()
            button.setIcon(tool_icon(name))
            button.setToolTip(title)
            button.clicked.connect(callback)
            tools.addWidget(button)
        layout.addLayout(tools)
