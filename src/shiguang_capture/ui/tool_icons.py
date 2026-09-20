"""Small vector tools with readable accessible names supplied by their buttons."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF


def tool_icon(name, color='#263D4C'):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    if name == 'play':
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF([QPointF(7, 4), QPointF(20, 12), QPointF(7, 20)]))
    elif name == 'pause':
        painter.fillRect(QRectF(6, 5, 4, 14), QColor(color))
        painter.fillRect(QRectF(14, 5, 4, 14), QColor(color))
    elif name == 'stop':
        painter.fillRect(QRectF(5, 5, 14, 14), QColor(color))
    elif name == 'rect':
        painter.drawRect(QRectF(4, 5, 16, 14))
    elif name == 'arrow':
        painter.drawLine(4, 20, 19, 5)
        painter.drawLine(11, 5, 19, 5)
        painter.drawLine(19, 5, 19, 13)
    elif name == 'pen':
        painter.drawLine(5, 19, 17, 5)
        painter.drawLine(17, 5, 20, 8)
        painter.drawLine(20, 8, 8, 21)
        painter.drawLine(5, 19, 8, 21)
    elif name == 'redact':
        painter.fillRect(QRectF(4, 6, 16, 12), QColor(color))
    elif name == 'copy':
        painter.drawLine(4, 12, 10, 18)
        painter.drawLine(10, 18, 21, 5)
    elif name == 'cancel':
        painter.drawLine(6, 6, 18, 18)
        painter.drawLine(18, 6, 6, 18)
    elif name == 'save':
        painter.drawRect(QRectF(5, 4, 14, 16))
        painter.drawRect(QRectF(8, 4, 8, 6))
        painter.drawRect(QRectF(8, 14, 8, 6))
    elif name == 'pin':
        painter.drawLine(9, 4, 19, 14)
        painter.drawLine(10, 5, 6, 10)
        painter.drawLine(18, 13, 13, 17)
        painter.drawLine(6, 10, 13, 17)
        painter.drawLine(10, 14, 4, 21)
    elif name == 'table':
        painter.drawRect(QRectF(3, 4, 18, 16))
        painter.drawLine(3, 10, 21, 10)
        painter.drawLine(3, 15, 21, 15)
        painter.drawLine(10, 4, 10, 20)
    elif name == 'record':
        painter.setBrush(QColor('#DB4C46'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(5, 5, 14, 14))
    else:
        labels = {'view':'↔', 'text':'T', 'undo':'↶', 'redo':'↷', 'ocr':'OCR', 'code':'</>', 'scroll':'↕'}
        font = QFont('DejaVu Sans', 9 if name in {'ocr', 'code'} else 17)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, labels.get(name, name[:1]))
    painter.end()
    return QIcon(pixmap)
