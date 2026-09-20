"""app_entry.py — PyInstaller 打包入口。

直接以脚本方式启动应用（等价 python -m shiguang_capture）。
"""
import multiprocessing
multiprocessing.freeze_support()
from shiguang_capture.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
