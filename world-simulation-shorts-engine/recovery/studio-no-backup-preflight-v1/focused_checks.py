#!/usr/bin/env python3
"""CPU-only checks of frozen, pre-durability Studio contracts.

Policy cases reuse the preserved four-hour tests' real validator entrypoints.
Coordinator ordering cases use its documented TEST_ONLY component seam: they
exercise real control flow and private ledgers, not GPU or mounted media I/O.
No deployment, renderer, Dropbox request, Secret access, or approval is created.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
INSTALLED = Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
RECOVERY = INSTALLED if INSTALLED.is_dir() else HERE.parent
PLAN_SHA256 = '2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6'
PINS = {
    'production-studio-mvp-v1/studio_controller.py': 'c2e0d94a31cd90569d29f944da1a538c9efcf77d15cd0f2bfacbe99396ae053c',
    'universal-auto-video-v2/orchestrator.py': '2e1e9d76c6ecf760f69fa2204c80d91da251fa0ee2abf8ed7cf3fe2388afcca4',
    'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json': PLAN_SHA256,
}


def frozen_bytes(relative):
    path = RECOVERY / relative
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise RuntimeError('NO_BACKUP_FROZEN_SYMLINK_FORBIDDEN')
    if path.is_file():
        raw = path.read_bytes()
    elif RECOVERY == HERE.parent:
        # A sparse checkout can preserve a source in Git without materializing
        # it. Read the existing local blob; never fetch or create a substitute.
        root = RECOVERY.parents[1]
        raw = subprocess.run(
            ['git', '-C', str(root), 'show', 'HEAD:world-simulation-shorts-engine/recovery/' + relative],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15).stdout
    else:
        raise RuntimeError('NO_BACKUP_FROZEN_SOURCE_MISSING')
    if hashlib.sha256(raw).hexdigest() != PINS[relative]:
        raise RuntimeError('NO_BACKUP_FROZEN_SOURCE_CHANGED')
    return raw


def load_frozen(name, relative):
    frozen_bytes(relative)
    spec = importlib.util.spec_from_file_location(name, RECOVERY / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class OriginalContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path[:0] = [str(RECOVERY / 'production-studio-mvp-v1'),
                        str(RECOVERY / 'universal-auto-video-v2')]
        cls.controller = load_frozen('_no_backup_frozen_controller',
                                     'production-studio-mvp-v1/studio_controller.py')
        cls.coordinator = load_frozen('_no_backup_frozen_coordinator',
                                      'universal-auto-video-v2/orchestrator.py')
        cls.plan = json.loads(frozen_bytes('verified-front-data-v4-recovery/VIDEO_PLAN_80S.json'))

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        # Synthetic free-test inputs only: these are not a price or approval.
        self.policy = {'validUntil': (self.now + timedelta(hours=8)).isoformat(),
                       'maxWallSeconds': 14400, 'maxRetries': 0,
                       'maxCostAmount': '12.00', 'currency': 'USD',
                       'gpuHourlyRate': '3.00'}

    def read_policy(self, policy):
        class Reader:
            def json(self, name, optional=False):
                if name != 'operator_policy.json':
                    raise AssertionError('Unexpected policy read')
                return policy
        return self.controller.StudioController._policy(None, Reader())

    def approval(self, policy=None):
        return {'schema': self.coordinator.AUTH_SCHEMA, 'approved': True,
                'planSHA256': self.coordinator.canonical_sha256(self.plan),
                'imageDigest': self.plan['renderProfile']['imageDigest'],
                **deepcopy(self.policy if policy is None else policy)}

    def reject(self, code, action):
        with self.assertRaises(Exception) as caught:
            action()
        self.assertEqual(getattr(caught.exception, 'code', None) or str(caught.exception), code)

    def both_reject(self, policy, studio_code, coordinator_code):
        self.reject(studio_code, lambda: self.read_policy(policy))
        self.reject(coordinator_code, lambda: self.coordinator.validate_approval(
            self.approval(policy), self.plan, now=self.now))

    def test_01_original_80s_plan_has_exact_twelve_contiguous_scenes(self):
        self.coordinator.validate_plan(self.plan, require_renderable=True)
        self.assertEqual(self.plan['durationSeconds'], 80)
        self.assertEqual(self.plan['fps'], 30)
        self.assertEqual(self.plan['totalFrames'], 2400)
        self.assertEqual(len(self.plan['scenes']), 12)
        self.assertEqual(self.plan['resolution'], {'width': 1080, 'height': 1920})
        cursor = 0
        for scene in self.plan['scenes']:
            self.assertEqual(scene['startFrame'], cursor)
            self.assertGreater(scene['endFrame'], cursor)
            cursor = scene['endFrame']
        self.assertEqual(cursor, 2400)

    def test_02_unchanged_validators_accept_four_hours(self):
        self.assertEqual(self.read_policy(self.policy)['maxWallSeconds'], 14400)
        approval = self.approval()
        self.assertEqual(self.coordinator.validate_approval(approval, self.plan, now=self.now), approval)

    def test_03_insufficient_budget_is_rejected_at_both_layers(self):
        self.both_reject({**self.policy, 'maxCostAmount': '11.99'},
                         'STUDIO_COST_LIMIT_EXCEEDED', 'TIME_CEILING_EXCEEDS_APPROVED_COST')

    def test_04_expired_approval_is_rejected_at_both_layers(self):
        self.both_reject({**self.policy, 'validUntil': (self.now - timedelta(seconds=1)).isoformat()},
                         'STUDIO_OPERATOR_POLICY_EXPIRED', 'GPU_APPROVAL_EXPIRED')

    def test_05_excessive_retries_are_rejected_at_both_layers(self):
        self.both_reject({**self.policy, 'maxRetries': 3},
                         'STUDIO_OPERATOR_POLICY_INVALID', 'BOUNDED_APPROVAL_REQUIRED')

    def test_06_new_policy_never_extends_existing_approval(self):
        original = self.approval({**self.policy, 'maxWallSeconds': 3600})
        before = deepcopy(original)
        self.read_policy(self.policy)
        self.coordinator.validate_approval(self.approval(), self.plan, now=self.now)
        self.coordinator.validate_approval(original, self.plan, now=self.now)
        self.assertEqual(original, before)
        self.assertEqual(original['maxWallSeconds'], 3600)

    def test_07_missing_or_wrong_plan_approval_is_rejected(self):
        self.reject('EXPLICIT_GPU_APPROVAL_REQUIRED',
                    lambda: self.coordinator.validate_approval({}, self.plan, now=self.now))
        bad = self.approval(); bad['planSHA256'] = '0' * 64
        self.reject('APPROVAL_PLAN_MISMATCH',
                    lambda: self.coordinator.validate_approval(bad, self.plan, now=self.now))

    def run_test_coordinator(self, checkpoint_status='ok'):
        events = []

        class TestCache:
            def __init__(self, _root): pass
            def lookup(self, _key): return None
            def begin(self, key): return key
            def complete(self, _key, _attempt, segment): return segment
            def close(self): pass

        def render(_plan, scene, _attempt, **_kwargs):
            events.append(('render', scene['sceneId']))
            return {'path': 'CPU_TEST_SEAM_NO_MEDIA', 'sha256': 'a' * 64,
                    **{key: scene[key] for key in ('sceneId', 'startFrame', 'endFrame')}}

        def checkpoint(_plan, scene, _segment, _export, **_kwargs):
            events.append(('checkpoint', scene['sceneId']))
            if checkpoint_status == 'raise':
                raise RuntimeError('TEST_CHECKPOINT_WRITE_FAILED')
            return {'mountedViewReadbackVerified': checkpoint_status == 'ok'}

        def compose(_plan, segments, _path):
            events.append(('compose', len(segments)))
            return {'CPU_TEST_SEAM': True}

        components = {'render': render, 'verify': lambda *_: {}, 'checkpoint': checkpoint,
                      'compose': compose, 'export': lambda *_: {'mountedViewReadbackVerified': True},
                      'lease': nullcontext}
        # Preserve the real POSIX-private directory checks. A root-owned sticky
        # /tmp is valid; the managed sandbox's nobody-owned /tmp is not.
        parent = Path('/tmp') if os.stat('/tmp').st_uid == 0 else RECOVERY.parents[1].parent
        with tempfile.TemporaryDirectory(prefix='we-no-backup-cpu-', dir=parent) as temporary:
            root = Path(temporary) / 'private'
            with mock.patch.object(self.coordinator, 'SceneCache', TestCache), \
                 mock.patch.object(self.coordinator, '_identity', return_value=None), \
                 mock.patch.object(self.coordinator, '_alive', return_value=False):
                error_code = None
                try:
                    state = self.coordinator.run_job(self.plan, control_root=root,
                        export_root=Path(temporary) / 'shared', approval=self.approval(),
                        _test_components=components)
                except Exception as error:
                    error_code = getattr(error, 'code', None) or str(error)
                    job = root / self.coordinator._job_id(self.plan) / 'JOB.json'
                    state = json.loads(job.read_text())
            return events, state, error_code

    def test_08_every_completed_scene_checkpoints_before_next_render(self):
        events, state, error = self.run_test_coordinator()
        expected = []
        for scene in self.plan['scenes']:
            expected.extend([('render', scene['sceneId']), ('checkpoint', scene['sceneId'])])
        expected.append(('compose', 12))
        self.assertEqual(events, expected)
        self.assertIsNone(error)
        self.assertEqual(state['state'], 'COMPLETED')
        self.assertEqual(state['progressFrames'], 2400)
        self.assertIs(state['testOnly'], True)
        self.assertIs(state['gpuRenderingVerified'], False)

    def test_09_checkpoint_write_failure_blocks_next_scene(self):
        events, state, error = self.run_test_coordinator('raise')
        first = self.plan['scenes'][0]['sceneId']
        self.assertEqual(events, [('render', first), ('checkpoint', first)])
        self.assertEqual(error, 'TEST_CHECKPOINT_WRITE_FAILED')
        self.assertEqual(state['state'], 'FAILED')
        self.assertEqual(state['completedScenes'], {})
        self.assertEqual(state['firstFailure']['code'], error)
        self.assertIs(state['gpuRenderingVerified'], False)

    def test_10_checkpoint_readback_failure_blocks_next_scene(self):
        events, state, error = self.run_test_coordinator('bad-readback')
        self.assertEqual(len(events), 2)
        self.assertEqual(error, 'SCENE_CHECKPOINT_MOUNTED_READBACK_FAILED')
        self.assertEqual(state['state'], 'FAILED')
        self.assertEqual(state['completedScenes'], {})
        self.assertIs(state['gpuRenderingVerified'], False)


class ClosedResults(unittest.TestResult):
    def __init__(self):
        super().__init__(); self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append({'check': test._testMethodName, 'status': 'PASS'})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.rows.append({'check': getattr(test, '_testMethodName', 'suite'), 'status': 'FAIL',
                          'reasonCode': 'FOCUSED_ASSERTION_FAILED'})

    def addError(self, test, error):
        super().addError(test, error)
        self.rows.append({'check': getattr(test, '_testMethodName', 'suite'), 'status': 'BLOCKED',
                          'reasonCode': 'FOCUSED_CPU_DEPENDENCY_OR_RUNTIME_FAILED'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    # Never serialize test exception payloads, local environment, or tokens.
    result = ClosedResults()
    with mock.patch('sys.stdout', new_callable=io.StringIO), mock.patch('sys.stderr', new_callable=io.StringIO):
        unittest.defaultTestLoader.loadTestsFromTestCase(OriginalContracts).run(result)
    success = result.wasSuccessful() and result.testsRun == 10
    report = {'schema': 'WORLD_ENGINE_NO_BACKUP_CPU_FOCUSED_CHECKS_V1',
              'status': 'PASS' if success else 'FAIL', 'checksRun': result.testsRun,
              'checks': result.rows, 'frozenPlanSHA256': PLAN_SHA256,
              'policyBudgetFixtures': 'SYNTHETIC_NOT_OWNER_APPROVAL_OR_PROVIDER_PRICE',
              'checkpointOrderChecks': 'REAL_COORDINATOR_TEST_ONLY_COMPONENT_SEAM',
              'actualMediaExportVerifiedThisRun': False, 'externalDownloadVerified': False,
              'gpuRenderingVerified': False, 'gpuExecuted': False, 'paidOperations': 0,
              'providerRequests': 0, 'secretsAccessed': False}
    raw = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    if args.output:
        # Explicit caller-supplied new report only; existing evidence is kept.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(raw)
    print(raw, end='')
    return 0 if success else 2


if __name__ == '__main__':
    raise SystemExit(main())
