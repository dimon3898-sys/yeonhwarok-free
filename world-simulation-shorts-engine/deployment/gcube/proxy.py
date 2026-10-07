"""Strict gcube/Istio envelope parsing; forwarded addresses never authenticate.

Only a same-pod/loopback proxy may rewrite the public authority. Public Host
preservation still works without trusting a peer. XFF is syntax-checked and is
never used for owner authentication, origin binding, or rate-limit identity.
"""
from __future__ import annotations

from functools import lru_cache
import ipaddress
import re
import socket
from urllib.parse import urlsplit

from deployment.security import RequestPolicy, SecurityError, _authority

PROVIDER_HOST = re.compile(r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:service\.)?gcube\.ai")
RESERVED = {"www", "api", "console", "docs", "app", "auth", "accounts", "login", "status", "support", "service"}


def invalid_forwarding():
    raise SecurityError("INVALID_FORWARDED_HEADERS", "프록시 주소 헤더를 확인해 주세요.", 403)


def provider_origin(host):
    try:
        authority = _authority(host, "https")
        hostname = urlsplit("//" + authority).hostname
    except (ValueError, TypeError):
        raise SecurityError("INVALID_HOST", "허용되지 않은 주소입니다.", 400) from None
    match = PROVIDER_HOST.fullmatch(hostname or "")
    if not match or match[1] in RESERVED:
        raise SecurityError("INVALID_HOST", "허용되지 않은 주소입니다.", 400)
    return "https://" + authority


@lru_cache(maxsize=1)
def pod_addresses():
    """Exact local addresses, not a blanket trust of all private networks."""
    values = {"127.0.0.1", "::1"}
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None)[:64]:
            address = ipaddress.ip_address(item[4][0])
            if not address.is_unspecified and not address.is_multicast:
                values.add(str(address))
    except (OSError, ValueError):
        pass
    return frozenset(values)


def trusted_peer(peer_ip):
    try:
        address = ipaddress.ip_address(peer_ip)
        return address.is_loopback or str(address) in pod_addresses()
    except (ValueError, TypeError):
        return False


def list_header(headers, name):
    values = headers.get_all(name, []) if hasattr(headers, "get_all") else ([headers[name]] if name in headers else [])
    if not values:
        return None
    if len(values) > 8 or any(not isinstance(v, str) or not v.isascii() or
                             len(v) > 4096 or any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in v)
                             for v in values):
        invalid_forwarding()
    value = ",".join(values)
    if len(value) > 4096:
        invalid_forwarding()
    return value


def split_quoted(value, delimiter):
    parts, start, quoted, escaped = [], 0, False, False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
        elif character == "\\" and quoted:
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif character == delimiter and not quoted:
            parts.append(value[start:index].strip(" \t"))
            start = index + 1
    if quoted or escaped:
        invalid_forwarding()
    parts.append(value[start:].strip(" \t"))
    if any(not part for part in parts) or len(parts) > 32:
        invalid_forwarding()
    return parts


def forwarded_value(value):
    if value.startswith('"'):
        if not value.endswith('"') or len(value) < 2:
            invalid_forwarding()
        value = value[1:-1]
        # The required IP/authority/protocol fields have no escaped characters.
        if '"' in value or "\\" in value:
            invalid_forwarding()
    elif not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z:-]+", value):
        invalid_forwarding()
    return value


def port_number(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
        invalid_forwarding()
    return int(value)


def forwarded_ip(value, *, node=False):
    try:
        if not value or "%" in value:
            raise ValueError()
        if node and value.startswith("["):
            match = re.fullmatch(r"\[([^\]]+)\](?::([0-9]{1,5}))?", value)
            if not match:
                raise ValueError()
            value = match[1]
            if match[2] is not None:
                port_number(match[2])
        elif node and value.count(":") == 1:
            value, port = value.split(":")
            port_number(port)
        return str(ipaddress.ip_address(value))
    except (ValueError, TypeError):
        invalid_forwarding()


def internal_authority(host, port):
    """Recognize only this listener's loopback or exact pod address and port."""
    try:
        if not isinstance(host, str) or not host.isascii() or re.search(r"[\s,\\/?#@]", host):
            return False
        parsed = urlsplit("//" + host)
        if parsed.port != port or host.endswith(":") or parsed.path or parsed.username or parsed.password:
            return False
        return parsed.hostname in {"localhost", "0.0.0.0", *pod_addresses()}
    except (ValueError, TypeError):
        return False


def internal_probe_headers(headers, *, peer_ip, port):
    """A bounded sidecar HTTP probe may receive an internal service name.

    This permits only fixed read-only liveness/readiness, never the gateway
    envelope, origin binding, authentication or project APIs.
    """
    if not trusted_peer(peer_ip) or any(headers.get_all(name, []) for name in (
            "Forwarded", "X-Forwarded-Port", "X-Forwarded-For", "X-Envoy-External-Address")):
        return False
    proto = RequestPolicy._single_header(headers, "X-Forwarded-Proto")
    host = RequestPolicy._single_header(headers, "X-Forwarded-Host")
    return proto == "http" and bool(host) and (internal_authority(host, port) or
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?:" + str(port), host) is not None)


def parse_forwarding(headers, peer_ip):
    xf_host = RequestPolicy._single_header(headers, "X-Forwarded-Host")
    proto = RequestPolicy._single_header(headers, "X-Forwarded-Proto")
    raw_port = RequestPolicy._single_header(headers, "X-Forwarded-Port")
    if proto not in {None, "https", "http"}:
        invalid_forwarding()
    port = port_number(raw_port) if raw_port is not None else None
    raw_xff = list_header(headers, "X-Forwarded-For")
    xff = [forwarded_ip(item) for item in split_quoted(raw_xff, ",")] if raw_xff is not None else []
    raw = list_header(headers, "Forwarded")
    forwarded = []
    if raw is not None:
        for item in split_quoted(raw, ","):
            entry = {}
            for parameter in split_quoted(item, ";"):
                key, separator, value = parameter.partition("=")
                key, value = key.strip(" \t").lower(), value.strip(" \t")
                if not separator or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", key) or key in entry:
                    invalid_forwarding()
                entry[key] = forwarded_value(value)
            for key in ("for", "by"):
                if key in entry:
                    entry[key] = forwarded_ip(entry[key], node=True)
            if entry.get("proto") not in {None, "https", "http"}:
                invalid_forwarding()
            forwarded.append(entry)
    envoy = RequestPolicy._single_header(headers, "X-Envoy-External-Address")
    if envoy is not None:
        forwarded_ip(envoy)
    if (xff or forwarded or envoy is not None) and not trusted_peer(peer_ip):
        invalid_forwarding()
    if proto == "http" and not gcube_internal_http_profile(
            RequestPolicy._single_header(headers, "Host"), peer_ip, xff, envoy):
        invalid_forwarding()
    if forwarded:
        if forwarded[0].get("proto") not in {None, "https"}:
            invalid_forwarding()
        if xff and forwarded[0].get("for") and forwarded[0]["for"] != xff[0]:
            invalid_forwarding()
        forwarded_proto = forwarded[0].get("proto")
        if proto is not None and forwarded_proto is not None and proto != forwarded_proto:
            invalid_forwarding()
        proto = proto or forwarded_proto
    return xf_host, proto, port, xff, forwarded, envoy is not None


def gcube_internal_http_profile(host, peer_ip, xff, envoy):
    """Only the captured service-host/sidecar shape may carry upstream HTTP.

    This describes an internal hop, never attests browser TLS. No new peer
    networks are trusted, and XFF/Envoy values never authenticate an owner.
    All addresses have already passed the strict syntax parser above.
    """
    if not trusted_peer(peer_ip):
        return False
    try:
        service = urlsplit(provider_origin(host))
        if not service.hostname.endswith('.service.gcube.ai') or len(xff) != 2 or envoy is None:
            return False
        first, second, external = (ipaddress.ip_address(value) for value in (*xff, envoy))
        return (all(value.version == 4 for value in (first, second, external))
                and first.is_global and second.is_private and external.is_private
                and not any(value.is_unspecified or value.is_multicast for value in (first, second, external)))
    except (SecurityError, ValueError, TypeError):
        return False


def request_envelope(headers, *, origin=None, port=8000, peer_ip=None):
    host = RequestPolicy._single_header(headers, "Host")
    xf_host, proto, xf_port, xff, forwarded, envoy = parse_forwarding(headers, peer_ip)
    candidates = [value for value in (xf_host, forwarded[0].get("host") if forwarded else None) if value is not None]
    try:
        host_origin = provider_origin(host)
    except SecurityError:
        if not trusted_peer(peer_ip) or not internal_authority(host, port) or not candidates or proto != "https":
            raise
        host_origin = None
    if candidates:
        candidate = provider_origin(candidates[0])
        if any(provider_origin(other) != candidate for other in candidates[1:]):
            invalid_forwarding()
        if host_origin and candidate != host_origin:
            actual, supplied = urlsplit(host_origin), urlsplit(candidate)
            # Ports 8000/default may be the internal listener, never a different
            # assigned external port or another workload's public hostname.
            if (not trusted_peer(peer_ip) or proto != "https" or actual.hostname != supplied.hostname
                    or actual.port not in {None, port}):
                invalid_forwarding()
    else:
        candidate = host_origin
    parsed = urlsplit(candidate)
    if xf_port is not None:
        if parsed.port not in {None, xf_port}:
            if parsed.port != port or not trusted_peer(peer_ip) or proto != "https" or candidates:
                invalid_forwarding()
        if parsed.port is None or parsed.port == port:
            if xf_port != (parsed.port or 443) and (not trusted_peer(peer_ip) or proto != "https"):
                invalid_forwarding()
            candidate = provider_origin(parsed.hostname + (":" + str(xf_port) if xf_port != 443 else ""))
    for entry in forwarded[1:]:
        value = entry.get("host")
        if value is not None and not internal_authority(value, port):
            other = urlsplit(provider_origin(value))
            if other.hostname != urlsplit(candidate).hostname or other.port not in {None, port, urlsplit(candidate).port}:
                invalid_forwarding()
    if origin is not None and candidate != origin:
        raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
    return candidate, {"normalized_host": host_origin.removeprefix("https://") if host_origin else host,
                       "forwarded_host": urlsplit(provider_origin(xf_host)).netloc if xf_host else None,
                       "forwarded_proto": proto, "forwarded_port": xf_port,
                       "xff_entry_count": len(xff), "envoy_external_address_present": envoy,
                       "forwarded_proto_is_browser_tls_proof": False,
                       "effective_origin": candidate}


def safe_proxy_summary(headers, *, peer_ip=None):
    """Read-only blocked-startup projection. Never reflects invalid raw input."""
    try:
        candidate, summary = request_envelope(headers, peer_ip=peer_ip)
        origin = RequestPolicy._single_header(headers, "Origin")
        if origin is not None and origin != candidate:
            raise SecurityError("INVALID_ORIGIN", "같은 사이트의 요청만 허용됩니다.", 403)
        return {"status": "PASS", **summary}
    except SecurityError as error:
        return {"status": "FAIL", "error_code": error.code}
