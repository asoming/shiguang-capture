"""colors.py — 取色器色彩格式换算（纯逻辑）。"""
from __future__ import annotations

import colorsys

_RGB_MAX = 255


def clamp8(v: int) -> int:
    return max(0, min(_RGB_MAX, int(v)))


def rgb_to_hex(r: int, g: int, b: int, upper: bool = True) -> str:
    h = "#{:02X}{:02X}{:02X}".format(clamp8(r), clamp8(g), clamp8(b))
    return h if upper else h.lower()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """解析 #RGB / #RRGGBB / RRGGBB，非法输入抛 ValueError。"""
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"非法十六进制色值: {value!r}")
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        raise ValueError(f"非法十六进制色值: {value!r}") from None


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[int, int, int]:
    """返回 (H: 0-360, S: 0-100, V: 0-100)。"""
    h, s, v = colorsys.rgb_to_hsv(clamp8(r) / 255, clamp8(g) / 255, clamp8(b) / 255)
    return round(h * 360), round(s * 100), round(v * 100)


def format_color(r: int, g: int, b: int, fmt: str = "hex") -> str:
    """按取色器输出格式渲染（FR：支持 hex / rgb / hsv 直接复制）。"""
    fmt = fmt.lower()
    if fmt == "hex":
        return rgb_to_hex(r, g, b)
    if fmt == "rgb":
        return f"rgb({clamp8(r)}, {clamp8(g)}, {clamp8(b)})"
    if fmt == "hsv":
        h, s, v = rgb_to_hsv(r, g, b)
        return f"hsv({h}, {s}%, {v}%)"
    raise ValueError(f"不支持的色值格式: {fmt!r}")
