#!/usr/bin/env python3
"""Free CPU packaging for the additive Dropbox offline OAuth adapter.

Reuse pinned registry, auth, scanner and bounded evidence helpers. No GPU,
gCube deployment, paid service, inherited-file write or Docker cleanup occurs.
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
    raise RuntimeError('OFFLINE_FROZEN_CI_SHA_MISMATCH')
spec = importlib.util.spec_from_file_location('_studio_offline_frozen_ci', FROZEN_CI)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
ci.HERE = HERE
ci.NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-dropbox-offline-v1'
ci.WORKFLOW = '.github/workflows/studio-dropbox-offline-v1.yml'
ci.BRANCH = 'development/dropbox-offline-token-v1-20261018'
ci.BASE_DIGEST = 'sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b'
ci.BASE = ci.IMAGE + '@' + ci.BASE_DIGEST
ci.DEST = '/opt/world-engine-studio-dropbox-offline'
ci.TAG = re.compile(r'studio-dropbox-offline-v1-165a348-[1-9][0-9]*-[1-9][0-9]*\Z')
VENV_PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'
MANIFEST = 'OFFLINE_FILES.json'
SECRET_NAMES = ('WORLD_ENGINE_STUDIO_BACKUP_KEY',
                'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY',
                'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET',
                'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN')


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-dropbox-offline-package-v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


ci.location = location
original_state, original_bounded = ci.state, ci.bounded


def state():
    value = original_state()
    value['schema'] = 'WORLD_ENGINE_STUDIO_DROPBOX_OFFLINE_PACKAGE_V1'
    value['status'] = value['status'].replace('STUDIO_HTTPS_CANDIDATE', 'STUDIO_DROPBOX_OFFLINE_CANDIDATE')
    value.setdefault('actualExternalBackupVerified', False)
    value.setdefault('actualOfflineTokenRefreshVerified', False)
    value.setdefault('actualContainerRestartRecoveryVerified', False)
    return value


def bounded(text):
    text = original_bounded(text)
    for name in (*SECRET_NAMES, 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN'):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, '[REDACTED]')
    return text


ci.state, ci.bounded = state, bounded


def preflight():
    value = ci.state()
    value['builder'] = ci.require_free_runner()
    if not ci.COMMIT.fullmatch(os.environ.get('GITHUB_SHA', '')):
        raise RuntimeError('OFFLINE_SOURCE_COMMIT_REQUIRED')
    value['tag'] = 'studio-dropbox-offline-v1-165a348-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not ci.TAG.fullmatch(value['tag']):
        raise RuntimeError('OFFLINE_UNIQUE_TAG_REQUIRED')
    value['image'] = ci.IMAGE + ':' + value['tag']
    ci.save(value)


def generated_manifest():
    source = os.environ.get('GITHUB_SHA', '')
    if not ci.COMMIT.fullmatch(source):
        raise RuntimeError('OFFLINE_SOURCE_COMMIT_REQUIRED')
    definition = (HERE / MANIFEST).read_bytes()
    document = json.loads(definition)
    document['sourceCommit'] = source
    document['definitionManifestSha256'] = hashlib.sha256(definition).hexdigest()
    return (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='offline-payload-', dir=location()))
    payload = context / 'extension'
    payload.mkdir()
    generated = generated_manifest()
    document = json.loads(generated)
    files, tests = document.get('files', {}), document.get('testFiles', {})
    if (not isinstance(files, dict) or not isinstance(tests, dict)
            or not {'offline_entry.py', 'offline_manifest.py'} <= set(files) or not tests
            or set(files) & set(tests)):
        raise RuntimeError('OFFLINE_EXPLICIT_RUNTIME_AND_TESTS_REQUIRED')
    for name, digest in sorted({**files, **tests}.items()):
        relative = PurePosixPath(name)
        source = HERE / name
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                or '\\' in name or not ci.HASH.fullmatch(str(digest))
                or any(p.is_symlink() for p in (source, *source.parents))
                or not source.is_file() or not 0 < source.stat().st_size <= 4 * 1024**2
                or ci.sha(source) != digest):
            raise RuntimeError('OFFLINE_MANIFESTED_REGULAR_SOURCE_REQUIRED')
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (payload / MANIFEST).write_bytes(generated)
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    shutil.copyfile(HERE / '.dockerignore', context / '.dockerignore')
    return context


ci.payload_context = payload_context


def selftest():
    definition = (HERE / MANIFEST).read_bytes()
    generated = generated_manifest()
    document = json.loads(generated)
    if (document['sourceCommit'] != os.environ['GITHUB_SHA']
            or document['definitionManifestSha256'] != hashlib.sha256(definition).hexdigest()
            or generated != generated_manifest()):
        raise RuntimeError('OFFLINE_GENERATED_PROVENANCE_SELFTEST_FAILED')
    context = payload_context()
    try:
        if ((context / 'extension' / MANIFEST).read_bytes() != generated
                or (HERE / MANIFEST).read_bytes() != definition):
            raise RuntimeError('OFFLINE_SOURCE_DEFINITION_MUTATED')
        for group in ('files', 'testFiles'):
            for name, digest in document[group].items():
                if ci.sha(context / 'extension' / name) != digest:
                    raise RuntimeError('OFFLINE_STAGED_HASH_MISMATCH')
        print(json.dumps({'status': 'PASS', 'sourceCommit': document['sourceCommit'],
                          'definitionManifestSha256': hashlib.sha256(definition).hexdigest(),
                          'generatedManifestSha256': hashlib.sha256(generated).hexdigest(),
                          'gpuExecuted': False, 'dockerExecuted': False}))
    finally:
        shutil.rmtree(context)  # Only this selftest's new staging directory.


def packagingtest():
    """Host-only packaging tests are hashed but never installed in runtime."""
    document = json.loads((HERE / MANIFEST).read_bytes())
    files = document.get('packagingTestFiles')
    if not isinstance(files, dict) or not files:
        raise RuntimeError('OFFLINE_PACKAGING_TEST_HASHES_REQUIRED')
    for name, digest in files.items():
        relative = PurePosixPath(name)
        source = HERE / name
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                or not name.startswith('packaging_tests/') or '\\' in name
                or not ci.HASH.fullmatch(str(digest))
                or any(p.is_symlink() for p in (source, *source.parents))
                or not source.is_file() or ci.sha(source) != digest):
            raise RuntimeError('OFFLINE_PACKAGING_TEST_SHA_MISMATCH')
    ci.record('host-cpu-packaging-safety', [sys.executable, '-B', '-m', 'unittest',
              'discover', '-s', str(HERE / 'packaging_tests'), '-p', 'test_*.py', '-v'], timeout=120)


def container(image, *, context=None, evidence=None):
    if context is not None or evidence is not None:
        raise RuntimeError('OFFLINE_CANDIDATE_IMAGE_TEST_REQUIRED')
    return ['docker', 'run', '--rm', '--network=none', '--user=1000:1000',
            '--memory=8g', '--cpus=2', '--pids-limit=512', '--restart=no', '--shm-size=2g',
            '--tmpfs', '/tmp:rw,mode=1777', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'HOME=/tmp', '--env', 'TMPDIR=/tmp',
            '--entrypoint=' + VENV_PYTHON, image, '-B']


ci.container = container


def frozen_parent_report(image):
    result = ci.run(container(image) + ['/opt/world-engine-studio-durability/manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('OFFLINE_PROTECTED_PARENT_REPORT_REQUIRED') from None
    if report.get('status') != 'PASS' or report.get('gpuExecuted') is not False:
        raise RuntimeError('OFFLINE_PROTECTED_PARENT_HASHES_FAILED')
    return report


def frozen_dependencies(image):
    """Whole inherited Python inventories and isolated dependency bytes stay fixed."""
    body = '''import hashlib,importlib.metadata as m,json,pathlib,sys
venv=pathlib.Path('/opt/world-engine-studio-durability-venv')
root=venv/'lib/python3.12/site-packages'
raw=(venv/'DEPENDENCIES.json').read_bytes()
manifest=json.loads(raw)
actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file()}
assert actual==manifest['files'] and not any(p.is_symlink() for p in root.rglob('*'))
assert manifest['installedDistributions']['cryptography']=='50.0.0'
assert manifest['scope']=='NEW_ISOLATED_VENV_ONLY'
rows=sorted((d.metadata['Name'],d.version,str(d.locate_file(''))) for d in m.distributions())
print(json.dumps({'status':'PASS','interpreter':sys.executable,
  'inventorySha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
  'dependencyManifestSha256':hashlib.sha256(raw).hexdigest(),
  'isolatedFiles':len(actual),'gpuExecuted':False},sort_keys=True))
'''
    reports = []
    for python in ('/usr/bin/python3', VENV_PYTHON):
        command = container(image)
        command[command.index('--entrypoint=' + VENV_PYTHON)] = '--entrypoint=' + python
        result = ci.run(command + ['-c', body])
        try:
            report = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise RuntimeError('OFFLINE_PARENT_DEPENDENCY_REPORT_REQUIRED') from None
        if report.get('status') != 'PASS' or report.get('gpuExecuted') is not False:
            raise RuntimeError('OFFLINE_PARENT_DEPENDENCY_HASHES_FAILED')
        reports.append(report)
    return reports


def stage():
    ci.require_free_runner()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    context = payload_context()
    value = ci.state()
    value.update(context=str(context), extensionManifestSha256=ci.sha(context / 'extension' / MANIFEST),
                 dockerfileSha256=ci.sha(context / 'Dockerfile'),
                 protectedParentBefore=frozen_parent_report(ci.BASE),
                 parentDependenciesBefore=frozen_dependencies(ci.BASE))
    ci.save(value)


def inspect_image(image):
    row = json.loads(ci.run(['docker', 'image', 'inspect', image]).stdout)[0]
    config = row.get('Config', {})
    labels = config.get('Labels', {})
    entrypoint = ['/usr/bin/tini', '-g', '--', VENV_PYTHON, '-B', ci.DEST + '/offline_entry.py', 'bootstrap']
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != entrypoint
            or labels.get('world-engine.studio-dropbox-offline.parent-digest') != ci.BASE_DIGEST
            or labels.get('world-engine.studio-dropbox-offline.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('OFFLINE_IMAGE_PROVENANCE_REQUIRED')
    forbidden = {'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
                 'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON',
                 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN', *SECRET_NAMES}
    if set(item.partition('=')[0] for item in config.get('Env', [])) & forbidden:
        raise RuntimeError('OFFLINE_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('OFFLINE_INHERITED_SERVICE_HEALTH_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
            'entrypoint': entrypoint, 'healthcheck': config['Healthcheck'],
            'platform': 'linux/amd64', 'secretEnvironmentPresent': False}


ci.inspect_image = inspect_image


def build():
    ci.require_free_runner()
    value = ci.state()
    if not value.get('context'):
        raise RuntimeError('OFFLINE_STAGED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (ci.sha(context / 'extension' / MANIFEST) != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('OFFLINE_FROZEN_CONTEXT_SHA_REQUIRED')
    result = ci.run(['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
                     '--label', 'world-engine.studio-dropbox-offline.source-revision=' + os.environ['GITHUB_SHA'],
                     '--tag', value['image'], str(context)], timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode,
                            'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    ci.save(value)
    if result.returncode:
        raise RuntimeError('OFFLINE_IMAGE_BUILD_FAILED')
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    ci.save(value)


def test():
    value = ci.state()
    if not value.get('imageBuilt'):
        raise RuntimeError('OFFLINE_LOCAL_CANDIDATE_REQUIRED')
    code = ('import sys,unittest,json;sys.path.insert(0,' + repr(ci.DEST) + ');'
            's=unittest.defaultTestLoader.discover(' + repr(ci.DEST + '/tests') + ',pattern="test_*.py");'
            'r=unittest.TextTestRunner(verbosity=2).run(s);'
            'print(json.dumps({"testsRun":r.testsRun,"failures":len(r.failures),'
            '"errors":len(r.errors),"skips":len(r.skipped),"gpuExecuted":False}));'
            'raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)')
    result = ci.record('focused-uid1000-cpu-offline-token', container(value['image']) + ['-c', code], timeout=900)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    ci.record('connected-offline-entry-cli-help', container(value['image']) +
              [ci.DEST + '/offline_entry.py', 'cli', '--help'], timeout=120)
    value = ci.state()
    value.update(testsStatus='PASS', focusedTestReport=report,
                 testsScope='CPU_MOCK_OAUTH_AND_RECOVERY_NOT_REAL_DROPBOX_OR_NVIDIA',
                 inheritedFullTestsRepeated=False)
    ci.save(value)


def image_hashes(image, context=None):
    if context is not None:
        raise RuntimeError('OFFLINE_IMMUTABLE_CANDIDATE_REQUIRED')
    result = ci.run(container(image) + [ci.DEST + '/offline_manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('OFFLINE_SOURCE_REPORT_REQUIRED') from None
    if (report.get('status') != 'PASS' or report.get('gpuExecuted') is not False
            or report.get('sourceCommit') != os.environ['GITHUB_SHA']
            or report.get('manifestSha256') != hashlib.sha256(generated_manifest()).hexdigest()):
        raise RuntimeError('OFFLINE_SOURCE_VERIFICATION_FAILED')
    return report


ci.image_hashes = image_hashes


def verify():
    value = ci.state()
    if value.get('testsStatus') != 'PASS' or not value.get('imageBuilt'):
        raise RuntimeError('OFFLINE_FOCUSED_TEST_PASS_REQUIRED')
    after = frozen_parent_report(value['image'])
    deps = frozen_dependencies(value['image'])
    if after != value['protectedParentBefore'] or deps != value['parentDependenciesBefore']:
        raise RuntimeError('OFFLINE_PROTECTED_PARENT_CHANGED')
    value.update(imageHashes=image_hashes(value['image']),
                 protectedParentAfter=after, parentDependenciesAfter=deps,
                 inheritedDependenciesChanged=False, secretScan=ci.secret_scan(), verification='PASS')
    ci.save(value)


def pull():
    ci.pull()  # Registry manifest digest, tag binding and separate Docker pull.
    value = ci.state()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    before = frozen_parent_report(ci.BASE)
    after = frozen_parent_report(value['imageReference'])
    base_deps = frozen_dependencies(ci.BASE)
    candidate_deps = frozen_dependencies(value['imageReference'])
    if before != after or base_deps != candidate_deps:
        raise RuntimeError('OFFLINE_INDEPENDENT_PARENT_HASH_MISMATCH')
    value.update(protectedParentBefore=before, protectedParentAfter=after,
                 parentDependenciesBefore=base_deps, parentDependenciesAfter=candidate_deps,
                 protectedParentUnchanged=True, inheritedDependenciesChanged=False)
    ci.save(value)


def external():
    """Optional actual offline refresh, scoped API access and encrypted recovery."""
    inputs = [os.environ.get(name, '') for name in SECRET_NAMES]
    report = {'status': 'BLOCKED', 'reasonCode': 'OFFLINE_EXTERNAL_SECRETS_NOT_BOUND',
              'scope': 'REAL_DROPBOX_OFFLINE_REFRESH_AND_CPU_SYNTHETIC_RECOVERY_PROOF',
              'credentialsAvailable': all(bool(item) for item in inputs),
              'externalStorageRecoveryVerified': False, 'offlineTokenRefreshVerified': False,
              'metadataReadVerified': False, 'gpuExecuted': False,
              'nvidiaRenderingVerified': False, 'productionRenderingStarted': False,
              'productionApprovalGranted': False, 'rawOutputRecorded': False}
    if not all(inputs):
        value = ci.state()
        value.update(externalDurability=report, actualExternalBackupVerified=False,
                     actualOfflineTokenRefreshVerified=False, actualContainerRestartRecoveryVerified=False)
        ci.save(value)
        print(json.dumps(report, sort_keys=True))
        return
    directory, probe_container = None, None
    secret_paths = []
    runner_uid, runner_gid = os.geteuid(), os.getegid()
    clean_env = {key: item for key, item in os.environ.items()
                 if key not in {*SECRET_NAMES, 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN'}}
    try:
        value = ci.state()
        if (value.get('builder', {}).get('status') != 'PASS'
                or os.environ.get('GITHUB_ACTIONS') != 'true'
                or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
                or os.environ.get('GITHUB_REF') != 'refs/heads/' + ci.BRANCH
                or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'
                or os.environ.get('RESULT_RUNNER_LABEL') != 'ubuntu-24.04'):
            raise RuntimeError('OFFLINE_EXTERNAL_FREE_PUBLIC_RUNNER_REQUIRED')
        digest, image = value.get('imageDigest', ''), value.get('imageReference', '')
        if (value.get('pullVerified') is not True or not ci.DIGEST.fullmatch(digest)
                or image != ci.IMAGE + '@' + digest):
            raise RuntimeError('OFFLINE_EXTERNAL_IMMUTABLE_PULL_REQUIRED')
        if any(not 1 <= len(item.encode()) <= 65536 for item in inputs):
            raise RuntimeError('OFFLINE_EXTERNAL_SECRET_INPUT_INVALID')
        directory = Path(tempfile.mkdtemp(prefix='studio-offline-external-secrets-',
                                         dir=os.environ.get('RUNNER_TEMP', '/tmp')))
        for name, body in zip(('backup-key', 'app-key', 'app-secret', 'refresh-token'), inputs):
            path = directory / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(body.encode())
                stream.flush()
                os.fsync(stream.fileno())
            secret_paths.append(path)
        ci.run(['sudo', '-n', 'chown', '1000:1000', str(directory),
                *(str(path) for path in secret_paths)], environment=clean_env)
        metadata = ('import pathlib,stat,sys;d=pathlib.Path(sys.argv[1]);s=d.stat();'
                    'assert s.st_uid==1000 and s.st_gid==1000 and stat.S_IMODE(s.st_mode)==0o700;'
                    'rows=[p.stat() for p in d.iterdir()];assert len(rows)==4;'
                    'assert all(s.st_uid==1000 and s.st_gid==1000 and '
                    'stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1 for s in rows)')
        ci.run(['sudo', '-n', '/usr/bin/python3', '-B', '-c', metadata, str(directory)], environment=clean_env)
        probe = '/tmp/world-engine-offline-external-proof'
        code = ('import os,runpy,sys;os.mkdir(' + repr(probe) + ',0o700);'
                'sys.argv=[' + repr(ci.DEST + '/offline_entry.py')
                + ',"cli","external-check","--private-work-root",' + repr(probe) + '];'
                'runpy.run_path(' + repr(ci.DEST + '/offline_entry.py') + ',run_name="__main__")')
        probe_container = 'studio-offline-external-' + os.urandom(16).hex()
        secret_root = '/run/world-engine-backup-secrets/'
        command = ['docker', 'run', '--rm', '--name', probe_container,
                   '--user=1000:1000', '--read-only', '--memory=2g', '--cpus=2',
                   '--pids-limit=256', '--restart=no', '--cap-drop=ALL',
                   '--security-opt=no-new-privileges', '--tmpfs', '/tmp:rw,mode=1777',
                   '--mount', 'type=bind,source=' + str(directory) + ',target=' + secret_root.rstrip('/') + ',readonly',
                   '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/tmp',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_MODE=dropbox-api',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE=offline',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX=/WORLD_ENGINE_STUDIO_BACKUPS_V1',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE=' + secret_root + 'backup-key',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY_FILE=' + secret_root + 'app-key',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET_FILE=' + secret_root + 'app-secret',
                   '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN_FILE=' + secret_root + 'refresh-token',
                   '--entrypoint=' + VENV_PYTHON, image, '-B', '-c', code]
        result = ci.run(command, environment=clean_env, timeout=900, check=False)
        report['containerExitCode'] = result.returncode
        if result.returncode:
            error = ''
            # Both frozen CLI and new entry report safe JSON, on different
            # streams. Keep only the bounded symbolic code, never raw output.
            for output in (result.stderr, result.stdout):
                try:
                    candidate = json.loads(output.strip().splitlines()[-1]).get('errorCode', '')
                except (ValueError, IndexError, AttributeError):
                    continue
                if re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', str(candidate)):
                    error = candidate
                    break
            report['reasonCode'] = error if re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', error) else 'OFFLINE_EXTERNAL_PROOF_FAILED'
        else:
            try:
                proof = json.loads(result.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                raise RuntimeError('OFFLINE_EXTERNAL_SAFE_PROOF_REQUIRED') from None
            if (not isinstance(proof, dict) or proof.get('status') != 'PASS'
                    or not ci.HASH.fullmatch(str(proof.get('proofId', '')))
                    or not ci.HASH.fullmatch(str(proof.get('checkpointId', '')))
                    or type(proof.get('expiresUnix')) is not int
                    or proof.get('externalStorageRecoveryVerified') is not True
                    or proof.get('offlineTokenRefreshVerified') is not True
                    or proof.get('metadataReadVerified') is not True
                    or proof.get('nvidiaRenderingVerified') is not False
                    or proof.get('syntheticMedia') is not True
                    or proof.get('productionRenderingStarted') is not False
                    or proof.get('productionApprovalGranted') is not False):
                raise RuntimeError('OFFLINE_EXTERNAL_SAFE_PROOF_REQUIRED')
            report.update(status='PASS', reasonCode='OFFLINE_EXTERNAL_CPU_PROOF_VERIFIED',
                          proofId=proof['proofId'], checkpointId=proof['checkpointId'],
                          expiresUnix=proof['expiresUnix'], externalStorageRecoveryVerified=True,
                          offlineTokenRefreshVerified=True, metadataReadVerified=True, syntheticMedia=True)
    except Exception as error:
        code = str(error)
        report['reasonCode'] = code if re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', code) else 'OFFLINE_EXTERNAL_PROOF_FAILED'
    finally:
        if probe_container is not None:
            try:
                ci.run(['docker', 'stop', '--time=5', probe_container], environment=clean_env, timeout=30, check=False)
            except Exception:
                report.update(status='BLOCKED', reasonCode='OFFLINE_EXTERNAL_PROBE_CLEANUP_FAILED',
                              externalStorageRecoveryVerified=False, offlineTokenRefreshVerified=False,
                              metadataReadVerified=False)
        if directory is not None:
            try:
                ci.run(['sudo', '-n', 'chown', str(runner_uid) + ':' + str(runner_gid),
                        str(directory), *(str(path) for path in secret_paths)], environment=clean_env)
                shutil.rmtree(directory)  # Only this invocation's new private Secret files.
                report['secretFilesRemoved'] = True
            except Exception:
                report.update(status='BLOCKED', reasonCode='OFFLINE_EXTERNAL_SECRET_CLEANUP_FAILED',
                              secretFilesRemoved=False, externalStorageRecoveryVerified=False,
                              offlineTokenRefreshVerified=False, metadataReadVerified=False)
        value = ci.state()
        value.update(externalDurability=report, actualExternalBackupVerified=report['status'] == 'PASS',
                     actualOfflineTokenRefreshVerified=report['status'] == 'PASS',
                     actualContainerRestartRecoveryVerified=False)
        ci.save(value)
    print(json.dumps(report, sort_keys=True))


def persist():
    (location() / 'mobile').mkdir(mode=0o700, exist_ok=True)
    ci.persist()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'selftest', 'packagingtest', 'guard', 'stage', 'build', 'test',
                                         'verify', 'publish', 'pull', 'external', 'persist'))
    args = parser.parse_args()
    try:
        (globals().get(args.phase) or getattr(ci, args.phase))()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'OFFLINE_CI_FAILED'
        value = ci.state()
        value.update(status='STUDIO_DROPBOX_OFFLINE_CANDIDATE_BLOCKED', failedPhase=args.phase,
                     reasonCode=code, errorType=type(error).__name__)
        ci.save(value)
        print(json.dumps({'status': value['status'], 'phase': args.phase, 'reasonCode': code}))
        raise SystemExit(1)
