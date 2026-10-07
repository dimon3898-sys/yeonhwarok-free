"""Observe the unchanged v005 validator; never admit or repair a request.

Only bounded, typed header structure leaves this module. IPs and workload
labels have keyed, per-process comparison IDs; arbitrary strings are omitted.
No frame-local header value, exception text, query, body or auth header is logged.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit

from deployment.gcube import proxy
from deployment.security import SecurityError

EXPECTED_PROXY_SHA256 = "b5e66d4ceee91c25eab4daa8a24339a67c89592ae25ba2dacdc68c6bdb2ede07"
FIELDS = ("Host", "Origin", "X-Forwarded-Host", "X-Forwarded-Proto",
          "X-Forwarded-Port", "X-Forwarded-For", "Forwarded", "X-Envoy-External-Address")
KNOWN_RELATED = frozenset(("x-envoy-external-address", "x-envoy-original-path",
    "x-envoy-attempt-count", "x-envoy-decorator-operation", "x-envoy-downstream-service-cluster",
    "x-envoy-downstream-service-node", "x-envoy-expected-rq-timeout-ms", "x-envoy-internal",
    "x-forwarded-client-cert", "x-request-id", "x-b3-traceid", "x-b3-spanid", "x-b3-sampled"))
RULES = {
    "list_header": ("CHAIN_FIELD_BOUNDS_OR_CONTROL", "CHAIN_TOTAL_SIZE_LIMIT"),
    "split_quoted": ("CHAIN_QUOTE_SYNTAX", "CHAIN_EMPTY_OR_TOO_MANY_ENTRIES"),
    "forwarded_value": ("FORWARDED_UNCLOSED_QUOTED_VALUE", "FORWARDED_ESCAPED_VALUE",
                        "FORWARDED_VALUE_TOKEN_SYNTAX"),
    "port_number": ("PORT_FORMAT_OR_RANGE",),
    "forwarded_ip": ("IP_NODE_FORMAT",),
    "parse_forwarding": ("X_FORWARDED_PROTO_NOT_HTTPS", "FORWARDED_PARAMETER_SYNTAX_OR_DUPLICATE",
        "FORWARDED_PROTO_VALUE", "FORWARDED_PEER_NOT_TRUSTED", "FORWARDED_FIRST_PROTO_NOT_HTTPS",
        "FORWARDED_FOR_XFF_DISAGREE", "FORWARDED_PROTO_HEADERS_DISAGREE"),
    "request_envelope": ("FORWARDED_HOST_HEADERS_DISAGREE", "HOST_FORWARDED_AUTHORITY_DISAGREE",
        "X_FORWARDED_PORT_AUTHORITY_DISAGREE", "PORT_RECONSTRUCTION_PEER_OR_PROTO",
        "FORWARDED_LATER_HOST_DISAGREE"),
}


def rule_catalog():
    source = Path(proxy.__file__).read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED_PROXY_SHA256:
        raise RuntimeError("VALIDATOR_SOURCE_CHANGED")
    result = {}
    for function in ast.parse(source).body:
        if not isinstance(function, ast.FunctionDef) or function.name not in RULES:
            continue
        calls = sorted((node for node in ast.walk(function) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "invalid_forwarding"),
                       key=lambda node: node.lineno)
        if len(calls) != len(RULES[function.name]):
            raise RuntimeError("VALIDATOR_RULE_MAP_CHANGED")
        for call, rule in zip(calls, RULES[function.name]):
            result[call.lineno] = {"FAILED_VALIDATION_RULE": rule, "function": function.name,
                                  "source": "deployment/gcube/proxy.py", "line": call.lineno}
    return result


def failure_rule(error, catalog):
    frames = []
    tb = error.__traceback__
    while tb is not None:
        frames.append((tb.tb_frame, tb.tb_lineno))
        tb = tb.tb_next
    for frame, line in reversed(frames):
        filename = Path(frame.f_code.co_filename)
        if filename == Path(proxy.__file__) and line in catalog:
            result = dict(catalog[line])
            if result["FAILED_VALIDATION_RULE"] == "IP_NODE_FORMAT":
                if frame.f_locals.get("node") is True:
                    result["header_family"] = "FORWARDED_NODE"
                else:
                    # Python 3.12 inlines list comprehensions; the pinned source
                    # call site distinguishes XFF from Envoy on both versions.
                    result["header_family"] = "XFF" if any(f.f_code.co_name == "<listcomp>" or
                        f.f_code.co_name == "parse_forwarding" and n == 167 for f, n in frames) else "X_ENVOY_EXTERNAL_ADDRESS"
            return result
        if filename.name == "security.py" and frame.f_code.co_name == "_single_header":
            name = frame.f_locals.get("name")
            if name not in FIELDS:
                name = "OTHER"
            values = frame.f_locals.get("values")
            duplicate = isinstance(values, (list, tuple)) and len(values) > 1
            return {"FAILED_VALIDATION_RULE": "SINGLE_HEADER_DUPLICATE" if duplicate else "SINGLE_HEADER_WHITESPACE_OR_COMMA",
                    "header": name, "function": "RequestPolicy._single_header",
                    "source": "deployment/security.py", "line": line}
    code = error.code if isinstance(error, SecurityError) else "DIAGNOSTIC_INTERNAL_FAILURE"
    return {"FAILED_VALIDATION_RULE": {"INVALID_HOST": "PUBLIC_OR_INTERNAL_HOST_NOT_ALLOWED",
                                       "INVALID_ORIGIN": "ORIGIN_EFFECTIVE_OR_BOUND_AUTHORITY_MISMATCH"}.get(code, "UNMAPPED_SECURITY_RULE")}


class Observer:
    def __init__(self, key):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("DIAGNOSTIC_KEY_REQUIRED")
        self.key, self.catalog = key, rule_catalog()

    def tag(self, value):
        return hmac.new(self.key, value.encode(), hashlib.sha256).hexdigest()[:12]

    def authority(self, raw):
        # Report internal listener *shape*, never arbitrary upstream DNS names.
        if proxy.internal_authority(raw, 8000):
            return {"kind": "INTERNAL_LISTENER", "port": 8000,
                    "authority_id": self.tag(raw.lower()), "redacted": True}
        try:
            origin = proxy.provider_origin(raw)
            parsed = urlsplit(origin)
        except (SecurityError, ValueError, TypeError):
            return {"kind": "NOT_PUBLIC_GCUBE_AUTHORITY", "value": "<MASKED>"}
        return {"kind": "GCUBE_AUTHORITY", "domain_pattern": "<workload>.service.gcube.ai" if
                parsed.hostname.endswith(".service.gcube.ai") else "<workload>.gcube.ai",
                "port": parsed.port or 443, "authority_id": self.tag(origin),
                "legacy_e_hostname": parsed.hostname == "e.gcube.ai"}

    def ip_structure(self, raw):
        raw = raw.strip(" \t")
        quoted = len(raw) >= 2 and raw.startswith('"') and raw.endswith('"')
        value = raw[1:-1] if quoted else raw
        form, port = "IP", None
        bracket = re.fullmatch(r"\[([^\]]+)\](?::([0-9]{1,5}))?", value)
        if bracket:
            value, port, form = bracket[1], bracket[2], "BRACKETED"
        elif value.count(":") == 1 and "." in value:
            value, port = value.split(":")
            form = "IPV4_WITH_PORT"
        try:
            if "%" in value or "\\" in value:
                raise ValueError()
            address = ipaddress.ip_address(value)
            mapped = isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None
            normalized = address.ipv4_mapped if mapped else address
            kind = "IPV4_MAPPED_IPV6" if mapped else "IPV4" if address.version == 4 else "IPV6"
            return {"kind": kind, "form": form, "quoted": quoted, "has_port": port is not None,
                    "port_valid": bool(port and port.isdecimal() and 1 <= int(port) <= 65535) if port is not None else None,
                    "address_id": self.tag(str(normalized)), "loopback": address.is_loopback,
                    "private": address.is_private, "redacted": True}
        except (ValueError, TypeError):
            return {"kind": "INVALID_OR_NON_IP", "quoted": quoted, "redacted": True}

    def chain(self, value):
        if not isinstance(value, str) or len(value) > 4096:
            return {"structure": "<BOUNDED_INVALID>", "entry_count": None}
        try:
            parts = proxy.split_quoted(value, ",")
            syntax = True
        except SecurityError:
            parts, syntax = value.split(","), False
        entries = [self.ip_structure(part) if part.strip() else {"kind": "EMPTY", "redacted": True}
                   for part in parts[:32]]
        return {"structure": ", ".join('<' + entry["kind"] +
                (":PORT" if entry.get("has_port") else "") + '>' for entry in entries),
                "entry_count": len(parts), "quote_chain_syntax_valid": syntax,
                "entries": entries, "truncated": len(parts) > 32}

    def forwarded(self, value):
        if not isinstance(value, str) or len(value) > 4096:
            return {"present": True, "structure": "<BOUNDED_INVALID>"}
        try:
            elements = proxy.split_quoted(value, ",")
        except SecurityError:
            return {"present": True, "structure": "<MALFORMED_QUOTE_OR_CHAIN>", "comma_count": value.count(",")}
        result = []
        for element in elements[:32]:
            entry = {"parameters": [], "duplicate_parameter": False}
            try:
                parameters = proxy.split_quoted(element, ";")
            except SecurityError:
                entry["syntax"] = "INVALID"
                result.append(entry)
                continue
            seen = set()
            for parameter in parameters[:32]:
                name, separator, raw = parameter.partition("=")
                name = name.strip().lower()
                if name not in {"for", "by", "host", "proto"} or not separator:
                    entry["parameters"].append({"name": "<UNKNOWN_OR_INVALID>", "value": "<MASKED>"})
                    continue
                if name in seen: entry["duplicate_parameter"] = True
                seen.add(name)
                raw = raw.strip()
                quoted = raw.startswith('"')
                if name in {"for", "by"}: value_summary = self.ip_structure(raw)
                elif name == "host": value_summary = self.authority(raw[1:-1] if quoted and raw.endswith('"') else raw)
                else:
                    text = raw[1:-1] if quoted and raw.endswith('"') else raw
                    value_summary = {"value": text if text in {"http", "https"} else "<MASKED_INVALID>"}
                entry["parameters"].append({"name": name, "quoted": quoted, "summary": value_summary})
            result.append(entry)
        return {"present": True, "entry_count": len(elements), "structure": result,
                "truncated": len(elements) > 32}

    def capture(self, headers, peer_ip):
        captured = {}
        for name in FIELDS:
            values = headers.get_all(name, []) if hasattr(headers, "get_all") else ([headers[name]] if name in headers else [])
            field = {"present": bool(values), "field_count": len(values), "values": [],
                     "shapes": [{"length": len(value), "ascii": value.isascii(),
                         "comma_count": value.count(","), "quotes_present": '"' in value,
                         "whitespace_present": bool(re.search(r"\s", value)),
                         "controls_present": any(ord(c)<32 and c!='\t' or ord(c)==127 for c in value)}
                         for value in values[:8]]}
            if name == "X-Envoy-External-Address":
                field["address_format"] = [self.ip_structure(value) for value in values[:8]]
            else:
                for value in values[:8]:
                    if name in {"Host", "X-Forwarded-Host"}: summary = self.authority(value)
                    elif name == "Origin":
                        try:
                            parts = urlsplit(value)
                            summary = self.authority(parts.netloc) if parts.scheme in {"http", "https"} else {"value": "<MASKED_INVALID>"}
                            summary["scheme"] = parts.scheme if parts.scheme in {"http", "https"} else "<MASKED_INVALID>"
                            summary["path_query_or_fragment_present"] = bool(parts.path or parts.query or parts.fragment)
                        except ValueError: summary = {"value": "<MASKED_INVALID>"}
                    elif name == "X-Forwarded-Proto":
                        parts = value.split(",") if len(value) <= 4096 else []
                        summary = {"structure": [part.strip() if part.strip() in {"http", "https"} else "<MASKED_INVALID>" for part in parts[:32]],
                                   "comma_chain": len(parts) > 1, "whitespace_present": bool(re.search(r"\s", value))}
                    elif name == "X-Forwarded-Port":
                        summary = {"value": int(value) if re.fullmatch(r"[0-9]{1,5}", value) and 1 <= int(value) <= 65535 else "<MASKED_INVALID>"}
                    elif name == "X-Forwarded-For": summary = self.chain(value)
                    else: summary = self.forwarded(value)
                    field["values"].append(summary)
            captured[name] = field
        peer = self.ip_structure(peer_ip or "")
        peer["trusted_by_unchanged_v005"] = proxy.trusted_peer(peer_ip)
        return {"headers": captured, "tcp_peer": peer,
                "trusted_peer_policy": {"kind": "LOOPBACK_OR_EXACT_RESOLVED_POD_ADDRESS",
                    "addresses": [self.ip_structure(value) for value in sorted(proxy.pod_addresses())[:64]],
                    "address_count": len(proxy.pod_addresses())},
                "known_envoy_istio_header_names": sorted({name.lower() for name in headers.keys()} & KNOWN_RELATED)}

    def observe(self, policy, headers, *, method, peer_ip):
        try:
            effective = policy.check_request(headers, method=method, peer_ip=peer_ip)
            validation = {"status": "PASS", "FAILED_VALIDATION_RULE": None}
            error = None
        except SecurityError as failure:
            effective, error = None, failure
            validation = {"status": "FAIL", "error_code": failure.code, **failure_rule(failure, self.catalog)}
        report = {"diagnostic_mode": "PROXY_ONLY", "validator_sha256": EXPECTED_PROXY_SHA256,
                  "validation": validation, "engine_ready": False, "gpu": "NOT_RUN",
                  "rendering": "DISABLED", **self.capture(headers, peer_ip)}
        return effective, error, report
