"""Repair one stale startup pin. Preserve the v13 worker and all render data."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:c43c8514e471a68d0c150f01358a7fff0ee5d059e0b3da5b699bcf354b202da4'
PARENT = IMAGE + '@' + PARENT_DIGEST
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
RECOVERY = 'world-simulation-shorts-engine/recovery/'
RUNTIME = RECOVERY + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP = RECOVERY + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = RECOVERY + 'studio-cold-start-v2/bootstrap.py'
OLD_PIN = 'f007273ae3dbb4ddead292e0c325b9a16eb7fb2680133d96ac8c3cb0cc14eab1'
RUNTIME_PIN = 'c70ec44c260c73b1366c3a4e5b66285297d247f4d33739936d96887df141cdfd'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
def need(value, code):
    if not value: raise RuntimeError(code)
def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(raw)
    path.chmod(0o644)

def candidate():
    old = (HERE/'baseline/bootstrap.py').read_bytes()
    startup_raw = (HERE/'baseline/STARTUP_MANIFEST.json').read_bytes()
    need(sha(old) == '86dda271dd984e968def727bf9ef2ecbef1f308ab8573c008407dd1169d6162a', 'BASE_BOOTSTRAP_PIN')
    need(sha(startup_raw) == 'f8ca6ffe790a2c5fdf71b9b0212e51947dad5326812ab6532aeb96fc6ce17ab8', 'BASE_STARTUP_PIN')
    before = ("SOURCE_SHA = '" + OLD_PIN + "'").encode()
    after = ("SOURCE_SHA = '" + RUNTIME_PIN + "'").encode()
    need(old.count(before) == 1, 'EXACT_STALE_PIN_REQUIRED')
    new = old.replace(before, after)
    old_tree, new_tree = ast.parse(old), ast.parse(new)
    for tree in (old_tree, new_tree):
        rows = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_SHA' for t in n.targets)]
        need(len(rows) == 1, 'SINGLE_SOURCE_PIN')
        rows[0].value = ast.Constant(value='NORMALIZED_PIN')
    need(ast.dump(old_tree) == ast.dump(new_tree), 'ONLY_PIN_ASSIGNMENT_MAY_CHANGE')
    startup = json.loads(startup_raw)
    need(startup['runtimeManifestSHA256'] == RUNTIME_PIN, 'RUNTIME_ALREADY_CORRECT')
    startup['files']['bootstrap.py'] = {'bytes': len(new), 'sha256': sha(new)}
    return new, encoded(startup)

def prepare(context):
    need(not context.exists(), 'FRESH_CONTEXT_REQUIRED')
    cpu = json.loads((HERE/'evidence/CPU_RESULT.json').read_bytes())
    need(cpu['status'] == 'PASS' and cpu['oldPASSReruns'] == 0, 'NEW_STARTUP_BOUNDARY_PASS_REQUIRED')
    bootstrap, startup = candidate()
    need(sha(bootstrap) == cpu['bootstrapSHA256'] and sha(startup) == cpu['startupSHA256'], 'CANDIDATE_CHANGED_AFTER_CHECK')
    overlay = {BOOTSTRAP: bootstrap, STARTUP: startup}
    for name, raw in overlay.items(): write(context/'overlay'/name, raw)
    entry = ['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',ROOT+'/'+BOOTSTRAP,
        '--startup-manifest',ROOT+'/'+STARTUP,'--startup-manifest-sha256',sha(startup),
        '--source-manifest',ROOT+'/'+RUNTIME,'--source-manifest-sha256',RUNTIME_PIN,
        '--export-root','/world-storage']
    dockerfile = ('FROM '+PARENT+'\nCOPY --chown=0:0 '+json.dumps(['overlay/',ROOT+'/'])+'\nENTRYPOINT '+json.dumps(entry)+'\n').encode()
    write(context/'Dockerfile', dockerfile)
    plan = {'schema':'WORLD_ENGINE_COLD_START_PIN_PACKAGE_V14','parentImage':PARENT,
        'entrypoint':entry,'runtimeManifestSHA256':RUNTIME_PIN,'startupManifestSHA256':sha(startup),
        'overlay':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in overlay.items()],
        'cpuResultSHA256':sha((HERE/'evidence/CPU_RESULT.json').read_bytes()),
        'scope':'Bootstrap SOURCE_SHA assignment and its startup manifest row only',
        'gpuStarts':0,'renders':0,'oldPASSReruns':0,'runtimeSourcesChanged':False,
        'v13WorkerPreserved':True,'inputsChanged':False,'renderersChanged':False}
    write(context/'CONTEXT.json', encoded(plan))
    return plan
