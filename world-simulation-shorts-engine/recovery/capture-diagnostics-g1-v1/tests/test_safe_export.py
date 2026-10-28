import errno
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from export_fixture import exporter, write_private

class SafeExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.job = self.root / 'studio-' 
        self.job.mkdir(mode=0o700)
        (self.job / 'capture').mkdir(mode=0o700)
        write_private(self.job / 'LEASE_SUPERVISOR_RESULT.json', {'cleanupVerified': True})
        self.failure = {'operationId': 'READBACK', 'sourceId': 'NATIVE_GUARD', 'errorCode': 'GCUBE_NATIVE_READBACK_INVALID',
            'failureKind': 'DOMAIN_ERROR', 'exceptionType': 'Error', 'frameIndex': 0}
        self.checkpoint = {'schema': 'WORLD_ENGINE_CAPTURE_OPERATIONS_V1', 'operationId': 'READBACK',
            'lastCompletedOperation': 'DRAW', 'firstFailure': self.failure, 'cleanupFailure': None,
            'renderedFrames': 0, 'sequence': 4, 'nativeProofCompleted': False, 'evidenceStatus': 'LOCAL_ATOMIC_CHECKPOINT'}
        write_private(self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json', self.checkpoint)
    def tearDown(self):
        self.tmp.cleanup()
    def test_checkpoint_survives_missing_receipt(self):
        result = exporter.export_failure(self.job, self.root / 'export')
        payload = result['diagnostic']
        self.assertTrue(payload['missingEvidence']['capture'])
        self.assertEqual(payload['capture']['code'], 'GCUBE_NATIVE_READBACK_INVALID')
        self.assertEqual(payload['capture']['operations']['lastCompletedOperation'], 'DRAW')
        raw = (self.root / 'export/CAPTURE_DIAGNOSTIC.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
    def test_no_secret_or_arbitrary_fields_escape(self):
        secret = 'SYNTHETIC_SECRET_NOT_FOR_EXPORT'
        self.checkpoint.update(token=secret, url='https://example.invalid/?owner='+secret, environment={'OWNER_CODE':secret})
        self.failure.update(errorCode=secret, sourceId='NATIVE_GUARD', stack=secret, line=secret)
        write_private(self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json', self.checkpoint)
        result = exporter.export_failure(self.job, self.root / 'export')
        wire = json.dumps(result)
        self.assertNotIn(secret, wire)
        self.assertNotIn('https://', wire)
        self.assertEqual(result['diagnostic']['capture']['code'], 'UNCLASSIFIED_EXCEPTION')
    def test_cleanup_gate_unchanged(self):
        write_private(self.job / 'LEASE_SUPERVISOR_RESULT.json', {'cleanupVerified': False})
        with self.assertRaisesRegex(ValueError, 'DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED'):
            exporter.export_failure(self.job, self.root / 'export')
        self.assertFalse((self.root / 'export').exists())
    def test_symlink_private_receipt_rejected(self):
        target = self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json'
        preserved = self.job / 'original.json'
        target.rename(preserved)
        target.symlink_to(preserved)
        self.assertIsNone(exporter.read_json_safe(target))
    def test_size_limit_and_permission_rejected(self):
        target = self.job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json'
        target.write_bytes(b' ' * (exporter.LIMIT + 1));target.chmod(0o600)
        self.assertIsNone(exporter.read_json_safe(target))
        write_private(target, self.checkpoint);target.chmod(0o644)
        self.assertIsNone(exporter.read_json_safe(target))
    def test_atomic_export_and_storage_failure_classification(self):
        for error, expected in [(errno.EACCES,21),(errno.ENOSPC,22),(errno.EFBIG,23),(errno.EIO,24)]:
            with self.subTest(errno=error):
                self.assertEqual(exporter.storage_exit_code(OSError(error,'SYNTHETIC_SECRET_NOT_FOR_EXPORT')),expected)
        self.assertEqual(exporter.storage_exit_code(TimeoutError()),25)
        with patch.object(exporter.os,'fsync',side_effect=OSError(errno.ENOSPC,'secret')):
            with self.assertRaises(OSError):exporter.export_failure(self.job,self.root/'failed')
        self.assertFalse((self.root/'failed/CAPTURE_DIAGNOSTIC.json').exists())
        self.assertTrue((self.job/'capture/CAPTURE_OPERATION_CHECKPOINT.json').exists())
    def test_existing_destination_not_overwritten(self):
        target=self.root/'export';target.mkdir();(target/'sentinel').write_text('preserve')
        with self.assertRaises(FileExistsError):exporter.export_failure(self.job,target)
        self.assertEqual((target/'sentinel').read_text(),'preserve')

if __name__ == '__main__':unittest.main()
