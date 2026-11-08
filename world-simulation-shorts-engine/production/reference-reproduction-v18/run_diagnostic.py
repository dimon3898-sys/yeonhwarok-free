"""Read-only existing image, existing sparse CPU diagnostic driver, no MP4."""
import hashlib,json,os,subprocess
from pathlib import Path
repo=Path(os.environ['GITHUB_WORKSPACE']);here=repo/'world-simulation-shorts-engine/production/reference-reproduction-v18'
image='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b'
root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
out=Path(os.environ['RUNNER_TEMP'])/'reference-v18-evidence';out.mkdir();out.chmod(0o777)
driver=repo/'world-simulation-shorts-engine/production/korean-war-20s-detail-v2/render_clip_cpu.mjs'
pins=json.loads((here/'READY_MANIFEST.json').read_text())
for relative,digest in pins['files'].items():assert hashlib.sha256((here/relative).read_bytes()).hexdigest()==digest,relative
assert hashlib.sha256(driver.read_bytes()).hexdigest()==pins['existingPixelDriverSHA256']
subprocess.run(['docker','pull',image],check=True,timeout=1200)
commands=['set -euo pipefail','mkdir -m 700 /workspace/private',
 f'node /review/prepare_diagnostic.mjs {root} /review/ready /workspace/private /out',
 f'node {root}/world-simulation-shorts-engine/production/korean-war-20s-detail-v2/render_clip_cpu.mjs --prepared=/workspace/private/PREPARED_1.json --output=/out/part-01 --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium --frames=0,90,149,150,215,299',
 f'node {root}/world-simulation-shorts-engine/production/korean-war-20s-detail-v2/render_clip_cpu.mjs --prepared=/workspace/private/PREPARED_2.json --output=/out/part-02 --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium --frames=0,75,110,149,150,240,299']
args=['docker','run','--rm','--network','none','--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--shm-size','1g',
 '--tmpfs','/tmp:rw,nosuid,size=512m','--tmpfs','/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m','--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1024m',
 '-e','NVIDIA_VISIBLE_DEVICES=void','-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map',
 '--mount',f'type=bind,src={here},dst=/review,readonly',
 '--mount',f'type=bind,src={driver},dst={root}/world-simulation-shorts-engine/production/korean-war-20s-detail-v2/render_clip_cpu.mjs,readonly',
 '--mount',f'type=bind,src={out},dst=/out','--entrypoint','/bin/bash',image,'-c','\n'.join(commands)]
code=99
try:code=subprocess.run(args,timeout=1200).returncode
finally:
 subprocess.run(['sudo','chmod','-R','a+rX',str(out)],check=True)
 mp4=list(out.rglob('*.mp4'));assert not mp4,'MP4_FORBIDDEN'
 (out/'RUN_RESULT.json').write_text(json.dumps({'status':'PASS_SPARSE_CPU_DIAGNOSTICS' if code==0 else 'BLOCKED','exitCode':code,'image':image,'sourceCommit':os.environ['GITHUB_SHA'],'gpuStarts':0,'studioRenders':0,'imageBuilds':0,'mp4Encodes':0,'oldPASSReruns':0,'referenceQualityApproved':False,'scope':'13 selected diagnostic stills; unchanged formal renderer; no alternative production video'},indent=2)+'\n')
raise SystemExit(code)
