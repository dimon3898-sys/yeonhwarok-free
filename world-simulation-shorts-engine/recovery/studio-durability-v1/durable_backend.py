"""Fail-closed durability around the frozen Studio backend, never a renderer."""
from __future__ import annotations
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

from parent import HERE, RECOVERY, STUDIO, runtime


class DurabilityLaunchBlocked(RuntimeError):
    """Known pre-spawn failure, unlike an ambiguous detached-launch result."""
    def __init__(self, code, public_state):
        self.code, self.public_state = code, public_state
        super().__init__(code)


def secret_file(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('DURABILITY_SECRET_FILE_REQUIRED')
    path = Path(value)
    if (not path.is_absolute() or '..' in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))
            or path == Path('/world-storage') or path.is_relative_to('/world-storage')):
        raise RuntimeError('DURABILITY_PRIVATE_SECRET_PATH_REQUIRED')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_gid != os.getegid() or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1 or not 1 <= info.st_size <= 65536):
            raise RuntimeError('DURABILITY_PRIVATE_SECRET_FILE_REQUIRED')
        raw = os.read(fd, 65537)
        if len(raw) != info.st_size:
            raise RuntimeError('DURABILITY_SECRET_CHANGED')
        return raw
    finally:
        os.close(fd)


def make_vault_from_env():
    if os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_MODE') != 'dropbox-api':
        raise RuntimeError('DURABILITY_DROPBOX_API_MODE_REQUIRED')
    from stores import DropboxStore
    from vault import Vault, read_key_file
    secret_file('WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE')
    key = read_key_file(os.environ['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
    # The token remains in its private file and is never put in a process argv.
    secret_file('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN_FILE')
    store = DropboxStore(os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX',
                                        '/WORLD_ENGINE_STUDIO_BACKUPS_V1'),
                         os.environ['WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN_FILE'])
    return Vault(key, store)


def checkpoints():
    from checkpoint import Checkpoints
    from preflight import require_external_proof
    vault = make_vault_from_env()
    require_external_proof(vault, os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID'))
    return Checkpoints(vault, production=True)


def save(plan, audio, profile_id, control_root, coordinator_root=None):
    result = checkpoints().save(plan, audio, profile_id, Path(control_root),
                                coordinator_root=coordinator_root)
    if (not isinstance(result, dict) or result.get('remotePersistenceVerified') is not True
            or result.get('externalDownloadVerified') is not True):
        raise RuntimeError('DURABILITY_EXTERNAL_ROUNDTRIP_REQUIRED')
    return result


class ProcessAdapter:
    """Intercept only two fixed entry points in this isolated runtime instance."""
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        return getattr(self.original, name)

    def Popen(self, command, **kwargs):
        command = list(command)
        if len(command) >= 4 and command[:3] == ['/usr/bin/python3', '-B', str(STUDIO / 'studio_runtime.py')]:
            if command[3] != 'worker':
                raise RuntimeError('DURABILITY_FIXED_WORKER_REQUIRED')
            control = Path(command[command.index('--control-root') + 1])
            job_id = command[command.index('--job-id') + 1]
            old = runtime()
            with old._cache().PrivateTree(control) as root, root.child(job_id) as job:
                state, plan, audio = job.json('STATE.json'), job.json('PLAN.json'), job.json('AUDIO.json')
                try:
                    save(plan, audio, state['profileId'], control)
                except Exception as error:
                    # The enclosing unchanged supervisor holds this job lock.
                    # No child has been spawned, so this is a determinate failure.
                    code = old._safe(error)
                    state.update(state='FAILED', phase='DURABLE_BACKUP_FAILED', errorCode=code,
                                 supervisorIdentity=None, updatedAt=old._stamp(), finishedUnix=time.time())
                    job.write_json('STATE.json', state, replace=True)
                    raise DurabilityLaunchBlocked(code, old._public(state)) from None
            # No detached child exists if the initial backup fails.
            command[0] = sys.executable
            command[2] = str(HERE / 'runtime_entry.py')
        return self.original.Popen(command, **kwargs)

    def run(self, command, **kwargs):
        command = list(command)
        candidates = {str(RECOVERY / relative / 'orchestrator.py'): profile
                      for profile, relative in runtime().PROFILES.items()}
        if len(command) >= 4 and command[2] in candidates:
            profile = candidates[command[2]]
            action = command[3]
            if action not in {'start', 'status'}:
                raise RuntimeError('DURABILITY_FIXED_COORDINATOR_ACTION_REQUIRED')
            plan_path = Path(command[command.index('--plan') + 1])
            command = [*command[:2], str(HERE / 'durable_coordinator.py'),
                       '--profile', profile, '--studio-job-dir', str(plan_path.parent), *command[3:]]
            command[0] = sys.executable
        return self.original.run(command, **kwargs)


_INSTALLED = False


def backend():
    global _INSTALLED
    original = runtime()
    if not _INSTALLED:
        original.subprocess = ProcessAdapter(subprocess)
        _INSTALLED = True
    return original


def preflight(plan, profile_id, *, control_root, export_root):
    report = backend().preflight(plan, profile_id, control_root=control_root, export_root=export_root)
    try:
        # Read-only transport/configuration check. Only the actual queued job
        # can publish Scene+audio checkpoints; never create a newer dummy
        # checkpoint that could obscure a useful recovery receipt.
        checkpoints()
        check = {'name': 'DURABLE_BACKUP', 'status': 'PASS', 'facts': {
            'externalProofFreshlyVerified': True, 'checkpointPublished': False,
            'currentSceneCheckpointRequiredBeforeSpawn': True}}
    except Exception as error:
        check = {'name': 'DURABLE_BACKUP', 'status': 'BLOCKED', 'code': backend()._safe(error)}
    checks = [*report.get('checks', []), check]
    allowed = report.get('renderAllowed') is True and check['status'] == 'PASS'
    return {**report, 'checks': checks, 'status': 'PASS' if allowed else 'BLOCKED', 'renderAllowed': allowed}


def __getattr__(name):
    # Public production operations still run unchanged authorization/claims.
    if name in {'studio_status', 'default_plan', 'bind_render_image', 'validate_render_plan'}:
        return getattr(backend(), name)
    raise AttributeError(name)


def _launch(name, *args, **kwargs):
    try:
        return getattr(backend(), name)(*args, **kwargs)
    except DurabilityLaunchBlocked as error:
        # Preserve the unchanged controller's claim/history with a real FAILED
        # job receipt. Never reset a claim or retry a failed backup automatically.
        return error.public_state


def start_studio_job(*args, **kwargs):
    return _launch('start_studio_job', *args, **kwargs)


def start_studio_revision(*args, **kwargs):
    return _launch('start_studio_revision', *args, **kwargs)


def start_studio_recovery(*args, **kwargs):
    return _launch('start_studio_recovery', *args, **kwargs)
