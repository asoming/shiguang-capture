"""Transient countdown and draggable recording controls."""
import math
import time
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget, QToolButton, QLabel
from .tool_icons import tool_icon


class CountdownOverlay(QWidget):
    cancelled = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.deadline = 0
        self.animation = QTimer(self)
        self.animation.setInterval(16)
        self.animation.timeout.connect(self.update)

    def begin(self, screen, deadline):
        self.deadline = deadline
        self.setGeometry(screen.geometry())
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.animation.start()

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        remaining = max(0, self.deadline-time.monotonic())
        phase = remaining % 1
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(7, 19, 40, 100))
        center = self.rect().center()
        p.translate(center)
        glow = QRadialGradient(0, 0, 180)
        glow.setColorAt(0, QColor(40, 131, 255, 160))
        glow.setColorAt(1, QColor(40, 131, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-180, -180, 360, 360))
        p.setBrush(QColor(14, 38, 78, 220))
        p.drawEllipse(QRectF(-102, -102, 204, 204))
        p.setPen(QPen(QColor(106, 183, 255, 75), 3))
        p.drawEllipse(QRectF(-112, -112, 224, 224))
        p.setPen(QPen(QColor('#72D5FF'), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(-112, -112, 224, 224), 90*16, -round(phase*360*16))
        font = QFont('DejaVu Sans')
        font.setPixelSize(round(88+14*phase))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('white'))
        p.drawText(QRectF(-100, -105, 200, 200), Qt.AlignmentFlag.AlignCenter, str(max(1, math.ceil(remaining))))
        font.setPixelSize(13)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor('#D8E9FF'))
        p.drawText(QRectF(-150, 130, 300, 40), Qt.AlignmentFlag.AlignCenter, 'Esc 取消')


class RecordingOrb(QWidget):
    stop_requested = Signal()
    toggle_requested = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle('拾光 · 录制控制')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('录制控制')
        self.setAccessibleDescription('空格或回车展开控制，Esc 收起；可拖动到屏幕边缘。')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.expanded = False
        self.docked = None
        self._press = self._origin = None
        self._dragged = False
        self.animation = QTimer(self)
        self.animation.setInterval(40)
        self.animation.timeout.connect(self.update)
        self.clock = QLabel('00:00', self)
        self.clock.setStyleSheet('color:#527397; background:transparent; font-family:"DejaVu Sans Mono","Consolas",monospace; font-size:11px;')
        self.play = self._button('play', '继续录制', self.toggle_requested.emit)
        self.pause = self._button('pause', '暂停录制', self.toggle_requested.emit)
        self.stop_button = self._button('stop', '停止并保存', self.stop_requested.emit)
        self.resize(64, 64)
        screen = QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right()-100, area.top()+120)
        self.set_state('starting')
        self._layout()

    def _button(self, icon, title, callback):
        button = QToolButton(self)
        button.setIcon(tool_icon(icon, '#ED6D8C' if icon == 'stop' else '#3182E9'))
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setStyleSheet('QToolButton {background:#E6F1FF;border:1px solid #C6DEF9;border-radius:18px;} QToolButton:hover {background:#D2E8FF;border-color:#7BBAF0;} QToolButton:pressed {background:#BCDDFE;} QToolButton:disabled {background:#EDF2F8;border-color:#DEE7F2;} QToolButton:focus {border:2px solid #9AE7FF;}')
        button.clicked.connect(callback)
        return button

    def set_state(self, state):
        self.state = state
        self.play.setEnabled(state == 'paused')
        self.pause.setEnabled(state == 'recording')
        self.stop_button.setEnabled(state in ('starting', 'recording', 'paused'))
        self.setToolTip({'starting': '准备录制', 'recording': '录制中 · 点击展开',
                         'paused': '已暂停 · 点击展开', 'saving': '正在保存'}.get(state, '录制控制'))
        self._animate_if_needed()
        self.update()

    def _animate_if_needed(self):
        if self.isVisible() and not self.docked and self.state in ('starting', 'recording', 'saving'):
            self.animation.start()
        else:
            self.animation.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._animate_if_needed()

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def _layout(self):
        for index, button in enumerate((self.play, self.pause, self.stop_button)):
            button.setGeometry(77+index*43, 8, 36, 36)
            button.setVisible(self.expanded)
        self.clock.setGeometry(78, 45, 135, 16)
        self.clock.setVisible(self.expanded)
        self._animate_if_needed()
        self.update()

    def set_expanded(self, expanded):
        screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        self.expanded = expanded
        self.docked = None
        self.resize(218 if expanded else 64, 64)
        if screen:
            area = screen.availableGeometry()
            self.move(max(area.left(), min(self.x(), area.right()-self.width()+1)),
                      max(area.top(), min(self.y(), area.bottom()-63)))
        self._layout()

    def dock_if_near_edge(self):
        screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        left = self.x() <= area.left()+24
        right = self.x()+self.width() >= area.right()-24
        if left or right:
            self.expanded = False
            self.docked = 'left' if left else 'right'
            self.resize(32, 64)
            self.move(area.left() if left else area.right()-31,
                      max(area.top(), min(self.y(), area.bottom()-63)))
            self._layout()
        else:
            self.move(max(area.left(), min(self.x(), area.right()-self.width()+1)),
                      max(area.top(), min(self.y(), area.bottom()-63)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
            self._dragged = False

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        delta = event.globalPosition().toPoint()-self._press
        if delta.manhattanLength() > 5:
            self._dragged = True
        if self._dragged:
            if self.docked:
                self.docked = None
                self.resize(64, 64)
                self._animate_if_needed()
            self.move(self._origin+delta)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._press is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self._press = None
        if self._dragged:
            self.dock_if_near_edge()
        else:
            self.set_expanded(not self.expanded)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.set_expanded(not self.expanded)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.set_expanded(False)
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.expanded:
            p.setPen(QPen(QColor('#DFE6EF'), 1))
            p.setBrush(QColor(255, 255, 255, 252))
            p.drawRoundedRect(QRectF(1, 1, self.width()-2, 62), 31, 31)
        x = -30 if self.docked == 'left' else (2 if self.docked == 'right' else 2)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(x+30, 32, 32)
        glow.setColorAt(0, QColor(40, 156, 255, 200))
        glow.setColorAt(.8, QColor(40, 156, 255, 90))
        glow.setColorAt(1, QColor(40, 156, 255, 0))
        p.setBrush(glow)
        p.drawEllipse(QRectF(x-2, 0, 64, 64))
        body = QLinearGradient(x+5, 5, x+51, 62)
        body.setColorAt(0, QColor('#61D9FF'))
        body.setColorAt(.42, QColor('#2875F6'))
        body.setColorAt(1, QColor('#193FAD'))
        p.setBrush(body)
        p.drawEllipse(QRectF(x, 2, 60, 60))
        if self.docked:
            p.setPen(QPen(QColor('#B2EDFF'), 2))
            p.drawArc(QRectF(x+6, 8, 48, 48), 45*16, 180*16)
            return
        p.setPen(QPen(QColor(201, 237, 255, 90), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(9, 9, 46, 46))
        paused = self.state == 'paused'
        angle = 90 if paused else int(time.monotonic()*90) % 360
        p.setPen(QPen(QColor('#FFE0A1' if paused else '#D9FAFF'), 2.5,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(9, 9, 46, 46), angle*16, 105*16)
        p.setPen(QPen(QColor(150, 235, 255, 110), 2))
        p.drawArc(QRectF(9, 9, 46, 46), (angle+180)*16, 50*16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('white'))
        if paused:
            p.drawRoundedRect(QRectF(24, 23, 5, 18), 2, 2)
            p.drawRoundedRect(QRectF(35, 23, 5, 18), 2, 2)
        else:
            radius = 7 + (math.sin(time.monotonic()*3)*.7 if self.state == 'recording' else 0)
            p.drawEllipse(QRectF(32-radius, 32-radius, radius*2, radius*2))

    def closeEvent(self, event):
        self.stop_requested.emit()
        event.ignore()
