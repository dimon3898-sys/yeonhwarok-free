#!/usr/bin/env python3
"""Verify seven exact HTTPS GET bodies against original and saved Git bytes."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from urllib.parse import quote,urlparse
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PREFIX='world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/public-review/'
EXPECTED={'WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4','COMPARE_01_START.png','COMPARE_02_ADVANCE.png',
 'COMPARE_03_TRACKING.png','COMPARE_04_CONTINUOUS_CONTROL.png','COMPARE_05_END.png','SHA256SUMS'}
def digest(value):return hashlib.sha256(value).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--media-commit',required=True);a=p.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',a.media_commit):raise SystemExit('Full saved media commit required')
 declared=json.loads((HERE/'evidence/PUBLIC_REVIEW_FILES.json').read_text())['files']
 names=[row['file'] for row in declared];folder=HERE/'public-review'
 if len(names)!=7 or len(set(names))!=7 or set(names)!=EXPECTED or set(x.name for x in folder.iterdir())!=EXPECTED:
  raise SystemExit('EXACT seven MP4/five comparison PNG/SHA bodies required; no Scene or diagnostics')
 if any(not x.is_file() or x.is_symlink() for x in folder.iterdir()):raise SystemExit('Regular public files only')
 cache=Path('/workspace/.onboarding/moving-frontier-glow-downloads')/a.media_commit;cache.mkdir(parents=True,exist_ok=True)
 receipt={'schema':'MOVING_FRONTIER_GLOW_PUBLIC_DOWNLOAD_VERIFICATION_V1','status':'IN_PROGRESS','mediaCommit':a.media_commit,
  'method':'ACTUAL_HTTPS_GET_WITH_TLS_VERIFICATION','files':[],'requiredTempOnlyFiles':0,'publicSceneJSON':False,
  'userVideoReview':'REQUIRED','finalPromotion':False}
 output_receipt=HERE/'evidence/HTTP_DOWNLOAD_VERIFY.json'
 for name in sorted(names):
  original=(folder/name).read_bytes();saved=subprocess.check_output(['git','show',a.media_commit+':'+PREFIX+name],cwd=REPO)
  row=next(item for item in declared if item['file']==name)
  if original!=saved or row.get('sha256')!=digest(original) or row.get('bytes')!=len(original):
   raise RuntimeError('ORIGINAL_GIT_DECLARED_BODY_MISMATCH '+name)
  url='https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+a.media_commit+'/'+PREFIX+quote(name)
  target=cache/name
  result=subprocess.run(['curl','--silent','--show-error','--fail','--location','--proto','=https','--proto-redir','=https',
   '--tlsv1.2','--connect-timeout','20','--max-time','60','--output',str(target),
   '--write-out','%{http_code}\n%{url_effective}\n',url],capture_output=True,text=True)
  if result.returncode:raise RuntimeError('DOWNLOAD_FAILED '+name+' '+result.stderr[:400])
  response=result.stdout.splitlines();status,effective=response[:2]
  downloaded=target.read_bytes()
  if status!='200' or downloaded!=original or urlparse(effective).scheme!='https':raise RuntimeError('HTTP_TLS_OR_SHA_MISMATCH '+name)
  actual={'file':name,'url':url,'effectiveUrl':effective,'httpStatus':200,'bytes':len(original),
   'sha256':digest(original),'originalSha256':digest(original),'gitSha256':digest(saved),
   'downloadedSha256':digest(downloaded),'byteEquality':True}
  receipt['files'].append(actual);output_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
  print(json.dumps({'file':name,'httpStatus':200,'sha256':actual['sha256'],'equal':True}),flush=True)
 receipt['status']='PASS';output_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'status':'PASS','verifiedDownloads':7,'publicSceneJSON':False}),flush=True)
if __name__=='__main__':main()
