#!/usr/bin/env python3
"""Separate quality profile preparation; original ASTRA source pipeline unchanged."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MANIFEST_FILE = HERE / 'QUALITY_FILES.json'
BASELINE = 'a7df81f6ad246333fe826270c14c242e477362d4'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8aba498e295b45a9cbfa29eeacd6f7779ff3d2ce4482c92215176be1540ff71a'
PARENT_MANIFEST_SHA = '8264f51f52693a0ce80ed167d0d25fa56c6d5505b5cc01712c2d198c6448f330'
PROFILE_ID = 'VISUAL_QUALITY_UPGRADE_V1'
SCHEMA = 'WORLD_ENGINE_VISUAL_QUALITY_FILES_V1'
_HASH = re.compile(r'[0-9a-f]{64}\Z')
parent_file = HERE.parent / 'astra-gpu-activation-v1/prepare_activation.py'
if hashlib.sha256(parent_file.read_bytes()).hexdigest() != 'fc55ba7c20894d7ab89452ef168a3837575b88f075b358a2bf7bc443c33c6a6f':
    raise RuntimeError('PINNED_ASTRA_PREPARATION_REQUIRED')
spec = importlib.util.spec_from_file_location('_quality_original_astra_preparation', parent_file)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def verify_extension(package_root=Path('/opt/rtx-package'), *, require_staged=True):
    original = base.verify_extension(package_root, require_staged=require_staged)
    if original.get('status') != 'PASS' or original.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise base.ActivationError('QUALITY_PARENT_MANIFEST_MISMATCH')
    raw = base._regular(MANIFEST_FILE)
    manifest = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('profileId') != PROFILE_ID
            or manifest.get('baselineCommit') != BASELINE or manifest.get('parentImage') != PARENT_IMAGE
            or not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('sourceCommit')))
            or not isinstance(manifest.get('files'), dict) or not manifest['files']):
        raise base.ActivationError('QUALITY_MANIFEST_REQUIRED')
    count = 0
    for name, expected in manifest['files'].items():
        if ('/' in name or not _HASH.fullmatch(str(expected))
                or base._sha(base._regular(base._relative(HERE, name), 64*1024*1024)) != expected):
            raise base.ActivationError('QUALITY_SOURCE_HASH_MISMATCH')
        count += 1
    dependencies = manifest.get('repoDependencies', {})
    if not isinstance(dependencies, dict):
        raise base.ActivationError('QUALITY_DEPENDENCY_MANIFEST_REQUIRED')
    for name, expected in dependencies.items():
        if (not _HASH.fullmatch(str(expected))
                or base._sha(base._regular(base._relative(REPO, name), 64*1024*1024)) != expected):
            raise base.ActivationError('QUALITY_DEPENDENCY_HASH_MISMATCH')
        count += 1
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
            'manifestSha256': base._sha(raw), 'sourceCommit': manifest['sourceCommit'],
            'files': count, 'parent': original, 'testOnly': not require_staged, 'gpuExecuted': False}


def prepare_activation(private_root, profile='F'):
    if not isinstance(profile, str) or profile not in tuple('ABCDEF'):
        raise base.ActivationError('QUALITY_PROFILE_REQUIRED')
    prepared = base.prepare_activation(private_root)
    original = json.loads(base._regular(prepared['activationFile']))
    if base._sha(base._regular(prepared['activationFile'])) != prepared['activationSha256']:
        raise base.ActivationError('QUALITY_PREPARED_SOURCE_CHANGED')
    original.update(profileId=PROFILE_ID + '_' + profile, quality={'profile': profile})
    raw = (json.dumps(original, indent=2, allow_nan=False) + '\n').encode()
    target = Path(prepared['activationFile']).parent / ('quality_activation_' + profile + '.json')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as destination:
        destination.write(raw)
        destination.flush()
        os.fsync(destination.fileno())
    return {**prepared, 'activationFile': str(target), 'activationSha256': base._sha(raw),
            'profileId': original['profileId'], 'qualityProfile': profile,
            'originalSceneAndDataPreserved': True, 'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--verify-extension', action='store_true')
    choice.add_argument('--prepare-activation', action='store_true')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--profile', choices=tuple('ABCDEF'), default='F')
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify_extension:
            result = verify_extension(require_staged=not args.source_only)
        elif args.private_root is not None and not args.source_only:
            result = prepare_activation(args.private_root, profile=args.profile)
        else:
            raise base.ActivationError('QUALITY_EXPLICIT_ARGUMENTS_REQUIRED')
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except Exception as error:
        code = str(error)
        if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) is None:
            code = 'QUALITY_PREPARATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
