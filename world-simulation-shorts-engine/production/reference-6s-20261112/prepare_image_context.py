"""Package the verified source closure over the existing immutable CPU/NVIDIA image."""
from pathlib import Path
import json,hashlib,shutil,sys,os
P=Path(__file__).resolve().parent;E=P.parents[1];R=E.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review=json.loads((P/'CPU_SCREEN_REVIEW.json').read_text());continuity=json.loads((P/'CPU_CONTINUITY_REVIEW.json').read_text())
assert review['status']=='PASS' and continuity['status']=='PASS','CPU_GATES_REQUIRED'
request=json.loads((P/'REGISTERED_RUNTIME_REQUEST.json').read_text());assert review['compilerInputSHA256']==continuity['compilerInputSHA256']==request['sourceInputSHA256']
manifest=E/'recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json';startup=E/'recovery/studio-cold-start-v2/STARTUP_MANIFEST.json';m=json.loads(manifest.read_text());st=json.loads(startup.read_text());assert st['runtimeManifestSHA256']==sha(manifest)
context=Path(sys.argv[1]);context.mkdir(exist_ok=False);overlay=context/'overlay';overlay.mkdir();files=[]
def copy(p,expected=None):
 b=p.read_bytes();assert expected is None or len(b)==expected['bytes'] and hashlib.sha256(b).hexdigest()==expected['sha256'],'SOURCE_BINDING_CHANGED:'+str(p)
 target=overlay/p.relative_to(R);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);target.chmod(0o644);files.append({'path':str(p.relative_to(R)),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
for row in m['files']:copy(R/row['path'],row)
copy(manifest);copy(startup)
for name,row in st['files'].items():copy(startup.parent/name,row)
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo';prefix=root+'/world-simulation-shorts-engine/recovery/'
entry=['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',prefix+'studio-cold-start-v2/bootstrap.py','--startup-manifest',prefix+'studio-cold-start-v2/STARTUP_MANIFEST.json','--startup-manifest-sha256',sha(startup),'--source-manifest',prefix+'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json','--source-manifest-sha256',sha(manifest),'--export-root','/world-storage']
parent='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:af3ad26a305c160a916ac231122a31824cbee4759338c044bab0d6c9dab1691a'
(context/'Dockerfile').write_text('FROM '+parent+'\nCOPY --chown=0:0 ["overlay/", "'+root+'/"]\nENTRYPOINT '+json.dumps(entry)+'\n')
(context/'verify_image.py').write_text('''from pathlib import Path
import importlib.util,json,os
r=Path("'''+root+'''");p=r/"world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
s=importlib.util.spec_from_file_location("reference6s_boot",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert os.getuid()==1000
m.verify_startup(p.parent/"STARTUP_MANIFEST.json","'''+sha(startup)+'''")
m.source_contract(r/"world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json","'''+sha(manifest)+'''")
print(json.dumps({"status":"PASS_ACTUAL_IMAGE_SOURCE_CLOSURE","uid":1000,"GPUExecutions":0,"renderStarted":False}))
''')
(context/'CONTEXT_RECEIPT.json').write_text(json.dumps({'status':'PACKAGED_NOT_BUILT','parentImage':parent,'sourceCommit':os.environ.get('GITHUB_SHA'),'startupManifestSHA256':sha(startup),'runtimeManifestSHA256':sha(manifest),'compilerInputSHA256':request['sourceInputSHA256'],'entrypoint':entry,'files':files,'GPUExecutions':0},indent=2)+'\n')
print(json.dumps({'files':len(files),'bytes':sum(x['bytes']for x in files),'parentImage':parent,'GPUExecutions':0}))
