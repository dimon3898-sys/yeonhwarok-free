"""Three-file additive package over the existing native image; no rendering."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726'
PARENT = IMAGE + '@' + PARENT_DIGEST
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
RECOVERY = 'world-simulation-shorts-engine/recovery/'
WORKER = RECOVERY + 'codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
RUNTIME = RECOVERY + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP = RECOVERY + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = RECOVERY + 'studio-cold-start-v2/bootstrap.py'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
def need(value, code):
    if not value: raise RuntimeError(code)
def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(raw)
    path.chmod(0o644)

def prepare(context):
    need(not context.exists(), 'FRESH_CONTEXT_REQUIRED')
    cpu_raw = (HERE / 'evidence/CPU_RESULT.json').read_bytes()
    cpu = json.loads(cpu_raw)
    need(cpu['status'] == 'PASS' and cpu['uniqueTests'] == 10 and cpu['existingPassReruns'] == 0,
         'NEW_BOUNDARY_CPU_PASS_REQUIRED')
    baseline = json.loads((HERE / 'BASELINE.json').read_bytes())
    worker = (HERE / 'candidate/controller/nvidia_worker.py').read_bytes()
    need(sha(worker) == baseline['candidateSHA256'], 'CANDIDATE_CHANGED_AFTER_TEST')
    runtime_raw = (HERE / 'BASE_RUNTIME_SOURCE_MANIFEST.json').read_bytes()
    startup_raw = (HERE / 'BASE_STARTUP_MANIFEST.json').read_bytes()
    need(sha(runtime_raw) == 'f007273ae3dbb4ddead292e0c325b9a16eb7fb2680133d96ac8c3cb0cc14eab1', 'BASE_RUNTIME_PIN')
    need(sha(startup_raw) == '6956261376cad8c409671ba9a50c6cf29c508a9d903cafb79e52f72c3aa2f87a', 'BASE_STARTUP_PIN')
    runtime, startup = json.loads(runtime_raw), json.loads(startup_raw)
    rows = [r for r in runtime['files'] if r['path'] == WORKER]
    need(len(rows) == 1 and rows[0]['sha256'] == baseline['originalSHA256'], 'INSTALLED_WORKER_BASELINE')
    need(len(runtime['files']) == 361, 'EXACT_RUNTIME_ROWS')
    rows[0].update(sha256=sha(worker), bytes=len(worker))
    runtime_raw = encoded(runtime)
    startup['runtimeManifestSHA256'] = sha(runtime_raw)
    startup_raw = encoded(startup)
    overlay = {WORKER: worker, RUNTIME: runtime_raw, STARTUP: startup_raw}
    for name, raw in overlay.items(): write(context / 'overlay' / name, raw)
    entry = ['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',ROOT+'/'+BOOTSTRAP,
        '--startup-manifest',ROOT+'/'+STARTUP,'--startup-manifest-sha256',sha(startup_raw),
        '--source-manifest',ROOT+'/'+RUNTIME,'--source-manifest-sha256',sha(runtime_raw),
        '--export-root','/world-storage']
    dockerfile = ('FROM '+PARENT+'\nCOPY --chown=0:0 '+json.dumps(['overlay/', ROOT+'/'])+'\nENTRYPOINT '+json.dumps(entry)+'\n').encode()
    write(context / 'Dockerfile', dockerfile)
    plan = {'schema':'WORLD_ENGINE_CAPTURE_JSON_PACKAGE_V13','parentImage':PARENT,
        'entrypoint':entry,'runtimeManifestSHA256':sha(runtime_raw),'startupManifestSHA256':sha(startup_raw),
        'overlay':[{'path':p,'sha256':sha(b),'bytes':len(b)} for p,b in overlay.items()],
        'cpuResultSHA256':sha(cpu_raw),'dockerfileSHA256':sha(dockerfile),
        'renderersChanged':False,'inputsChanged':False,'oldPASSReruns':0,'gpuStarts':0,
        'scope':'Only post-capture frame-ledger reader and required source/startup hashes'}
    write(context / 'CONTEXT.json', encoded(plan))
    return plan
