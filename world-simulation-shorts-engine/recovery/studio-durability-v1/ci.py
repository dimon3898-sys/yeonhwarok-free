#!/usr/bin/env python3
"""Free CPU-only packaging for additive, encrypted Studio checkpoints.

Reuse the SHA-pinned registry/auth/evidence implementation. No gCube command,
GPU device, map renderer, cache cleanup, or existing-image mutation is invoked.
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
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FROZEN_CI = HERE.parent / 'studio-https-bootstrap-v1' / 'ci_package.py'
if hashlib.sha256(FROZEN_CI.read_bytes()).hexdigest() != '93f588a9f1df0763814d42c8842495fd7733dcd3bbb97304c16a264d4cc6b393':
    raise RuntimeError('DURABILITY_FROZEN_CI_SHA_MISMATCH')
spec = importlib.util.spec_from_file_location('_studio_durability_frozen_ci', FROZEN_CI)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

ci.HERE = HERE
ci.NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-durability-v1'
ci.WORKFLOW = '.github/workflows/studio-durability-v1.yml'
ci.BRANCH = 'development/studio-durability-v1-20261018'
ci.BASE_DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
ci.BASE = ci.IMAGE + '@' + ci.BASE_DIGEST
ci.DEST = '/opt/world-engine-studio-durability'
ci.TAG = re.compile(r'studio-durability-v1-f983adc-[1-9][0-9]*-[1-9][0-9]*\Z')
VENV_PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'
DEPENDENCY_BUILDER_DIGEST = 'sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d'
DEPENDENCY_BUILDER = 'docker.io/library/python@' + DEPENDENCY_BUILDER_DIGEST
MANIFEST = 'DURABILITY_FILES.json'


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-durability-package-v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


ci.location = location
original_state, original_bounded = ci.state, ci.bounded


def state():
    value = original_state()
    value['schema'] = 'WORLD_ENGINE_STUDIO_DURABILITY_PACKAGE_V1'
    value['status'] = value['status'].replace('STUDIO_HTTPS_CANDIDATE', 'STUDIO_DURABILITY_CANDIDATE')
    value.setdefault('actualExternalBackupVerified', False)
    value.setdefault('actualContainerRestartRecoveryVerified', False)
    return value


def bounded(text):
    text = original_bounded(text)
    for name in ('WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN'):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, '[REDACTED]')
    return text


ci.state, ci.bounded = state, bounded


def preflight():
    value = ci.state()
    value['builder'] = ci.require_free_runner()
    if not ci.COMMIT.fullmatch(os.environ.get('GITHUB_SHA', '')):
        raise RuntimeError('DURABILITY_SOURCE_COMMIT_REQUIRED')
    value['tag'] = 'studio-durability-v1-f983adc-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not ci.TAG.fullmatch(value['tag']):
        raise RuntimeError('DURABILITY_UNIQUE_TAG_REQUIRED')
    value['image'] = ci.IMAGE + ':' + value['tag']
    ci.save(value)


def generated_manifest():
    """Bind packaged provenance to this exact CI source without Git self-reference."""
    source = os.environ.get('GITHUB_SHA', '')
    if not ci.COMMIT.fullmatch(source):
        raise RuntimeError('DURABILITY_SOURCE_COMMIT_REQUIRED')
    definition = (HERE / MANIFEST).read_bytes()
    document = json.loads(definition)
    document['sourceCommit'] = source
    document['definitionManifestSha256'] = hashlib.sha256(definition).hexdigest()
    return (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='durability-payload-', dir=location()))
    payload = context / 'extension'
    payload.mkdir()
    generated = generated_manifest()
    document = json.loads(generated)
    files = document.get('files', {})
    tests = document.get('testFiles', {})
    if not isinstance(files, dict) or not isinstance(tests, dict):
        raise RuntimeError('DURABILITY_EXPLICIT_PAYLOAD_MANIFEST_REQUIRED')
    expected = {**files, **tests}
    if (not {'bootstrap.py', 'runtime_entry.py', 'durable_server.py', 'durable_backend.py',
             'checkpoint.py', 'vault.py', 'stores.py', 'manifest.py', 'requirements.txt'} <= set(files)
            or not tests):
        raise RuntimeError('DURABILITY_CONNECTED_RUNTIME_AND_TESTS_REQUIRED')
    for name, digest in sorted(expected.items()):
        relative = PurePosixPath(name)
        source = HERE / name
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                or not ci.HASH.fullmatch(str(digest))
                or any(p.is_symlink() for p in (source, *source.parents))
                or not source.is_file() or not 0 < source.stat().st_size <= 4 * 1024**2
                or ci.sha(source) != digest):
            raise RuntimeError('DURABILITY_MANIFESTED_REGULAR_SOURCE_REQUIRED')
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (payload / MANIFEST).write_bytes(generated)
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    shutil.copyfile(HERE / '.dockerignore', context / '.dockerignore')
    return context


ci.payload_context = payload_context


def selftest():
    """No Docker/network: generated provenance is stable and definition is immutable."""
    definition = (HERE / MANIFEST).read_bytes()
    generated = generated_manifest()
    document = json.loads(generated)
    if (document['sourceCommit'] != os.environ['GITHUB_SHA']
            or document['definitionManifestSha256'] != hashlib.sha256(definition).hexdigest()
            or generated != generated_manifest()):
        raise RuntimeError('DURABILITY_GENERATED_MANIFEST_SELFTEST_FAILED')
    context = payload_context()
    try:
        staged = (context / 'extension' / MANIFEST).read_bytes()
        if staged != generated or (HERE / MANIFEST).read_bytes() != definition:
            raise RuntimeError('DURABILITY_SOURCE_DEFINITION_MUTATED')
        for group in ('files', 'testFiles'):
            for name, digest in document[group].items():
                if ci.sha(context / 'extension' / name) != digest:
                    raise RuntimeError('DURABILITY_SELFTEST_STAGED_HASH_MISMATCH')
        print(json.dumps({'status': 'PASS', 'sourceCommit': document['sourceCommit'],
                          'definitionManifestSha256': document['definitionManifestSha256'],
                          'generatedManifestSha256': hashlib.sha256(generated).hexdigest(),
                          'gpuExecuted': False, 'dockerExecuted': False}))
    finally:
        # Only the new scratch payload from this selftest is removed.
        shutil.rmtree(context)


def container(image, *, context=None, evidence=None):
    if context is not None or evidence is not None:
        raise RuntimeError('DURABILITY_CANDIDATE_IMAGE_TEST_REQUIRED')
    return ['docker', 'run', '--rm', '--network=none', '--user=1000:1000',
            '--memory=8g', '--cpus=2', '--pids-limit=512', '--restart=no', '--shm-size=2g',
            '--tmpfs', '/tmp:rw,mode=1777', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'HOME=/tmp', '--env', 'TMPDIR=/tmp',
            '--entrypoint=' + VENV_PYTHON, image, '-B']


ci.container = container


def frozen_parent_report(image):
    # This established verifier recursively checks HTTPS, Studio and frozen V4
    # inventory hashes. Compare the full report against the immutable parent.
    command = container(image)
    command[command.index('--entrypoint=' + VENV_PYTHON)] = '--entrypoint=/usr/bin/python3'
    result = ci.run(command + ['/opt/world-engine-studio-https-proxy-fix/manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('DURABILITY_PROTECTED_PARENT_REPORT_REQUIRED') from None
    if report.get('status') != 'PASS' or report.get('gpuExecuted') is not False:
        raise RuntimeError('DURABILITY_PROTECTED_PARENT_HASHES_FAILED')
    return report


def frozen_dependency_hash(image):
    command = container(image)
    command[command.index('--entrypoint=' + VENV_PYTHON)] = '--entrypoint=/usr/bin/python3'
    code = ('import hashlib,importlib.metadata as m,json;'
            'rows=sorted((d.metadata["Name"],d.version,str(d.locate_file(""))) for d in m.distributions());'
            'print(hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())')
    digest = ci.run(command + ['-c', code]).stdout.strip()
    if not ci.HASH.fullmatch(digest):
        raise RuntimeError('DURABILITY_PARENT_DEPENDENCY_INVENTORY_REQUIRED')
    return digest


def stage():
    ci.require_free_runner()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    context = payload_context()
    value = ci.state()
    value.update(context=str(context),
                 extensionManifestSha256=ci.sha(context / 'extension' / MANIFEST),
                 dockerfileSha256=ci.sha(context / 'Dockerfile'),
                 protectedParentBefore=frozen_parent_report(ci.BASE),
                 parentDependenciesBefore=frozen_dependency_hash(ci.BASE))
    ci.save(value)


def inspect_image(image):
    row = json.loads(ci.run(['docker', 'image', 'inspect', image]).stdout)[0]
    config, labels = row.get('Config', {}), row.get('Config', {}).get('Labels', {})
    entrypoint = ['/usr/bin/tini', '-g', '--', VENV_PYTHON, '-B', ci.DEST + '/bootstrap.py']
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != entrypoint
            or labels.get('world-engine.studio-durability.parent-digest') != ci.BASE_DIGEST
            or labels.get('world-engine.studio-durability.dependency-builder-digest') != DEPENDENCY_BUILDER_DIGEST
            or labels.get('world-engine.studio-durability.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('DURABILITY_IMAGE_PROVENANCE_REQUIRED')
    forbidden = {'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
                 'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON',
                 'WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN'}
    if set(item.partition('=')[0] for item in config.get('Env', [])) & forbidden:
        raise RuntimeError('DURABILITY_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('DURABILITY_SERVICE_HEALTH_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
            'entrypoint': entrypoint, 'healthcheck': config['Healthcheck'],
            'platform': 'linux/amd64', 'secretEnvironmentPresent': False}


ci.inspect_image = inspect_image


def build():
    ci.require_free_runner()
    value = ci.state()
    if not value.get('context'):
        raise RuntimeError('DURABILITY_STAGED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (ci.sha(context / 'extension' / MANIFEST) != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('DURABILITY_FROZEN_CONTEXT_SHA_REQUIRED')
    result = ci.run(['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
                     '--label', 'world-engine.studio-durability.source-revision=' + os.environ['GITHUB_SHA'],
                     '--tag', value['image'], str(context)], timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode,
                            'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    ci.save(value)
    if result.returncode:
        raise RuntimeError('DURABILITY_IMAGE_BUILD_FAILED')
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    ci.save(value)


def test():
    ci.require_free_runner()
    value = ci.state()
    if not value.get('imageBuilt'):
        raise RuntimeError('DURABILITY_LOCAL_CANDIDATE_REQUIRED')
    code = ('import sys,unittest,json;sys.path.insert(0,' + repr(ci.DEST) + ');'
            's=unittest.defaultTestLoader.discover(' + repr(ci.DEST + '/tests') + ',pattern="test_*.py");'
            'r=unittest.TextTestRunner(verbosity=2).run(s);'
            'print(json.dumps({"testsRun":r.testsRun,"failures":len(r.failures),'
            '"errors":len(r.errors),"skips":len(r.skipped),"gpuExecuted":False}));'
            'raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)')
    result = ci.record('focused-uid1000-cpu-durability', container(value['image']) + ['-c', code], timeout=900)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    dependency = ci.run(container(value['image']) + ['-c',
        'import cryptography;assert cryptography.__version__=="50.0.0";print(cryptography.__version__)']).stdout.strip()
    value = ci.state()
    value.update(testsStatus='PASS', focusedTestReport=report,
                 isolatedCryptographyVersion=dependency,
                 testsScope='CPU_FIXTURES_NOT_NVIDIA_OR_EXTERNAL_DURABILITY')
    ci.save(value)


def image_hashes(image, context=None):
    if context is not None:
        raise RuntimeError('DURABILITY_IMMUTABLE_CANDIDATE_REQUIRED')
    result = ci.run(container(image) + [ci.DEST + '/manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('DURABILITY_SOURCE_REPORT_REQUIRED') from None
    if (report.get('status') != 'PASS' or report.get('gpuExecuted') is not False
            or report.get('sourceCommit') != os.environ['GITHUB_SHA']
            or report.get('manifestSha256') != hashlib.sha256(generated_manifest()).hexdigest()):
        raise RuntimeError('DURABILITY_SOURCE_VERIFICATION_FAILED')
    return report


ci.image_hashes = image_hashes


def dependency_report(image):
    """Verify only the newly copied wheels; inherited Python is checked separately."""
    code = '''import hashlib,json,pathlib,sys
venv=pathlib.Path('/opt/world-engine-studio-durability-venv')
root=venv/'lib/python3.12/site-packages'
raw=(venv/'DEPENDENCIES.json').read_bytes()
report=json.loads(raw)
assert report['schema']=='WORLD_ENGINE_STUDIO_DURABILITY_DEPENDENCIES_V1'
assert report['builderImage']==BUILDER
assert report['pythonABI']=='3.12' and sys.version_info[:2]==(3,12)
assert report['scope']=='NEW_ISOLATED_VENV_ONLY'
assert report['sourceRequirementsSha256']==REQUIREMENTS_SHA
assert report['installedDistributions']['cryptography']=='50.0.0'
assert report['files'] and isinstance(report['files'],dict)
actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file()}
assert not any(p.is_symlink() for p in root.rglob('*'))
assert actual==report['files']
print(json.dumps({'status':'PASS','manifestSha256':hashlib.sha256(raw).hexdigest(),
    'builderImage':report['builderImage'],'builderPythonVersion':report['builderPythonVersion'],
    'pythonABI':report['pythonABI'],'nativePythonVersion':sys.version.split()[0],
    'sourceRequirementsSha256':report['sourceRequirementsSha256'],
    'installedDistributions':report['installedDistributions'],'files':len(actual),
    'scope':report['scope'],'gpuExecuted':False},sort_keys=True))
'''
    code = ('BUILDER=' + repr(DEPENDENCY_BUILDER) + ';REQUIREMENTS_SHA='
            + repr(ci.sha(HERE / 'requirements.txt')) + '\n' + code)
    result = ci.run(container(image) + ['-c', code])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('DURABILITY_ISOLATED_DEPENDENCY_REPORT_REQUIRED') from None
    if report.get('status') != 'PASS' or report.get('gpuExecuted') is not False:
        raise RuntimeError('DURABILITY_ISOLATED_DEPENDENCY_SHA_FAILED')
    return report


def verify():
    value = ci.state()
    if value.get('testsStatus') != 'PASS' or not value.get('imageBuilt'):
        raise RuntimeError('DURABILITY_FOCUSED_TEST_PASS_REQUIRED')
    after = frozen_parent_report(value['image'])
    deps = frozen_dependency_hash(value['image'])
    if after != value['protectedParentBefore'] or deps != value['parentDependenciesBefore']:
        raise RuntimeError('DURABILITY_PROTECTED_PARENT_CHANGED')
    value.update(imageHashes=image_hashes(value['image']),
                 dependencyProvenance=dependency_report(value['image']), protectedParentAfter=after,
                 parentDependenciesAfter=deps, secretScan=ci.secret_scan(), verification='PASS')
    ci.save(value)


def pull():
    # Reuse official registry digest verification, independent Docker pull,
    # config/source verification and tag-to-digest matching from frozen helper.
    ci.pull()
    value = ci.state()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    before = frozen_parent_report(ci.BASE)
    after = frozen_parent_report(value['imageReference'])
    base_deps = frozen_dependency_hash(ci.BASE)
    candidate_deps = frozen_dependency_hash(value['imageReference'])
    if before != after or base_deps != candidate_deps:
        raise RuntimeError('DURABILITY_INDEPENDENT_PARENT_HASH_MISMATCH')
    value.update(protectedParentBefore=before, protectedParentAfter=after,
                 parentDependenciesBefore=base_deps, parentDependenciesAfter=candidate_deps,
                 dependencyProvenance=dependency_report(value['imageReference']),
                 protectedParentUnchanged=True)
    ci.save(value)


def external():
    """Optional real Dropbox CPU proof, never infer success from bound Secrets."""
    names = ('WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN')
    inputs = [os.environ.get(name, '') for name in names]
    value = ci.state()
    report = {'status': 'BLOCKED', 'reasonCode': 'DURABILITY_EXTERNAL_SECRETS_NOT_BOUND',
              'scope': 'REAL_DROPBOX_CPU_SYNTHETIC_RECOVERY_PROOF',
              'credentialsAvailable': all(bool(item) for item in inputs),
              'externalStorageRecoveryVerified': False, 'gpuExecuted': False,
              'nvidiaRenderingVerified': False, 'productionRenderingStarted': False,
              'productionApprovalGranted': False, 'rawOutputRecorded': False}
    if not all(inputs):
        value['externalDurability'] = report
        value['actualExternalBackupVerified'] = False
        value['actualContainerRestartRecoveryVerified'] = False
        ci.save(value)
        print(json.dumps(report, sort_keys=True))
        return
    directory = None
    probe_container = None
    secret_paths = []
    runner_uid, runner_gid = os.geteuid(), os.getegid()
    clean_env = {key: item for key, item in os.environ.items() if key not in names}
    try:
        # The pull job already passed the 20 GiB preflight. Do not reapply
        # build-space requirements after downloading image layers for this
        # bounded, tiny CPU transport probe.
        if (value.get('builder', {}).get('status') != 'PASS'
                or os.environ.get('GITHUB_ACTIONS') != 'true'
                or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
                or os.environ.get('GITHUB_REF') != 'refs/heads/' + ci.BRANCH
                or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'
                or os.environ.get('RESULT_RUNNER_LABEL') != 'ubuntu-24.04'):
            raise RuntimeError('DURABILITY_EXTERNAL_FREE_PUBLIC_RUNNER_REQUIRED')
        digest = value.get('imageDigest', '')
        image = value.get('imageReference', '')
        if (value.get('pullVerified') is not True or not ci.DIGEST.fullmatch(digest)
                or image != ci.IMAGE + '@' + digest):
            raise RuntimeError('DURABILITY_EXTERNAL_IMMUTABLE_PULL_REQUIRED')
        if any(not 1 <= len(item.encode()) <= 65536 for item in inputs):
            raise RuntimeError('DURABILITY_EXTERNAL_SECRET_INPUT_INVALID')
        directory = Path(tempfile.mkdtemp(prefix='studio-durability-external-secrets-',
                                         dir=os.environ.get('RUNNER_TEMP', '/tmp')))
        for name, body in zip(('backup-key', 'dropbox-token'), inputs):
            path = directory / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(body.encode())
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                # fdopen owns the descriptor once entered.
                raise
            secret_paths.append(path)
        ci.run(['sudo', '-n', 'chown', '1000:1000', str(directory),
                *(str(path) for path in secret_paths)], environment=clean_env)
        # Hosted runners use a different UID, so validate the 0700 directory
        # as root without making it traversable to the runner account.
        metadata = ('import pathlib,stat,sys;d=pathlib.Path(sys.argv[1]);s=d.stat();'
                    'assert s.st_uid==1000 and s.st_gid==1000 and stat.S_IMODE(s.st_mode)==0o700;'
                    'rows=[(d/n).stat() for n in ("backup-key","dropbox-token")];'
                    'assert all(s.st_uid==1000 and s.st_gid==1000 and '
                    'stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1 for s in rows)')
        ci.run(['sudo', '-n', '/usr/bin/python3', '-B', '-c', metadata, str(directory)],
               environment=clean_env)
        probe = '/tmp/world-engine-external-proof'
        code = ('import os,sys;os.mkdir(' + repr(probe) + ',0o700);'
                'sys.path.insert(0,' + repr(ci.DEST) + ');import cli;'
                'raise SystemExit(cli.main(["external-check","--private-work-root",' + repr(probe) + ']))')
        probe_container = 'studio-durability-external-' + os.urandom(16).hex()
        command = ['docker', 'run', '--rm', '--name', probe_container,
                   '--user=1000:1000', '--read-only',
                   '--memory=2g', '--cpus=2', '--pids-limit=256', '--restart=no',
                   '--cap-drop=ALL', '--security-opt=no-new-privileges',
                   '--tmpfs', '/tmp:rw,mode=1777',
                   '--mount', 'type=bind,source=' + str(directory) + ',target=/run/world-engine-backup-secrets,readonly',
                   '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/tmp',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_MODE=dropbox-api',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX=/WORLD_ENGINE_STUDIO_BACKUPS_V1',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE=/run/world-engine-backup-secrets/backup-key',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN_FILE=/run/world-engine-backup-secrets/dropbox-token',
                   '--entrypoint=' + VENV_PYTHON, image, '-B', '-c', code]
        # Docker receives file paths only. The inherited backup CLI performs
        # bounded official HTTPS requests with no redirects or API retries.
        result = ci.run(command, environment=clean_env, timeout=900, check=False)
        report['containerExitCode'] = result.returncode
        if result.returncode:
            try:
                error = json.loads(result.stderr.strip().splitlines()[-1]).get('errorCode', '')
            except (ValueError, IndexError, AttributeError):
                error = ''
            report['reasonCode'] = error if re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', error) else 'DURABILITY_EXTERNAL_PROOF_FAILED'
        else:
            try:
                proof = json.loads(result.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                raise RuntimeError('DURABILITY_EXTERNAL_SAFE_PROOF_REQUIRED') from None
            if (not isinstance(proof, dict) or proof.get('status') != 'PASS'
                    or not ci.HASH.fullmatch(str(proof.get('proofId', '')))
                    or not ci.HASH.fullmatch(str(proof.get('checkpointId', '')))
                    or type(proof.get('expiresUnix')) is not int
                    or proof.get('externalStorageRecoveryVerified') is not True
                    or proof.get('nvidiaRenderingVerified') is not False
                    or proof.get('syntheticMedia') is not True
                    or proof.get('productionRenderingStarted') is not False
                    or proof.get('productionApprovalGranted') is not False):
                raise RuntimeError('DURABILITY_EXTERNAL_SAFE_PROOF_REQUIRED')
            report.update(status='PASS', reasonCode='DURABILITY_EXTERNAL_CPU_PROOF_VERIFIED',
                          proofId=proof['proofId'], checkpointId=proof['checkpointId'],
                          expiresUnix=proof['expiresUnix'],
                          externalStorageRecoveryVerified=True, syntheticMedia=True)
    except Exception as error:
        code = str(error)
        report['reasonCode'] = code if re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', code) else 'DURABILITY_EXTERNAL_PROOF_FAILED'
    finally:
        if probe_container is not None:
            # A timed-out Docker client must not leave its newly created CPU
            # probe running. This random name belongs only to this invocation.
            try:
                ci.run(['docker', 'stop', '--time=5', probe_container],
                       environment=clean_env, timeout=30, check=False)
            except Exception:
                report.update(status='BLOCKED', reasonCode='DURABILITY_EXTERNAL_PROBE_CLEANUP_FAILED',
                              externalStorageRecoveryVerified=False)
        if directory is not None:
            try:
                # Only this invocation's new credential files are removed.
                ci.run(['sudo', '-n', 'chown', str(runner_uid) + ':' + str(runner_gid),
                        str(directory), *(str(path) for path in secret_paths)], environment=clean_env)
                shutil.rmtree(directory)
                report['secretFilesRemoved'] = True
            except Exception:
                report.update(status='BLOCKED', reasonCode='DURABILITY_EXTERNAL_SECRET_CLEANUP_FAILED',
                              secretFilesRemoved=False, externalStorageRecoveryVerified=False)
        value = ci.state()
        value.update(externalDurability=report,
                     actualExternalBackupVerified=report['status'] == 'PASS',
                     actualContainerRestartRecoveryVerified=False)
        ci.save(value)
    print(json.dumps(report, sort_keys=True))


def persist():
    # Existing evidence writer optionally copies mobile artifacts; this focused
    # CPU suite produces JSON evidence only. The empty directory is deliberate.
    (location() / 'mobile').mkdir(mode=0o700, exist_ok=True)
    ci.persist()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'selftest', 'guard', 'stage', 'build', 'test',
                                         'verify', 'publish', 'pull', 'external', 'persist'))
    args = parser.parse_args()
    try:
        (globals().get(args.phase) or getattr(ci, args.phase))()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'DURABILITY_CI_FAILED'
        value = ci.state()
        value.update(status='STUDIO_DURABILITY_CANDIDATE_BLOCKED', failedPhase=args.phase,
                     reasonCode=code, errorType=type(error).__name__)
        ci.save(value)
        print(json.dumps({'status': value['status'], 'phase': args.phase, 'reasonCode': code}))
        raise SystemExit(1)
