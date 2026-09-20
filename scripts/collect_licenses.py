"""Collect installed distribution notices into the standalone bundle."""
from importlib import metadata
from pathlib import Path
import json
import shutil
import subprocess
import sysconfig


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
    python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, destination/'Python-LICENSE.txt')
    # Native desktop libraries pulled in by Qt also need their distribution notices.
    if __import__('sys').platform.startswith('linux'):
        import ast
        native = destination/'system'
        if native.exists(): shutil.rmtree(native)
        native.mkdir(exist_ok=True)
        package_names=set()
        toc = Path('build/pyinstaller/ShiguangCapture/COLLECT-00.toc')
        entries_toc = ast.literal_eval(toc.read_text())[0] if toc.is_file() else []
        sources = sorted({source for name, source, kind in entries_toc
                          if kind == 'BINARY' and source.startswith(('/usr/lib/', '/lib/'))})
        # usr-merge aliases may differ from the paths recorded by dpkg.
        aliases=[]
        for source in sources:
            alternate = '/usr'+source if source.startswith('/lib/') else source.removeprefix('/usr')
            if Path(alternate).is_file() and Path(alternate).samefile(source): aliases.append(alternate)
        sources = sorted(set(sources+aliases))
        query=subprocess.run(['dpkg-query','-S',*sources],capture_output=True,text=True) if sources else None
        for line in query.stdout.splitlines() if query else []:
            owner=line.split(': ',1)[0]
            if not owner:continue
            package_names.add(owner)
            notice=Path('/usr/share/doc')/owner.split(':')[0]/'copyright'
            if notice.is_file():shutil.copy2(notice,native/(owner.replace(':','_')+'-copyright.txt'))
        common=Path('/usr/share/common-licenses')
        if common.is_dir():shutil.copytree(common,native/'common-licenses',dirs_exist_ok=True)
        if package_names:
            versions=subprocess.run(['dpkg-query','-W','-f=${binary:Package} ${Version}\\n',*sorted(package_names)],capture_output=True,text=True)
            (native/'versions.txt').write_text(versions.stdout)
    (destination/'dependencies.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':collect('dist/ShiguangCapture/licenses/dependencies')
