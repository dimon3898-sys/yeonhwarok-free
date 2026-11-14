"""Pinned access to the unchanged Studio policy and common lease helpers."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parents[1]
REPO = HERE.parents[3]
PROFILE = 'GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1'
HISTORY_PROFILE = 'GCUBE_NVIDIA_CONTINUOUS_HISTORY_20S_V1'
WINDOW_PROFILE = 'GCUBE_NVIDIA_HISTORICAL_V2'
WINDOW_RUNTIME_PROFILE = 'HISTORICAL_AUTHORED_WINDOW_V2'
REQUEST = 'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1'
PLAN = 'WORLD_ENGINE_NVIDIA_PRESENTATION_PLAN_V1'
SHA = re.compile(r'[0-9a-f]{64}\Z')
DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(name, file):
    file = Path(file)
    if any(p.is_symlink() for p in (file, *file.parents)) or not file.is_file():
        raise RuntimeError('HANDOFF_SOURCE_PATH_UNSAFE')
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mvp():
    directory = RECOVERY / 'production-studio-mvp-v1'
    pins = json.loads((HERE / 'preserved_mvp_sources.json').read_bytes())['files']
    # Prefer the hash-pinned, copied source tree. Already imported frozen HTTPS
    # modules may originate from the original fixed alias, but only exact bytes
    # from that allowlisted location can be reused; no arbitrary sys.path module.
    for filename, pin in pins.items():
        file = directory / filename
        if any(p.is_symlink() for p in (file, *file.parents)) or sha(file.read_bytes()) != pin['sha256']:
            raise RuntimeError('HANDOFF_FROZEN_STUDIO_DEPENDENCY_CHANGED')
        cached = sys.modules.get(Path(filename).stem)
        if cached is not None:
            old = Path(getattr(cached, '__file__', ''))
            if (old not in {file, Path('/opt/world-engine-production-studio') / filename}
                    or any(p.is_symlink() for p in (old, *old.parents))
                    or sha(old.read_bytes()) != pin['sha256']):
                raise RuntimeError('HANDOFF_FROZEN_STUDIO_MODULE_ORIGIN_CHANGED')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    name = '_handoff_preserved_production_controller'
    return sys.modules.get(name) or load(name, directory / 'studio_controller.py')


def verify_manifest(file, expected, *, repo=REPO, require_external=False):
    file, repo = Path(file), Path(repo)
    if not SHA.fullmatch(str(expected)) or any(p.is_symlink() for p in (file, *file.parents)):
        raise RuntimeError('HANDOFF_SOURCE_MANIFEST_REQUIRED')
    raw = file.read_bytes()
    if len(raw) > 8 * 1024 ** 2 or sha(raw) != expected:
        raise RuntimeError('HANDOFF_SOURCE_MANIFEST_CHANGED')
    value = json.loads(raw)
    if value.get('schema') != 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1' or not value.get('files'):
        raise RuntimeError('HANDOFF_SOURCE_MANIFEST_SCHEMA')
    seen = set()
    for row in value['files']:
        relative = Path(row.get('path', ''))
        if (relative.is_absolute() or '..' in relative.parts or not relative.parts
                or relative.as_posix() in seen or not SHA.fullmatch(str(row.get('sha256')))):
            raise RuntimeError('HANDOFF_SOURCE_MANIFEST_PATH')
        seen.add(relative.as_posix())
        source = repo / relative
        if any(p.is_symlink() for p in (source, *source.parents)) or not source.is_file():
            raise RuntimeError('HANDOFF_REQUIRED_SOURCE_UNAVAILABLE')
        data = source.read_bytes()
        if sha(data) != row['sha256'] or len(data) != row['bytes']:
            raise RuntimeError('HANDOFF_REQUIRED_SOURCE_CHANGED')
    external = value.get('externalFiles', [])
    if require_external and not external:
        raise RuntimeError('HANDOFF_INSTALLED_PARENT_CONTRACT_REQUIRED')
    if require_external:
        checked = set()
        conditional = value.get('conditionalExternalFiles', [])
        if conditional and value.get('conditionalExternalPolicy') != 'VERIFY_EXACT_BYTES_IF_PRESENT_ELSE_ORIGINAL_PINNED_NEW_REPO_FALLBACK':
            raise RuntimeError('HANDOFF_INSTALLED_ALIAS_POLICY_REQUIRED')
        for row in [*external, *[r for r in conditional if Path(r.get('path', '')).exists() or Path(r.get('path', '')).is_symlink()]]:
            source = Path(row.get('path', ''))
            if (not source.is_absolute() or '..' in source.parts or not source.is_relative_to('/opt')
                    or str(source) in checked or not SHA.fullmatch(str(row.get('sha256')))
                    or any(p.is_symlink() for p in (source, *source.parents)) or not source.is_file()):
                raise RuntimeError('HANDOFF_INSTALLED_PARENT_UNAVAILABLE')
            checked.add(str(source))
            raw = source.read_bytes()
            if sha(raw) != row['sha256'] or len(raw) != row['bytes']:
                raise RuntimeError('HANDOFF_INSTALLED_PARENT_CHANGED')
    return {'sourceClosureSHA256': expected, 'verifiedFiles': len(seen),
            'externalParentContractVerified': require_external}


def window_history(plan):
    return (isinstance(plan, dict) and isinstance(plan.get('historicalAdmission'), dict)
            and plan['historicalAdmission'].get('scope') == WINDOW_RUNTIME_PROFILE)


def profile_for(plan):
    if window_history(plan):
        return WINDOW_PROFILE
    return HISTORY_PROFILE if isinstance(plan, dict) and plan.get('durationSeconds') == 20 else PROFILE


def duration_contract(plan):
    """Keep legacy defaults; the new 600 contract requires explicit history."""
    if (not isinstance(plan, dict) or type(plan.get('durationSeconds')) is not int
            or plan['durationSeconds'] not in {6, 10, 20}
            or type(plan.get('totalFrames')) is not int
            or plan['totalFrames'] != plan['durationSeconds'] * 30
            or type(plan.get('fps')) is not int or plan['fps'] != 30):
        raise RuntimeError('HANDOFF_EXACT_NONHISTORICAL_SIX_SECOND_PLAN_REQUIRED')
    if window_history(plan):
        admission = plan['historicalAdmission']
        if (plan.get('simulationType') != 'HISTORICAL'
                or plan.get('renderProfile', {}).get('profileId') != WINDOW_PROFILE
                or admission.get('schema') != 'WORLD_ENGINE_AUTHORED_HISTORY_ADMISSION_V2'
                or admission.get('status') != 'PASS' or admission.get('simulationType') != 'HISTORICAL'
                or admission.get('paidExecutionAllowed') is not False
                or not SHA.fullmatch(str(admission.get('runtimeSegmentSHA256')))
                or not SHA.fullmatch(str(admission.get('authoredInputSHA256')))):
            raise RuntimeError('HANDOFF_REVIEWED_HISTORY_WINDOW_REQUIRED')
    elif plan['durationSeconds'] == 20:
        admission = plan.get('historicalAdmission', {})
        if (plan.get('simulationType') != 'HISTORICAL'
                or plan.get('renderProfile', {}).get('profileId') != HISTORY_PROFILE
                or admission.get('schema') != 'WORLD_ENGINE_AUTHORED_HISTORY_ADMISSION_V1'
                or admission.get('status') != 'PASS' or admission.get('scope') != 'HISTORICAL_CONTINUOUS_600F_V1'
                or admission.get('simulationType') != 'HISTORICAL' or admission.get('paidExecutionAllowed') is not False):
            raise RuntimeError('HANDOFF_REVIEWED_CONTINUOUS_HISTORY_REQUIRED')
    return {'durationSeconds': plan['durationSeconds'], 'totalFrames': plan['totalFrames'], 'fps': 30}


def validate_plan(plan, *, image_digest, source_sha):
    timing = duration_contract(plan)
    frames = timing['totalFrames']
    if (not isinstance(plan, dict) or plan.get('schema') != PLAN
            or plan.get('resolution') != {'width': 1080, 'height': 1920}
            or plan.get('aspectRatio') != '9:16'
            or plan.get('audioSettings') != {'enabled': False, 'mode': 'SILENT'}
            or (plan.get('simulationType') != 'HISTORICAL' if timing['durationSeconds'] == 20 or window_history(plan)
                else plan.get('simulationType') not in {'GENERAL', 'FICTIONAL'})):
        raise RuntimeError('HANDOFF_EXACT_NONHISTORICAL_SIX_SECOND_PLAN_REQUIRED')
    profile = plan.get('renderProfile', {})
    if (profile != {'profileId': profile_for(plan), 'backend': 'vulkan', 'imageDigest': image_digest,
                    'sourceClosureSHA256': source_sha}
            or not DIGEST.fullmatch(str(image_digest)) or not SHA.fullmatch(str(source_sha))):
        raise RuntimeError('HANDOFF_PLAN_EXECUTION_BINDING_CHANGED')
    wire, runtime = plan.get('runtimeWireJSON'), plan.get('runtime')
    if (not isinstance(wire, str) or len(wire.encode()) > 8 * 1024 ** 2
            or sha(wire.encode()) != plan.get('runtimeWireSHA256')
            or not isinstance(runtime, dict) or json.loads(wire) != runtime or runtime.get('totalFrames') != frames
            or (timing['durationSeconds'] in {10, 20} and runtime.get('durationSeconds') != timing['durationSeconds'])
            or ('durationSeconds' in runtime and runtime['durationSeconds'] != timing['durationSeconds'])
            or not SHA.fullmatch(str(plan.get('sourceQualificationSHA256')))):
        raise RuntimeError('HANDOFF_RUNTIME_WIRE_BINDING_CHANGED')
    if timing['durationSeconds'] == 20 or window_history(plan):
        expected_profile = WINDOW_RUNTIME_PROFILE if window_history(plan) else 'HISTORICAL_CONTINUOUS_600F_V1'
        if (runtime.get('profile') != expected_profile
                or runtime.get('simulationType') != 'HISTORICAL'
                or runtime.get('historicalAdmission') != plan['historicalAdmission']
                or len(runtime.get('segments', [])) != 1
                or runtime['segments'][0].get('presentation', {}).get('territoryChanges', {}).get('profile') != 'HISTORICAL_CONTINUOUS_V1'):
            raise RuntimeError('HANDOFF_HISTORY_ADMISSION_BINDING_CHANGED')
    cursor = 0
    for segment in runtime.get('segments', []):
        scene = segment.get('scene', {})
        scene_frames_match = scene.get('timing', {}).get('total_frames') == segment.get('endFrame', -1) - cursor
        if window_history(plan):
            window = segment.get('timelineWindow', {})
            scene_frames_match = (set(window) == {'startFrame', 'endFrame'}
                and type(window.get('startFrame')) is int and type(window.get('endFrame')) is int
                and 0 <= window['startFrame'] < window['endFrame'] <= scene.get('timing', {}).get('total_frames', 0)
                and window['endFrame'] - window['startFrame'] == segment.get('endFrame', -1) - cursor
                and window == plan['historicalAdmission'].get('timeline', {}).get('window')
                and scene.get('timing', {}).get('total_frames') == plan['historicalAdmission'].get('timeline', {}).get('totalFrames'))
        elif 'timelineWindow' in segment:
            raise RuntimeError('HANDOFF_LEGACY_WINDOW_FORBIDDEN')
        if (segment.get('startFrame') != cursor or type(segment.get('endFrame')) is not int
                or segment['endFrame'] <= cursor or scene.get('timing', {}).get('fps') != 30
                or not scene_frames_match
                or scene.get('metadata', {}).get('output') != {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}):
            raise RuntimeError('HANDOFF_SCENE_FRAME_BINDING_CHANGED')
        cursor = segment['endFrame']
    if cursor != frames:
        raise RuntimeError('HANDOFF_SCENE_FRAME_COVERAGE_CHANGED')
    return True
