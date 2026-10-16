#!/usr/bin/env python3
"""Bind catalog-native inputs and reuse the frozen CPU ASTRA preparation once.

No browser, GPU context, renderer frame, old claim or completed result is touched.
A prepared plan is immutable: authorization must be issued after this binding.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from contracts import ContractError, canonical_json, canonical_sha256, validate_plan
from planner import DEFAULT_CATALOG, ENGINE, _bound_file, bind_renderer, plan_topic
from cache import PrivateTree

NATIVE_SCHEMA = 'WORLD_ENGINE_UNIVERSAL_NATIVE_INPUT_V1'
INPUT_SCHEMA = 'WORLD_ENGINE_UNIVERSAL_PREPARED_INPUTS_V1'
NATIVE_KEYS = ('regionalPlan', 'continentPlan', 'scene', 'cameraPlan', 'inputManifest')
MAX_SOURCE_BYTES = 64 * 1024**2
MAX_PREPARED_BYTES = 512 * 1024**2
HASH = re.compile(r'[0-9a-f]{64}\Z')


class PreparationError(ContractError):
    pass


def _safe_regular(path, limit=MAX_SOURCE_BYTES):
    path = Path(path)
    if not path.is_absolute() or path != Path(os.path.abspath(path)) or '..' in path.parts:
        raise PreparationError('CANONICAL_ABSOLUTE_FILE_REQUIRED')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise PreparationError('SOURCE_SYMLINK_FORBIDDEN')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise PreparationError('BOUNDED_REGULAR_SOURCE_REQUIRED')
        body = bytearray()
        while len(body) < before.st_size:
            block = os.read(descriptor, min(1024 * 1024, before.st_size - len(body)))
            if not block:
                raise PreparationError('SOURCE_CHANGED_DURING_READ')
            body.extend(block)
        after = os.fstat(descriptor)
        current = os.stat(path, follow_symlinks=False)
        fields = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if fields(before) != fields(after) or fields(current) != fields(before):
            raise PreparationError('SOURCE_CHANGED_DURING_READ')
        return bytes(body)
    finally:
        os.close(descriptor)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _engine_file(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value or value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/')):
        raise PreparationError('NATIVE_ENGINE_RELATIVE_PATH_REQUIRED')
    return ENGINE / value


def _payload_path(value):
    path = Path(value)
    return path if path.is_absolute() else _engine_file(value)


def _catalog_entry(plan, catalog_path):
    raw = _safe_regular(Path(catalog_path).absolute())
    if _sha(raw) != plan['sourceManifest']['catalogSHA256']:
        raise PreparationError('PLAN_CATALOG_HASH_MISMATCH')
    catalog = json.loads(raw)
    entries = [entry for entry in catalog.get('entries', []) if entry.get('subjectId') == plan.get('subjectId') and entry.get('factsSHA256') == plan['sourceManifest']['factsSHA256']]
    if len(entries) != 1:
        raise PreparationError('NATIVE_CATALOG_ENTRY_REQUIRED')
    return entries[0]


def build_native_payload(plan, *, catalog_path=DEFAULT_CATALOG):
    """Fixture wiring is reviewed catalog data, never a country branch in code."""
    validate_plan(plan)
    entry = _catalog_entry(plan, catalog_path)
    fixture_ref = entry.get('nativeRuntimeFixture')
    if not isinstance(fixture_ref, dict) or not HASH.fullmatch(str(fixture_ref.get('sha256', ''))):
        raise PreparationError('CATALOG_NATIVE_RUNTIME_FIXTURE_REQUIRED')
    fixture_file = _bound_file(fixture_ref.get('path'), fixture_ref['sha256'], 'nativeRuntimeFixture')
    fixture = json.loads(_safe_regular(fixture_file))
    files = fixture.get('nativeFiles')
    if not isinstance(files, dict) or set(files) != set(NATIVE_KEYS):
        raise PreparationError('EXACT_FIVE_NATIVE_FILES_REQUIRED')
    payload = {'schema': NATIVE_SCHEMA, 'nativeFiles': {},
               'cameraStartFrame': fixture.get('presentation', {}).get('cameraStartFrame'),
               'sourcePolicy': 'EXISTING_VERIFIED_NATIVE_INPUTS',
               'nativeRuntimeFixture': deepcopy(fixture_ref)}
    for key in NATIVE_KEYS:
        path = _engine_file(files[key])
        payload['nativeFiles'][key] = {'path': files[key], 'sha256': _sha(_safe_regular(path))}
    validate_native_binding(plan, payload)
    return payload


def validate_native_binding(plan, payload):
    """Check actual preserved bytes, camera FPS, geography and lock before READY."""
    if not isinstance(payload, dict) or payload.get('schema') != NATIVE_SCHEMA or payload.get('sourcePolicy') != 'EXISTING_VERIFIED_NATIVE_INPUTS':
        raise PreparationError('NATIVE_PAYLOAD_SCHEMA_REQUIRED')
    files = payload.get('nativeFiles')
    if not isinstance(files, dict) or set(files) != set(NATIVE_KEYS):
        raise PreparationError('EXACT_FIVE_NATIVE_FILES_REQUIRED')
    decoded = {}
    for key in NATIVE_KEYS:
        row = files[key]
        if not isinstance(row, dict) or not HASH.fullmatch(str(row.get('sha256', ''))):
            raise PreparationError('NATIVE_INPUT_HASH_REQUIRED')
        raw = _safe_regular(_engine_file(row.get('path')))
        if _sha(raw) != row['sha256']:
            raise PreparationError('NATIVE_INPUT_HASH_MISMATCH', key)
        decoded[key] = json.loads(raw)
    legacy = plan['legacyScenePlan']
    intent = legacy['camera_intent']
    native_scene, regional, camera, inputs = (decoded[key] for key in ('scene', 'regionalPlan', 'cameraPlan', 'inputManifest'))
    if native_scene.get('event_anchor') != intent.get('anchor'):
        raise PreparationError('NATIVE_EVENT_ANCHOR_MISMATCH')
    primary = intent.get('native_context', {}).get('primary_country_id')
    if not primary or native_scene.get('primary_region_id') != primary or regional.get('primary') != primary:
        raise PreparationError('NATIVE_COUNTRY_BINDING_MISMATCH')
    primary_geometry = native_scene.get('primary_geometry', {})
    supplied = [row['geometry'] for row in legacy.get('geometries', []) if row.get('id') == primary]
    if len(supplied) != 1 or supplied[0] != {'type': primary_geometry.get('geometry_type'), 'coordinates': primary_geometry.get('coordinates')}:
        raise PreparationError('NATIVE_PRIMARY_GEOMETRY_MISMATCH')
    canonical_output = [plan['resolution']['width'], plan['resolution']['height']]
    if native_scene.get('canonical_output') != canonical_output or camera.get('canonicalOutput') != canonical_output or inputs.get('output') != canonical_output:
        raise PreparationError('NATIVE_OUTPUT_RESOLUTION_MISMATCH')
    if camera.get('directorVersion') != 'CAMERA_DIRECTOR_V5' or camera.get('fps') != plan['fps'] or inputs.get('fps') != plan['fps']:
        raise PreparationError('NATIVE_CAMERA_FPS_MISMATCH')
    if camera.get('intent', {}).get('finalExtent') != regional.get('framing', {}).get('bounds'):
        raise PreparationError('NATIVE_FINAL_FRAMING_MISMATCH')
    start = payload.get('cameraStartFrame')
    locks = [row['startFrame'] for row in camera.get('timeline', []) if row.get('state') == 'LOCK']
    if type(start) is not int or start < 0 or len(locks) != 1 or start + legacy['timing']['camera_lock_frame'] < locks[0]:
        raise PreparationError('EVENT_BEFORE_NATIVE_CAMERA_LOCK')
    return {'status': 'VERIFIED', 'nativeFiles': len(decoded), 'cameraStartFrame': start,
            'nativeLockFrame': locks[0], 'eventStartFrame': legacy['timing']['event_start_frame'],
            'gpuExecuted': False, 'visualQualityStatus': 'NOT_EXECUTED'}


def _write_exclusive(path, body):
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as destination:
        destination.write(body)
        destination.flush()
        os.fsync(destination.fileno())


def prepare_topic(topic, output_file, *, catalog_path=DEFAULT_CATALOG, duration_seconds=None,
                  fps=30, resolution=None, aspect_ratio=None, max_scene_frames=None,
                  payload_file=None, node='node', image_digest=None):
    """Produce a bound ready-to-run contract; no hardware or paid execution."""
    if image_digest is not None and (not isinstance(image_digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image_digest)):
        raise PreparationError('INVALID_IMAGE_DIGEST')
    output_file = Path(output_file).absolute()
    if output_file.exists() or output_file.is_symlink():
        raise PreparationError('PLAN_OUTPUT_ALREADY_EXISTS')
    if not output_file.parent.is_dir() or output_file.parent.is_symlink():
        raise PreparationError('PLAN_OUTPUT_DIRECTORY_REQUIRED')
    plan = plan_topic(topic, duration_seconds=duration_seconds, fps=fps, resolution=resolution,
                      aspect_ratio=aspect_ratio, catalog_path=catalog_path,
                      max_scene_frames=max_scene_frames, node=node)
    payload = build_native_payload(plan, catalog_path=catalog_path)
    payload_file = Path(payload_file).absolute() if payload_file is not None else output_file.parent / 'NATIVE_PAYLOAD.json'
    payload_bytes = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    if payload_file.exists() or payload_file.is_symlink():
        if _safe_regular(payload_file) != payload_bytes:
            raise PreparationError('EXISTING_NATIVE_PAYLOAD_CONFLICT')
    else:
        _write_exclusive(payload_file, payload_bytes)
    payload_path = str(payload_file.relative_to(ENGINE)) if payload_file.is_relative_to(ENGINE) else str(payload_file)
    profile = {**plan['renderProfile'], 'status': 'READY', 'reason': 'Preserved native source/camera bindings verified; actual GPU validation remains required',
               'adapter': 'UNIVERSAL_AREA_ASTRA_V2', 'rendererCapability': 'POLYGON_STATE_TIMELINE',
               'nativePayload': {'path': payload_path, 'sha256': _sha(payload_bytes), 'validationStatus': 'VERIFIED'},
               'nativeBindingValidation': 'CPU_SOURCE_AND_CAMERA_BINDING_ONLY', 'hardwareValidation': 'NOT_EXECUTED',
               'imageBindingStatus': 'IMAGE_BINDING_REQUIRED' if image_digest is None else 'OPERATOR_CONFIGURED_IMMUTABLE_DIGEST'}
    if image_digest is not None:
        profile['imageDigest'] = image_digest
    plan['sourceManifest']['nativeRuntimeFixture'] = deepcopy(payload['nativeRuntimeFixture'])
    bound = bind_renderer(plan, profile)
    validate_plan(bound, require_renderable=True)
    _write_exclusive(output_file, (json.dumps(bound, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())
    return bound


def _reference_preparation():
    directory = HERE.parent / 'reference-visual-master-v2'
    manifest = json.loads(_safe_regular(directory / 'REFERENCE_FILES.json'))
    target = directory / 'prepare_ref2.py'
    if _sha(_safe_regular(target)) != manifest.get('files', {}).get('prepare_ref2.py'):
        raise PreparationError('PINNED_REFERENCE_PREPARATION_REQUIRED')
    spec = importlib.util.spec_from_file_location('_universal_original_reference_preparation', target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_overlay():
    import universal_files
    report = universal_files.verify_extension()
    if report.get('status') != 'PASS' or report.get('testOnly') is not False:
        raise PreparationError('STAGED_UNIVERSAL_SOURCE_VERIFICATION_REQUIRED')
    return report


def _verify_activation(activation_file, expected_sha):
    """Original complete profile/bundle/source hash checks, CPU assembly only."""
    raw = _safe_regular(Path(activation_file))
    if _sha(raw) != expected_sha:
        raise PreparationError('PREPARED_ACTIVATION_HASH_MISMATCH')
    script = "const p=JSON.parse(await new Response(process.stdin).text()); const m=await import(p.module); const v=await m.loadReferenceRuntimePlan(p.options); process.stdout.write(JSON.stringify({status:'PASS',activationSha256:v.activationSha256,profileId:v.profile.profileId,gpuExecuted:false}));"
    module = (HERE.parent / 'reference-visual-master-v2/ref2_runtime.mjs').as_uri()
    arguments = {'module': module, 'options': {'activationFile': str(activation_file), 'expectedActivationSha256': expected_sha}}
    try:
        result = subprocess.run(['node', '--input-type=module', '-e', script], input=canonical_json(arguments),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreparationError('PREPARED_ACTIVATION_CPU_VALIDATION_UNAVAILABLE', type(exc).__name__) from exc
    if result.returncode:
        raise PreparationError('PREPARED_ACTIVATION_CPU_VALIDATION_FAILED')
    report = json.loads(result.stdout)
    if report != {'status': 'PASS', 'activationSha256': expected_sha, 'profileId': 'REFERENCE_VISUAL_MASTER_V2_F', 'gpuExecuted': False}:
        raise PreparationError('PREPARED_ACTIVATION_PROFILE_MISMATCH')
    return report


def _snapshot_prepared(root):
    root = Path(root)
    result, total = {}, 0
    for directory, subdirectories, files in os.walk(root, followlinks=False):
        for name in subdirectories:
            if (Path(directory) / name).is_symlink():
                raise PreparationError('PREPARED_DIRECTORY_SYMLINK_FORBIDDEN')
        for name in files:
            path = Path(directory) / name
            raw = _safe_regular(path)
            total += len(raw)
            if total > MAX_PREPARED_BYTES:
                raise PreparationError('PREPARED_INPUT_BUDGET_EXCEEDED')
            result[str(path.relative_to(root))] = {'sha256': _sha(raw), 'bytes': len(raw)}
    if not result:
        raise PreparationError('PREPARED_INPUTS_MISSING')
    return result


def prepare_job_inputs(plan_dict, private_job_root):
    """Reuse a complete verified receipt; preserve incomplete attempts without reuse."""
    validate_plan(plan_dict, require_renderable=True)
    ref = plan_dict['renderProfile']['nativePayload']
    native_raw = _safe_regular(_payload_path(ref['path']))
    if _sha(native_raw) != ref['sha256']:
        raise PreparationError('PLAN_NATIVE_PAYLOAD_HASH_MISMATCH')
    validate_native_binding(plan_dict, json.loads(native_raw))
    overlay = _verify_overlay()
    binding = {'planSHA256': canonical_sha256(plan_dict), 'sourceManifestSHA256': canonical_sha256(plan_dict['sourceManifest']),
               'renderProfileSHA256': canonical_sha256(plan_dict['renderProfile']), 'overlayManifestSHA256': overlay['manifestSha256']}
    with PrivateTree(Path(private_job_root)) as job, job.child('runtime-inputs', create=True) as runtime, runtime.lock():
        existing = runtime.json('INPUTS.json', optional=True)
        if existing is not None:
            if existing.get('schema') != INPUT_SCHEMA or existing.get('binding') != binding:
                raise PreparationError('PREPARED_JOB_BINDING_MISMATCH')
            attempt_name = existing.get('attemptDirectory')
            if not isinstance(attempt_name, str) or not re.fullmatch(r'attempt-[0-9]{4}', attempt_name):
                raise PreparationError('PREPARED_ATTEMPT_PATH_INVALID')
            attempt_root = runtime.path / attempt_name
            if not isinstance(existing.get('activationFile'), str) or not Path(existing['activationFile']).is_absolute() or not Path(existing['activationFile']).is_relative_to(attempt_root):
                raise PreparationError('ACTIVATION_OUTSIDE_PRIVATE_JOB')
            if _snapshot_prepared(attempt_root) != existing.get('files'):
                raise PreparationError('PREPARED_INPUT_HASH_MISMATCH')
            _verify_activation(existing['activationFile'], existing['activationSha256'])
            return {'activationFile': existing['activationFile'], 'activationSha256': existing['activationSha256'],
                    'cacheHit': True, 'gpuExecuted': False}
        prior = runtime.json('PREPARATION.json', optional=True)
        if prior is not None and (not isinstance(prior, dict) or prior.get('binding') != binding):
            raise PreparationError('PREPARED_JOB_BINDING_MISMATCH')
        count = prior.get('attempts', 0) if isinstance(prior, dict) else 0
        if type(count) is not int or count < 0 or count >= 2:
            raise PreparationError('PREPARATION_RETRY_LIMIT_REACHED')
        number = count + 1
        state = {'schema': INPUT_SCHEMA, 'binding': binding, 'attempts': number, 'state': 'PREPARING'}
        runtime.write_json('PREPARATION.json', state, replace=prior is not None)
        attempt_name = f'attempt-{number:04d}'
        try:
            with runtime.child(attempt_name, create=True) as attempt:
                if list(attempt.path.iterdir()):
                    raise PreparationError('PREPARATION_ATTEMPT_ALREADY_HAS_DATA')
                prepared = _reference_preparation().prepare_activation(attempt.path, variant='F')
                activation_file = Path(prepared['activationFile'])
                if not activation_file.is_relative_to(attempt.path):
                    raise PreparationError('ACTIVATION_OUTSIDE_PRIVATE_JOB')
                _verify_activation(str(activation_file), prepared['activationSha256'])
                files = _snapshot_prepared(attempt.path)
                receipt = {'schema': INPUT_SCHEMA, 'binding': binding, 'attemptDirectory': attempt_name,
                           'activationFile': str(activation_file), 'activationSha256': prepared['activationSha256'],
                           'files': files, 'gpuExecuted': False}
                runtime.write_json('INPUTS.json', receipt)
                runtime.write_json('PREPARATION.json', {**state, 'state': 'COMPLETED'}, replace=True)
                return {'activationFile': str(activation_file), 'activationSha256': prepared['activationSha256'],
                        'cacheHit': False, 'gpuExecuted': False}
        except BaseException as error:
            code = getattr(error, 'code', None) or str(error)
            if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code):
                code = 'CPU_INPUT_PREPARATION_FAILED'
            runtime.write_json('PREPARATION.json', {**state, 'state': 'FAILED', 'errorCode': code}, replace=True)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topic')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--duration-seconds', type=float)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    parser.add_argument('--max-scene-frames', type=int)
    parser.add_argument('--image-digest', default=os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'))
    args = parser.parse_args(argv)
    try:
        plan = prepare_topic(args.topic, args.output, catalog_path=args.catalog, duration_seconds=args.duration_seconds,
                             fps=args.fps, max_scene_frames=args.max_scene_frames, image_digest=args.image_digest)
        print(json.dumps({'status': 'READY_FOR_IMAGE_BINDING' if not plan['renderProfile'].get('imageDigest') else 'READY_FOR_APPROVAL', 'frames': plan['totalFrames'],
                          'scenes': len(plan['scenes']), 'planSHA256': canonical_sha256(plan),
                          'gpuExecuted': False, 'externalAIConnected': False}, ensure_ascii=False))
        return 0
    except (ContractError, OSError, ValueError) as error:
        code = getattr(error, 'code', None) or 'VIDEO_PREPARATION_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'gpuExecuted': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
