"""Prepare an additive, inactive code-only context. Never builds or publishes.

Existing image evidence is reused. Private rasters/registries are not embedded.
A separate private asset installation is required before this image can deploy.
"""
from pathlib import Path
import hashlib,json,shutil,sys
IMAGE='ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT=IMAGE+'@sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b'
ROOT='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
R='world-simulation-shorts-engine/recovery/'
WORKER=R+'codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
RUNTIME=R+'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
GENERATED=R+'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json'
BOOTSTRAP=R+'studio-cold-start-v2/bootstrap.py'
STARTUP=R+'studio-cold-start-v2/STARTUP_MANIFEST.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def encode(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def write(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as s:s.write(b)
 p.chmod(0o644)
def prepare(reference,overlay_source,validation_source,visual_receipt,destination):
 ref,src,validation,out=map(Path,[reference,overlay_source,validation_source,destination])
 review=json.loads(Path(visual_receipt).read_text())
 assert review['status']=='CPU_VISUAL_CHANGED_SCOPE_ACCEPTED' and review['gpuExecuted'] is False
 assert not out.exists(),'FRESH_DESTINATION_REQUIRED'
 raw=(ref/'V16_BASE_RUNTIME.json').read_bytes();assert sha(raw)=='c70ec44c260c73b1366c3a4e5b66285297d247f4d33739936d96887df141cdfd'
 runtime=json.loads(raw);rows={x['path']:x for x in runtime['files']}
 # Reconstitute only the published parent metadata, not an old build or test.
 rows[WORKER].update(bytes=20514,sha256='f96763045ae38f24b0dba6f609e049454464f8d8489e2762987155c1e1cf0171')
 assert sha(encode(runtime))=='659654d1cdb3b1a004e80b4fd67baa7d1b2a750abec4b66fce141dae0d2f7fa5'
 overlay={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()}
 assert not any(n.endswith('CANDIDATE_SOURCE_CREDITS_REFERENCE.json') for n in overlay),'PRIVATE_PROVENANCE_FORBIDDEN'
 assert len(overlay)==46 and all(n.startswith(R) and n.endswith(('.py','.mjs','.json','.LICENSE')) for n in overlay),'EXACT_REVIEWED_CODE_OVERLAY_REQUIRED'
 generated=(ref/'PARENT_GENERATED_SOURCE_MANIFEST.json').read_bytes()
 assert sha(generated)==rows[GENERATED]['sha256'],'PARENT_VARIANT_MANIFEST_PIN'
 metadata=json.loads(generated);variant_changes=[]
 for row in metadata['variants']:
  name=R+'codex-to-gcube-handoff-v1/'+row['variant']
  if name in overlay:
   before=row['variantSHA256'];row['variantSHA256']=sha(overlay[name]);variant_changes.append({'variant':row['variant'],'beforeSHA256':before,'afterSHA256':row['variantSHA256']})
 assert len(variant_changes)==2
 overlay[GENERATED]=encode(metadata)
 for name,b in overlay.items():rows[name]={'path':name,'bytes':len(b),'sha256':sha(b)}
 runtime['files']=sorted(rows.values(),key=lambda x:x['path'])
 runtime['candidateOverlayCommit']='5d749200684406ad66a6a381e04d5a31a3ef7b05'
 runtime_raw=encode(runtime)
 boot=(ref/'V16_BASE_BOOTSTRAP.py').read_bytes();assert sha(boot)=='093b03586767c15c29d436f4feb9b0d6f47590da439b4662ed2e40e293324d71'
 old=b"SOURCE_SHA = 'c70ec44c260c73b1366c3a4e5b66285297d247f4d33739936d96887df141cdfd'"
 assert boot.count(old)==1;boot=boot.replace(old,("SOURCE_SHA = '"+sha(runtime_raw)+"'").encode())
 startup_raw=(ref/'V16_BASE_STARTUP.json').read_bytes();assert sha(startup_raw)=='5189b25317048d11afffe019c3796560ecacab30a628de8b0d58b3b9a547b04c'
 startup=json.loads(startup_raw);startup['runtimeManifestSHA256']=sha(runtime_raw);startup['files']['bootstrap.py']={'bytes':len(boot),'sha256':sha(boot)};startup_raw=encode(startup)
 overlay.update({RUNTIME:runtime_raw,BOOTSTRAP:boot,STARTUP:startup_raw})
 for name,b in overlay.items():write(out/'overlay'/name,b)
 entry=['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',ROOT+'/'+BOOTSTRAP,'--startup-manifest',ROOT+'/'+STARTUP,'--startup-manifest-sha256',sha(startup_raw),'--source-manifest',ROOT+'/'+RUNTIME,'--source-manifest-sha256',sha(runtime_raw),'--export-root','/world-storage']
 write(out/'Dockerfile',('FROM '+PARENT+'\nCOPY --chown=0:0 '+json.dumps(['overlay/',ROOT+'/'])+'\nENTRYPOINT '+json.dumps(entry)+'\n').encode())
 plan={'schema':'WORLD_ENGINE_NATIVE_CODE_PACKAGE_V1','status':'PREPARED_INACTIVE_REQUIRES_BUILD_AND_PRIVATE_ASSETS','parentImage':PARENT,'entrypoint':entry,'runtimeManifestSHA256':sha(runtime_raw),'startupManifestSHA256':sha(startup_raw),'variantPinChanges':variant_changes,'overlay':[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(overlay.items())],'rawDataIncluded':False,'privateRegistryIncluded':False,'privateAssetInstallationRequired':True,'fullInstalledImageQualification':'NOT_RUN','imageBuilt':False,'deploymentReady':False,'oldTestsRerun':False,'gpuExecuted':False}
 write(out/'CONTEXT.json',encode(plan));return plan
if __name__=='__main__':
 if len(sys.argv)!=6:raise SystemExit('REFERENCE OVERLAY_SOURCE VALIDATION_SOURCE VISUAL_RECEIPT NEW_DESTINATION')
 p=prepare(*sys.argv[1:]);print(json.dumps({k:p[k] for k in ['status','runtimeManifestSHA256','startupManifestSHA256','variantPinChanges','deploymentReady']}))
