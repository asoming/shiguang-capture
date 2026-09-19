"""_console.py — 控制台输出编码兼容（Windows CI / 重定向场景）。

Windows 控制台默认 cp1252 或 cp936，直接 print 中文会抛
`UnicodeEncodeError: 'charmap' codec can't encode characters`。
CI 上 stdout 还常被重定向到文件或 PowerShell 管道，同样会炸。

用法：在任何输出之前调用 `fix_console_encoding()`。
"""
from __future__ import annotations

import sys


def fix_console_encoding() -> None:
    """把 stdout/stderr 切到 UTF-8（失败则静默放行，不影响主流程）。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # 某些环境（如被 pytest 捕获的流）不允许 reconfigure
            pass
