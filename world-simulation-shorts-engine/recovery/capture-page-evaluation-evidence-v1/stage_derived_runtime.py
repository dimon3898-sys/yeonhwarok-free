"""Prepare an isolated derivative from the VERIFIED 352-file diagnostic image.
Offline, no GPU, no image build or deployment. Fails closed on pin mismatches.
"""
import argparse, hashlib, json, pathlib, shutil

PARENT_ROOT=pathlib.Path('/opt/world-engine-handoffs/studio-diagnostics-v1/repo')
PARENT_MANIFEST_SHA='312d806393ab7776167a0977678df067b7b1f4ff3c8d25f9f119e549e0e74251'
PARENT_STARTUP_SHA='09d9f21f3fa58f5ec81e6753bb946def49d4f666ad58f88f104ad409e2f78ebc'
REC='world-simulation-shorts-engine/recovery/'
MANIFEST=REC+'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP=REC+'studio-cold-start-v2/'
CAPTURE=REC+'codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs'
EXPORTER=REC+'codex-to-gcube-handoff-v1/controller/safe_capture_export.py'
SOURCE_SHA_NEEDLE="SOURCE_SHA = '"+PARENT_MANIFEST_SHA+"'"

def digest(data):return hashlib.sha256(data).hexdigest()
def wire(data):return (json.dumps(data,sort_keys=True,indent=2)+'\n').encode()
def require(test,code):
 if not test:raise RuntimeError(code)
def read(root,name):
 p=root/name
 require(p.is_file() and not p.is_symlink() and '..' not in pathlib.PurePosixPath(name).parts,'SOURCE_PATH_INVALID')
 return p.read_bytes()

def stage(parent,candidate,dest):
 require(not dest.exists(),'DERIVATIVE_DESTINATION_EXISTS')
 raw=read(parent,MANIFEST)
 require(digest(raw)==PARENT_MANIFEST_SHA,'PARENT_MANIFEST_PIN_MISMATCH')
 manifest=json.loads(raw)
 require(len(manifest['files'])==352,'PARENT_352_FILE_CONTRACT_CHANGED')
 startup_raw=read(parent,STARTUP+'STARTUP_MANIFEST.json')
 require(digest(startup_raw)==PARENT_STARTUP_SHA,'PARENT_STARTUP_PIN_MISMATCH')
 startup=json.loads(startup_raw)
 require(startup['runtimeManifestSHA256']==PARENT_MANIFEST_SHA,'PARENT_STARTUP_SOURCE_PIN_MISMATCH')
 rows={r['path']:r for r in manifest['files']}
 require(CAPTURE in rows and EXPORTER in rows,'DERIVATIVE_SOURCE_ROWS_MISSING')
 require(all(digest(read(parent,r['path']))==r['sha256'] and len(read(parent,r['path']))==r['bytes'] for r in manifest['files']),'PARENT_SOURCE_CHANGED')
 # Original parent tree remains immutable; no in-place editing.
 shutil.copytree(parent,dest,symlinks=True)
 original_capture=read(parent,CAPTURE).decode()
 changed_capture=read(candidate,'candidate_capture_vulkan.mjs').decode()
 markers=[
  ("let browser,encoder,encoderExit,service;","let browser,encoder,encoderExit,service;let diagnosticStage='BEFORE_PAGE_EVALUATION';"),
  ("await page.evaluate(async()=>{window.payload=","diagnosticStage='PAGE_EVALUATE_RUNTIME_IMPORT';await page.evaluate(async()=>{window.payload="),
  ("const firstNativeProof=await page.evaluate(async()=>{","diagnosticStage='PAGE_EVALUATE_FIRST_NATIVE_DRAW';const firstNativeProof=await page.evaluate(async()=>{"),
  ("const capture=await page.evaluate(async frame=>{","diagnosticStage='PAGE_EVALUATE_FRAME_CAPTURE';const capture=await page.evaluate(async frame=>{"),
  ("receipt.failure={code:String(error.message).slice(0,4000)};","receipt.failure={code:String(error.message).slice(0,4000),diagnosticStage};")]
 expected=original_capture
 for a,b in markers:
  require(expected.count(a)==1,'CAPTURE_ANCHOR_CHANGED')
  expected=expected.replace(a,b,1)
 require(changed_capture==expected,'UNAPPROVED_CAPTURE_DELTA')
 original_exporter=read(parent,EXPORTER).decode()
 changed_exporter=read(candidate,'safe_capture_export.py').decode()
 require(changed_exporter.replace('DIAGNOSTIC_STAGES = frozenset({"PAGE_EVALUATE_RUNTIME_IMPORT", "PAGE_EVALUATE_FIRST_NATIVE_DRAW", "PAGE_EVALUATE_FRAME_CAPTURE"})\n','').replace('    raw_stage = failure.get("diagnosticStage") if isinstance(failure, dict) else None\n    safe_stage = raw_stage if type(raw_stage) is str and raw_stage in DIAGNOSTIC_STAGES else None\n','').replace('            "diagnosticStage": safe_stage,\n','')==original_exporter,'UNAPPROVED_EXPORTER_DELTA')
 for name,raw in ((CAPTURE,changed_capture.encode()),(EXPORTER,changed_exporter.encode())):
  (dest/name).write_bytes(raw)
  rows[name].update(bytes=len(raw),sha256=digest(raw))
 manifest['files']=sorted(rows.values(),key=lambda r:r['path'])
 manifest['derivation']={'parentRuntimeManifestSHA256':PARENT_MANIFEST_SHA,'stageOnly':True,'parentPreserved':True}
 derived=wire(manifest);(dest/MANIFEST).write_bytes(derived)
 bootstrap=dest/STARTUP/'bootstrap.py'
 b=bootstrap.read_text()
 require(b.count(SOURCE_SHA_NEEDLE)==1,'BOOTSTRAP_PIN_CHANGED')
 bootstrap.write_text(b.replace(SOURCE_SHA_NEEDLE,"SOURCE_SHA = '"+digest(derived)+"'"))
 startup['runtimeManifestSHA256']=digest(derived)
 for name in startup['files']:
  data=read(dest,STARTUP+name)
  startup['files'][name]={'bytes':len(data),'sha256':digest(data)}
 new_startup=wire(startup);(dest/STARTUP/'STARTUP_MANIFEST.json').write_bytes(new_startup)
 require(digest(read(parent,MANIFEST))==PARENT_MANIFEST_SHA and digest(read(parent,STARTUP+'STARTUP_MANIFEST.json'))==PARENT_STARTUP_SHA,'PARENT_MUTATED')
 return {'status':'ISOLATED_DERIVATIVE_STAGED','runtimeManifestSHA256':digest(derived),'startupManifestSHA256':digest(new_startup),'sourceFiles':352,'changedSourceFiles':[CAPTURE,EXPORTER],'gpuExecuted':False,'imageBuilt':False,'deployReady':False}

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--parent',type=pathlib.Path,default=PARENT_ROOT)
 p.add_argument('--candidate',type=pathlib.Path,required=True)
 p.add_argument('--destination',type=pathlib.Path,required=True)
 args=p.parse_args()
 try:print(json.dumps(stage(args.parent,args.candidate,args.destination),sort_keys=True))
 except Exception as e:
  print(json.dumps({'status':'BLOCKED','code':str(e),'gpuExecuted':False}))
  raise SystemExit(1) from None
