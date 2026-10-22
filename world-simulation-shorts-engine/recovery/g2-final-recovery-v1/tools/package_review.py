"""Deterministic public review package; excludes private jobs and old caches."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

HERE=Path(__file__).resolve().parents[1]
EXCLUDE={'SHA256SUMS','public-review/SHA256SUMS','reports/FILE_MANIFEST.csv',
    'reports/PACKAGE_MANIFEST.json','reports/DOWNLOAD_VERIFICATION.json',
    'reports/SESSION_CHECKPOINT.json','reports/PROTECTION_DELIVERY.json'}
ZIP_PUBLIC={'G2_FINAL_DEMO_6S.mp4','BEFORE_AFTER_CONTACT_SHEET.png',
    'ACTUAL_REGIONS_CONTACT_SHEET.png','FLAGGED_F133_ACTUAL_CROPS.png','SOURCE_NATIVE_OVERLAP.png'}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    gates=json.loads((HERE/'reports/GATES.json').read_text())
    assert gates['g2Status']=='TECHNICAL_PASS' and gates['qualityStatus']=='QUALITY_REVIEW_REQUIRED'
    assert gates['historicalG3']=='BLOCKED' and gates['userApproved'] is False
    entries=[]
    for file in sorted(HERE.rglob('*')):
        if not file.is_file() or file.is_symlink() or '__pycache__' in file.parts:continue
        name=file.relative_to(HERE).as_posix()
        if name in EXCLUDE or name.split('/')[0] in {'captures','review-package'}:continue
        entries.append((name,file))
    rows=[{'path':name,'bytes':file.stat().st_size,'sha256':sha(file.read_bytes())} for name,file in entries]
    buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=['path','bytes','sha256']);writer.writeheader();writer.writerows(rows)
    (HERE/'reports/FILE_MANIFEST.csv').write_text(buf.getvalue())
    selected=[(name,file) for name,file in entries if not name.startswith('assets/')
              and (not name.startswith('public-review/') or file.name in ZIP_PUBLIC)]
    selected.append(('reports/FILE_MANIFEST.csv',HERE/'reports/FILE_MANIFEST.csv'))
    manifest={'schema':'WORLD_ENGINE_G2_FINAL_REVIEW_PACKAGE_V1',
        'g2':'TECHNICAL_PASS','quality':'QUALITY_REVIEW_REQUIRED','g3':'BLOCKED',
        'privateJobsOrCredentialsIncluded':False,'oldSourceOrCacheCopied':False,
        'separatelyPersistedAssetsInRepository':[r for r in rows if r['path'].startswith('assets/')],
        'separateFullResolutionCheckpointsAndOverviews':True,
        'files':[{'path':name,'bytes':file.stat().st_size,'sha256':sha(file.read_bytes())} for name,file in selected]}
    raw=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
    (HERE/'reports/PACKAGE_MANIFEST.json').write_bytes(raw)
    archive=HERE/'review-package/G2_FINAL_RECOVERY_REVIEW.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,file in selected:
            info=zipfile.ZipInfo(name,date_time=(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,file.read_bytes())
        z.writestr('PACKAGE_MANIFEST.json',raw)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in manifest['files']:assert sha(z.read(row['path']))==row['sha256']
        assert not any(n.startswith('/') or '..' in Path(n).parts for n in z.namelist())
    assert archive.stat().st_size<32*1024**2
    public=[(f.name,f) for f in sorted((HERE/'public-review').iterdir()) if f.suffix in {'.mp4','.png'}]
    (HERE/'public-review/SHA256SUMS').write_text(''.join(sha(f.read_bytes())+'  '+n+'\n' for n,f in public))
    outputs=[('public-review/'+n,f) for n,f in public]
    outputs.append(('review-package/G2_FINAL_RECOVERY_REVIEW.zip',archive))
    outputs += [(name,HERE/name) for name in ['README.md','ROOT_CAUSE_REPORT.md','LAYOUT_FIX_REPORT.md',
        'REGRESSION_TEST_REPORT.md','FRAME_AUDIT.md','G2_GATE_DECISION.md','reports/GATES.json',
        'reports/PROTECTION_FINAL.json','reports/FILE_MANIFEST.csv','reports/PACKAGE_MANIFEST.json']]
    (HERE/'SHA256SUMS').write_text(''.join(sha(f.read_bytes())+'  '+n+'\n' for n,f in outputs))
    print(json.dumps({'status':'PASS','zipBytes':archive.stat().st_size,
                     'zipSHA256':sha(archive.read_bytes()),'zipFiles':len(selected)+1,'downloadFiles':len(outputs)+1}))

if __name__=='__main__':main()
