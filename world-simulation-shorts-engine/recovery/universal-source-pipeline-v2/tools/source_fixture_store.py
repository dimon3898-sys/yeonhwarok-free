"""Restore only the pinned public fixture package, with bounded safe extraction."""
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile

HERE=Path(__file__).resolve().parents[1]


def restore(destination=None):
    pin=json.loads((HERE/'fixtures/SOURCE_CATALOG_PIN.json').read_bytes())
    archive=HERE/'fixtures/SOURCE_BUNDLE.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=pin['archiveSHA256']:
        raise ValueError('SOURCE_FIXTURE_ARCHIVE_HASH_MISMATCH')
    destination=Path(destination or ('/tmp/world-engine-source-'+pin['indexSHA256'][:16]))
    if destination.exists():
        if destination.is_symlink() or destination.stat().st_uid!=os.getuid() or destination.stat().st_mode&0o077:
            raise ValueError('SOURCE_FIXTURE_CACHE_UNSAFE')
    else:destination.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('SOURCE_MANIFEST.json'))
        if len(manifest)>2000 or sum(r['bytes'] for r in manifest)>64*1024**2:
            raise ValueError('SOURCE_FIXTURE_EXTRACTION_CAPACITY')
        for row in manifest:
            relative=Path(row['path'])
            if relative.is_absolute() or '..' in relative.parts or '\\' in row['path']:
                raise ValueError('SOURCE_FIXTURE_PATH_ESCAPE')
            data=z.read(row['path'])
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                raise ValueError('SOURCE_FIXTURE_ENTRY_HASH_MISMATCH')
            target=destination/relative
            for parent in [target,*target.parents]:
                if parent.is_symlink():raise ValueError('SOURCE_FIXTURE_SYMLINK_REJECTED')
                if parent==destination:break
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if target.exists():
                if not target.is_file() or target.read_bytes()!=data:
                    raise ValueError('SOURCE_FIXTURE_EXISTING_DATA_CHANGED')
            else:
                descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as f:f.write(data)
    if hashlib.sha256((destination/'INDEX.json').read_bytes()).hexdigest()!=pin['indexSHA256']:
        raise ValueError('SOURCE_FIXTURE_INDEX_CHANGED')
    return destination,pin['indexSHA256']


if __name__=='__main__':
    root,pin=restore();print(json.dumps({'sourceRoot':str(root),'indexSHA256':pin}))
