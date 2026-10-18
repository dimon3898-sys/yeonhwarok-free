#!/usr/bin/env python3
"""Version future-job wall limits without changing existing GPU approvals.

This local UID1000 operator tool has no HTTP endpoint and launches no work.
The original private-tree and rate/cost/retry/expiry validators remain final.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ENGINE = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
          if str(HERE).startswith('/opt/') else HERE.parent)
STUDIO = Path('/opt/world-engine-production-studio') if str(HERE).startswith('/opt/') else HERE.parent / 'production-studio-mvp-v1'
CONTROLLER_SHA = 'c2e0d94a31cd90569d29f944da1a538c9efcf77d15cd0f2bfacbe99396ae053c'
CACHE_SHA = '4ad9dc03c11ccb39df027cb39dc31715525f2eb7be6da76bedbccfaefd5984fd'
FUTURE_WALL_SECONDS = 10800


def _load(name, path, expected):
    if any(p.is_symlink() for p in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('RECOVERY_FROZEN_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        sys.path.insert(0, str(STUDIO))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module


def dependencies():
    return (_load('_cpu_recovery_policy_cache', ENGINE / 'universal-auto-video-v2/cache.py', CACHE_SHA),
            _load('_cpu_recovery_policy_controller', STUDIO / 'studio_controller.py', CONTROLLER_SHA))


def validate_future_policy(candidate, previous, *, now=None):
    _, module = dependencies()
    class Reader:
        def json(self, name, optional=False):
            if name != 'operator_policy.json':
                raise RuntimeError('RECOVERY_POLICY_READER_INVALID')
            return candidate
    # Reuse the complete original cost, field, expiry and retry checks.
    policy = module.StudioController._policy(None, Reader())
    if policy['maxWallSeconds'] != FUTURE_WALL_SECONDS:
        raise RuntimeError('RECOVERY_FUTURE_LIMIT_MUST_BE_10800')
    # The user approved a new time ceiling, not an increased financial or retry
    # allowance. Such a change requires a separately approved policy operation.
    for name in ('gpuHourlyRate', 'currency', 'maxCostAmount', 'maxRetries'):
        if policy[name] != previous.get(name):
            raise RuntimeError('RECOVERY_EXISTING_FINANCIAL_AND_RETRY_CAPS_REQUIRED')
    current = datetime.now(timezone.utc) if now is None else now
    expiry = datetime.fromisoformat(policy['validUntil'])
    if (expiry - current).total_seconds() < FUTURE_WALL_SECONDS:
        raise RuntimeError('RECOVERY_POLICY_VALIDITY_TOO_SHORT_FOR_180_MINUTES')
    return policy


def stage_future_policy(control_root, candidate_path):
    """Persist a validated inactive revision. Never overwrite the old policy."""
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise RuntimeError('RECOVERY_UID_GID_1000_REQUIRED')
    cache, _ = dependencies()
    candidate_path = Path(candidate_path).absolute()
    with cache.PrivateTree(candidate_path.parent) as source:
        candidate = source.json(candidate_path.name)
    with cache.PrivateTree(Path(control_root)) as root, root.lock(wait_seconds=5):
        previous = root.json('operator_policy.json')
        normalized = validate_future_policy(candidate, previous)
        old_sha = root.hash_file('operator_policy.json')['sha256']
        key = cache.canonical_sha256({'previousPolicySHA256': old_sha, 'policy': normalized})
        with root.child('future-policy-revisions', create=True) as revisions, revisions.child(key, create=True) as revision:
            record = revision.json('REVISION.json', optional=True)
            expected = {'schema': 'WORLD_ENGINE_FUTURE_POLICY_REVISION_V1', 'revisionId': key,
                        'previousPolicySHA256': old_sha, 'policySHA256': cache.canonical_sha256(normalized),
                        'maxWallSeconds': FUTURE_WALL_SECONDS, 'scope': 'FUTURE_NEW_JOBS_ONLY',
                        'originalApprovalsChanged': False, 'financialCapsIncreased': False}
            if record is not None and record != expected:
                raise RuntimeError('RECOVERY_POLICY_REVISION_CONFLICT')
            if record is not None:
                if (revision.json('POLICY.json') != normalized or revision.json('PREVIOUS_POLICY.json') != previous
                        or revision.hash_file('PREVIOUS_POLICY_BYTES.json')['sha256'] != old_sha):
                    raise RuntimeError('RECOVERY_POLICY_REVISION_CORRUPT')
            if record is None:
                descriptor = os.open('operator_policy.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root.fd)
                try:
                    cache.storage._file_info(descriptor, uid=1000, private=True)
                    raw = cache.storage._read_fd(descriptor, limit=65536)
                finally:
                    os.close(descriptor)
                if hashlib.sha256(raw).hexdigest() != old_sha:
                    raise RuntimeError('RECOVERY_POLICY_CHANGED_DURING_REVIEW')
                cache.storage._new_file(revision.fd, 'PREVIOUS_POLICY_BYTES.json', raw, private=True)
                revision.write_json('PREVIOUS_POLICY.json', previous)
                revision.write_json('POLICY.json', normalized)
                revision.write_json('REVISION.json', expected)
        return {**expected, 'status': 'STAGED_NOT_ACTIVE', 'gpuExecuted': False}


def activate_future_policy(control_root, revision_id, *, consent=False):
    """Explicit operator action, future policy only, with retained previous data."""
    if consent is not True:
        raise RuntimeError('RECOVERY_EXPLICIT_POLICY_ACTIVATION_REQUIRED')
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise RuntimeError('RECOVERY_UID_GID_1000_REQUIRED')
    cache, _ = dependencies()
    if not isinstance(revision_id, str) or not cache.HEX.fullmatch(revision_id):
        raise RuntimeError('RECOVERY_POLICY_REVISION_INVALID')
    with cache.PrivateTree(Path(control_root)) as root, root.lock(wait_seconds=5):
        with root.child('future-policy-revisions') as revisions, revisions.child(revision_id) as revision:
            record = revision.json('REVISION.json')
            previous, candidate = revision.json('PREVIOUS_POLICY.json'), revision.json('POLICY.json')
            current = root.json('operator_policy.json')
            if (record.get('revisionId') != revision_id or record.get('policySHA256') != cache.canonical_sha256(candidate)
                    or revision_id != cache.canonical_sha256({'previousPolicySHA256': record.get('previousPolicySHA256'), 'policy': candidate})):
                raise RuntimeError('RECOVERY_POLICY_REVISION_CORRUPT')
            validate_future_policy(candidate, previous)
            if revision.hash_file('PREVIOUS_POLICY_BYTES.json')['sha256'] != record.get('previousPolicySHA256'):
                raise RuntimeError('RECOVERY_POLICY_REVISION_CORRUPT')
            receipt = {'scope': 'FUTURE_NEW_JOBS_ONLY', 'originalApprovalsChanged': False}
            if cache.canonical_sha256(current) == cache.canonical_sha256(candidate):
                saved = revision.json('ACTIVATED.json', optional=True)
                if saved is None:
                    revision.write_json('ACTIVATED.json', receipt)
                elif saved != receipt:
                    raise RuntimeError('RECOVERY_POLICY_ACTIVATION_RECEIPT_CORRUPT')
                return {'status': 'ALREADY_ACTIVE', 'revisionId': revision_id, 'maxWallSeconds': FUTURE_WALL_SECONDS,
                        'originalApprovalsChanged': False, 'gpuExecuted': False}
            if root.hash_file('operator_policy.json')['sha256'] != record['previousPolicySHA256'] or current != previous:
                raise RuntimeError('RECOVERY_POLICY_CHANGED_SINCE_REVIEW')
            root.write_json('operator_policy.json', candidate, replace=True)
            if revision.json('ACTIVATED.json', optional=True) is None:
                revision.write_json('ACTIVATED.json', receipt)
        return {'status': 'ACTIVE_FUTURE_NEW_JOBS_ONLY', 'revisionId': revision_id,
                'maxWallSeconds': FUTURE_WALL_SECONDS, 'originalApprovalsChanged': False, 'gpuExecuted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['stage', 'activate'])
    parser.add_argument('--control-root', required=True, type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--revision-id')
    parser.add_argument('--confirm-future-policy', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'stage':
            if args.candidate is None:
                raise RuntimeError('RECOVERY_APPROVED_POLICY_FILE_REQUIRED')
            result = stage_future_policy(args.control_root, args.candidate)
        else:
            result = activate_future_policy(args.control_root, args.revision_id, consent=args.confirm_future_policy)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        code = getattr(error, 'code', None) or str(error)
        import re
        if not isinstance(code, str) or not re.fullmatch('[A-Z][A-Z0-9_]{1,95}', code):
            code = 'RECOVERY_POLICY_OPERATION_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'gpuExecuted': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
