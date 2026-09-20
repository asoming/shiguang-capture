"""build_exe.py — PyInstaller 打包脚本（本机与 CI 共用）。

产出：dist/ShiguangCapture/（onedir 目录形态，启动快于 onefile）。
用法：python scripts/build_exe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from shiguang_capture._console import fix_console_encoding

    fix_console_encoding()   # Windows CI 控制台默认 cp1252，中文输出会炸
except ImportError:
    pass


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
        "--collect-data", "shiguang_capture",
        "--workpath", str(ROOT / "build/pyinstaller"),
        "--specpath", str(ROOT / "build"),
        "--distpath", str(ROOT / "dist"),
    ]
    if sys.platform.startswith('linux'):
        args += ['--hidden-import', 'pynput.keyboard._xorg', '--hidden-import', 'pynput.mouse._xorg']
        import os
        cursor_lib = Path(os.environ.get('SHIGUANG_XCB_CURSOR', '/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0'))
        if not cursor_lib.is_file():
            raise RuntimeError('打包需要 libxcb-cursor0；安装系统库或通过 SHIGUANG_XCB_CURSOR 指定库文件。')
        args += ['--add-binary', f'{cursor_lib}:.']
    if icon.is_file() and sys.platform == "win32":
        args += ["--icon", str(icon)]

    print("PyInstaller args:", " ".join(args))
    PyInstaller.__main__.run(args)

    exe = ROOT / "dist/ShiguangCapture/ShiguangCapture.exe"
    if sys.platform != "win32":
        exe = exe.with_suffix("")
    if not exe.exists():
        raise RuntimeError('打包没有生成可执行文件')
    import shutil
    from collect_licenses import collect
    bundle = exe.parent
    collect(bundle / 'licenses/dependencies')
    shutil.copytree(ROOT / 'licenses', bundle / 'licenses', dirs_exist_ok=True)
    for name in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, bundle / name)
    shutil.copy2(ROOT / 'docs/assets/icon-256.png', bundle / 'icon.png')
    if sys.platform.startswith('linux'):
        shutil.copy2(ROOT / 'scripts/install-linux.sh', bundle / 'install-linux.sh')
    print("OK ->", exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
