"""__main__.py — python -m shiguang_capture 入口。"""
from __future__ import annotations

import argparse
import sys

from . import __app_name__, __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shiguang-capture", description=f"{__app_name__} — 屏幕信息捕获与再利用工具")
    p.add_argument("--version", action="store_true", help="显示版本号并退出")
    p.add_argument("--check", action="store_true", help="仅做环境自检（不启动 GUI）")
    return p


def main() -> int:
    from ._console import fix_console_encoding

    fix_console_encoding()   # Windows 控制台默认非 UTF-8，中文输出会炸
    args = build_parser().parse_args()
    if args.version:
        print(f"{__app_name__} v{__version__}")
        return 0
    if args.check:
        from .config import AppConfig
        from .geometry import Rect
        from .naming import shot_name
        from datetime import datetime

        cfg = AppConfig.load()
        _ = Rect.from_corners(0, 0, 10, 10).is_valid
        _ = shot_name(datetime.now(), 1)
        print(f"self-check OK · config={cfg.image_format} ocr={cfg.ocr_engine}")
        return 0
    from .app import main as gui_main

    return gui_main(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
