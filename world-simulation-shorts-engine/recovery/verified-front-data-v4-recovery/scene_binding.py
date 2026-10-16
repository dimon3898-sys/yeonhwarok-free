"""Hash-bind archival data to the immutable parent plan without retiming it.

The existing V3 scene allocator remains the sole scene/cache contract owner.
This module supplies data identity, not new historical coordinates or GPU proof.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PRODUCTION = HERE.parent / 'universal-production-v3'
PROFILE_ID = 'VERIFIED_ARCHIVAL_FRONT_V4'
PARENT_PLAN_SHA256 = '6fb40abd4970c2595877c4bfb469d8ad0d62e552a03651748b8a1c41a993c28b'
PLANNER_SHA256 = '7b7bfbe132903714279f5308d32827fe80a34578fbb5a3bd7f6747e584919f62'
HASH = re.compile(r'[a-f0-9]{64}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')


def _read(path, maximum=16 * 1024**2):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('FRONT_EXECUTION_SOURCE_SYMLINK_FORBIDDEN')
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= maximum:
        raise ValueError('FRONT_EXECUTION_BOUNDED_SOURCE_REQUIRED')
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('FRONT_EXECUTION_SOURCE_CHANGED_DURING_READ')
    return raw


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('FRONT_EXECUTION_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('FRONT_EXECUTION_FINITE_JSON_REQUIRED')))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _planner():
    path = PRODUCTION / 'scene_planner.py'
    if _sha(_read(path)) != PLANNER_SHA256:
        raise ValueError('FRONT_FROZEN_V3_PLANNER_CHANGED')
    spec = importlib.util.spec_from_file_location('_archival_front_v4_frozen_planner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parent_plan():
    raw = _read(HERE / 'PARENT_PLAN_80S.json')
    if _sha(raw) != PARENT_PLAN_SHA256:
        raise ValueError('FRONT_IMMUTABLE_PARENT_PLAN_CHANGED')
    plan = _json(raw)
    _planner().validate_production_plan(plan, require_renderable=True)
    return plan


def source_binding():
    manifest_raw = _read(HERE / 'FRONT_FILES.json', 4 * 1024**2)
    manifest = _json(manifest_raw)
    profile_raw = _read(HERE / 'FRONT_PROFILE.json')
    if (manifest.get('schema') != 'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4'
            or manifest.get('profileId') != PROFILE_ID
            or manifest.get('files', {}).get('FRONT_PROFILE.json') != _sha(profile_raw)):
        raise ValueError('FRONT_EXECUTION_PROFILE_MANIFEST_BINDING_REQUIRED')
    return {'profileId': PROFILE_ID, 'profileSha256': _sha(profile_raw),
            'sourceManifestSha256': _sha(manifest_raw)}


def derive_execution_plan(original, *, image_digest, front_profile_sha256,
                          front_manifest_sha256):
    if original != parent_plan():
        raise ValueError('FRONT_EXECUTION_UNCHANGED_PARENT_PLAN_REQUIRED')
    if not isinstance(image_digest, str) or not DIGEST.fullmatch(image_digest):
        raise ValueError('FRONT_EXECUTION_IMMUTABLE_IMAGE_REQUIRED')
    if any(not isinstance(value, str) or not HASH.fullmatch(value)
           for value in (front_profile_sha256, front_manifest_sha256)):
        raise ValueError('FRONT_EXECUTION_DATA_HASHES_REQUIRED')
    plan = deepcopy(original)
    plan['renderProfile']['imageDigest'] = image_digest
    plan['sourceManifest']['archivalFrontV4'] = {
        'profileId': PROFILE_ID, 'profileSha256': front_profile_sha256,
        'sourceManifestSha256': front_manifest_sha256}
    planner = _planner()
    plan['scenes'] = planner._work_scenes(plan, plan['splitPolicy']['maxSceneFrames'])
    planner.validate_production_plan(plan, require_renderable=True)
    return plan


def validate_execution_plan(plan):
    binding = source_binding()
    expected = derive_execution_plan(parent_plan(),
        image_digest=plan.get('renderProfile', {}).get('imageDigest'),
        front_profile_sha256=binding['profileSha256'],
        front_manifest_sha256=binding['sourceManifestSha256'])
    if plan != expected:
        raise ValueError('FRONT_EXECUTION_PLAN_DATA_OR_TIMELINE_MISMATCH')
    return plan


def verify_sources():
    """Bind the fixed new verifier before its strict inherited image check."""
    manifest = _json(_read(HERE / 'FRONT_FILES.json', 4 * 1024**2))
    path = HERE / 'source_manifest_recovery.py'
    expected = manifest.get('files', {}).get(path.name)
    if not isinstance(expected, str) or not HASH.fullmatch(expected) or _sha(_read(path)) != expected:
        raise ValueError('FRONT_EXECUTION_SOURCE_VERIFIER_CHANGED')
    spec = importlib.util.spec_from_file_location('_archival_front_execution_verifier', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_sources(require_staged=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-digest', required=True)
    args = parser.parse_args(argv)
    binding = source_binding()
    result = derive_execution_plan(parent_plan(), image_digest=args.image_digest,
        front_profile_sha256=binding['profileSha256'], front_manifest_sha256=binding['sourceManifestSha256'])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
