"""Build a Debian/Ubuntu installer from the verified standalone Linux bundle."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    bundle = ROOT / 'dist/ShiguangCapture'
    version = (bundle / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('A stable package version is required')
    output = ROOT / f'dist/ShiguangCapture-v{version}-Linux-amd64.deb'
    with tempfile.TemporaryDirectory(prefix='shiguang-deb-') as temporary:
        stage = Path(temporary)
        app = stage / 'opt/shiguang-capture'
        shutil.copytree(bundle, app, symlinks=True)
        (app / 'ShiguangCapture').chmod(0o755)
        control = stage / 'DEBIAN'
        control.mkdir()
        size = sum(p.stat().st_size for p in app.rglob('*') if p.is_file() and not p.is_symlink())
        (control / 'control').write_text(f'''Package: shiguang-capture
Version: {version}
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: asoming <2824691696@qq.com>
Installed-Size: {(size+1023)//1024}
Depends: libc6 (>= 2.35), libegl1, libgl1, libxkbcommon0, libxkbcommon-x11-0, libdbus-1-3, libfontconfig1, libpulse0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-xinerama0, libxcb-render-util0
Homepage: https://github.com/asoming/shiguang-capture
Description: Screen capture, recording and offline OCR for X11
 Region and manual scrolling screenshots, annotations, recording,
 local OCR and offline Chinese/English translation.
''')
        launcher = stage / 'usr/bin/shiguang-capture'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nexec /opt/shiguang-capture/ShiguangCapture "$@"\n')
        launcher.chmod(0o755)
        desktop = stage / 'usr/share/applications/shiguang-capture.desktop'
        desktop.parent.mkdir(parents=True)
        desktop.write_text('''[Desktop Entry]
Type=Application
Name=Shiguang Capture
Name[zh_CN]=拾光 Capture
Comment=Screenshot, recording and offline OCR
Exec=/usr/bin/shiguang-capture
Icon=shiguang-capture
Terminal=false
Categories=Graphics;
StartupWMClass=shiguang-capture
''')
        icon = stage / 'usr/share/icons/hicolor/256x256/apps/shiguang-capture.png'
        icon.parent.mkdir(parents=True)
        shutil.copy2(bundle / 'icon.png', icon)
        documentation = stage / 'usr/share/doc/shiguang-capture'
        documentation.mkdir(parents=True)
        shutil.copy2(bundle / 'LICENSE', documentation / 'copyright')
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z1', '--build', str(stage), str(output)], check=True)
    print(output)


if __name__ == '__main__':
    main()
