"""Package a new, already validated neutral fixture tree; never change its inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def sha(data):
    return hashlib.sha256(data).hexdigest()

def package(root, archive, pin):
    root=root.resolve()
    if archive.exists() or pin.exists():
        raise ValueError('SOURCE_PACKAGE_OUTPUT_ALREADY_EXISTS')
    files=[]
    for file in sorted(root.rglob('*')):
        if file.is_symlink():raise ValueError('SOURCE_PACKAGE_SYMLINK_REJECTED')
        if file.is_file():
            raw=file.read_bytes();json.loads(raw)
            files.append((file.relative_to(root).as_posix(),raw))
    if len(files)>2000 or sum(len(raw) for _,raw in files)>64*1024**2:
        raise ValueError('SOURCE_PACKAGE_CAPACITY')
    manifest=[{'path':name,'sha256':sha(raw),'bytes':len(raw)} for name,raw in files]
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for name,raw in files:
            info=zipfile.ZipInfo(name,date_time=(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100600<<16;target.writestr(info,raw)
        info=zipfile.ZipInfo('SOURCE_MANIFEST.json',date_time=(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100600<<16
        target.writestr(info,json.dumps(manifest,sort_keys=True,separators=(',',':')).encode())
    data=archive.read_bytes()
    result={'schema':'WORLD_ENGINE_SOURCE_FIXTURE_PIN_V2','archive':'SOURCE_BUNDLE.zip',
        'archiveSHA256':sha(data),'bytes':len(data),'files':len(files),
        'indexSHA256':sha((root/'INDEX.json').read_bytes()),'requiredTempOnly':0,
        'classification':'NEUTRAL_SOURCE_PACKAGE_NOT_GPU_UPLOAD_OR_HISTORICAL_QUALIFICATION'}
    pin.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--pin',type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(a.root,a.archive,a.pin)))
