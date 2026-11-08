"""New post-capture JSON boundary only; no renderer, browser, FFmpeg or GPU."""
import ast
import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]
CACHE_PATH = ENGINE / 'recovery/universal-auto-video-v2/cache.py'
spec = importlib.util.spec_from_file_location('size_boundary_original_cache', CACHE_PATH)
CACHE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CACHE)
CANDIDATE = HERE / 'candidate/controller/nvidia_worker.py'
tree = ast.parse(CANDIDATE.read_text())
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_read_frame_evidence')
scope = {'os': os, 'json': json, 're': re, 'cache': lambda: CACHE,
         'sha': lambda raw: hashlib.sha256(raw).hexdigest()}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(CANDIDATE), 'exec'), scope)
READ = scope['_read_frame_evidence']
MEASUREMENTS = {}


class FrameEvidenceBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='frame-evidence-boundary-')
        self.root = Path(self.temp.name)
        self.directory = CACHE.PrivateTree(self.root)

    def tearDown(self):
        self.directory.close()
        self.temp.cleanup()

    def write(self, raw, name='FRAME_EVIDENCE.json'):
        file = self.root / name
        with file.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
        return {'file': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_archived_geometry_exceeds_frozen_cache_but_is_read_intact(self):
        # Reuse one prior diagnostic, not a new draw or a claim of GPU output.
        source = gzip.decompress(base64.b64decode((HERE / 'ARCHIVED_FRAME_192.json.gz.base64').read_bytes()))
        diagnostic = json.loads(source)['diagnostic']
        rows = [{'frame': i, 'diagnostic': diagnostic if i < 32 else {'glError': 0}}
                for i in range(300)]
        value = {'schema': 'WORLD_ENGINE_NVIDIA_PRESENTATION_FRAMES_V1',
                 'durationSeconds': 10, 'totalFrames': 300, 'frames': rows}
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
        self.assertGreater(len(raw), CACHE.MAX_JSON)
        reference = self.write(raw)
        with self.assertRaisesRegex(CACHE.CacheError, '^JSON_SIZE_INVALID$'):
            self.directory.json('FRAME_EVIDENCE.json')
        loaded = READ(self.directory, reference, 300)
        self.assertEqual(loaded, value)
        self.assertEqual(len(loaded['frames']), 300)
        self.assertEqual(CACHE.MAX_JSON, 32 * 1024**2)
        MEASUREMENTS.update(fixtureBytes=len(raw), frozenLimitBytes=CACHE.MAX_JSON,
                            sourceSHA256=hashlib.sha256(source).hexdigest(), sourceFrame=192,
                            baselineError='JSON_SIZE_INVALID', candidateRoundTrip='IDENTICAL',
                            actualIncidentFileSize='UNKNOWN', syntheticFixtureNotRendered=True)

    def test_existing_small_180_frame_document(self):
        value = {'frames': [{'frame': i, 'diagnostic': {'glError': 0}} for i in range(180)]}
        ref = self.write(json.dumps(value).encode())
        self.assertEqual(READ(self.directory, ref, 180), value)

    def test_checksum_mismatch_rejected(self):
        ref = self.write(b'{}'); ref['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'SHA256_MISMATCH'):
            READ(self.directory, ref, 300)

    def test_reference_name_and_frame_scope_rejected(self):
        ref = self.write(b'{}')
        for count in (0, 301, 300.0, True):
            with self.assertRaisesRegex(RuntimeError, 'REFERENCE_INVALID'):
                READ(self.directory, ref, count)
        for reference in (None, {}, {**ref, 'file': '../FRAME_EVIDENCE.json'}, {**ref, 'file': 'PLAN.json'}):
            with self.assertRaisesRegex(RuntimeError, 'REFERENCE_INVALID'):
                READ(self.directory, reference, 300)

    def test_empty_and_over_cap_rejected_before_read(self):
        ref = self.write(b'')
        with self.assertRaisesRegex(RuntimeError, 'SIZE_INVALID'):
            READ(self.directory, ref, 300)
        with (self.root / 'FRAME_EVIDENCE.json').open('r+b') as stream:
            stream.truncate(512 * 1024**2 + 1)
        with patch.object(CACHE.storage, '_read_fd', side_effect=AssertionError('must reject before read')):
            with self.assertRaisesRegex(RuntimeError, 'SIZE_INVALID'):
                READ(self.directory, ref, 300)

    def test_symlink_and_hardlink_rejected(self):
        ref = self.write(b'{}', 'other.json'); ref['file'] = 'FRAME_EVIDENCE.json'
        destination = self.root / 'FRAME_EVIDENCE.json'
        destination.symlink_to(self.root / 'other.json')
        with self.assertRaises(OSError):
            READ(self.directory, ref, 300)
        destination.unlink()
        os.link(self.root / 'other.json', destination)
        with self.assertRaisesRegex(CACHE.CacheError, 'PRIVATE_PATH_REQUIRED'):
            READ(self.directory, ref, 300)

    def test_public_permissions_rejected(self):
        ref = self.write(b'{}'); (self.root / 'FRAME_EVIDENCE.json').chmod(0o644)
        with self.assertRaisesRegex(CACHE.CacheError, 'PRIVATE_PATH_REQUIRED'):
            READ(self.directory, ref, 300)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw, code in ((b'{"a":1,"a":2}', 'DUPLICATE_JSON_KEY'), (b'{"a":NaN}', 'NONFINITE_JSON')):
            ref = self.write(raw)
            with self.assertRaisesRegex(CACHE.CacheError, code):
                READ(self.directory, ref, 300)
            (self.root / 'FRAME_EVIDENCE.json').unlink()

    def test_inode_replacement_during_read_rejected(self):
        ref = self.write(b'{}'); original = CACHE.storage._read_fd
        def replace_after_read(fd, **kw):
            result = original(fd, **kw)
            other = self.root / 'replacement'
            other.write_bytes(b'{}'); other.chmod(0o600)
            os.replace(other, self.root / 'FRAME_EVIDENCE.json')
            return result
        with patch.object(CACHE.storage, '_read_fd', side_effect=replace_after_read):
            # Unlinking the original inode also makes nlink=0; the ownership
            # guard rejects it before the later immutable-path comparison.
            with self.assertRaisesRegex(CACHE.CacheError, 'PRIVATE_PATH_REQUIRED'):
                READ(self.directory, ref, 300)

    def test_other_documents_keep_original_limit(self):
        file = self.root / 'PLAN.json'
        with file.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600); stream.truncate(CACHE.MAX_JSON + 1)
        with self.assertRaisesRegex(CACHE.CacheError, '^JSON_SIZE_INVALID$'):
            self.directory.json('PLAN.json')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FrameEvidenceBoundary)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    payload = {'status': 'PASS' if result.wasSuccessful() else 'FAIL',
               'testsRun': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'scope': 'NEW_FRAME_EVIDENCE_READER_BOUNDARY_ONLY', 'oldPASSReruns': 0,
               'rendererExecutions': 0, 'gpuStarts': 0, 'mediaEncodes': 0,
               'installedImageValidation': 'NOT_RUN', **MEASUREMENTS}
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
