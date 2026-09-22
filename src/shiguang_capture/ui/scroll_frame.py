"""Click-through bounds for manual scrolling, kept outside the image if possible."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor, QPainter

from ..geometry import Rect


def border_rectangles(selection: Rect, screen: Rect, thickness: int = 2) -> list[Rect]:
    """Move only screen-edge borders inside; never enlarge the capture itself."""
    t = min(thickness, selection.width, selection.height)
    left = selection.x-t if selection.x-t >= screen.x else selection.x
    right = selection.right if selection.right+t <= screen.right else selection.right-t
    top = selection.y-t if selection.y-t >= screen.y else selection.y
    bottom = selection.bottom if selection.bottom+t <= screen.bottom else selection.bottom-t
    return [Rect(left, top, right+t-left, t), Rect(left, bottom, right+t-left, t),
            Rect(left, top, t, bottom+t-top), Rect(right, top, t, bottom+t-top)]


class _BorderEdge(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#378BFA'))


class ScrollCaptureFrame:
    def __init__(self, owner: QWidget):
        self.selection = None
        self.rectangles = []
        self.edges = []
        for _ in range(4):
            edge = _BorderEdge(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                           | Qt.WindowType.WindowStaysOnTopHint
                           | Qt.WindowType.WindowTransparentForInput
                           | Qt.WindowType.WindowDoesNotAcceptFocus
                           | Qt.WindowType.NoDropShadowWindowHint
                           | Qt.WindowType.X11BypassWindowManagerHint)
            edge.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            edge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            edge.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            edge.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.edges.append(edge)

    def anchor_to(self, selection: Rect, screen: Rect):
        self.selection = selection
        self.rectangles = border_rectangles(selection, screen)
        for edge, rect in zip(self.edges, self.rectangles):
            edge.setGeometry(rect.x, rect.y, rect.width, rect.height)

    def show(self):
        if self.selection is not None:
            for edge in self.edges:
                edge.show()

    def prepare_capture(self):
        for edge, rect in zip(self.edges, self.rectangles):
            if rect.intersects(self.selection):
                edge.hide()

    def close(self):
        for edge in self.edges:
            edge.close()
