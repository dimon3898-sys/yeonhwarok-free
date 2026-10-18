"""Owner-authorized HTTPS trust establishment, separate from render admission.

No authority is learned from a request header. The owner explicitly supplies
and confirms the candidate; only an authenticated transaction may persist it.
The frozen Studio authentication and fixed-origin request policy are reused.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import stat
import threading
import time
from urllib.parse import urlsplit

from frozen import load_originals

_originals = load_originals()
security = _originals.server.security
SetupError = security.SecurityError
SCHEMA = 'WORLD_ENGINE_STUDIO_HTTPS_ORIGIN_V1'
TTL = 120


def _fail(code, status=400):
    raise SetupError(code, '초기 설정 정보와 HTTPS 주소를 확인해 주세요.', status)


class SetupSessions(security.OwnerSessions):
    cookie_name = '__Host-world_studio_setup'


def canonical_origin(value):
    """Validate one explicit external HTTPS origin, without DNS or HTTP calls."""
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        _fail('STUDIO_HTTPS_ORIGIN_REQUIRED')
    try:
        parsed = urlsplit(value)
        normalized = security._origin(value)
        if (parsed.scheme != 'https' or parsed.path or parsed.query or parsed.fragment
                or parsed.username is not None or parsed.password is not None
                or normalized != value or not parsed.hostname):
            raise ValueError()
        hostname = parsed.hostname
        if hostname in {'localhost', 'localhost.localdomain'} or hostname.endswith(('.localhost', '.local', '.internal')):
            raise ValueError()
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            if '.' not in hostname:
                raise ValueError()
        else:
            if not address.is_global:
                raise ValueError()
        return normalized
    except (TypeError, ValueError):
        _fail('STUDIO_HTTPS_ORIGIN_REQUIRED')


def _private_file(path, *, optional=False, maximum=65536):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        if optional:
            return None
        _fail('STUDIO_OWNER_CONFIGURATION_REQUIRED')
    value = path.lstat()
    if (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
            or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o600
            or not 1 <= value.st_size <= maximum):
        _fail('STUDIO_PRIVATE_FILE_REQUIRED')
    return path


def _read_json(path, *, optional=False):
    checked = _private_file(path, optional=optional)
    if checked is None:
        return None
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        return json.loads(checked.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (OSError, UnicodeError, ValueError, RecursionError):
        _fail('STUDIO_PRIVATE_CONFIGURATION_INVALID')


def _rotate_sessions(sessions):
    with sessions.lock:
        sessions.record['sessions'] = {}
        sessions.record['signing_key'] = secrets.token_hex(32)
        sessions.key = bytes.fromhex(sessions.record['signing_key'])
        security.private_json(sessions.path, sessions.record)


class SetupCore:
    def __init__(self, state_root, owner_file, port=8080, clock=time.time):
        root = Path(state_root)
        if (not root.is_absolute() or '..' in root.parts
                or root == Path('/world-storage') or root.is_relative_to('/world-storage')):
            _fail('STUDIO_PRIVATE_LOCAL_STATE_REQUIRED')
        cursor = Path(root.anchor)
        for part in root.parts[1:]:
            cursor /= part
            if cursor.is_symlink():
                _fail('STUDIO_PRIVATE_PATH_SYMLINK_FORBIDDEN')
        if not root.exists():
            root.mkdir(mode=0o700)
        info = root.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            _fail('STUDIO_PRIVATE_DIRECTORY_REQUIRED')
        self.root = root
        self.owner_file = Path(owner_file)
        if self.owner_file.parent != root:
            _fail('STUDIO_OWNER_PRIVATE_STATE_REQUIRED')
        _private_file(self.owner_file, maximum=4096)
        if type(port) is not int or not 1024 <= port <= 65535 or port == 8000:
            _fail('STUDIO_DISTINCT_PORT_REQUIRED')
        self.port, self.clock = port, clock
        self.lock = threading.RLock()
        self.rate = security.RateLimiter()
        self.origin_path = root / 'https-origin.json'
        self.auth_path = root / 'https-setup-auth.json'
        _private_file(self.auth_path, optional=True)
        self.sessions = SetupSessions(self.owner_file, self.auth_path, lifetime=600, clock=clock)
        self._production_sessions = None
        self._challenges, self._pending = {}, {}
        self._origin_record()

    def _origin_record(self):
        value = _read_json(self.origin_path, optional=True)
        if value is None:
            return None
        if (not isinstance(value, dict) or set(value) != {'schema', 'origin', 'version', 'registeredAt'}
                or value['schema'] != SCHEMA or type(value['version']) is not int or value['version'] < 1
                or not isinstance(value['registeredAt'], str)):
            _fail('STUDIO_ORIGIN_CONFIGURATION_INVALID')
        canonical_origin(value['origin'])
        return value

    @property
    def public_origin(self):
        with self.lock:
            value = self._origin_record()
            return value['origin'] if value is not None else None

    def bind_production_sessions(self, sessions):
        """Bind the live frozen app so origin changes revoke its in-memory keys."""
        if not isinstance(sessions, security.OwnerSessions):
            _fail('STUDIO_SESSION_BINDING_INVALID')
        if Path(sessions.path) != self.root / 'studio-auth.json':
            _fail('STUDIO_SESSION_BINDING_INVALID')
        with self.lock:
            self._production_sessions = sessions

    def _clean(self):
        now = self.clock()
        self._challenges = {key: value for key, value in self._challenges.items() if value['expires'] > now}
        self._pending = {key: value for key, value in self._pending.items() if value['expires'] > now}

    def challenge(self):
        """Return a private browser cookie and its same-origin one-use nonce."""
        with self.lock:
            self._clean()
            if len(self._challenges) >= 128:
                _fail('STUDIO_SETUP_BUSY', 429)
            cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            key = hashlib.sha256(cookie.encode('ascii')).hexdigest()
            self._challenges[key] = {'csrf': csrf, 'expires': self.clock() + TTL}
            return cookie, csrf

    def _check_challenge(self, cookie, csrf):
        if not isinstance(cookie, str) or not 32 <= len(cookie) <= 128 or not cookie.isascii():
            _fail('STUDIO_SETUP_CHALLENGE_REQUIRED', 403)
        key = hashlib.sha256(cookie.encode('ascii')).hexdigest()
        self._clean()
        challenge = self._challenges.get(key)
        if (challenge is None or not isinstance(csrf, str) or not csrf.isascii()
                or not hmac.compare_digest(challenge['csrf'], csrf)):
            _fail('STUDIO_SETUP_CHALLENGE_REQUIRED', 403)
        # Valid challenge is consumed even for a subsequent bad password.
        del self._challenges[key]

    def _request(self, headers, peer_ip, request_origin):
        if security.RequestPolicy._single_header(headers, 'Sec-Fetch-Site') != 'same-origin':
            _fail('STUDIO_SETUP_SAME_ORIGIN_REQUIRED', 403)
        values = headers.get_all('Content-Type', []) if hasattr(headers, 'get_all') else ([headers['Content-Type']] if 'Content-Type' in headers else [])
        if len(values) != 1 or values[0].lower().strip() not in {'application/json', 'application/json; charset=utf-8'}:
            _fail('STUDIO_SETUP_JSON_REQUIRED', 415)
        # This policy is constructed only after owner authentication. The origin
        # comes from explicit owner input or the existing private configuration.
        policy = security.RequestPolicy([request_origin], local_port=self.port, environ={})
        effective = policy.check_request(headers, method='POST', peer_ip=peer_ip)
        if effective != request_origin:
            _fail('STUDIO_ORIGIN_MISMATCH', 403)

    def begin(self, headers, peer_ip, password, candidate_origin, cookie, csrf):
        candidate = canonical_origin(candidate_origin)
        with self.lock:
            if not self.rate.allow(('setup-login', str(peer_ip)[:128]), count=5):
                _fail('LOGIN_RATE_LIMIT', 429)
            self._check_challenge(cookie, csrf)
            token = self.sessions.login(password)
            if not token:
                _fail('LOGIN_FAILED', 401)
            try:
                current = self.public_origin
                request_origin = current or candidate
                self._request(headers, peer_ip, request_origin)
                claim = self.sessions.claims(token)
                commit_csrf = secrets.token_urlsafe(32)
                self._pending[claim['sid']] = {'origin': candidate, 'requestOrigin': request_origin,
                                              'csrf': commit_csrf, 'expires': self.clock() + TTL}
                return {'token': token, 'csrf': commit_csrf, 'origin': candidate}
            except BaseException:
                self.sessions.logout(token)
                raise

    def _revoke_all(self):
        # Revoke before writing an origin: interruption can log an owner out,
        # but can never publish a new origin with still-valid old credentials.
        _rotate_sessions(self.sessions)
        production_path = self.root / 'studio-auth.json'
        if self._production_sessions is not None:
            _rotate_sessions(self._production_sessions)
        elif _private_file(production_path, optional=True) is not None:
            production = _read_json(production_path)
            if not isinstance(production, dict) or not {'salt', 'digest', 'signing_key', 'sessions'} <= production.keys():
                _fail('STUDIO_PRIVATE_CONFIGURATION_INVALID')
            production['sessions'], production['signing_key'] = {}, secrets.token_hex(32)
            security.private_json(production_path, production)
        self._pending.clear()
        self._challenges.clear()

    def _persist(self, origin):
        previous = self._origin_record()
        record = {'schema': SCHEMA, 'origin': origin, 'version': 1 if previous is None else previous['version'] + 1,
                  'registeredAt': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()}
        _private_file(self.origin_path, optional=True)
        self._revoke_all()
        security.private_json(self.origin_path, record)
        # Fsync the parent directory as well as the file for restart durability.
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return {'origin': record['origin'], 'version': record['version'],
                'registered': True, 'reloginRequired': True, 'renderAllowed': False}

    def configure_from_environment(self, origin):
        if origin is None or origin == '':
            return None
        candidate = canonical_origin(origin)
        with self.lock:
            current = self._origin_record()
            if current is not None:
                if current['origin'] != candidate:
                    _fail('STUDIO_CONFIGURED_ORIGIN_CONFLICT')
                return {'origin': current['origin'], 'version': current['version'], 'registered': True}
            return self._persist(candidate)

    def commit(self, headers, peer_ip, token, csrf, origin, confirm):
        candidate = canonical_origin(origin)
        if confirm is not True:
            _fail('STUDIO_SETUP_EXPLICIT_CONFIRMATION_REQUIRED', 403)
        with self.lock:
            self._clean()
            claim = self.sessions.claims(token)
            if not claim:
                _fail('AUTH_REQUIRED', 401)
            pending = self._pending.get(claim['sid'])
            if (pending is None or not isinstance(csrf, str) or not csrf.isascii()
                    or not hmac.compare_digest(pending['csrf'], csrf)
                    or pending['origin'] != candidate):
                _fail('CSRF_REQUIRED', 403)
            if pending['requestOrigin'] != (self.public_origin or candidate):
                _fail('STUDIO_SETUP_ORIGIN_CHANGED', 409)
            self._request(headers, peer_ip, pending['requestOrigin'])
            return self._persist(candidate)
