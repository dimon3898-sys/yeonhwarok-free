#!/usr/bin/env python3
"""Strict additive production closure over the immutable universal V2 image."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = 'WORLD_ENGINE_UNIVERSAL_PRODUCTION_FILES_V3'
PROFILE_ID = 'UNIVERSAL_PRODUCTION_V3'
MANIFEST_NAME = 'PRODUCTION_FILES.json'
PARENT_NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-auto-video-v2'
PARENT_SOURCE_COMMIT = '311a92137d00ba88220c1caa243c9ff0389e4121'
PARENT_MANIFEST_SHA = '982cf2c0a5f435afe936605c0aeb76cbf40b6990da41d27c0ea0bd5ef22eb756'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014'
PARENT_ADDITIONS = 86
PARENT_INVENTORY_FILES = 248
HASH = re.compile(r'[a-f0-9]{64}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')


def read_source(root: Path, name: str) -> bytes:
    """Read a bounded canonical regular source, rejecting every symlink parent."""
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise RuntimeError('PRODUCTION_CANONICAL_SOURCE_REQUIRED')
    cursor = Path(root)
    if cursor.is_symlink():
        raise RuntimeError('PRODUCTION_SOURCE_SYMLINK_FORBIDDEN')
    for part in name.split('/'):
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError('PRODUCTION_SOURCE_SYMLINK_FORBIDDEN')
    if not cursor.is_file() or not 0 < cursor.stat().st_size <= 64 * 1024**2:
        raise RuntimeError('PRODUCTION_BOUNDED_REGULAR_SOURCE_REQUIRED')
    return cursor.read_bytes()


def parent_closure(repo: Path | None = None):
    """Derive the exact inherited 86-file extension; never regenerate V2 hashes."""
    root = Path(repo) if repo is not None else REPO
    raw = read_source(root, PARENT_NAMESPACE + '/UNIVERSAL_FILES.json')
    if hashlib.sha256(raw).hexdigest() != PARENT_MANIFEST_SHA:
        raise RuntimeError('PRODUCTION_FROZEN_PARENT_MANIFEST_CHANGED')
    parent = json.loads(raw)
    if (parent.get('schema') != 'WORLD_ENGINE_UNIVERSAL_AUTO_VIDEO_FILES_V2'
            or parent.get('sourceCommit') != PARENT_SOURCE_COMMIT):
        raise RuntimeError('PRODUCTION_FROZEN_PARENT_PROVENANCE_REQUIRED')
    inherited = dict(parent['repoDependencies'])
    groups = [parent['additionalRepoFiles'],
        {PARENT_NAMESPACE + '/' + key: value for key, value in parent['files'].items()},
        {PARENT_NAMESPACE + '/' + key: value for key, value in parent['testFiles'].items()},
        {PARENT_NAMESPACE + '/UNIVERSAL_FILES.json': PARENT_MANIFEST_SHA}]
    for group in groups:
        if inherited.keys() & group.keys():
            raise RuntimeError('PRODUCTION_PARENT_DUPLICATE_SOURCE')
        inherited.update(group)
    if len(inherited) != PARENT_ADDITIONS:
        raise RuntimeError('PRODUCTION_EXACT_PARENT_CLOSURE_REQUIRED')
    for name, expected in inherited.items():
        if not HASH.fullmatch(str(expected)) or hashlib.sha256(read_source(root, name)).hexdigest() != expected:
            raise RuntimeError('PRODUCTION_FROZEN_PARENT_SOURCE_CHANGED')
    return parent, inherited


def verify_sources(package_root=Path('/opt/rtx-package'), *, require_staged=True):
    raw = read_source(HERE, MANIFEST_NAME)
    manifest = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('profileId') != PROFILE_ID
            or manifest.get('family') != PROFILE_ID or manifest.get('parentImage') != PARENT_IMAGE
            or manifest.get('parentManifestSha256') != PARENT_MANIFEST_SHA
            or manifest.get('parentSourceCommit') != PARENT_SOURCE_COMMIT
            or manifest.get('parentInventoryFiles') != PARENT_INVENTORY_FILES
            or not COMMIT.fullmatch(str(manifest.get('sourceCommit')))
            or not isinstance(manifest.get('files'), dict) or 'source_manifest.py' not in manifest['files']
            or not isinstance(manifest.get('testFiles'), dict)):
        raise RuntimeError('PRODUCTION_MANIFEST_REQUIRED')
    parent, inherited = parent_closure()
    closure = json.loads(read_source(HERE, 'PARENT_CLOSURE.json'))
    expected_closure = {'schema': 'WORLD_ENGINE_PRODUCTION_PARENT_CLOSURE_V3',
        'parentImage': PARENT_IMAGE, 'parentSourceCommit': PARENT_SOURCE_COMMIT,
        'parentManifestSha256': PARENT_MANIFEST_SHA, 'parentInventoryFiles': PARENT_INVENTORY_FILES,
        'originalReceiptFiles': 160, 'inventoryMetadataFiles': 2, 'additiveFiles': inherited}
    if closure != expected_closure or manifest.get('repoDependencies') != inherited:
        raise RuntimeError('PRODUCTION_PARENT_CLOSURE_MISMATCH')
    names = set()
    for group in ('files', 'testFiles'):
        for name, expected in manifest[group].items():
            if name in names or not HASH.fullmatch(str(expected)):
                raise RuntimeError('PRODUCTION_SOURCE_BINDING_INVALID')
            names.add(name)
            if hashlib.sha256(read_source(HERE, name)).hexdigest() != expected:
                raise RuntimeError('PRODUCTION_SOURCE_HASH_MISMATCH')
    verifier = REPO / PARENT_NAMESPACE / 'universal_files.py'
    # Its bytes were checked against the frozen parent before importing it.
    specification = importlib.util.spec_from_file_location('_production_frozen_v2_verifier', verifier)
    original = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(original)
    report = original.verify_extension(package_root=package_root, require_staged=require_staged)
    if report.get('status') != 'PASS' or report.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise RuntimeError('PRODUCTION_PARENT_VERIFICATION_FAILED')
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
        'sourceCommit': manifest['sourceCommit'], 'manifestSha256': hashlib.sha256(raw).hexdigest(),
        'files': len(names), 'frozenParentAdditiveFiles': len(inherited),
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
            code = 'PRODUCTION_SOURCE_VERIFICATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
