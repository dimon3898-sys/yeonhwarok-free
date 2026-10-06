"""Owner authentication and bounded request policy, outside the approved core."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import threading
import time
from urllib.parse import urlsplit


class SecurityError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def private_json(path, value):
    """Only deployment-owned private state; never logs the value."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise SecurityError('UNSAFE_STATE_PATH', '상태 파일 경로를 확인해 주세요.')
    tmp = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _private_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SecurityError('UNSAFE_ACCESS_FILE', '소유자 접근 파일을 확인해 주세요.')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise SecurityError('ACCESS_FILE_PERMISSIONS', '소유자 접근 파일은 0600 권한이어야 합니다.')
    return path


def ensure_access_file(path):
    """Create a plaintext owner code once, returning its path, never its secret."""
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = False
    if not path.exists() and not path.is_symlink():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(secrets.token_urlsafe(32) + '\n')
            f.flush()
            os.fsync(f.fileno())
        created = True
    _private_file(path)
    return {'path': str(path), 'created': created}


def _owner_code(path):
    p = _private_file(path)
    if p.stat().st_size > 4096:
        raise SecurityError('INVALID_ACCESS_FILE', '소유자 접근 파일 형식이 잘못되었습니다.')
    value = p.read_text(encoding='utf-8').strip()
    # Controlled JSON fixtures are useful for browser tests; production uses .txt.
    if value.startswith('{'):
        try:
            value = json.loads(value)['password']
        except (ValueError, KeyError, TypeError):
            raise SecurityError('INVALID_ACCESS_FILE', '소유자 접근 파일 형식이 잘못되었습니다.') from None
    if not isinstance(value, str) or not 16 <= len(value) <= 512:
        raise SecurityError('INVALID_ACCESS_FILE', '소유자 접근 코드 길이를 확인해 주세요.')
    return value


def _derive(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)


class OwnerSessions:
    cookie_name = 'world_owner_session'

    def __init__(self, access_file, state_file, *, lifetime=12 * 3600, clock=time.time):
        self.path, self.clock, self.lifetime = Path(state_file), clock, lifetime
        self.lock = threading.RLock()
        code = _owner_code(access_file)
        record = None
        if self.path.exists():
            _private_file(self.path)
            try:
                record = json.loads(self.path.read_text())
                salt = bytes.fromhex(record['salt'])
                if not hmac.compare_digest(_derive(code, salt).hex(), record['digest']):
                    record = None
            except (ValueError, KeyError, TypeError):
                record = None
        if record is None:
            salt = secrets.token_bytes(16)
            record = {'salt': salt.hex(), 'digest': _derive(code, salt).hex(),
                      'signing_key': secrets.token_bytes(32).hex(), 'sessions': {}}
            private_json(self.path, record)
        self.record = record
        self.salt = bytes.fromhex(record['salt'])
        self.key = bytes.fromhex(record['signing_key'])
        # Plaintext is not copied into auth state, tickets, responses or logs.
        del code

    def _clean(self):
        now = self.clock()
        self.record['sessions'] = {k: v for k, v in self.record.get('sessions', {}).items()
                                   if isinstance(v, (int, float)) and v > now}

    def login(self, password):
        if not isinstance(password, str) or not 1 <= len(password) <= 512:
            return None
        if not hmac.compare_digest(_derive(password, self.salt).hex(), self.record['digest']):
            return None
        with self.lock:
            self._clean()
            while len(self.record['sessions']) >= 16:
                oldest = min(self.record['sessions'], key=self.record['sessions'].get)
                self.record['sessions'].pop(oldest)
            sid, expiry = secrets.token_hex(20), int(self.clock() + self.lifetime)
            payload = base64.urlsafe_b64encode(json.dumps({'sid': sid, 'exp': expiry}, separators=(',', ':')).encode()).decode().rstrip('=')
            signature = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
            self.record['sessions'][sid] = expiry
            private_json(self.path, self.record)
            return payload + '.' + signature

    def claims(self, token):
        if not isinstance(token, str) or len(token) > 1024:
            return None
        try:
            payload, supplied = token.split('.')
            expected = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, supplied):
                return None
            claim = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
            with self.lock:
                valid = (claim['exp'] > self.clock() and
                         self.record.get('sessions', {}).get(claim['sid']) == claim['exp'])
            return claim if valid else None
        except (ValueError, KeyError, TypeError, UnicodeError):
            return None

    def logout(self, token):
        claim = self.claims(token)
        if claim:
            with self.lock:
                self.record['sessions'].pop(claim['sid'], None)
                private_json(self.path, self.record)


class RateLimiter:
    def __init__(self, clock=time.monotonic, maximum_keys=1024):
        self.clock, self.maximum_keys = clock, maximum_keys
        self.lock, self.buckets = threading.Lock(), {}

    def allow(self, key, *, count, window=60):
        with self.lock:
            now = self.clock()
            if key not in self.buckets and len(self.buckets) >= self.maximum_keys:
                self.buckets = {k: [t for t in ts if t > now - window]
                                for k, ts in self.buckets.items() if any(t > now - window for t in ts)}
                if len(self.buckets) >= self.maximum_keys:
                    return False
            values = [t for t in self.buckets.get(key, []) if t > now - window]
            if len(values) >= count:
                self.buckets[key] = values
                return False
            values.append(now)
            self.buckets[key] = values
            return True


class RequestPolicy:
    def __init__(self, public_origins=(), *, local_port=7860):
        self.origins = set()
        self.hosts = {f'127.0.0.1:{local_port}', f'localhost:{local_port}'}
        for value in public_origins:
            u = urlsplit(value)
            if u.scheme not in {'https', 'http'} or not u.netloc or u.path not in {'', '/'} or u.query or u.fragment or u.username:
                raise SecurityError('INVALID_PUBLIC_ORIGIN', '공개 주소 설정을 확인해 주세요.')
            if u.scheme != 'https' and u.hostname not in {'localhost', '127.0.0.1'}:
                raise SecurityError('HTTPS_REQUIRED', '공개 주소에는 HTTPS가 필요합니다.')
            self.origins.add(f'{u.scheme}://{u.netloc}')
            self.hosts.add(u.netloc)
        self.secure_cookie = any(x.startswith('https://') for x in self.origins)

    def check_host(self, host):
        if host not in self.hosts:
            raise SecurityError('INVALID_HOST', '허용되지 않은 주소입니다.', 400)

    def check_origin(self, origin, host):
        self.check_host(host)
        expected = self.origins | {f'http://{h}' for h in self.hosts if h.split(':')[0] in {'localhost', '127.0.0.1'}}
        if origin not in expected:
            raise SecurityError('INVALID_ORIGIN', '같은 사이트의 요청만 허용됩니다.', 403)


def content_length(headers, maximum, *, required=True):
    values = headers.get_all('Content-Length', [])
    if headers.get('Transfer-Encoding') or len(values) != 1 or not values[0].isdigit() or len(values[0]) > 12:
        if not required and not values and not headers.get('Transfer-Encoding'):
            return 0
        raise SecurityError('INVALID_BODY_LENGTH', '요청 길이를 확인해 주세요.', 400)
    size = int(values[0])
    if size <= 0 or size > maximum:
        raise SecurityError('REQUEST_TOO_LARGE', '요청 크기 제한을 확인해 주세요.', 413)
    return size


def owned_path(root, relative):
    root = Path(root).resolve()
    candidate = root / relative
    if any(part in {'.', '..'} or part.startswith('.') for part in Path(relative).parts):
        raise SecurityError('INVALID_FILE', '허용되지 않은 파일입니다.', 404)
    walk = candidate
    while walk != root and root in walk.parents:
        if walk.is_symlink():
            raise SecurityError('INVALID_FILE', '허용되지 않은 파일입니다.', 404)
        walk = walk.parent
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise SecurityError('INVALID_FILE', '허용되지 않은 파일입니다.', 404)
    return resolved
