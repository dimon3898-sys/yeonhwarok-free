"""Versioned close-view radiance treatment over the frozen v018 material.

No new texture, camera, lighting clock, night data, or geographic geometry is
created. Old plans keep their exact material/cache identity unless they opt in.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math

from . import visual_quality as parent

ROOT = parent.ROOT
VERSION = 'v019'
SOURCES = ('engine/event_quality.py', 'engine/event_quality_backend.py',
           'web/event_quality_adapter.js', 'web/render_event_quality_earth.html',
           'data/event_quality_v019.json', 'web/event_quality_v019.json')
PROFILE_URL = '/static/event_quality_v019.json'
NIGHT_PATH = 'cinematic-world-map/assets/v3/earth/earth-night-8k.jpg'
NIGHT_SHA256 = '9894e83a585a22c1c425e7ca4f987a9ba625bf08ecee45d3c9dcacae3c2ad5f7'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile():
    data = ROOT / 'data/event_quality_v019.json'
    served = ROOT / 'web/event_quality_v019.json'
    if data.read_bytes() != served.read_bytes():
        raise ValueError('EVENT_QUALITY_SERVED_PROFILE_MISMATCH')
    value = json.loads(data.read_text())
    if value.get('version') != VERSION or value.get('parent_version') != parent.VERSION:
        raise ValueError('EVENT_QUALITY_VERSION_INVALID')
    for key, low, high in (('day_input_scale', .4, 1),
                           ('ocean_specular_scale', .1, 1),
                           ('city_contribution_scale', .01, 1)):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not low <= item <= high:
            raise ValueError('EVENT_QUALITY_RESPONSE_INVALID')
    if value.get('city_mask') != 'existing_native_regional_land_mask':
        raise ValueError('EVENT_QUALITY_MASK_SOURCE_INVALID')
    start, full = value.get('daylight_start'), value.get('daylight_full')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, full)) or not 0 <= start <= .5 or not start + .001 <= full <= .5:
        raise ValueError('EVENT_QUALITY_DAYLIGHT_GATE_INVALID')
    if isinstance(value.get('additional_textures'), bool) or value.get('additional_textures') != 0:
        raise ValueError('EVENT_QUALITY_UNEXPECTED_TEXTURE')
    return value


def hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def _contract():
    _profile()
    source = ROOT.parent / NIGHT_PATH
    if _sha(source) != NIGHT_SHA256:
        raise ValueError('EVENT_QUALITY_NIGHT_SOURCE_CHANGED')
    # Validate the native cropped day/mask bytes; never reinterpret them as a
    # higher-resolution night map or derive elevation from RGB shaded relief.
    parent.asset_records()
    return dict(version=VERSION, profile_url=PROFILE_URL,
                profile_sha256=_sha(ROOT / 'web/event_quality_v019.json'),
                source_hashes=hashes(), parent_source_hashes=parent.hashes(),
                night_source=dict(path=NIGHT_PATH, sha256=NIGHT_SHA256,
                                  resolution=[8192, 4096], higher_resolution=False),
                additional_textures=0)


def apply_quality(plan):
    if not parent.validate_quality(plan)['passed']:
        raise ValueError('EVENT_QUALITY_V018_BASELINE_REQUIRED')
    value = deepcopy(plan)
    contract = _contract()
    for scene in value['scenes']:
        scene['event_quality'] = deepcopy(contract)
    value['metadata']['event_quality'] = dict(version=VERSION, source_hashes=contract['source_hashes'])
    install_validation()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('EVENT_QUALITY_PLAN_INVALID')
    return value


def validate_quality(plan):
    errors = []
    try:
        contract = _contract()
        if not parent.validate_quality(plan)['passed']:
            errors.append(dict(code='EVENT_QUALITY_V018_BASELINE_REQUIRED'))
        if plan.get('metadata', {}).get('event_quality') != dict(version=VERSION, source_hashes=contract['source_hashes']):
            errors.append(dict(code='EVENT_QUALITY_METADATA_MISMATCH'))
        for scene in plan.get('scenes', []):
            if scene.get('event_quality') != contract:
                errors.append(dict(code='EVENT_QUALITY_SOURCE_MISMATCH', scene_id=scene.get('scene_id')))
        if not plan.get('scenes'):
            errors.append(dict(code='EVENT_QUALITY_SCENES_REQUIRED'))
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'EVENT_QUALITY_DEPENDENCY_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION,
                parent_version=parent.VERSION, additional_textures=0,
                night_source=dict(path=NIGHT_PATH, sha256=NIGHT_SHA256,
                                  resolution=[8192, 4096], higher_resolution=False),
                physical_gpu='NOT_RUN')


def install_validation():
    from . import schema, gpu_preflight
    if getattr(schema.validate_plan, 'event_quality_wrapper', False):
        gpu_preflight.validate_plan = schema.validate_plan
        return
    parent.install_validation()
    original = schema.validate_plan
    def checked(plan):
        selected = plan.get('metadata', {}).get('event_quality') is not None or any('event_quality' in s for s in plan.get('scenes', []))
        if not selected:
            return original(plan)
        quality = validate_quality(plan)
        if not quality['passed']:
            return quality
        baseline = deepcopy(plan)
        baseline['metadata'].pop('event_quality', None)
        for scene in baseline['scenes']:
            scene.pop('event_quality', None)
        return {**original(baseline), 'event_quality': dict(passed=True, version=VERSION)}
    checked.event_quality_wrapper = True
    checked.visual_quality_wrapper = getattr(original, 'visual_quality_wrapper', False)
    checked.single_test_wrapper = getattr(original, 'single_test_wrapper', False)
    schema.validate_plan = checked
    gpu_preflight.validate_plan = checked


def renderer_version(scene):
    base = parent.renderer_version(scene)
    if not scene.get('event_quality'):
        return base
    digest = hashlib.sha256(b'EARTH_EVENT_QUALITY/v019' + bytes.fromhex(base))
    digest.update(json.dumps(scene['event_quality'], sort_keys=True, separators=(',', ':')).encode())
    return digest.hexdigest()


def project_renderer_version(plan):
    return hashlib.sha256(json.dumps({s['scene_id']: renderer_version(s) for s in plan['scenes']},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def record_source_report(directory, plan, assets=None, *, original=None):
    from .storage import atomic_json
    import os
    directory = Path(directory)
    report = (original or parent.record_source_report)(directory, plan, assets)
    quality = validate_quality(plan)
    if not quality['passed']:
        raise ValueError('EVENT_QUALITY_SOURCE_REPORT_INVALID')
    report['event_quality'] = quality
    report['renderer_version'] = project_renderer_version(plan)
    report['license_notice'] += ' v019 changes close-view radiance only; existing native regional day/mask and licensed 8K night data remain unchanged. No new city, texture, elevation, blur, or inferred urban detail is created.'
    atomic_json(directory / 'source_report.json', report)
    atomic_json(directory / 'event_quality_sources.json', quality, exclusive=True)
    with (directory / 'source_report.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## v019 close-view radiance\n\n' + report['license_notice'] + '\n')
        stream.write('\nRenderer SHA-256: `' + report['renderer_version'] + '`\n')
        stream.flush()
        os.fsync(stream.fileno())
    return report
