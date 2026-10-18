"""Offline OAuth at the frozen durability engine's existing injection seams.

Only authentication and child entry points change. Scene checkpoints, encrypted
objects, restore provenance, owner/Origin/CSRF checks and GPU policy stay in the
unchanged parent implementation.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from offline_frozen import DURABILITY, HERE, modules
from renewal import OfflineOpener, TokenProvider

OAUTH_INPUTS = (
    ('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY',
     'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY_FILE', 'dropbox-app-key'),
    ('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET',
     'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET_FILE', 'dropbox-app-secret'),
    ('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN',
     'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN_FILE', 'dropbox-refresh-token'),
)
STATIC_TOKEN = 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN'
_PROVIDER_LOCK = threading.Lock()
_PROVIDER = None
_PROVIDER_BINDING = None
_INSTALL_LOCK = threading.Lock()
_INSTALLED = False


@contextmanager
def _access_scratch(old):
    """Choose only a new directory accepted by the unchanged private policy."""
    selected = None
    for parent in (Path('/tmp'), HERE):
        temporary = None
        try:
            temporary = tempfile.TemporaryDirectory(prefix='studio-offline-access-', dir=parent)
            with old.parent.runtime()._cache().PrivateTree(temporary.name):
                pass
            selected = temporary
            break
        except Exception:
            if temporary is not None:
                temporary.cleanup()
    if selected is None:
        raise old.stores.BackupError('DURABILITY_OAUTH_PRIVATE_SCRATCH_UNAVAILABLE')
    try:
        yield Path(selected.name)
    finally:
        selected.cleanup()


def _provider():
    """Reuse only an in-memory access token; changed Secret files rebind it."""
    global _PROVIDER, _PROVIDER_BINDING
    old = modules()
    files, fingerprints = [], []
    for _, name, _ in OAUTH_INPUTS:
        raw = old.backend.secret_file(name)
        path = os.environ[name]
        files.append(path)
        # Never logged, serialized or put in a backup. Re-read the strict private
        # files on each factory call so a stale cached token cannot hide a
        # permission/path change.
        fingerprints.append((path, hashlib.sha256(raw).digest()))
    binding = tuple(fingerprints)
    with _PROVIDER_LOCK:
        if _PROVIDER is None or _PROVIDER_BINDING != binding:
            _PROVIDER = TokenProvider(*files)
            _PROVIDER_BINDING = binding
        return _PROVIDER


def make_vault_from_env():
    """Exact frozen DropboxStore + renewable bearer; no static-token fallback."""
    old = modules()
    if os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_MODE') != 'dropbox-api':
        raise old.stores.BackupError('DURABILITY_DROPBOX_API_MODE_REQUIRED')
    if os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE', 'offline') != 'offline':
        raise old.stores.BackupError('DURABILITY_OAUTH_OFFLINE_MODE_REQUIRED')
    old.backend.secret_file('WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE')
    key_path = Path(os.environ['WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE'])
    key = old.vault.read_key_file(key_path)
    provider = _provider()
    token = provider.access_token()
    # The frozen class deliberately reads a private file. Preserve that contract
    # instead of replacing its class or bypassing the production exact-type gate.
    # Never caller-controlled TMPDIR or the read-only Secret mount. The frozen
    # private-tree policy verifies every newly created 0700 scratch directory.
    with _access_scratch(old) as scratch:
        descriptor, temporary = tempfile.mkstemp(prefix='access-', dir=scratch)
        identity = None
        try:
            os.fchmod(descriptor, 0o600)
            body = token.encode('ascii')
            view = memoryview(body)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise old.stores.BackupError('DURABILITY_OAUTH_PRIVATE_TOKEN_WRITE_FAILED')
                view = view[written:]
            identity = os.fstat(descriptor)
            store = old.stores.DropboxStore(
                os.environ.get('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX',
                               '/WORLD_ENGINE_STUDIO_BACKUPS_V1'), temporary)
        finally:
            # Delete only this new, still-identical ephemeral file. Never touch
            # retained key/refresh files or any previous output.
            if identity is None:
                identity = os.fstat(descriptor)
            try:
                current = os.stat(temporary, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    os.unlink(temporary)
            finally:
                os.close(descriptor)
    store._opener = OfflineOpener(provider, store._opener)
    return old.vault.Vault(key, store)


def redirect_command(command):
    """Redirect only four pinned durability children; leave GPU commands alone."""
    if not isinstance(command, (list, tuple)):
        return command
    copied = list(command)
    stages = {'durable_server.py': 'server', 'runtime_entry.py': 'runtime',
              'durable_coordinator.py': 'coordinator', 'startup_restore.py': 'startup-restore'}
    if len(copied) >= 3 and copied[1] == '-B':
        for filename, stage in stages.items():
            if copied[2] == str(DURABILITY / filename):
                return [sys.executable, '-B', str(HERE / 'offline_entry.py'), stage, *copied[3:]]
    return copied


class ProcessRedirect:
    """Module-local subprocess proxy, keeping detach/UID/timeout arguments."""
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        return getattr(self.original, name)

    def Popen(self, command, **kwargs):
        return self.original.Popen(redirect_command(command), **kwargs)

    def run(self, command, **kwargs):
        return self.original.run(redirect_command(command), **kwargs)


def require_metadata_access(vault):
    """Exercise the real App Folder metadata permission without exposing names."""
    old = modules()
    store = old.preflight.require_dropbox_transport(vault)
    raw = store._request('list', argument={'path': '', 'recursive': False,
                         'include_deleted': False, 'limit': 1})
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        raise old.stores.BackupError('DURABILITY_OAUTH_METADATA_RESPONSE_INVALID') from None
    # Dropbox documents limit as approximate, not a strict response count.
    if (not isinstance(result, dict) or not isinstance(result.get('entries'), list)
            or len(result['entries']) > 2000 or type(result.get('has_more')) is not bool):
        raise old.stores.BackupError('DURABILITY_OAUTH_METADATA_RESPONSE_INVALID')
    return True


def install():
    """Install independent module-instance adapters in every detached process."""
    global _INSTALLED
    with _INSTALL_LOCK:
        old = modules()
        if _INSTALLED:
            return old
        old.backend.make_vault_from_env = make_vault_from_env
        # These are module attributes, never mutations of shared subprocess
        # functions. Each unchanged ProcessAdapter still enforces its fixed path.
        old.backend.subprocess = ProcessRedirect(subprocess)
        if old.backend._INSTALLED:
            adapter = old.backend.backend().subprocess
            if type(adapter) is not old.backend.ProcessAdapter:
                raise old.stores.BackupError('DURABILITY_OAUTH_RUNTIME_ADAPTER_CONFLICT')
            adapter.original = old.backend.subprocess
        old.coordinator.subprocess = ProcessRedirect(subprocess)
        old.bootstrap.subprocess = ProcessRedirect(subprocess)
        old.bootstrap.SECRET_INPUTS = (old.bootstrap.SECRET_INPUTS[0], *OAUTH_INPUTS)
        original_prepare = old.bootstrap.prepare_backup_secrets

        def prepare(environ, state_root, *, uid=1000, gid=1000):
            environment = dict(environ)
            environment.pop(STATIC_TOKEN, None)
            environment.pop(STATIC_TOKEN + '_FILE', None)
            return original_prepare(environment, state_root, uid=uid, gid=gid)

        old.bootstrap.prepare_backup_secrets = prepare
        original_restore = old.bootstrap.prepare_startup_restore

        def prepare_restore(environ, *, run=None):
            if run is None:
                run = old.bootstrap.subprocess.run
            else:
                supplied = run
                run = lambda command, **kwargs: supplied(redirect_command(command), **kwargs)
            return original_restore(environ, run=run)

        old.bootstrap.prepare_startup_restore = prepare_restore
        original_external_check = old.cli.external_check

        def external_check(vault, private_work_root):
            require_metadata_access(vault)
            result = original_external_check(vault, private_work_root)
            return {**result, 'offlineTokenRefreshVerified': True,
                    'metadataReadVerified': True}

        old.cli.external_check = external_check
        _INSTALLED = True
        return old
