"""Use the current pinned image as an offline CPU test environment, no build/GPU."""
from pathlib import Path
import hashlib,json,os,subprocess

repo=Path(os.environ['GITHUB_WORKSPACE']).resolve()
audit='world-simulation-shorts-engine/recovery/capture-stall-review-v1'
image_root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
image='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:534e5afd33e73b9d3f3e49db3f4a7dc63a1ee25a91457611f2d4b4fcb00e1e4c'
out=Path(os.environ['RUNNER_TEMP'])/'incident-evidence';out.mkdir(mode=0o777);out.chmod(0o777)
seal=json.loads((repo/audit/'evidence/INCIDENT_SOURCE_SEAL.json').read_text())
mounts=[]
for row in seal['files']:
    p=repo/row['path'];b=p.read_bytes()
    assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
    mounts+=['--mount',f'type=bind,src={p},dst={image_root}/{row["path"]},readonly']
mounts+=['--mount',f'type=bind,src={repo/audit},dst={image_root}/{audit},readonly',
    '--mount',f'type=bind,src={out},dst=/out']
tests=image_root+'/'+audit+'/tests/'
baseline=image_root+'/'+audit+'/executions/20261105-user-render-a1/BASELINE_PRESENTATION_RUNTIME.mjs'
fixture=image_root+'/'+audit+'/executions/20261105-user-render-a1/REQUEST_FIXTURE.json'
commands='\n'.join(['set -euo pipefail',
    'python3 -B '+tests+'incident_control_focus.py /out/control',
    'node '+tests+'prepare_incident_fixture.mjs '+fixture+' /workspace/incident-private-prepared.json',
    'node '+tests+'frame1_pixels.mjs --prepared=/workspace/incident-private-prepared.json --output=/out/pixels --baseline='+baseline+' --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium'])
command=['docker','run','--rm','--name','we-incident-cpu-'+os.environ['GITHUB_RUN_ID'],
    '--network','none','--read-only','--user','1000:1000','--cap-drop','ALL',
    '--security-opt','no-new-privileges','--shm-size','1g',
    '--tmpfs','/tmp:rw,nosuid,size=512m',
    '--tmpfs','/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m',
    '--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1536m',
    '-e','NVIDIA_VISIBLE_DEVICES=void','-e','PYTHONDONTWRITEBYTECODE=1',
    '-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map',*mounts,
    '--entrypoint','/bin/bash',image,'-c',commands]
result=subprocess.run(command,timeout=600)
subprocess.run(['sudo','chmod','-R','a+rX',str(out)],check=True)
summary={'schema':'WORLD_ENGINE_INCIDENT_CPU_V1','status':'PASS' if result.returncode==0 else 'FAIL',
    'sourceCommit':os.environ['GITHUB_SHA'],'image':image,'uid':1000,'exitCode':result.returncode,
    'gpuStarts':0,'imageBuilds':0,'imagePublications':0,'fullVideoRenders':0,'oldPassSuitesRerun':0,
    'scope':'Actual frame1 regression plus terminal-failure cleanup and slow-checkpoint storage',
    'actualFUSEValidated':False,'nvidiaCandidateValidated':False,'referenceQualityValidated':False}
(out/'RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
print('INCIDENT_CPU_RESULT='+json.dumps(summary),flush=True)
raise SystemExit(result.returncode)
