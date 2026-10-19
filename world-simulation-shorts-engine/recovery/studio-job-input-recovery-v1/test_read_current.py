"""Offline contracts only; does not contact gCube or launch GPU work."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('read_current', Path(__file__).with_name('read_current.py'))
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class SnapshotTests(unittest.TestCase):
    def test_public_origin_rejects_credentials_paths_redirect_targets_and_other_hosts(self):
        self.assertEqual(reader.origin('https://ae20158c.service.gcube.ai:24999/'), 'https://ae20158c.service.gcube.ai:24999')
        for value in ('http://ae20158c.service.gcube.ai:24999', 'https://user@ae20158c.service.gcube.ai:24999',
                      'https://ae20158c.service.gcube.ai:24999/setup', 'https://ae20158c.service.gcube.ai:24999/?token=hidden',
                      'https://elsewhere.invalid:24999', 'https://ae20158c.service.gcube.ai:0'):
            self.assertIsNone(reader.origin(value))

    def test_real_native_envelope_required_and_nested_json_is_supported(self):
        record = {'schema': 'RTX_GPU_ADMISSION_V1', 'status': 'GPU_VERIFIED', 'gpuRenderingVerified': True,
            'testOnly': False, 'model': 'RTX 5090', 'renderMode': 'gpu-required', 'gpuProfile': 'egl',
            'verificationScope': 'STARTUP_NATIVE_GPU_PIXEL_DRAW'}
        self.assertTrue(reader.gpu_summary([{'logs': [{'message': json.dumps(record)}]}])['startupRtx5090NativeDrawEvidenceFound'])
        for key, value in (('testOnly', True), ('model', 'RTX 4080 SUPER'), ('gpuRenderingVerified', False), ('gpuProfile', 'swiftshader')):
            self.assertFalse(reader.gpu_summary([{**record, key: value}])['startupRtx5090NativeDrawEvidenceFound'])

    def test_snapshot_only_three_official_reads_no_jobs_secrets_or_render(self):
        calls = []
        secret = 'PRIVATE_OFFLINE_SENTINEL'
        class API:
            def describe(self, workload):
                calls.append(('describe', workload))
                return SimpleNamespace(raw={'ser': 5373, 'state': 'deploy', 'containerArray': [{'containerEnvs': [
                    {'WORLD_ENGINE_STUDIO_OWNER_CODE': secret}, {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': reader.DIGEST}]}]})
            def pods(self, workload): calls.append(('pods', workload)); return [{'name': 'existing-pod', 'status': 'Running'}]
            def logs(self, workload, pod): calls.append(('logs', workload, pod)); print(secret); return secret
        value = reader.collect({'GCUBE_ACCESS_TOKEN': secret}, factory=lambda _: API(), reader=lambda _: self.fail('No public origin'))
        self.assertEqual(calls, [('describe', '5373'), ('pods', '5373'), ('logs', '5373', 'existing-pod')])
        self.assertNotIn(secret, json.dumps(value))
        self.assertFalse(value['jobAbsenceConfirmed']); self.assertFalse(value['renderStarted'])

    def test_missing_credentials_and_exception_never_leak_or_fall_back(self):
        self.assertEqual(reader.collect({}, factory=lambda _: self.fail('No token'))['operations'], [])
        def fail(_): raise RuntimeError('PRIVATE_OFFLINE_SENTINEL')
        result = reader.collect({'GCUBE_ACCESS_TOKEN': 'OFFLINE_ONLY'}, factory=fail)
        self.assertNotIn('PRIVATE_OFFLINE_SENTINEL', json.dumps(result))
        self.assertEqual(result['blockingReason'], 'UNEXPECTED_ERROR')


if __name__ == '__main__': unittest.main()
