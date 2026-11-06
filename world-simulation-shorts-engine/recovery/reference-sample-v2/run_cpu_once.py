"""CPU-only new-sample checks and preview over the preserved deployed image."""
import hashlib,json,os,subprocess
from pathlib import Path
repo=Path(os.environ['GITHUB_WORKSPACE']).resolve();audit='world-simulation-shorts-engine/recovery/reference-sample-v2'
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
seal=json.loads((repo/audit/'SOURCE_SEAL.json').read_bytes());image=seal['parentImage']
out=Path(os.environ['RUNNER_TEMP'])/'reference-sample-evidence';out.mkdir(mode=0o777);out.chmod(0o777)
mounts=[]
for row in seal['files']:
 p=repo/row['path'];raw=p.read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
 mounts+=['--mount',f'type=bind,src={p},dst={root}/{row["path"]},readonly']
mounts+=['--mount',f'type=bind,src={repo/audit},dst={root}/{audit},readonly','--mount',f'type=bind,src={out},dst=/out']
baseline='world-simulation-shorts-engine/recovery/reference-label-quality-v1/QUALITY_LABELS_10S.json'
assert hashlib.sha256((repo/baseline).read_bytes()).hexdigest()=='281250a9f3c866d4d0a424da0d06a6e9a3cf4e2ab31660b879657e7ab0b3a24e'
mounts+=['--mount',f'type=bind,src={repo/baseline},dst={root}/{baseline},readonly']
probe='''import importlib.util,json,os
from pathlib import Path
r=Path("'''+root+'''");p=r/"world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
s=importlib.util.spec_from_file_location("_sample_boot",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
seal=json.loads((r/"'''+audit+'''/SOURCE_SEAL.json").read_bytes());assert os.getuid()==1000
m.verify_startup(p.parent/"STARTUP_MANIFEST.json",seal["startupManifestSHA256"])
m.source_contract(r/"world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json",seal["runtimeManifestSHA256"])
Path("/out/INSTALLED_SOURCE.json").write_text(json.dumps({"status":"PASS","uid":1000,"runtimeRows":356,"overlayPins":len(seal["files"]),"gpuExecutions":0})+"\\n")
'''
(out/'probe.py').write_text(probe)
tests=root+'/'+audit
commands='\n'.join(['set -euo pipefail','python3 -I -B /out/probe.py','mkdir -m 700 /workspace/sample-private',
 'node '+tests+'/check_new_sample.mjs /out/check /workspace/sample-private',
 'node '+tests+'/render_cpu_preview.mjs --prepared=/out/check/PREPARED.json --output=/out/preview --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium'])
args=['docker','run','--rm','--name','we-reference-sample-'+os.environ['GITHUB_RUN_ID'],'--network','none','--read-only','--user','1000:1000',
 '--cap-drop','ALL','--security-opt','no-new-privileges','--shm-size','1g',
 '--tmpfs','/tmp:rw,nosuid,size=512m','--tmpfs','/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m',
 '--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1024m','-e','NVIDIA_VISIBLE_DEVICES=void','-e','PYTHONDONTWRITEBYTECODE=1',
 '-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map',*mounts,'--entrypoint','/bin/bash',image,'-c',commands]
try:
 result=subprocess.run(args,timeout=1200);code=result.returncode
finally:
 subprocess.run(['sudo','chmod','-R','a+rX',str(out)],check=True)
summary={'schema':'WORLD_ENGINE_REFERENCE_SAMPLE_CPU_RUN_V2','status':'PASS' if code==0 else 'FAIL','sourceCommit':os.environ['GITHUB_SHA'],
 'parentImage':image,'exitCode':code,'gpuStarts':0,'gpuRenders':0,'imageBuilds':0,'imagePublications':0,'gCubeChanges':0,'oldPassSuitesRerun':0}
(out/'RUN_RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
raise SystemExit(code)
