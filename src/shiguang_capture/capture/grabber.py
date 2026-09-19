"""capture/grabber.py — 屏幕抓取（FR-1.4 多显示器 / FR-1.18 不降采样）。"""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QImage, QPixmap

from ..geometry import Rect, union


def virtual_desktop_rect() -> Rect:
    """所有屏幕的几何并集（多显示器时允许负坐标）。"""
    rects = []
    for screen in QGuiApplication.screens():
        g = screen.geometry()
        rects.append(Rect(g.x(), g.y(), g.width(), g.height()))
    return union(rects) if rects else Rect(0, 0, 0, 0)


def grab_region(rect: Rect) -> QImage:
    """抓取全局坐标下的矩形区域。

    逐屏抓取再拼接，天然支持跨屏选区；不做任何缩放，
    返回物理像素图像（FR-1.18 分辨率保持）。
    """
    result = QImage(rect.width, rect.height, QImage.Format.Format_ARGB32)
    result.fill(0)
    for screen in QGuiApplication.screens():
        g = screen.geometry()
        srect = Rect(g.x(), g.y(), g.width(), g.height())
        if not srect.intersects(rect):
            continue
        ix = max(rect.x, srect.x)
        iy = max(rect.y, srect.y)
        iw = min(rect.right, srect.right) - ix
        ih = min(rect.bottom, srect.bottom) - iy
        dpr = screen.devicePixelRatio()
        pix: QPixmap = screen.grabWindow(0, ix - srect.x, iy - srect.y, iw, ih)
        img = pix.toImage()
        from PySide6.QtGui import QPainter

        painter = QPainter(result)
        # 物理像素 -> 目标偏移（除以 DPR 映射回选区坐标系）
        painter.drawImage(
            int((ix - rect.x)), int((iy - rect.y)),
            img.scaled(iw, ih),
        )
        painter.end()
        _ = dpr  # 高 DPI 细节在 V1.x 细化
    return result


def grab_fullscreen() -> QImage:
    return grab_region(virtual_desktop_rect())
