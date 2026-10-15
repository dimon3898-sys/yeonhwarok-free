#!/usr/bin/env python3
"""Bounded, read-only GHCR checks for the separately authorized image workflow.

Usage (credentials come from GH_TOKEN and GITHUB_ACTOR, never arguments):
  python3 registry_guard.py check-tag --tag rtx4080s-2f9158b-123456-1
  python3 registry_guard.py inspect-digest --digest sha256:<64 lowercase hex>

Only the fixed repository below is supported. check-tag permits an unambiguous
MANIFEST_UNKNOWN response; it does not reserve the tag or prove write access.
The workflow must serialize its writers and must never overwrite a tag. Issued
JWT scope observations are not a push test. Opaque issued tokens are explicitly
unverified. Only a separately successful push establishes actual write success.

inspect-digest checks remote raw manifest/index, amd64 child, and config hashes;
it does not download/verify layer contents, run the image, or test a GPU. Its
imageReference is the immutable gCube input: ghcr.io/<repository>@sha256:...
No login, upload, deletion, retry, token persistence, or visibility change occurs.
TLS certificate verification uses urllib's default HTTPS trust configuration.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import os
import re
import sys
from typing import Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REGISTRY = "https://ghcr.io"
REPOSITORY = "dimon3898-sys/world-simulation-shorts-engine"
IMAGE = "ghcr.io/" + REPOSITORY
TIMEOUT_SECONDS = 20
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
MAX_TOKEN_RESPONSE_BYTES = 64 * 1024
MAX_TOKEN_BYTES = 16 * 1024
MAX_INDEX_DESCRIPTORS = 1024
TAG_PATTERN = re.compile(r"rtx4080s-2f9158b-[1-9][0-9]*-[1-9][0-9]*", re.ASCII)
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}", re.ASCII)
ACTOR_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?", re.ASCII)
MANIFEST_TYPES = frozenset((
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))
INDEX_TYPES = frozenset((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
))
CONFIG_TYPES = frozenset((
    "application/vnd.oci.image.config.v1+json",
    "application/vnd.docker.container.image.v1+json",
))
LAYER_TYPES = frozenset((
    "application/vnd.oci.image.layer.v1.tar",
    "application/vnd.oci.image.layer.v1.tar+gzip",
    "application/vnd.oci.image.layer.v1.tar+zstd",
    "application/vnd.oci.image.layer.nondistributable.v1.tar",
    "application/vnd.oci.image.layer.nondistributable.v1.tar+gzip",
    "application/vnd.oci.image.layer.nondistributable.v1.tar+zstd",
    "application/vnd.docker.image.rootfs.diff.tar.gzip",
    "application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
))
MANIFEST_ACCEPT = ", ".join(sorted(MANIFEST_TYPES | INDEX_TYPES))


class GuardError(Exception):
    """A fixed, secret-free reason code; remote messages are never propagated."""

    def __init__(self, code: str):
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code, re.ASCII):
            code = "INTERNAL_GUARD_ERROR"
        super().__init__(code)


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _header(response: Response, name: str) -> str | None:
    matches = [v for k, v in response.headers.items() if k.lower() == name.lower()]
    if len(matches) > 1 or any(not isinstance(v, str) for v in matches):
        raise GuardError("INVALID_RESPONSE_HEADER")
    return matches[0] if matches else None


def _http_get(url: str, headers: Mapping[str, str], max_bytes: int) -> Response:
    """One bounded GET, no implicit redirects or retries, default verified TLS."""
    try:
        opener = build_opener(_NoRedirect())
        request = Request(url, headers=dict(headers), method="GET")
        try:
            stream = opener.open(request, timeout=TIMEOUT_SECONDS)
        except HTTPError as error:
            stream = error
        with stream:
            # Preserve duplicate headers as comma-separated values, so checks
            # cannot silently choose one conflicting digest/length/location.
            collected = {
                key.lower(): ",".join(stream.headers.get_all(key))
                for key in stream.headers.keys()
            }
            length = collected.get("content-length")
            if length is not None and (
                not re.fullmatch(r"[0-9]+", length, re.ASCII)
                or int(length) > max_bytes
            ):
                raise GuardError("RESPONSE_TOO_LARGE_OR_INVALID_LENGTH")
            body = stream.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise GuardError("RESPONSE_TOO_LARGE")
            return Response(stream.code, collected, body)
    except GuardError:
        raise
    except Exception:
        # urllib exceptions may contain URLs, signed queries or headers.
        raise GuardError("NETWORK_OR_TLS_FAILURE") from None


def _json_object(body: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("constant")

    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise ValueError("object")
        pending = [(value, 0)]
        count = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 32 or count > 20000:
                raise ValueError("complexity")
            if isinstance(item, dict):
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
        return value
    except Exception:
        raise GuardError("INVALID_JSON_RESPONSE") from None


def validate_tag(tag: str) -> str:
    if not isinstance(tag, str) or len(tag) > 128 or not TAG_PATTERN.fullmatch(tag):
        raise GuardError("INVALID_TAG")
    return tag


def validate_digest(digest: str) -> str:
    if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        raise GuardError("INVALID_DIGEST")
    return digest


def _token_string(value) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TOKEN_BYTES:
        raise GuardError("INVALID_TOKEN_RESPONSE")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise GuardError("INVALID_TOKEN_RESPONSE")
    return value


def _issued_access(token: str) -> dict:
    observation = {"status": "UNVERIFIED", "pull": None, "push": None,
                   "pushVerified": False}
    parts = token.split(".")
    if len(parts) != 3:
        return observation
    if any(not part or not re.fullmatch(r"[A-Za-z0-9_-]+", part, re.ASCII)
           for part in parts):
        raise GuardError("INVALID_ISSUED_JWT")
    try:
        payload = base64.b64decode(parts[1] + "=" * (-len(parts[1]) % 4),
                                   altchars=b"-_", validate=True)
        claims = _json_object(payload)
    except Exception:
        raise GuardError("INVALID_ISSUED_JWT") from None
    access = claims.get("access")
    if not isinstance(access, list):
        raise GuardError("ISSUED_ACCESS_UNVERIFIED")
    matching = [item for item in access if isinstance(item, dict)
                and item.get("type") == "repository"
                and item.get("name") == REPOSITORY]
    if len(matching) != 1:
        raise GuardError("ISSUED_ACCESS_UNVERIFIED")
    actions = matching[0].get("actions")
    if (not isinstance(actions, list) or any(not isinstance(v, str) for v in actions)
            or not {"pull", "push"}.issubset(actions)):
        raise GuardError("ISSUED_PULL_PUSH_NOT_GRANTED")
    return {"status": "OBSERVED_IN_ISSUED_TOKEN", "pull": True, "push": True,
            "pushVerified": False}


def _descriptor(value, media_types: frozenset, max_size: int | None = None) -> dict:
    if (not isinstance(value, dict) or not isinstance(value.get("mediaType"), str)
            or value["mediaType"] not in media_types):
        raise GuardError("INVALID_DESCRIPTOR_MEDIA_TYPE")
    validate_digest(value.get("digest"))
    size = value.get("size")
    if type(size) is not int or size <= 0 or size > 2**63 - 1:
        raise GuardError("INVALID_DESCRIPTOR_SIZE")
    if max_size is not None and size > max_size:
        raise GuardError("DESCRIPTOR_TOO_LARGE")
    return value


class RegistryGuard:
    """Inject transport/environment for tests; production transport has no retries."""

    def __init__(self, *, transport: Callable | None = None,
                 environ: Mapping[str, str] | None = None):
        self._transport = transport or _http_get
        self._environ = os.environ if environ is None else environ

    def _get(self, url: str, headers: Mapping[str, str], limit: int) -> Response:
        try:
            response = self._transport(url, headers, limit)
            if (not isinstance(response, Response) or type(response.status) is not int
                    or not isinstance(response.headers, Mapping)
                    or not isinstance(response.body, bytes)):
                raise GuardError("INVALID_TRANSPORT_RESPONSE")
            if len(response.body) > limit:
                raise GuardError("RESPONSE_TOO_LARGE")
            encoding = _header(response, "Content-Encoding")
            if encoding is not None and encoding.lower() != "identity":
                raise GuardError("UNSUPPORTED_CONTENT_ENCODING")
            return response
        except GuardError:
            raise
        except Exception:
            raise GuardError("NETWORK_OR_TLS_FAILURE") from None

    def _authenticate(self) -> tuple[str, dict]:
        actor = self._environ.get("GITHUB_ACTOR")
        if not isinstance(actor, str) or not ACTOR_PATTERN.fullmatch(actor):
            raise GuardError("GITHUB_ACTOR_REQUIRED_OR_INVALID")
        secret = self._environ.get("GH_TOKEN")
        try:
            secret = _token_string(secret)
        except GuardError:
            raise GuardError("GH_TOKEN_REQUIRED_OR_INVALID") from None
        basic = base64.b64encode((actor + ":" + secret).encode("ascii")).decode("ascii")
        url = REGISTRY + "/token?" + urlencode({
            "service": "ghcr.io", "scope": "repository:" + REPOSITORY + ":pull,push"
        })
        response = self._get(url, {"Authorization": "Basic " + basic,
                                 "Accept": "application/json",
                                 "Accept-Encoding": "identity"}, MAX_TOKEN_RESPONSE_BYTES)
        if response.status != 200:
            raise GuardError("TOKEN_HTTP_NOT_200")
        document = _json_object(response.body)
        token = document.get("token", document.get("access_token"))
        if "token" in document and "access_token" in document:
            if document["token"] != document["access_token"]:
                raise GuardError("CONFLICTING_ISSUED_TOKENS")
        token = _token_string(token)
        return token, _issued_access(token)

    @staticmethod
    def _headers(token: str, accept: str = MANIFEST_ACCEPT) -> dict:
        return {"Authorization": "Bearer " + token, "Accept": accept,
                "Accept-Encoding": "identity"}

    def check_tag(self, tag: str) -> dict:
        tag = validate_tag(tag)
        token, access = self._authenticate()
        response = self._get(REGISTRY + "/v2/" + REPOSITORY + "/manifests/" + tag,
                             self._headers(token), MAX_MANIFEST_BYTES)
        if response.status == 200:
            raise GuardError("TAG_ALREADY_EXISTS")
        if response.status != 404:
            raise GuardError("TAG_ABSENCE_NOT_VERIFIED")
        document = _json_object(response.body)
        errors = document.get("errors")
        if (not isinstance(errors, list) or not errors
                or any(not isinstance(error, dict)
                       or error.get("code") != "MANIFEST_UNKNOWN" for error in errors)):
            raise GuardError("TAG_ABSENCE_NOT_MANIFEST_UNKNOWN")
        return {"status": "PASS", "stage": "tag_absence", "tag": tag,
                "imageReference": IMAGE + ":" + tag, "tagAvailable": True,
                "tagReserved": False, "issuedAccess": access,
                "writeVerified": False}

    def _manifest(self, token: str, digest: str, expected_size: int | None = None) -> dict:
        response = self._get(REGISTRY + "/v2/" + REPOSITORY + "/manifests/" + digest,
                             self._headers(token), MAX_MANIFEST_BYTES)
        if response.status != 200:
            raise GuardError("MANIFEST_HTTP_NOT_200")
        self._verify_bytes(response, digest, expected_size, require_digest_header=True)
        content_type = _header(response, "Content-Type")
        if content_type is None:
            raise GuardError("MANIFEST_CONTENT_TYPE_REQUIRED")
        content_type = content_type.split(";", 1)[0].strip()
        if content_type not in MANIFEST_TYPES | INDEX_TYPES:
            raise GuardError("UNSUPPORTED_MANIFEST_MEDIA_TYPE")
        document = _json_object(response.body)
        if (type(document.get("schemaVersion")) is not int
                or document["schemaVersion"] != 2 or document.get("mediaType") != content_type):
            raise GuardError("INVALID_MANIFEST_SCHEMA")
        return document

    @staticmethod
    def _verify_bytes(response: Response, digest: str, size: int | None,
                      *, require_digest_header: bool = False) -> None:
        if "sha256:" + hashlib.sha256(response.body).hexdigest() != digest:
            raise GuardError("REMOTE_BODY_DIGEST_MISMATCH")
        if size is not None and len(response.body) != size:
            raise GuardError("REMOTE_BODY_SIZE_MISMATCH")
        header = _header(response, "Docker-Content-Digest")
        if require_digest_header and header is None:
            raise GuardError("REMOTE_DIGEST_HEADER_REQUIRED")
        if header is not None and header != digest:
            raise GuardError("REMOTE_DIGEST_HEADER_MISMATCH")

    def _config(self, token: str, descriptor: dict) -> dict:
        url = REGISTRY + "/v2/" + REPOSITORY + "/blobs/" + descriptor["digest"]
        response = self._get(url, self._headers(token, "application/octet-stream"),
                             MAX_CONFIG_BYTES)
        if response.status in (301, 302, 303, 307, 308):
            location = _header(response, "Location")
            try:
                target = urlsplit(location) if isinstance(location, str) else None
                if (target is None or target.scheme != "https"
                        or target.hostname not in ("ghcr.io", "pkg-containers.githubusercontent.com")
                        or target.username is not None or target.password is not None
                        or target.port not in (None, 443) or target.fragment
                        or any(ord(c) < 33 or ord(c) > 126 for c in location)):
                    raise ValueError("redirect")
            except Exception:
                raise GuardError("UNSAFE_BLOB_REDIRECT") from None
            # Only one bounded official-host redirect. Never forward credentials,
            # even to the same host; never include the signed URL in any report.
            response = self._get(location, {"Accept": "application/octet-stream",
                                           "Accept-Encoding": "identity"}, MAX_CONFIG_BYTES)
        if response.status != 200:
            raise GuardError("CONFIG_HTTP_NOT_200")
        self._verify_bytes(response, descriptor["digest"], descriptor["size"])
        return _json_object(response.body)

    def inspect_digest(self, digest: str) -> dict:
        digest = validate_digest(digest)
        token, access = self._authenticate()
        manifest = self._manifest(token, digest)
        media_type = manifest["mediaType"]
        image_digest = digest
        if media_type in INDEX_TYPES:
            descriptors = manifest.get("manifests")
            if (not isinstance(descriptors, list) or not descriptors
                    or len(descriptors) > MAX_INDEX_DESCRIPTORS):
                raise GuardError("INVALID_INDEX_DESCRIPTORS")
            selected = []
            for item in descriptors:
                item = _descriptor(item, MANIFEST_TYPES | INDEX_TYPES, MAX_MANIFEST_BYTES)
                platform = item.get("platform")
                if not isinstance(platform, dict):
                    raise GuardError("INDEX_PLATFORM_REQUIRED")
                annotations = item.get("annotations", {})
                if not isinstance(annotations, dict):
                    raise GuardError("INVALID_INDEX_ANNOTATIONS")
                if annotations.get("vnd.docker.reference.type") == "attestation-manifest":
                    if (platform.get("os") != "unknown"
                            or platform.get("architecture") != "unknown"):
                        raise GuardError("INVALID_ATTESTATION_PLATFORM")
                    continue
                if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
                    if platform.get("variant") not in (None, ""):
                        raise GuardError("UNSUPPORTED_AMD64_VARIANT")
                    if item["mediaType"] not in MANIFEST_TYPES:
                        raise GuardError("NESTED_AMD64_INDEX_UNSUPPORTED")
                    selected.append(item)
            if len(selected) != 1:
                raise GuardError("AMD64_IMAGE_NOT_UNIQUE")
            image_digest = selected[0]["digest"]
            manifest = self._manifest(token, image_digest, selected[0]["size"])
            if manifest["mediaType"] not in MANIFEST_TYPES:
                raise GuardError("NESTED_AMD64_INDEX_UNSUPPORTED")
        config = _descriptor(manifest.get("config"), CONFIG_TYPES, MAX_CONFIG_BYTES)
        layers = manifest.get("layers")
        if not isinstance(layers, list) or len(layers) > MAX_INDEX_DESCRIPTORS:
            raise GuardError("INVALID_LAYER_DESCRIPTORS")
        for layer in layers:
            _descriptor(layer, LAYER_TYPES)
        document = self._config(token, config)
        if (document.get("os") != "linux" or document.get("architecture") != "amd64"
                or document.get("variant") not in (None, "")):
            raise GuardError("CONFIG_PLATFORM_MISMATCH")
        return {"status": "PASS", "stage": "remote_digest", "digest": digest,
                "imageReference": IMAGE + "@" + digest,
                "mediaType": media_type, "imageManifestDigest": image_digest,
                "configDigest": config["digest"], "platform": "linux/amd64",
                "remotePresenceVerified": True, "manifestAndConfigBytesVerified": True,
                "layerContentsVerified": False, "issuedAccess": access,
                "writeVerified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-tag").add_argument("--tag", required=True)
    commands.add_parser("inspect-digest").add_argument("--digest", required=True)
    args = parser.parse_args(argv)
    try:
        guard = RegistryGuard()
        result = (guard.check_tag(args.tag) if args.command == "check-tag"
                  else guard.inspect_digest(args.digest))
    except GuardError as error:
        result = {"status": "BLOCK", "stage": args.command,
                  "reason": str(error), "writeVerified": False}
    except Exception:
        # Never let an unexpected parsing error print remote data or credentials.
        result = {"status": "BLOCK", "stage": args.command,
                  "reason": "INTERNAL_GUARD_ERROR", "writeVerified": False}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
