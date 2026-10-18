"""Opaque, additive checkpoint objects on an untrusted mount or Dropbox HTTPS.

Neither checksums nor this store confer provenance: vault authentication does.
No network call is made until get/put, and requests never retry or redirect.
"""
from __future__ import annotations

import json
import ctypes
import errno
import os
from pathlib import Path
import re
import stat
import urllib.error
import urllib.request

MAX_OBJECT = 4 * 1024**2
OID = re.compile(r'[0-9a-f]{64}\Z')
MAX_RECEIPTS = 4096


def _receipt_limit(limit):
    if type(limit) is not int or not 1 <= limit <= MAX_RECEIPTS:
        raise BackupError('DURABILITY_RECEIPT_LIMIT_INVALID')
    return limit


class BackupError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class NotFound(BackupError):
    def __init__(self):
        super().__init__('DURABILITY_OBJECT_NOT_FOUND')


class Conflict(BackupError):
    def __init__(self):
        super().__init__('DURABILITY_OBJECT_CONFLICT')


def _oid(value):
    if not isinstance(value, str) or not OID.fullmatch(value):
        raise BackupError('DURABILITY_OBJECT_ID_INVALID')
    return value


def _payload(value):
    if not isinstance(value, bytes) or not 1 <= len(value) <= MAX_OBJECT:
        raise BackupError('DURABILITY_OBJECT_SIZE_INVALID')
    return value


def _publish_noreplace(directory, temporary, oid):
    """Linux atomic no-replace rename: partial objects never acquire final IDs.

    A filesystem lacking this primitive is not promoted to a durable backend.
    Do not replace it with overwrite-rename or a check-then-rename race.
    """
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, 'renameat2', None)
    if rename is None:
        raise BackupError('DURABILITY_ATOMIC_PUBLISH_UNSUPPORTED')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, temporary.encode('ascii'), directory, oid.encode('ascii'), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise Conflict()
        if code in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP}:
            raise BackupError('DURABILITY_ATOMIC_PUBLISH_UNSUPPORTED')
        raise BackupError('DURABILITY_ATOMIC_PUBLISH_FAILED')


def _directory(path):
    """Pin every directory using openat; never follow a mount-side symlink."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise BackupError('DURABILITY_ABSOLUTE_PATH_REQUIRED')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_private_file(path, *, limit=16384):
    """Secrets must be separate UID1000, singly linked 0600 regular files."""
    path = Path(path)
    parent = fd = None
    try:
        parent = _directory(path.parent)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 1000
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                or not 1 <= before.st_size <= limit):
            raise BackupError('DURABILITY_PRIVATE_SECRET_REQUIRED')
        body = os.read(fd, limit + 1)
        after = os.fstat(fd)
        current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        if identity(before) != identity(after) or identity(current) != identity(after) or len(body) != before.st_size:
            raise BackupError('DURABILITY_SECRET_CHANGED')
        return body
    except BackupError:
        raise
    except OSError:
        raise BackupError('DURABILITY_PRIVATE_SECRET_REQUIRED') from None
    finally:
        for item in (fd, parent):
            if item is not None:
                os.close(item)


class MountedStore:
    """Mounted readback is not proof of external Dropbox synchronization."""
    external_verified = False

    def __init__(self, root):
        self.root = Path(root)
        # Root creation belongs to the explicitly configured mount adapter.
        fd = _directory(self.root)
        os.close(fd)

    def get(self, oid):
        _oid(oid)
        directory = fd = None
        try:
            directory = _directory(self.root)
            try:
                fd = os.open(oid, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                raise NotFound() from None
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 1 <= before.st_size <= MAX_OBJECT:
                raise BackupError('DURABILITY_STORED_OBJECT_INVALID')
            body = bytearray()
            while len(body) <= MAX_OBJECT:
                chunk = os.read(fd, min(1024**2, MAX_OBJECT + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            after = os.fstat(fd)
            current = os.stat(oid, dir_fd=directory, follow_symlinks=False)
            facts = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
            if facts(before) != facts(after) or facts(current) != facts(after) or len(body) != before.st_size:
                raise BackupError('DURABILITY_STORED_OBJECT_CHANGED')
            return bytes(body)
        except BackupError:
            raise
        except OSError:
            raise BackupError('DURABILITY_MOUNT_READ_FAILED') from None
        finally:
            for item in (fd, directory):
                if item is not None:
                    os.close(item)

    def put(self, oid, payload):
        _oid(oid)
        _payload(payload)
        directory = fd = None
        temporary = '.pending-' + os.urandom(16).hex()
        published = False
        try:
            directory = _directory(self.root)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise BackupError('DURABILITY_MOUNT_WRITE_FAILED')
                view = view[written:]
            os.fsync(fd)
            try:
                _publish_noreplace(directory, temporary, oid)
                published = True
            except Conflict:
                if self.get(oid) != payload:
                    raise
            # Shared/FUSE fsync errors stay failures; never claim persistence.
            os.fsync(directory)
        except BackupError:
            raise
        except OSError:
            raise BackupError('DURABILITY_MOUNT_WRITE_FAILED') from None
        finally:
            if not published and fd is not None and directory is not None:
                try:
                    held, current = os.fstat(fd), os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                    if (held.st_dev, held.st_ino) == (current.st_dev, current.st_ino):
                        os.unlink(temporary, dir_fd=directory)
                except OSError:
                    pass
            for item in (fd, directory):
                if item is not None:
                    os.close(item)
        if self.get(oid) != payload:
            raise BackupError('DURABILITY_MOUNT_READBACK_FAILED')

    def _receipts(self, *, create=False):
        directory = _directory(self.root)
        try:
            if create:
                try:
                    os.mkdir('receipts', 0o700, dir_fd=directory)
                    os.fsync(directory)
                except FileExistsError:
                    pass
            try:
                receipt_fd = os.open('receipts', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            except FileNotFoundError:
                raise NotFound() from None
            os.close(receipt_fd)
        except BackupError:
            raise
        except OSError:
            raise BackupError('DURABILITY_RECEIPT_DIRECTORY_INVALID') from None
        finally:
            os.close(directory)
        return MountedStore(self.root / 'receipts')

    def publish_receipt(self, receipt_manifest_id):
        """Append a copy of an already encrypted/authenticated manifest root."""
        _oid(receipt_manifest_id)
        payload = self.get(receipt_manifest_id)
        self._receipts(create=True).put(receipt_manifest_id, payload)

    def list_receipts(self, limit=256):
        _receipt_limit(limit)
        try:
            receipts = self._receipts()
        except NotFound:
            return []
        directory = _directory(receipts.root)
        result, scanned = [], 0
        try:
            with os.scandir(directory) as rows:
                for row in rows:
                    scanned += 1
                    if scanned > MAX_RECEIPTS + 128:
                        raise BackupError('DURABILITY_RECEIPT_CATALOG_TOO_LARGE')
                    if row.name.startswith('.pending-'):
                        continue  # Uncommitted ciphertext is never a receipt.
                    if not OID.fullmatch(row.name) or not row.is_file(follow_symlinks=False):
                        raise BackupError('DURABILITY_RECEIPT_CATALOG_INVALID')
                    result.append(row.name)
                    if len(result) > limit:
                        raise BackupError('DURABILITY_RECEIPT_CATALOG_TOO_LARGE')
        finally:
            os.close(directory)
        return sorted(result)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BackupError('DURABILITY_HTTP_REDIRECT_REJECTED')


class DropboxStore:
    """Real HTTPS content upload/download with an independently injected token.

    external_verified identifies the transport, not a successful operation.
    The caller must authenticate and rehash a completed remote readback before
    recording an externally verified checkpoint. No mocked result is hardware
    or Dropbox evidence.
    """
    external_verified = True

    def __init__(self, prefix, token_file):
        if (not isinstance(prefix, str) or not re.fullmatch(r'/(?:[A-Za-z0-9_-]{1,100})(?:/[A-Za-z0-9_-]{1,100}){0,7}', prefix)
                or len(prefix) > 512):
            raise BackupError('DURABILITY_DROPBOX_PREFIX_INVALID')
        self.prefix = prefix
        raw = read_private_file(token_file, limit=8192)
        try:
            token = raw.decode('ascii').strip()
        except UnicodeError:
            raise BackupError('DURABILITY_DROPBOX_TOKEN_INVALID') from None
        if not 16 <= len(token) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise BackupError('DURABILITY_DROPBOX_TOKEN_INVALID')
        self._token = token
        self._opener = urllib.request.build_opener(_NoRedirect())
        self._prefix_ready = False

    def _request(self, endpoint, *, argument=None, data=None):
        routes = {'download': 'https://content.dropboxapi.com/2/files/download',
                  'upload': 'https://content.dropboxapi.com/2/files/upload',
                  'mkdir': 'https://api.dropboxapi.com/2/files/create_folder_v2',
                  'list': 'https://api.dropboxapi.com/2/files/list_folder',
                  'continue': 'https://api.dropboxapi.com/2/files/list_folder/continue'}
        headers = {'Authorization': 'Bearer ' + self._token}
        if endpoint in {'download', 'upload'}:
            headers['Dropbox-API-Arg'] = json.dumps(argument, separators=(',', ':'), ensure_ascii=True)
            if endpoint == 'upload':
                headers['Content-Type'] = 'application/octet-stream'
            body = b'' if data is None else data
        else:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(argument, separators=(',', ':')).encode('ascii')
        request = urllib.request.Request(routes[endpoint], data=body, headers=headers, method='POST')
        try:
            with self._opener.open(request, timeout=30) as response:
                if response.status != 200 or response.geturl() != routes[endpoint]:
                    raise BackupError('DURABILITY_DROPBOX_HTTP_FAILED')
                limit = MAX_OBJECT if endpoint == 'download' else (1024**2 if endpoint in {'list', 'continue'} else 64 * 1024)
                result = response.read(limit + 1)
                if len(result) > limit:
                    raise BackupError('DURABILITY_DROPBOX_RESPONSE_TOO_LARGE')
                return result
        except urllib.error.HTTPError as error:
            # Parse only bounded protocol tags; never log response or token.
            try:
                result = json.loads(error.read(16385))
                summary = result.get('error_summary', '') if isinstance(result, dict) else ''
            except Exception:
                summary = ''
            if error.code == 409 and isinstance(summary, str):
                if summary.startswith('path/not_found/'):
                    raise NotFound() from None
                if summary.startswith('path/conflict/'):
                    raise Conflict() from None
            if error.code in {401, 403}:
                raise BackupError('DURABILITY_DROPBOX_AUTH_FAILED') from None
            raise BackupError('DURABILITY_DROPBOX_HTTP_FAILED') from None
        except BackupError:
            raise
        except Exception:
            raise BackupError('DURABILITY_DROPBOX_CONNECTION_FAILED') from None

    def get(self, oid):
        return _payload(self._request('download', argument={'path': self.prefix + '/' + _oid(oid)}))

    def _ensure_prefix(self):
        if self._prefix_ready:
            return
        path = ''
        for part in self.prefix[1:].split('/'):
            path += '/' + part
            try:
                self._request('mkdir', argument={'path': path, 'autorename': False})
            except Conflict:
                pass  # A file at this path still makes the subsequent upload fail.
        self._prefix_ready = True

    def put(self, oid, payload):
        _oid(oid)
        _payload(payload)
        try:
            if self.get(oid) != payload:
                raise Conflict()
            return
        except NotFound:
            pass
        self._ensure_prefix()
        self._request('upload', argument={'path': self.prefix + '/' + oid,
            'mode': 'add', 'autorename': False, 'mute': True, 'strict_conflict': True}, data=payload)
        if self.get(oid) != payload:
            raise BackupError('DURABILITY_DROPBOX_READBACK_FAILED')

    def _receipt_store(self):
        child = object.__new__(DropboxStore)
        child.prefix, child._token = self.prefix + '/receipts', self._token
        child._opener, child._prefix_ready = self._opener, False
        return child

    def publish_receipt(self, receipt_manifest_id):
        _oid(receipt_manifest_id)
        payload = self.get(receipt_manifest_id)
        self._receipt_store().put(receipt_manifest_id, payload)

    def list_receipts(self, limit=256):
        _receipt_limit(limit)
        result, seen, cursor = [], set(), None
        for _ in range(16):
            try:
                if cursor is None:
                    raw = self._request('list', argument={'path': self.prefix + '/receipts',
                        'recursive': False, 'include_deleted': False, 'limit': min(1000, limit + 1)})
                else:
                    raw = self._request('continue', argument={'cursor': cursor})
            except NotFound:
                if cursor is None:
                    return []
                raise BackupError('DURABILITY_RECEIPT_CATALOG_CHANGED') from None
            try:
                page = json.loads(raw)
            except (ValueError, TypeError):
                raise BackupError('DURABILITY_RECEIPT_CATALOG_INVALID') from None
            if (not isinstance(page, dict) or not isinstance(page.get('entries'), list)
                    or len(page['entries']) > 1000 or type(page.get('has_more')) is not bool):
                raise BackupError('DURABILITY_RECEIPT_CATALOG_INVALID')
            for entry in page['entries']:
                if (not isinstance(entry, dict) or entry.get('.tag') != 'file'
                        or not isinstance(entry.get('name'), str) or not OID.fullmatch(entry['name'])
                        or entry['name'] in seen or type(entry.get('size')) is not int
                        or not 1 <= entry['size'] <= MAX_OBJECT
                        or entry.get('path_lower') != (self.prefix + '/receipts/' + entry['name']).lower()):
                    raise BackupError('DURABILITY_RECEIPT_CATALOG_INVALID')
                seen.add(entry['name'])
                result.append(entry['name'])
                if len(result) > limit:
                    raise BackupError('DURABILITY_RECEIPT_CATALOG_TOO_LARGE')
            if not page['has_more']:
                return sorted(result)
            new_cursor = page.get('cursor')
            if (not isinstance(new_cursor, str) or not 1 <= len(new_cursor) <= 8192
                    or new_cursor == cursor):
                raise BackupError('DURABILITY_RECEIPT_CURSOR_INVALID')
            cursor = new_cursor
        raise BackupError('DURABILITY_RECEIPT_PAGE_LIMIT_REACHED')
