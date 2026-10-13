#!/usr/bin/env python3
"""GET pinned original review bytes; never transcode/recreate/publicize source data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--commit',required=True)
    args=parser.parse_args()
    if len(args.commit)!=40 or any(c not in '0123456789abcdef' for c in args.commit):
        raise SystemExit('Full immutable media commit required')
    root=Path(__file__).resolve().parent
    repo=root.parents[2]
    public=root/'public-review'
    files=sorted(p for p in public.iterdir() if p.is_file())
    assert len(files)==9
    assert {p.suffix for p in files}=={'.png','.mp4',''}
    assert {p.name for p in files if not p.suffix}=={'SHA256SUMS'}
    base='https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+args.commit+'/'+public.relative_to(repo).as_posix()+'/'
    with tempfile.TemporaryDirectory(prefix='v3-review-download-') as tmp:
        tmp=Path(tmp)
        def check(source):
            original=source.read_bytes()
            relative=source.relative_to(repo).as_posix()
            committed=subprocess.check_output(['git','show',args.commit+':'+relative],cwd=repo)
            assert committed==original,relative
            url=base+source.name
            with urllib.request.urlopen(url,timeout=60) as response:
                status=response.status
                downloaded=response.read()
            assert status==200,url
            actual=hashlib.sha256(downloaded).hexdigest()
            expected=hashlib.sha256(original).hexdigest()
            assert actual==expected and downloaded==original,url
            (tmp/source.name).write_bytes(downloaded)
            return {'file':source.name,'url':url,'http_status':status,'sha256':expected,
                    'download_sha256':actual,'bytes':len(downloaded),'download_matches_original_and_commit':True}
        with ThreadPoolExecutor(max_workers=3) as executor:
            rows=list(executor.map(check,files))
        by_name={r['file']:r for r in rows}
        sums=(tmp/'SHA256SUMS').read_text().splitlines()
        assert len(sums)==8
        for line in sums:
            digest,name=line.split('  ',1)
            assert by_name[name]['sha256']==digest
    report={'schema':1,'status':'PASS','mediaCommit':args.commit,'files':rows,'verifiedFiles':9,
            'publicReviewAllowedOnly':['MP4','PNG','SHA256SUMS'],'publicReviewOtherFiles':0,
            'originalMp4Reencoded':False,'downloadCopiesTemporaryOnlyNotRuntimeInputs':True}
    output=root/'evidence/HTTP_DOWNLOAD_VERIFY.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','http200':len(rows),'matchingOriginalSha256':len(rows),'mediaCommit':args.commit}))

if __name__=='__main__':
    main()
