"""Build the recording runtime against minimal, replaceable FFmpeg libraries.

Linux/macOS build prerequisite: C compiler, make, pkg-config and NASM (x86).
Build artifacts and original corresponding sources stay under --directory.
No runtime downloads or third-party codec libraries are enabled.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import shutil
import shlex

VERSION = '8.0.1'
SHA256 = '05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41'
FLAGS = [
    '--disable-everything', '--disable-autodetect', '--disable-network', '--disable-programs',
    '--disable-doc', '--disable-debug', '--enable-shared', '--disable-static', '--enable-pic',
    '--enable-encoder=mpeg4,aac', '--enable-decoder=mpeg4,aac', '--enable-muxer=matroska,mp4',
    '--enable-demuxer=matroska,mov', '--enable-protocol=file',
    '--enable-filter=abuffer,abuffersink,aformat,aresample,buffer,buffersink,format,scale',
    '--enable-parser=mpeg4video,aac', '--enable-bsf=aac_adtstoasc,extract_extradata',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path('build/media-runtime'))
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root/f'ffmpeg-{VERSION}.tar.xz'
    url = f'https://ffmpeg.org/releases/{archive.name}'
    if not archive.exists():
        urllib.request.urlretrieve(url, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('FFmpeg source checksum mismatch')
    source = root/f'ffmpeg-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as content:
            content.extractall(root, filter='data')
    prefix = root/'runtime'
    if sys.platform == 'win32':
        bash = os.environ['SHIGUANG_MSYS_BASH']
        def unix_path(path):
            return subprocess.check_output([bash, '-c', 'cygpath -u '+shlex.quote(str(path))], text=True).strip()
        compiler = shutil.which('cl')
        if compiler is None:
            raise RuntimeError('Use an x64 Visual Studio developer environment before building.')
        compiler_path = unix_path(Path(compiler).parent)
        configure = ['./configure', f'--prefix={unix_path(prefix)}', '--toolchain=msvc', *FLAGS]
        def build(command):
            # MSVC link.exe must take precedence over MSYS's unrelated link tool.
            script = 'export PATH='+shlex.quote(compiler_path)+':"$PATH"; '+shlex.join(command)
            subprocess.run([bash, '-c', script], cwd=source, check=True)
    else:
        configure = ['./configure', f'--prefix={prefix}', *FLAGS]
        def build(command):
            subprocess.run(command, cwd=source, check=True)
    build(configure)
    build(['make', '-j', str(min(4, os.cpu_count() or 2))])
    build(['make', 'install'])
    environment = os.environ.copy()
    environment['PKG_CONFIG_PATH'] = str(prefix/'lib/pkgconfig')
    library_var = 'DYLD_LIBRARY_PATH' if sys.platform == 'darwin' else 'LD_LIBRARY_PATH'
    environment[library_var] = str(prefix/'lib') + os.pathsep + environment.get(library_var, '')
    if sys.platform == 'win32':
        environment['INCLUDE'] = str(prefix/'include')+';'+environment.get('INCLUDE', '')
        environment['LIB'] = str(prefix/'lib')+';'+environment.get('LIB', '')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'Cython>=3.1,<4'], check=True)
    # --no-cache-dir avoids reusing a wheel from a different codec build.
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', 'av==16.1.0', '--no-binary=av',
                    '--no-build-isolation', '--no-deps', '--no-cache-dir', '-w', str(root/'wheels')],
                   env=environment, check=True)
    manifest = {'ffmpeg_version': VERSION, 'source_url': url, 'source_sha256': SHA256,
                'configure': configure, 'pyav_version': '16.1.0', 'third_party_codecs': []}
    (root/'build-info.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(f'Install the wheel from {root / "wheels"}; build with {library_var}={prefix / "lib"}')


if __name__ == '__main__':
    main()
