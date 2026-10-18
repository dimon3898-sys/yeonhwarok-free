"""Authenticated, neutral scene-cache snapshots; never restores execution authority.

Shared bytes remain untrusted. The separate Vault authenticates them before any
private cache is reconstructed. Restoration is an explicit CPU operation into a
fresh root and cannot launch a renderer, revive a claim or extend an approval.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

from vault import BackupError

HERE = Path(__file__).resolve().parent
RECOVERY = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
            if str(HERE).startswith('/opt/') else HERE.parent)
SCHEMA = 'WORLD_ENGINE_STUDIO_DURABLE_CHECKPOINT_V1'
SHA = re.compile(r'[a-f0-9]{64}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
ATTEMPT = re.compile(r'attempt-[a-f0-9]{24}\Z')
PROFILES = {'V4_ARCHIVAL_80S': 'render-v4', 'UNIVERSAL_V3': 'render-v3'}
MAX_FILE = 4 * 1024 ** 3
MAX_RECORD = 32 * 1024 ** 2
ARTIFACT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z')
_MODULES = None


def fail(code):
    raise BackupError(code)


def modules():
    global _MODULES
    if _MODULES is None:
        result = {}
        for name, digest in [('cache', '4ad9dc03c11ccb39df027cb39dc31715525f2eb7be6da76bedbccfaefd5984fd'),
                             ('compose', 'd4478f758988923a18620a07b0dcf0e0883c99b6ef419d4bffac5999e65d5245')]:
            path = RECOVERY / 'universal-auto-video-v2' / (name + '.py')
            if (any(p.is_symlink() for p in (path, *path.parents)) or
                    hashlib.sha256(path.read_bytes()).hexdigest() != digest):
                fail('DURABILITY_FROZEN_DEPENDENCY_CHANGED')
            spec = importlib.util.spec_from_file_location('_durability_frozen_' + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            result[name] = module
        _MODULES = result
    return _MODULES


def canonical(value):
    return modules()['cache'].canonical_bytes(value)


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _no_credentials(value, depth=0):
    if depth > 64:
        fail('DURABILITY_INPUT_DEPTH_EXCEEDED')
    forbidden = {'password', 'token', 'apitoken', 'accesstoken', 'secret', 'privatekey',
                 'ownercode', 'authorization', 'approval', 'operatorpolicy', 'sessions', 'signingkey'}
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub('[^a-z]', '', str(key).lower())
            if normalized in forbidden or normalized.startswith('gcube') and normalized.endswith('token'):
                fail('DURABILITY_CREDENTIAL_FIELD_FORBIDDEN')
            _no_credentials(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _no_credentials(item, depth + 1)


def _inputs(plan, audio, profile, production):
    if profile not in PROFILES or not isinstance(plan, dict) or not isinstance(audio, dict):
        fail('DURABILITY_INPUT_INVALID')
    _no_credentials(plan)
    _no_credentials(audio)
    if len(canonical(plan)) > MAX_RECORD or len(canonical(audio)) > MAX_RECORD:
        fail('DURABILITY_INPUT_SIZE_EXCEEDED')
    digest = plan.get('renderProfile', {}).get('imageDigest')
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        fail('DURABILITY_IMAGE_BINDING_REQUIRED')
    if not isinstance(plan.get('sourceManifest'), dict) or not plan['sourceManifest']:
        fail('DURABILITY_SOURCE_BINDING_REQUIRED')
    scenes, cursor, names = plan.get('scenes'), 0, set()
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 10000:
        fail('DURABILITY_SCENE_LIST_INVALID')
    for scene in scenes:
        sid = scene.get('sceneId') if isinstance(scene, dict) else None
        if (not isinstance(sid, str) or not 1 <= len(sid) <= 160 or sid in names or
                type(scene.get('startFrame')) is not int or scene['startFrame'] != cursor or
                type(scene.get('endFrame')) is not int or scene['endFrame'] <= cursor):
            fail('DURABILITY_SCENE_TIMELINE_INVALID')
        names.add(sid)
        cursor = scene['endFrame']
    if type(plan.get('totalFrames')) is not int or cursor != plan['totalFrames']:
        fail('DURABILITY_SCENE_TIMELINE_INVALID')
    contract = modules()['compose'].video_contract(plan)
    if contract['frames'] != cursor or type(plan.get('testOnly', False)) is not bool:
        fail('DURABILITY_SCENE_TIMELINE_INVALID')
    if production and plan.get('testOnly') is True:
        fail('DURABILITY_SYNTHETIC_PRODUCTION_FORBIDDEN')
    if not production and plan.get('testOnly') is not True:
        fail('DURABILITY_EXPLICIT_TEST_PROVENANCE_REQUIRED')
    return digest


def _key(plan, index):
    scenes = plan['scenes']
    return modules()['cache'].scene_cache_key(plan, scenes[index],
        scenes[index - 1] if index else None, scenes[index + 1] if index + 1 < len(scenes) else None)


def _artifact(name):
    if (not isinstance(name, str) or not ARTIFACT.fullmatch(name) or name in {'.', '..'} or
            name in {'COMPLETE.json', 'SUCCESS.json', 'ATTEMPT.json', 'APPROVAL.json', 'JOB.json', 'PLAN.json', 'AUDIO.json'} or
            name.lower().endswith(('.png', '.jpg', '.jpeg', '.raw', '.rgba', '.rgb', '.exr'))):
        fail('DURABILITY_CACHE_ARTIFACT_INVALID')
    return name


def _provenance(segment, scene, production):
    if (not isinstance(segment, dict) or any(segment.get(k) != scene.get(k) for k in ('sceneId', 'startFrame', 'endFrame')) or
            segment.get('technical') != 'PASS' or segment.get('frameCountVerified') is not True or
            segment.get('fullDecodeVerified') is not True or type(segment.get('testOnly')) is not bool or
            (production and (segment['testOnly'] or segment.get('hardwareVerified') is not True)) or
            (not production and segment['testOnly'] is not True)):
        fail('DURABILITY_VERIFIED_SCENE_PROVENANCE_REQUIRED')
    _no_credentials(segment)


def _history(tree, plan):
    """Only accounting facts, never a runnable job or approved capability."""
    result = {}
    name = 'video-v2-' + sha(plan)[:24]
    try:
        with tree.child(name) as job:
            ledger = job.json('JOB.json', optional=True)
    except FileNotFoundError:
        return result
    if not isinstance(ledger, dict) or ledger.get('planSHA256') != sha(plan):
        fail('DURABILITY_LEDGER_PLAN_MISMATCH')
    for key in ('retriesUsed', 'startedUnix', 'deadlineUnix', 'progressFrames', 'totalFrames'):
        value = ledger.get(key)
        if type(value) in (int, float) and 0 <= value <= 10 ** 15:
            result[key] = value
    if ledger.get('state') in {'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED'}:
        result['historicalState'] = ledger['state']
    result['executionAuthorityRestored'] = False
    return result


class Checkpoints:
    def __init__(self, vault, *, production=True):
        self.vault, self.production = vault, production

    def save(self, plan, audio, profile_id, control_root, coordinator_root=None):
        digest = _inputs(plan, audio, profile_id, self.production)
        if self.production and getattr(self.vault.store, 'external_verified', False) is not True:
            fail('DURABILITY_EXTERNAL_STORE_REQUIRED')
        cachemod = modules()['cache']
        with cachemod.PrivateTree(Path(control_root)):
            pass
        manifest = {'schema': SCHEMA, 'plan': plan, 'audio': audio, 'profileId': profile_id,
                    'planSHA256': sha(plan), 'audioSHA256': sha(audio), 'imageDigest': digest,
                    'sourceManifestSHA256': sha(plan.get('sourceManifest')), 'scenes': [],
                    'history': {}, 'testOnly': not self.production, 'executionAuthorityRestored': False}
        if coordinator_root is not None:
            root = Path(coordinator_root)
            if root.name == 'video-v2-' + sha(plan)[:24]:
                root = root.parent
            with cachemod.PrivateTree(root) as coordinator:
                manifest['history'] = _history(coordinator, plan)
                try:
                    cached = coordinator.child('cache')
                except FileNotFoundError:
                    cached = None
                if cached is not None:
                    with cached, _closing_cache(cachemod.SceneCache(cached.path)) as cache:
                        for i, scene in enumerate(plan['scenes']):
                            key = _key(plan, i)
                            try:
                                entry = cached.child(key)
                            except FileNotFoundError:
                                continue
                            with entry:
                                index = entry.json('SUCCESS.json', optional=True)
                                if index is None:
                                    continue
                                if (set(index) != {'key', 'attemptId', 'receiptSHA256'} or index['key'] != key or
                                        not isinstance(index.get('attemptId'), str) or not ATTEMPT.fullmatch(index['attemptId'])):
                                    fail('DURABILITY_CACHE_INDEX_INVALID')
                                segment = cache.lookup(key)
                                _provenance(segment, scene, self.production)
                                with entry.child(index['attemptId']) as attempt:
                                    receipt = attempt.json('COMPLETE.json')
                                    rows = receipt.get('files')
                                    if (not isinstance(rows, list) or not 1 <= len(rows) <= 12 or
                                            len({r.get('file') for r in rows if isinstance(r, dict)}) != len(rows)):
                                        fail('DURABILITY_CACHE_ARTIFACT_LIST_INVALID')
                                    copied = []
                                    for row in rows:
                                        if not isinstance(row, dict) or set(row) != {'file', 'sha256', 'bytes'}:
                                            fail('DURABILITY_CACHE_ARTIFACT_LIST_INVALID')
                                        name = _artifact(row['file'])
                                        facts = attempt.hash_file(name)
                                        if facts != row or not 0 < facts['bytes'] <= MAX_FILE:
                                            fail('DURABILITY_CACHE_ARTIFACT_HASH_MISMATCH')
                                        descriptor = self.vault.put_file(attempt.path / name, expected_sha=facts['sha256'])
                                        self.vault.verify_descriptor(descriptor)
                                        if descriptor['sha256'] != row['sha256'] or descriptor['bytes'] != row['bytes']:
                                            fail('DURABILITY_VAULT_FILE_BINDING_MISMATCH')
                                        copied.append({'name': name, 'descriptor': descriptor})
                                    saved = {k: v for k, v in receipt['segment'].items()
                                             if k not in {'path', 'cacheHit', 'cacheKey', 'verificationDirectory'}}
                                    _no_credentials(saved)
                                    manifest['scenes'].append({'sceneId': scene['sceneId'], 'cacheKey': key,
                                        'sceneSHA256': sha(scene), 'segment': saved, 'files': copied})
        checkpoint_id = self.vault.save_manifest(manifest)
        if self.vault.load_manifest(checkpoint_id) != manifest:
            fail('DURABILITY_MANIFEST_READBACK_MISMATCH')
        # The catalog marker contains only this opaque, key-addressed receipt
        # ID. Its payload is a separate authenticated encrypted manifest, so a
        # shared directory listing can discover snapshots without trusting
        # unauthenticated timestamps or exposing Scene/asset/private paths.
        receipt_manifest = {'schema': 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1',
            'checkpointId': checkpoint_id, 'planSHA256': manifest['planSHA256'],
            'completedScenes': len(manifest['scenes']), 'createdUnixNs': time.time_ns(),
            'testOnly': not self.production}
        receipt_id = self.vault.save_manifest(receipt_manifest)
        if self.vault.load_manifest(receipt_id) != receipt_manifest:
            fail('DURABILITY_RECEIPT_READBACK_MISMATCH')
        publisher = getattr(self.vault.store, 'publish_receipt', None)
        if not callable(publisher):
            fail('DURABILITY_DISCOVERABLE_RECEIPT_REQUIRED')
        publisher(receipt_id)
        return {'checkpointId': checkpoint_id, 'planSHA256': manifest['planSHA256'],
                'receiptId': receipt_id,
                'completedScenes': len(manifest['scenes']), 'externalDownloadVerified': bool(self.vault.store.external_verified),
                'remotePersistenceVerified': bool(self.vault.store.external_verified)}


class _closing_cache:
    def __init__(self, cache): self.cache = cache
    def __enter__(self): return self.cache
    def __exit__(self, *_): self.cache.close()


def restore(vault, checkpoint_id, destination_state_root, *, expected_plan_sha, expected_image_digest, production=True):
    if production and getattr(vault.store, 'external_verified', False) is not True:
        fail('DURABILITY_EXTERNAL_STORE_REQUIRED')
    manifest = vault.load_manifest(checkpoint_id)
    required = {'schema', 'plan', 'audio', 'profileId', 'planSHA256', 'audioSHA256', 'imageDigest',
                'sourceManifestSHA256', 'scenes', 'history', 'testOnly', 'executionAuthorityRestored'}
    if not isinstance(manifest, dict) or set(manifest) != required or manifest.get('schema') != SCHEMA:
        fail('DURABILITY_CHECKPOINT_MANIFEST_INVALID')
    plan, audio, profile = manifest['plan'], manifest['audio'], manifest['profileId']
    digest = _inputs(plan, audio, profile, production)
    if (not isinstance(expected_plan_sha, str) or not SHA.fullmatch(expected_plan_sha) or
            sha(plan) != expected_plan_sha or manifest['planSHA256'] != expected_plan_sha or
            manifest['audioSHA256'] != sha(audio) or manifest['imageDigest'] != digest or digest != expected_image_digest or
            manifest['sourceManifestSHA256'] != sha(plan.get('sourceManifest')) or
            manifest['testOnly'] is not (not production) or manifest['executionAuthorityRestored'] is not False):
        fail('DURABILITY_CHECKPOINT_BINDING_MISMATCH')
    history = manifest['history']
    if (not isinstance(history, dict) or set(history) - {'retriesUsed', 'startedUnix', 'deadlineUnix',
            'progressFrames', 'totalFrames', 'historicalState', 'executionAuthorityRestored'} or
            ('executionAuthorityRestored' in history and history['executionAuthorityRestored'] is not False)):
        fail('DURABILITY_HISTORY_NOT_INERT')
    rows = manifest['scenes']
    if not isinstance(rows, list) or len(rows) > len(plan['scenes']):
        fail('DURABILITY_CHECKPOINT_SCENES_INVALID')
    by_id = {s['sceneId']: (i, s) for i, s in enumerate(plan['scenes'])}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'sceneId', 'cacheKey', 'sceneSHA256', 'segment', 'files'}:
            fail('DURABILITY_CHECKPOINT_SCENES_INVALID')
        sid = row['sceneId']
        if not isinstance(sid, str) or sid not in by_id or sid in seen:
            fail('DURABILITY_CHECKPOINT_SCENES_INVALID')
        seen.add(sid)
        i, scene = by_id[sid]
        if row['cacheKey'] != _key(plan, i) or row['sceneSHA256'] != sha(scene):
            fail('DURABILITY_CHECKPOINT_CACHE_BINDING_MISMATCH')
        _provenance(row['segment'], scene, production)
        files = row['files']
        if not isinstance(files, list) or not 1 <= len(files) <= 12:
            fail('DURABILITY_CHECKPOINT_FILES_INVALID')
        names = []
        for file in files:
            if not isinstance(file, dict) or set(file) != {'name', 'descriptor'}:
                fail('DURABILITY_CHECKPOINT_FILES_INVALID')
            names.append(_artifact(file['name']))
            if (not isinstance(file['descriptor'], dict) or type(file['descriptor'].get('bytes')) is not int or
                    not 0 < file['descriptor']['bytes'] <= MAX_FILE):
                fail('DURABILITY_CHECKPOINT_FILES_INVALID')
            vault.verify_descriptor(file['descriptor'])
        if len(names) != len(set(names)) or row['segment'].get('file') not in names:
            fail('DURABILITY_CHECKPOINT_FILES_INVALID')
    destination = Path(destination_state_root)
    if destination.exists() or destination.is_symlink():
        fail('DURABILITY_FRESH_RESTORE_ROOT_REQUIRED')
    cachemod, compose = modules()['cache'], modules()['compose']
    with cachemod.PrivateTree(destination, create=True) as root, root.child('production', create=True) as prod:
        prod.write_json('PLAN.json', plan)
        prod.write_json('AUDIO.json', audio)
        prod.write_json('RECOVERY_HISTORY.json', {'checkpointId': checkpoint_id, 'history': manifest['history'],
                        'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True})
        with prod.child(PROFILES[profile], create=True) as native, native.child('cache', create=True) as cache_tree:
            with _closing_cache(cachemod.SceneCache(cache_tree.path)) as cache:
                for row in rows:
                    scene = by_id[row['sceneId']][1]
                    attempt = cache.begin(row['cacheKey'])
                    for file in row['files']:
                        vault.restore_file(file['descriptor'], attempt / file['name'])
                    segment = dict(row['segment'], path=str(attempt / row['segment']['file']))
                    checked = compose.verify_segment(Path(segment['path']), scene, plan)
                    if checked['sha256'] != segment.get('sha256'):
                        fail('DURABILITY_RESTORED_SEGMENT_HASH_MISMATCH')
                    segment.update({k: v for k, v in checked.items() if k != 'verificationDirectory'})
                    segment['artifacts'] = [f['name'] for f in row['files']]
                    cache.complete(row['cacheKey'], attempt, segment)
                    if cache.lookup(row['cacheKey'])['sha256'] != checked['sha256']:
                        fail('DURABILITY_RESTORED_CACHE_VERIFICATION_FAILED')
        receipt = {'checkpointId': checkpoint_id, 'planSHA256': expected_plan_sha, 'imageDigest': digest,
                   'profileId': profile, 'completedScenes': len(rows), 'totalScenes': len(plan['scenes']),
                   'nextIncompleteSceneIds': [s['sceneId'] for s in plan['scenes'] if s['sceneId'] not in seen],
                   'sourceManifestSHA256': manifest['sourceManifestSHA256'], 'restoreVerified': True,
                   'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True,
                   'externalDownloadVerified': bool(vault.store.external_verified),
                   'remotePersistenceVerified': bool(vault.store.external_verified), 'testOnly': not production}
        prod.write_json('RESTORED_INPUT.json', receipt)
    return receipt
