#!/usr/bin/env python3
"""Seal the reviewed opt-in quality overlay; no build, network or GPU operation."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re

BASE = 'f276f19fc3c61c77e17e3683a8b8302523a379dc'
REC = 'world-simulation-shorts-engine/recovery/'
HERE = REC + 'reference-label-quality-v1/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
GENERATED = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
SCENE = HERE + 'QUALITY_LABELS_10S.json'
VERIFIER = HANDOFF + 'backend/capture_nvidia.mjs'
BASE_PINS = {
 RUNTIME:'a9ab747b27ba1927c03bc4cbb1939a888a2afaaffcbf8b6f5ceb90b481fcfab2',
 GENERATED:'c9122a200b0e918747824d5e73253d98d64b2a8746cfb72f3d5a656b0c4271ca',
 BOOTSTRAP:'b3790c43c1db8236d00789bfd322622eade9f1c38f3dfed5204f59bf868a4efd',
 STARTUP:'af13464f56e309b1454dbd708d101e1b9d0bceedd705ac8833795f4ef869f918',
}
def need(ok, code):
 if not ok: raise RuntimeError(code)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
def row(repo,path):
 file=repo/path
 need(file.is_file() and not file.is_symlink(), 'MISSING_OR_UNSAFE_SOURCE:'+path)
 raw=file.read_bytes()
 return {'path':path,'bytes':len(raw),'sha256':sha(raw)}
def seal(repo,added):
 repo=repo.resolve(); baseline=repo/HERE/'baseline'
 base={}
 for path,pin in BASE_PINS.items():
  raw=(baseline/Path(path).name).read_bytes();need(sha(raw)==pin,'BASELINE_PIN:'+path);base[path]=raw
 runtime=json.loads(base[RUNTIME]);old_rows={r['path']:r for r in runtime['files']}
 need(len(old_rows)==355,'BASELINE_SOURCE_COUNT')
 need(len(added)==len(set(added)) and not any(p in old_rows for p in added),'ADDITION_NOT_NEW')
 for path in added:
  need(path.startswith('world-simulation-shorts-engine/') and '..' not in Path(path).parts,'UNSAFE_ADDITION')
 # Variant original/actual links are derived from bytes, never bypassed.
 generated=json.loads(base[GENERATED])
 verifier=(baseline/'capture_nvidia.mjs').read_bytes()
 verifier_row=old_rows[VERIFIER]
 need(sha(verifier)==verifier_row['sha256'],'VERIFIER_BASE_CHANGED')
 evidence=repo/HERE/'evidence';evidence.mkdir(exist_ok=True)
 for variant in generated['variants']:
  original=variant['original']; target=HANDOFF+variant['variant']
  original_row=row(repo,original); target_row=row(repo,target)
  previous_original=variant['originalSHA256']
  if original_row['sha256']!=previous_original:
   need(verifier.count(previous_original.encode())==1,'VERIFIER_HASH_LITERAL_COUNT')
   verifier=verifier.replace(previous_original.encode(),original_row['sha256'].encode())
  variant['originalSHA256']=original_row['sha256'];variant['variantSHA256']=target_row['sha256']
  if variant != next(v for v in json.loads(base[GENERATED])['variants'] if v['variant']==variant['variant']):
   variant['oldFileModified']=original_row['sha256']!=previous_original
   patch=''.join(difflib.unified_diff((repo/original).read_text().splitlines(True),(repo/target).read_text().splitlines(True),fromfile=original,tofile=target))
   (evidence/(variant['variant']+'.patch')).write_text(patch)
   variant['diff']='../reference-label-quality-v1/evidence/'+variant['variant']+'.patch'
 (repo/VERIFIER).write_bytes(verifier)
 generated['defaultSoftwareFilesChanged']=any(v['oldFileModified'] for v in generated['variants'])
 generated['optionalReferenceLabelQuality']={'sourceBaseCommit':BASE,'optInOnly':True,'actualGPUValidation':'NOT_RUN'}
 (repo/GENERATED).write_bytes(encoded(generated))
 changed=[]
 for path,prior in old_rows.items():
  file=repo/path
  if not file.exists(): continue # Unchanged parent rows may be inherited without local copy.
  current=row(repo,path)
  if current!=prior:
   changed.append(path);prior.update(current)
 for path in added: runtime['files'].append(row(repo,path))
 runtime['files'].sort(key=lambda r:r['path'])
 need(set(old_rows).issubset({r['path'] for r in runtime['files']}),'BASE_ROWS_REMOVED')
 (repo/RUNTIME).write_bytes(encoded(runtime))
 runtime_sha=sha((repo/RUNTIME).read_bytes())
 bootstrap,n=re.subn(rb"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$",("SOURCE_SHA = '"+runtime_sha+"'").encode(),base[BOOTSTRAP])
 need(n==1,'BOOTSTRAP_SOURCE_PIN_COUNT')
 (repo/BOOTSTRAP).write_bytes(bootstrap)
 startup=json.loads(base[STARTUP]);startup['runtimeManifestSHA256']=runtime_sha
 startup['files']['bootstrap.py']={'bytes':len(bootstrap),'sha256':sha(bootstrap)}
 (repo/STARTUP).write_bytes(encoded(startup))
 paths=sorted(set(changed+added+[RUNTIME,BOOTSTRAP,STARTUP]))
 result={'schema':'WORLD_ENGINE_REFERENCE_LABEL_QUALITY_OVERLAY_V1','status':'PASS','sourceBaseCommit':BASE,
  'changedSources':sorted(changed),'addedRuntimeSources':sorted(added),'overlay':[row(repo,p) for p in paths],
  'runtimeSourceRows':len(runtime['files']),'runtimeManifestSHA256':runtime_sha,'startupManifestSHA256':sha((repo/STARTUP).read_bytes()),
  'scene':row(repo,SCENE),'oldPASSReruns':0,'gpuExecutions':0}
 (repo/HERE/'SEALED_OVERLAY.json').write_bytes(encoded(result))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True,type=Path);p.add_argument('--add-runtime',action='append',default=[])
 a=p.parse_args();print(json.dumps(seal(a.repo,a.add_runtime),indent=2))
