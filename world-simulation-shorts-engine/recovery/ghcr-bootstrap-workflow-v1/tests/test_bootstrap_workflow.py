"""NEW bootstrap executable/workflow cases only; all external effects are mocked.

The previously accepted first-registration contract's fourteen tests are not
imported or executed. Recorded immutable-parent bytes are reused as a fixture.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
import registration_contract as contract
import bootstrap_registration as client

POLICY_PATH = ROOT / 'BOOTSTRAP_POLICY.json'
WORKFLOW_PATH = ROOT / '.github/workflows/world-engine-ghcr-first-registration.yml'
NOW_MS = 1793257200000
HEAD = 'a' * 40
RUN_ID = '42123456789'
POLICY_SHA = 'b' * 64
WORKFLOW_SHA = 'c' * 64
SECRET = 'SYNTHETIC_SECRET_DO_NOT_EMIT_123'


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def approved_policy():
    value = json.loads(POLICY_PATH.read_text())
    value.update(status='APPROVED_FOR_SEPARATE_REGISTRATION', executionEnabled=True,
                 skopeoVersion='skopeo version 1.15.0')
    return value


def owner_attestation():
    return {
        'schema': 'WORLD_ENGINE_BOOTSTRAP_OWNER_ATTESTATION_V1',
        'reviewedHeadSHA': HEAD,
        'policySHA256': POLICY_SHA,
        'workflowSHA256': WORKFLOW_SHA,
        'observedAtUnixMs': NOW_MS,
        'namespaceExclusiveWindowConfirmed': True,
        'creatorAdminAcknowledged': True,
        'candidateAbsence': {
            'schema': 'WORLD_ENGINE_PACKAGE_ABSENCE_PROOF_V1',
            'repository': contract.CANDIDATE_PACKAGE,
            'status': 'CONFIRMED_ABSENT',
            'httpStatus': 404,
            'authorizedMetadataRead': True,
            'readPrincipalRole': 'NAMESPACE_OWNER',
            'source': 'NAMESPACE_OWNER_UI_READ_ONLY',
            'proofSHA256': 'd' * 64,
            'observedAtUnixMs': NOW_MS,
        },
        'successfulPackageAccessBefore': {
            'schema': 'WORLD_ENGINE_READ_ONLY_PACKAGE_ACCESS_SNAPSHOT_V1',
            'packageRepository': contract.SUCCESS_PACKAGE,
            'subjectRepository': contract.BOOTSTRAP_REPOSITORY,
            'source': 'PACKAGE_SETTINGS_READ_ONLY',
            'proofSHA256': 'e' * 64,
            'observedAtUnixMs': NOW_MS,
            'linked': False,
            'permissionInheritance': False,
            'actionsRole': 'NONE',
            'canWrite': False,
            'canDelete': False,
            'mutationProbePerformed': False,
        },
    }


def dispatch_event(attestation=None):
    return {
        'sender': {'login': contract.OWNER},
        'repository': {'id': 1438054766, 'full_name': contract.BOOTSTRAP_REPOSITORY,
                       'private': False, 'visibility': 'public', 'default_branch': 'main'},
        'inputs': {
            'approval': 'FIRST_REGISTER_CANDIDATE_PARENT_COPY_ONCE',
            'reviewed_head': HEAD,
            'policy_sha256': POLICY_SHA,
            'zero_cost_confirmed': 'true',
            'budget_stop_confirmed': 'true',
            'owner_attestation': json.dumps(attestation or owner_attestation()),
        },
    }


def dispatch_env():
    return {
        'GITHUB_ACTIONS': 'true',
        'GITHUB_EVENT_NAME': 'workflow_dispatch',
        'GITHUB_REPOSITORY': contract.BOOTSTRAP_REPOSITORY,
        'GITHUB_REPOSITORY_ID': '1438054766',
        'GITHUB_REPOSITORY_OWNER': contract.OWNER,
        'GITHUB_REF': 'refs/heads/main',
        'GITHUB_SHA': HEAD,
        'GITHUB_ACTOR': contract.OWNER,
        'GITHUB_TRIGGERING_ACTOR': contract.OWNER,
        'GITHUB_RUN_ID': RUN_ID,
        'GITHUB_RUN_ATTEMPT': '1',
        'GITHUB_WORKFLOW_REF': contract.BOOTSTRAP_REPOSITORY + '/.github/workflows/world-engine-ghcr-first-registration.yml@refs/heads/main',
        'GITHUB_WORKFLOW_SHA': HEAD,
        'RUNNER_ENVIRONMENT': 'github-hosted',
        'RUNNER_OS': 'Linux',
        'ImageOS': 'ubuntu24',
    }


class WorkflowBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)

    def test_01_manual_only_checkout_and_token_boundary(self):
        workflow = self.workflow
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        self.assertEqual(workflow['permissions'], {})
        jobs = workflow['jobs']
        self.assertEqual(set(jobs), {'first-registration'})
        job = jobs['first-registration']
        self.assertEqual(job['permissions'], {'contents': 'read', 'packages': 'write'})
        steps = job['steps']
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]['uses'], 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683')
        self.assertEqual(steps[0]['with']['ref'], '${{ github.sha }}')
        self.assertEqual(steps[0]['with']['persist-credentials'], 'false')
        self.assertNotIn('env', steps[1])
        self.assertEqual(steps[2]['env'], {'GHCR_BOOTSTRAP_TOKEN': '${{ github.token }}'})
        for step in steps[1:]:
            self.assertNotIn('${{ inputs.', step['run'])
            self.assertNotIn('continue-on-error', step)
        self.assertIn('bootstrap_registration.py preflight', steps[1]['run'])
        self.assertIn('bootstrap_registration.py register', steps[2]['run'])

    def test_02_serialization_cost_owner_and_single_attempt_controls(self):
        workflow = self.workflow
        self.assertEqual(workflow['concurrency'], {
            'group': 'world-engine-candidate-first-registration',
            'cancel-in-progress': 'false',
        })
        job = workflow['jobs']['first-registration']
        self.assertEqual(job['runs-on'], 'ubuntu-24.04')
        self.assertLessEqual(int(job['timeout-minutes']), 15)
        condition = job['if']
        for required in (
            "github.event_name == 'workflow_dispatch'",
            "github.repository == '" + contract.BOOTSTRAP_REPOSITORY + "'",
            "github.ref == 'refs/heads/main'",
            "github.actor == '" + contract.OWNER + "'",
            "github.triggering_actor == '" + contract.OWNER + "'",
            'github.run_attempt == 1', 'inputs.reviewed_head == github.sha',
            'inputs.zero_cost_confirmed == true',
            'inputs.budget_stop_confirmed == true',
        ):
            self.assertIn(required, condition)
        inputs = workflow['on']['workflow_dispatch']['inputs']
        self.assertEqual(inputs['zero_cost_confirmed']['default'], 'false')
        self.assertEqual(inputs['budget_stop_confirmed']['default'], 'false')
        self.assertEqual(set(inputs), {'approval', 'reviewed_head', 'policy_sha256',
                                     'zero_cost_confirmed', 'budget_stop_confirmed',
                                     'owner_attestation'})


class FakeEffects:
    """Explicit effect spy; no inherited network or subprocess implementation."""
    def __init__(self):
        self.events = []
        self.raw = (ROOT / 'tests/fixtures/parent-registry-manifest.json').read_bytes()
        self.clock = NOW_MS
        self.metadata = {
            'id': 1438054766, 'full_name': contract.BOOTSTRAP_REPOSITORY,
            'private': False, 'default_branch': 'main', 'archived': False,
        }
        self.package = {
            'id': 1234567, 'name': 'world-engine-vulkan-surface-candidates',
            'package_type': 'container', 'visibility': 'private',
            'repository': {'full_name': contract.BOOTSTRAP_REPOSITORY},
        }
        self.version = 'skopeo version 1.15.0'
        self.capacity = 2147483648
        self.exists_before = False
        self.candidate_error = None
        self.inspect_overrides = {}
        self.copy_error = None
        self.copy_calls = 0
        self.before_copy = None

    def now_ms(self):
        return self.clock

    def repository_metadata(self, token=None):
        self.events.append(('repository', token is not None))
        return self.metadata

    def candidate_metadata(self, token=None):
        self.events.append(('candidate', token is not None))
        if self.candidate_error:
            raise self.candidate_error
        return self.package if self.copy_calls or self.exists_before else None

    def tool_version(self):
        self.events.append(('tool',))
        return self.version

    def free_bytes(self):
        self.events.append(('capacity',))
        return self.capacity

    def inspect_raw(self, image, token=None):
        self.events.append(('inspect', image, token is not None))
        value = self.inspect_overrides.get(image, self.raw)
        if callable(value):
            return value(self)
        if isinstance(value, Exception):
            raise value
        return value

    def copy_once(self, source, destination, token):
        self.events.append(('copy', source, destination, token == SECRET))
        if self.before_copy:
            self.before_copy()
        self.copy_calls += 1
        if self.copy_error:
            raise self.copy_error


class BootstrapRuntimeTests(unittest.TestCase):
    def setUp(self):
        # A mistaken use of real effects aborts the test before an external call.
        self.subprocess_guard = mock.patch('subprocess.run', side_effect=AssertionError('REAL_SUBPROCESS_FORBIDDEN'))
        self.network_guard = mock.patch('urllib.request.build_opener', side_effect=AssertionError('REAL_NETWORK_FORBIDDEN'))
        self.subprocess_guard.start()
        self.network_guard.start()
        self.addCleanup(self.subprocess_guard.stop)
        self.addCleanup(self.network_guard.stop)
        self.policy = approved_policy()
        self.attestation = owner_attestation()
        self.context = client.derive_context(dispatch_env(), dispatch_event())
        self.effects = FakeEffects()
        self.temporary = tempfile.TemporaryDirectory(prefix='bootstrap-synthetic-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.output = io.StringIO()

    def prepare(self):
        return client.preflight(self.policy, self.context, self.attestation,
                                self.effects, POLICY_SHA, WORKFLOW_SHA)

    def run_register(self, prepared=None):
        if prepared is None:
            prepared = self.prepare()
        with mock.patch('sys.stdout', self.output):
            return client.register(self.policy, self.context, self.attestation,
                                   self.effects, POLICY_SHA, WORKFLOW_SHA,
                                   SECRET, self.directory, prepared)

    def read_outcome(self):
        return json.loads((self.directory / 'OUTCOME.json').read_bytes())

    def test_03_committed_draft_stops_before_external_effects(self):
        self.policy = json.loads(POLICY_PATH.read_bytes())
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_DRAFT_POLICY_NOT_AUTHORIZED'):
            self.prepare()
        self.assertEqual(self.effects.events, [])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_04_dispatch_context_rejects_wrong_execution_identity(self):
        changes = {
            'GITHUB_EVENT_NAME': 'push', 'GITHUB_REPOSITORY': contract.ORIGINAL_REPOSITORY,
            'GITHUB_ACTOR': 'other-user', 'GITHUB_TRIGGERING_ACTOR': 'other-user',
            'GITHUB_REF': 'refs/heads/recovery', 'GITHUB_RUN_ATTEMPT': '2',
            'RUNNER_ENVIRONMENT': 'self-hosted', 'RUNNER_OS': 'Windows',
            'ImageOS': 'ubuntu22', 'GITHUB_SHA': 'f' * 40,
            'GITHUB_WORKFLOW_SHA': 'f' * 40, 'GITHUB_ACTIONS': 'false',
            'GITHUB_REPOSITORY_OWNER': 'other-user', 'GITHUB_REPOSITORY_ID': '1',
            'GITHUB_WORKFLOW_REF': contract.ORIGINAL_REPOSITORY + '/.github/workflows/called.yml@refs/heads/main',
        }
        for name, value in changes.items():
            with self.subTest(name=name):
                env = dispatch_env()
                env[name] = value
                with self.assertRaises(RuntimeError):
                    client.derive_context(env, dispatch_event())
        self.assertEqual(self.effects.events, [])

    def test_05_dispatch_event_rejects_nonowner_private_unreviewed_or_uncosted_run(self):
        events = []
        for path, value in (
            (('sender', 'login'), 'other-user'),
            (('repository', 'private'), True),
            (('repository', 'default_branch'), 'other'),
            (('inputs', 'approval'), 'yes'),
            (('inputs', 'reviewed_head'), 'f' * 40),
            (('inputs', 'zero_cost_confirmed'), 'false'),
            (('inputs', 'budget_stop_confirmed'), 'false'),
            (('inputs', 'zero_cost_confirmed'), 1),
        ):
            event = dispatch_event()
            event[path[0]][path[1]] = value
            events.append((path, event))
        for name, event in events:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                client.derive_context(dispatch_env(), event)

    def test_06_owner_evidence_hash_age_and_exclusive_window_gate_before_effects(self):
        edits = (
            ('reviewedHeadSHA', 'f' * 40), ('policySHA256', 'f' * 64),
            ('workflowSHA256', 'f' * 64), ('observedAtUnixMs', NOW_MS - 600001),
            ('observedAtUnixMs', NOW_MS + 1),
            ('namespaceExclusiveWindowConfirmed', False), ('creatorAdminAcknowledged', False),
        )
        for field, value in edits:
            with self.subTest(field=field, value=value):
                self.attestation = owner_attestation()
                self.attestation[field] = value
                with self.assertRaises(RuntimeError):
                    self.prepare()
        self.assertEqual(self.effects.events, [])

    def test_07_nested_owner_absence_and_old_acl_proofs_must_remain_fresh(self):
        for field in ('candidateAbsence', 'successfulPackageAccessBefore'):
            with self.subTest(field=field):
                self.attestation = owner_attestation()
                self.attestation[field]['observedAtUnixMs'] = NOW_MS - 600001
                with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_OWNER_PROOF_STALE_OR_FUTURE'):
                    self.prepare()
        self.assertEqual(self.effects.events, [])

    def test_08_repository_tool_disk_and_existing_package_gate_new_execution(self):
        conditions = (
            ('private_repository', lambda e: e.metadata.update(private=True)),
            ('wrong_repository_id', lambda e: e.metadata.update(id=1438054767)),
            ('wrong_tool', lambda e: setattr(e, 'version', 'skopeo version 1.14.0')),
            ('disk_full', lambda e: setattr(e, 'capacity', 2147483647)),
        )
        for name, mutate in conditions:
            with self.subTest(name=name):
                self.effects = FakeEffects()
                mutate(self.effects)
                with self.assertRaises(RuntimeError):
                    self.prepare()
                self.assertEqual(self.effects.copy_calls, 0)
                self.assertFalse((self.directory / 'INTENT.json').exists())

        self.effects = FakeEffects()
        self.effects.exists_before = True
        prepared = self.prepare()
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_CANDIDATE_PACKAGE_ALREADY_EXISTS'):
            self.run_register(prepared)
        self.assertEqual(self.effects.copy_calls, 0)
        self.assertFalse((self.directory / 'INTENT.json').exists())

    def test_09_ambiguous_metadata_read_never_becomes_absence_proof(self):
        for error in (RuntimeError('401'), RuntimeError('403'), TimeoutError('network')):
            with self.subTest(error=type(error).__name__):
                self.effects = FakeEffects()
                prepared = self.prepare()
                self.effects.candidate_error = error
                with self.assertRaises(Exception):
                    self.run_register(prepared)
                self.assertEqual(self.effects.copy_calls, 0)

    def test_10_source_raw_digest_and_success_tag_drift_block_before_copy(self):
        for address in (client.SOURCE_IMAGE, client.SUCCESS_TAG):
            with self.subTest(address=address):
                self.effects = FakeEffects()
                self.effects.inspect_overrides[address] = self.effects.raw + b'\n'
                with self.assertRaises(RuntimeError):
                    self.prepare()
                self.assertEqual(self.effects.copy_calls, 0)

    def test_11_preflight_binds_fixed_parent_unique_tag_without_write(self):
        prepared = self.prepare()
        self.assertEqual(prepared['status'], 'PREPARED_NOT_COPIED')
        self.assertEqual(prepared['destination'], contract.CANDIDATE_PACKAGE + ':' + contract.bootstrap_tag(RUN_ID))
        self.assertEqual(prepared['sourceRegistryDigest'], contract.SUCCESS_DIGEST)
        self.assertEqual(prepared['manifestBytes'], 15994)
        self.assertFalse(prepared['live404IsAuthoritative'])
        self.assertFalse(prepared['normalPublicationReady'])
        self.assertEqual(self.effects.copy_calls, 0)
        self.assertEqual(list(self.directory.iterdir()), [])
        other = dict(self.context, runId=str(int(RUN_ID) + 1))
        next_receipt = client.preflight(self.policy, other, self.attestation,
                                       self.effects, POLICY_SHA, WORKFLOW_SHA)
        self.assertNotEqual(next_receipt['destination'], prepared['destination'])

    def test_12_register_requires_exact_bound_preflight_and_rechecks_proof_age(self):
        original = self.prepare()
        for field, value in (
            ('policySHA256', 'f' * 64), ('workflowSHA256', 'f' * 64),
            ('contextBindingSHA256', 'f' * 64), ('destination', 'other'),
            ('sourceConfigDigest', 'sha256:' + 'f' * 64),
        ):
            with self.subTest(field=field):
                prepared = copy.deepcopy(original)
                prepared[field] = value
                with self.assertRaises(RuntimeError):
                    self.run_register(prepared)
                self.assertEqual(self.effects.copy_calls, 0)
        self.effects.clock = NOW_MS + 600001
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_OWNER_PROOF_STALE_OR_FUTURE'):
            self.run_register(original)
        self.assertFalse((self.directory / 'INTENT.json').exists())

    def test_13_intent_is_exclusive_fsynced_and_logged_before_single_copy(self):
        original_fsync = client.os.fsync
        syncs = []
        def fsync(fd):
            syncs.append(fd)
            return original_fsync(fd)
        def before_copy():
            self.assertGreaterEqual(len(syncs), 2)
            intent = json.loads((self.directory / 'INTENT.json').read_bytes())
            self.assertEqual(intent['logicalCopyAttempt'], 1)
            self.assertEqual(intent['retryCount'], 0)
            self.assertEqual(intent['deleteRequests'], 0)
            self.assertIn('WORLD_ENGINE_SAFE_RECEIPT_B64=', self.output.getvalue())
        self.effects.before_copy = before_copy
        with mock.patch.object(client.os, 'fsync', side_effect=fsync):
            outcome = self.run_register()
        copies = [x for x in self.effects.events if x[0] == 'copy']
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0][1], contract.SOURCE_IMAGE)
        self.assertEqual(copies[0][2], contract.CANDIDATE_PACKAGE + ':' + contract.bootstrap_tag(RUN_ID))
        self.assertTrue(copies[0][3])
        self.assertEqual(outcome['status'], 'COPY_OBSERVED_PENDING_INDEPENDENT_POST_JOB_ADMIN_REVIEW')
        self.assertFalse(outcome['firstRegistrationPass'])
        self.assertFalse(outcome['normalPublicationReady'])
        self.assertEqual(outcome['bootstrapTokenExpiry'], 'NOT_OBSERVABLE_INSIDE_OWN_JOB')
        self.assertEqual((self.directory / 'INTENT.json').stat().st_mode & 0o777, 0o600)

    def test_14_timeout_keeps_unknown_outcome_without_retry_or_secret_error(self):
        self.effects.copy_error = TimeoutError(SECRET + ' RAW_STDERR')
        with self.assertRaisesRegex(RuntimeError, '^BOOTSTRAP_COPY_OR_POSTCHECK_BLOCKED_NO_RETRY$'):
            self.run_register()
        outcome = self.read_outcome()
        self.assertEqual(outcome['status'], 'COPY_OUTCOME_UNCONFIRMED_NO_RETRY')
        self.assertEqual(self.effects.copy_calls, 1)
        preserved = ''.join(p.read_text() for p in self.directory.iterdir()) + self.output.getvalue()
        self.assertNotIn(SECRET, preserved)
        self.assertNotIn('RAW_STDERR', preserved)
        self.assertEqual(outcome['retryCount'], 0)
        self.assertEqual(outcome['deleteRequests'], 0)

    def test_15_existing_intent_prevents_another_logical_copy(self):
        prepared = self.prepare()
        client.exclusive_receipt(self.directory, 'INTENT.json', {'status': 'EXISTING_UNRESOLVED_INTENT'})
        before = (self.directory / 'INTENT.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_register(prepared)
        self.assertEqual(self.effects.copy_calls, 0)
        self.assertEqual((self.directory / 'INTENT.json').read_bytes(), before)

    def test_16_postcopy_association_or_visibility_failure_quarantines_without_repair(self):
        for name, mutate in (
            ('wrong_link', lambda e: e.package['repository'].update(full_name=contract.ORIGINAL_REPOSITORY)),
            ('public', lambda e: e.package.update(visibility='public')),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                self.directory = Path(directory)
                self.effects = FakeEffects()
                mutate(self.effects)
                with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_COPY_OR_POSTCHECK_BLOCKED_NO_RETRY'):
                    self.run_register()
                self.assertEqual(self.effects.copy_calls, 1)
                self.assertEqual(self.read_outcome()['status'], 'COPY_RETURNED_SUCCESS_POSTCHECK_BLOCKED_QUARANTINE_NO_RETRY')
                self.assertEqual(self.read_outcome()['deleteRequests'], 0)

    def test_17_postcopy_destination_or_old_success_digest_drift_blocks(self):
        destination = contract.CANDIDATE_PACKAGE + ':' + contract.bootstrap_tag(RUN_ID)
        for address in (destination, contract.CANDIDATE_PACKAGE + '@' + contract.SUCCESS_DIGEST, client.SUCCESS_TAG):
            with self.subTest(address=address), tempfile.TemporaryDirectory() as directory:
                self.directory = Path(directory)
                self.effects = FakeEffects()
                self.effects.inspect_overrides[address] = lambda e: e.raw + (b'\n' if e.copy_calls else b'')
                with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_COPY_OR_POSTCHECK_BLOCKED_NO_RETRY'):
                    self.run_register()
                self.assertEqual(self.effects.copy_calls, 1)
                self.assertFalse(self.read_outcome()['firstRegistrationPass'])

    def test_18_bound_receipts_never_include_token_raw_errors_or_admin_success_claim(self):
        result = self.run_register()
        saved = self.read_outcome()
        self.assertEqual(saved, result)
        self.assertEqual(saved['creatorAdminRole'], 'REQUIRES_INDEPENDENT_ADMIN_READ_ONLY_PROOF')
        self.assertEqual(saved['oldPackagePostACL'], 'REQUIRES_INDEPENDENT_ADMIN_READ_ONLY_PROOF')
        self.assertFalse(saved['seedIsVulkanCandidate'])
        self.assertFalse(saved['imageBuilt'])
        self.assertFalse(saved['gpuExecuted'])
        for path in self.directory.iterdir():
            self.assertLessEqual(path.stat().st_size, 8193)
            self.assertNotIn(SECRET, path.read_text())
            self.assertNotIn('Authorization', path.read_text())
        self.assertNotIn(SECRET, self.output.getvalue())

    def test_19_json_parser_rejects_duplicate_nonfinite_oversized_and_extra_attestation(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b' ' * 16385):
            with self.subTest(raw_size=len(raw)), self.assertRaises(RuntimeError):
                client.load_json_strict(raw)
        self.attestation['environment'] = SECRET
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_OWNER_ATTESTATION_SCHEMA_INVALID'):
            self.prepare()
        self.assertEqual(self.effects.events, [])

    def test_20_receipt_writes_reject_symlink_overwrite_and_oversize(self):
        target = self.directory / 'unrelated'
        target.write_text('PRESERVE')
        (self.directory / 'INTENT.json').symlink_to(target)
        with self.assertRaises(OSError):
            client.exclusive_receipt(self.directory, 'INTENT.json', {'status': 'forbidden'})
        self.assertEqual(target.read_text(), 'PRESERVE')
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_RECEIPT_SIZE_INVALID'):
            client.exclusive_receipt(self.directory, 'OUTCOME.json', {'tooLarge': 'x' * 8192})
        self.assertFalse((self.directory / 'OUTCOME.json').exists())

    def test_21_live_copy_adapter_uses_exact_endpoints_preserve_digest_zero_retry_no_source_creds(self):
        live = client.LiveEffects(self.policy, self.directory)
        destination = contract.CANDIDATE_PACKAGE + ':' + contract.bootstrap_tag(RUN_ID)
        with mock.patch.object(live, '_command', return_value=b'') as command:
            live.copy_once(contract.SOURCE_IMAGE, destination, SECRET)
        args, kwargs = command.call_args
        self.assertEqual(args[0], ['copy', '--preserve-digests', '--retry-times=0', '--src-no-creds',
                                  'docker://' + contract.SOURCE_IMAGE, 'docker://' + destination])
        self.assertEqual(args[1], 600)
        self.assertEqual(kwargs, {'capture': False, 'auth_token': SECRET})
        for wrong_source, wrong_destination in (
            (contract.SUCCESS_PACKAGE + ':latest', destination),
            (contract.SOURCE_IMAGE, contract.SUCCESS_PACKAGE + ':overwrite'),
        ):
            with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_COPY_ENDPOINT_FORBIDDEN'):
                live.copy_once(wrong_source, wrong_destination, SECRET)

    def test_22_live_api_errors_and_redirects_never_prove_authoritative_absence(self):
        live = client.LiveEffects(self.policy, self.directory)
        for status in (401, 403, 500):
            error = urllib.error.HTTPError('https://api.github.com', status, SECRET, {}, None)
            opener = mock.Mock()
            opener.open.side_effect = error
            with mock.patch('urllib.request.build_opener', return_value=opener):
                with self.assertRaisesRegex(RuntimeError, '^BOOTSTRAP_API_READ_BLOCKED$'):
                    live.candidate_metadata(SECRET)
        error = urllib.error.HTTPError('https://api.github.com', 404, 'hidden', {}, None)
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch('urllib.request.build_opener', return_value=opener):
            self.assertIsNone(live.candidate_metadata(SECRET))
        # The 404 remains secondary: no source/new plan can be obtained without
        # the separately owner-attested, hash-bound fresh absence metadata.
        del self.attestation['candidateAbsence']
        with self.assertRaises(RuntimeError):
            self.prepare()
        with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_API_REDIRECT_FORBIDDEN'):
            client._NoRedirect().redirect_request(None, None, 302, 'move', {}, 'https://evil.invalid')

    def test_23_live_command_hides_credentials_stderr_and_removes_private_authfile(self):
        live = client.LiveEffects(self.policy, self.directory)
        observed = {}
        def subprocess_spy(argv, **kwargs):
            observed['argv'] = argv
            observed['env'] = kwargs['env']
            observed['kwargs'] = kwargs
            auth_path = Path(kwargs['env']['REGISTRY_AUTH_FILE'])
            observed['auth_path'] = auth_path
            observed['auth'] = json.loads(auth_path.read_bytes())
            self.assertEqual(auth_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(auth_path.parent.stat().st_mode & 0o777, 0o700)
            return type('Completed', (), {'returncode': 0})()
        with mock.patch.object(Path, 'is_file', return_value=True), mock.patch('subprocess.run', side_effect=subprocess_spy):
            live.copy_once(contract.SOURCE_IMAGE, contract.CANDIDATE_PACKAGE + ':' + contract.bootstrap_tag(RUN_ID), SECRET)
        self.assertNotIn(SECRET, ' '.join(observed['argv']))
        self.assertNotIn(SECRET, json.dumps(observed['env']))
        self.assertEqual(observed['kwargs']['stderr'], client.subprocess.DEVNULL)
        self.assertEqual(observed['kwargs']['stdin'], client.subprocess.DEVNULL)
        self.assertFalse(observed['kwargs']['check'])
        self.assertNotIn('shell', observed['kwargs'])
        self.assertFalse(observed['auth_path'].exists())
        self.assertNotIn('GHCR_BOOTSTRAP_TOKEN', observed['env'])
        self.assertEqual(set(observed['env']), {'PATH', 'LANG', 'HOME', 'REGISTRY_AUTH_FILE'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
