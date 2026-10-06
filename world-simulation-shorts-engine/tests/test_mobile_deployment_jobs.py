"""Job queue/checkpoint policy, tested with a cooperative fake runner only."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from deployment.mobile_server import DurableJobs
from deployment.security import private_json
from engine.storage import EngineError, plan_hash


def wait_until(fn):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(.01)
    return False


class FakeStore:
    def __init__(self):
        self.plans = {p: {'duration': 12, 'scenes': [{'scene_id': 'S001'}], 'request': {'topic': p}}
                      for p in ['project_aaaaaa', 'project_bbbbbb', 'project_cccccc']}
        self.states = {p: {'status': 'planned'} for p in self.plans}
        self.approved = set(self.plans)

    def require_approved(self, pid, version):
        if pid not in self.approved:
            raise EngineError('APPROVAL_REQUIRED', 'approval required')
        return copy.deepcopy(self.plans[pid])

    def status(self, pid, version):
        return self.states[pid]

    def set_status(self, pid, version, **kwargs):
        self.states[pid].update(kwargs)


class FakeApp:
    def __init__(self, root):
        self.state_root, self.base_url, self.store = root, 'http://127.0.0.1:12345', FakeStore()

    def check_plan_budget(self, plan):
        if plan['duration'] > 180:
            raise EngineError('DEPLOYMENT_JOB_LIMIT', 'budget exceeded')

    def outputs(self, *args):
        return []


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = FakeApp(Path(self.temp.name))
        self.started, self.release, self.calls = threading.Event(), threading.Event(), []
        def fake(ticket, plan, cancel):
            self.calls.append(ticket['project_id'])
            self.started.set()
            while not self.release.wait(.01):
                if cancel.is_set():
                    self.app.store.set_status(ticket['project_id'], ticket['version'], status='interrupted')
                    return
            self.app.store.set_status(ticket['project_id'], ticket['version'], status='complete')
        self.runner = fake
        self.jobs = DurableJobs(self.app, fake)
        self.validator = patch('engine.schema.validate_plan', return_value={'passed': True})
        self.validator.start()

    def tearDown(self):
        self.jobs.close()
        self.validator.stop()
        self.temp.cleanup()

    def test_one_active_one_queued_duplicate_and_full_queue(self):
        self.jobs.start()
        first = self.jobs.submit('project_aaaaaa', 'v001')
        self.assertTrue(self.started.wait(2))
        self.assertEqual(self.jobs.submit('project_aaaaaa', 'v001')['job_id'], first['job_id'])
        self.jobs.submit('project_bbbbbb', 'v001')
        with self.assertRaises(EngineError) as e:
            self.jobs.submit('project_cccccc', 'v001')
        self.assertEqual(e.exception.code, 'JOB_QUEUE_FULL')
        self.release.set()
        self.assertTrue(wait_until(lambda: len(self.calls) == 2 and self.jobs.active is None))

    def test_approval_and_ticket_selected_scenes_hash_bound(self):
        self.app.store.approved.remove('project_aaaaaa')
        with self.assertRaises(EngineError):
            self.jobs.submit('project_aaaaaa', 'v001')
        self.assertFalse(list(self.jobs.root.glob('*.json')))
        self.app.store.approved.add('project_aaaaaa')
        first = self.jobs.submit('project_aaaaaa', 'v001')
        self.assertEqual(first['selected_scene_ids'], ['S001'])
        self.assertEqual(first['plan_hash'], plan_hash(self.app.store.plans['project_aaaaaa']))

    def test_retry_clears_public_error_and_preserves_failed_receipts(self):
        pid = 'project_aaaaaa'
        old = {'job_id': 'job_000000000001', 'project_id': pid, 'version': 'v001',
               'plan_hash': plan_hash(self.app.store.plans[pid]), 'status': 'failed',
               'resume_on_restart': True, 'internal_url': self.app.base_url}
        receipt = self.jobs.root / (old['job_id'] + '.json')
        failure = self.jobs.root / (old['job_id'] + '.failure.json')
        private_json(receipt, old)
        private_json(failure, {'code': 'WORKER_FAILED', 'message': 'original failed attempt'})
        original = {path: path.read_bytes() for path in (receipt, failure)}
        self.jobs.tickets[old['job_id']] = old
        self.app.store.set_status(pid, 'v001', status='failed', error={'code': 'WORKER_FAILED'})
        retry = self.jobs.submit(pid, 'v001')
        self.assertNotEqual(retry['job_id'], old['job_id'])
        self.assertEqual(self.app.store.status(pid, 'v001')['status'], 'queued')
        self.assertIsNone(self.app.store.status(pid, 'v001')['error'])
        # Startup/rendering must clear stale errors as well as queue acceptance.
        self.app.store.set_status(pid, 'v001', error={'code': 'WORKER_FAILED'})
        self.jobs.start()
        self.assertTrue(self.started.wait(2))
        self.assertEqual(self.app.store.status(pid, 'v001')['status'], 'rendering')
        self.assertIsNone(self.app.store.status(pid, 'v001')['error'])
        for path, value in original.items():
            self.assertEqual(path.read_bytes(), value)
        self.release.set()
        self.assertTrue(wait_until(lambda: self.jobs.active is None))

    def test_queue_cancel_not_rendered_or_restarted(self):
        self.jobs.start()
        self.jobs.submit('project_aaaaaa', 'v001')
        self.started.wait(2)
        second = self.jobs.submit('project_bbbbbb', 'v001')
        self.assertEqual(self.jobs.cancel(second['job_id'])['status'], 'cancelled')
        self.release.set()
        self.assertTrue(wait_until(lambda: self.jobs.active is None))
        self.assertEqual(self.calls, ['project_aaaaaa'])
        stored = json.loads((self.jobs.root / (second['job_id'] + '.json')).read_text())
        self.assertFalse(stored['resume_on_restart'])
        self.assertEqual(self.app.store.states['project_bbbbbb']['status'], 'interrupted')

    def test_active_cancel_preserves_interrupted_checkpoint_state(self):
        self.jobs.start()
        first = self.jobs.submit('project_aaaaaa', 'v001')
        self.started.wait(2)
        self.jobs.cancel(first['job_id'])
        self.assertTrue(wait_until(lambda: self.jobs.active is None))
        self.assertEqual(self.jobs.tickets[first['job_id']]['status'], 'cancelled')
        self.assertEqual(self.app.store.states['project_aaaaaa']['status'], 'interrupted')

    def test_restart_autoload_only_approved_unchanged_pending(self):
        for i, pid in enumerate(self.app.store.plans):
            ticket = {'job_id': f'job_{i+1:012x}', 'project_id': pid, 'version': 'v001',
                      'plan_hash': plan_hash(self.app.store.plans[pid]), 'status': 'interrupted',
                      'resume_on_restart': True, 'internal_url': self.app.base_url}
            private_json(self.jobs.root / (ticket['job_id'] + '.json'), ticket)
        self.app.store.approved.remove('project_bbbbbb')
        self.app.store.plans['project_cccccc']['request']['topic'] = 'changed'
        self.jobs.start()
        self.assertTrue(self.started.wait(2))
        self.release.set()
        self.assertTrue(wait_until(lambda: self.jobs.active is None))
        self.assertEqual(self.calls, ['project_aaaaaa'])
        self.assertEqual(self.jobs.tickets['job_000000000002']['status'], 'blocked')
        self.assertEqual(self.jobs.tickets['job_000000000003']['status'], 'blocked')

    def test_shutdown_ticket_resumable_but_completed_never_replayed(self):
        self.jobs.start()
        first = self.jobs.submit('project_aaaaaa', 'v001')
        self.started.wait(2)
        self.jobs.close()
        path = self.jobs.root / (first['job_id'] + '.json')
        ticket = json.loads(path.read_text())
        self.assertEqual(ticket['status'], 'interrupted')
        self.assertTrue(ticket['resume_on_restart'])
        ticket['status'] = 'complete'
        private_json(path, ticket)
        fresh = DurableJobs(self.app, self.runner)
        fresh.start()
        fresh.close()
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    unittest.main()
