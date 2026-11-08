"""One worker publication fix and the complete required source/startup pins."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
IMAGE='ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST='sha256:a1eb4f0f1671d1cec1fb7e310c65b8479b0aa5e1e7bf11b00a1e3f9a1f78d3a7'
PARENT=IMAGE+'@'+PARENT_DIGEST
ROOT='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
RECOVERY='world-simulation-shorts-engine/recovery/'
WORKER=RECOVERY+'codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
RUNTIME=RECOVERY+'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP=RECOVERY+'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP=RECOVERY+'studio-cold-start-v2/bootstrap.py'
OLD_RUNTIME='c70ec44c260c73b1366c3a4e5b66285297d247f4d33739936d96887df141cdfd'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def need(value,code):
    if not value:raise RuntimeError(code)
def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)
    path.chmod(0o644)

def prepare(context):
    need(not context.exists(),'FRESH_CONTEXT_REQUIRED')
    cpu_raw=(HERE/'evidence/CPU_RESULT.json').read_bytes();cpu=json.loads(cpu_raw)
    need(cpu['status']=='PASS' and len(cpu['tests'])==6 and cpu['oldPASSReruns']==0,'NEW_RACE_BOUNDARY_PASS_REQUIRED')
    worker=(HERE/'candidate/controller/nvidia_worker.py').read_bytes()
    need(sha(worker)==cpu['sourceSHA256'],'CANDIDATE_CHANGED_AFTER_TEST')
    baseline=(HERE/'baseline/nvidia_worker.py').read_bytes()
    need(sha(baseline)=='d5bf03d4b79d70411c02d542bbebd08d9df0463636f558f02ee271c259b6b3d9','BASE_WORKER_PIN')
    start=worker.index(b'    # The worker can read initial state before the parent publishes its PID.\n')
    end=worker.index(b'    original = lease_helper()\n',start)
    need(worker[:start]+worker[end:]==baseline,'ONLY_LAUNCH_BARRIER_MAY_CHANGE')
    runtime_raw=(HERE/'baseline/RUNTIME_SOURCE_MANIFEST.json').read_bytes()
    need(sha(runtime_raw)==OLD_RUNTIME,'BASE_RUNTIME_PIN')
    runtime=json.loads(runtime_raw)
    rows=[r for r in runtime['files'] if r['path']==WORKER]
    need(len(rows)==1 and rows[0]['sha256']==sha(baseline),'EXACT_WORKER_BASELINE')
    rows[0].update(bytes=len(worker),sha256=sha(worker));runtime_raw=encoded(runtime)
    bootstrap=(HERE/'baseline/bootstrap.py').read_bytes()
    need(sha(bootstrap)=='093b03586767c15c29d436f4feb9b0d6f47590da439b4662ed2e40e293324d71','BASE_BOOTSTRAP_PIN')
    needle=("SOURCE_SHA = '"+OLD_RUNTIME+"'").encode()
    need(bootstrap.count(needle)==1,'EXACT_SOURCE_PIN_REQUIRED')
    bootstrap=bootstrap.replace(needle,("SOURCE_SHA = '"+sha(runtime_raw)+"'").encode())
    startup_raw=(HERE/'baseline/STARTUP_MANIFEST.json').read_bytes()
    need(sha(startup_raw)=='5189b25317048d11afffe019c3796560ecacab30a628de8b0d58b3b9a547b04c','BASE_STARTUP_PIN')
    startup=json.loads(startup_raw);startup['runtimeManifestSHA256']=sha(runtime_raw)
    startup['files']['bootstrap.py']={'bytes':len(bootstrap),'sha256':sha(bootstrap)}
    startup_raw=encoded(startup)
    overlay={WORKER:worker,RUNTIME:runtime_raw,BOOTSTRAP:bootstrap,STARTUP:startup_raw}
    for path,raw in overlay.items():write(context/'overlay'/path,raw)
    entry=['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',ROOT+'/'+BOOTSTRAP,
        '--startup-manifest',ROOT+'/'+STARTUP,'--startup-manifest-sha256',sha(startup_raw),
        '--source-manifest',ROOT+'/'+RUNTIME,'--source-manifest-sha256',sha(runtime_raw),
        '--export-root','/world-storage']
    dockerfile=('FROM '+PARENT+'\nCOPY --chown=0:0 '+json.dumps(['overlay/',ROOT+'/'])+'\nENTRYPOINT '+json.dumps(entry)+'\n').encode()
    write(context/'Dockerfile',dockerfile)
    plan={'schema':'WORLD_ENGINE_WORKER_LAUNCH_PACKAGE_V16','parentImage':PARENT,
        'entrypoint':entry,'runtimeManifestSHA256':sha(runtime_raw),'startupManifestSHA256':sha(startup_raw),
        'overlay':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in overlay.items()],
        'cpuResultSHA256':sha(cpu_raw),'workerSHA256':sha(worker),'gpuStarts':0,'renders':0,'oldPASSReruns':0,
        'scope':'Reload and validate published worker identity before first save; required manifest/startup pins',
        'renderersChanged':False,'inputsChanged':False,'jsonSizeFixPreserved':True,
        'cleanupPolicyChanged':False,'statusLivenessGuardChanged':False,
        'incidentAttribution':'UNCONFIRMED; original state/launch not recovered'}
    write(context/'CONTEXT.json',encoded(plan));return plan
