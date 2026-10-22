"""Build a small, explicit public review bundle, excluding private runs and video copies."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE=Path(__file__).resolve().parents[1]

def main():
    output=HERE/'review-package/WORLD_ENGINE_G2_G3_REVIEW.zip'
    if output.exists():raise ValueError('REVIEW_PACKAGE_REFUSE_OVERWRITE')
    rows=[]
    suffixes={'.py','.mjs','.json','.csv','.md','.geojson'}
    thumbnails={'DEMO_ACTUAL_CONTACT_SHEET.png','DEMO_ABLATION_COMPARISON.png','DEMO_ENCODED_TEMPORAL_REVIEW.png'}
    for file in sorted(HERE.rglob('*')):
        if not file.is_file() or file.is_symlink():continue
        rel=file.relative_to(HERE);parts=rel.parts
        if any(v in parts for v in ('captures','__pycache__','review-package')):continue
        if file.name=='DOWNLOAD_VERIFICATION.json':continue
        allowed=(parts[0]=='public-review' and file.name in thumbnails
            or parts[0]=='source-review' and file.suffix in {'.png','.json'}
            or parts[0]=='fixtures' and file.name=='SOURCE_BUNDLE.zip'
            or parts[0]!='public-review' and file.suffix in suffixes)
        if allowed:
            raw=file.read_bytes();rows.append((rel.as_posix(),raw))
    manifest=[{'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in rows]
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for name,raw in rows:target.writestr(name,raw)
        target.writestr('REVIEW_MANIFEST.json',json.dumps({'schema':'WORLD_ENGINE_G2_G3_PUBLIC_REVIEW_BUNDLE_V2',
            'qualification':'NEW_REVIEW_BUNDLE_NOT_ORIGINAL_ASTRA_UPLOAD','videoIncluded':False,
            'privateRunsIncluded':False,'entries':manifest},indent=2))
    if output.stat().st_size>32*1024**2:raise ValueError('REVIEW_PACKAGE_MOBILE_SIZE_LIMIT')
    with zipfile.ZipFile(output) as check:
        if check.testzip():raise ValueError('REVIEW_PACKAGE_CRC_FAILURE')
        for row in manifest:
            if hashlib.sha256(check.read(row['path'])).hexdigest()!=row['sha256']:
                raise ValueError('REVIEW_PACKAGE_READBACK_HASH_FAILURE')
    print(json.dumps({'file':str(output),'bytes':output.stat().st_size,'entries':len(rows),
        'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))

if __name__=='__main__':main()
