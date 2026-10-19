"""Whitelist public reports, contracts and safe proof; exclude source assets/state."""
from pathlib import Path
import hashlib
import io
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()

def package():
    handoff=ROOT/'handoff';handoff.mkdir(exist_ok=True)
    archive=handoff/'WORLD_ENGINE_5S_RENDER_PATH_RECONCILIATION.zip'
    if archive.exists():raise RuntimeError('EXISTING_HANDOFF_PRESERVED')
    files={}
    for folder in ('reports','proof'):
        for file in sorted((ROOT/folder).iterdir()):
            if file.is_file() and file.suffix in {'.json','.csv','.md'}:
                if file.is_symlink():raise RuntimeError('PUBLIC_REGULAR_REPORT_REQUIRED')
                files[file.relative_to(ROOT).as_posix()]=file.read_bytes()
    for name in ('RESULT.md','README.md','RECONCILIATION_FILES.json'):
        files[name]=(ROOT/name).read_bytes()
    parent=ROOT.parent/'universal-overnight-v3'
    files['contracts/EXISTING_5S_PROMPT.json']=(parent/'fixtures/STUDIO_OVERNIGHT_5S_PROMPT.json').read_bytes()
    for name in ('STUDIO_OVERNIGHT_PROMPT.schema.json','VISUAL_EXTENSIONS.schema.json'):
        files['contracts/'+name]=(parent/name).read_bytes()
    run=ROOT/'runs/39317457661-1'
    for name in ('IMAGE_PROOF.json','OLD_CAPTURE_COMPATIBILITY_IMAGE_PROOF.json'):
        files['image/'+name]=(run/name).read_bytes()
    files['SHA256SUMS']=''.join(sha(raw)+'  '+name+'\n' for name,raw in sorted(files.items())).encode()
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for name,raw in sorted(files.items()):output.writestr(name,raw)
    with zipfile.ZipFile(archive) as checked:
        assert checked.testzip() is None
        assert len(checked.namelist())==len(files)
        for line in checked.read('SHA256SUMS').decode().splitlines():
            expected,name=line.split('  ',1);assert sha(checked.read(name))==expected
    (handoff/'SHA256SUMS').write_text(sha(archive.read_bytes())+'  '+archive.name+'\n')
    return {'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes()),
            'members':len(files),'internalSHA256Verified':True,'rawAssetsPrivateStateSecretsIncluded':False}

if __name__=='__main__':print(json.dumps(package()))
