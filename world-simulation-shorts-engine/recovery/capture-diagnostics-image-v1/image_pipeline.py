"""Pinned derivative packaging and focused image verification. Never deploys a GPU."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

BASE_DIGEST = 'sha256:abbdab6844bb27bd0d7ea0339a6242dd15805b0cd6446c9fd76d9ba6d86f3eb6'
SOURCE_COMMIT = 'bc76bbfacc9b8fab40e89c3eb8d85b94b3ae8dbb'
BASE_SOURCE_SHA = '138f5ff4761e2fa3589e15493ded5401afe1ec4dfa0dc5ad5a725e03e53b9270'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
BASE = Path('/opt/world-engine-handoffs/studio-v2/repo')
TARGET = '/opt/world-engine-handoffs/studio-diagnostics-v1/repo'
RECOVERY = 'world-simulation-shorts-engine/recovery/'
CTRL = RECOVERY + 'codex-to-gcube-handoff-v1/controller/'
MANIFEST = RECOVERY + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP = RECOVERY + 'studio-cold-start-v2'


def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def run(argv, *, seconds=120, data=None, allow_failure=False):
    p = subprocess.run(argv, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=seconds)
    need(allow_failure or p.returncode == 0, 'IMAGE_SUBPROCESS_FAILED')
    return p


def safe_source(root, relative):
    name = PurePosixPath(relative)
    need(not name.is_absolute() and '..' not in name.parts and str(name) == relative,
         'IMAGE_RELATIVE_PATH_REQUIRED')
    p = root / relative
    need(p.is_file() and not any(x.is_symlink() for x in (p, *p.parents)),
         'IMAGE_REGULAR_SOURCE_REQUIRED')
    return p.read_bytes()


def stage(args):
    context = args.context
    need(not context.exists(), 'IMAGE_NEW_CONTEXT_REQUIRED')
    original = safe_source(BASE, MANIFEST)
    need(sha(original) == BASE_SOURCE_SHA, 'IMAGE_FROZEN_MANIFEST_CHANGED')
    manifest = json.loads(original)
    need(len(manifest['files']) == 350, 'IMAGE_BASE_INVENTORY_CHANGED')
    startup_raw = safe_source(BASE, STARTUP + '/STARTUP_MANIFEST.json')
    startup = json.loads(startup_raw)
    need(startup['runtimeManifestSHA256'] == BASE_SOURCE_SHA
         and set(startup['files']) == {'bootstrap.py', 'worker.py'}, 'IMAGE_STARTUP_CONTRACT_CHANGED')
    candidate_manifest = json.loads(safe_source(args.payload, RECOVERY+'capture-diagnostics-local/BACKUP_MANIFEST.json'))
    candidates = {r['path']: r for r in candidate_manifest['files']}
    repo = context / 'repo'
    repo.mkdir(parents=True, mode=0o755)
    for row in manifest['files']:
        raw = safe_source(BASE, row['path'])
        need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'IMAGE_BASE_BYTES_CHANGED')
        dest = repo / row['path']; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    for name, row in startup['files'].items():
        raw = safe_source(BASE, STARTUP + '/' + name)
        need(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'IMAGE_STARTUP_BYTES_CHANGED')
        dest = repo / STARTUP / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    changed = {}
    for name in ('nvidia_worker.py', 'safe_capture_export.py', 'capture_diagnostics_safe.py'):
        relative = CTRL + name
        raw = safe_source(args.payload, relative)
        pin = candidates[relative]
        need(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'IMAGE_CANDIDATE_BYTES_CHANGED')
        (repo / relative).write_bytes(raw)
        changed[relative] = {'path': relative, 'bytes': len(raw), 'sha256': sha(raw)}
    # Only the worker's failure-export clause may differ; all other runtime rows stay exact.
    old = safe_source(BASE, CTRL+'nvidia_worker.py').decode()
    new = (repo/CTRL/'nvidia_worker.py').read_text()
    extra = """        # Diagnostics are best-effort and only exported after confirmed cleanup.
        # Never export raw stderr, approvals, or any private source files.
        if not unresolved and cleanup_verified:
            try:
                from capture_diagnostics_safe import export_after_cleanup
                export_after_cleanup(job, exports, state['executionDeadline'])
            except Exception:
                pass  # Preserve the original capture error and GPU cleanup result.
"""
    need(new.count(extra) == 1 and new.replace(extra, '') == old, 'IMAGE_UNAPPROVED_WORKER_DELTA')
    manifest['files'] = [changed.pop(row['path'], row) for row in manifest['files']]
    manifest['files'] += list(changed.values())
    manifest['files'].sort(key=lambda row: row['path'])
    manifest['derivation'] = {'parentManifestSHA256': BASE_SOURCE_SHA,
        'parentImageDigest': BASE_DIGEST, 'diagnosticSourceCommit': SOURCE_COMMIT,
        'originalSourceAndImagePreserved': True}
    derived = wire(manifest); source_sha = sha(derived)
    (repo/MANIFEST).write_bytes(derived)
    bootstrap = repo/STARTUP/'bootstrap.py'
    source = bootstrap.read_text()
    needle = "SOURCE_SHA = '" + BASE_SOURCE_SHA + "'"
    need(source.count(needle) == 1, 'IMAGE_EXACT_PIN_SUBSTITUTION_REQUIRED')
    bootstrap.write_text(source.replace(needle, "SOURCE_SHA = '"+source_sha+"'"))
    startup['runtimeManifestSHA256'] = source_sha
    for name in startup['files']:
        raw = (repo/STARTUP/name).read_bytes()
        startup['files'][name] = {'bytes':len(raw), 'sha256':sha(raw)}
    new_startup = wire(startup); startup_sha = sha(new_startup)
    (repo/STARTUP/'STARTUP_MANIFEST.json').write_bytes(new_startup)
    facts = {'schema':'WORLD_ENGINE_DIAGNOSTIC_IMAGE_DERIVATION_V1',
        'sourceCommit':SOURCE_COMMIT,'parentImageDigest':BASE_DIGEST,
        'parentRuntimeManifestSHA256':BASE_SOURCE_SHA,'runtimeManifestSHA256':source_sha,
        'startupManifestSHA256':startup_sha,'runtimeFiles':len(manifest['files']),
        'sourceRoot':TARGET,'productionFilesChanged':1,'newRuntimeModules':2,
        'startupLogicChanged':False,'startupHashPinUpdated':True,'gpuExecuted':False}
    (context/'DERIVATION.json').write_bytes(wire(facts))
    entry = ['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',
        TARGET+'/'+STARTUP+'/bootstrap.py','--startup-manifest',TARGET+'/'+STARTUP+'/STARTUP_MANIFEST.json',
        '--startup-manifest-sha256',startup_sha,'--source-manifest',TARGET+'/'+MANIFEST,
        '--source-manifest-sha256',source_sha,'--export-root','/world-storage']
    (context/'Dockerfile').write_text('\n'.join([
        'FROM '+IMAGE+'@'+BASE_DIGEST, 'USER 0',
        'RUN test ! -e /opt/world-engine-handoffs/studio-diagnostics-v1',
        'COPY --chown=0:0 repo/ '+TARGET+'/',
        'COPY --chown=0:0 DERIVATION.json /opt/world-engine-handoffs/studio-diagnostics-v1/DERIVATION.json',
        'RUN find /opt/world-engine-handoffs/studio-diagnostics-v1 -type d -exec chmod 0755 {} + && '
        'find /opt/world-engine-handoffs/studio-diagnostics-v1 -type f -exec chmod 0644 {} +',
        'LABEL world-engine.capture-diagnostics.parent="'+BASE_DIGEST+'"',
        'LABEL org.opencontainers.image.source="https://github.com/dimon3898-sys/yeonhwarok-free"',
        'ENTRYPOINT '+json.dumps(entry), 'CMD []','']))
    need(sha(safe_source(BASE, MANIFEST)) == BASE_SOURCE_SHA
        and safe_source(BASE, STARTUP+'/STARTUP_MANIFEST.json') == startup_raw,
        'IMAGE_PARENT_MODIFIED')
    print(json.dumps({'stage':'DERIVED_CONTEXT_CREATED', **facts},sort_keys=True))


def validate(args):
    support = args.payload/'support'
    test_dir = args.context/'repo'/STARTUP/'tests'
    test_dir.mkdir(parents=True, exist_ok=False)
    suite = (support/'container_suite.py').read_text().replace(str(BASE), TARGET)
    probe = (support/'container_probe.py').read_text().replace(str(BASE), TARGET)
    tree = ast.parse(suite)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Suite')
    execute = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    kept, current = [], None
    keep = {'default_entrypoint_setup_owner_plan_and_term','missing_owner_blocks_before_listener'}
    selected = set()
    for node in execute.body:
        if (isinstance(node, ast.Assign) and len(node.targets)==1
                and isinstance(node.targets[0], ast.Attribute) and node.targets[0].attr=='active_case'
                and isinstance(node.value, ast.Constant)):
            current = node.value.value
        if current in keep:
            kept.append(node); selected.add(current)
    need(selected == keep, 'IMAGE_TEST_SELECTION_CHANGED')
    execute.body = kept
    (test_dir/'container_suite.py').write_text(ast.unparse(tree)+'\n')
    (test_dir/'container_probe.py').write_text(probe)
    result = run(['python3',str(test_dir/'container_suite.py'),'--repo',str(args.context/'repo'),
        '--image',args.image,'--result',str(args.result)],seconds=360,allow_failure=True)
    report = json.loads(args.result.read_bytes()) if args.result.exists() else {}
    need(result.returncode==0 and report.get('status')=='PASS'
         and report.get('defaultEntrypointVerified') is True and report.get('testContainersRemoved') is True
         and report.get('renderExecuted') is False,'IMAGE_DERIVED_STARTUP_FAILED')
    # Read installed receipt contract and source pins in the actual derivative, not a source mount.
    inspect_code = """import hashlib,json,os,sys,importlib.util,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
root=Path('/opt/world-engine-handoffs/studio-diagnostics-v1/repo')
rel='world-simulation-shorts-engine/recovery/'
manifest=root/rel/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
facts=json.loads(Path('/opt/world-engine-handoffs/studio-diagnostics-v1/DERIVATION.json').read_bytes())
startup=root/rel/'studio-cold-start-v2'
spec=importlib.util.spec_from_file_location('packaged_bootstrap',startup/'bootstrap.py')
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
b.verify_startup(startup/'STARTUP_MANIFEST.json',facts['startupManifestSHA256'])
serve,contract=b.source_contract(manifest,facts['runtimeManifestSHA256'])
assert len(contract.files)==352
ctrl=root/rel/'codex-to-gcube-handoff-v1/controller';sys.path.insert(0,str(ctrl))
from capture_diagnostics_safe import export_after_cleanup
with tempfile.TemporaryDirectory() as td:
 job=Path(td)/('studio-'+'a'*32);job.mkdir(mode=0o700);exports=Path(td)/'exports';exports.mkdir()
 for name,value in [('FIRST_CAPTURE_FAILURE.json',{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME'}),('LEASE_SUPERVISOR_RESULT.json',{'cleanupVerified':True,'reason':'GCUBE_CAPTURE_RUNTIME_FAILED'})]:
  f=job/name;f.write_text(json.dumps(value));f.chmod(0o600)
 result=export_after_cleanup(job,exports,(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat())
 assert result['status']=='EXPORTED'
 dest=exports/('capture-diagnostic-'+job.name)
 raw=(dest/'CAPTURE_DIAGNOSTIC.json').read_bytes()
 assert json.loads(raw)['firstFailure']['code']=='GCUBE_CAPTURE_RUNTIME_FAILED'
 assert (dest/'SHA256SUMS').read_text().startswith(hashlib.sha256(raw).hexdigest())
old=Path('/opt/world-engine-handoffs/studio-v2/repo')/rel/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
assert hashlib.sha256(old.read_bytes()).hexdigest()==facts['parentRuntimeManifestSHA256']
print(json.dumps({'status':'INSTALLED_DERIVATIVE_DIAGNOSTIC_PASS','sourceFiles':352,'parentPreserved':True,'gpuExecuted':False}))
"""
    probe_run = run(['docker','run','--rm','--network','none','--read-only',
        '--user','1000:1000','--tmpfs','/tmp:rw,nosuid,nodev,mode=1777',
        '--entrypoint','/usr/bin/python3',args.image,'-I','-c',inspect_code],seconds=45)
    proof=json.loads(probe_run.stdout)
    need(proof.get('status')=='INSTALLED_DERIVATIVE_DIAGNOSTIC_PASS','IMAGE_DIAGNOSTIC_INSTALL_FAILED')
    report['installedDiagnostic']=proof
    report['selectedStartupCases']=sorted(keep)
    args.result.write_bytes(wire(report))
    print(json.dumps({'stage':'DERIVED_IMAGE_CPU_VERIFIED','report':report},sort_keys=True))


def registry_get(reference):
    scope='repository:dimon3898-sys/world-simulation-shorts-engine:pull'
    with urllib.request.urlopen('https://ghcr.io/token?'+urllib.parse.urlencode(
            {'service':'ghcr.io','scope':scope}), timeout=30) as response:
        token=json.loads(response.read(65537))['token']
    req=urllib.request.Request('https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/'+reference,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json','Accept-Encoding':'identity'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw=response.read(4194305); digest=response.headers.get('Docker-Content-Digest')
        need(len(raw)<=4194304 and digest=='sha256:'+sha(raw),'IMAGE_REGISTRY_DIGEST_MISMATCH')
        value=json.loads(raw)
        return {'status':200,'digest':digest,'configDigest':value['config']['digest']}
    except urllib.error.HTTPError as error:
        if error.code==404:
            return {'status':404}
        raise RuntimeError('IMAGE_REGISTRY_READ_FAILED') from None


def publish(args):
    need(os.environ.get('GITHUB_REPOSITORY')=='dimon3898-sys/yeonhwarok-free'
         and os.environ.get('GITHUB_REF')=='refs/heads/recovery/world-engine-capture-diagnostics-local-20261028'
         and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','IMAGE_APPROVED_RUN_REQUIRED')
    tag='capture-diag-v1-'+os.environ['GITHUB_SHA'][:12]+'-'+os.environ['GITHUB_RUN_ID']
    need(args.image==IMAGE+':'+tag,'IMAGE_UNIQUE_TAG_REQUIRED')
    report=json.loads(args.result.read_bytes())
    info=json.loads(run(['docker','image','inspect',args.image]).stdout)[0]
    need(report['status']=='PASS' and report['imageConfigDigest']==info['Id']
         and report['gpuExecuted'] is False
         and report['installedDiagnostic']['status']=='INSTALLED_DERIVATIVE_DIAGNOSTIC_PASS',
         'IMAGE_TESTED_BYTES_REQUIRED')
    need(registry_get(tag)['status']==404,'IMAGE_TAG_ALREADY_EXISTS')
    token=os.environ.get('GH_TOKEN');actor=os.environ.get('GITHUB_ACTOR')
    need(bool(token and actor),'IMAGE_REGISTRY_AUTH_REQUIRED')
    run(['docker','login','ghcr.io','-u',actor,'--password-stdin'],data=token.encode(),seconds=30)
    try:
        run(['docker','push',args.image],seconds=180)
    finally:
        run(['docker','logout','ghcr.io'],seconds=15,allow_failure=True)
    remote=registry_get(tag)
    need(remote.get('configDigest')==info['Id'],'IMAGE_PUBLISHED_CONFIG_CHANGED')
    derivation=json.loads((args.context/'DERIVATION.json').read_bytes())
    final={'status':'DIAGNOSTIC_IMAGE_CPU_VERIFIED_PUBLISHED', 'image':args.image,
        'digest':remote['digest'],'configDigest':info['Id'],'derivation':derivation,
        'sourceBackupVerified':True,'gpuExecuted':False,'originalGpuRootCause':'UNKNOWN',
        'dropboxRemoteReadback':False,'gcubeUpdated':False,'deployReady':False,
        'startupCases':len(report['cases']),'installedDiagnostic':report['installedDiagnostic']}
    (args.context/'PUBLISH_RESULT.json').write_bytes(wire(final))
    print(json.dumps(final,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=('stage','validate','publish'))
    p.add_argument('--payload',type=Path,default=Path('/payload'))
    p.add_argument('--context',type=Path,required=True)
    p.add_argument('--image')
    p.add_argument('--result',type=Path)
    a=p.parse_args()
    try:
        globals()[a.mode](a)
    except Exception as error:
        code=str(error)
        print(json.dumps({'status':'BLOCKED','stage':a.mode,
            'code':code if re.fullmatch(r'IMAGE_[A-Z_]+',code) else 'IMAGE_OPERATION_FAILED',
            'exceptionType':type(error).__name__,'gpuExecuted':False}))
        raise SystemExit(1) from None
