"""Free CI only: two-container, read-only recovery of the approved checkpoint.

No provider implementation, uploads, receipt creation, key rotation or GPU
execution lives here. Secrets are raw input copies mounted 0600/read-only; the
candidate's actual production reader performs any byte-preserving normalization.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from restart_probe import CHECKPOINT_ID, PROOF_ID

IMAGE = re.compile(r'ghcr\.io/dimon3898-sys/world-simulation-shorts-engine@sha256:[a-f0-9]{64}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
CODE = re.compile(r'[A-Z][A-Z0-9_]{2,95}\Z')
SECRET_ROOT = '/run/world-engine-production-restart-secrets'
DATA_ROOT = '/tmp/world-engine-production-restart'
SECRET_ENV = ('WORLD_ENGINE_STUDIO_BACKUP_KEY',
              'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY',
              'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET',
              'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN')


def fail(code):
    raise RuntimeError(code)


def safe_reason(error):
    candidate = getattr(error, 'code', str(error))
    return candidate if isinstance(candidate, str) and CODE.fullmatch(candidate) else 'PRODUCTION_RESTART_CI_FAILED'


def result_document(result):
    """Read only the bounded, safe driver envelope, never forward raw output."""
    output = result.stdout
    if not isinstance(output, str) or len(output.encode('utf-8')) > 65536:
        fail('PRODUCTION_RESTART_SAFE_DRIVER_RESULT_REQUIRED')
    try:
        document = json.loads(output.strip().splitlines()[-1])
    except (ValueError, IndexError, TypeError):
        fail('PRODUCTION_RESTART_SAFE_DRIVER_RESULT_REQUIRED')
    if not isinstance(document, dict):
        fail('PRODUCTION_RESTART_SAFE_DRIVER_RESULT_REQUIRED')
    if result.returncode or document.get('status') != 'PASS':
        code = document.get('reasonCode')
        fail(code if isinstance(code, str) and CODE.fullmatch(code) else 'PRODUCTION_RESTART_CONTAINER_FAILED')
    return document


def checked_report(document, stage):
    if (document.get('schema') != 'WORLD_ENGINE_CPU_CONTAINER_RESTART_RESULT_V1'
            or document.get('status') != 'PASS' or document.get('stage') != stage
            or document.get('proofId') != PROOF_ID
            or document.get('checkpointId') != CHECKPOINT_ID
            or document.get('imageDigest') != 'sha256:' + 'b' * 64
            or document.get('completedScenes') != 2
            or type(document.get('completedScenes')) is not int
            or document.get('nextIncompleteSceneIds') != ['external-probe-1']
            or document.get('remoteWrites') != 0 or type(document.get('remoteWrites')) is not int
            or type(document.get('authenticatedDownloads')) is not int
            or document.get('authenticatedDownloads') < 1
            or any(document.get(name) is not False for name in (
                'executionAuthorityRestored', 'renderAllowed', 'productionRenderingStarted', 'gpuExecuted'))
            or document.get('newOperatorApprovalRequired') is not True
            or document.get('syntheticMedia') is not True
            or document.get('distinctContainerVerified') is not (stage == 'verify')
            or document.get('retainedBytesAndClaimUnchanged') is not (stage == 'verify')
            or any(not SHA.fullmatch(str(document.get(name))) for name in (
                'retainedTreeSHA256', 'containerIdentitySHA256', 'planSHA256'))):
        fail('PRODUCTION_RESTART_DRIVER_PROOF_INVALID')
    # Explicit allowlist: no unexpected response keys, remote Scene or Secret
    # bodies can enter CI persistence even if a driver response is malformed.
    return {name: document[name] for name in ('stage', 'retainedTreeSHA256',
        'containerIdentitySHA256', 'planSHA256', 'authenticatedDownloads')}


def create_command(ci, image, *, directory, name, stage):
    if stage not in {'restore', 'verify'} or not IMAGE.fullmatch(image):
        fail('PRODUCTION_RESTART_FIXED_CONTAINER_REQUEST_REQUIRED')
    if tuple(ci.SECRET_NAMES) != SECRET_ENV:
        fail('PRODUCTION_RESTART_EXISTING_SECRET_CONTRACT_REQUIRED')
    if (ci.PYTHON != '/opt/world-engine-studio-durability-venv/bin/python'
            or ci.DEST != '/opt/world-engine-studio-dropbox-gpu-production'):
        fail('PRODUCTION_RESTART_FIXED_RUNTIME_ENTRY_REQUIRED')
    command = ['docker', 'create', '--name', name, '--user=1000:1000',
        '--read-only', '--memory=2g', '--cpus=2', '--pids-limit=256',
        '--restart=no', '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--tmpfs', '/tmp:rw,mode=1777',
        '--mount', 'type=bind,source=' + str(directory / 'secrets') + ',target=' + SECRET_ROOT + ',readonly',
        '--mount', 'type=bind,source=' + str(directory / 'data') + ',target=' + DATA_ROOT,
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/tmp', '--env', 'TMPDIR=/tmp',
        '--env', 'WORLD_ENGINE_STUDIO_BACKUP_MODE=dropbox-api',
        '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE=offline',
        '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX=/WORLD_ENGINE_STUDIO_BACKUPS_V1']
    for index, variable in enumerate(SECRET_ENV):
        command.extend(['--env', variable + '_FILE=' + SECRET_ROOT + '/credential-' + str(index)])
    command.extend(['--entrypoint=' + ci.PYTHON, image, '-B', ci.DEST + '/restart_probe.py', stage])
    return command


def run_restart(ci):
    """Called only after published-candidate independent digest pull succeeds."""
    ci.require_free()
    initial = ci.state()
    image = initial.get('imageReference')
    if initial.get('pullVerified') is not True or not isinstance(image, str) or not IMAGE.fullmatch(image):
        fail('PRODUCTION_RESTART_INDEPENDENT_DIGEST_PULL_REQUIRED')
    if tuple(ci.SECRET_NAMES) != SECRET_ENV:
        fail('PRODUCTION_RESTART_EXISTING_SECRET_CONTRACT_REQUIRED')
    inputs = {}
    for variable in SECRET_ENV:
        value = os.environ.get(variable)
        if not isinstance(value, str) or not 1 <= len(value.encode('utf-8')) <= 65536:
            fail('PRODUCTION_RESTART_EXISTING_SECRET_NOT_BOUND')
        inputs[variable] = value.encode('utf-8')
    # Child host commands receive no Dropbox credential environment. Only the
    # strictly read-only, private bind mount reaches either CPU container.
    clean_environment = {name: value for name, value in os.environ.items() if name not in SECRET_ENV}
    report = {'schema': 'WORLD_ENGINE_CPU_CONTAINER_RESTART_PROOF_V1',
        'status': 'FAIL', 'reasonCode': 'PRODUCTION_RESTART_NOT_COMPLETED',
        'proofId': PROOF_ID, 'checkpointId': CHECKPOINT_ID, 'imageReference': image,
        'distinctContainerVerified': False, 'retainedBytesAndClaimUnchanged': False,
        'remoteWrites': 0, 'secretFilesRemoved': False, 'rawSecretBytesPreserved': False,
        'gpuExecuted': False, 'productionRenderingStarted': False,
        'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True}
    directory = None
    created = []
    runner_uid, runner_gid = os.geteuid(), os.getegid()
    owner = str(runner_uid) + ':' + str(runner_gid)
    directory_identity = None
    cleanup_safe = True
    failure = None
    try:
        directory = Path(tempfile.mkdtemp(prefix='world-engine-readonly-restart-',
            dir=os.environ.get('RUNNER_TEMP', '/tmp')))
        directory.chmod(0o700)
        directory_identity = (directory.stat().st_dev, directory.stat().st_ino)
        for child in ('secrets', 'data'):
            (directory / child).mkdir(mode=0o700)
        for index, variable in enumerate(SECRET_ENV):
            path = directory / 'secrets' / ('credential-' + str(index))
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                body = memoryview(inputs[variable])
                while body:
                    written = os.write(descriptor, body)
                    if written < 1:
                        fail('PRODUCTION_RESTART_SECRET_FILE_WRITE_FAILED')
                    body = body[written:]
                os.fsync(descriptor)
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
        ci.run(['sudo', '-n', 'chown', '-R', '--no-dereference', '1000:1000', str(directory)],
               environment=clean_environment, timeout=30)
        stages = []
        for stage in ('restore', 'verify'):
            name = 'world-engine-restart-' + stage + '-' + os.urandom(12).hex()
            result = ci.run(create_command(ci, image, directory=directory, name=name, stage=stage),
                            environment=clean_environment, timeout=60, check=False)
            identity = result.stdout.strip() if isinstance(result.stdout, str) else ''
            if result.returncode or not SHA.fullmatch(identity):
                fail('PRODUCTION_RESTART_CONTAINER_CREATE_FAILED')
            # A full returned container ID proves this invocation created it;
            # never stop/remove an existing container solely by a guessed name.
            created.append(identity)
            result = ci.run(['docker', 'start', '--attach', identity],
                            environment=clean_environment, timeout=600, check=False)
            document = result_document(result)
            stage_report = checked_report(document, stage)
            state = ci.run(['docker', 'inspect', '--format={{json .State}}', identity],
                           environment=clean_environment, timeout=30, check=False)
            try:
                status = json.loads(state.stdout)
            except (ValueError, TypeError):
                fail('PRODUCTION_RESTART_EXIT_STATUS_REQUIRED')
            if state.returncode or status.get('Running') is not False or status.get('ExitCode') != 0:
                fail('PRODUCTION_RESTART_CONTAINER_DID_NOT_EXIT_CLEANLY')
            stages.append({**stage_report, 'containerId': identity, 'exitCode': 0})
        first, second = stages
        if (first['containerId'] == second['containerId']
                or first['containerIdentitySHA256'] == second['containerIdentitySHA256']
                or first['retainedTreeSHA256'] != second['retainedTreeSHA256']
                or first['planSHA256'] != second['planSHA256']):
            fail('PRODUCTION_RESTART_DISTINCT_CONTAINERS_AND_IDENTICAL_CACHE_REQUIRED')
        report.update(status='PASS', reasonCode='PRODUCTION_READ_ONLY_CONTAINER_RESTART_VERIFIED',
            distinctContainerVerified=True, retainedBytesAndClaimUnchanged=True,
            stages=stages, completedScenes=2, nextIncompleteSceneIds=['external-probe-1'])
    except Exception as error:
        failure = safe_reason(error)
    finally:
        for identity in created:
            try:
                ci.run(['docker', 'stop', '--time=5', identity], environment=clean_environment,
                       timeout=30, check=False)
                status = ci.run(['docker', 'inspect', '--format={{.State.Running}}', identity],
                                environment=clean_environment, timeout=30, check=False)
                if status.returncode or status.stdout.strip() != 'false':
                    ci.run(['docker', 'kill', identity], environment=clean_environment, timeout=30, check=False)
                    status = ci.run(['docker', 'inspect', '--format={{.State.Running}}', identity],
                                    environment=clean_environment, timeout=30, check=False)
                    if status.returncode or status.stdout.strip() != 'false':
                        fail('PRODUCTION_RESTART_CONTAINER_STOP_UNCONFIRMED')
                removed = ci.run(['docker', 'rm', identity], environment=clean_environment,
                                 timeout=30, check=False)
                if removed.returncode:
                    fail('PRODUCTION_RESTART_CONTAINER_CLEANUP_FAILED')
            except Exception:
                cleanup_safe = False
                report['cleanupReasonCode'] = 'PRODUCTION_RESTART_CONTAINER_CLEANUP_FAILED'
                failure = failure or report['cleanupReasonCode']
        if directory is not None and cleanup_safe:
            try:
                info = directory.lstat()
                if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != directory_identity:
                    fail('PRODUCTION_RESTART_TEMP_DIRECTORY_CHANGED')
                ci.run(['sudo', '-n', 'chown', '-R', '--no-dereference', owner, str(directory)],
                       environment=clean_environment, timeout=60)
                try:
                    report['rawSecretBytesPreserved'] = all(
                        (directory / 'secrets' / ('credential-' + str(index))).read_bytes() == inputs[variable]
                        for index, variable in enumerate(SECRET_ENV))
                except OSError:
                    report['rawSecretBytesPreserved'] = False
                # Only this invocation's newly created synthetic files/Secret
                # copies are removed, after both containers are proved stopped.
                shutil.rmtree(directory)
                report['secretFilesRemoved'] = not directory.exists()
                if not report['rawSecretBytesPreserved'] or not report['secretFilesRemoved']:
                    fail('PRODUCTION_RESTART_SECRET_PRESERVATION_OR_CLEANUP_FAILED')
            except Exception:
                report['cleanupReasonCode'] = 'PRODUCTION_RESTART_SECRET_PRESERVATION_OR_CLEANUP_FAILED'
                failure = failure or report['cleanupReasonCode']
        elif directory is not None:
            report['cleanupRequiresOperatorReview'] = True
        if failure:
            report.update(status='FAIL', reasonCode=failure,
                          distinctContainerVerified=False, retainedBytesAndClaimUnchanged=False)
        value = ci.state()
        value.update(restartRecovery=report,
            actualContainerRestartRecoveryVerified=report['status'] == 'PASS')
        ci.save(value)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')), flush=True)
    if report['status'] != 'PASS':
        fail(report['reasonCode'])
    return report
