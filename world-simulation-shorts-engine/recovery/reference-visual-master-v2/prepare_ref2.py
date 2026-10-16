#!/usr/bin/env python3
"""Separate V2 activation over pinned Quality F data preparation; no GPU use."""
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
MANIFEST_FILE = HERE / 'REFERENCE_FILES.json'
BASELINE = '233bca75f38005c314da8f8af3b33c240f7fb89f'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae'
PARENT_MANIFEST_SHA = 'cd025141c88f1d5fa196fc58c3026565ceb386b09926f7036638d78ecb3385ff'
PROFILE_ID = 'REFERENCE_VISUAL_MASTER_V2'
SCHEMA = 'WORLD_ENGINE_REFERENCE_VISUAL_FILES_V2'
_HASH = re.compile(r'[0-9a-f]{64}\Z')
TEST_FILES = frozenset({'software_probe_ref2.mjs', 'gain_ab_probe.mjs', 'source_grade_ab_probe.mjs',
                        'build_source_probe.py', 'outer_glow_ab_probe.mjs'})
parent_file = HERE.parent / 'visual-quality-upgrade-v1/prepare_quality.py'
if hashlib.sha256(parent_file.read_bytes()).hexdigest() != 'ff0c8bbbbb2c4052b2270f35971682eb8951995c976570d5ed9153bbc5522a59':
    raise RuntimeError('PINNED_QUALITY_PREPARATION_REQUIRED')
spec = importlib.util.spec_from_file_location('_reference_v2_original_quality_preparation', parent_file)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ActivationError = base.base.ActivationError


def verify_extension(package_root=Path('/opt/rtx-package'), *, require_staged=True):
    original = base.verify_extension(package_root, require_staged=require_staged)
    if original.get('status') != 'PASS' or original.get('manifestSha256') != PARENT_MANIFEST_SHA:
        raise ActivationError('REFERENCE_PARENT_MANIFEST_MISMATCH')
    raw = base.base._regular(MANIFEST_FILE)
    manifest = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('profileId') != PROFILE_ID
            or manifest.get('baselineCommit') != BASELINE or manifest.get('parentImage') != PARENT_IMAGE
            or manifest.get('parentQualityManifestSha256') != PARENT_MANIFEST_SHA
            or not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('sourceCommit')))
            or not isinstance(manifest.get('files'), dict) or not manifest['files']):
        raise ActivationError('REFERENCE_MANIFEST_REQUIRED')
    count = 0
    for name, expected in manifest['files'].items():
        if (not isinstance(name, str) or '/' in name or not _HASH.fullmatch(str(expected))
                or base.base._sha(base.base._regular(base.base._relative(HERE, name), 64 * 1024 * 1024)) != expected):
            raise ActivationError('REFERENCE_SOURCE_HASH_MISMATCH')
        count += 1
    tools = manifest.get('testFiles')
    if not isinstance(tools, dict) or set(tools) != TEST_FILES:
        raise ActivationError('REFERENCE_TEST_TOOL_MANIFEST_REQUIRED')
    for name, expected in tools.items():
        if (not isinstance(name, str) or '/' in name or not _HASH.fullmatch(str(expected))
                or base.base._sha(base.base._regular(base.base._relative(HERE, name), 64 * 1024 * 1024)) != expected):
            raise ActivationError('REFERENCE_TEST_TOOL_HASH_MISMATCH')
        count += 1
    dependencies = manifest.get('repoDependencies', {})
    if not isinstance(dependencies, dict):
        raise ActivationError('REFERENCE_DEPENDENCY_MANIFEST_REQUIRED')
    for name, expected in dependencies.items():
        if (not _HASH.fullmatch(str(expected))
                or base.base._sha(base.base._regular(base.base._relative(REPO, name), 64 * 1024 * 1024)) != expected):
            raise ActivationError('REFERENCE_DEPENDENCY_HASH_MISMATCH')
        count += 1
    return {'status': 'PASS', 'schema': SCHEMA, 'profileId': PROFILE_ID,
            'manifestSha256': base.base._sha(raw), 'sourceCommit': manifest['sourceCommit'],
            'files': count, 'parent': original, 'testOnly': not require_staged, 'gpuExecuted': False}


def prepare_activation(private_root, variant='F', parameters=None):
    if not isinstance(variant, str) or variant not in tuple('ABCDEF'):
        raise ActivationError('REFERENCE_VARIANT_REQUIRED')
    # Canonical parameter validation/defaults belong to ref2_profiles.mjs and
    # are bound by the runtime source manifest. Preserve overrides verbatim;
    # do not implement a second Python normalizer or claim GPU validation.
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, dict) or any(not isinstance(key, str) for key in parameters):
        raise ActivationError('REFERENCE_PARAMETERS_OBJECT_REQUIRED')
    try:
        overrides = json.dumps(parameters, allow_nan=False, separators=(',', ':'))
        if len(overrides.encode()) > 16 * 1024:
            raise ValueError()
        parameters = json.loads(overrides)
    except (ValueError, TypeError, RecursionError):
        raise ActivationError('REFERENCE_PARAMETERS_INVALID') from None
    prepared = base.prepare_activation(private_root, profile='F')
    old_bytes = base.base._regular(prepared['activationFile'])
    if base.base._sha(old_bytes) != prepared['activationSha256']:
        raise ActivationError('REFERENCE_PREPARED_SOURCE_CHANGED')
    activation = json.loads(old_bytes)
    if activation.get('quality') != {'profile': 'F'}:
        raise ActivationError('REFERENCE_QUALITY_F_BASE_REQUIRED')
    activation.update(profileId=PROFILE_ID + '_' + variant,
                      referenceV2={'variant': variant, 'parameters': parameters})
    raw = (json.dumps(activation, indent=2, allow_nan=False) + '\n').encode()
    target = Path(prepared['activationFile']).parent / ('reference_v2_activation_' + variant + '.json')
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as destination:
        destination.write(raw)
        destination.flush()
        os.fsync(destination.fileno())
    return {**prepared, 'activationFile': str(target), 'activationSha256': base.base._sha(raw),
            'profileId': activation['profileId'], 'referenceVariant': variant, 'qualityProfile': 'F',
            'parameterValidation': 'CANONICAL_JS_RUNTIME_REQUIRED',
            'originalSceneAndDataPreserved': True, 'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--verify-extension', action='store_true')
    choice.add_argument('--prepare-activation', action='store_true')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--variant', choices=tuple('ABCDEF'), default='F')
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify_extension:
            result = verify_extension(require_staged=not args.source_only)
        elif args.private_root is not None and not args.source_only:
            result = prepare_activation(args.private_root, variant=args.variant)
        else:
            raise ActivationError('REFERENCE_EXPLICIT_ARGUMENTS_REQUIRED')
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except Exception as error:
        code = str(error)
        if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code) is None:
            code = 'REFERENCE_PREPARATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
