"""Collect installed distribution notices into the standalone bundle."""
from importlib import metadata
from pathlib import Path
import json
import shutil


def collect(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    entries=[]
    for dist in metadata.distributions():
        if not str(dist.locate_file('')).startswith(str(Path(__import__('sys').prefix))): continue
        name=dist.metadata.get('Name','unknown')
        if name.lower()=='shiguang-capture' or not any(str(f).endswith('METADATA') for f in dist.files or []):continue
        directory=destination/name;directory.mkdir(exist_ok=True)
        license_files=[]
        for item in dist.files or []:
            parts=str(item).lower()
            if any(word in Path(parts).name for word in ('license','copying','notice')) and '.py' not in Path(parts).suffix:
                source=Path(dist.locate_file(item))
                if source.is_file():
                    target=directory/str(item).replace('/','__').replace('..','_')
                    shutil.copyfile(source,target);license_files.append(target.name)
        (directory/'METADATA.txt').write_text(dist.read_text('METADATA') or '',encoding='utf-8')
        entries.append({'name':name,'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License','See package metadata'),'notices':license_files})
    (destination/'dependencies.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':collect('dist/ShiguangCapture/licenses/dependencies')
