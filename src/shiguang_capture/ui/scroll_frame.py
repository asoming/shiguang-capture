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
        painter.fillRect(self.rect(), QColor('#C3E2F5'))


class ScrollCaptureFrame:
    def __init__(self, owner: QWidget):
        self.selection = None
        self.rectangles = []
        self.edges = []
        self.shades = []
        self.shade_bounds = []
        self.badge = self._window(_SizeBadge)
        self.badge_rect = None
        self.edges = [self._window(_BorderEdge) for _ in range(4)]

    @staticmethod
    def _window(widget_type):
        window = widget_type(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                             | Qt.WindowType.WindowStaysOnTopHint
                             | Qt.WindowType.WindowTransparentForInput
                             | Qt.WindowType.WindowDoesNotAcceptFocus
                             | Qt.WindowType.NoDropShadowWindowHint
                             | Qt.WindowType.X11BypassWindowManagerHint)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        window.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        window.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return window

    def anchor_to(self, selection: Rect, screen: Rect, screens=None):
        self.selection = selection
        self.rectangles = border_rectangles(selection, screen)
        for shade in self.shades:
            shade.close()
            shade.deleteLater()
        self.shade_bounds = [rect for desktop in (screens or [screen]) for rect in shade_rectangles(selection, desktop)]
        self.shades = [self._window(_ShadePanel) for _ in self.shade_bounds]
        for shade, rect in zip(self.shades, self.shade_bounds):
            shade.setGeometry(rect.x, rect.y, rect.width, rect.height)
        x = max(screen.x, min(selection.x, screen.right-140))
        y = selection.y-34 if selection.y-34 >= screen.y else selection.y+8
        self.badge_rect = Rect(x, min(y, screen.bottom-28), 140, 26)
        self.badge.setGeometry(self.badge_rect.x, self.badge_rect.y, 140, 26)
        self.set_size(selection.width, selection.height)
        for edge, rect in zip(self.edges, self.rectangles):
            edge.setGeometry(rect.x, rect.y, rect.width, rect.height)

    def show(self):
        if self.selection is not None:
            for shade in self.shades:
                shade.show()
            for edge in self.edges:
                edge.show()
            self.badge.show()

    def set_size(self, width, height):
        self.badge.text = f'{width} × {height}'
        self.badge.update()

    def prepare_capture(self):
        if self.badge_rect and self.badge_rect.intersects(self.selection):
            self.badge.hide()
        for edge, rect in zip(self.edges, self.rectangles):
            if rect.intersects(self.selection):
                edge.hide()

    def close(self):
        for window in [*self.edges, *self.shades, self.badge]:
            window.close()


def shade_rectangles(selection: Rect, screen: Rect) -> list[Rect]:
    """Cover only the desktop outside the live capture aperture."""
    hole = selection.clamp(screen)
    if hole.area == 0:
        return [screen]
    return [rect for rect in [Rect(screen.x, screen.y, screen.width, hole.y-screen.y),
                             Rect(screen.x, hole.bottom, screen.width, screen.bottom-hole.bottom),
                             Rect(screen.x, hole.y, hole.x-screen.x, hole.height),
                             Rect(hole.right, hole.y, screen.right-hole.right, hole.height)] if rect.area > 0]


class _ShadePanel(_BorderEdge):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))


class _SizeBadge(_BorderEdge):
    text = ''

    def paintEvent(self, event):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QFont, QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor('#FBFCFE'))
        painter.setPen(QPen(QColor('#CCD4DC'), 1))
        painter.drawRoundedRect(QRectF(.5, .5, self.width()-1, self.height()-1), 7, 7)
        font = QFont('DejaVu Sans Mono')
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor('#303842'))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)
