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
    import os
    media = Path(os.environ.get('SHIGUANG_MEDIA_BUILD', ROOT/'build/media-runtime'))
    dll_directory = None
    if sys.platform == 'win32':
        dll_directory = os.add_dll_directory(str(media/'runtime/bin'))
        os.environ['PATH'] = str(media/'runtime/bin')+os.pathsep+os.environ['PATH']
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
        "--collect-all", "av",
        "--collect-all", "soundcard",
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
    if sys.platform == "win32":
        if icon.is_file():
            args += ["--icon", str(icon)]
        for library in (media/'runtime/bin').glob('*.dll'):
            args += ['--add-binary', f'{library}:.']
    if sys.platform == 'darwin':
        args += ['--osx-bundle-identifier', 'io.github.asoming.shiguang-capture']

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
    from shiguang_capture import __version__
    (bundle/'VERSION').write_text(__version__+'\n', encoding='ascii')
    # PDF decoding and the virtual keyboard are not product features. Do not ship
    # their optional Qt modules or plugins (which have separate licensing).
    package_roots = [bundle]
    if sys.platform == 'darwin':
        package_roots.append(ROOT/'dist/ShiguangCapture.app/Contents')
    unused_patterns = (
        '**/libqpdf.so', '**/libqpdf.dylib', '**/qpdf.dll',
        '**/libqtvirtualkeyboardplugin.so', '**/libqtvirtualkeyboardplugin.dylib',
        '**/qtvirtualkeyboardplugin.dll', '**/libQt6Pdf.so*', '**/Qt6Pdf*.dll',
        '**/QtPdf.framework', '**/QtPdfWidgets.framework',
        '**/libQt6VirtualKeyboard*.so*', '**/Qt6VirtualKeyboard*.dll', '**/QtVirtualKeyboard.framework',
    )
    for package in package_roots:
        for pattern in unused_patterns:
            for unused in package.glob(pattern):
                if unused.is_symlink() or not unused.is_dir():
                    unused.unlink()
                else:
                    shutil.rmtree(unused)
    collect(bundle / 'licenses/dependencies')
    import os
    media = Path(os.environ.get('SHIGUANG_MEDIA_BUILD', ROOT/'build/media-runtime'))
    if not (media/'ffmpeg-8.0.1.tar.xz').is_file() or not (media/'build-info.json').is_file():
        raise RuntimeError('先运行 scripts/build_media_runtime.py，并通过 SHIGUANG_MEDIA_BUILD 指定构建目录。')
    media_notices = bundle/'licenses/recording-runtime'
    media_notices.mkdir(parents=True, exist_ok=True)
    for source in (media/'ffmpeg-8.0.1.tar.xz', media/'build-info.json',
                   media/'ffmpeg-8.0.1/COPYING.LGPLv2.1', media/'ffmpeg-8.0.1/LICENSE.md'):
        shutil.copy2(source, media_notices/source.name)
    shutil.copy2(ROOT/'scripts/build_media_runtime.py', media_notices/'build_media_runtime.py')
    shutil.copytree(ROOT / 'licenses', bundle / 'licenses', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'validation', bundle / 'validation', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'requirements-linux.lock', bundle / 'requirements-linux.lock')
    for name in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, bundle / name)
    shutil.copy2(ROOT / 'docs/assets/icon-256.png', bundle / 'icon.png')
    if sys.platform.startswith('linux'):
        shutil.copy2(ROOT / 'scripts/install-linux.sh', bundle / 'install-linux.sh')
    if sys.platform == 'darwin':
        import plistlib
        import subprocess
        application = ROOT/'dist/ShiguangCapture.app'
        plist_path = application/'Contents/Info.plist'
        with plist_path.open('rb') as source:
            info = plistlib.load(source)
        info['CFBundleDisplayName'] = '拾光 Capture'
        info['NSMicrophoneUsageDescription'] = '仅在你选择麦克风录屏时采集声音，并保存到你选择的本地视频文件。'
        with plist_path.open('wb') as destination:
            plistlib.dump(info, destination)
        resources = ROOT/'dist/ShiguangCapture.app/Contents/Resources'
        for directory in ('licenses', 'validation'):
            shutil.copytree(bundle/directory, resources/directory, dirs_exist_ok=True)
        for name in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md', 'VERSION'):
            shutil.copy2(bundle/name, resources/name)
        # Adding notices/metadata changes the bundle seal. Re-sign the finished
        # preview locally; this is ad-hoc signing, not Developer ID/notarization.
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(application)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(application)], check=True)
    print("OK ->", exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
