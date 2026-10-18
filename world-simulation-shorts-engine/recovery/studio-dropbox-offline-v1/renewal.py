"""Bounded offline OAuth refresh for the unchanged Dropbox checkpoint store.

Only the access token lives in memory. Credential files remain under the same
UID1000/0600 policy as the frozen checkpoint implementation. Neither an OAuth
response nor a request body is included in a public exception or representation.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = 'https://api.dropboxapi.com/oauth2/token'
FILE_ROUTES = frozenset({
    'https://content.dropboxapi.com/2/files/download',
    'https://content.dropboxapi.com/2/files/upload',
    'https://api.dropboxapi.com/2/files/create_folder_v2',
    'https://api.dropboxapi.com/2/files/list_folder',
    'https://api.dropboxapi.com/2/files/list_folder/continue',
})
REQUIRED_SCOPES = frozenset({
    'files.content.read', 'files.content.write', 'files.metadata.read',
})
MAX_RESPONSE = 64 * 1024
MAX_EXPIRES_IN = 31 * 24 * 60 * 60


def _stores():
    # The additive runtime supplies the frozen, hash-verified module. In
    # particular, do not define a second weaker secret-file implementation.
    from offline_frozen import modules
    return modules().stores


def _error(code):
    return _stores().BackupError(code)


def _visible(value, minimum, maximum):
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and all(33 <= ord(character) <= 126 for character in value))


def _credential(path, *, minimum, maximum, identifier=False):
    raw = _stores().read_private_file(path, limit=maximum + 2)
    try:
        value = raw.decode('ascii').strip()
    except UnicodeError:
        raise _error('DURABILITY_OAUTH_CREDENTIAL_INVALID') from None
    if (not _visible(value, minimum, maximum)
            or (identifier and re.fullmatch(r'[A-Za-z0-9_-]+', value) is None)):
        raise _error('DURABILITY_OAUTH_CREDENTIAL_INVALID')
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise _error('DURABILITY_OAUTH_REDIRECT_REJECTED')


def _safe_opener(opener):
    """Reject urllib's permissive default redirect handler when injected.

    Existing store openers have a rejecting subclass. Fake transports used by
    the CPU suite do not have handlers. Transport injection is trusted local
    application code; user input cannot select the transport or token URL.
    """
    for handler in getattr(opener, 'handlers', ()):
        if (isinstance(handler, urllib.request.HTTPRedirectHandler)
                and type(handler).redirect_request is urllib.request.HTTPRedirectHandler.redirect_request):
            raise _error('DURABILITY_OAUTH_REDIRECT_POLICY_REQUIRED')
    return opener


def token_request(form, *, opener=None):
    """Shared bounded transport for offline enrollment and later refresh.

    A caller holding the private credentials can exchange a user-approved
    authorization code once, or refresh its token. The caller must validate
    grant-specific fields in the returned dictionary before using them. This
    function never emits the response, retries, or accepts a different URL.
    """
    if not isinstance(form, dict):
        raise _error('DURABILITY_OAUTH_REQUEST_INVALID')
    grant = form.get('grant_type')
    secret_field = ({'refresh_token': 'refresh_token',
                     'authorization_code': 'code'}.get(grant)
                    if isinstance(grant, str) else None)
    if (secret_field is None or set(form) != {'grant_type', 'client_id', 'client_secret', secret_field}
            or not _visible(form.get('client_id'), 8, 256)
            or re.fullmatch(r'[A-Za-z0-9_-]+', form['client_id']) is None
            or not _visible(form.get('client_secret'), 8, 256)
            or not _visible(form.get(secret_field), 8 if secret_field == 'code' else 16, 4096)):
        raise _error('DURABILITY_OAUTH_REQUEST_INVALID')
    opener = _safe_opener(opener if opener is not None else
                          urllib.request.build_opener(_NoRedirect()))
    body = urllib.parse.urlencode(form).encode('ascii')
    request = urllib.request.Request(TOKEN_URL, data=body, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    })
    try:
        with opener.open(request, timeout=30) as response:
            if response.geturl() != TOKEN_URL:
                raise _error('DURABILITY_OAUTH_REDIRECT_REJECTED')
            if response.status != 200:
                raise _error('DURABILITY_OAUTH_HTTP_FAILED')
            payload = response.read(MAX_RESPONSE + 1)
            if len(payload) > MAX_RESPONSE:
                raise _error('DURABILITY_OAUTH_RESPONSE_TOO_LARGE')
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        if status in {400, 401}:
            raise _error('DURABILITY_OAUTH_REFRESH_REJECTED') from None
        if status == 429:
            raise _error('DURABILITY_OAUTH_RATE_LIMITED') from None
        raise _error('DURABILITY_OAUTH_HTTP_FAILED') from None
    except _stores().BackupError:
        raise
    except Exception:
        raise _error('DURABILITY_OAUTH_CONNECTION_FAILED') from None
    try:
        result = json.loads(payload, object_pairs_hook=_unique_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError, TypeError, UnicodeError):
        raise _error('DURABILITY_OAUTH_RESPONSE_INVALID') from None
    if not isinstance(result, dict):
        raise _error('DURABILITY_OAUTH_RESPONSE_INVALID')
    return result


class TokenProvider:
    """One in-memory token per process, with one serialized refresh at a time.

    A refresh failure clears the cached token and propagates a safe error.
    There are no retries, fallback credentials, persistent access-token cache,
    token endpoint overrides, or background threads.
    """

    def __init__(self, app_key_file, app_secret_file, refresh_token_file, *,
                 opener=None, clock=time.monotonic):
        self._app_key = _credential(app_key_file, minimum=8, maximum=256, identifier=True)
        self._app_secret = _credential(app_secret_file, minimum=8, maximum=256)
        self._refresh_token = _credential(refresh_token_file, minimum=16, maximum=4096)
        self._opener = _safe_opener(opener if opener is not None else
                                    urllib.request.build_opener(_NoRedirect()))
        self._clock = clock
        self._lock = threading.RLock()
        self._access_token = None
        self._refresh_at = 0.0

    def __repr__(self):
        return '<TokenProvider credentials=REDACTED>'

    def _now(self):
        try:
            value = self._clock()
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('invalid clock')
            return float(value)
        except Exception:
            raise _error('DURABILITY_OAUTH_CLOCK_INVALID') from None

    def access_token(self, force=False, rejected_token=None):
        """Return a current token or refresh; concurrent 401s share one refresh.

        rejected_token identifies the already rejected token. If another
        thread has replaced it, the replacement is reused rather than causing
        a second refresh. Callers never include either token in diagnostics.
        """
        if type(force) is not bool or (rejected_token is not None
                                      and not _visible(rejected_token, 16, 4096)):
            raise _error('DURABILITY_OAUTH_REQUEST_INVALID')
        with self._lock:
            now = self._now()
            fresh = self._access_token is not None and now < self._refresh_at
            if fresh and (not force or (rejected_token is not None
                                       and rejected_token != self._access_token)):
                return self._access_token
            self._access_token = None
            self._refresh_at = 0.0
            token, ttl = self._refresh()
            # Include refresh latency in the lifetime. A token that aged past
            # its usable lifetime during a blocked request is never returned.
            after = self._now()
            lead = min(60.0, ttl / 10.0)
            refresh_at = now + ttl - lead
            if after >= refresh_at:
                raise _error('DURABILITY_OAUTH_TOKEN_LIFETIME_EXHAUSTED')
            self._access_token, self._refresh_at = token, refresh_at
            return token

    def _refresh(self):
        result = token_request({
            'grant_type': 'refresh_token',
            'refresh_token': self._refresh_token,
            'client_id': self._app_key,
            'client_secret': self._app_secret,
        }, opener=self._opener)
        token, ttl = result.get('access_token'), result.get('expires_in')
        if (not _visible(token, 16, 4096)
                or not isinstance(result.get('token_type'), str)
                or result['token_type'].lower() != 'bearer'
                or type(ttl) is not int or not 1 <= ttl <= MAX_EXPIRES_IN):
            raise _error('DURABILITY_OAUTH_RESPONSE_INVALID')
        if 'scope' in result:
            scopes = result['scope']
            if (not isinstance(scopes, str) or len(scopes) > 8192
                    or not REQUIRED_SCOPES.issubset(scopes.split())):
                raise _error('DURABILITY_OAUTH_SCOPE_MISSING')
        return token, ttl


class OfflineOpener:
    """Inject current authorization only into the frozen file API routes.

    The only replay is a single explicit HTTP 401 (rejected authorization).
    An upload connection failure or any 403/429/5xx is not replayed. Existing
    immutable-object handling remains responsible for interrupted uploads.
    """

    def __init__(self, provider, underlying):
        self._provider, self._underlying = provider, _safe_opener(underlying)

    def __repr__(self):
        return '<OfflineOpener authorization=REDACTED>'

    @staticmethod
    def _request(request, token):
        if (not isinstance(request, urllib.request.Request)
                or request.full_url not in FILE_ROUTES or request.get_method() != 'POST'
                or (request.data is not None and not isinstance(request.data, bytes))):
            raise _error('DURABILITY_OAUTH_FILE_ROUTE_REJECTED')
        headers = {}
        for key, value in request.header_items():
            if key.lower() == 'authorization':
                continue
            if key.lower() == 'host' and value.lower() != urllib.parse.urlsplit(request.full_url).netloc:
                raise _error('DURABILITY_OAUTH_FILE_ROUTE_REJECTED')
            headers[key] = value
        headers['Authorization'] = 'Bearer ' + token
        return urllib.request.Request(request.full_url, data=request.data,
                                      headers=headers, method='POST')

    def open(self, request, timeout=30):
        # Validate the route before accessing any credential or sending OAuth.
        self._request(request, 'ROUTE_VALIDATION_ONLY')
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 0 < timeout <= 30):
            raise _error('DURABILITY_OAUTH_TIMEOUT_INVALID')
        token = self._provider.access_token()
        for attempt in range(2):
            authorized = self._request(request, token)
            try:
                response = self._underlying.open(authorized, timeout=timeout)
            except urllib.error.HTTPError as error:
                if error.code != 401 or attempt:
                    raise
                error.close()
                token = self._provider.access_token(force=True, rejected_token=token)
                continue
            if response.geturl() != request.full_url:
                response.close()
                raise _error('DURABILITY_OAUTH_REDIRECT_REJECTED')
            return response
        raise _error('DURABILITY_OAUTH_REFRESH_REJECTED')
