import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.one_url import sandbox_boot as boot


class SandboxBootTests(unittest.TestCase):
    def test_trusted_provider_authority(self):
        self.assertEqual(boot.trusted_tunnel('https://sb-test-7860.modal.host/'),
                         'https://sb-test-7860.modal.host')
        for bad in ['http://sb-test-7860.modal.host', 'https://modal.host.evil.invalid',
                    'https://a@sb-test.modal.host', 'https://x.modal.host:7860',
                    'https://x.modal.host/?token=secret', 'https://x.modal.host/path']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boot.trusted_tunnel(bad)

    def test_configuration_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'origin.json'
            with patch.object(boot, 'ORIGIN_FILE', p):
                boot.configure('https://one.modal.host')
                before = p.read_bytes()
                with self.assertRaises(FileExistsError):
                    boot.configure('https://two.modal.host')
                self.assertEqual(p.read_bytes(), before)
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_owner_kept_and_never_rotated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = boot.prepare_owner(root, 'synthetic-owner-password')
            before = p.read_bytes()
            self.assertEqual(boot.prepare_owner(root, 'synthetic-owner-password'), p)
            with self.assertRaises(ValueError):
                boot.prepare_owner(root, 'a-different-synthetic-password')
            self.assertEqual(p.read_bytes(), before)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_owner_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'target').write_text('keep')
            (root / 'owner-code.txt').symlink_to(root / 'target')
            with self.assertRaises(ValueError):
                boot.prepare_owner(root, 'synthetic-owner-password')
            self.assertEqual((root / 'target').read_text(), 'keep')

    def test_idle_never_stops_pending_or_unknown_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(boot.busy_jobs(root))
            (root / 'jobs').mkdir()
            p = root / 'jobs/job_012345678abc.json'
            for status in ['queued', 'rendering', 'interrupted']:
                p.write_text(json.dumps({'status': status}))
                self.assertTrue(boot.busy_jobs(root))
            for status in ['complete', 'failed', 'cancelled']:
                p.write_text(json.dumps({'status': status}))
                self.assertFalse(boot.busy_jobs(root))
            p.write_text('{broken')
            self.assertTrue(boot.busy_jobs(root))
            for raw in ['[]', 'null', '5', '{"status":"unknown"}']:
                p.write_text(raw)
                self.assertTrue(boot.busy_jobs(root))
            p.write_text('{"status":"complete"}')
            (root / 'jobs/job_012345678abc.failure.json').write_text('{"error":"diagnostic"}')
            self.assertFalse(boot.busy_jobs(root))

    def test_import_does_not_deploy(self):
        from deployment.one_url import modal_candidate
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as caught:
                modal_candidate.build_app()
            self.assertEqual(str(caught.exception), 'BUDGET_UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
