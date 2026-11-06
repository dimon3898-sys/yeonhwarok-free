"""Use published image + four sealed mounts for CPU-only production source preparation."""
from pathlib import Path
import base64,hashlib,json,os,subprocess

repo=Path(os.environ['GITHUB_WORKSPACE']).resolve()
audit='world-simulation-shorts-engine/recovery/capture-stall-review-v1'
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
image='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:dd79cad7aafcd2caefb1468c95f9fc28f8834c960135c6a038e208d04d221091'
out=Path(os.environ['RUNNER_TEMP'])/'variant-preflight-evidence';out.mkdir(mode=0o777);out.chmod(0o777)
seal=json.loads((repo/audit/'evidence/VARIANT_PREFLIGHT_SOURCE_SEAL.json').read_bytes())
assert seal['parentImage']==image and len(seal['files'])==4
mounts=[]
for row in seal['files']:
    p=repo/row['path'];raw=p.read_bytes()
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
    mounts+=['--mount',f'type=bind,src={p},dst={root}/{row["path"]},readonly']
mounts+=['--mount',f'type=bind,src={repo/audit},dst={root}/{audit},readonly','--mount',f'type=bind,src={out},dst=/out']
test=root+'/'+audit+'/tests/variant_preflight_focus.mjs'
fixture=root+'/'+audit+'/executions/20261105-user-render-a1/REQUEST_FIXTURE.json'
# This guard executes before any fixture work and checks the installed source closure.
probe='''import importlib.util,json,os
from pathlib import Path
r=Path("'''+root+'''"); p=r/"world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
s=importlib.util.spec_from_file_location("_variant_boot",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
seal=json.loads((r/"'''+audit+'''/evidence/VARIANT_PREFLIGHT_SOURCE_SEAL.json").read_bytes())
assert os.getuid()==1000
m.verify_startup(p.parent/"STARTUP_MANIFEST.json",seal["startupManifestSHA256"])
m.source_contract(r/"world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json",seal["runtimeManifestSHA256"])
Path("/out/INSTALLED_SOURCE.json").write_text(json.dumps({"status":"PASS","uid":1000,"runtimeRows":356,"overlayPins":4,"gpuExecutions":0})+"\\n")
'''
(out/'probe.py').write_text(probe)
commands='set -euo pipefail\npython3 -I -B /out/probe.py\nnode '+test+' '+fixture+' /out/FACADE_RESULT.json'
command=['docker','run','--rm','--name','we-variant-cpu-'+os.environ['GITHUB_RUN_ID'],
 '--network','none','--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges',
 '--tmpfs','/tmp:rw,nosuid,size=128m','--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1024m',
 '-e','NVIDIA_VISIBLE_DEVICES=void','-e','PYTHONDONTWRITEBYTECODE=1',*mounts,'--entrypoint','/bin/bash',image,'-c',commands]
completed=subprocess.run(command,timeout=360)
summary={'schema':'WORLD_ENGINE_VARIANT_PREFLIGHT_CPU_V1','status':'PASS' if completed.returncode==0 else 'FAIL',
 'sourceCommit':os.environ['GITHUB_SHA'],'image':image,'uid':1000,'exitCode':completed.returncode,
 'gpuExecutions':0,'imageBuilds':0,'imagePublications':0,'oldPASSReruns':0,'renderedFrames':0,
 'scope':'Changed source closure and production NVIDIA prepare/verify facade only',
 'actualGcubeMountVerified':False,'fullStudioHttpPreflightVerified':False}
(out/'CPU_RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
for p in sorted(out.glob('*.json')):
    raw=p.read_bytes();print('VARIANT_CPU_EVIDENCE='+json.dumps({'name':p.name,'sha256':hashlib.sha256(raw).hexdigest(),'base64':base64.b64encode(raw).decode()}),flush=True)
raise SystemExit(completed.returncode)
