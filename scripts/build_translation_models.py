"""Download pinned, verified OPUS-MT models for offline bilingual packages."""
from pathlib import Path
import hashlib
import json
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    'en_zh': '433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab',
    'zh_en': '62e7af5a3a48b530e47b7b3e5c78c2de79073ecd815750d2bf3ab35b4a67da2d',
}


def main():
    cache = ROOT/'build/translation-models'
    cache.mkdir(parents=True, exist_ok=True)
    target = ROOT/'src/shiguang_capture/translation_data'
    manifest = []
    for direction, digest in MODELS.items():
        filename = f'translate-{direction}-1_9.argosmodel'
        url = f'https://argos-net.com/v1/{filename}'
        archive = cache/filename
        if not archive.exists():
            partial = archive.with_suffix('.download')
            with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output)
            partial.replace(archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Model checksum mismatch: {filename}')
        with zipfile.ZipFile(archive) as package:
            prefix = f'translate-{direction}-1_9/'
            for name in package.namelist():
                if not name.startswith(prefix):
                    raise ValueError('Unexpected model archive path')
                relative = Path(name[len(prefix):])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Unsafe model archive path')
                # CTranslate2 handles inference directly; no Stanza/Torch data.
                if name.endswith('/') or not (relative.parts[0] == 'model' or relative.name in ('sentencepiece.model', 'README.md', 'metadata.json')):
                    continue
                destination = target/direction/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(package.read(name))
        manifest.append({'direction': direction, 'version': '1.9', 'url': url, 'sha256': digest,
                         'license': 'CC-BY-4.0', 'authors': 'Jörg Tiedemann and Santhosh Thottingal',
                         'modifications': 'Unmodified inference weights; omitted unused Stanza sentence splitter.'})
    (target/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Verified offline translation models:', target)


if __name__ == '__main__':
    main()
