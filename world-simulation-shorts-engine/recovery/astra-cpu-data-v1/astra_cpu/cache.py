"""Verified CPU raw/neutral cache and opt-in, bounded HTTPS acquisition.

Only complete artifacts become cache hits. Resume state consists of immutable,
validated Range chunks; an interrupted response is never appended. Locally
computed hashes establish byte consistency, not provider-authenticated accuracy.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import timezone
from email.utils import parsedate_to_datetime
import fcntl
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .download_contract import DownloadRequest, DownloadResponse
from .model import DataError, RasterData, sha256, validate_bbox
from .neutral import decode_neutral, encode_neutral


MAX_BYTES = 64 * 1024 * 1024
_MANIFEST_LIMIT = 128 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_STRONG_ETAG = re.compile(r'"[\x21\x23-\x7e\x80-\xff]*"\Z')
_THREAD_LOCKS = {}
_REGISTRY_LOCK = threading.Lock()
_ACTIVE_LOCK_FDS = set()
_LOCK_CONTEXT = threading.local()


def _after_fork_child():
    # Close inherited descriptors without LOCK_UN: their open descriptions are
    # shared with the parent, whose locks must remain held until it completes.
    global _THREAD_LOCKS, _REGISTRY_LOCK, _ACTIVE_LOCK_FDS, _LOCK_CONTEXT
    for descriptor in _ACTIVE_LOCK_FDS:
        os.close(descriptor)
    _ACTIVE_LOCK_FDS = set()
    _THREAD_LOCKS = {}
    _REGISTRY_LOCK = threading.Lock()
    _LOCK_CONTEXT = threading.local()


os.register_at_fork(before=lambda: _REGISTRY_LOCK.acquire(),
                    after_in_parent=lambda: _REGISTRY_LOCK.release(), after_in_child=_after_fork_child)


def _open_lock_file(path):
    with _REGISTRY_LOCK:
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        _ACTIVE_LOCK_FDS.add(descriptor)
    return descriptor


def _close_lock_file(descriptor):
    with _REGISTRY_LOCK:
        _ACTIVE_LOCK_FDS.discard(descriptor)
        os.close(descriptor)


class CacheError(DataError):
    """A cache/acquisition failure, with a safe code and provider-compatible state."""
    def __init__(self, message, *, code="CACHE_INVALID", status="invalid_data"):
        if status not in {"unavailable", "auth_required", "version_changed", "license_unverified", "invalid_data"}:
            raise DataError("CacheError requires a failure status")
        super().__init__(message)
        self.code = code
        self.status = status


def _finite_json(value, depth=0):
    if depth > 16:
        raise CacheError("cache descriptor nesting exceeds limit")
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CacheError("cache descriptor dictionary keys must be strings")
        return {key: _finite_json(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(item, depth + 1) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(float(value))
        except (ValueError, TypeError, OverflowError):
            finite = False
        if not finite:
            raise CacheError("cache descriptor numbers must be finite")
    elif value is not None and not isinstance(value, (str, bool)):
        raise CacheError("unsupported cache descriptor value")
    return value


def _canonical(value):
    try:
        encoded = json.dumps(_finite_json(value), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as error:
        raise CacheError("invalid cache descriptor") from error
    if len(encoded) > _MANIFEST_LIMIT:
        raise CacheError("cache descriptor exceeds bounded manifest size")
    return encoded


def _hash_value(value, name, *, optional=False):
    if optional and value is None:
        return
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise CacheError(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True)
class CacheRequest:
    source_id: str
    source_version: str
    bbox: tuple | None = None
    crs: str = "EPSG:4326"
    resolution: object = None
    source_sha256: str | None = None
    transform_version: str = "RAW_BYTES_V1"
    source_metadata_sha256: str | None = None
    url_sha256: str | None = None
    byte_range: tuple | None = None
    expected_etag: str | None = None
    total_object_bytes: int | None = None

    def validate(self):
        for value in (self.source_id, self.source_version, self.crs, self.transform_version):
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise CacheError("pinned source/version/CRS/transform identifiers are required")
        for name in ("source_sha256", "source_metadata_sha256", "url_sha256"):
            _hash_value(getattr(self, name), name, optional=True)
        if self.source_sha256 is None and self.source_metadata_sha256 is None and self.url_sha256 is None:
            raise CacheError("unknown source SHA requires request URL or metadata identity")
        if self.bbox is not None:
            try:
                validate_bbox(self.bbox)
            except DataError as error:
                raise CacheError("invalid finite geographic cache bbox") from error
        _canonical(self.resolution)
        if isinstance(self.resolution, (int, float)) and (isinstance(self.resolution, bool) or self.resolution <= 0):
            raise CacheError("scalar cache resolution must be positive")
        if self.total_object_bytes is not None and (isinstance(self.total_object_bytes, bool)
                or not isinstance(self.total_object_bytes, int) or self.total_object_bytes <= 0):
            raise CacheError("object size must be a positive integer")
        _finite_json(self.total_object_bytes)
        if self.byte_range is not None:
            if (not isinstance(self.byte_range, (list, tuple)) or len(self.byte_range) != 2
                    or any(isinstance(n, bool) or not isinstance(n, int) for n in self.byte_range)
                    or not 0 <= self.byte_range[0] <= self.byte_range[1]
                    or self.byte_range[1] - self.byte_range[0] + 1 > MAX_BYTES
                    or (self.total_object_bytes is not None and self.byte_range[1] >= self.total_object_bytes)):
                raise CacheError("invalid bounded byte interval")
        if self.expected_etag is not None and (not isinstance(self.expected_etag, str)
                or not self.expected_etag or len(self.expected_etag) > 1024
                or any(ord(c) < 32 or ord(c) == 127 for c in self.expected_etag)):
            raise CacheError("ETag must be nonempty header-safe text")

    def descriptor(self, source_sha256=None):
        self.validate()
        if source_sha256 is not None:
            _hash_value(source_sha256, "resolved source SHA")
        return {"sourceId": self.source_id, "sourceVersion": self.source_version,
                "bbox": list(self.bbox) if self.bbox is not None else None, "crs": self.crs,
                "resolution": _finite_json(self.resolution),
                "sourceSha256": source_sha256 if source_sha256 is not None else self.source_sha256,
                "transformVersion": self.transform_version,
                "sourceMetadataSha256": self.source_metadata_sha256, "urlSha256": self.url_sha256,
                "byteRange": list(self.byte_range) if self.byte_range is not None else None,
                "expectedEtag": self.expected_etag, "totalObjectBytes": self.total_object_bytes}

    def lookup_key(self):
        return sha256(_canonical(self.descriptor()))

    def resolved_key(self, actual_sha256):
        return sha256(_canonical(self.descriptor(actual_sha256)))

    @classmethod
    def from_download(cls, request):
        try:
            request.validate()
        except (DataError, TypeError, ValueError) as error:
            raise CacheError("invalid download request") from error
        return cls(request.source_id, request.source_version, request.bbox, request.crs,
                   deepcopy(request.resolution), request.expected_sha256, "RAW_RESPONSE_V1",
                   request.source_metadata_sha256, sha256(request.url.encode()), request.byte_range,
                   request.expected_etag, request.total_object_bytes)


@dataclass(frozen=True)
class CacheEntry:
    data: bytes
    sha256: str
    key: str
    metadata: dict

    @property
    def actual_sha256(self):
        return self.sha256


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_bounded(path, limit):
    try:
        # Generated names are hashes, and cache artifacts must be ordinary files.
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            attributes = os.fstat(stream.fileno())
            if not stat.S_ISREG(attributes.st_mode):
                raise CacheError("cache artifact must be an ordinary file")
            if attributes.st_size > limit:
                raise CacheError("cache artifact exceeds byte limit")
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise CacheError("cache artifact exceeds byte limit")
        return data
    except FileNotFoundError:
        raise
    except OSError as error:
        raise CacheError("cache artifact cannot be read safely") from error


def _load_json(path):
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CacheError("duplicate cache manifest key")
            result[key] = value
        return result
    try:
        value = json.loads(_read_bounded(path, _MANIFEST_LIMIT), object_pairs_hook=unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(CacheError("nonfinite cache manifest")))
        if not isinstance(value, dict):
            raise CacheError("cache manifest must be an object")
        _canonical(value)
        return value
    except FileNotFoundError:
        return None
    except (ValueError, TypeError, UnicodeError) as error:
        raise CacheError("invalid cache manifest") from error


def _atomic_write(path, data, *, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                existing = _read_bounded(path, max(len(data), 1))
                if existing != data:
                    raise CacheError("existing immutable cache blob is corrupt")
        else:
            os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class FileCache:
    """Content-addressed bytes plus atomically published, versioned lookups.

    Corruption raises CacheError (a DataError); repair and garbage collection are
    explicit future operations. Lock files are never unlinked or shared by FD.
    """
    def __init__(self, root, max_bytes=MAX_BYTES, *, create=True):
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 0 < max_bytes <= MAX_BYTES:
            raise CacheError("cache byte limit must be 1..64MiB")
        if not isinstance(create, bool):
            raise CacheError("cache create flag must be an explicit boolean")
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes
        # This flag controls constructor initialization, not authorization for
        # later writes. Callers enforce their cache read/write mode separately.
        if not create:
            return
        for kind in ("raw", "derived"):
            (self.root / "blobs" / kind).mkdir(parents=True, exist_ok=True)
            (self.root / "lookups" / kind).mkdir(parents=True, exist_ok=True)
        (self.root / "locks").mkdir(parents=True, exist_ok=True)
        (self.root / "partials").mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self, name, *, deadline=None, clock=time.monotonic, sleep=time.sleep):
        lock_path = self.root / "locks" / (sha256(name.encode()) + ".lock")
        registry_key = str(lock_path)
        held = getattr(_LOCK_CONTEXT, "held", set())
        if registry_key in held:
            raise CacheError("recursive producer cannot reacquire the same cache source lock")
        with _REGISTRY_LOCK:
            thread_lock = _THREAD_LOCKS.setdefault(registry_key, threading.Lock())
        remaining = None if deadline is None else max(0, deadline - clock())
        acquired = thread_lock.acquire() if remaining is None else thread_lock.acquire(timeout=remaining)
        if not acquired:
            raise CacheError("cache lock deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
        descriptor = None
        locked = False
        try:
            descriptor = _open_lock_file(lock_path)
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except BlockingIOError:
                    if deadline is not None and clock() >= deadline:
                        raise CacheError("cache lock deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
                    sleep(.01 if deadline is None else min(.01, max(0, deadline - clock())))
            held.add(registry_key)
            _LOCK_CONTEXT.held = held
            yield
        finally:
            if descriptor is not None:
                if locked:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                _close_lock_file(descriptor)
            held.discard(registry_key)
            thread_lock.release()

    def _lock_name(self, request, kind="raw"):
        # Different lookups of the same pinned exact bytes share one acquisition.
        return kind + ":" + (request.source_sha256 or request.lookup_key())

    def _raw_assertions(self, request, data, metadata):
        if ((request.byte_range is not None and len(data) != request.byte_range[1] - request.byte_range[0] + 1)
                or (request.byte_range is None and request.total_object_bytes is not None
                    and len(data) != request.total_object_bytes)):
            raise CacheError("raw artifact differs from requested interval/object size")
        claims = {"responseSha256": sha256(data), "sourceVersion": request.source_version,
                  "sourceMetadataSha256": request.source_metadata_sha256,
                  "byteRange": list(request.byte_range) if request.byte_range is not None else None,
                  "checksumOrigin": "provided_expected_sha256" if request.source_sha256 is not None
                  else "self_computed_at_download"}
        for field, expected in claims.items():
            if field in metadata and metadata[field] != expected:
                raise CacheError("cached receipt contradicts request/content identity")
        if request.expected_etag is not None and metadata.get("etag") not in (None, request.expected_etag):
            raise CacheError("cached receipt contradicts pinned ETag")
        if (request.expected_etag is not None and metadata.get("etag") is None
                and request.source_sha256 is None):
            raise CacheError("unpinned cached artifact lacks required ETag evidence")

    def _get(self, request, kind):
        descriptor = request.descriptor()
        manifest = _load_json(self.root / "lookups" / kind / (request.lookup_key() + ".json"))
        if manifest is None:
            return None
        if manifest.get("schema") != "ASTRA_FILE_CACHE_V1" or manifest.get("kind") != kind:
            raise CacheError("unsupported cache manifest schema/kind")
        if manifest.get("request") != descriptor:
            raise CacheError("cache request identity mismatch")
        digest = manifest.get("blobSha256")
        source_sha = manifest.get("sourceSha256")
        _hash_value(digest, "cache blob SHA")
        _hash_value(source_sha, "cache source SHA")
        if request.source_sha256 is not None and source_sha != request.source_sha256:
            raise CacheError("cache source SHA differs from pinned source")
        if kind == "raw" and source_sha != digest:
            raise CacheError("raw content SHA differs from source SHA")
        if manifest.get("resolvedKey") != request.resolved_key(source_sha):
            raise CacheError("cache resolved key mismatch")
        size = manifest.get("byteLength")
        if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= self.max_bytes:
            raise CacheError("invalid bounded cache byte length")
        try:
            data = _read_bounded(self.root / "blobs" / kind / (digest + ".bin"), self.max_bytes)
        except FileNotFoundError as error:
            raise CacheError("published cache blob is missing") from error
        if len(data) != size or sha256(data) != digest:
            raise CacheError("cache blob size/SHA-256 mismatch")
        metadata = manifest.get("metadata")
        if not isinstance(metadata, dict):
            raise CacheError("invalid cache receipt metadata")
        if kind == "raw":
            self._raw_assertions(request, data, metadata)
        return CacheEntry(data, digest, manifest["resolvedKey"], deepcopy(metadata))

    def _put(self, request, data, kind, *, source_sha, metadata=None):
        if not isinstance(data, bytes) or len(data) > self.max_bytes:
            raise CacheError("cache data must be bounded bytes")
        _hash_value(source_sha, "source SHA")
        if request.source_sha256 is not None and request.source_sha256 != source_sha:
            raise CacheError("source SHA-256 mismatch")
        digest = sha256(data)
        if kind == "raw" and digest != source_sha:
            raise CacheError("raw SHA-256 mismatch")
        metadata = {} if metadata is None else _finite_json(metadata)
        if not isinstance(metadata, dict):
            raise CacheError("cache receipt metadata must be a dictionary")
        if kind == "raw":
            self._raw_assertions(request, data, metadata)
        manifest = {"schema": "ASTRA_FILE_CACHE_V1", "kind": kind,
                    "request": request.descriptor(), "resolvedKey": request.resolved_key(source_sha),
                    "sourceSha256": source_sha, "blobSha256": digest,
                    "byteLength": len(data), "metadata": metadata}
        encoded = _canonical(manifest)
        _atomic_write(self.root / "blobs" / kind / (digest + ".bin"), data, immutable=True)
        _atomic_write(self.root / "lookups" / kind / (request.lookup_key() + ".json"), encoded)
        return CacheEntry(data, digest, manifest["resolvedKey"], deepcopy(metadata))

    def get_raw(self, request):
        return self._get(request, "raw")

    def put_raw(self, request, data, receipt_metadata=None):
        request.validate()
        if not isinstance(data, bytes):
            raise CacheError("raw cache data must be exact bytes")
        with self._lock(self._lock_name(request)):
            return self._put(request, data, "raw", source_sha=sha256(data), metadata=receipt_metadata)

    def get_or_create_raw(self, request, producer):
        request.validate()
        with self._lock(self._lock_name(request)):
            entry = self._get(request, "raw")
            if entry is not None:
                return entry
            # Reuse already verified pinned bytes under another request lookup.
            if request.source_sha256 is not None:
                blob = self.root / "blobs" / "raw" / (request.source_sha256 + ".bin")
                if blob.exists():
                    data = _read_bounded(blob, self.max_bytes)
                    if sha256(data) != request.source_sha256:
                        raise CacheError("existing raw cache blob SHA-256 mismatch")
                    return self._put(request, data, "raw", source_sha=request.source_sha256)
            data = producer()
            if not isinstance(data, bytes):
                raise CacheError("raw producer must return exact bytes")
            return self._put(request, data, "raw", source_sha=sha256(data))

    def _derived_provenance(self, request, raster):
        if request.source_sha256 is None:
            raise CacheError("neutral cache requires a resolved source SHA")
        if request.source_metadata_sha256 is None:
            raise CacheError("neutral cache requires sidecar/datum/catalog metadata SHA")
        if not isinstance(raster, RasterData):
            raise CacheError("neutral cache requires RasterData")
        if raster.valid.dtype.kind != "b":
            raise CacheError("neutral support mask must be actual booleans")
        if raster.metadata.get("inputSha256") != request.source_sha256:
            raise CacheError("neutral original inputSha256 differs from source SHA")
        if raster.metadata.get("crs") != request.crs:
            raise CacheError("neutral native CRS differs from cache request")
        if request.bbox is not None:
            west, south, east, north = validate_bbox(request.bbox)
            columns = ((raster.x >= west) & (raster.x < east)) if west < east else (
                (raster.x >= west) | (raster.x < east))
            if not columns.all() or not ((raster.y >= south) & (raster.y < north)).all():
                raise CacheError("neutral sample centers lie outside requested bbox/parts")

    def get_derived(self, request):
        request.validate()
        entry = self._get(request, "derived")
        if entry is None:
            return None
        try:
            raster = decode_neutral(entry.data, expected_sha256=entry.sha256)
        except DataError as error:
            raise CacheError("invalid neutral cache artifact") from error
        self._derived_provenance(request, raster)
        if (raster.metadata.get("cacheTransformVersion") != request.transform_version
                or raster.metadata.get("cacheSourceMetadataSha256") != request.source_metadata_sha256):
            raise CacheError("neutral derivation/catalog provenance mismatch")
        return raster

    def put_derived(self, request, raster):
        request.validate()
        self._derived_provenance(request, raster)
        metadata = deepcopy(raster.metadata)
        metadata.update(cacheTransformVersion=request.transform_version,
                        cacheSourceMetadataSha256=request.source_metadata_sha256)
        frozen = RasterData(raster.values, raster.x, raster.y, raster.valid, metadata)
        data = encode_neutral(frozen)
        with self._lock("derived:" + request.lookup_key()):
            existing = self._get(request, "derived")
            if existing is not None and existing.sha256 != sha256(data):
                raise CacheError("neutral output changed without source/metadata/transform identity change")
            return self._put(request, data, "derived", source_sha=request.source_sha256)


def _validate_url(url):
    try:
        if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError("unsafe URL text")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment or "\\" in parsed.netloc):
            raise ValueError("unsafe HTTPS URL")
        if parsed.port is not None and not 0 < parsed.port <= 65535:
            raise ValueError("invalid port")
        return parsed.hostname.lower()
    except (ValueError, TypeError) as error:
        raise CacheError("URL must be HTTPS without userinfo, fragment or control characters", code="INVALID_URL") from error


_CRITICAL_HEADERS = frozenset({"content-length", "content-range", "etag", "retry-after",
                               "content-encoding", "content-type", "transfer-encoding", "location"})


def _headers(headers):
    if not hasattr(headers, "items"):
        raise CacheError("response headers must be a mapping", code="INVALID_HEADERS")
    result = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise CacheError("response header names/values must be text", code="INVALID_HEADERS")
        name = name.lower()
        if name in result and name in _CRITICAL_HEADERS:
            raise CacheError("duplicate critical response header", code="INVALID_HEADERS")
        if name in _CRITICAL_HEADERS and (len(value) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise CacheError("invalid critical response header", code="INVALID_HEADERS")
        result[name] = value.strip()
    return result


def _positive_header_integer(value, name, *, zero=False):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value):
        raise CacheError(f"invalid {name}", code="INVALID_RESPONSE_SIZE")
    number = int(value)
    if number < (0 if zero else 1):
        raise CacheError(f"invalid {name}", code="INVALID_RESPONSE_SIZE")
    return number


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class UrllibTransport:
    """HTTPS GET with inherited proxies, verified CA trust, and explicit policy.

    Read-one calls and remaining-deadline socket timeouts bound streamed reads.
    Redirect bodies are closed without being drained; each target is validated.
    """
    def __init__(self, *, network_enabled=False, allowed_hosts=(), clock=time.monotonic):
        if not isinstance(network_enabled, bool):
            raise CacheError("network_enabled must be a boolean")
        if isinstance(allowed_hosts, str) or any(not isinstance(host, str) or not host
                or any(c.isspace() for c in host) or "/" in host or "*" in host
                for host in allowed_hosts):
            raise CacheError("allowed_hosts must contain exact host names")
        self.network_enabled = network_enabled
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.clock = clock

    def _policy(self, url):
        host = _validate_url(url)
        if not self.network_enabled:
            raise CacheError("real network acquisition is disabled", code="NETWORK_DISABLED", status="unavailable")
        if host not in self.allowed_hosts:
            raise CacheError("HTTPS host is not explicitly allowed", code="HOST_NOT_ALLOWED", status="unavailable")

    def __call__(self, request, *, headers, timeout, deadline):
        self._policy(request.url)
        # build_opener preserves the standard environment ProxyHandler. TLS
        # verification and configured SSL_CERT_FILE/SSL_CERT_DIR remain enabled.
        opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        url = request.url
        for redirects in range(4):
            self._policy(url)
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise CacheError("download deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
            query = Request(url, headers=headers, method="GET")
            try:
                response = opener.open(query, timeout=min(timeout, remaining))
            except HTTPError as error:
                response = error
            try:
                normalized = _headers(response.headers)
                status = response.status if hasattr(response, "status") else response.code
                if status in (301, 302, 303, 307, 308):
                    if redirects == 3 or "location" not in normalized:
                        raise CacheError("redirect limit or missing location", code="INVALID_REDIRECT")
                    target = urljoin(url, normalized["location"])
                    self._policy(target)
                    url = target
                    continue
                if status not in (200, 206):
                    # Error HTML/credentials are neither retained nor logged.
                    return DownloadResponse(status, normalized, b"")
                if (request.byte_range is not None and status != 206) or (request.byte_range is None and status != 200):
                    # A server ignoring Range can offer an enormous full body.
                    # Close it immediately; response validation reports refusal.
                    return DownloadResponse(status, normalized, b"")
                if normalized.get("content-encoding", "identity").lower() != "identity":
                    raise CacheError("encoded HTTP bodies are unsupported", code="UNSUPPORTED_ENCODING")
                if "content-length" in normalized:
                    size = _positive_header_integer(normalized["content-length"], "Content-Length", zero=True)
                    if size > request.max_bytes:
                        raise CacheError("HTTP body exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
                pieces, size = [], 0
                while True:
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        raise CacheError("download deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
                    # CPython's urllib HTTPResponse exposes its SocketIO socket.
                    # Reject an unsupported stream instead of claiming a deadline
                    # for a read that cannot be bounded.
                    fp = getattr(response, "fp", None)
                    if fp is None:
                        break
                    socket = getattr(getattr(fp, "raw", None), "_sock", None)
                    if socket is None or not callable(getattr(response, "read1", None)):
                        raise CacheError("HTTP stream cannot enforce read deadline", code="UNBOUNDED_HTTP_STREAM")
                    socket.settimeout(min(timeout, remaining))
                    piece = response.read1(min(64 * 1024, request.max_bytes - size + 1))
                    if self.clock() >= deadline:
                        raise CacheError("download deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
                    if not piece:
                        break
                    size += len(piece)
                    if size > request.max_bytes:
                        raise CacheError("HTTP body exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
                    pieces.append(piece)
                return DownloadResponse(status, normalized, b"".join(pieces))
            finally:
                response.close()
        raise CacheError("redirect limit exceeded", code="INVALID_REDIRECT")


@dataclass(frozen=True)
class DownloadResult:
    status: str
    body: bytes | None = None
    response_sha256: str | None = None
    checksum_origin: str | None = None
    etag: str | None = None
    cache_hit: bool = False
    resumed: bool = False
    attempts: int = 0
    error: dict | None = None

    def __post_init__(self):
        if self.status == "available":
            if (not isinstance(self.body, bytes) or not self.body or self.error is not None
                    or self.response_sha256 != sha256(self.body)
                    or self.checksum_origin not in {"provided_expected_sha256", "self_computed_at_download"}):
                raise CacheError("available download receipt requires complete verified bytes")
        elif self.status not in {"unavailable", "auth_required", "version_changed", "license_unverified", "invalid_data"}:
            raise CacheError("invalid download receipt status")
        elif self.body is not None or self.response_sha256 is not None:
            raise CacheError("failed download receipt cannot carry a successful artifact")


class DownloadManager:
    """Single-flight fetch with one bounded retry/deadline budget per artifact.

    An injected callable transport is an offline testing seam. Only the default
    UrllibTransport performs real networking, which is disabled by default.
    Resume is explicit because servers lacking strong ETags/Range support cannot
    safely commit recoverable chunks. Full and narrow-range hashes stay distinct.
    """
    def __init__(self, cache, transport=None, *, network_enabled=False, allowed_hosts=(),
                 max_concurrency=2, timeout_seconds=10, deadline_seconds=30,
                 max_retries=2, retry_after_ceiling=10, chunk_bytes=1024 * 1024,
                 clock=time.monotonic, sleep=time.sleep, wall_clock=time.time):
        if not isinstance(cache, FileCache):
            raise CacheError("DownloadManager requires FileCache")
        for name, value, maximum in (("max_concurrency", max_concurrency, 8),
                                     ("max_retries", max_retries, 5), ("chunk_bytes", chunk_bytes, MAX_BYTES)):
            minimum = 0 if name == "max_retries" else 1
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise CacheError(f"invalid bounded {name}")
        for name, value in (("timeout_seconds", timeout_seconds), ("deadline_seconds", deadline_seconds),
                            ("retry_after_ceiling", retry_after_ceiling)):
            _finite_json(value)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise CacheError(f"invalid finite {name}")
            if value > 3600:
                raise CacheError(f"{name} exceeds bounded one-hour policy")
            if name != "retry_after_ceiling" and value == 0:
                raise CacheError(f"{name} must be positive")
        self.cache, self.clock, self.sleep, self.wall_clock = cache, clock, sleep, wall_clock
        self.max_concurrency, self.max_retries, self.chunk_bytes = max_concurrency, max_retries, chunk_bytes
        self.timeout, self.duration, self.retry_ceiling = timeout_seconds, deadline_seconds, retry_after_ceiling
        self.transport = transport if transport is not None else UrllibTransport(
            network_enabled=network_enabled, allowed_hosts=allowed_hosts, clock=clock)
        if not callable(self.transport):
            raise CacheError("transport must be callable")

    @contextmanager
    def _slot(self, deadline):
        # Nonblocking flock permits a shared cross-process concurrency cap.
        descriptors = []
        try:
            while True:
                if self.clock() >= deadline:
                    raise CacheError("download slot deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
                for index in range(self.max_concurrency):
                    path = self.cache.root / "locks" / f"download-slot-{index}.lock"
                    descriptor = _open_lock_file(path)
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        _close_lock_file(descriptor)
                        continue
                    except Exception:
                        _close_lock_file(descriptor)
                        raise
                    descriptors.append(descriptor)
                    yield
                    return
                self.sleep(min(.01, max(0, deadline - self.clock())))
        finally:
            for descriptor in descriptors:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                _close_lock_file(descriptor)

    def _remaining(self, budget):
        remaining = budget["deadline"] - self.clock()
        if remaining <= 0:
            raise CacheError("download deadline exceeded", code="DEADLINE_EXCEEDED", status="unavailable")
        return remaining

    def _retry_delay(self, headers, budget):
        delay = min(2.0, .1 * 2 ** budget["retries"])
        if "retry-after" in headers:
            value = headers["retry-after"]
            if re.fullmatch(r"[0-9]{1,10}", value):
                delay = max(delay, float(value))
            else:
                try:
                    moment = parsedate_to_datetime(value)
                    if moment.tzinfo is None:
                        moment = moment.replace(tzinfo=timezone.utc)
                    delay = max(delay, moment.timestamp() - self.wall_clock(), 0)
                except (ValueError, TypeError, OverflowError) as error:
                    raise CacheError("invalid Retry-After", code="INVALID_RETRY_AFTER") from error
        # Do not shorten a provider-requested wait to work around rate limits.
        if delay > self.retry_ceiling or delay >= self._remaining(budget):
            raise CacheError("Retry-After exceeds bounded retry policy", code="RETRY_DELAY_EXCEEDS_POLICY", status="unavailable")
        return delay

    def _response(self, request, budget):
        while True:
            remaining = self._remaining(budget)
            headers = {"Accept-Encoding": "identity"}
            if request.byte_range is not None:
                headers["Range"] = f"bytes={request.byte_range[0]}-{request.byte_range[1]}"
                if request.expected_etag is not None:
                    headers["If-Range"] = request.expected_etag
            try:
                with self._slot(budget["deadline"]):
                    budget["attempts"] += 1
                    response = self.transport(request, headers=headers,
                                              timeout=min(self.timeout, self._remaining(budget)),
                                              deadline=budget["deadline"])
                self._remaining(budget)
                if not isinstance(response, DownloadResponse) or not isinstance(response.body, bytes):
                    raise CacheError("transport must return exact DownloadResponse bytes", code="INVALID_TRANSPORT_RESPONSE")
                if len(response.body) > request.max_bytes:
                    raise CacheError("response exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
                if isinstance(response.status, bool) or not isinstance(response.status, int) or not 100 <= response.status <= 599:
                    raise CacheError("invalid HTTP status", code="INVALID_HTTP_STATUS")
                normalized = _headers(response.headers)
                status = response.status
                if status in (200, 206):
                    return DownloadResponse(status, normalized, response.body)
                if status in (401, 403):
                    raise CacheError("source requires configured authorization", code="HTTP_AUTH_REQUIRED", status="auth_required")
                if status in (404, 410):
                    raise CacheError("source object is unavailable", code="HTTP_NOT_FOUND", status="unavailable")
                if status == 412:
                    raise CacheError("source validator changed", code="HTTP_PRECONDITION_FAILED", status="version_changed")
                if status != 429 and not 500 <= status <= 599:
                    raise CacheError("HTTP response cannot provide requested bytes", code="HTTP_STABLE_FAILURE")
                retry_headers = normalized
            except (TimeoutError, URLError) as error:
                # URLError may contain a credential-bearing URL; never retain its text.
                if isinstance(error, URLError) and not isinstance(error.reason, TimeoutError):
                    raise CacheError("HTTPS transport failed", code="TRANSPORT_FAILURE", status="unavailable") from error
                retry_headers = {}
            except HTTPException as error:
                raise CacheError("HTTP response was malformed or truncated", code="INVALID_HTTP_STREAM") from error
            if budget["retries"] >= self.max_retries:
                raise CacheError("bounded download retry budget exhausted", code="RETRIES_EXHAUSTED", status="unavailable")
            delay = self._retry_delay(retry_headers, budget)
            budget["retries"] += 1
            self.sleep(delay)

    def _validate_response(self, request, response, *, require_strong_etag=False):
        headers, body = response.headers, response.body
        if (request.expected_etag is not None and headers.get("etag") is not None
                and headers["etag"] != request.expected_etag):
            raise CacheError("response ETag differs from pinned validator", code="ETAG_MISMATCH", status="version_changed")
        if request.byte_range is not None and response.status != 206:
            raise CacheError("server refused the exact Range request", code="RANGE_NOT_HONORED")
        if request.byte_range is None and response.status != 200:
            raise CacheError("full download requires an ordinary 200 response", code="UNEXPECTED_RANGE_RESPONSE")
        if not body:
            raise CacheError("download returned an empty artifact", code="EMPTY_RESPONSE")
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise CacheError("encoded response cannot preserve requested bytes", code="UNSUPPORTED_ENCODING")
        if ("transfer-encoding" in headers and ("content-length" in headers
                or headers["transfer-encoding"].lower() != "chunked")):
            raise CacheError("ambiguous/unsupported HTTP transfer encoding", code="INVALID_TRANSFER_ENCODING")
        if headers.get("content-type", "").lower().startswith("multipart/"):
            raise CacheError("multipart byte ranges are unsupported", code="MULTIPART_RANGE_UNSUPPORTED")
        if "content-length" in headers and _positive_header_integer(headers["content-length"], "Content-Length", zero=True) != len(body):
            raise CacheError("Content-Length differs from actual body", code="RESPONSE_SIZE_MISMATCH")
        etag = headers.get("etag")
        if request.expected_etag is not None and etag != request.expected_etag:
            raise CacheError("response ETag differs from pinned validator", code="ETAG_MISMATCH", status="version_changed")
        if require_strong_etag and (not isinstance(etag, str) or _STRONG_ETAG.fullmatch(etag) is None):
            raise CacheError("safe resume requires a strong ETag", code="RESUME_REQUIRES_STRONG_ETAG")
        if request.byte_range is None:
            if response.status != 200 or "content-range" in headers:
                raise CacheError("full download requires an ordinary 200 response", code="UNEXPECTED_RANGE_RESPONSE")
            total = len(body)
            if request.total_object_bytes is not None and total != request.total_object_bytes:
                raise CacheError("object length differs from pinned size", code="OBJECT_SIZE_CHANGED", status="version_changed")
        else:
            if response.status != 206:
                raise CacheError("server refused the exact Range request", code="RANGE_NOT_HONORED")
            match = re.fullmatch(r"bytes ([0-9]{1,20})-([0-9]{1,20})/([0-9]{1,20})", headers.get("content-range", ""))
            if match is None:
                raise CacheError("invalid numeric Content-Range", code="INVALID_CONTENT_RANGE")
            start, end, total = map(int, match.groups())
            if (start, end) != tuple(request.byte_range) or not 0 <= start <= end < total or len(body) != end - start + 1:
                raise CacheError("Content-Range interval/body does not match request", code="CONTENT_RANGE_MISMATCH")
            if request.total_object_bytes is not None and total != request.total_object_bytes:
                raise CacheError("object size changed during range acquisition", code="OBJECT_SIZE_CHANGED", status="version_changed")
        return etag, total

    def _receipt(self, request, body, etag, *, resumed=False):
        digest = sha256(body)
        if request.expected_sha256 is not None and digest != request.expected_sha256:
            raise CacheError("download artifact SHA-256 mismatch", code="CHECKSUM_MISMATCH")
        return {"responseSha256": digest, "checksumOrigin": "provided_expected_sha256" if request.expected_sha256
                else "self_computed_at_download", "etag": etag, "resumed": resumed,
                "sourceMetadataSha256": request.source_metadata_sha256,
                "sourceVersion": request.source_version,
                "byteRange": list(request.byte_range) if request.byte_range is not None else None}

    def _partial_path(self, key):
        return self.cache.root / "partials" / key.lookup_key()

    def _resume(self, request, key, budget):
        partial = self._partial_path(key)
        partial.mkdir(parents=True, exist_ok=True)
        state = _load_json(partial / "state.json")
        start = request.byte_range[0] if request.byte_range is not None else 0
        end = request.byte_range[1] if request.byte_range is not None else (
            request.total_object_bytes - 1 if request.total_object_bytes is not None else None)
        pieces, chunks = [], []
        total, anchor = request.total_object_bytes, request.expected_etag
        if anchor is not None and _STRONG_ETAG.fullmatch(anchor) is None:
            raise CacheError("safe resume requires a strong expected ETag", code="RESUME_REQUIRES_STRONG_ETAG")
        resumed = state is not None
        offset = start
        if state is not None:
            if state.get("schema") != "ASTRA_RANGE_CHUNKS_V1" or state.get("request") != key.descriptor():
                raise CacheError("partial cache identity mismatch", code="INVALID_PARTIAL_STATE")
            if state.get("invalid"):
                raise CacheError("partial state was rejected earlier", code="INVALID_PARTIAL_STATE")
            total, anchor = state.get("objectBytes"), state.get("etag")
            if (isinstance(total, bool) or not isinstance(total, int) or total <= 0
                    or not isinstance(anchor, str) or _STRONG_ETAG.fullmatch(anchor) is None
                    or (request.total_object_bytes is not None and total != request.total_object_bytes)
                    or (request.expected_etag is not None and anchor != request.expected_etag)):
                raise CacheError("partial validator/object identity mismatch", code="INVALID_PARTIAL_STATE")
            if end is None:
                end = total - 1
            if end >= total or end - start + 1 > min(request.max_bytes, self.cache.max_bytes):
                raise CacheError("restored artifact exceeds object or byte cap", code="BYTE_LIMIT_EXCEEDED")
            chunks = state.get("chunks")
            if not isinstance(chunks, list) or len(chunks) > 1024:
                raise CacheError("invalid bounded partial chunk list", code="INVALID_PARTIAL_STATE")
            for chunk in chunks:
                if not isinstance(chunk, dict) or set(chunk) != {"start", "end", "sha256"}:
                    raise CacheError("invalid partial chunk record", code="INVALID_PARTIAL_STATE")
                first, last = chunk["start"], chunk["end"]
                if (any(isinstance(n, bool) or not isinstance(n, int) for n in (first, last))
                        or first != offset or not first <= last <= end or last >= total):
                    raise CacheError("partial chunks must be a bounded contiguous prefix", code="INVALID_PARTIAL_STATE")
                _hash_value(chunk["sha256"], "partial chunk SHA")
                size = last - first + 1
                if offset - start + size > min(request.max_bytes, self.cache.max_bytes):
                    raise CacheError("restored partial prefix exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
                try:
                    body = _read_bounded(partial / (chunk["sha256"] + ".chunk"), size)
                except FileNotFoundError as error:
                    raise CacheError("committed partial chunk is missing", code="INVALID_PARTIAL_STATE") from error
                if len(body) != last - first + 1 or sha256(body) != chunk["sha256"]:
                    raise CacheError("partial chunk size/SHA mismatch", code="CORRUPT_PARTIAL_CHUNK")
                pieces.append(body)
                offset = last + 1
            if sum(map(len, pieces)) > request.max_bytes:
                raise CacheError("partial artifact exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
        if end is not None and end - start + 1 > min(request.max_bytes, self.cache.max_bytes):
            raise CacheError("requested artifact exceeds hard byte cap", code="BYTE_LIMIT_EXCEEDED")
        try:
            while end is None or offset <= end:
                self._remaining(budget)
                if len(chunks) >= 1024:
                    raise CacheError("bounded chunk count exceeded", code="CHUNK_LIMIT_EXCEEDED")
                # Unknown whole-object size is discovered through one exact byte.
                last = offset if end is None else min(end, offset + self.chunk_bytes - 1)
                chunk_request = replace(request, max_bytes=last - offset + 1,
                                        expected_sha256=None, byte_range=(offset, last),
                                        expected_etag=anchor, total_object_bytes=total)
                chunk_request.validate()
                response = self._response(chunk_request, budget)
                actual_etag, actual_total = self._validate_response(chunk_request, response, require_strong_etag=True)
                if total is not None and total != actual_total:
                    raise CacheError("object size changed during resume", code="OBJECT_SIZE_CHANGED", status="version_changed")
                total, anchor = actual_total, actual_etag
                if end is None:
                    end = total - 1
                if end >= total or end - start + 1 > min(request.max_bytes, self.cache.max_bytes):
                    raise CacheError("resolved artifact exceeds object or byte cap", code="BYTE_LIMIT_EXCEEDED")
                if (end - start + 1 + self.chunk_bytes - 1) // self.chunk_bytes + 1 > 1024:
                    raise CacheError("bounded chunk count exceeded", code="CHUNK_LIMIT_EXCEEDED")
                digest = sha256(response.body)
                _atomic_write(partial / (digest + ".chunk"), response.body, immutable=True)
                chunks.append({"start": offset, "end": last, "sha256": digest})
                pieces.append(response.body)
                state = {"schema": "ASTRA_RANGE_CHUNKS_V1", "request": key.descriptor(),
                         "objectBytes": total, "etag": anchor, "chunks": chunks}
                _atomic_write(partial / "state.json", _canonical(state))
                offset = last + 1
            body = b"".join(pieces)
            if len(body) != end - start + 1 or len(body) > request.max_bytes:
                raise CacheError("assembled artifact length mismatch", code="RESPONSE_SIZE_MISMATCH")
            receipt = self._receipt(request, body, anchor, resumed=resumed)
            return body, receipt, resumed
        except CacheError as error:
            if state is not None and (error.status == "version_changed" or error.code == "CHECKSUM_MISMATCH"):
                state["invalid"] = error.code
                _atomic_write(partial / "state.json", _canonical(state))
            raise

    def fetch(self, request, *, resume=False):
        """Return a receipt; failures have neither successful bytes nor a hash.

        max_bytes bounds the requested artifact, including a narrow range from a
        much larger object. SourceSpec/provider success must still parse/check the
        bytes against their pinned source metadata and license conditions.
        """
        budget = {"deadline": self.clock() + self.duration, "retries": 0, "attempts": 0}
        try:
            if not isinstance(request, DownloadRequest) or not isinstance(resume, bool):
                raise CacheError("invalid download request/resume flag")
            _validate_url(request.url)
            key = CacheRequest.from_download(request)
            if request.byte_range is None and request.total_object_bytes is not None and request.total_object_bytes > request.max_bytes:
                raise CacheError("whole source object exceeds response byte cap", code="BYTE_LIMIT_EXCEEDED")
            with self.cache._lock(self.cache._lock_name(key), deadline=budget["deadline"], clock=self.clock, sleep=self.sleep):
                self._remaining(budget)
                entry = self.cache._get(key, "raw")
                if entry is None and request.expected_sha256 is not None:
                    blob = self.cache.root / "blobs" / "raw" / (request.expected_sha256 + ".bin")
                    if blob.exists():
                        existing = _read_bounded(blob, min(request.max_bytes, self.cache.max_bytes))
                        if not existing:
                            raise CacheError("cached download artifact is empty", code="EMPTY_RESPONSE")
                        receipt = self._receipt(request, existing, None)
                        receipt["reuseOrigin"] = "verified_content_hash"
                        entry = self.cache._put(key, existing, "raw", source_sha=request.expected_sha256, metadata=receipt)
                if entry is not None:
                    if not entry.data:
                        raise CacheError("cached download artifact is empty", code="EMPTY_RESPONSE")
                    if len(entry.data) > request.max_bytes:
                        raise CacheError("cached artifact exceeds request byte cap", code="BYTE_LIMIT_EXCEEDED")
                    if ((request.byte_range is not None and len(entry.data) != request.byte_range[1] - request.byte_range[0] + 1)
                            or (request.byte_range is None and request.total_object_bytes is not None
                                and len(entry.data) != request.total_object_bytes)):
                        raise CacheError("cached artifact differs from requested interval/size", code="RESPONSE_SIZE_MISMATCH")
                    return DownloadResult("available", entry.data, entry.sha256,
                                          entry.metadata.get("checksumOrigin", "provided_expected_sha256" if request.expected_sha256
                                                             else "self_computed_at_download"),
                                          entry.metadata.get("etag"), True, False, 0)
                if resume:
                    body, receipt, resumed = self._resume(request, key, budget)
                else:
                    response = self._response(request, budget)
                    etag, _ = self._validate_response(request, response)
                    body, resumed = response.body, False
                    receipt = self._receipt(request, body, etag)
                self._remaining(budget)
                entry = self.cache._put(key, body, "raw", source_sha=receipt["responseSha256"], metadata=receipt)
                return DownloadResult("available", entry.data, entry.sha256, receipt["checksumOrigin"],
                                      receipt["etag"], False, resumed, budget["attempts"])
        except CacheError as error:
            return DownloadResult(error.status, attempts=budget["attempts"],
                                  error={"code": error.code, "message": str(error)})
        except (DataError, ValueError, TypeError, OSError) as error:
            # Never serialize transport exception strings, URLs or auth headers.
            return DownloadResult("invalid_data", attempts=budget["attempts"],
                                  error={"code": "ACQUISITION_OR_CACHE_FAILURE", "message": type(error).__name__})
