#!/usr/bin/env python3
"""Small additive CI adapter over the immutable, already verified free builder.

Never deploys gCube, invokes a renderer, requests hardware GPUs, or changes an
existing tag. Container tests exercise the actual new Studio import/guard path.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'universal-overnight-v3/ci_package.py'
if hashlib.sha256(FROZEN.read_bytes()).hexdigest() != '2572fc96cce0e464b894f08f2d8775cf3ae5664f0e2d385abf2a4d6abe194340':
    raise RuntimeError('RECONCILIATION_FROZEN_CI_CHANGED')
spec = importlib.util.spec_from_file_location('_reconciliation_verified_ci', FROZEN)
parent_ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_ci)
ci = parent_ci.ci
ci.HERE = HERE
ci.NAMESPACE = 'world-simulation-shorts-engine/recovery/render-path-reconciliation-v1'
ci.WORKFLOW = '.github/workflows/world-engine-reconciliation-v1.yml'
ci.BRANCH = 'development/5s-render-reconciliation-20261020'
ci.BASE_DIGEST = 'sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645'
ci.BASE = ci.IMAGE + '@' + ci.BASE_DIGEST
ci.DEST = '/opt/rtx-package/repo/' + ci.NAMESPACE
ci.TAG = re.compile(r'reconcile-v1-[a-f0-9]{7,12}-[1-9][0-9]*-[1-9][0-9]*\Z')
MANIFEST = 'RECONCILIATION_FILES.json'
PARENT_SHA = 'ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7'
BASE_COMMIT = '1c34f688908e87520d60b578484eea3d9940ed6e'


def location():
    path = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'world-engine-reconciliation-v1-package'
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


ci.location = location
_original_state = ci.state


def state():
    value = _original_state()
    value['schema'] = 'WORLD_ENGINE_RECONCILIATION_IMAGE_CPU_V1'
    value['status'] = value['status'].replace('STUDIO_HTTPS_CANDIDATE', 'RECONCILIATION_CANDIDATE').replace('OVERNIGHT_CANDIDATE', 'RECONCILIATION_CANDIDATE')
    value.update(gpuExecuted=False, nvidiaHardwareVerified=False, paidWorkExecuted=False, gCubeDeployed=False)
    return value


ci.state = state


def _manifest(root):
    path = Path(root) / MANIFEST
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024**2:
        raise RuntimeError('RECONCILIATION_BOUNDED_MANIFEST_REQUIRED')
    value = json.loads(path.read_bytes())
    if (value.get('schema') != 'WORLD_ENGINE_RECONCILIATION_FILES_V1'
            or value.get('baseOperatingImageDigest') != ci.BASE_DIGEST
            or value.get('previousManifestSHA256') != PARENT_SHA
            or not isinstance(value.get('files'), dict) or not value['files']):
        raise RuntimeError('RECONCILIATION_PARENT_BOUND_MANIFEST_REQUIRED')
    for name, digest in value['files'].items():
        if (not isinstance(name, str) or Path(name).name != name or '\\' in name or name in {'.', '..'}
                or not ci.HASH.fullmatch(str(digest))):
            raise RuntimeError('RECONCILIATION_PACKAGE_PATH_INVALID')
    return value


def payload_context(*, root=HERE):
    manifest = _manifest(root)
    if not {'bootstrap.py', 'studio_entry.py', 'studio_controller.py', 'runtime_bridge.py',
            'package_manifest.py', 'native_capabilities.py'} <= set(manifest['files']):
        raise RuntimeError('RECONCILIATION_CONNECTED_ENTRY_REQUIRED')
    context = Path(tempfile.mkdtemp(prefix='payload-', dir=location()))
    payload = context / 'reconciliation'
    payload.mkdir(mode=0o755)
    for name in sorted({*manifest['files'], MANIFEST}):
        source = Path(root) / name
        if (any(p.is_symlink() for p in (source, *source.parents)) or not source.is_file()
                or not 0 < source.stat().st_size <= 16 * 1024**2
                or (name in manifest['files'] and ci.sha(source) != manifest['files'][name])):
            raise RuntimeError('RECONCILIATION_REGULAR_SHA_SOURCE_REQUIRED')
        shutil.copyfile(source, payload / name)
    dockerfile = Path(root) / 'Dockerfile'
    if dockerfile.is_symlink() or not dockerfile.is_file():
        raise RuntimeError('RECONCILIATION_REGULAR_DOCKERFILE_REQUIRED')
    shutil.copyfile(dockerfile, context / 'Dockerfile')
    return context


def source_protection():
    changed = ci.run(['git', 'diff', '--name-only', BASE_COMMIT, 'HEAD']).stdout.splitlines()
    disallowed = [name for name in changed if not (name.startswith(ci.NAMESPACE + '/') or name == ci.WORKFLOW)]
    if disallowed:
        raise RuntimeError('RECONCILIATION_PROTECTED_SOURCE_CHANGED')
    return {'status': 'PASS', 'baseCommit': BASE_COMMIT, 'protectedChanged': 0,
        'allowedNamespace': ci.NAMESPACE, 'oldImagesDeleted': False}


def preflight():
    value = ci.state()
    value.update(builder=ci.require_free_runner(), sourceProtection=source_protection())
    commit = os.environ.get('GITHUB_SHA', '')
    if not ci.COMMIT.fullmatch(commit):
        raise RuntimeError('RECONCILIATION_SOURCE_COMMIT_REQUIRED')
    tag = 'reconcile-v1-' + commit[:10] + '-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not ci.TAG.fullmatch(tag):
        raise RuntimeError('RECONCILIATION_UNIQUE_TAG_REQUIRED')
    value.update(tag=tag, image=ci.IMAGE + ':' + tag)
    ci.save(value)


def container(image, *, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=6g', '--cpus=2',
        '--pids-limit=256', '--restart=no', '--shm-size=2g', '--tmpfs', '/tmp:rw,mode=1777']
    if context:
        command += ['--mount', 'type=bind,source=' + str(context / 'reconciliation') + ',target=' + ci.DEST + ',readonly']
    return command + ['--entrypoint=/usr/bin/python3', image, '-B']


def source_code():
    return ("import importlib.util,json,sys,os;os.setgroups([]);os.setgid(1000);os.setuid(1000);"
        "sys.path.insert(0,'/opt/world-engine-studio-https-proxy-fix');"
        "from manifest import verify_sources as frozen_verify;frozen=frozen_verify();"
        "s=importlib.util.spec_from_file_location('_reconciliation_ci_sources','" + ci.DEST + "/package_manifest.py');"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);new=m.verify_sources();"
        "print(json.dumps({'status':'PASS','reconciliation':new,'frozen':frozen,'gpuExecuted':False}))")


def image_hashes(image, context=None):
    result = ci.record('actual-container-source-hashes', container(image, context=context) + ['-c', source_code()], timeout=180)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    expected = ci.sha((context / 'reconciliation' if context else HERE) / MANIFEST)
    if (report.get('status') != 'PASS' or report.get('gpuExecuted') is not False
            or report.get('reconciliation', {}).get('manifestSHA256') != expected
            or report['reconciliation'].get('parentFiles') != 82
            or report['reconciliation'].get('previousManifestSHA256') != PARENT_SHA
            or report.get('frozen', {}).get('status') != 'PASS'):
        raise RuntimeError('RECONCILIATION_CONTAINER_SOURCE_HASH_MISMATCH')
    return report


ci.image_hashes = image_hashes


def inspect_image(image):
    row = json.loads(ci.run(['docker', 'image', 'inspect', image]).stdout)[0]
    config = row.get('Config', {})
    labels = config.get('Labels', {})
    expected = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', ci.DEST + '/bootstrap.py']
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != expected
            or labels.get('world-engine.reconciliation.parent-digest') != ci.BASE_DIGEST
            or labels.get('world-engine.reconciliation.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('RECONCILIATION_IMAGE_PROVENANCE_REQUIRED')
    if set(item.partition('=')[0] for item in config.get('Env', [])) & {
            'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
            'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON',
            'DROPBOX_REFRESH_TOKEN', 'WORLD_ENGINE_BACKUP_KEY'}:
        raise RuntimeError('RECONCILIATION_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('RECONCILIATION_EXISTING_HEALTHCHECK_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
        'entrypoint': expected, 'platform': 'linux/amd64', 'secretEnvironmentPresent': False, 'gpuExecuted': False}


ci.inspect_image = inspect_image


def startup_probe_code():
    body = r"""
import importlib.util,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, '__DEST__')
import studio_entry,runtime_bridge,native_capabilities
request={'schema':'WORLD_ENGINE_OVERNIGHT_VISUAL_V1','scalarTerritory':None,'nationalUnits':None}
guard=native_capabilities.guard_native_selection(request)
assert guard['status']=='NATIVE_GUARD_PASSED'
actual_bridge=studio_entry.controller.bridge
selected={**request,'scalarTerritory':{'sourceRef':'CPU_CONTAINER_MOCK_SOURCE_ADMISSION_ONLY'}}
mock_context={'selectedVisualAdmission':{'status':'CPU_ADMITTED','scalarControlSelected':True,'nationalUnitsSelected':False}}
with patch.object(actual_bridge,'_preserved_gate_context',return_value=mock_context), patch.object(actual_bridge.preserved,'load',side_effect=AssertionError('GPU_MANAGER_MUST_NOT_LOAD')):
    blocked=actual_bridge.preflight({'overnightV3':{'visualExtensions':selected}},control_root=Path('/unused'),export_root=Path('/unused'),image_digest='CPU_CONTAINER_TEST_ONLY')
assert blocked['renderAllowed'] is False
assert blocked['checks'][0]['code']=='RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE'
os.environ['WORLD_ENGINE_STUDIO_STATE_ROOT']='/tmp/reconciliation-owner-negative'
os.environ.pop('WORLD_ENGINE_STUDIO_OWNER_CODE',None)
s=importlib.util.spec_from_file_location('_reconciliation_negative_boot','__DEST__/bootstrap.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:
    with patch('subprocess.Popen',side_effect=AssertionError('NO_PROCESS_ALLOWED')):
        m.main([])
except Exception as error:
    code=getattr(error,'code',None) or str(error)
    if code!='STUDIO_OWNER_CONFIGURATION_REQUIRED':
        raise
    print(json.dumps({'status':'PASS','studioImportVerified':True,'nativeGuardVerified':True,'selectedScalarBlockedBeforeManager':True,'selectedScalarScope':'MOCK_SOURCE_RECEIPT_ACTUAL_STUDIO_NATIVE_GUARD','historicalSourceAdmissionVerified':False,'errorCode':code,'renderStarted':False,'gpuExecuted':False}))
else:
    raise RuntimeError('RECONCILIATION_MISSING_OWNER_DID_NOT_FAIL')
"""
    return body.replace('__DEST__', ci.DEST)


def test():
    ci.require_free_runner()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    context = payload_context()
    value = ci.state()
    value['testContext'] = str(context)
    ci.save(value)
    hashes = image_hashes(ci.BASE, context)
    result = ci.record('actual-container-studio-guard-and-owner-fail-closed',
        container(ci.BASE, context=context) + ['-c', startup_probe_code()], timeout=180)
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    value = ci.state()
    value.update(testsStatus='PASS', testSourceHashes=hashes,
        actualStudioGuardAndOwnerNegative=probe, sourceProtection=source_protection())
    ci.save(value)


def stage():
    value = ci.state()
    if value.get('testsStatus') != 'PASS':
        raise RuntimeError('RECONCILIATION_CPU_CONTAINER_TESTS_REQUIRED')
    context = payload_context()
    if ((context / 'reconciliation' / MANIFEST).read_bytes()
            != (Path(value['testContext']) / 'reconciliation' / MANIFEST).read_bytes()):
        raise RuntimeError('RECONCILIATION_TESTED_CONTEXT_CHANGED')
    value.update(context=str(context), extensionManifestSha256=ci.sha(context / 'reconciliation' / MANIFEST),
        dockerfileSha256=ci.sha(context / 'Dockerfile'))
    ci.save(value)


def build():
    value = ci.state()
    ci.require_free_runner()
    if value.get('testsStatus') != 'PASS' or not value.get('context'):
        raise RuntimeError('RECONCILIATION_TESTED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (ci.sha(context / 'reconciliation' / MANIFEST) != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('RECONCILIATION_FROZEN_CONTEXT_CHANGED')
    result = ci.run(['docker', 'build', '--platform=linux/amd64', '--network=none',
        '--file', str(context / 'Dockerfile'), '--label',
        'world-engine.reconciliation.source-revision=' + os.environ['GITHUB_SHA'],
        '--tag', value['image'], str(context)], timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode,
        'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    ci.save(value)
    if result.returncode:
        raise RuntimeError('RECONCILIATION_IMAGE_BUILD_FAILED')
    value = ci.state()
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    ci.save(value)


def verify():
    value = ci.state()
    if not value.get('imageBuilt'):
        raise RuntimeError('RECONCILIATION_BUILT_IMAGE_REQUIRED')
    hashes = image_hashes(value['image'])
    scan = ci.secret_scan()
    value = ci.state()
    value.update(imageHashes=hashes, secretScan=scan, verification='PASS')
    ci.save(value)


def pull():
    ci.pull()
    value = ci.state()
    if value.get('pullVerified') is not True or value.get('imageHashes', {}).get('status') != 'PASS':
        raise RuntimeError('RECONCILIATION_INDEPENDENT_PULL_REQUIRED')
    value['imageProof'] = {'schema': 'WORLD_ENGINE_RECONCILIATION_IMAGE_PROOF_V1',
        'imageDigest': value['imageDigest'], 'sourceManifestSHA256': ci.sha(HERE / MANIFEST),
        'sourceCommit': os.environ['GITHUB_SHA'], 'independentPullVerified': True,
        'sourceHashesVerified': True, 'baseDigest': ci.BASE_DIGEST, 'result': 'PASS',
        'gpuVerified': False, 'visualQualityApproved': False}
    # The preserved capture owner validates its own unchanged layer manifest,
    # not the newly added one. Attest that old layer again against the ACTUAL
    # independently pulled child digest; never copy its old image approval.
    compatibility = {'schema': 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_V1',
        'imageDigest': value['imageDigest'], 'sourceManifestSHA256': PARENT_SHA,
        'sourceCommit': os.environ['GITHUB_SHA'], 'independentPullVerified': True,
        'sourceHashesVerified': True,
        'baseDigest': 'sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886',
        'result': 'PASS'}
    ci.save(value)
    code = ("import importlib.util,json;"
        "s=importlib.util.spec_from_file_location('_retained_image_receipt','" + ci.DEST +
        "/../universal-overnight-v3/package_manifest.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "proof=json.loads(" + repr(json.dumps(compatibility, sort_keys=True)) + ");"
        "m.validate_image_proof(proof,source_manifest_sha256='" + PARENT_SHA +
        "',image_digest='" + value['imageDigest'] + "');"
        "print(json.dumps({'status':'PASS','retainedOwnerValidation':True,'gpuVerified':False}))")
    receipt = ci.record('actual-container-retained-image-proof-validation',
        container(value['imageReference']) + ['-c', code], timeout=180)
    if json.loads(receipt.stdout.strip().splitlines()[-1]).get('retainedOwnerValidation') is not True:
        raise RuntimeError('RECONCILIATION_RETAINED_PROOF_VALIDATION_REQUIRED')
    value = ci.state()
    value['retainedOvernightImageProof'] = compatibility
    value['dualAttestation'] = {'status': 'PASS',
        'newLayerManifest': value['imageProof']['sourceManifestSHA256'],
        'retainedLayerManifest': PARENT_SHA, 'sameIndependentlyPulledDigest': value['imageDigest'],
        'retainedOwnerValidatedInContainer': True, 'gpuVerified': False}
    ci.save(value)


def persist():
    value = ci.state()
    value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if 'failure' in value['stepOutcomes'].values():
        value['status'] = 'RECONCILIATION_CANDIDATE_BLOCKED'
    for name in ('context', 'testContext'):
        value.pop(name, None)
    phase = os.environ.get('RESULT_PHASE')
    run_id = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if phase not in {'build', 'pull'} or not re.fullmatch('[1-9][0-9]*-[1-9][0-9]*', run_id):
        raise RuntimeError('RECONCILIATION_BOUNDED_RESULT_REQUIRED')
    relative = Path(ci.NAMESPACE) / 'runs' / run_id
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 4 * 1024**2 or ci.SENSITIVE.search(raw.decode()):
        raise RuntimeError('RECONCILIATION_SAFE_EVIDENCE_REQUIRED')
    artifacts = {str(relative / (phase + '.json')): raw,
        str(relative / (phase + '.SHA256SUMS')): (hashlib.sha256(raw).hexdigest() + '  ' + phase + '.json\n').encode()}
    if phase == 'pull' and value.get('imageProof', {}).get('result') == 'PASS':
        proof = (json.dumps(value['imageProof'], indent=2) + '\n').encode()
        artifacts[str(relative / 'IMAGE_PROOF.json')] = proof
        artifacts[str(relative / 'IMAGE_PROOF.SHA256SUMS')] = (hashlib.sha256(proof).hexdigest() + '  IMAGE_PROOF.json\n').encode()
        if value.get('dualAttestation', {}).get('retainedOwnerValidatedInContainer') is True:
            compatibility = (json.dumps(value['retainedOvernightImageProof'], indent=2) + '\n').encode()
            compatibility_name = 'OLD_CAPTURE_COMPATIBILITY_IMAGE_PROOF.json'
            artifacts[str(relative / compatibility_name)] = compatibility
            artifacts[str(relative / 'OLD_CAPTURE_COMPATIBILITY_IMAGE_PROOF.SHA256SUMS')] = (hashlib.sha256(compatibility).hexdigest() + '  ' + compatibility_name + '\n').encode()
    ci.run(['git', 'fetch', '--filter=blob:none', 'origin', ci.BRANCH], timeout=180)
    ci.run(['git', 'switch', '--detach', 'FETCH_HEAD'])
    for name, raw in artifacts.items():
        target = ci.REPO / name
        if target.exists():
            raise RuntimeError('RECONCILIATION_EXISTING_EVIDENCE_PRESERVED')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    ci.run(['git', 'config', 'user.name', 'github-actions[bot]'])
    ci.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    ci.run(['git', 'add', '--sparse', '--', *sorted(artifacts)])
    if sorted(ci.run(['git', 'diff', '--cached', '--name-only']).stdout.splitlines()) != sorted(artifacts):
        raise RuntimeError('RECONCILIATION_BOUNDED_EVIDENCE_COMMIT_REQUIRED')
    ci.run(['git', 'diff', '--cached', '--check'])
    ci.run(['git', 'commit', '-m', 'docs(reconciliation): persist ' + phase + ' CPU image evidence [skip ci]'])
    ci.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + ci.BRANCH], timeout=180)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'))
    phase = parser.parse_args(argv).phase
    try:
        (globals().get(phase) or getattr(ci, phase))()
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'RECONCILIATION_CI_FAILED'
        value = ci.state()
        value.update(status='RECONCILIATION_CANDIDATE_BLOCKED', failedPhase=phase,
            reasonCode=code, errorType=type(error).__name__)
        ci.save(value)
        print(json.dumps({'status': value['status'], 'phase': phase, 'reasonCode': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
