"""ui/icon.py — 应用图标（QPainter 矢量绘制，任意尺寸渲染）。

设计语言：紫蓝渐变圆角底板 + 白色「截取框」四角括号。
括号是截图工具 universally 的符号，比字母标更直观。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

_BRAND_A = QColor(95, 128, 245)    # 蓝
_BRAND_B = QColor(154, 92, 245)    # 紫
_FRAME = QColor(255, 255, 255, 235)


def render_pixmap(size: int = 256) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = float(size)
    margin = s * 0.02
    radius = s * 0.24

    # ---- 底板：圆角矩形 + 对角渐变 ----
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0.0, _BRAND_A)
    grad.setColorAt(1.0, _BRAND_B)
    base = QPainterPath()
    base.addRoundedRect(QRectF(margin, margin, s - 2 * margin, s - 2 * margin), radius, radius)
    p.fillPath(base, grad)

    # ---- 截取框：四角括号 ----
    inset = s * 0.26          # 括号离边距离
    arm = s * 0.16            # 括号臂长
    pen = QPen(_FRAME)
    pen.setWidthF(s * 0.075)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    corners = [
        # (x, y, dx, dy)：左上角括号向右向下伸
        (inset, inset, 1, 1),
        (s - inset, inset, -1, 1),
        (inset, s - inset, 1, -1),
        (s - inset, s - inset, -1, -1),
    ]
    for x, y, dx, dy in corners:
        path = QPainterPath()
        path.moveTo(x + dx * arm, y)
        path.lineTo(x, y)
        path.lineTo(x, y + dy * arm)
        p.drawPath(path)

    # ---- 中心高光点（取景焦点）----
    p.setBrush(_FRAME)
    p.setPen(Qt.PenStyle.NoPen)
    dot = s * 0.055
    p.drawEllipse(QRectF(s / 2 - dot, s / 2 - dot, dot * 2, dot * 2))

    p.end()
    return pix


def make_icon() -> QIcon:
    """多尺寸合成图标，系统自动选用。"""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render_pixmap(size))
    return icon


def export_pngs(directory: Path, sizes: tuple[int, ...] = (32, 64, 128, 256)) -> list[Path]:
    """导出 PNG 资产（站点 favicon / README / 打包用）。"""
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for size in sizes:
        path = directory / f"icon-{size}.png"
        render_pixmap(size).save(str(path))
        out.append(path)
    return out
