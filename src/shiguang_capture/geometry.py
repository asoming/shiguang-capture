"""geometry.py — 选区几何计算（纯逻辑，与 Qt 解耦，可直接单元测试）。"""
from __future__ import annotations

from dataclasses import dataclass

# 选区小于该尺寸视为误触（FR-1.5：拖拽框选的最小有效区域）
MIN_SELECTION = 4


@dataclass(frozen=True)
class Rect:
    """屏幕上的一个矩形选区。坐标为全局虚拟桌面坐标（支持多显示器负坐标）。"""

    x: int
    y: int
    width: int
    height: int

    # ---------- 构造 ----------
    @staticmethod
    def from_corners(x1: int, y1: int, x2: int, y2: int) -> "Rect":
        """由任意两个对角点构造（自动归一化，允许反向拖拽）。"""
        x, y = min(x1, x2), min(y1, y2)
        return Rect(x, y, abs(x2 - x1), abs(y2 - y1))

    # ---------- 判断 ----------
    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def is_valid(self) -> bool:
        """是否达到最小有效选区尺寸。"""
        return self.width >= MIN_SELECTION and self.height >= MIN_SELECTION

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def intersects(self, other: "Rect") -> bool:
        return not (
            other.x >= self.right
            or other.right <= self.x
            or other.y >= self.bottom
            or other.bottom <= self.y
        )

    # ---------- 变换 ----------
    def clamp(self, bounds: "Rect") -> "Rect":
        """将选区限制在 bounds（通常为屏幕并集）内。"""
        x = max(self.x, bounds.x)
        y = max(self.y, bounds.y)
        right = min(self.right, bounds.right)
        bottom = min(self.bottom, bounds.bottom)
        return Rect(x, y, max(0, right - x), max(0, bottom - y))

    def translated(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def with_locked_aspect(self, new_w: int, ratio: float) -> "Rect":
        """按固定长宽比调整宽度（FR-1.8：固定尺寸截图锁定长宽比）。"""
        if ratio <= 0:
            raise ValueError("ratio 必须为正数")
        return Rect(self.x, self.y, new_w, round(new_w / ratio))

    def nudged(self, dx: int, dy: int, bounds: "Rect") -> "Rect":
        """方向键逐像素微调（FR-1.10），结果不越出 bounds。"""
        return self.translated(dx, dy).clamp(bounds)


def union(rects: list[Rect]) -> Rect:
    """多个屏幕矩形的并集（多显示器虚拟桌面）。"""
    if not rects:
        raise ValueError("至少需要一个矩形")
    x = min(r.x for r in rects)
    y = min(r.y for r in rects)
    right = max(r.right for r in rects)
    bottom = max(r.bottom for r in rects)
    return Rect(x, y, right - x, bottom - y)
