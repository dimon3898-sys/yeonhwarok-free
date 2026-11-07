"""Continue only previously undrawn frames, split at existing runtime scene resets."""
import hashlib,json,os,subprocess
from pathlib import Path
repo=Path(os.environ['GITHUB_WORKSPACE']).resolve()
audit='world-simulation-shorts-engine/production/korean-war-20s-viewport-v8';movie='world-simulation-shorts-engine/production/korean-war-20s-final-movie-v9';detail='world-simulation-shorts-engine/production/korean-war-20s-detail-v2'
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
clip=int(os.environ['KW20_CLIP']);start=int(os.environ['KW20_START']);end=start+150
assert clip in (1,2) and start in (0,150)
seal=json.loads((repo/audit/'SOURCE_SEAL.json').read_bytes())
pins=json.loads((repo/movie/'CACHED_FRAMES.json').read_bytes())
cached={r['frame'] for r in pins if r['clip']==clip and start<=r['frame']<end}
frames=[f for f in range(start,end) if f not in cached]
out=Path(os.environ['RUNNER_TEMP'])/'kw20-evidence';out.mkdir(mode=0o777);out.chmod(0o777)
mounts=[]
for row in [*seal['files'],*seal['assets'],*seal['inputs']]:
    path=repo/row.get('overlayPath',row['path']);raw=path.read_bytes()
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'SOURCE_BINDING_CHANGED'
for folder in [audit,movie,detail,'world-simulation-shorts-engine/production/korean-war-20s-visual-v4']:
    mounts+=['--mount',f'type=bind,src={repo/folder},dst={root}/{folder},readonly']
for row in seal['files']:
    if row['path'].startswith(detail+'/'):continue
    mounts+=['--mount',f'type=bind,src={repo/row.get("overlayPath",row["path"])},dst={root}/{row["path"]},readonly']
mounts+=['--mount',f'type=bind,src={out},dst=/out']
for name in ['previous','viewport']:
    mounts+=['--mount',f'type=bind,src={Path(os.environ["RUNNER_TEMP"])/("kw20-"+name)/"pixels"},dst=/{name},readonly']
probe='''import importlib.util,json,os
from pathlib import Path
r=Path("'''+root+'''");p=r/"world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
s=importlib.util.spec_from_file_location("_kw20_boot",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
seal=json.loads((r/"'''+audit+'''/SOURCE_SEAL.json").read_bytes());assert os.getuid()==1000
m.verify_startup(p.parent/"STARTUP_MANIFEST.json",seal["startupManifestSHA256"])
m.source_contract(r/"world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json",seal["runtimeManifestSHA256"])
Path("/out/INSTALLED_SOURCE.json").write_text(json.dumps({"status":"PASS_INSTALLED_SOURCE_BINDING","uid":1000,"runtimeManifestSHA256":seal["runtimeManifestSHA256"],"gpuExecutions":0})+"\\n")
'''
(out/'probe.py').write_text(probe)
commands='\n'.join(['set -euo pipefail','python3 -I -B /out/probe.py','mkdir -m 700 /workspace/kw20-private',
 f'node {root}/{movie}/prepare_cached.mjs /out/check /workspace/kw20-private --reuse-analysis',
 f'node {root}/{detail}/render_clip_cpu.mjs --prepared=/out/check/PREPARED_{clip}.json --output=/out/chunk --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium --frames='+','.join(map(str,frames)),
 f'python3 -I -B {root}/{movie}/encode_chunk.py'])
args=['docker','run','--rm','--name','we-kw20-'+os.environ['GITHUB_RUN_ID'],'--network','none','--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--shm-size','1g',
 '--tmpfs','/tmp:rw,nosuid,size=512m','--tmpfs','/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m','--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1024m',
 '-e','NVIDIA_VISIBLE_DEVICES=void','-e','PYTHONDONTWRITEBYTECODE=1','-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map',
 '-e',f'KW20_CLIP={clip}','-e',f'KW20_START={start}',*mounts,'--entrypoint','/bin/bash',seal['parentImage'],'-c',commands]
code=99
try:code=subprocess.run(args,timeout=5700).returncode
finally:
    subprocess.run(['sudo','chmod','-R','a+rX',str(out)],check=True)
    (out/'RUN_RESULT.json').write_text(json.dumps({'status':'PASS' if code==0 else 'FAIL','sourceCommit':os.environ['GITHUB_SHA'],'exitCode':code,'clip':clip,'start':start,'end':end,'newFramesRequested':len(frames),'priorFramesReused':sorted(cached),'gpuStarts':0,'imageBuilds':0,'oldPassSuitesRerun':0},indent=2)+'\n')
raise SystemExit(code)
