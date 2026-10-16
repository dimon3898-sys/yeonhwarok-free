#!/usr/bin/env python3
"""Hash-bound additive universal runtime; the frozen reference V2 is never rewritten."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = 'WORLD_ENGINE_UNIVERSAL_AUTO_VIDEO_FILES_V2'
PROFILE_ID = 'UNIVERSAL_AUTO_VIDEO_V2'
MANIFEST_NAME = 'UNIVERSAL_FILES.json'
PARENT_NAMESPACE = 'world-simulation-shorts-engine/recovery/reference-visual-master-v2'
PARENT_MANIFEST_SHA = '28de18a52014ba56e91c31f91af40bc4f81c81b92e0fcf85bd83a651f7da3606'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5'
HASH = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')


def _bytes(root: Path, name: str) -> bytes:
    if (not isinstance(name, str) or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(part in ('', '.', '..') for part in PurePosixPath(name).parts)):
        raise RuntimeError('UNIVERSAL_SOURCE_PATH_INVALID')
    current = root
    for part in PurePosixPath(name).parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError('UNIVERSAL_SOURCE_SYMLINK_FORBIDDEN')
    if not current.is_file() or not 0 < current.stat().st_size <= 64 * 1024**2:
        raise RuntimeError('UNIVERSAL_REGULAR_SOURCE_REQUIRED')
    return current.read_bytes()


def frozen_parent_files(repo: Path = REPO):
    root = Path(repo)
    raw = _bytes(root, PARENT_NAMESPACE + '/REFERENCE_FILES.json')
    if hashlib.sha256(raw).hexdigest() != PARENT_MANIFEST_SHA:
        raise RuntimeError('FROZEN_REFERENCE_MANIFEST_CHANGED')
    parent = json.loads(raw)
    files = dict(parent['repoDependencies'])
    for group in ('files', 'testFiles'):
        files.update({PARENT_NAMESPACE + '/' + name: digest for name, digest in parent[group].items()})
    files[PARENT_NAMESPACE + '/REFERENCE_FILES.json'] = PARENT_MANIFEST_SHA
    if len(files) != 57:
        raise RuntimeError('EXACT_REFERENCE_PARENT_CLOSURE_REQUIRED')
    for name, expected in files.items():
        if not HASH.fullmatch(str(expected)) or hashlib.sha256(_bytes(root, name)).hexdigest() != expected:
            raise RuntimeError('FROZEN_REFERENCE_SOURCE_CHANGED')
    return parent, files


def verify_files(package_root=Path('/opt/rtx-package'), *, require_staged=True):
    raw = _bytes(HERE, MANIFEST_NAME)
    manifest = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('profileId') != PROFILE_ID
            or manifest.get('family') != PROFILE_ID
            or manifest.get('parentImage') != PARENT_IMAGE
            or manifest.get('parentReferenceManifestSha256') != PARENT_MANIFEST_SHA
            or not COMMIT.fullmatch(str(manifest.get('sourceCommit')))
            or not isinstance(manifest.get('files'), dict) or not manifest['files']
            or 'universal_files.py' not in manifest['files']
            or not isinstance(manifest.get('testFiles'), dict)):
        raise RuntimeError('UNIVERSAL_MANIFEST_REQUIRED')
    parent, dependencies = frozen_parent_files()
    if manifest.get('repoDependencies') != dependencies:
        raise RuntimeError('UNIVERSAL_PARENT_CLOSURE_MISMATCH')
    additions = manifest.get('additionalRepoFiles')
    if not isinstance(additions, dict) or set(additions) & set(dependencies):
        raise RuntimeError('UNIVERSAL_SUPPLEMENTAL_CLOSURE_REQUIRED')
    for name, expected in additions.items():
        if not HASH.fullmatch(str(expected)) or hashlib.sha256(_bytes(REPO, name)).hexdigest() != expected:
            raise RuntimeError('UNIVERSAL_SUPPLEMENTAL_SOURCE_CHANGED')
    paths = set()
    for group in ('files', 'testFiles'):
        for name, expected in manifest[group].items():
            if name in paths or not HASH.fullmatch(str(expected)):
                raise RuntimeError('UNIVERSAL_SOURCE_BINDING_INVALID')
            paths.add(name)
            if hashlib.sha256(_bytes(HERE, name)).hexdigest() != expected:
                raise RuntimeError('UNIVERSAL_SOURCE_HASH_MISMATCH')
    target = REPO / PARENT_NAMESPACE / 'prepare_ref2.py'
    if hashlib.sha256(target.read_bytes()).hexdigest() != parent['files']['prepare_ref2.py']:
        raise RuntimeError('PINNED_REFERENCE_PREPARATION_REQUIRED')
    spec = importlib.util.spec_from_file_location('_universal_frozen_reference_verifier', target)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    report = original.verify_extension(package_root=package_root, require_staged=require_staged)
    if report.get('status') != 'PASS' or report.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise RuntimeError('UNIVERSAL_PARENT_VERIFICATION_FAILED')
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
            'sourceCommit': manifest['sourceCommit'], 'manifestSha256': hashlib.sha256(raw).hexdigest(),
            'files': len(paths), 'frozenReferenceFiles': len(dependencies), 'parent': report,
            'supplementalFiles': len(additions),
            'testOnly': not require_staged, 'gpuExecuted': False}


def check_supplemental_absent():
    """Run before Docker COPY; adding old assets must not overwrite base bytes."""
    manifest = json.loads(_bytes(HERE, MANIFEST_NAME))
    additions = manifest.get('additionalRepoFiles')
    if manifest.get('schema') != SCHEMA or not isinstance(additions, dict):
        raise RuntimeError('UNIVERSAL_SUPPLEMENTAL_CLOSURE_REQUIRED')
    for name in additions:
        if (not isinstance(name, str) or str(PurePosixPath(name)) != name
                or PurePosixPath(name).is_absolute() or '\\' in name
                or any(part in ('', '.', '..') for part in PurePosixPath(name).parts)):
            raise RuntimeError('UNIVERSAL_SOURCE_PATH_INVALID')
        if (REPO / name).exists() or (REPO / name).is_symlink():
            raise RuntimeError('SUPPLEMENTAL_WOULD_OVERWRITE_PARENT_FILE')
    return {'status': 'PASS', 'supplementalFilesAbsent': len(additions), 'gpuExecuted': False}


# Python and CLI use the same strict verifier; no duplicate integrity engine.
verify_extension = verify_files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify-files', '--verify-extension', action='store_true')
    action.add_argument('--check-supplemental-absent', action='store_true')
    parser.add_argument('--source-only', '--allow-unstaged-for-cpu', action='store_true')
    parser.add_argument('--package-root', type=Path, default=Path('/opt/rtx-package'))
    args = parser.parse_args()
    try:
        result = check_supplemental_absent() if args.check_supplemental_absent else verify_files(package_root=args.package_root, require_staged=not args.source_only)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'UNIVERSAL_SOURCE_VERIFICATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
