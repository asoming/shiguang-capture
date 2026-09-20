"""Image annotation canvas. All output is flattened from the visible edits."""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QInputDialog, QWidget


@dataclass
class Mark:
    tool: str
    points: list[QPointF]
    text: str = ''
    color: str = '#DA704C'
    width: float = 0


class ImageCanvas(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.tool = 'view'
        self.color = '#DA704C'
        self.line_width = 0
        self.marks: list[Mark] = []
        self.undone: list[list[Mark]] = []
        self.history: list[list[Mark]] = []
        self.draft = None
        self.highlight = None
        self.zoom = 1.0
        self.pan = QPointF()
        self._pan_origin = None
        self.setMinimumSize(250, 230)
        self.setMouseTracking(True)

    def set_image(self, image):
        self.image = image.copy()
        self.image.setDevicePixelRatio(1)
        self.marks.clear()
        self.undone.clear()
        self.history.clear()
        self.draft = None
        self.highlight = None
        self.zoom = 1.0
        self.pan = QPointF()
        self.update()

    def image_rect(self):
        if self.image.isNull():
            return QRectF()
        space = self.rect().adjusted(22, 22, -22, -22)
        ratio = min(space.width() / self.image.width(), space.height() / self.image.height())
        w, h = self.image.width() * ratio * self.zoom, self.image.height() * ratio * self.zoom
        return QRectF((self.width()-w)/2+self.pan.x(), (self.height()-h)/2+self.pan.y(), w, h)

    def point_on_image(self, point):
        rect = self.image_rect()
        if rect.isEmpty():
            return QPointF()
        return QPointF(max(0, min(self.image.width(), (point.x()-rect.x())*self.image.width()/rect.width())),
                       max(0, min(self.image.height(), (point.y()-rect.y())*self.image.height()/rect.height())))

    def paint_marks(self, painter, marks):
        width = max(2, self.image.width()/450)
        for mark in marks:
            a, b = mark.points[0], mark.points[-1]
            painter.setPen(QPen(QColor(mark.color), mark.width or width, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            box = QRectF(a, b).normalized()
            if mark.tool == 'redact':
                # Solid coverage is intentionally non-antialiased at the boundary.
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                painter.fillRect(box.toAlignedRect(), QColor('#20374B'))
                painter.restore()
            elif mark.tool == 'rect':
                painter.drawRect(box)
            elif mark.tool == 'pen':
                painter.drawPolyline(QPolygonF(mark.points))
            elif mark.tool == 'arrow':
                painter.drawLine(a, b)
                angle = math.atan2(b.y()-a.y(), b.x()-a.x())
                size = width*5
                for offset in (-0.5, 0.5):
                    painter.drawLine(b, QPointF(b.x()-size*math.cos(angle+offset), b.y()-size*math.sin(angle+offset)))
            elif mark.tool == 'text':
                font = QFont('Noto Sans CJK SC')
                font.setPixelSize(max(18, round(width*7)))
                painter.setFont(font)
                painter.drawText(a, mark.text)

    def text_bounds(self, mark):
        font = QFont('Noto Sans CJK SC')
        font.setPixelSize(max(18, round(max(2, self.image.width()/450)*7)))
        return QFontMetricsF(font).boundingRect(mark.text).translated(mark.points[0]).adjusted(-5, -5, 5, 5)

    def rendered_image(self):
        result = self.image.copy()
        if not result.isNull():
            painter = QPainter(result)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.paint_marks(painter, self.marks)
            painter.end()
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#F3F6FA'))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target = self.image_rect()
        if self.image.isNull():
            painter.setPen(QColor('#657D8E'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '拖入 PNG / JPEG\n或点击「打开图片」开始')
            return
        painter.drawImage(target, self.image)
        painter.save()
        painter.translate(target.topLeft())
        painter.scale(target.width()/self.image.width(), target.height()/self.image.height())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_marks(painter, self.marks + ([self.draft] if self.draft else []))
        if self.highlight:
            left, top, right, bottom = self.highlight
            painter.setPen(QPen(QColor('#167D8D'), max(2,self.image.width()/400)))
            painter.setBrush(QColor(22,125,141,35))
            painter.drawRect(QRectF(left,top,right-left,bottom-top))
        painter.restore()
        painter.setPen(QColor('#167D8D'))
        painter.drawRect(target)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.tool in ('view', 'text') and not self.image.isNull():
            point = self.point_on_image(event.position())
            for index in range(len(self.marks)-1, -1, -1):
                mark = self.marks[index]
                if mark.tool == 'text' and self.text_bounds(mark).contains(point):
                    text, accepted = QInputDialog.getText(self, '修改文字', '标注文字', text=mark.text)
                    if accepted and text != mark.text:
                        self.checkpoint()
                        if text:
                            self.marks[index].text = text
                        else:
                            self.marks.pop(index)
                        self.changed.emit()
                        self.update()
                    return
        if event.button() == Qt.MouseButton.LeftButton and self.tool == 'view':
            self._pan_origin = event.position()
            return
        if event.button() != Qt.MouseButton.LeftButton or self.tool == 'view' or self.image.isNull():
            return
        if not self.image_rect().contains(event.position()):
            return
        point = self.point_on_image(event.position())
        if self.tool == 'text':
            text, ok = QInputDialog.getText(self, '添加文字', '标注文字')
            if ok and text.strip():
                self.checkpoint()
                self.marks.append(Mark('text', [point], text, self.color, self.line_width))
                self.undone.clear()
                self.changed.emit()
                self.update()
        else:
            self.draft = Mark(self.tool, [point, point], color=self.color, width=self.line_width)

    def mouseMoveEvent(self, event):
        if self._pan_origin is not None:
            self.pan += event.position()-self._pan_origin
            self._pan_origin = event.position()
            self.update()
        if self.draft:
            point = self.point_on_image(event.position())
            if self.tool == 'pen':
                self.draft.points.append(point)
            else:
                self.draft.points[-1] = point
            self.update()

    def mouseReleaseEvent(self, event):
        self._pan_origin = None
        if self.draft and event.button() == Qt.MouseButton.LeftButton:
            if self.draft.points[0] != self.draft.points[-1]:
                self.checkpoint()
                self.marks.append(self.draft)
                self.undone.clear()
                self.changed.emit()
            self.draft = None
            self.update()

    def checkpoint(self):
        self.history.append(deepcopy(self.marks))
        self.undone.clear()

    def undo(self):
        if self.history:
            self.undone.append(deepcopy(self.marks))
            self.marks = self.history.pop()
            self.changed.emit()
            self.update()

    def redo(self):
        if self.undone:
            self.history.append(deepcopy(self.marks))
            self.marks = self.undone.pop()
            self.changed.emit()
            self.update()

    def set_zoom(self, zoom):
        self.zoom = max(.25, min(20, zoom))
        self.pan = QPointF()
        self.update()

    def actual_size(self):
        if self.image.isNull():
            return
        space = self.rect().adjusted(22,22,-22,-22)
        fit = min(space.width()/self.image.width(), space.height()/self.image.height())
        self.set_zoom(1/fit)

    def wheelEvent(self, event):
        if self.tool == 'view':
            self.set_zoom(self.zoom*(1.15 if event.angleDelta().y()>0 else 1/1.15))
            event.accept()
