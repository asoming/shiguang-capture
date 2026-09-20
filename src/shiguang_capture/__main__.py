"""__main__.py — python -m shiguang_capture 入口。"""
from __future__ import annotations

import argparse
import sys

from . import __app_name__, __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shiguang-capture", description=f"{__app_name__} — 屏幕信息捕获与再利用工具")
    p.add_argument("--version", action="store_true", help="显示版本号并退出")
    p.add_argument("--check", action="store_true", help="仅做环境自检（不启动 GUI）")
    p.add_argument("--self-test", action="store_true", help="运行安装包离屏自测（使用合成图片）")
    p.add_argument("--desktop-test", action="store_true", help="使用合成窗口实测当前 X11 桌面")
    p.add_argument('--recording-self-test', action='store_true', help='使用合成画面与音调验证安装包编码')
    p.add_argument('--recording-desktop-test', metavar='OUTPUT', help='录制合成窗口并写入桌面验收报告')
    p.add_argument('--translation-self-test', action='store_true', help='验证随包中英双向离线翻译')
    return p


def main() -> int:
    import multiprocessing
    multiprocessing.freeze_support()
    from ._console import fix_console_encoding

    fix_console_encoding()   # Windows 控制台默认非 UTF-8，中文输出会炸
    args = build_parser().parse_args()
    if args.version:
        print(f"{__app_name__} v{__version__}")
        return 0
    if args.translation_self_test:
        from .translation_selftest import run
        return run()
    if args.recording_self_test:
        from .recording.selftest import run
        return run()
    if args.recording_desktop_test:
        from .recording.acceptance import main
        main(args.recording_desktop_test)
        return 0
    if args.desktop_test:
        from .desktoptest import main as desktop_test
        desktop_test()
        return 0
    if args.self_test:
        from .selftest import run
        return run()
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
