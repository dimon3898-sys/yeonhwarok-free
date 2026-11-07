"""Package already validated bytes; never generate inputs, frames or new terrain."""
import hashlib
import json
from pathlib import Path
import zipfile

REC = 'world-simulation-shorts-engine/recovery/'
HERE = 'world-simulation-shorts-engine/production/korean-war-20s-deployment-v11/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
PARENT_DIGEST = 'sha256:af3ad26a305c160a916ac231122a31824cbee4759338c044bab0d6c9dab1691a'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT = IMAGE + '@' + PARENT_DIGEST

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
def need(value, code):
    if not value: raise RuntimeError(code)
def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(raw)
    path.chmod(0o644)

def prepare(repo, prior, context):
    pins = json.loads((repo / HERE / 'EVIDENCE_PINS.json').read_bytes())
    need(not context.exists(), 'FRESH_CONTEXT_REQUIRED')
    for name, digest in pins['files'].items():
        need(sha((prior/name).read_bytes()) == digest, 'PRIOR_EVIDENCE_CHANGED:' + name)
    seal = json.loads((prior/'VIEWPORT_SOURCE_SEAL.json').read_bytes())
    need(seal['parentImage'] == PARENT and len(seal['files']) == 17, 'SOURCE_PARENT_OR_ROWS_CHANGED')
    overlay = {}
    with zipfile.ZipFile(prior/'VIEWPORT_OVERLAY.zip') as archive:
        need(set(archive.namelist()) == {'overlay/'+row['path'] for row in seal['files']}, 'EXACT_OVERLAY_REQUIRED')
        for row in seal['files']:
            path = row['path']
            need(not Path(path).is_absolute() and '..' not in Path(path).parts, 'UNSAFE_PATH')
            raw = archive.read('overlay/'+path)
            need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'OVERLAY_BYTES_CHANGED')
            overlay[path] = raw
    for row in seal['inputs']:
        raw = (prior/Path(row['path']).name).read_bytes()
        need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'INPUT_BYTES_CHANGED')
        overlay[row['path']] = raw
    with zipfile.ZipFile(prior/'KW20_PINNED_SOURCE_CROP.zip') as archive:
        for row in seal['assets']:
            raw = archive.read(Path(row['path']).name)
            need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'TERRAIN_BYTES_CHANGED')
            overlay[row['path']] = raw
    with zipfile.ZipFile(prior/'KW20_DETAIL_EVIDENCE.zip') as archive:
        evidence = json.loads(archive.read('RUN_RESULT.json'))
        need(evidence['status'] == 'PASS' and evidence['sourceCommit'] == pins['validatedCommit'], 'EXISTING_VIEWPORT_PASS_REQUIRED')
        expected_scenes = []
        for index in (1, 2):
            analysis = json.loads(archive.read(f'check/ANALYSIS_{index}.json'))
            need(analysis['status'] == 'PASS' and analysis['totalFrames'] == 300, 'EXISTING_ANALYSIS_REQUIRED')
            expected_scenes.append([r['scene'] for r in analysis['renderRequests']])
        compose = archive.read('check/COMPOSE_PLAN.json')
        need(json.loads(compose)['durationSeconds'] == 20, 'EXISTING_COMPOSE_PLAN_REQUIRED')
        overlay[HERE+'COMPOSE_PLAN.json'] = compose
    runtime = json.loads(overlay[RUNTIME]); startup = json.loads(overlay[STARTUP])
    need(sha(overlay[RUNTIME]) == seal['runtimeManifestSHA256'], 'RUNTIME_PIN')
    need(startup['runtimeManifestSHA256'] == seal['runtimeManifestSHA256'], 'STARTUP_RUNTIME_PIN')
    need(sha(overlay[STARTUP]) == seal['startupManifestSHA256'], 'STARTUP_PIN')
    need(startup['files']['bootstrap.py'] == {'bytes':len(overlay[BOOTSTRAP]), 'sha256':sha(overlay[BOOTSTRAP])}, 'BOOTSTRAP_PIN')
    need(len(runtime['files']) == 361, 'RUNTIME_COUNT')
    context.mkdir(mode=0o755)
    for path, raw in overlay.items(): write(context/'overlay'/path, raw)
    entry = ['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',ROOT+'/'+BOOTSTRAP,
        '--startup-manifest',ROOT+'/'+STARTUP,'--startup-manifest-sha256',seal['startupManifestSHA256'],
        '--source-manifest',ROOT+'/'+RUNTIME,'--source-manifest-sha256',seal['runtimeManifestSHA256'],'--export-root','/world-storage']
    dockerfile = ('FROM '+PARENT+'\nCOPY --chown=0:0 '+json.dumps(['overlay/', ROOT+'/'])+'\nENTRYPOINT '+json.dumps(entry)+'\n').encode()
    write(context/'Dockerfile', dockerfile)
    plan = {'schema':'WORLD_ENGINE_NATIVE_KW20_PACKAGE_V11','status':'PREPARED_NOT_VALIDATED',
        'parentImage':PARENT,'parentDigest':PARENT_DIGEST,'runtimeManifestSHA256':seal['runtimeManifestSHA256'],
        'startupManifestSHA256':seal['startupManifestSHA256'],'runtimeSourceRows':361,'entrypoint':entry,
        'overlay':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in overlay.items()],
        'inputs':seal['inputs'],'expectedScenes':expected_scenes,'sourceArtifact':pins['artifact'],
        'unchangedContractPins':pins['unchangedContractPins'],
        'reusedViewportRegression':pins['validatedCommit'],'oldPASSReruns':0,'gpuStarts':0,'renders':0,
        'dockerfileSHA256':sha(dockerfile)}
    write(context/'CONTEXT.json',encoded(plan))
    for directory in context.rglob('*'):
        if directory.is_dir(): directory.chmod(0o755)
    return plan
