"""Fixed-origin HTTPS policy for an HTTP hop behind a TLS edge.

X-Forwarded-Proto describes a proxy hop; it is never proof of the browser's
transport or a source of trusted origins. The frozen policy already accepts
an omitted XFP. This adapter permits the single value ``http`` only when Host
and every supplied XFH exactly match the independently configured HTTPS
authority. All original Host, Origin and duplicate-header checks still run.

This is a compatibility path, not an observation of gCube request headers.
Actual gCube upstream headers have not been observed by this implementation.
"""
from __future__ import annotations

from email.message import Message
import json
from urllib.parse import urlsplit

from parent import modules

security = modules().security
_diagnostic_rate = security.RateLimiter()
_HEADER_NAMES = ('Host', 'Origin', 'X-Forwarded-Host', 'X-Forwarded-Proto',
                 'Forwarded', 'Sec-Fetch-Site')
_ERROR_CODES = frozenset({'INVALID_HOST', 'INVALID_ORIGIN',
                          'INVALID_FORWARDED_HEADERS', 'STUDIO_ORIGIN_MISMATCH'})


def _values(headers, name):
    if hasattr(headers, 'get_all'):
        return headers.get_all(name, [])
    return [value for key, value in headers.items() if str(key).lower() == name.lower()]


def _copy(headers):
    result = Message()
    items = headers.raw_items() if hasattr(headers, 'raw_items') else headers.items()
    for key, value in items:
        result[key] = value
    return result


def _canonical_authority(value):
    try:
        return security._authority(value, 'https')
    except (ValueError, TypeError):
        return None


def request_diagnostics(headers, origin=None):
    """Return only bounded counts, closed classifications and match booleans.

    No raw header, URL, peer address, body, cookie or credential is returned.
    Callers may expose this narrow record without creating a header echo API.
    """
    values = {name: _values(headers, name) for name in _HEADER_NAMES}
    proto = values['X-Forwarded-Proto']
    proto_class = ('MULTIPLE' if len(proto) > 1 else 'NONE' if not proto else
                   'HTTP' if proto[0] == 'http' else 'HTTPS' if proto[0] == 'https' else 'INVALID')
    site = values['Sec-Fetch-Site']
    site_names = {'same-origin': 'SAME_ORIGIN', 'same-site': 'SAME_SITE',
                  'cross-site': 'CROSS_SITE', 'none': 'NAVIGATION'}
    site_class = ('MULTIPLE' if len(site) > 1 else 'NONE' if not site else
                  site_names.get(site[0], 'INVALID') if isinstance(site[0], str) else 'INVALID')
    expected = None
    try:
        if isinstance(origin, str) and security._origin(origin) == origin and origin.startswith('https://'):
            expected = urlsplit(origin).netloc
    except (ValueError, TypeError):
        pass
    host = values['Host']
    match = (expected is not None and len(host) == 1 and
             _canonical_authority(host[0]) == expected)
    return {'headerCounts': {name: min(len(value), 3) for name, value in values.items()},
            'protoClass': proto_class, 'hostMatchesKnownOrigin': match,
            'standardForwardedPresent': bool(values['Forwarded']),
            'secFetchSiteClass': site_class}


def _diagnose(event, headers, origin, code=None):
    if not _diagnostic_rate.allow('fixed-https-proxy', count=20, window=60):
        return
    record = {'event': event, **request_diagnostics(headers, origin)}
    if code is not None:
        record['errorCode'] = code if code in _ERROR_CODES else 'INVALID_FORWARDED_HEADERS'
    print(json.dumps(record, separators=(',', ':'), sort_keys=True), flush=True)


class FixedHTTPSProxyPolicy(security.RequestPolicy):
    """Retain one configured HTTPS authority; never learn one from a request."""
    def __init__(self, public_origins=(), *, local_port=8080, environ=None):
        configured = tuple(public_origins)
        if len(configured) != 1:
            raise security.SecurityError('INVALID_PUBLIC_ORIGIN', '공개 HTTPS 주소 하나가 필요합니다.')
        # Do not derive Codespaces or other origins implicitly in this adapter.
        super().__init__(configured, local_port=local_port, environ={} if environ is None else environ)
        if len(self.origins) != 1:
            raise security.SecurityError('INVALID_PUBLIC_ORIGIN', '공개 HTTPS 주소 하나가 필요합니다.')
        self.fixed_origin = next(iter(self.origins))
        if not self.fixed_origin.startswith('https://'):
            raise security.SecurityError('HTTPS_REQUIRED', '공개 주소에는 HTTPS가 필요합니다.')
        self.fixed_authority = urlsplit(self.fixed_origin).netloc

    def _checked(self, headers, *, method='GET', peer_ip=None):
        copied = _copy(headers)
        changed = False
        try:
            # Validate duplicate and ambiguous security headers before looking
            # at any value. No list splitting or first/last-hop guessing.
            host = self._single_header(copied, 'Host')
            forwarded_host = self._single_header(copied, 'X-Forwarded-Host')
            proto = self._single_header(copied, 'X-Forwarded-Proto')
            if (proto == 'http' and _canonical_authority(host) == self.fixed_authority
                    and (forwarded_host is None or
                         _canonical_authority(forwarded_host) == self.fixed_authority)):
                # Equivalent to an absent advisory hop header, which the frozen
                # policy already supports. Fixed Host and mutation Origin are
                # checked again by the complete unchanged policy below.
                del copied['X-Forwarded-Proto']
                changed = True
            effective = super().check_request(copied, method=method, peer_ip=peer_ip)
            if effective != self.fixed_origin:
                raise security.SecurityError('STUDIO_ORIGIN_MISMATCH', '같은 Studio 주소에서 요청해 주세요.', 403)
        except security.SecurityError as error:
            _diagnose('STUDIO_PROXY_ENVELOPE_REJECTED', headers, self.fixed_origin, error.code)
            raise
        if changed:
            _diagnose('STUDIO_PROXY_HTTP_HOP_COMPATIBILITY', headers, self.fixed_origin)
        return effective, copied

    def check_request(self, headers, *, method='GET', peer_ip=None):
        return self._checked(headers, method=method, peer_ip=peer_ip)[0]


def normalize_headers(headers, origin, local_port=8080, method='POST', peer_ip=None):
    """Return a validated copy for the unchanged authenticated setup policy."""
    policy = FixedHTTPSProxyPolicy([origin], local_port=local_port, environ={})
    return policy._checked(headers, method=method, peer_ip=peer_ip)[1]
