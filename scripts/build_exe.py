"""build_exe.py — PyInstaller 打包脚本（本机与 CI 共用）。

产出：dist/ShiguangCapture/（onedir 目录形态，启动快于 onefile）。
用法：python scripts/build_exe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        import PyInstaller.__main__
    except ImportError:
        print("需要 pyinstaller：pip install pyinstaller")
        return 1

    icon = ROOT / "docs/assets/icon.ico"
    args = [
        str(ROOT / "scripts/app_entry.py"),
        "--name", "ShiguangCapture",
        "--windowed",               # 无控制台窗口（托盘应用）
        "--onedir",                 # 目录形态：冷启动显著快于 onefile（PRD 秒开约束）
        "--noconfirm",
        "--clean",
        "--paths", str(ROOT / "src"),
        "--collect-all", "rapidocr_onnxruntime",   # 模型与配置随包分发
        "--collect-all", "onnxruntime",
        "--collect-all", "cv2",
        "--workpath", str(ROOT / "build/pyinstaller"),
        "--specpath", str(ROOT / "build"),
        "--distpath", str(ROOT / "dist"),
    ]
    if icon.is_file() and sys.platform == "win32":
        args += ["--icon", str(icon)]

    print("PyInstaller args:", " ".join(args))
    PyInstaller.__main__.run(args)

    exe = ROOT / "dist/ShiguangCapture/ShiguangCapture.exe"
    if sys.platform != "win32":
        exe = exe.with_suffix("")
    print("OK ->", exe if exe.exists() else "(见上方输出)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
