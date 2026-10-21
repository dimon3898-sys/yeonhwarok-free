"""Unauthenticated HTTPS GET + streamed hash of each immutable public artifact."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'public-review'
commit=sys.argv[1]
if not re.fullmatch('[0-9a-f]{40}',commit):
    raise ValueError('IMMUTABLE_ARTIFACT_COMMIT_REQUIRED')
base='https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+commit+'/world-simulation-shorts-engine/recovery/astra-event-director-v2/public-review/'
entries=[]
for line in (PUBLIC/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    if not re.fullmatch('[0-9a-f]{64}',digest) or Path(name).name!=name:
        raise ValueError('SAFE_PUBLIC_DOWNLOAD_MANIFEST_REQUIRED')
    entries.append((name,digest))
entries.append(('SHA256SUMS',hashlib.sha256((PUBLIC/'SHA256SUMS').read_bytes()).hexdigest()))


def verify(entry):
    name,expected=entry
    for attempt in range(2):
        try:
            request=urllib.request.Request(base+name,headers={'User-Agent':'WORLD-ENGINE-Public-Review-Verifier/2'})
            with urllib.request.urlopen(request,timeout=60) as response:
                if response.status!=200:
                    raise ValueError('PUBLIC_DOWNLOAD_HTTP_200_REQUIRED')
                actual=hashlib.sha256();size=0
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    size+=len(chunk);actual.update(chunk)
                digest=actual.hexdigest()
            if digest!=expected:
                raise ValueError('PUBLIC_DOWNLOAD_SHA_MISMATCH')
            return {'file':name,'url':base+name,'httpStatus':200,'expectedSHA256':expected,
                'downloadSHA256':digest,'bytes':size,'shaMatch':True,'status':'PASS','authenticationUsed':False}
        except urllib.error.HTTPError as error:
            if attempt==0 and error.code in {404,429,502,503,504}:
                time.sleep(4);continue
            return {'file':name,'url':base+name,'status':'FAIL','httpStatus':error.code,'shaMatch':False}
        except Exception as error:
            return {'file':name,'url':base+name,'status':'FAIL','error':type(error).__name__,'shaMatch':False}


with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(verify,entries))
report={'schema':'WORLD_ENGINE_ASTRA_V2_PUBLIC_DOWNLOAD_VERIFICATION_V1',
    'artifactCommit':commit,'status':'PASS'if all(r['status']=='PASS'for r in results)else'FAIL',
    'filesVerified':len(results),'results':results,'gpuOrPaidServicesUsed':False}
(ROOT/'reports/DOWNLOAD_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='results'}))
if report['status']!='PASS':raise SystemExit(1)
