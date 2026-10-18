#!/usr/bin/env python3
"""Explicit CPU-only fresh-root restore; never restores execution authority.

An optional bootstrap profile invokes this as UID/GID1000 before the web/GPU
services. Repeated container starts only verify the same restored bytes and
leave all later claims, job records and completed results untouched.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

import checkpoint
from stores import BackupError

SHA = re.compile(r'[a-f0-9]{64}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')


def _bindings(checkpoint_id, plan_sha, image_digest, state_root):
    target = Path(state_root)
    if (not isinstance(checkpoint_id, str) or not SHA.fullmatch(checkpoint_id)
            or not isinstance(plan_sha, str) or not SHA.fullmatch(plan_sha)
            or not isinstance(image_digest, str) or not DIGEST.fullmatch(image_digest)):
        raise BackupError('DURABILITY_RESTORE_BINDINGS_REQUIRED')
    if (not target.is_absolute() or '..' in target.parts or target == Path('/')
            or target.is_relative_to('/world-storage')
            or any(p.is_symlink() for p in (target, *target.parents))):
        raise BackupError('DURABILITY_PRIVATE_RESTORE_ROOT_REQUIRED')
    return target


def _verify_existing(vault, checkpoint_id, plan_sha, image_digest, target, *, production=True):
    """Authenticate remote manifest then rehash/probe each retained cache entry."""
    manifest = vault.load_manifest(checkpoint_id)
    if (not isinstance(manifest, dict) or manifest.get('schema') != checkpoint.SCHEMA
            or manifest.get('planSHA256') != plan_sha or manifest.get('imageDigest') != image_digest
            or manifest.get('testOnly') is not (not production)
            or manifest.get('executionAuthorityRestored') is not False):
        raise BackupError('DURABILITY_RESTORE_BINDING_MISMATCH')
    plan, audio, profile = manifest.get('plan'), manifest.get('audio'), manifest.get('profileId')
    checkpoint._inputs(plan, audio, profile, production)
    if (checkpoint.sha(plan) != plan_sha or plan['renderProfile']['imageDigest'] != image_digest
            or checkpoint.sha(audio) != manifest.get('audioSHA256')
            or checkpoint.sha(plan.get('sourceManifest')) != manifest.get('sourceManifestSHA256')):
        raise BackupError('DURABILITY_RESTORE_BINDING_MISMATCH')
    cachemod, compose = checkpoint.modules()['cache'], checkpoint.modules()['compose']
    rows = manifest.get('scenes')
    if not isinstance(rows, list) or len(rows) > len(plan['scenes']):
        raise BackupError('DURABILITY_RESTORE_MANIFEST_INVALID')
    scenes = {scene['sceneId']: (index, scene) for index, scene in enumerate(plan['scenes'])}
    seen = set()
    with cachemod.PrivateTree(target) as root, root.child('production') as prod:
        receipt = prod.json('RESTORED_INPUT.json')
        if (not isinstance(receipt, dict) or receipt.get('checkpointId') != checkpoint_id
                or receipt.get('planSHA256') != plan_sha or receipt.get('imageDigest') != image_digest
                or receipt.get('restoreVerified') is not True or receipt.get('profileId') != profile
                or receipt.get('testOnly') is not (not production)
                or receipt.get('completedScenes') != len(rows)
                or receipt.get('executionAuthorityRestored') is not False
                or receipt.get('newOperatorApprovalRequired') is not True
                or prod.json('PLAN.json') != plan or prod.json('AUDIO.json') != audio):
            raise BackupError('DURABILITY_EXISTING_RESTORE_MISMATCH')
        with prod.child(checkpoint.PROFILES[profile]) as native, native.child('cache') as ct:
            cache = cachemod.SceneCache(ct.path)
            try:
                for row in rows:
                    if (not isinstance(row, dict) or row.get('sceneId') not in scenes
                            or row['sceneId'] in seen):
                        raise BackupError('DURABILITY_RESTORE_MANIFEST_INVALID')
                    seen.add(row['sceneId'])
                    index, scene = scenes[row['sceneId']]
                    key = checkpoint._key(plan, index)
                    if row.get('cacheKey') != key or row.get('sceneSHA256') != checkpoint.sha(scene):
                        raise BackupError('DURABILITY_RESTORE_CACHE_BINDING_MISMATCH')
                    # Require a preexisting key first; frozen lookup otherwise
                    # creates a missing directory. Verification never repairs it.
                    with ct.child(key):
                        pass
                    segment = cache.lookup(key)
                    checkpoint._provenance(segment, scene, production)
                    if segment.get('sha256') != row.get('segment', {}).get('sha256'):
                        raise BackupError('DURABILITY_RESTORE_CACHE_HASH_MISMATCH')
                    files = row.get('files')
                    if not isinstance(files, list) or not 1 <= len(files) <= 12:
                        raise BackupError('DURABILITY_RESTORE_MANIFEST_INVALID')
                    with cachemod.PrivateTree(Path(segment['path']).parent) as attempt:
                        names = set()
                        for file in files:
                            if not isinstance(file, dict):
                                raise BackupError('DURABILITY_RESTORE_MANIFEST_INVALID')
                            name = checkpoint._artifact(file.get('name'))
                            descriptor = file.get('descriptor')
                            if name in names or not isinstance(descriptor, dict):
                                raise BackupError('DURABILITY_RESTORE_MANIFEST_INVALID')
                            names.add(name)
                            expected = {'file': name, 'sha256': descriptor.get('sha256'),
                                        'bytes': descriptor.get('bytes')}
                            if attempt.hash_file(name) != expected:
                                raise BackupError('DURABILITY_RESTORE_CACHE_HASH_MISMATCH')
                    # Do not add evidence directories to an existing cache or
                    # touch any later claims/results during a repeated start.
                    with tempfile.TemporaryDirectory(prefix='restore-recheck-', dir=target.parent) as diagnostics:
                        checked = compose.verify_segment(Path(segment['path']), scene, plan,
                                                         diagnostics=Path(diagnostics) / 'media')
                    if checked.get('sha256') != segment.get('sha256'):
                        raise BackupError('DURABILITY_RESTORE_CACHE_HASH_MISMATCH')
            finally:
                cache.close()
    return {'checkpointId': checkpoint_id, 'planSHA256': plan_sha, 'imageDigest': image_digest,
            'completedScenes': len(rows), 'totalScenes': len(plan['scenes']),
            'restoreVerified': True, 'executionAuthorityRestored': False,
            'newOperatorApprovalRequired': True, 'testOnly': not production}


def ensure_restore(vault, checkpoint_id, plan_sha, image_digest, state_root):
    """Production entry always rejects synthetic data; no environment bypass."""
    target = _bindings(checkpoint_id, plan_sha, image_digest, state_root)
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise BackupError('DURABILITY_UID_GID_1000_REQUIRED')
    from preflight import require_dropbox_transport
    require_dropbox_transport(vault)
    if target.exists() or target.is_symlink():
        result = _verify_existing(vault, checkpoint_id, plan_sha, image_digest, target, production=True)
        result['startupRestore'] = 'EXISTING_RESTORE_VERIFIED'
    else:
        result = checkpoint.restore(vault, checkpoint_id, target,
            expected_plan_sha=plan_sha, expected_image_digest=image_digest, production=True)
        result['startupRestore'] = 'FRESH_ROOT_RESTORED'
    return {**result, 'productionRenderingStarted': False, 'gpuVerified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint-id', required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--image-digest', required=True)
    parser.add_argument('--state-root', required=True)
    args = parser.parse_args(argv)
    try:
        from durable_backend import make_vault_from_env
        result = ensure_restore(make_vault_from_env(), args.checkpoint_id, args.plan_sha256,
                                args.image_digest, args.state_root)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        code = getattr(error, 'code', str(error))
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,95}', code):
            code = 'DURABILITY_STARTUP_RESTORE_FAILED'
        print(json.dumps({'startupRestore': 'BLOCKED', 'code': code, 'productionRenderingStarted': False,
                          'gpuVerified': False}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
