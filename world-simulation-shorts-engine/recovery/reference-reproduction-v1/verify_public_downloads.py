#!/usr/bin/env python3
"""GET immutable review URLs and verify original, Git, and downloaded bytes."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREFIX = 'world-simulation-shorts-engine/recovery/reference-reproduction-v1/public-review/'

def digest(value):
    return hashlib.sha256(value).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--media-commit', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.media_commit):
        raise SystemExit('Full saved media commit required')
    entries = json.loads((HERE/'evidence/PUBLIC_REVIEW_FILES.json').read_text())['files']
    names = [row['file'] for row in entries]
    if len(names) != len(set(names)) or sorted(names) != sorted(p.name for p in (HERE/'public-review').iterdir()):
        raise SystemExit('Exact public allowlist required')
    expected = {'WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4', 'SCENE_PLAN.json', 'SHA256SUMS',
                'COMPARE_01_START.png', 'COMPARE_02_ADVANCE.png', 'COMPARE_03_TRACKING.png',
                'COMPARE_04_CONTINUOUS_CONTROL.png', 'COMPARE_05_END.png'}
    if set(names) != expected:
        raise SystemExit('Review must contain only authorized media/comparison/scene/SHA files')
    cache = Path('/workspace/.onboarding/reference-reproduction-downloads')/args.media_commit
    cache.mkdir(parents=True, exist_ok=True)
    receipt = {'schema':'REFERENCE_PUBLIC_REVIEW_DOWNLOAD_VERIFICATION_V1','status':'IN_PROGRESS',
               'mediaCommit':args.media_commit,'method':'ACTUAL_HTTPS_GET_WITH_TLS_VERIFICATION',
               'files':[],'requiredTempOnlyFiles':0,'userVideoReview':'REQUIRED','finalPromotion':False}
    for name in sorted(names):
        original = (HERE/'public-review'/name).read_bytes()
        saved = subprocess.check_output(['git','show',args.media_commit+':'+PREFIX+name],cwd=REPO)
        if original != saved:
            raise RuntimeError('ORIGINAL_GIT_BYTES_MISMATCH '+name)
        url = 'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+args.media_commit+'/'+PREFIX+quote(name)
        output = cache/name
        result = subprocess.run(['curl','--silent','--show-error','--fail','--location',
                                 '--proto','=https','--proto-redir','=https','--tlsv1.2',
                                 '--connect-timeout','20','--max-time','60','--output',str(output),
                                 '--write-out','%{http_code}\n%{url_effective}\n',url],capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError('DOWNLOAD_FAILED '+name+' '+result.stderr[:400])
        status, effective = result.stdout.splitlines()[:2]
        downloaded = output.read_bytes()
        if status != '200' or downloaded != original:
            raise RuntimeError('HTTP_OR_SHA_MISMATCH '+name)
        row = {'file':name,'url':url,'effectiveUrl':effective,'httpStatus':200,'bytes':len(original),
               'sha256':digest(original),'originalSha256':digest(original),'gitSha256':digest(saved),
               'downloadedSha256':digest(downloaded),'byteEquality':True}
        receipt['files'].append(row)
        (HERE/'evidence/PUBLIC_DOWNLOADS.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({'file':name,'httpStatus':200,'sha256':row['sha256'],'equal':True}),flush=True)
    receipt['status']='PASS'
    (HERE/'evidence/PUBLIC_DOWNLOADS.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'PASS','verifiedDownloads':len(receipt['files'])}),flush=True)

if __name__ == '__main__':
    main()
