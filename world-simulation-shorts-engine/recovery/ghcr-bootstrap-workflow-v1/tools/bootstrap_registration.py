"""One-shot, fail-closed first registration; never builds or changes an image.

Preparation tests inject Effects. Import performs no network, subprocess or writes. The
committed policy remains DRAFT; real copy additionally requires owner-reviewed
fresh metadata proofs and a separately approved direct manual dispatch.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# -I deliberately excludes the script directory from sys.path. Load only the
# adjacent, reviewed contract, rather than any ambient Python search location.
import importlib.util
_spec = importlib.util.spec_from_file_location(
    '_world_engine_registration_contract', Path(__file__).with_name('registration_contract.py'))
_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contract)

OWNER = _contract.OWNER
BOOTSTRAP_REPOSITORY = _contract.BOOTSTRAP_REPOSITORY
SOURCE_IMAGE = _contract.SOURCE_IMAGE
CANDIDATE_PACKAGE = _contract.CANDIDATE_PACKAGE
SUCCESS_DIGEST = _contract.SUCCESS_DIGEST
SUCCESS_TAG = (_contract.SUCCESS_PACKAGE
    + ':g2-diagnostics-v1-27f9fa5c133a-40767632198')
APPROVAL = 'FIRST_REGISTER_CANDIDATE_PARENT_COPY_ONCE'
WORKFLOW_PATH = '.github/workflows/world-engine-ghcr-first-registration.yml'
POLICY_PATH = 'BOOTSTRAP_POLICY.json'
POLICY_KEYS = {'schema', 'status', 'executionEnabled', 'bootstrapRepository',
    'bootstrapRepositoryId', 'sourceImage', 'candidateRepository', 'skopeoVersion',
    'maxProofAgeSeconds', 'commandTimeoutSeconds', 'copyTimeoutSeconds',
    'minFreeBytes', 'independentPostJobReviewRequired'}
ATTESTATION_KEYS = {'schema', 'reviewedHeadSHA', 'policySHA256', 'workflowSHA256',
    'observedAtUnixMs', 'candidateAbsence', 'successfulPackageAccessBefore',
    'namespaceExclusiveWindowConfirmed', 'creatorAdminAcknowledged'}
INPUT_KEYS = {'approval', 'reviewed_head', 'policy_sha256', 'zero_cost_confirmed',
    'budget_stop_confirmed', 'owner_attestation'}
HASH_RE = re.compile(r'[a-f0-9]{64}')


def require(value, code):
    if not value:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def load_json_strict(raw, max_bytes=16384):
    if isinstance(raw, str):
        raw = raw.encode()
    require(type(raw) is bytes and len(raw) <= max_bytes, 'BOOTSTRAP_JSON_SIZE_INVALID')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'BOOTSTRAP_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def constant(_):
        raise RuntimeError('BOOTSTRAP_NONFINITE_JSON_FORBIDDEN')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise RuntimeError('BOOTSTRAP_JSON_INVALID') from None


def derive_context(env, event):
    inputs = event.get('inputs') if isinstance(event, dict) else None
    require(isinstance(inputs, dict) and set(inputs) == INPUT_KEYS,
            'BOOTSTRAP_DISPATCH_INPUTS_INVALID')
    require(event.get('sender', {}).get('login') == OWNER,
            'BOOTSTRAP_OWNER_DISPATCH_REQUIRED')
    repository = event.get('repository', {})
    require(repository.get('full_name') == BOOTSTRAP_REPOSITORY
        and repository.get('private') is False
        and repository.get('default_branch') == 'main',
        'BOOTSTRAP_PUBLIC_REPOSITORY_EVENT_REQUIRED')
    require(env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
        and env.get('GITHUB_ACTIONS') == 'true'
        and env.get('GITHUB_REPOSITORY') == BOOTSTRAP_REPOSITORY
        and env.get('GITHUB_REPOSITORY_OWNER') == OWNER
        and env.get('GITHUB_REPOSITORY_ID') == '1438054766'
        and env.get('GITHUB_ACTOR') == OWNER
        and env.get('GITHUB_TRIGGERING_ACTOR') == OWNER
        and env.get('GITHUB_REF') == 'refs/heads/main'
        and env.get('GITHUB_RUN_ATTEMPT') == '1'
        and env.get('RUNNER_ENVIRONMENT') == 'github-hosted'
        and env.get('RUNNER_OS') == 'Linux'
        and env.get('ImageOS') == 'ubuntu24',
        'BOOTSTRAP_MANUAL_STANDARD_RUNNER_CONTEXT_REQUIRED')
    sha = env.get('GITHUB_SHA', '')
    run_id = env.get('GITHUB_RUN_ID', '')
    require(re.fullmatch('[a-f0-9]{40}', sha) and inputs['reviewed_head'] == sha
        and env.get('GITHUB_WORKFLOW_SHA') == sha
        and env.get('GITHUB_WORKFLOW_REF') == BOOTSTRAP_REPOSITORY
            + '/' + WORKFLOW_PATH + '@refs/heads/main'
        and inputs['approval'] == APPROVAL,
        'BOOTSTRAP_EXACT_REVIEWED_WORKFLOW_REQUIRED')
    _contract.bootstrap_tag(run_id)
    require(all(value is True or (type(value) is str and value == 'true')
        for value in (inputs['zero_cost_confirmed'], inputs['budget_stop_confirmed'])),
        'BOOTSTRAP_FRESH_COST_APPROVAL_REQUIRED')
    require(type(inputs['policy_sha256']) is str
        and HASH_RE.fullmatch(inputs['policy_sha256']),
        'BOOTSTRAP_POLICY_HASH_INPUT_INVALID')
    return {'repository': BOOTSTRAP_REPOSITORY, 'repositoryId': repository.get('id'),
        'sha': sha, 'runId': run_id, 'runAttempt': 1,
        'policySHA256': inputs['policy_sha256'], 'actor': OWNER,
        'ref': 'refs/heads/main', 'event': 'workflow_dispatch',
        'runner': 'github-hosted-standard-ubuntu-24.04',
        'zeroCostConfirmed': True, 'budgetStopConfirmed': True}


def validate_policy(policy, context, attestation, now_ms, policy_sha, workflow_sha):
    require(isinstance(policy, dict) and set(policy) == POLICY_KEYS,
            'BOOTSTRAP_POLICY_SCHEMA_INVALID')
    require(policy['schema'] == 'WORLD_ENGINE_GHCR_BOOTSTRAP_WORKFLOW_POLICY_V1'
        and policy['status'] == 'APPROVED_FOR_SEPARATE_REGISTRATION'
        and policy['executionEnabled'] is True,
        'BOOTSTRAP_DRAFT_POLICY_NOT_AUTHORIZED')
    require(policy['bootstrapRepository'] == BOOTSTRAP_REPOSITORY
        and type(policy['bootstrapRepositoryId']) is int
        and policy['bootstrapRepositoryId'] == 1438054766
        and context.get('repository') == BOOTSTRAP_REPOSITORY
        and context.get('repositoryId') == policy['bootstrapRepositoryId']
        and policy['sourceImage'] == SOURCE_IMAGE
        and policy['candidateRepository'] == CANDIDATE_PACKAGE
        and policy['independentPostJobReviewRequired'] is True,
        'BOOTSTRAP_FIXED_REPOSITORY_POLICY_REQUIRED')
    require(context.get('actor') == OWNER and context.get('ref') == 'refs/heads/main',
            'BOOTSTRAP_OWNER_MAIN_CONTEXT_REQUIRED')
    require(type(policy['skopeoVersion']) is str
        and re.fullmatch(r'skopeo version [0-9]+\.[0-9]+\.[0-9]+', policy['skopeoVersion'])
        and type(policy['maxProofAgeSeconds']) is int
        and 1 <= policy['maxProofAgeSeconds'] <= 600
        and type(policy['commandTimeoutSeconds']) is int
        and 1 <= policy['commandTimeoutSeconds'] <= 30
        and type(policy['copyTimeoutSeconds']) is int
        and 1 <= policy['copyTimeoutSeconds'] <= 600
        and type(policy['minFreeBytes']) is int
        and policy['minFreeBytes'] >= 2147483648,
        'BOOTSTRAP_TOOL_TIMEOUT_OR_CAPACITY_POLICY_INVALID')
    require(isinstance(attestation, dict) and set(attestation) == ATTESTATION_KEYS,
            'BOOTSTRAP_OWNER_ATTESTATION_SCHEMA_INVALID')
    require(attestation['schema'] == 'WORLD_ENGINE_BOOTSTRAP_OWNER_ATTESTATION_V1'
        and attestation['reviewedHeadSHA'] == context.get('sha')
        and attestation['policySHA256'] == context.get('policySHA256') == policy_sha
        and attestation['workflowSHA256'] == workflow_sha
        and HASH_RE.fullmatch(policy_sha or '') and HASH_RE.fullmatch(workflow_sha or '')
        and attestation['namespaceExclusiveWindowConfirmed'] is True
        and attestation['creatorAdminAcknowledged'] is True,
        'BOOTSTRAP_OWNER_ATTESTATION_BINDING_REQUIRED')
    require(isinstance(attestation['candidateAbsence'], dict)
        and isinstance(attestation['successfulPackageAccessBefore'], dict),
        'BOOTSTRAP_OWNER_PROOF_OBJECTS_REQUIRED')
    for observed in (attestation['observedAtUnixMs'],
            attestation['candidateAbsence'].get('observedAtUnixMs'),
            attestation['successfulPackageAccessBefore'].get('observedAtUnixMs')):
        require(type(now_ms) is int and type(observed) is int
            and 0 <= now_ms - observed <= policy['maxProofAgeSeconds'] * 1000,
            'BOOTSTRAP_OWNER_PROOF_STALE_OR_FUTURE')
    plan = {'schema': 'WORLD_ENGINE_GHCR_FIRST_REGISTRATION_PLAN_V1',
        'status': 'APPROVED_FOR_SEPARATE_REGISTRATION',
        'separateRegistrationApprovalRecorded': True, 'approval': APPROVAL,
        'namespaceOwner': OWNER, 'namespaceType': 'USER',
        'bootstrapRepository': BOOTSTRAP_REPOSITORY,
        'workflowRepository': BOOTSTRAP_REPOSITORY,
        'githubContextRepository': context['repository'], 'reusableWorkflowUsed': False,
        'credentialKind': 'GITHUB_TOKEN', 'credentialRepository': BOOTSTRAP_REPOSITORY,
        'packagesPermission': 'write', 'contentsPermission': 'read',
        'runId': context['runId'], 'runAttempt': context['runAttempt'],
        'reviewedHeadSHA': context['sha'], 'trigger': context['event'],
        'runner': context['runner'], 'repositoryPublic': True,
        'zeroCostConfirmed': context['zeroCostConfirmed'],
        'budgetStopConfirmed': context['budgetStopConfirmed'],
        'sourceImage': SOURCE_IMAGE, 'candidateRepository': CANDIDATE_PACKAGE,
        'destination': CANDIDATE_PACKAGE + ':' + _contract.bootstrap_tag(context['runId']),
        'candidateAbsence': attestation['candidateAbsence'],
        'successfulPackageAccessBefore': attestation['successfulPackageAccessBefore'],
        'firstCreationAdminAcknowledged': True,
        'candidateDeleteCapabilityDeniedClaimed': False, 'requestedVisibility': 'private',
        'imageBuildAllowed': False, 'sourceMutationAllowed': False,
        'destructiveOperationsAllowed': False, 'gpuAllowed': False,
        'normalPublisherEnabled': False, 'existingPassTestsRerun': False}
    _contract.validate_first_registration_plan(plan)
    return plan


def _check_repository(metadata, policy):
    require(isinstance(metadata, dict)
        and metadata.get('id') == policy['bootstrapRepositoryId']
        and type(metadata.get('id')) is int
        and metadata.get('full_name') == BOOTSTRAP_REPOSITORY
        and metadata.get('private') is False
        and metadata.get('default_branch') == 'main'
        and metadata.get('archived') is False,
        'BOOTSTRAP_LIVE_PUBLIC_REPOSITORY_REQUIRED')


def _manifest(raw):
    require(type(raw) is bytes and len(raw) <= 65536
        and 'sha256:' + digest(raw) == SUCCESS_DIGEST,
        'BOOTSTRAP_FIXED_PARENT_MANIFEST_DIGEST_MISMATCH')
    parsed = load_json_strict(raw, 65536)
    config = parsed.get('config') if isinstance(parsed, dict) else None
    require(isinstance(parsed, dict) and parsed.get('schemaVersion') == 2 and isinstance(config, dict)
        and re.fullmatch(r'sha256:[a-f0-9]{64}', config.get('digest', ''))
        and isinstance(parsed.get('layers'), list),
        'BOOTSTRAP_SINGLE_IMAGE_MANIFEST_REQUIRED')
    return parsed


def preflight(policy, context, attestation, effects, policy_sha, workflow_sha):
    plan = validate_policy(policy, context, attestation, effects.now_ms(),
                           policy_sha, workflow_sha)
    _check_repository(effects.repository_metadata(), policy)
    require(effects.tool_version() == policy['skopeoVersion'],
            'BOOTSTRAP_REVIEWED_SKOPEO_VERSION_REQUIRED')
    require(effects.free_bytes() >= policy['minFreeBytes'],
            'BOOTSTRAP_DISK_CAPACITY_BLOCKED')
    # Candidate metadata requires authentication. Preflight has no job token and
    # deliberately relies only on the separate fresh namespace-owner proof.
    # Registration performs a secondary authenticated existence check; its 404
    # still cannot replace the authoritative owner proof.
    source = effects.inspect_raw(SOURCE_IMAGE)
    source_manifest = _manifest(source)
    require(effects.inspect_raw(SUCCESS_TAG) == source,
            'BOOTSTRAP_SUCCESS_TAG_BEFORE_MISMATCH')
    return {'schema': 'WORLD_ENGINE_BOOTSTRAP_PREFLIGHT_V1', 'status': 'PREPARED_NOT_COPIED',
        'planBindingSHA256': _contract.binding(plan), 'policySHA256': policy_sha,
        'workflowSHA256': workflow_sha, 'contextBindingSHA256': _contract.binding(context),
        'observedAtUnixMs': effects.now_ms(), 'destination': plan['destination'],
        'sourceRegistryDigest': SUCCESS_DIGEST,
        'sourceConfigDigest': source_manifest['config']['digest'],
        'manifestBytes': len(source), 'registryWrites': 0,
        'authoritativeAbsenceSource': 'SEPARATE_FRESH_NAMESPACE_OWNER_ATTESTATION',
        'live404IsAuthoritative': False, 'normalPublicationReady': False}


def exclusive_receipt(directory, name, receipt):
    require(name in ('PREPARED.json', 'INTENT.json', 'OUTCOME.json'),
            'BOOTSTRAP_RECEIPT_NAME_INVALID')
    raw = canonical(receipt)
    require(len(raw) <= 8192, 'BOOTSTRAP_RECEIPT_SIZE_INVALID')
    directory = Path(directory)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(directory / name, flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw + b'\n')
            handle.flush()
            os.fsync(handle.fileno())
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        # Preserve partially written receipts too. Never delete or replace them.
        raise


def _emit(receipt):
    raw = canonical(receipt)
    require(len(raw) <= 8192, 'BOOTSTRAP_RECEIPT_SIZE_INVALID')
    # Base64 prevents arbitrary registry text from becoming an Actions command.
    print('WORLD_ENGINE_SAFE_RECEIPT_B64=' + base64.b64encode(raw).decode(), flush=True)


def register(policy, context, attestation, effects, policy_sha, workflow_sha,
             token, evidence_dir, prepared=None):
    # Every gate runs before the only mutation, including a fresh proof-age check.
    require(type(token) is str and 1 <= len(token) <= 4096
        and '\n' not in token and '\r' not in token,
        'BOOTSTRAP_JOB_TOKEN_REQUIRED')
    plan = validate_policy(policy, context, attestation, effects.now_ms(),
                           policy_sha, workflow_sha)
    require(isinstance(prepared, dict)
        and prepared.get('schema') == 'WORLD_ENGINE_BOOTSTRAP_PREFLIGHT_V1'
        and prepared.get('status') == 'PREPARED_NOT_COPIED'
        and prepared.get('planBindingSHA256') == _contract.binding(plan)
        and prepared.get('policySHA256') == policy_sha
        and prepared.get('workflowSHA256') == workflow_sha
        and prepared.get('contextBindingSHA256') == _contract.binding(context)
        and prepared.get('destination') == plan['destination']
        and prepared.get('sourceRegistryDigest') == SUCCESS_DIGEST
        and type(prepared.get('observedAtUnixMs')) is int
        and 0 <= effects.now_ms() - prepared['observedAtUnixMs'] <= 600000,
        'BOOTSTRAP_PREFLIGHT_BINDING_REQUIRED')
    _check_repository(effects.repository_metadata(token), policy)
    require(effects.tool_version() == policy['skopeoVersion']
        and effects.free_bytes() >= policy['minFreeBytes'],
        'BOOTSTRAP_FRESH_TOOL_AND_DISK_GATES_REQUIRED')
    require(effects.candidate_metadata(token) is None,
            'BOOTSTRAP_CANDIDATE_PACKAGE_ALREADY_EXISTS')
    source = effects.inspect_raw(SOURCE_IMAGE)
    parsed = _manifest(source)
    require(prepared.get('sourceConfigDigest') == parsed['config']['digest']
        and effects.inspect_raw(SUCCESS_TAG) == source,
        'BOOTSTRAP_PRECOPY_SOURCE_IDENTITY_MISMATCH')
    # Refresh immediately before mutation; preflight may have waited in a queue.
    validate_policy(policy, context, attestation, effects.now_ms(), policy_sha, workflow_sha)
    intent = {'schema': 'WORLD_ENGINE_BOOTSTRAP_INTENT_V1',
        'status': 'COPY_INTENT_PERSISTED_OUTCOME_NOT_YET_KNOWN',
        'planBindingSHA256': _contract.binding(plan), 'destination': plan['destination'],
        'sourceImage': SOURCE_IMAGE, 'runId': context['runId'], 'runAttempt': 1,
        'logicalCopyAttempt': 1, 'retryCount': 0, 'deleteRequests': 0,
        'normalPublicationReady': False}
    exclusive_receipt(evidence_dir, 'INTENT.json', intent)
    _emit(intent)
    copied = False
    try:
        effects.copy_once(SOURCE_IMAGE, plan['destination'], token)
        copied = True
        destination = effects.inspect_raw(plan['destination'], token)
        addressed = effects.inspect_raw(CANDIDATE_PACKAGE + '@' + SUCCESS_DIGEST, token)
        _manifest(destination)
        require(destination == source == addressed,
                'BOOTSTRAP_DESTINATION_DIGEST_OR_BYTES_MISMATCH')
        require(effects.inspect_raw(SUCCESS_TAG) == source,
                'BOOTSTRAP_SUCCESS_TAG_AFTER_MISMATCH')
        metadata = effects.candidate_metadata(token)
        require(isinstance(metadata, dict) and type(metadata.get('id')) is int
            and metadata['id'] > 0
            and metadata.get('name') == 'world-engine-vulkan-surface-candidates'
            and metadata.get('package_type') == 'container'
            and metadata.get('visibility') == 'private'
            and metadata.get('repository', {}).get('full_name') == BOOTSTRAP_REPOSITORY,
            'BOOTSTRAP_CREATED_METADATA_REQUIRES_QUARANTINE_REVIEW')
        outcome = {'schema': 'WORLD_ENGINE_BOOTSTRAP_PROVISIONAL_OUTCOME_V1',
            'status': 'COPY_OBSERVED_PENDING_INDEPENDENT_POST_JOB_ADMIN_REVIEW',
            'planBindingSHA256': _contract.binding(plan), 'destination': plan['destination'],
            'packageId': metadata['id'], 'sourceRegistryDigest': SUCCESS_DIGEST,
            'destinationTagDigest': SUCCESS_DIGEST, 'destinationAddressedDigest': SUCCESS_DIGEST,
            'sourceConfigDigest': parsed['config']['digest'], 'manifestBytesEqual': True,
            'packageAssociationRepository': BOOTSTRAP_REPOSITORY, 'visibility': 'private',
            'logicalCopyAttempts': 1, 'retryCount': 0, 'deleteRequests': 0,
            'creatorAdminRole': 'REQUIRES_INDEPENDENT_ADMIN_READ_ONLY_PROOF',
            'oldPackagePostACL': 'REQUIRES_INDEPENDENT_ADMIN_READ_ONLY_PROOF',
            'bootstrapTokenExpiry': 'NOT_OBSERVABLE_INSIDE_OWN_JOB',
            'firstRegistrationPass': False, 'seedIsVulkanCandidate': False,
            'normalPublicationReady': False, 'imageBuilt': False, 'gpuExecuted': False}
        exclusive_receipt(evidence_dir, 'OUTCOME.json', outcome)
        _emit(outcome)
        return outcome
    except Exception:
        outcome = {'schema': 'WORLD_ENGINE_BOOTSTRAP_PROVISIONAL_OUTCOME_V1',
            'status': ('COPY_RETURNED_SUCCESS_POSTCHECK_BLOCKED_QUARANTINE_NO_RETRY'
                       if copied else 'COPY_OUTCOME_UNCONFIRMED_NO_RETRY'),
            'destination': plan['destination'], 'logicalCopyAttempts': 1,
            'retryCount': 0, 'deleteRequests': 0, 'normalPublicationReady': False,
            'firstRegistrationPass': False, 'manualRegistryAndAdminReviewRequired': True}
        try:
            exclusive_receipt(evidence_dir, 'OUTCOME.json', outcome)
        finally:
            _emit(outcome)
        raise RuntimeError('BOOTSTRAP_COPY_OR_POSTCHECK_BLOCKED_NO_RETRY') from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('BOOTSTRAP_API_REDIRECT_FORBIDDEN')


@contextlib.contextmanager
def _deadline(seconds):
    """Bound the complete HTTP operation, including a slowly streamed response."""
    def expired(_signum, _frame):
        raise RuntimeError('BOOTSTRAP_API_TOTAL_TIMEOUT')
    previous_handler = signal.signal(signal.SIGALRM, expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


class LiveEffects:
    """Fixed API endpoints and bounded no-shell commands; never expose raw errors."""
    def __init__(self, policy, evidence_dir):
        self.policy = policy
        self.evidence_dir = Path(evidence_dir)

    def now_ms(self):
        return time.time_ns() // 1000000

    def free_bytes(self):
        return shutil.disk_usage(self.evidence_dir).free

    def _api(self, path, token=None, absent_allowed=False):
        require(path in ('/repos/' + BOOTSTRAP_REPOSITORY,
            '/users/' + OWNER + '/packages/container/world-engine-vulkan-surface-candidates'),
            'BOOTSTRAP_API_PATH_FORBIDDEN')
        headers = {'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'world-engine-bootstrap-v1'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request('https://api.github.com' + path, headers=headers, method='GET')
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with _deadline(self.policy['commandTimeoutSeconds']):
                with opener.open(request, timeout=self.policy['commandTimeoutSeconds']) as response:
                    require(response.status == 200, 'BOOTSTRAP_API_STATUS_BLOCKED')
                    raw = response.read(16385)
            return load_json_strict(raw, 16384)
        except urllib.error.HTTPError as exc:
            if absent_allowed and exc.code == 404:
                return None
            raise RuntimeError('BOOTSTRAP_API_READ_BLOCKED') from None
        except (OSError, ValueError):
            raise RuntimeError('BOOTSTRAP_API_READ_BLOCKED') from None

    def repository_metadata(self, token=None):
        return self._api('/repos/' + BOOTSTRAP_REPOSITORY, token)

    def candidate_metadata(self, token=None):
        return self._api('/users/' + OWNER
            + '/packages/container/world-engine-vulkan-surface-candidates', token, True)

    def _command(self, args, timeout, capture=True, auth_token=None):
        # Use only a known system executable, a minimal environment, and an empty
        # private auth file for public source reads. No implicit Docker credentials.
        require(Path('/usr/bin/skopeo').is_file(), 'BOOTSTRAP_PREINSTALLED_SKOPEO_REQUIRED')
        with tempfile.TemporaryDirectory(prefix='auth-', dir=self.evidence_dir) as temporary:
            os.chmod(temporary, 0o700)
            authfile = Path(temporary) / 'auth.json'
            auth = {'auths': {}}
            if auth_token is not None:
                auth = {'auths': {'ghcr.io': {'auth': base64.b64encode(
                    (OWNER + ':' + auth_token).encode()).decode()}}}
            fd = os.open(authfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(canonical(auth))
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': temporary,
                   'REGISTRY_AUTH_FILE': str(authfile)}
            argv = ['/usr/bin/skopeo'] + list(args)
            if args != ['--version']:
                argv[2:2] = ['--authfile', str(authfile)]
            try:
                # A regular output file avoids unbounded pipe buffering. RLIMIT
                # bounds writes even if a compromised tool/server floods output.
                import resource
                def limits():
                    resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536))
                with tempfile.TemporaryFile(dir=temporary) as output:
                    result = subprocess.run(argv, stdin=subprocess.DEVNULL,
                        stdout=output if capture else subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, env=env, timeout=timeout,
                        check=False, preexec_fn=limits if capture else None)
                    require(result.returncode == 0, 'BOOTSTRAP_SKOPEO_COMMAND_BLOCKED')
                    output.seek(0)
                    raw = output.read(65537) if capture else b''
                    require(len(raw) <= 65536, 'BOOTSTRAP_SKOPEO_OUTPUT_LIMIT')
                    return raw
            except (subprocess.TimeoutExpired, OSError, ValueError):
                raise RuntimeError('BOOTSTRAP_SKOPEO_COMMAND_BLOCKED') from None

    def tool_version(self):
        try:
            return self._command(['--version'], self.policy['commandTimeoutSeconds']).decode().strip()
        except UnicodeDecodeError:
            raise RuntimeError('BOOTSTRAP_SKOPEO_VERSION_INVALID') from None

    def inspect_raw(self, image, token=None):
        permitted = image in (SOURCE_IMAGE, SUCCESS_TAG, CANDIDATE_PACKAGE + '@' + SUCCESS_DIGEST)
        permitted = permitted or (type(image) is str and re.fullmatch(
            re.escape(CANDIDATE_PACKAGE) + r':bootstrap-parent-9378a86d8134-[1-9][0-9]{0,19}-a1', image))
        require(permitted, 'BOOTSTRAP_INSPECT_SOURCE_FORBIDDEN')
        require(token is None or image.startswith(CANDIDATE_PACKAGE),
                'BOOTSTRAP_PUBLISH_TOKEN_SOURCE_READ_FORBIDDEN')
        return self._command(['inspect', '--raw', 'docker://' + image],
            self.policy['commandTimeoutSeconds'], auth_token=token)

    def copy_once(self, source, destination, token):
        require(source == SOURCE_IMAGE and re.fullmatch(re.escape(CANDIDATE_PACKAGE)
            + r':bootstrap-parent-9378a86d8134-[1-9][0-9]{0,19}-a1', destination),
            'BOOTSTRAP_COPY_ENDPOINT_FORBIDDEN')
        # The source is public; --src-no-creds prevents the new-package job token
        # being applied to the old successful package even for read requests.
        self._command(['copy', '--preserve-digests', '--retry-times=0', '--src-no-creds',
            'docker://' + source, 'docker://' + destination],
            self.policy['copyTimeoutSeconds'], capture=False, auth_token=token)


def _secure_directory(env):
    raw_temp = env.get('RUNNER_TEMP', '')
    require(type(raw_temp) is str and Path(raw_temp).is_absolute(),
            'BOOTSTRAP_RUNNER_TEMP_REQUIRED')
    runner_temp = Path(raw_temp).resolve(strict=True)
    require(runner_temp.is_dir(), 'BOOTSTRAP_RUNNER_TEMP_REQUIRED')
    directory = runner_temp / 'world-engine-ghcr-bootstrap'
    if not directory.exists():
        directory.mkdir(mode=0o700)
    require(not directory.is_symlink() and directory.is_dir()
        and directory.stat().st_uid == os.getuid()
        and directory.stat().st_mode & 0o777 == 0o700,
        'BOOTSTRAP_PRIVATE_EVIDENCE_DIRECTORY_REQUIRED')
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('preflight', 'register'))
    parser.add_argument('--policy', default=POLICY_PATH)
    parser.add_argument('--workflow', default=WORKFLOW_PATH)
    parser.add_argument('--evidence-dir')
    args = parser.parse_args(argv)
    require(args.policy == POLICY_PATH and args.workflow == WORKFLOW_PATH,
            'BOOTSTRAP_REVIEWED_ROOT_PATHS_REQUIRED')
    env = dict(os.environ)
    token = env.pop('GHCR_BOOTSTRAP_TOKEN', None)
    os.environ.pop('GHCR_BOOTSTRAP_TOKEN', None)
    require(args.mode == 'register' or token is None,
            'BOOTSTRAP_PREFLIGHT_TOKEN_FORBIDDEN')
    event_raw = Path(env['GITHUB_EVENT_PATH']).read_bytes()
    event = load_json_strict(event_raw, 32768)
    context = derive_context(env, event)
    policy_raw = Path(POLICY_PATH).read_bytes()
    workflow_raw = Path(WORKFLOW_PATH).read_bytes()
    policy = load_json_strict(policy_raw)
    attestation = load_json_strict(event['inputs']['owner_attestation'], 8192)
    # Draft and all owner proof checks happen before network, subprocess or mkdir.
    validate_policy(policy, context, attestation, time.time_ns() // 1000000,
                    digest(policy_raw), digest(workflow_raw))
    directory = _secure_directory(env)
    if args.evidence_dir is not None:
        require(Path(args.evidence_dir).resolve() == directory,
                'BOOTSTRAP_FIXED_EVIDENCE_PATH_REQUIRED')
    effects = LiveEffects(policy, directory)
    if args.mode == 'preflight':
        receipt = preflight(policy, context, attestation, effects,
                            digest(policy_raw), digest(workflow_raw))
        exclusive_receipt(directory, 'PREPARED.json', receipt)
        _emit(receipt)
    else:
        prepared_path = directory / 'PREPARED.json'
        require(not prepared_path.is_symlink(), 'BOOTSTRAP_PREFLIGHT_PATH_UNSAFE')
        prepared = load_json_strict(prepared_path.read_bytes(), 8192)
        register(policy, context, attestation, effects, digest(policy_raw),
                 digest(workflow_raw), token, directory, prepared)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # Never surface exception strings; urllib/subprocess may retain secrets.
        print('WORLD_ENGINE_BOOTSTRAP_BLOCKED_NO_RETRY', flush=True)
        raise SystemExit(1) from None
