"""naming.py — 截图文件命名体系（纯逻辑）。

录屏模块共享同一套命名（PRD 6.2：录屏与截图共享文件命名体系）。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

PATTERN = "SG_{ts}_{seq:04d}.{ext}"
_TS_RE = re.compile(r"^SG_(\d{8}_\d{6})_(\d{4})\.(\w+)$")


def shot_name(now: datetime, seq: int, ext: str = "png") -> str:
    """生成截图文件名，如 SG_20260919_120552_0007.png。"""
    if seq < 0 or seq > 9999:
        raise ValueError("seq 超出 0000-9999 范围")
    ext = ext.lstrip(".").lower()
    if not ext.isalnum():
        raise ValueError(f"非法扩展名: {ext!r}")
    return PATTERN.format(ts=now.strftime("%Y%m%d_%H%M%S"), seq=seq, ext=ext)


def recording_name(now: datetime, seq: int, ext: str = "mp4") -> str:
    """录屏文件复用同一命名体系，扩展名不同。"""
    return shot_name(now, seq, ext)


def next_seq(directory: Path, now: datetime) -> int:
    """扫描目录，返回当日下一个可用序号（跨日清零，同日递增）。"""
    today = now.strftime("%Y%m%d")
    max_seq = 0
    if directory.is_dir():
        for f in directory.iterdir():
            m = _TS_RE.match(f.name)
            if m and m.group(1).startswith(today):
                max_seq = max(max_seq, int(m.group(2)))
    return max_seq + 1
