"""Cache identities, integrity, lossless exchange and process-safe single flight."""
from dataclasses import replace
from http.client import IncompleteRead
import json
import multiprocessing
import os
from pathlib import Path
from queue import Queue
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import ssl
from urllib.request import HTTPSHandler, OpenerDirector, ProxyHandler

import numpy as np

import astra_cpu.cache as cache_module
from astra_cpu.cache import CacheEntry, CacheError, CacheRequest, DownloadManager, DownloadResult, FileCache
from astra_cpu.download_contract import DownloadRequest, DownloadResponse
from astra_cpu.model import DataError, RasterData, sha256


RAW = b"original provider bytes\x00\xff\n"
RAW_SHA = sha256(RAW)
METADATA_SHA = sha256(b"sidecars and mean-sea-level datum evidence")
DOWNLOAD_BODY = bytes(range(23))


def download_request(**overrides):
    fields = dict(url="https://example.invalid/object", source_id="download-source", source_version="v1",
                  max_bytes=64, expected_sha256=sha256(DOWNLOAD_BODY), source_metadata_sha256=METADATA_SHA)
    fields.update(overrides)
    return DownloadRequest(**fields)


class RangeTransport:
    def __init__(self, *, fail_at=None, headers=None, status=206):
        self.calls = []
        self.fail_at, self.extra_headers, self.status = fail_at, headers or {}, status

    def __call__(self, request, *, headers, timeout, deadline):
        first, last = request.byte_range
        self.calls.append((first, last, dict(headers), request.expected_sha256))
        if first == self.fail_at:
            raise TimeoutError("interrupted response bytes must never be appended")
        response_headers = {"ETag": '"v1"', "Content-Range": f"bytes {first}-{last}/{len(DOWNLOAD_BODY)}"}
        response_headers.update(self.extra_headers)
        return DownloadResponse(self.status, response_headers, DOWNLOAD_BODY[first:last + 1])


def _process_resume_worker(root, interrupted, results):
    transport = RangeTransport(fail_at=6 if interrupted else None)
    manager = DownloadManager(FileCache(root), transport=transport, chunk_bytes=5, max_retries=0)
    result = manager.fetch(download_request(expected_etag='"v1"'), resume=True)
    results.put((result.status, result.body, result.response_sha256, result.resumed,
                 [(first, last) for first, last, _, _ in transport.calls]))


def _process_slot_worker(root, identity, ready, start, results, active, peak):
    try:
        def transport(*args, **kwargs):
            with active.get_lock():
                active.value += 1
                with peak.get_lock():
                    peak.value = max(peak.value, active.value)
            try:
                time.sleep(.08)
                return DownloadResponse(200, {}, DOWNLOAD_BODY)
            finally:
                with active.get_lock():
                    active.value -= 1

        manager = DownloadManager(FileCache(root), transport=transport)
        ready.put(True)
        if not start.wait(30):
            raise RuntimeError("slot worker start deadline")
        result = manager.fetch(download_request(url=f"https://example.invalid/{identity}", expected_sha256=None))
        results.put((result.status, result.body))
    except Exception as error:
        results.put(("error", type(error).__name__))


def _fork_lock_worker(root, results):
    results.put(("ready", None))
    try:
        entry = FileCache(root).get_or_create_raw(cache_request(), lambda: b"must not run")
        results.put(("ok", entry.data))
    except Exception as error:
        results.put(("error", type(error).__name__))


class FakeClock:
    def __init__(self):
        self.now = 0.
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, value):
        self.waits.append(value)
        self.now += value


class FakeHTTPStream:
    def __init__(self, *, status=200, body=DOWNLOAD_BODY, headers=None, clock=None, read_seconds=0):
        self.status, self.headers, self.body = status, headers or {}, body
        self.clock, self.read_seconds, self.position = clock, read_seconds, 0
        self.timeouts = []
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
        self.closed = False

    def read1(self, maximum):
        if self.clock is not None:
            self.clock.now += self.read_seconds
        piece = self.body[self.position:self.position + min(maximum, 8)]
        self.position += len(piece)
        return piece

    def close(self):
        self.closed = True
        self.fp = None


def cache_request(**overrides):
    fields = dict(source_id="synthetic-source", source_version="release-2026",
                  bbox=(0, 0, 2, 1), crs="EPSG:4326",
                  resolution={"units": "degree", "spacing": [1, 1], "policy": "native"},
                  source_sha256=RAW_SHA, source_metadata_sha256=METADATA_SHA)
    fields.update(overrides)
    return CacheRequest(**fields)


def raster_fixture(**metadata_overrides):
    metadata = {"transform": [0., 1., 0., 1., 0., -1.], "crs": "EPSG:4326",
                "inputSha256": RAW_SHA, "verticalDatum": "MEAN_SEA_LEVEL_ASSUMPTION",
                "horizontalUnits": "degree", "nodata": float("nan"),
                "originalColorProfile": b"binary metadata\x00\xff"}
    metadata.update(metadata_overrides)
    return RasterData(np.array([[np.nan, -2124.]], dtype=np.float32),
                      [.5, 1.5], [.5], [[False, True]], metadata)


def _process_singleflight_worker(root, ready, start, results, counter):
    """Spawned workers create fresh cache/lock state rather than inheriting FDs."""
    try:
        cache = FileCache(root)
        request = cache_request()
        ready.put(True)
        if not start.wait(30):
            raise RuntimeError("single-flight start deadline exceeded")

        def produce():
            with counter.get_lock():
                counter.value += 1
            time.sleep(.12)
            return RAW

        entry = cache.get_or_create_raw(request, produce)
        results.put(("ok", entry.data, entry.sha256, entry.key))
    except Exception as error:
        results.put(("error", type(error).__name__, str(error)))


class CacheRequestTests(unittest.TestCase):
    def test_cache_error_is_a_data_error(self):
        self.assertTrue(issubclass(CacheError, DataError))

    def test_each_source_and_transform_identity_dimension_changes_the_key(self):
        request = cache_request()
        variations = {
            "source_id": "another-provider",
            "source_version": "release-2027",
            "bbox": (0, 0, 1, 1),
            "crs": "EPSG:4269",
            "resolution": {"units": "degree", "spacing": [.5, .5], "policy": "native"},
            "source_sha256": sha256(b"changed source bytes"),
            "transform_version": "NEUTRAL_PARSE_V2",
            "source_metadata_sha256": sha256(b"different sidecars or vertical datum"),
            "url_sha256": sha256(b"https://example.invalid/different-object"),
            "byte_range": (1, 4),
        }
        keys = {request.lookup_key()}
        for field, value in variations.items():
            with self.subTest(field=field):
                changed = replace(request, **{field: value})
                changed.validate()
                self.assertNotEqual(changed.lookup_key(), request.lookup_key())
                keys.add(changed.lookup_key())
        self.assertEqual(len(keys), len(variations) + 1)

    def test_canonical_dictionary_order_and_unrounded_coordinates(self):
        first = cache_request(resolution={"policy": "native", "spacing": [1, 1], "units": "degree"})
        second = cache_request(resolution={"units": "degree", "spacing": [1, 1], "policy": "native"})
        self.assertEqual(first.lookup_key(), second.lookup_key())
        self.assertEqual(first.resolved_key(RAW_SHA), second.resolved_key(RAW_SHA))
        self.assertNotEqual(first.lookup_key(), replace(first, bbox=(1e-12, 0, 2, 1)).lookup_key())

    def test_dateline_request_identity_preserves_west_east_order(self):
        crossing = cache_request(bbox=(175, -1, -175, 1))
        crossing.validate()
        self.assertNotEqual(crossing.lookup_key(), cache_request(bbox=(-175, -1, 175, 1)).lookup_key())

    def test_download_handoff_retains_pinned_identity_and_hashes_url(self):
        download = DownloadRequest(
            "https://example.invalid/source?part=one", "source", "v1", 64,
            expected_sha256=RAW_SHA, byte_range=(2, 5), expected_etag='"object-v1"',
            bbox=(0, 0, 2, 1), crs="EPSG:4326", resolution={"units": "m", "value": 30},
            source_metadata_sha256=METADATA_SHA, total_object_bytes=100)
        request = CacheRequest.from_download(download)
        request.validate()
        self.assertEqual(request.source_id, download.source_id)
        self.assertEqual(request.source_version, download.source_version)
        self.assertEqual(request.source_sha256, RAW_SHA)
        self.assertEqual(request.source_metadata_sha256, METADATA_SHA)
        self.assertEqual(request.url_sha256, sha256(download.url.encode()))
        self.assertEqual(tuple(request.byte_range), (2, 5))
        self.assertEqual(request.expected_etag, '"object-v1"')
        self.assertEqual(request.total_object_bytes, 100)
        self.assertEqual(request.crs, download.crs)
        self.assertEqual(request.resolution, download.resolution)

    def test_unknown_source_hash_requires_a_stable_lookup_identity(self):
        with self.assertRaises(CacheError):
            cache_request(source_sha256=None, source_metadata_sha256=None).validate()
        for stable_identity in ({"source_metadata_sha256": METADATA_SHA},
                                {"source_metadata_sha256": None, "url_sha256": sha256(b"source URL")}):
            with self.subTest(stable_identity=stable_identity):
                request = cache_request(source_sha256=None, **stable_identity)
                request.validate()
                self.assertEqual(request.resolved_key(RAW_SHA),
                                 replace(request, source_sha256=RAW_SHA).resolved_key(RAW_SHA))
                self.assertNotEqual(request.resolved_key(RAW_SHA), request.resolved_key(sha256(b"other bytes")))

    def test_malformed_and_nonfinite_identity_fields_fail_before_caching(self):
        invalid = [
            {"source_id": ""}, {"source_version": ""}, {"crs": ""},
            {"transform_version": ""}, {"source_sha256": "bad"},
            {"source_metadata_sha256": "g" * 64}, {"url_sha256": "bad"},
            {"bbox": (0, 0, 0, 1)}, {"bbox": (0, 0, 1, float("nan"))},
            {"bbox": (False, 0, 1, 1)}, {"resolution": float("inf")},
            {"resolution": {"spacing": [1, float("nan")]}},
            {"resolution": {1: "ambiguous non-string dictionary key"}},
            {"resolution": object()}, {"byte_range": (-1, 2)},
            {"byte_range": (True, 2)}, {"byte_range": (3, 2)},
            {"total_object_bytes": 0}, {"total_object_bytes": True},
            {"byte_range": (0, 4), "total_object_bytes": 4},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(CacheError):
                cache_request(**changes).validate()


class RawCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-cache-tests-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.cache = FileCache(Path(self.temp.name) / "cache")
        self.request = cache_request()

    def lookup(self, request=None, kind="raw"):
        return self.cache.root / "lookups" / kind / ((request or self.request).lookup_key() + ".json")

    def blob(self, digest=RAW_SHA, kind="raw"):
        return self.cache.root / "blobs" / kind / (digest + ".bin")

    def test_miss_and_exact_raw_roundtrip_survive_new_cache_instance(self):
        self.assertIsNone(self.cache.get_raw(self.request))
        entry = self.cache.put_raw(self.request, RAW, receipt_metadata={"etag": '"object-v1"'})
        self.assertIsInstance(entry, CacheEntry)
        self.assertEqual(entry.data, RAW)
        self.assertEqual(entry.sha256, RAW_SHA)
        self.assertEqual(entry.actual_sha256, RAW_SHA)
        self.assertEqual(entry.key, self.request.resolved_key(RAW_SHA))
        reopened = FileCache(self.cache.root).get_raw(self.request)
        self.assertEqual(reopened.data, RAW)
        self.assertEqual(reopened.sha256, RAW_SHA)
        self.assertEqual(reopened.key, entry.key)
        self.assertEqual(reopened.metadata, entry.metadata)

    def test_unknown_source_hash_resolves_to_verified_content_identity(self):
        request = replace(self.request, source_sha256=None)
        entry = self.cache.put_raw(request, RAW)
        self.assertEqual(entry.sha256, RAW_SHA)
        self.assertEqual(entry.key, request.resolved_key(RAW_SHA))
        self.assertEqual(FileCache(self.cache.root).get_raw(request).data, RAW)

    def test_distinct_version_and_sidecar_datum_metadata_are_cache_misses(self):
        self.cache.put_raw(self.request, RAW)
        for request in (replace(self.request, source_version="v2"),
                        replace(self.request, source_metadata_sha256=sha256(b"new datum and PGW")),
                        replace(self.request, bbox=(0, 0, 1, 1)),
                        replace(self.request, resolution={"units": "degree", "spacing": [.5, .5]})):
            with self.subTest(request=request):
                self.assertIsNone(self.cache.get_raw(request))

    def test_known_source_hash_mismatch_is_not_published(self):
        with self.assertRaises(CacheError):
            self.cache.put_raw(self.request, b"wrong raw source")
        self.assertIsNone(self.cache.get_raw(self.request))
        self.assertFalse(self.lookup().exists())

    def test_hard_byte_bound_rejects_oversized_raw_before_publication(self):
        bounded = FileCache(self.cache.root, max_bytes=len(RAW) - 1)
        with self.assertRaises(CacheError):
            bounded.put_raw(self.request, RAW)
        self.assertIsNone(self.cache.get_raw(self.request))

    def test_blob_digest_corruption_is_rejected_and_not_implicitly_repaired(self):
        self.cache.put_raw(self.request, RAW)
        corrupt = bytes([RAW[0] ^ 1]) + RAW[1:]
        self.blob().write_bytes(corrupt)
        with self.assertRaises(CacheError):
            FileCache(self.cache.root).get_raw(self.request)
        self.assertEqual(self.blob().read_bytes(), corrupt)

    def test_invalid_manifest_json_is_corruption_rather_than_a_miss(self):
        self.cache.put_raw(self.request, RAW)
        self.lookup().write_bytes(b'{"incomplete":')
        with self.assertRaises(CacheError):
            self.cache.get_raw(self.request)

    def test_well_formed_manifest_for_another_request_is_rejected(self):
        other = replace(self.request, source_version="different-release")
        self.cache.put_raw(self.request, RAW)
        self.cache.put_raw(other, RAW)
        self.lookup().write_bytes(self.lookup(other).read_bytes())
        with self.assertRaises(CacheError):
            self.cache.get_raw(self.request)

    def test_manifest_referencing_missing_blob_is_corruption(self):
        self.cache.put_raw(self.request, RAW)
        self.blob().unlink()
        with self.assertRaises(CacheError):
            self.cache.get_raw(self.request)

    def test_failed_update_preserves_previous_valid_entry(self):
        self.cache.put_raw(self.request, RAW)
        manifest = self.lookup().read_bytes()
        with self.assertRaises(CacheError):
            self.cache.put_raw(self.request, b"mismatched replacement")
        self.assertEqual(self.lookup().read_bytes(), manifest)
        self.assertEqual(self.cache.get_raw(self.request).data, RAW)

    def test_corrupt_existing_immutable_blob_is_not_overwritten_by_another_key(self):
        self.cache.put_raw(self.request, RAW)
        corrupt = b"!" + RAW[1:]
        self.blob().write_bytes(corrupt)
        other = replace(self.request, source_version="v2")
        with self.assertRaises(CacheError):
            self.cache.put_raw(other, RAW)
        self.assertEqual(self.blob().read_bytes(), corrupt)
        self.assertFalse(self.lookup(other).exists())

    def test_orphan_blob_without_committed_pointer_is_not_a_hit(self):
        self.blob().parent.mkdir(parents=True, exist_ok=True)
        self.blob().write_bytes(RAW)
        self.assertIsNone(self.cache.get_raw(self.request))

    def test_failed_producer_is_not_cached_and_next_attempt_can_succeed(self):
        calls = []

        def fail():
            calls.append("failed")
            raise RuntimeError("producer declined")

        with self.assertRaisesRegex(Exception, "producer declined"):
            self.cache.get_or_create_raw(self.request, fail)
        self.assertEqual(calls, ["failed"])
        self.assertIsNone(self.cache.get_raw(self.request))
        entry = self.cache.get_or_create_raw(self.request, lambda: RAW)
        self.assertEqual(entry.data, RAW)
        cached = self.cache.get_or_create_raw(self.request,
                                             lambda: self.fail("cache hit must not invoke producer"))
        self.assertEqual(cached.data, RAW)

    def test_threads_using_independent_cache_instances_share_one_raw_producer(self):
        workers = 8
        barrier = threading.Barrier(workers)
        counter_lock = threading.Lock()
        counter = [0]
        results = Queue()

        def produce():
            with counter_lock:
                counter[0] += 1
            time.sleep(.08)
            return RAW

        def worker():
            try:
                cache = FileCache(self.cache.root)
                barrier.wait(timeout=10)
                entry = cache.get_or_create_raw(self.request, produce)
                results.put(("ok", entry.data, entry.sha256))
            except Exception as error:
                results.put(("error", type(error).__name__, str(error)))

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + 10
        for thread in threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        self.assertFalse(any(thread.is_alive() for thread in threads), "cache thread lock deadlocked")
        outputs = [results.get(timeout=1) for _ in range(workers)]
        self.assertEqual(outputs, [("ok", RAW, RAW_SHA)] * workers)
        self.assertEqual(counter[0], 1)

    def test_spawned_processes_share_one_raw_producer_and_fresh_cache_state(self):
        context = multiprocessing.get_context("spawn")
        ready, results = context.Queue(), context.Queue()
        start, counter = context.Event(), context.Value("i", 0)
        workers = [context.Process(target=_process_singleflight_worker,
                                   args=(str(self.cache.root), ready, start, results, counter))
                   for _ in range(4)]
        try:
            for worker in workers:
                worker.start()
            for _ in workers:
                self.assertTrue(ready.get(timeout=20))
            start.set()
            outputs = [results.get(timeout=20) for _ in workers]
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0, "cache process did not exit cleanly")
            expected = ("ok", RAW, RAW_SHA, self.request.resolved_key(RAW_SHA))
            self.assertEqual(outputs, [expected] * len(workers))
            self.assertEqual(counter.value, 1)
            self.assertEqual(FileCache(self.cache.root).get_raw(self.request).data, RAW)
        finally:
            start.set()
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                if worker.pid is not None:
                    worker.join(timeout=5)
            ready.close()
            results.close()


class DerivedCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-derived-cache-tests-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.cache = FileCache(Path(self.temp.name) / "cache")
        self.request = cache_request(transform_version="NEUTRAL_PARSE_V1")
        self.raster = raster_fixture()

    def test_neutral_roundtrip_keeps_dtype_bits_boolean_mask_and_source_provenance(self):
        self.assertIsNone(self.cache.get_derived(self.request))
        entry = self.cache.put_derived(self.request, self.raster)
        self.assertEqual(entry.sha256, sha256(entry.data))
        self.assertNotEqual(entry.sha256, RAW_SHA)
        self.assertEqual(entry.key, self.request.resolved_key(RAW_SHA))
        decoded = FileCache(self.cache.root).get_derived(self.request)
        self.assertIsInstance(decoded, RasterData)
        self.assertEqual(decoded.values.dtype, np.float32)
        np.testing.assert_array_equal(decoded.values.view(np.uint32), self.raster.values.view(np.uint32))
        np.testing.assert_array_equal(decoded.x, self.raster.x)
        np.testing.assert_array_equal(decoded.y, self.raster.y)
        np.testing.assert_array_equal(decoded.valid, self.raster.valid)
        self.assertEqual(decoded.valid.dtype, np.bool_)
        self.assertFalse(decoded.values.flags.writeable)
        self.assertFalse(decoded.valid.flags.writeable)
        self.assertEqual(decoded.metadata["inputSha256"], RAW_SHA)
        self.assertEqual(decoded.metadata["crs"], self.request.crs)
        self.assertEqual(decoded.metadata["verticalDatum"], self.raster.metadata["verticalDatum"])
        self.assertEqual(decoded.metadata["originalColorProfile"], b"binary metadata\x00\xff")
        self.assertTrue(np.isnan(decoded.metadata["nodata"]))

    def test_missing_wrong_source_sha_and_crs_are_rejected_before_publication(self):
        cases = [(replace(self.request, source_sha256=None), self.raster),
                 (self.request, raster_fixture(inputSha256=sha256(b"another source"))),
                 (self.request, raster_fixture(crs="EPSG:4269")),
                 (replace(self.request, crs="EPSG:4269"), self.raster)]
        for request, raster in cases:
            with self.subTest(request=request, crs=raster.metadata["crs"]), self.assertRaises(CacheError):
                self.cache.put_derived(request, raster)
        self.assertIsNone(self.cache.get_derived(self.request))

    def test_transform_resolution_bbox_and_metadata_changes_do_not_reuse_derived_entry(self):
        self.cache.put_derived(self.request, self.raster)
        changes = [{"transform_version": "NEUTRAL_PARSE_V2"},
                   {"source_metadata_sha256": sha256(b"other sidecars and vertical datum")},
                   {"resolution": {"units": "degree", "spacing": [.5, .5]}},
                   {"bbox": (0, 0, 1, 1)}]
        for fields in changes:
            with self.subTest(fields=fields):
                self.assertIsNone(self.cache.get_derived(replace(self.request, **fields)))

    def test_corrupt_neutral_blob_is_rejected_before_decoding_as_a_cache_hit(self):
        entry = self.cache.put_derived(self.request, self.raster)
        blob = self.cache.root / "blobs" / "derived" / (entry.sha256 + ".bin")
        original = blob.read_bytes()
        blob.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaises(CacheError):
            FileCache(self.cache.root).get_derived(self.request)

    def test_neutral_artifact_obeys_serialized_byte_limit(self):
        bounded = FileCache(self.cache.root, max_bytes=8)
        with self.assertRaises(CacheError):
            bounded.put_derived(self.request, self.raster)
        self.assertIsNone(self.cache.get_derived(self.request))


class CacheHardeningTests(unittest.TestCase):
    setUp = RawCacheTests.setUp
    lookup = RawCacheTests.lookup
    blob = RawCacheTests.blob

    def test_create_false_absent_cache_returns_misses_without_creating_directories(self):
        root = Path(self.temp.name) / "absent" / "cache"
        with patch.object(Path, "mkdir", side_effect=AssertionError("read-only construction cannot mkdir")):
            cache = FileCache(root, create=False)
            self.assertIsNone(cache.get_raw(self.request))
            self.assertIsNone(cache.get_derived(replace(self.request, transform_version="PARSE_V1")))
        self.assertFalse(root.parent.exists())

    def test_create_false_incomplete_cache_preserves_existing_directory_contents(self):
        root = Path(self.temp.name) / "incomplete-cache"
        root.mkdir()
        marker = root / "retained.txt"
        marker.write_bytes(b"user-created existing marker")
        with patch.object(Path, "mkdir", side_effect=AssertionError("no missing cache directories may be created")):
            cache = FileCache(root, create=False)
            self.assertIsNone(cache.get_raw(self.request))
        self.assertEqual(list(root.iterdir()), [marker])
        self.assertEqual(marker.read_bytes(), b"user-created existing marker")

    def test_create_false_reads_existing_raw_and_derived_cache_without_initialization(self):
        self.cache.put_raw(self.request, RAW)
        derived = replace(self.request, transform_version="PARSE_V1")
        self.cache.put_derived(derived, raster_fixture())
        before = {path.relative_to(self.cache.root) for path in self.cache.root.rglob("*")}
        with patch.object(Path, "mkdir", side_effect=AssertionError("existing-cache reads cannot mkdir")):
            cache = FileCache(self.cache.root, create=False)
            self.assertEqual(cache.get_raw(self.request).data, RAW)
            np.testing.assert_array_equal(cache.get_derived(derived).values, raster_fixture().values)
        self.assertEqual(before, {path.relative_to(self.cache.root) for path in self.cache.root.rglob("*")})

    def test_create_flag_rejects_truthy_non_boolean_values(self):
        for value in (1, "false", None):
            with self.subTest(value=value), self.assertRaises(CacheError):
                FileCache(Path(self.temp.name) / "bad-create", create=value)

    def test_threads_sharing_one_cache_instance_are_singleflight(self):
        barrier, calls, results = threading.Barrier(6), [], Queue()

        def produce():
            calls.append(True)
            time.sleep(.04)
            return RAW

        def worker():
            try:
                barrier.wait(timeout=5)
                results.put(self.cache.get_or_create_raw(self.request, produce).data)
            except Exception as error:
                results.put(type(error).__name__)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(6)]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + 5
        for thread in threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual([results.get(timeout=1) for _ in threads], [RAW] * 6)
        self.assertEqual(len(calls), 1)

    def test_forked_child_resets_thread_locks_and_closes_inherited_lock_fds(self):
        context = multiprocessing.get_context("fork")
        entered, release, outputs = threading.Event(), threading.Event(), Queue()

        def producer():
            entered.set()
            if not release.wait(10):
                raise RuntimeError("parent producer release deadline")
            return RAW

        def parent_thread():
            try:
                outputs.put(self.cache.get_or_create_raw(self.request, producer).data)
            except Exception as error:
                outputs.put(type(error).__name__)

        thread = threading.Thread(target=parent_thread, daemon=True)
        thread.start()
        self.assertTrue(entered.wait(5))
        results = context.Queue()
        child = context.Process(target=_fork_lock_worker, args=(str(self.cache.root), results))
        try:
            child.start()
            self.assertEqual(results.get(timeout=5), ("ready", None))
            release.set()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(outputs.get(timeout=1), RAW)
            self.assertEqual(results.get(timeout=5), ("ok", RAW))
            child.join(timeout=5)
            self.assertEqual(child.exitcode, 0)
        finally:
            release.set()
            if child.is_alive():
                child.terminate()
            if child.pid is not None:
                child.join(timeout=5)
            results.close()
    def test_pointer_replace_failure_keeps_previous_committed_artifact(self):
        request = replace(self.request, source_sha256=None)
        self.cache.put_raw(request, RAW)
        path = self.lookup(request)
        previous = path.read_bytes()
        real_replace = cache_module.os.replace

        def fail_pointer(source, destination):
            if Path(destination) == path:
                raise OSError("simulated manifest publication failure")
            return real_replace(source, destination)

        with patch.object(cache_module.os, "replace", side_effect=fail_pointer), self.assertRaises(OSError):
            self.cache.put_raw(request, b"new complete but uncommitted bytes")
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(FileCache(self.cache.root).get_raw(request).data, RAW)

    def test_fifo_corruption_fails_without_waiting_for_a_writer(self):
        self.cache.put_raw(self.request, RAW)
        self.blob().unlink()
        os.mkfifo(self.blob())
        with self.assertRaises(CacheError):
            self.cache.get_raw(self.request)

    def test_recursive_producer_fails_without_lock_deadlock(self):
        with self.assertRaisesRegex(CacheError, "recursive"):
            self.cache.get_or_create_raw(self.request,
                                         lambda: self.cache.get_or_create_raw(self.request, lambda: RAW).data)

    def test_declared_artifact_lengths_are_checked_before_raw_publication(self):
        for request in (replace(self.request, total_object_bytes=len(RAW) + 1),
                        replace(self.request, byte_range=(0, 2))):
            with self.subTest(request=request), self.assertRaises(CacheError):
                self.cache.put_raw(request, RAW)
            self.assertFalse(self.lookup(request).exists())

    def test_derived_center_support_and_auxiliary_metadata_identity_are_required(self):
        request = cache_request(transform_version="PARSE_V1")
        for invalid in (replace(request, bbox=(0, 0, 1, 1)),
                        replace(request, source_metadata_sha256=None)):
            with self.subTest(request=invalid), self.assertRaises(CacheError):
                self.cache.put_derived(invalid, raster_fixture())
        # Pixel edges can extend beyond requested edges when their centers fit.
        self.cache.put_derived(replace(request, bbox=(.1, .1, 1.9, .9)), raster_fixture())

    def test_derived_same_identity_cannot_change_sidecars_or_datum(self):
        request = cache_request(transform_version="PARSE_V1")
        self.cache.put_derived(request, raster_fixture(sidecarSha256={"worldfile": RAW_SHA}))
        with self.assertRaises(CacheError):
            self.cache.put_derived(request, raster_fixture(sidecarSha256={"worldfile": METADATA_SHA}))


class DownloadManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="astra-download-tests-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.cache = FileCache(Path(self.temp.name) / "cache")

    def test_verified_download_and_metadata_lookup_hit_do_not_repeat_transport(self):
        calls = []

        def transport(request, **options):
            calls.append(request)
            return DownloadResponse(200, {"ETag": '"v1"', "Content-Length": str(len(DOWNLOAD_BODY))}, DOWNLOAD_BODY)

        manager = DownloadManager(self.cache, transport=transport)
        request = download_request(expected_sha256=None, expected_etag='"v1"')
        first, second = manager.fetch(request), manager.fetch(request)
        self.assertEqual(first.status, "available")
        self.assertEqual(first.response_sha256, sha256(DOWNLOAD_BODY))
        self.assertEqual(first.checksum_origin, "self_computed_at_download")
        self.assertEqual(first.etag, '"v1"')
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.body, DOWNLOAD_BODY)
        self.assertEqual(len(calls), 1)
        entry = self.cache.get_raw(CacheRequest.from_download(request))
        self.assertEqual(entry.key, CacheRequest.from_download(request).resolved_key(sha256(DOWNLOAD_BODY)))

    def test_existing_exact_source_blob_is_reused_without_network_claims(self):
        self.cache.put_raw(cache_request(source_sha256=sha256(DOWNLOAD_BODY)), DOWNLOAD_BODY)
        request = download_request(expected_etag='"unobserved-pin"')
        result = DownloadManager(self.cache).fetch(request)
        self.assertEqual(result.status, "available")
        self.assertTrue(result.cache_hit)
        self.assertIsNone(result.etag)
        entry = self.cache.get_raw(CacheRequest.from_download(request))
        self.assertEqual(entry.metadata["reuseOrigin"], "verified_content_hash")

    def test_cached_receipt_contradictions_are_corruption_not_success(self):
        request = download_request(expected_etag='"v1"')
        manager = DownloadManager(self.cache, transport=lambda *args, **kw:
                                  DownloadResponse(200, {"ETag": '"v1"'}, DOWNLOAD_BODY))
        self.assertEqual(manager.fetch(request).status, "available")
        path = self.cache.root / "lookups" / "raw" / (CacheRequest.from_download(request).lookup_key() + ".json")
        original = path.read_bytes()
        changes = {"responseSha256": RAW_SHA, "sourceVersion": "wrong-version",
                   "sourceMetadataSha256": RAW_SHA, "byteRange": [1, 2],
                   "checksumOrigin": "self_computed_at_download", "etag": '"wrong"'}
        for field, value in changes.items():
            with self.subTest(field=field):
                manifest = json.loads(original)
                manifest["metadata"][field] = value
                path.write_text(json.dumps(manifest))
                result = manager.fetch(request)
                self.assertEqual(result.status, "invalid_data")
                self.assertIsNone(result.body)
        path.write_bytes(original)

    def test_empty_cached_download_and_incompatible_blob_length_are_rejected(self):
        empty = download_request(expected_sha256=sha256(b""))
        self.cache.put_raw(CacheRequest.from_download(empty), b"")
        self.assertEqual(DownloadManager(self.cache).fetch(empty).status, "invalid_data")
        self.cache.put_raw(cache_request(source_sha256=sha256(DOWNLOAD_BODY)), DOWNLOAD_BODY)
        for request in (download_request(total_object_bytes=len(DOWNLOAD_BODY) + 1),
                        download_request(byte_range=(0, 2))):
            with self.subTest(request=request):
                result = DownloadManager(self.cache).fetch(request)
                self.assertEqual(result.status, "invalid_data")
                self.assertIsNone(self.cache.get_raw(CacheRequest.from_download(request)))

    def test_hash_mismatch_and_oversized_response_never_publish_success(self):
        for body in (b"incorrect bytes", b"x" * 65):
            with self.subTest(length=len(body)):
                result = DownloadManager(self.cache, transport=lambda *a, **k: DownloadResponse(200, {}, body)).fetch(download_request())
                self.assertEqual(result.status, "invalid_data")
                self.assertIsNone(result.body)
                self.assertIsNone(self.cache.get_raw(CacheRequest.from_download(download_request())))

    def test_stable_http_failures_are_not_retried_or_cached(self):
        for status, outcome in ((401, "auth_required"), (403, "auth_required"), (404, "unavailable"),
                                (410, "unavailable"), (400, "invalid_data"), (416, "invalid_data"),
                                (412, "version_changed")):
            calls = []

            def transport(*args, **kwargs):
                calls.append(status)
                return DownloadResponse(status, {}, b"")

            with self.subTest(status=status):
                result = DownloadManager(self.cache, transport=transport).fetch(download_request())
                self.assertEqual(result.status, outcome)
                self.assertEqual(len(calls), 1)
                self.assertIsNone(result.body)
                self.assertIsNone(result.response_sha256)

    def test_timeout_and_retryable_status_share_one_bounded_budget(self):
        clock, calls = FakeClock(), []

        def transport(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise TimeoutError("not retained")
            if len(calls) == 2:
                return DownloadResponse(503, {"Retry-After": "1"}, b"")
            return DownloadResponse(200, {}, DOWNLOAD_BODY)

        result = DownloadManager(self.cache, transport=transport, clock=clock, sleep=clock.sleep).fetch(download_request())
        self.assertEqual(result.status, "available")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(clock.waits), 2)
        self.assertGreaterEqual(clock.waits[1], 1)

    def test_retry_after_ceiling_or_deadline_never_retries_earlier(self):
        for retry_after, duration in (("11", 30), ("2", 1), ("Wed, 01 Jan 2100 00:00:00 GMT", 30)):
            clock, calls = FakeClock(), []

            def transport(*args, **kwargs):
                calls.append(True)
                return DownloadResponse(429, {"Retry-After": retry_after}, b"")

            with self.subTest(retry_after=retry_after):
                result = DownloadManager(self.cache, transport=transport, clock=clock,
                                         sleep=clock.sleep, deadline_seconds=duration).fetch(download_request())
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(len(calls), 1)
                self.assertEqual(clock.waits, [])

    def test_resume_exact_chunks_verify_final_hash_and_strip_inner_checksum(self):
        transport = RangeTransport()
        result = DownloadManager(self.cache, transport=transport, chunk_bytes=5).fetch(download_request(), resume=True)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.body, DOWNLOAD_BODY)
        self.assertEqual(transport.calls[0][:2], (0, 0))
        self.assertTrue(all(checksum is None for _, _, _, checksum in transport.calls))
        self.assertTrue(all(headers["If-Range"] == '"v1"' for _, _, headers, _ in transport.calls[1:]))

    def test_explicit_narrow_range_hashes_only_selected_bytes_of_large_object(self):
        request = download_request(byte_range=(6, 13), expected_sha256=sha256(DOWNLOAD_BODY[6:14]),
                                   total_object_bytes=len(DOWNLOAD_BODY), max_bytes=8)
        transport = RangeTransport()
        result = DownloadManager(self.cache, transport=transport, chunk_bytes=3).fetch(request, resume=True)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.body, DOWNLOAD_BODY[6:14])
        self.assertEqual(transport.calls[0][:2], (6, 8))
        self.assertEqual(transport.calls[-1][:2], (12, 13))

    def test_resumed_artifact_completes_in_a_fresh_process_without_redownloading_prefix(self):
        context = multiprocessing.get_context("spawn")
        results = context.Queue()
        workers = []
        try:
            for interrupted in (True, False):
                worker = context.Process(target=_process_resume_worker,
                                         args=(str(self.cache.root), interrupted, results))
                workers.append(worker)
                worker.start()
                result = results.get(timeout=20)
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0)
                if interrupted:
                    self.assertEqual(result[0], "unavailable")
                    self.assertIsNone(result[1])
                    self.assertEqual(result[4], [(0, 0), (1, 5), (6, 10)])
                else:
                    self.assertEqual(result[:4], ("available", DOWNLOAD_BODY, sha256(DOWNLOAD_BODY), True))
                    self.assertEqual(result[4][0], (6, 10))
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=5)
            results.close()

    def test_range_refusal_and_malformed_identity_never_append_or_succeed(self):
        cases = [(200, {}, "invalid_data"), (206, {"ETag": 'W/"v1"'}, "version_changed"),
                 (206, {"ETag": '"changed"'}, "version_changed"),
                 (206, {"Content-Range": "bytes 0-1/23"}, "invalid_data"),
                 (206, {"Content-Range": "bytes 0-0/*"}, "invalid_data"),
                 (206, {"Content-Range": "bytes 0-0/24"}, "version_changed"),
                 (206, {"Content-Encoding": "gzip"}, "invalid_data"),
                 (206, {"Content-Type": "multipart/byteranges"}, "invalid_data")]
        for index, (status, headers, expected) in enumerate(cases):
            with self.subTest(index=index):
                request = download_request(url=f"https://example.invalid/{index}", expected_etag='"v1"',
                                           total_object_bytes=len(DOWNLOAD_BODY))
                # One-byte chunks keep Content-Range corruption unambiguous.
                result = DownloadManager(self.cache, transport=RangeTransport(headers=headers, status=status),
                                         chunk_bytes=1).fetch(request, resume=True)
                self.assertEqual(result.status, expected)
                self.assertIsNone(result.body)
                self.assertIsNone(self.cache.get_raw(CacheRequest.from_download(request)))

    def test_partial_corruption_and_forged_oversized_state_fail_before_network_or_allocation(self):
        request = download_request(expected_etag='"v1"')
        manager = DownloadManager(self.cache, transport=RangeTransport(fail_at=6), chunk_bytes=5, max_retries=0)
        self.assertEqual(manager.fetch(request, resume=True).status, "unavailable")
        partial = self.cache.root / "partials" / CacheRequest.from_download(request).lookup_key()
        state_path = partial / "state.json"
        original = state_path.read_bytes()
        state = json.loads(original)
        state["objectBytes"] = 1000000000
        state_path.write_text(json.dumps(state))
        with patch.object(cache_module, "_read_bounded", wraps=cache_module._read_bounded) as read:
            result = manager.fetch(request, resume=True)
            self.assertEqual(result.status, "invalid_data")
            self.assertFalse(any(str(call.args[0]).endswith(".chunk") for call in read.call_args_list))
        state_path.write_bytes(original)
        state = json.loads(original)
        chunk = partial / (state["chunks"][0]["sha256"] + ".chunk")
        chunk.write_bytes(b"corrupt committed prefix")
        result = manager.fetch(request, resume=True)
        self.assertEqual(result.status, "invalid_data")

    def test_retry_budget_is_global_across_resume_chunks(self):
        clock, calls, transport = FakeClock(), [], RangeTransport()

        def flaky(request, **kwargs):
            calls.append(request.byte_range)
            if len(calls) % 2 == 1:
                return DownloadResponse(503, {}, b"")
            return transport(request, **kwargs)

        result = DownloadManager(self.cache, transport=flaky, chunk_bytes=5, max_retries=2,
                                 clock=clock, sleep=clock.sleep).fetch(download_request(), resume=True)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.attempts, 5)
        self.assertEqual(len(clock.waits), 2)

    def test_malformed_http_stream_and_fabricated_success_error_are_safe_failures(self):
        def truncated(*args, **kwargs):
            raise IncompleteRead(b"uncommitted partial bytes", 100)

        result = DownloadManager(self.cache, transport=truncated).fetch(download_request())
        self.assertEqual(result.status, "invalid_data")
        self.assertIsNone(result.body)

        def wrong_status(*args, **kwargs):
            raise CacheError("failure cannot be available", status="available")

        result = DownloadManager(self.cache, transport=wrong_status).fetch(download_request())
        self.assertEqual(result.status, "invalid_data")
        with self.assertRaises(CacheError):
            DownloadResult("available", body=None)

    def test_default_two_download_slots_are_shared_across_fresh_processes(self):
        context = multiprocessing.get_context("spawn")
        ready, results = context.Queue(), context.Queue()
        start, active, peak = context.Event(), context.Value("i", 0), context.Value("i", 0)
        workers = [context.Process(target=_process_slot_worker,
                                   args=(str(self.cache.root), index, ready, start, results, active, peak))
                   for index in range(4)]
        try:
            for worker in workers:
                worker.start()
            deadline = time.monotonic() + 15
            for _ in workers:
                self.assertTrue(ready.get(timeout=max(.1, deadline - time.monotonic())))
            start.set()
            deadline = time.monotonic() + 15
            self.assertEqual([results.get(timeout=max(.1, deadline - time.monotonic())) for _ in workers],
                             [("available", DOWNLOAD_BODY)] * 4)
            self.assertEqual(peak.value, 2)
            for worker in workers:
                worker.join(timeout=5)
                self.assertEqual(worker.exitcode, 0)
        finally:
            start.set()
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                if worker.pid is not None:
                    worker.join(timeout=5)
            ready.close()
            results.close()

    def test_missing_or_weak_etag_cannot_establish_resume_anchor(self):
        for index, etag in enumerate(("", 'W/"v1"')):
            request = download_request(url=f"https://example.invalid/weak-{index}")
            result = DownloadManager(self.cache, transport=RangeTransport(headers={"ETag": etag})).fetch(request, resume=True)
            self.assertEqual(result.status, "invalid_data")
            self.assertEqual(result.error["code"], "RESUME_REQUIRES_STRONG_ETAG")
            self.assertIsNone(self.cache.get_raw(CacheRequest.from_download(request)))


class UrllibPolicyTests(unittest.TestCase):
    setUp = DownloadManagerTests.setUp
    def test_real_transport_is_network_disabled_by_default(self):
        with patch.object(cache_module, "build_opener", side_effect=AssertionError("network must not open")):
            result = DownloadManager(self.cache).fetch(download_request())
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.error["code"], "NETWORK_DISABLED")

    def test_host_policy_and_userinfo_urls_fail_before_opener_or_logging(self):
        for url in ("https://example.invalid.evil/object", "https://user:secret@example.invalid/object",
                    "https://@example.invalid/object", "http://example.invalid/object"):
            with self.subTest(url=url), patch.object(cache_module, "build_opener", side_effect=AssertionError("must not open")):
                result = DownloadManager(self.cache, network_enabled=True, allowed_hosts=("example.invalid",)).fetch(download_request(url=url))
                self.assertNotEqual(result.status, "available")
                self.assertNotIn("secret", repr(result))

    def test_mocked_urllib_preserves_proxy_handlers_and_verified_tls(self):
        stream = FakeHTTPStream()
        captures = []

        def open_without_network(opener, request, timeout):
            captures.extend(opener.handlers)
            return stream

        with patch.object(OpenerDirector, "open", open_without_network):
            result = DownloadManager(self.cache, network_enabled=True,
                                     allowed_hosts=("example.invalid",)).fetch(download_request())
        self.assertEqual(result.status, "available")
        self.assertTrue(any(isinstance(handler, ProxyHandler) for handler in captures))
        tls = next(handler for handler in captures if isinstance(handler, HTTPSHandler))._context
        self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(tls.check_hostname)
        self.assertTrue(stream.closed)

    def test_streamed_read_deadline_and_hard_byte_cap_stop_before_publication(self):
        clock = FakeClock()
        stream = FakeHTTPStream(clock=clock, read_seconds=2)
        with patch.object(cache_module, "build_opener", return_value=SimpleNamespace(open=lambda *a, **k: stream)):
            result = DownloadManager(self.cache, network_enabled=True, allowed_hosts=("example.invalid",),
                                     clock=clock, sleep=clock.sleep, deadline_seconds=3).fetch(download_request())
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.error["code"], "DEADLINE_EXCEEDED")
        self.assertEqual(stream.timeouts, [3, 1])
        self.assertIsNone(self.cache.get_raw(CacheRequest.from_download(download_request())))
        oversized = FakeHTTPStream(headers={"Content-Length": "1000"})
        with patch.object(cache_module, "build_opener", return_value=SimpleNamespace(open=lambda *a, **k: oversized)):
            result = DownloadManager(self.cache, network_enabled=True, allowed_hosts=("example.invalid",)).fetch(download_request())
        self.assertEqual(result.error["code"], "BYTE_LIMIT_EXCEEDED")
        self.assertEqual(oversized.position, 0)

    def test_redirect_host_is_checked_before_following_and_body_is_not_drained(self):
        stream = FakeHTTPStream(status=302, headers={"Location": "https://blocked.invalid/object"})
        calls = []

        def open_without_network(*args, **kwargs):
            calls.append(True)
            return stream

        with patch.object(cache_module, "build_opener", return_value=SimpleNamespace(open=open_without_network)):
            result = DownloadManager(self.cache, network_enabled=True, allowed_hosts=("example.invalid",)).fetch(download_request())
        self.assertEqual(result.error["code"], "HOST_NOT_ALLOWED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(stream.position, 0)
        self.assertTrue(stream.closed)

    def test_refused_range_closes_full_body_without_reading_or_appending(self):
        stream = FakeHTTPStream(headers={"Content-Length": "1000000000"})
        request = download_request(byte_range=(0, 0), expected_sha256=sha256(DOWNLOAD_BODY[:1]))
        with patch.object(cache_module, "build_opener", return_value=SimpleNamespace(open=lambda *a, **k: stream)):
            result = DownloadManager(self.cache, network_enabled=True, allowed_hosts=("example.invalid",)).fetch(request)
        self.assertEqual(result.error["code"], "RANGE_NOT_HONORED")
        self.assertEqual(stream.position, 0)
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
