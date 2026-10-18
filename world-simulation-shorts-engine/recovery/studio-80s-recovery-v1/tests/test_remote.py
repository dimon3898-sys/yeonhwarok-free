import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('recovery_remote', HERE / 'remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class RemoteTests(unittest.TestCase):
    def bundle(self, *, running=True, registration=True, wrong_id=False):
        self.calls = []
        class API:
            def describe(_, workload):
                self.calls.append(('describe', workload))
                return SimpleNamespace(raw={'ser': '99' if wrong_id else '5373', 'state': 'deploy',
                    'containerArray': [{'containerEnvs': []}]})
            def pods(_, workload):
                self.calls.append(('pods', workload))
                return [{'name': 'authorized-pod', 'status': 'Running' if running else 'Terminating'}]
            def logs(_, workload, pod):
                self.calls.append(('logs', workload))
                return '{"errorCode":"STUDIO_HTTPS_ORIGIN_REQUIRED","secret":"NEVER_PUBLISH"}'
        class SSH:
            def get(_, namespace, pod, container):
                self.calls.append(('get-existing', namespace, pod, container))
                return SimpleNamespace(user_pwd='NEVER_PUBLISH') if registration else None
        return API(), SSH(), lambda _: 'valid-namespace'

    def test_missing_secret_no_network(self):
        def forbidden(*_):
            raise AssertionError('network invoked')
        self.assertEqual(remote.collect({}, factory=forbidden)['blocking_reason'], 'APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED')

    def test_stopped_pod_never_queries_ssh(self):
        result = remote.collect({'GCUBE_ACCESS_TOKEN': 'TEST'}, factory=lambda _: self.bundle(running=False))
        self.assertEqual(result['blocking_reason'], 'EXISTING_RUNNING_POD_REQUIRED_NO_REDEPLOY')
        self.assertFalse(any(c[0] == 'get-existing' for c in self.calls))
        self.assertNotIn('NEVER_PUBLISH', json.dumps(result))

    def test_missing_existing_ssh_never_registers(self):
        result = remote.collect({'GCUBE_ACCESS_TOKEN': 'TEST'}, factory=lambda _: self.bundle(registration=False))
        self.assertEqual(result['blocking_reason'], 'EXISTING_SSH_REGISTRATION_NOT_AVAILABLE_NO_REGISTRATION_ATTEMPTED')
        self.assertEqual([c[0] for c in self.calls], ['describe', 'pods', 'logs', 'get-existing'])

    def test_wrong_workload_stops_before_pods(self):
        result = remote.collect({'GCUBE_ACCESS_TOKEN': 'TEST'}, factory=lambda _: self.bundle(wrong_id=True))
        self.assertEqual(result['blocking_reason'], 'WORKLOAD_ID_NOT_VERIFIED')
        self.assertEqual(self.calls, [('describe', '5373')])

    def test_existing_ssh_fixed_scanner_only(self):
        def scanner(info, roots):
            self.assertEqual(info.user_pwd, 'NEVER_PUBLISH')
            self.assertEqual(roots, list(remote.DEFAULT_ROOTS))
            return {'status': 'READ_ONLY_SCAN_COLLECTED'}
        result = remote.collect({'GCUBE_ACCESS_TOKEN': 'TEST'}, factory=lambda _: self.bundle(), scanner=scanner)
        self.assertEqual(result['status'], 'READ_ONLY_EVIDENCE_COLLECTED')
        self.assertEqual(result['paid_operations'], 0)
        self.assertEqual(result['state_changes'], 0)
        self.assertNotIn('NEVER_PUBLISH', json.dumps(result))

    def test_untrusted_paths_and_remote_values_not_published(self):
        for value in ['/tmp/any', '/var/lib/world-engine-private/engine/../secrets', '/world-storage', '/var/lib/world-engine-private/engine/x;id']:
            self.assertEqual(remote.candidate_roots({'containerEnvs': [{'WORLD_ENGINE_STUDIO_STATE_ROOT': value}]}), list(remote.DEFAULT_ROOTS))
        value = remote.sanitize_scan({'state': 'TOKEN_SECRET', 'rawToken': 'SECRET', 'timingsSeconds': {'composition': 4, 'secret': 'TOKEN'}, 'sha256': 'a' * 64})
        self.assertEqual(value, {'state': 'WITHHELD_UNKNOWN', 'timingsSeconds': {'composition': 4}, 'sha256': 'a' * 64})

    def test_scanner_has_no_mutating_or_process_api(self):
        for forbidden in ['subprocess', 'os.environ', 'O_WRONLY', 'O_RDWR', 'mkdir(', 'unlink(', 'chmod(', 'chown(', 'write(', 'importlib', 'socket']:
            self.assertNotIn(forbidden, remote.SCANNER)
        command = remote.scanner_command(list(remote.DEFAULT_ROOTS))
        self.assertIn('/usr/bin/python3 -B -c ', command)
        with self.assertRaises(ValueError):
            remote.scanner_command(['/etc'])

    def scanner(self):
        namespace = {'PRIVATE_UID': os.getuid()}
        exec(remote.SCANNER, namespace)
        return namespace

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(data); path.chmod(0o600)
        return hashlib.sha256(data).hexdigest()

    def test_readonly_scan_retains_found_job_without_lower_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); job = base / remote.JOB
            self.write(job / 'STATE.json', {'schema': 'WORLD_ENGINE_STUDIO_JOB_V1', 'jobId': remote.JOB,
                'state': 'FAILED', 'phase': 'SFX_AND_FINAL_COMPOSITION', 'errorCode': 'STUDIO_APPROVED_DEADLINE_EXCEEDED',
                'completedScenes': 12, 'processedFrames': 2400, 'profileId': 'V4_ARCHIVAL_80S',
                'timingsSeconds': {'gpuPipeline': 3540.5}})
            self.write(job / 'PLAN.json', {'scenes': [{'sceneId': 's1'}], 'totalFrames': 2400})
            self.write(job / 'AUDIO.json', {'enabled': True, 'secret': 'NEVER_PUBLISH'})
            before = {str(p): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result = self.scanner()['scan']([str(base)], str(base / 'exports'), remote.JOB)
            self.assertEqual(result['status'], 'FOUND')
            self.assertEqual(result['rootResults'][0]['timingsSeconds'], {'gpuPipeline': 3540.5})
            self.assertEqual(result['rootResults'][0]['scanError'], 'NOT_FOUND')
            self.assertEqual(result['rootResults'][0]['errorCode'], 'STUDIO_APPROVED_DEADLINE_EXCEEDED')
            self.assertEqual(before, {str(p): p.read_bytes() for p in base.rglob('*') if p.is_file()})
            self.assertNotIn('NEVER_PUBLISH', json.dumps(remote.sanitize_scan(result)))

    def test_scanner_rejects_symlink_and_world_readable_private_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); outside = root / 'original.json'
            self.write(outside, {'x': 1})
            link = root / 'alias.json'; link.symlink_to(outside)
            ns = self.scanner()
            with self.assertRaises(OSError): ns['read_json'](link)
            outside.chmod(0o644)
            with self.assertRaises(ns['ScanError']): ns['read_json'](outside)

    def test_cache_hash_provenance_and_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = 'a' * 64; attempt = root / 'cache' / key / ('attempt-' + 'b' * 24)
            segment = {'sceneId': 's1', 'startFrame': 0, 'endFrame': 200, 'sha256': hashlib.sha256(b'mp4-fixture').hexdigest(),
                'testOnly': False, 'hardwareVerified': True, 'fullDecodeVerified': True, 'frameCountVerified': True, 'file': 'segment.mp4'}
            attempt.mkdir(parents=True); media = attempt / 'segment.mp4'; media.write_bytes(b'mp4-fixture'); media.chmod(0o600)
            digest = self.write(attempt / 'COMPLETE.json', {'schema': 'WORLD_ENGINE_SCENE_CACHE_RECEIPT_V2', 'status': 'COMPLETE', 'key': key,
                'segment': segment, 'files': [{'file': 'segment.mp4', 'sha256': segment['sha256'], 'bytes': 11}]})
            self.write(attempt.parent / 'SUCCESS.json', {'key': key, 'attemptId': attempt.name, 'receiptSHA256': digest})
            ns = self.scanner()
            result = ns['segment'](root, key, segment['sha256'], segment)
            self.assertEqual(result['status'], 'VERIFIED')
            media.write_bytes(b'corruption!')
            with self.assertRaises(ns['ScanError']): ns['segment'](root, key, segment['sha256'], segment)


if __name__ == '__main__':
    unittest.main()
