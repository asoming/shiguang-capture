"""Frozen screen frames; cross-screen output uses the highest intersecting DPR."""
from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import QRect
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPainter
from ..geometry import Rect, union
from ..images import validate_size


def virtual_desktop_rect() -> Rect:
    rects = [Rect(s.geometry().x(), s.geometry().y(), s.geometry().width(),
                  s.geometry().height()) for s in QGuiApplication.screens()]
    return union(rects) if rects else Rect(0, 0, 0, 0)


@dataclass
class ScreenFrame:
    bounds: Rect
    image: QImage
    dpr: float


def capture_frames() -> list[ScreenFrame]:
    frames = []
    for screen in QGuiApplication.screens():
        g = screen.geometry()
        validate_size(round(g.width() * screen.devicePixelRatio()),
                      round(g.height() * screen.devicePixelRatio()))
        image = screen.grabWindow(0).toImage()
        if image.isNull():
            raise RuntimeError("无法捕获屏幕。请检查屏幕录制权限，或打开已有图片。")
        image.setDevicePixelRatio(1)
        frames.append(ScreenFrame(Rect(g.x(), g.y(), g.width(), g.height()),
                                  image, image.width() / g.width()))
    return frames


def compose_region(frames: list[ScreenFrame], rect: Rect, density: float | None = None) -> QImage:
    frames = [f for f in frames if f.bounds.intersects(rect)]
    if not frames:
        raise ValueError("所选区域不在可用屏幕内。")
    density = density or max(f.dpr for f in frames)
    width, height = round(rect.width * density), round(rect.height * density)
    validate_size(width, height)
    result = QImage(width, height, QImage.Format.Format_ARGB32)
    result.fill(0)
    painter = QPainter(result)
    for frame in frames:
        b = frame.bounds
        left, top = max(rect.x, b.x), max(rect.y, b.y)
        right, bottom = min(rect.right, b.right), min(rect.bottom, b.bottom)
        source = QRect(round((left - b.x) * frame.dpr), round((top - b.y) * frame.dpr),
                       round((right - left) * frame.dpr), round((bottom - top) * frame.dpr))
        x, y = round((left - rect.x) * density), round((top - rect.y) * density)
        target = QRect(x, y, round((right - rect.x) * density) - x,
                       round((bottom - rect.y) * density) - y)
        painter.drawImage(target, frame.image, source)
    painter.end()
    return result


def grab_region(rect: Rect) -> QImage:
    return compose_region(capture_frames(), rect)


def grab_fullscreen() -> QImage:
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError("没有可用屏幕。")
    g = screen.geometry()
    return grab_region(Rect(g.x(), g.y(), g.width(), g.height()))
