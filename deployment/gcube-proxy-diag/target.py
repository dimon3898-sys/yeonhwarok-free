"""Classify untrusted targets without exporting URLs, paths or query values.

Classification is not admission: an absolute authority must also match the
effective origin from the unchanged, peer-aware proxy/security validator.
No target is fetched, decoded into a filename, or used to select an origin.
"""
from urllib.parse import urlsplit
from deployment.security import _authority

READ_ONLY_QUERY_PATHS = frozenset(('/', '/auth/login', '/diag.json'))


def classify(raw):
    absolute = bool(isinstance(raw, str) and not raw.startswith('/') and ':' in raw.split('/', 1)[0])
    summary = {'length': len(raw) if isinstance(raw, str) else None,
               'form': 'ABSOLUTE_FORM' if absolute else 'ORIGIN_FORM' if
                       isinstance(raw, str) and raw.startswith('/') and not raw.startswith('//') else 'OTHER',
               'scheme_present': absolute, 'authority_present': bool(isinstance(raw, str) and
                       (raw.startswith('//') or absolute and '://' in raw)),
               'query_present': isinstance(raw, str) and '?' in raw.split('#', 1)[0],
               'fragment_present': isinstance(raw, str) and '#' in raw}
    if not isinstance(raw, str): return None, summary, 'TARGET_PARSE_FAILED'
    if len(raw) > 4096: return None, summary, 'TARGET_TOO_LONG'
    # urlsplit strips some controls. Test the raw bytes-as-text first.
    if any(ord(c) <= 32 or ord(c) == 127 for c in raw):
        return None, summary, 'TARGET_CONTROL_OR_WHITESPACE'
    if not raw.isascii() or '\\' in raw: return None, summary, 'TARGET_INVALID_CHARACTER'
    if summary['fragment_present']: return None, summary, 'TARGET_HAS_FRAGMENT'
    try:
        parsed = urlsplit(raw)
        summary['scheme_present'], summary['authority_present'] = bool(parsed.scheme), bool(parsed.netloc)
        if summary['form'] == 'ORIGIN_FORM':
            if parsed.scheme or parsed.netloc: return None, summary, 'TARGET_FORM_INVALID'
        elif summary['form'] == 'ABSOLUTE_FORM':
            if parsed.scheme not in {'http', 'https'}: return None, summary, 'TARGET_SCHEME_NOT_ALLOWED'
            if not parsed.netloc or parsed.username is not None or parsed.password is not None:
                return None, summary, 'TARGET_AUTHORITY_OR_USERINFO_INVALID'
            # Strict syntax, DNS/IP normalization and port bounds; no network IO.
            _authority(parsed.netloc, parsed.scheme)
        else: return None, summary, 'TARGET_FORM_INVALID'
    except Exception:
        # A parser error must produce structural diagnosis, never its value.
        return None, summary, 'TARGET_PARSE_FAILED'
    return parsed, summary, None


def routing_rule(parsed, summary, *, method):
    if summary['query_present'] and (method != 'GET' or parsed.path not in READ_ONLY_QUERY_PATHS):
        return 'TARGET_HAS_QUERY'
    return None


def admit(parsed, summary, *, method, effective):
    rule = routing_rule(parsed, summary, method=method)
    if rule: return rule
    if summary['form'] == 'ABSOLUTE_FORM':
        authority = _authority(parsed.netloc, parsed.scheme)
        if effective is None: return 'TARGET_PROXY_CONTEXT_UNVERIFIED'
        bound = urlsplit(effective)
        if parsed.scheme != bound.scheme: return 'TARGET_SCHEME_ORIGIN_MISMATCH'
        if authority != bound.netloc: return 'TARGET_AUTHORITY_MISMATCH'
    return None
