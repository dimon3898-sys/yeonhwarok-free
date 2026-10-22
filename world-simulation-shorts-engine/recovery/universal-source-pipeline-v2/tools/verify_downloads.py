"""GET immutable public artifacts and compare downloaded bytes, without credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError

HERE=Path(__file__).resolve().parents[1]
PREFIX='world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/'

def verify(commit):
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('DOWNLOAD_FIXED_COMMIT_REQUIRED')
    entries=[]
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);file=HERE/name
        if not file.resolve().is_relative_to(HERE) or file.is_symlink():
            raise ValueError('DOWNLOAD_LOCAL_SCOPE_REJECTED')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('DOWNLOAD_LOCAL_MANIFEST_MISMATCH')
        entries.append((name,digest))
    entries.append(('SHA256SUMS',hashlib.sha256((HERE/'SHA256SUMS').read_bytes()).hexdigest()))
    base='https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+commit+'/'+PREFIX
    def get(entry):
        name,expected=entry;url=base+quote(name,safe='/')
        for attempt in range(2):
            try:
                request=Request(url,headers={'User-Agent':'WORLD-ENGINE-public-integrity-review/2'})
                with urlopen(request,timeout=45) as response:
                    if response.status!=200 or urlsplit(response.geturl()).hostname!='raw.githubusercontent.com':
                        raise ValueError('DOWNLOAD_HTTP_OR_DESTINATION_MISMATCH')
                    digest=hashlib.sha256();count=0
                    while chunk:=response.read(1024*1024):digest.update(chunk);count+=len(chunk)
                actual=digest.hexdigest();match=actual==expected and count==(HERE/name).stat().st_size
                row={'path':name,'url':url,'httpStatus':200,'bytes':count,
                    'sourceSHA256':expected,'downloadSHA256':actual,'shaMatch':match}
                if not match:raise ValueError('DOWNLOAD_HASH_OR_LENGTH_MISMATCH')
                print(json.dumps({'path':name,'httpStatus':200,'shaMatch':True}),flush=True)
                return row
            except HTTPError as error:
                if error.code!=404 or attempt:raise
                time.sleep(2) # New immutable Git objects can briefly propagate.
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(get,entries))
    report={'schema':'WORLD_ENGINE_PUBLIC_DOWNLOAD_VERIFICATION_V2','artifactCommit':commit,
        'verifiedAtUTC':datetime.now(timezone.utc).isoformat(),'status':'PASS','filesVerified':len(results),
        'allHTTP200':True,'allDownloadedSHA256Match':True,'authenticatedRequestsUsed':False,
        'physicalMobilePlaybackVerified':False,'files':results}
    (HERE/'reports/DOWNLOAD_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True)
    report=verify(parser.parse_args().commit)
    print(json.dumps({'status':report['status'],'filesVerified':report['filesVerified']}))
