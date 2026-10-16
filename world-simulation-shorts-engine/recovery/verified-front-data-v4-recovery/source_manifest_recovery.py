#!/usr/bin/env python3
"""Verify a strictly additive archival-front extension over the frozen V3 image."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = 'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4'
PROFILE_ID = 'VERIFIED_ARCHIVAL_FRONT_V4'
MANIFEST_NAME = 'FRONT_FILES.json'
INVENTORY_NAME = 'RUNTIME_INVENTORY.json'
PARENT_NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-production-v3'
PARENT_SOURCE_COMMIT = 'df9a4f414fc4515b11b87258a2daa21d3f4b8e3a'
PARENT_MANIFEST_SHA = 'e1efd170f05d297ba222995af2557dc8d5d338f870c7d92c5a82f456f5d804e6'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb'
PARENT_INVENTORY_FILES = 272
PARENT_ADDITIONS = 110
HASH = re.compile(r'[a-f0-9]{64}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')


def read_source(root: Path, name: str) -> bytes:
    """Never follow symlinks, normalize paths, or silently change source bytes."""
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise RuntimeError('FRONT_CANONICAL_SOURCE_REQUIRED')
    cursor = Path(root)
    if cursor.is_symlink():
        raise RuntimeError('FRONT_SOURCE_SYMLINK_FORBIDDEN')
    for part in name.split('/'):
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError('FRONT_SOURCE_SYMLINK_FORBIDDEN')
    if not cursor.is_file() or not 0 < cursor.stat().st_size <= 64 * 1024**2:
        raise RuntimeError('FRONT_BOUNDED_REGULAR_SOURCE_REQUIRED')
    return cursor.read_bytes()


def parent_closure(repo: Path | None = None):
    """Preserve 110 additive files plus the original 162-file parent inventory."""
    root = Path(repo) if repo is not None else REPO
    raw = read_source(root, PARENT_NAMESPACE + '/PRODUCTION_FILES.json')
    if hashlib.sha256(raw).hexdigest() != PARENT_MANIFEST_SHA:
        raise RuntimeError('FRONT_FROZEN_PARENT_MANIFEST_CHANGED')
    parent = json.loads(raw)
    if (parent.get('schema') != 'WORLD_ENGINE_UNIVERSAL_PRODUCTION_FILES_V3'
            or parent.get('sourceCommit') != PARENT_SOURCE_COMMIT):
        raise RuntimeError('FRONT_FROZEN_PARENT_PROVENANCE_REQUIRED')
    inherited = dict(parent['repoDependencies'])
    for group in ({PARENT_NAMESPACE + '/' + key: value for key, value in parent['files'].items()},
                  {PARENT_NAMESPACE + '/' + key: value for key, value in parent['testFiles'].items()},
                  {PARENT_NAMESPACE + '/PRODUCTION_FILES.json': PARENT_MANIFEST_SHA}):
        if inherited.keys() & group.keys():
            raise RuntimeError('FRONT_PARENT_DUPLICATE_SOURCE')
        inherited.update(group)
    if len(inherited) != PARENT_ADDITIONS:
        raise RuntimeError('FRONT_EXACT_PARENT_CLOSURE_REQUIRED')
    for name, expected in inherited.items():
        if not HASH.fullmatch(str(expected)) or hashlib.sha256(read_source(root, name)).hexdigest() != expected:
            raise RuntimeError('FRONT_FROZEN_PARENT_SOURCE_CHANGED')
    return parent, inherited


def inventory(root: Path | None = None):
    root = HERE if root is None else Path(root)
    document = json.loads(read_source(root, INVENTORY_NAME))
    if set(document) != {'schema', 'files', 'testFiles'} or document['schema'] != 'WORLD_ENGINE_FRONT_RUNTIME_INVENTORY_V4':
        raise RuntimeError('FRONT_EXPLICIT_RUNTIME_INVENTORY_REQUIRED')
    rows = []
    for key in ('files', 'testFiles'):
        names = document[key]
        if not isinstance(names, list) or not names or len(names) > 1024 or names != sorted(set(names)):
            raise RuntimeError('FRONT_SORTED_DISJOINT_INVENTORY_REQUIRED')
        for name in names:
            if name in rows or name == MANIFEST_NAME:
                raise RuntimeError('FRONT_SORTED_DISJOINT_INVENTORY_REQUIRED')
            read_source(root, name)
            rows.append(name)
    if INVENTORY_NAME not in document['files'] or 'source_manifest_recovery.py' not in document['files']:
        raise RuntimeError('FRONT_VERIFIER_AND_INVENTORY_MUST_BE_BOUND')
    if document['testFiles'] != ['software_probe_front.mjs']:
        raise RuntimeError('FRONT_ACTUAL_SOFTWARE_PROBE_MUST_BE_BOUND')
    # A file can exist in the checkout/test bind while still being omitted from
    # the image's explicit COPY closure. Follow profile dependencies, regardless
    # of filename extension, before generating any manifest or running a draw.
    if 'FRONT_PROFILE.json' not in document['files']:
        raise RuntimeError('FRONT_PROFILE_MUST_BE_BOUND')
    profile = json.loads(read_source(root, 'FRONT_PROFILE.json'))
    if (profile.get('schema') != 'WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4'
            or profile.get('runtimeProfile') != PROFILE_ID
            or not isinstance(profile.get('fronts'), list) or not profile['fronts']):
        raise RuntimeError('FRONT_PROFILE_SOURCE_CLOSURE_REQUIRED')
    for front in profile['fronts']:
        name, expected = front.get('sourceFile'), front.get('geoJsonSha256')
        if name not in document['files']:
            raise RuntimeError('FRONT_PROFILE_SOURCE_NOT_IN_RUNTIME_INVENTORY')
        raw = read_source(root, name)
        if not HASH.fullmatch(str(expected)) or hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError('FRONT_PROFILE_SOURCE_SHA_MISMATCH')
    return document


def verify_sources(package_root=Path('/opt/rtx-package'), *, require_staged=True):
    raw = read_source(HERE, MANIFEST_NAME)
    manifest = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('profileId') != PROFILE_ID
            or manifest.get('family') != PROFILE_ID or manifest.get('parentImage') != PARENT_IMAGE
            or manifest.get('parentManifestSha256') != PARENT_MANIFEST_SHA
            or manifest.get('parentSourceCommit') != PARENT_SOURCE_COMMIT
            or manifest.get('parentInventoryFiles') != PARENT_INVENTORY_FILES
            or not COMMIT.fullmatch(str(manifest.get('sourceCommit')))
            or not isinstance(manifest.get('files'), dict) or not isinstance(manifest.get('testFiles'), dict)):
        raise RuntimeError('FRONT_MANIFEST_REQUIRED')
    _, inherited = parent_closure()
    if manifest.get('repoDependencies') != inherited:
        raise RuntimeError('FRONT_PARENT_CLOSURE_MISMATCH')
    declared = inventory()
    for group in ('files', 'testFiles'):
        if sorted(manifest[group]) != declared[group]:
            raise RuntimeError('FRONT_EXACT_NEW_SOURCE_CLOSURE_REQUIRED')
        for name, expected in manifest[group].items():
            if not HASH.fullmatch(str(expected)) or hashlib.sha256(read_source(HERE, name)).hexdigest() != expected:
                raise RuntimeError('FRONT_SOURCE_HASH_MISMATCH')
    verifier = REPO / PARENT_NAMESPACE / 'source_manifest.py'
    spec = importlib.util.spec_from_file_location('_front_frozen_v3_verifier', verifier)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    report = original.verify_sources(package_root=package_root, require_staged=require_staged)
    if report.get('status') != 'PASS' or report.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise RuntimeError('FRONT_PARENT_VERIFICATION_FAILED')
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
        'sourceCommit': manifest['sourceCommit'], 'manifestSha256': hashlib.sha256(raw).hexdigest(),
        'files': len(manifest['files']) + len(manifest['testFiles']),
        'parentInventoryFiles': PARENT_INVENTORY_FILES, 'parent': report,
        'testOnly': not require_staged, 'gpuExecuted': False}


verify_extension = verify_sources


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-extension', action='store_true', required=True)
    parser.add_argument('--source-only', action='store_true')
    parser.add_argument('--package-root', type=Path, default=Path('/opt/rtx-package'))
    arguments = parser.parse_args()
    try:
        print(json.dumps(verify_sources(arguments.package_root, require_staged=not arguments.source_only), sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'FRONT_SOURCE_VERIFICATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
