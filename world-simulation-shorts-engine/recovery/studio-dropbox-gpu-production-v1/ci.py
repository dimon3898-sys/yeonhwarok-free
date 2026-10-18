#!/usr/bin/env python3
"""Free CPU packaging of one additive production credential adapter.

Reuse the SHA-pinned existing registry/scanner/transport helpers, never gCube.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-dropbox-gpu-production-v1'
BRANCH = 'development/dropbox-gpu-production-20261018'
WORKFLOW = '.github/workflows/studio-dropbox-gpu-production-v1.yml'
BASE_COMMIT = '00cae13c4ce009ac3e56a8db1cf52f08de60a3cd'
BASE_DIGEST = 'sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0'
DEST = '/opt/world-engine-studio-dropbox-gpu-production'
PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'
SECRET_NAMES = ('WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY',
                'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN')
MANIFEST = 'PRODUCTION_FILES.json'


def load_helper():
    path = HERE.parent / 'studio-dropbox-offline-v1/ci.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != 'f8c269c1940ad77211e44e67b5fde95d26c822055aa0dc2d7eaea2b49d112680':
        raise RuntimeError('PRODUCTION_FROZEN_CI_CHANGED')
    spec = importlib.util.spec_from_file_location('_production_existing_ci', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


helper = load_helper()
ci = helper.ci
ci.HERE, ci.REPO, ci.NAMESPACE, ci.BRANCH, ci.WORKFLOW = HERE, REPO, NAMESPACE, BRANCH, WORKFLOW
ci.BASE_DIGEST, ci.BASE, ci.DEST = BASE_DIGEST, ci.IMAGE + '@' + BASE_DIGEST, DEST
ci.TAG = re.compile(r'studio-dropbox-gpu-prod-v1-00cae13-[1-9][0-9]*-[1-9][0-9]*\Z')


def location():
    path = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-dropbox-gpu-production-package'
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


ci.location = location
previous_state = ci.state


def state():
    value = previous_state()
    value['schema'] = 'WORLD_ENGINE_DROPBOX_GPU_PRODUCTION_PACKAGE_V1'
    return value


ci.state = state
save, run = ci.save, ci.run
require_free = ci.require_free_runner


def sources():
    definition = json.loads((HERE / 'SOURCE_FILES.json').read_bytes())
    if definition.get('protectedBase') != BASE_COMMIT:
        raise RuntimeError('PRODUCTION_SOURCE_BASE_REQUIRED')
    for entry in definition['files']:
        path = HERE / entry['path']
        if (PurePosixPath(entry['path']).is_absolute() or '..' in Path(entry['path']).parts
                or path.is_symlink() or ci.sha(path) != entry['sha256']):
            raise RuntimeError('PRODUCTION_SOURCE_SHA_MISMATCH')
    if ci.sha(REPO / WORKFLOW) != definition['workflowSha256']:
        raise RuntimeError('PRODUCTION_WORKFLOW_SHA_MISMATCH')
    if ci.sha(HERE / 'key_encoding.py') != 'c1c788370823c4012487c1e726156a332de4e19582c211fb5c4cb64f8901fdff':
        raise RuntimeError('PRODUCTION_VERIFIED_NORMALIZER_CHANGED')
    changed = run(['git', 'diff', '--name-only', BASE_COMMIT, '--']).stdout.splitlines()
    if any(not (p.startswith(NAMESPACE + '/') or p == WORKFLOW) for p in changed):
        raise RuntimeError('PRODUCTION_PROTECTED_SOURCE_CHANGED')


def preflight():
    sources()
    value = state()
    value.update(builder=require_free(), schema='WORLD_ENGINE_DROPBOX_GPU_PRODUCTION_PACKAGE_V1',
                 tag='studio-dropbox-gpu-prod-v1-00cae13-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
    if not ci.TAG.fullmatch(value['tag']) or not ci.COMMIT.fullmatch(os.environ.get('GITHUB_SHA', '')):
        raise RuntimeError('PRODUCTION_SOURCE_AND_TAG_REQUIRED')
    value.update(image=ci.IMAGE + ':' + value['tag'], protectedSourceChanges=0,
                 existingSecretsChanged=False, encryptionKeyBytesChanged=False)
    save(value)


def generated_manifest():
    source = os.environ.get('GITHUB_SHA', '')
    if not ci.COMMIT.fullmatch(source):
        raise RuntimeError('PRODUCTION_SOURCE_COMMIT_REQUIRED')
    raw = (HERE / MANIFEST).read_bytes()
    data = json.loads(raw)
    data.update(sourceCommit=source, definitionManifestSha256=hashlib.sha256(raw).hexdigest())
    return (json.dumps(data, indent=2, sort_keys=True) + '\n').encode()


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='production-payload-', dir=location()))
    target = context / 'extension'
    target.mkdir()
    generated = generated_manifest()
    for entry in json.loads(generated)['files']:
        name = entry['path']
        relative = PurePosixPath(name)
        source = HERE / name
        if (relative.is_absolute() or str(relative) != name or '..' in relative.parts
                or '\\' in name or any(p.is_symlink() for p in (source, *source.parents))
                or not source.is_file() or ci.sha(source) != entry['sha256']):
            raise RuntimeError('PRODUCTION_STAGED_SOURCE_SHA_REQUIRED')
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
    (target / MANIFEST).write_bytes(generated)
    for name in ('Dockerfile', '.dockerignore'):
        shutil.copyfile(HERE / name, context / name)
    return context


def container(image):
    return ['docker', 'run', '--rm', '--network=none', '--read-only', '--user=1000:1000',
            '--memory=8g', '--cpus=2', '--pids-limit=512', '--restart=no', '--shm-size=2g',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--tmpfs', '/tmp:rw,mode=1777',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/tmp',
            '--entrypoint=' + PYTHON, image, '-B']


def frozen_report(image):
    result = run(container(image) + ['/opt/world-engine-studio-dropbox-offline/offline_manifest.py', '--verify'])
    value = json.loads(result.stdout.strip().splitlines()[-1])
    if value.get('status') != 'PASS' or value.get('gpuExecuted') is not False:
        raise RuntimeError('PRODUCTION_FROZEN_PARENT_REPORT_REQUIRED')
    return value


def inspect_image(image):
    row = json.loads(run(['docker', 'image', 'inspect', image]).stdout)[0]
    parent = json.loads(run(['docker', 'image', 'inspect', ci.BASE]).stdout)[0]
    config = row.get('Config', {})
    labels = config.get('Labels', {})
    entry = ['/usr/bin/tini', '-g', '--', PYTHON, '-B', DEST + '/production_entry.py', 'bootstrap']
    forbidden = {*SECRET_NAMES, 'GCUBE_ACCESS_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN',
                 'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != entry
            or labels.get('world-engine.studio-dropbox-gpu-production.parent-digest') != BASE_DIGEST
            or labels.get('world-engine.studio-dropbox-gpu-production.source-revision') != os.environ['GITHUB_SHA']
            or set(item.partition('=')[0] for item in config.get('Env', [])) & forbidden
            or config.get('Healthcheck') != parent.get('Config', {}).get('Healthcheck')
            or row['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] != parent['RootFS']['Layers']):
        raise RuntimeError('PRODUCTION_IMAGE_SOURCE_AND_PARENT_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
            'platform': 'linux/amd64', 'entrypoint': entry,
            'parentLayersUnchanged': True, 'healthcheckUnchanged': True, 'secretEnvironmentPresent': False}


def image_hashes(image):
    result = run(container(image) + [DEST + '/production_manifest.py', '--verify'])
    report = json.loads(result.stdout.strip().splitlines()[-1])
    if (report.get('status') != 'PASS' or report.get('sourceCommit') != os.environ['GITHUB_SHA']
            or report.get('manifestSha256') != hashlib.sha256(generated_manifest()).hexdigest()):
        raise RuntimeError('PRODUCTION_IMAGE_MANIFEST_SHA_REQUIRED')
    return report


ci.inspect_image, ci.image_hashes = inspect_image, image_hashes


def stage():
    sources()
    require_free()
    run(['docker', 'pull', ci.BASE], timeout=900)
    context = payload_context()
    value = state()
    value.update(context=str(context), extensionManifestSha256=ci.sha(context / 'extension' / MANIFEST),
                 dockerfileSha256=ci.sha(context / 'Dockerfile'), parentBefore=frozen_report(ci.BASE),
                 dependenciesBefore=helper.frozen_dependencies(ci.BASE))
    save(value)


def build():
    value = state()
    require_free()
    context = Path(value['context'])
    if (ci.sha(context / 'extension' / MANIFEST) != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('PRODUCTION_FROZEN_CONTEXT_REQUIRED')
    run(['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
         '--label', 'world-engine.studio-dropbox-gpu-production.source-revision=' + os.environ['GITHUB_SHA'],
         '--tag', value['image'], str(context)], timeout=900)
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    save(value)


def test():
    value = state()
    if value.get('imageBuilt') is not True:
        raise RuntimeError('PRODUCTION_CANDIDATE_REQUIRED')
    code = ('import sys,unittest,json;sys.path.insert(0,' + repr(DEST) + ');'
            's=unittest.defaultTestLoader.discover(' + repr(DEST + '/tests') + ',pattern="test_*.py");'
            'r=unittest.TextTestRunner(verbosity=2).run(s);'
            'print(json.dumps({"testsRun":r.testsRun,"failures":len(r.failures),'
            '"errors":len(r.errors),"skips":len(r.skipped),'
            '"failedTests":[str(t) for t,_ in r.failures+r.errors],'
            '"errorTypes":[trace.strip().splitlines()[-1].partition(":")[0][:96] for _,trace in r.errors],'
            '"gpuExecuted":False}));'
            'raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)')
    result = run(container(value['image']) + ['-c', code], timeout=600, check=False)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    value = state()
    value.update(testsStatus='PASS' if result.returncode == 0 else 'FAIL', focusedTestReport=report,
                 fullInheritedSuiteRepeated=False)
    save(value)
    print(json.dumps(report, sort_keys=True))
    if result.returncode:
        raise RuntimeError('PRODUCTION_FOCUSED_TEST_FAILED')
    run(container(value['image']) + [DEST + '/production_entry.py', 'cli', '--help'])


def verify():
    value = state()
    if value.get('testsStatus') != 'PASS':
        raise RuntimeError('PRODUCTION_FOCUSED_TEST_PASS_REQUIRED')
    after = frozen_report(value['image'])
    dependencies = helper.frozen_dependencies(value['image'])
    if after != value['parentBefore'] or dependencies != value['dependenciesBefore']:
        raise RuntimeError('PRODUCTION_INHERITED_SOURCE_OR_DEPENDENCIES_CHANGED')
    value.update(imageHashes=image_hashes(value['image']), parentAfter=after,
                 inheritedDependenciesChanged=False, secretScan=ci.secret_scan(), verification='PASS')
    save(value)


def pull():
    require_free()
    run(['docker', 'pull', ci.BASE], timeout=900)
    ci.pull()
    value = state()
    if frozen_report(value['imageReference']) != frozen_report(ci.BASE):
        raise RuntimeError('PRODUCTION_INDEPENDENT_PARENT_MISMATCH')
    value.update(protectedParentUnchanged=True, inheritedDependenciesChanged=False)
    save(value)


def restart():
    from ci_restart import run_restart
    run_restart(sys.modules[__name__])


def persist():
    value = state()
    value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    phase = os.environ.get('RESULT_PHASE')
    if phase not in {'build', 'pull'}:
        raise RuntimeError('PRODUCTION_RESULT_PHASE_REQUIRED')
    good = not value.get('failedPhase') and all(x == 'success' for x in value['stepOutcomes'].values())
    if phase == 'pull':
        good = good and value.get('restartRecovery', {}).get('status') == 'PASS' and value.get('pullVerified') is True
    value['status'] = 'GPU_PRODUCTION_CANDIDATE_CPU_VERIFIED_HARDWARE_PENDING' if good else 'GPU_PRODUCTION_CANDIDATE_BLOCKED'
    # Only allowlisted facts; never persist raw container/provider/test output.
    keys = {'schema', 'status', 'sourceCommit', 'parentImage', 'tag', 'imageDigest', 'imageReference',
            'imageConfiguration', 'imageHashes', 'builder', 'imageBuilt', 'imagePushed', 'pullVerified',
            'focusedTestReport', 'testsStatus', 'fullInheritedSuiteRepeated', 'secretScan', 'verification',
            'protectedSourceChanges', 'protectedParentUnchanged', 'inheritedDependenciesChanged',
            'existingSecretsChanged', 'encryptionKeyBytesChanged', 'gpuExecuted', 'paidWorkExecuted',
            'gCubeDeployed', 'finalModified', 'rendererModified', 'oldImagesDeleted', 'videoQualityApproved',
            'restartRecovery', 'stepOutcomes', 'reasonCode', 'failedPhase'}
    safe = {key: val for key, val in value.items() if key in keys}
    raw = (json.dumps(safe, indent=2, sort_keys=True) + '\n').encode()
    run_id = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*', run_id):
        raise RuntimeError('PRODUCTION_RESULT_RUN_REQUIRED')
    relative = Path(NAMESPACE) / 'runs' / run_id
    artifacts = {str(relative / (phase + '.json')): raw,
                 str(relative / (phase + '.SHA256SUMS')): (hashlib.sha256(raw).hexdigest() + '  ' + phase + '.json\n').encode()}
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'])
    for name, body in artifacts.items():
        target = REPO / name
        if target.exists():
            raise RuntimeError('PRODUCTION_EXISTING_RECORD_OVERWRITE_FORBIDDEN')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    run(['git', 'config', 'user.name', 'github-actions[bot]'])
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    run(['git', 'add', '--', *sorted(artifacts)])
    if sorted(run(['git', 'diff', '--cached', '--name-only']).stdout.splitlines()) != sorted(artifacts):
        raise RuntimeError('PRODUCTION_BOUNDED_EVIDENCE_REQUIRED')
    run(['git', 'diff', '--cached', '--check'])
    run(['git', 'commit', '-m', 'docs(dropbox): persist production ' + phase + ' CPU evidence [skip ci]'])
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'guard', 'stage', 'build', 'test', 'verify', 'publish', 'pull', 'restart', 'persist'))
    args = parser.parse_args()
    try:
        if args.phase == 'guard':
            ci.guard()
        elif args.phase == 'publish':
            ci.publish()
        else:
            globals()[args.phase]()
    except Exception as error:
        code = getattr(error, 'code', str(error))
        code = code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{2,95}', code) else 'PRODUCTION_CPU_PHASE_FAILED'
        value = state()
        value.update(failedPhase=args.phase, reasonCode=code)
        save(value)
        print(json.dumps({'status': 'FAIL', 'phase': args.phase, 'reasonCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
