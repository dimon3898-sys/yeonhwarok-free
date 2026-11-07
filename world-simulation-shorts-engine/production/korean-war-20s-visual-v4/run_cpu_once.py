"""Six new source-detail frames; existing ten-second renderer, no GPU/image build."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
repo=Path(os.environ['GITHUB_WORKSPACE']).resolve();audit='world-simulation-shorts-engine/production/korean-war-20s-visual-v4'
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
seal=json.loads((repo/audit/'SOURCE_SEAL.json').read_bytes());out=Path(os.environ['RUNNER_TEMP'])/'kw20-evidence';out.mkdir(mode=0o777);out.chmod(0o777)
resume='world-simulation-shorts-engine/production/korean-war-20s-resume-v3'
remainingOnly=False
mounts=[]
for row in [*seal['files'], *seal.get('assets',[])]:
    p=repo/row['path'];b=p.read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
    mounts+=['--mount',f'type=bind,src={p},dst={root}/{row["path"]},readonly']
for row in seal['inputs']:
    b=(repo/row['path']).read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
mounts+=['--mount',f'type=bind,src={repo/audit},dst={root}/{audit},readonly','--mount',f'type=bind,src={out},dst=/out']
mounts+=['--mount',f'type=bind,src={repo/"world-simulation-shorts-engine/production/korean-war-20s-detail-v2"},dst={root}/world-simulation-shorts-engine/production/korean-war-20s-detail-v2,readonly']
if remainingOnly:mounts+=['--mount',f'type=bind,src={Path(os.environ["RUNNER_TEMP"])/"kw20-previous/evidence"},dst=/previous,readonly']
probe='''import importlib.util,json,os
from pathlib import Path
r=Path("'''+root+'''");p=r/"world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
s=importlib.util.spec_from_file_location("_kw20_boot",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
seal=json.loads((r/"'''+audit+'''/SOURCE_SEAL.json").read_bytes());assert os.getuid()==1000
m.verify_startup(p.parent/"STARTUP_MANIFEST.json",seal["startupManifestSHA256"])
m.source_contract(r/"world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json",seal["runtimeManifestSHA256"])
Path("/out/INSTALLED_SOURCE.json").write_text(json.dumps({"status":"PASS_NEW_OVERLAY_INTEGRITY","uid":1000,"runtimeRows":seal["runtimeSourceRows"],"overlayPins":len(seal["files"]),"gpuExecutions":0})+"\\n")
'''
(out/'probe.py').write_text(probe)
tool=root+'/'+audit
commands='\n'.join(['set -euo pipefail','python3 -I -B /out/probe.py','mkdir -m 700 /workspace/kw20-private',
 'node '+tool+'/prepare_visual.mjs /out/check /workspace/kw20-private',
 'node '+root+'/world-simulation-shorts-engine/production/korean-war-20s-detail-v2/render_clip_cpu.mjs --prepared=/out/check/PREPARED_1.json --output=/out/clip-01 --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium --frames=0,299',
 'node '+tool+'/render_clip_cpu.mjs --prepared=/out/check/PREPARED_2.json --output=/out/clip-02 --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium --frames=299'])
args=['docker','run','--rm','--name','we-kw20-'+os.environ['GITHUB_RUN_ID'],'--network','none','--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--shm-size','1g',
 '--tmpfs','/tmp:rw,nosuid,size=512m','--tmpfs','/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m','--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1024m',
 '-e','NVIDIA_VISIBLE_DEVICES=void','-e','PYTHONDONTWRITEBYTECODE=1','-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map',*mounts,'--entrypoint','/bin/bash',seal['parentImage'],'-c',commands]
code=99
try:code=subprocess.run(args,timeout=1500).returncode
finally:
    subprocess.run(['sudo','chmod','-R','a+rX',str(out)],check=True)
    (out/'RUN_RESULT.json').write_text(json.dumps({'status':'PASS' if code==0 else 'FAIL','sourceCommit':os.environ['GITHUB_SHA'],'exitCode':code,'gpuStarts':0,'gpuRenders':0,'imageBuilds':0,'imagePublications':0,'gCubeChanges':0,'oldPassSuitesRerun':0},indent=2)+'\n')
raise SystemExit(code)
