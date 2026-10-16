#!/usr/bin/env python3
"""Strict Studio-only payload verification; the immutable V4 tree stays untouched."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
SCHEMA = 'WORLD_ENGINE_PRODUCTION_STUDIO_FILES_V1'
PROFILE_ID = 'PRODUCTION_STUDIO_MVP_V1'
MANIFEST_NAME = 'STUDIO_FILES.json'
INVENTORY_NAME = 'RUNTIME_INVENTORY.json'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4'
PARENT_MANIFEST_SHA = 'b9353fadf6c93484e3c6e2723991db98439678b87eff5360371039aa4beadb93'
PARENT_SOURCE_COMMIT = '30ea53d85df39962822733f44872a303961aedde'
PARENT_NAMESPACE = 'world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery'
PARENT_INVENTORY_FILES = 373
BASELINE = '344dc2da48e15230725d687a4343456cbbae89a8'
HASH = re.compile(r'[a-f0-9]{64}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')


def read_source(root, name):
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise RuntimeError('STUDIO_CANONICAL_SOURCE_REQUIRED')
    cursor = Path(root)
    if cursor.is_symlink():
        raise RuntimeError('STUDIO_SOURCE_SYMLINK_FORBIDDEN')
    for part in name.split('/'):
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError('STUDIO_SOURCE_SYMLINK_FORBIDDEN')
    if not cursor.is_file() or not 0 < cursor.stat().st_size <= 64 * 1024**2:
        raise RuntimeError('STUDIO_BOUNDED_REGULAR_SOURCE_REQUIRED')
    return cursor.read_bytes()


def inventory(root=HERE):
    value = json.loads(read_source(root, INVENTORY_NAME))
    if set(value) != {'schema', 'files', 'testFiles'} or value['schema'] != 'WORLD_ENGINE_STUDIO_RUNTIME_INVENTORY_V1':
        raise RuntimeError('STUDIO_EXPLICIT_INVENTORY_REQUIRED')
    observed = set()
    for group in ('files', 'testFiles'):
        names = value[group]
        if not isinstance(names, list) or not names or names != sorted(set(names)) or len(names) > 2048:
            raise RuntimeError('STUDIO_SORTED_DISJOINT_INVENTORY_REQUIRED')
        for name in names:
            if name in observed or name == MANIFEST_NAME:
                raise RuntimeError('STUDIO_SORTED_DISJOINT_INVENTORY_REQUIRED')
            read_source(root, name)
            observed.add(name)
    if not {INVENTORY_NAME, 'studio_manifest.py', 'bootstrap.py', 'server.py', 'studio_runtime.py'} <= set(value['files']):
        raise RuntimeError('STUDIO_CONNECTED_RUNTIME_MUST_BE_BOUND')
    # Every licensed SFX file named by the asset manifest must enter the image.
    if 'audio/ASSET_MANIFEST.json' not in value['files']:
        raise RuntimeError('STUDIO_LICENSED_AUDIO_MANIFEST_REQUIRED')
    audio = json.loads(read_source(root, 'audio/ASSET_MANIFEST.json'))
    assets = audio.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 128:
        raise RuntimeError('STUDIO_LICENSED_AUDIO_ASSETS_REQUIRED')
    licensed = set()
    for asset in assets:
        if not isinstance(asset, dict) or asset.get('license') != 'CC0-1.0':
            raise RuntimeError('STUDIO_AUDIO_LICENSE_UNVERIFIED')
        name = asset.get('file')
        if not isinstance(name, str) or not name.endswith('.wav'):
            raise RuntimeError('STUDIO_AUDIO_ASSET_PATH_REQUIRED')
        name = name if name.startswith('audio/') else 'audio/' + name
        if name in licensed or name not in value['files']:
            raise RuntimeError('STUDIO_AUDIO_ASSET_NOT_MANIFESTED')
        raw = read_source(root, name)
        digest = asset.get('sha256')
        if not HASH.fullmatch(str(digest)) or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('STUDIO_AUDIO_ASSET_SHA_MISMATCH')
        licensed.add(name)
    if licensed != {name for name in value['files'] if name.endswith('.wav')}:
        raise RuntimeError('STUDIO_AUDIO_UNLICENSED_PAYLOAD_FORBIDDEN')
    return value


def verify_payload(root=HERE):
    root = Path(root)
    raw = read_source(root, MANIFEST_NAME)
    value = json.loads(raw)
    if (value.get('schema') != SCHEMA or value.get('profileId') != PROFILE_ID
            or value.get('parentImage') != PARENT_IMAGE or value.get('parentManifestSha256') != PARENT_MANIFEST_SHA
            or value.get('parentSourceCommit') != PARENT_SOURCE_COMMIT or value.get('parentInventoryFiles') != PARENT_INVENTORY_FILES
            or value.get('baselineCommit') != BASELINE or not COMMIT.fullmatch(str(value.get('sourceCommit')))):
        raise RuntimeError('STUDIO_FROZEN_PARENT_PROVENANCE_REQUIRED')
    declared = inventory(root)
    expected_paths = {MANIFEST_NAME}
    for group in ('files', 'testFiles'):
        entries = value.get(group)
        if not isinstance(entries, dict) or sorted(entries) != declared[group]:
            raise RuntimeError('STUDIO_EXACT_PAYLOAD_CLOSURE_REQUIRED')
        for name, digest in entries.items():
            if not HASH.fullmatch(str(digest)) or hashlib.sha256(read_source(root, name)).hexdigest() != digest:
                raise RuntimeError('STUDIO_SOURCE_SHA_MISMATCH')
            expected_paths.add(name)
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('STUDIO_SOURCE_SYMLINK_FORBIDDEN')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected_paths:
        raise RuntimeError('STUDIO_UNEXPECTED_PAYLOAD_FILE')
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
        'sourceCommit': value['sourceCommit'], 'manifestSha256': hashlib.sha256(raw).hexdigest(),
        'files': len(expected_paths), 'gpuExecuted': False, 'testOnly': True}


def verify_sources(root=HERE):
    result = verify_payload(root)
    parent_root = Path('/opt/rtx-package/repo') / PARENT_NAMESPACE
    raw = read_source(parent_root, 'FRONT_FILES.json')
    if hashlib.sha256(raw).hexdigest() != PARENT_MANIFEST_SHA:
        raise RuntimeError('STUDIO_FROZEN_PARENT_MANIFEST_CHANGED')
    spec = importlib.util.spec_from_file_location('_studio_frozen_v4_verifier', parent_root / 'source_manifest_recovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.verify_sources()
    if report.get('status') != 'PASS' or report.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise RuntimeError('STUDIO_PARENT_SOURCE_VERIFICATION_FAILED')
    result.update(parent=report, parentInventoryFiles=PARENT_INVENTORY_FILES, testOnly=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_sources(), sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_SOURCE_VERIFICATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
