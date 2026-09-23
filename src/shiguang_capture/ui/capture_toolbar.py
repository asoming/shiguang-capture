"""Compact screenshot tools with an anchored annotation palette."""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QToolButton, QWidget

from .tool_icons import tool_icon

DRAWING_TOOLS = {'view', 'rect', 'ellipse', 'arrow', 'pen', 'text', 'redact'}
STYLE_TOOLS = {'rect', 'ellipse', 'arrow', 'pen', 'text'}
TOOLS = [('view', '调整选区'), ('rect', '矩形'), ('ellipse', '椭圆'), ('arrow', '箭头'),
         ('pen', '画笔'), ('redact', '实色遮盖'), ('text', '文字')]
ACTIONS = [('translate', '识别并翻译'), ('ocr', '文字识别'), ('code', '代码识别'),
           ('table', '表格识别'), ('scroll', '长截图'), ('undo', '撤销 Ctrl+Z'),
           ('redo', '重做 Ctrl+Y'), ('save', '保存 Ctrl+S'), ('pin', '贴图'),
           ('cancel', '取消 Esc'), ('copy', '完成并复制 Enter / Ctrl+C')]
PANEL_STYLE = '''
QWidget#captureBar, QWidget#annotationPalette {background:#FFFFFF;border:1px solid #D9E3EF;border-radius:8px;}
QToolButton {background:transparent;border:1px solid transparent;border-radius:5px;padding:3px;}
QToolButton:hover {background:#EDF5FF;}
QToolButton:checked {background:#E6F1FF;border-color:#9AC3FC;}
QToolButton:focus {border-color:#378BFA;}
QComboBox {background:white;color:#263D4C;border:0;padding:3px;font-size:12px;}
QComboBox QAbstractItemView {background:white;color:#263D4C;selection-background-color:#E6F1FF;}
'''


class CaptureToolbar(QWidget):
    action_clicked = Signal(str)

    def __init__(self, parent, selection_only=False):
        super().__init__(parent)
        self.setObjectName('captureBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedHeight(46)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(7, 5, 7, 5)
        self.row.setSpacing(2)
        self.buttons = {}
        entries = [('cancel', '取消 Esc'), ('copy', '确认选区 Enter')] if selection_only else TOOLS+ACTIONS
        for action, label in entries:
            button = QToolButton(self)
            color = '#16A479' if action == 'copy' else '#EB5967' if action == 'cancel' else '#263D4C'
            button.setIcon(tool_icon(action, color))
            button.setIconSize(QSize(24, 24))
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedSize(34, 34)
            button.setCheckable(action in DRAWING_TOOLS)
            button.setChecked(action == 'view')
            button.clicked.connect(lambda checked=False, value=action: self.action_clicked.emit(value))
            self.row.addWidget(button)
            self.buttons[action] = button
            if action in {'text', 'scroll', 'redo', 'pin'}:
                line = QWidget(self)
                line.setFixedSize(1, 20)
                line.setStyleSheet('background:#DEE5EE;')
                self.row.addWidget(line)

    def fit_width(self, available):
        gaps = self.row.contentsMargins().left()+self.row.contentsMargins().right()+self.row.spacing()*(self.row.count()-1)
        separators = self.row.count()-len(self.buttons)
        size = min(34, max(16, (available-gaps-separators)//len(self.buttons)))
        for button in self.buttons.values():
            button.setFixedWidth(size)
            button.setIconSize(QSize(min(24, size-4), min(24, size-4)))
        self.adjustSize()

    def select_tool(self, tool):
        for key, button in self.buttons.items():
            if button.isCheckable():
                button.setChecked(key == tool)


class AnnotationPalette(QWidget):
    color_changed = Signal(str)
    size_changed = Signal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('annotationPalette')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedHeight(40)
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 4, 7, 4)
        row.setSpacing(4)
        self.size_combo = QComboBox(self)
        self.size_combo.setFixedWidth(60)
        self.size_combo.setAccessibleName('标注大小')
        self.size_combo.setToolTip('标注大小')
        self.size_combo.addItems(['小', '中', '大'])
        self.size_combo.setCurrentIndex(1)
        self.size_combo.currentIndexChanged.connect(self.size_changed)
        row.addWidget(self.size_combo)
        self.colors = {}
        for color, label in [('#DA704C','橙色'),('#EF5261','红色'),('#F5C443','黄色'),
                             ('#24BA85','绿色'),('#378BFA','蓝色'),('#A57AF5','紫色'),
                             ('#20374B','深色'),('#FFFFFF','白色')]:
            button = QToolButton(self)
            pixmap = QPixmap(22, 22)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QColor('#CBD7E4'))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(2, 2, 17, 17, 3, 3)
            painter.end()
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(28, 28)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setCheckable(True)
            button.setChecked(color == '#DA704C')
            button.clicked.connect(lambda checked=False, value=color: self._choose_color(value))
            self.colors[color] = button
            row.addWidget(button)
        self.adjustSize()

    def _choose_color(self, color):
        for value, button in self.colors.items():
            button.setChecked(value == color)
        self.color_changed.emit(color)
