"""Explicit v018 surface-detail opt-in; certified camera and old plans are intact.

Regional RGB shaded relief is reflectance detail, never invented elevation or
night emission. New bytes, profile and shader hashes live in the approved Scene
JSON and cache key. Existing plans do not opt in from a deployment variable.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v018'
SOURCES = ('engine/visual_quality.py', 'engine/visual_quality_backend.py',
           'web/visual_quality_adapter.js', 'web/render_visual_quality_earth.html',
           'data/visual_quality_v018.json', 'web/visual_quality_v018.json',
           'web/earth-detail/v018/manifest.json')
PROFILE_URL = '/static/visual_quality_v018.json'
MANIFEST = ROOT / 'web/earth-detail/v018/manifest.json'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _documents():
    profile = json.loads((ROOT / 'data/visual_quality_v018.json').read_text())
    manifest = json.loads(MANIFEST.read_text())
    if profile.get('version') != VERSION or manifest.get('version') != VERSION:
        raise ValueError('VISUAL_QUALITY_VERSION_INVALID')
    if (ROOT / 'data/visual_quality_v018.json').read_bytes() != (ROOT / 'web/visual_quality_v018.json').read_bytes():
        raise ValueError('VISUAL_QUALITY_SERVED_PROFILE_MISMATCH')
    detail = profile['regional_detail']
    if not (0 <= detail['max_blend'] <= .8 and 0 < detail['close_height'] < detail['wide_height']
            and detail['edge_feather_degrees'] > 0):
        raise ValueError('VISUAL_QUALITY_LOD_INVALID')
    surface = profile['surface']
    if not all(math.isfinite(surface[k]) and 0 < surface[k] <= 1 for k in
               ('close_exposure_scale', 'ocean_specular_scale', 'city_gain_scale')):
        raise ValueError('VISUAL_QUALITY_SURFACE_INVALID')
    if not (1 <= surface['city_power'] <= 2 and 1 <= surface['city_focus_limit'] <= 3):
        raise ValueError('VISUAL_QUALITY_CITY_RESPONSE_INVALID')
    return profile, manifest


def asset_records():
    """Verify deployed bytes, source grid and exact static URLs before Chromium."""
    from PIL import Image
    _, manifest = _documents()
    records = []
    for item in manifest['textures']:
        relative = item['file']
        path = (ROOT / relative).resolve()
        if not path.is_relative_to((ROOT / 'web/earth-detail/v018').resolve()):
            raise ValueError('VISUAL_QUALITY_ASSET_PATH_INVALID')
        if item['url'] != '/static/' + relative.removeprefix('web/'):
            raise ValueError('VISUAL_QUALITY_ASSET_URL_INVALID')
        if _sha(path) != item['sha256'] or path.stat().st_size <= 0:
            raise ValueError('VISUAL_QUALITY_ASSET_HASH_MISMATCH')
        with Image.open(path) as image:
            image.load()
            if image.format != 'PNG' or image.size != (item['width'], item['height']):
                raise ValueError('VISUAL_QUALITY_ASSET_RESOLUTION_INVALID')
            expected_mode = 'RGB' if item['role'] == 'regional_day_relief' else 'L'
            if image.mode != expected_mode:
                raise ValueError('VISUAL_QUALITY_ASSET_FORMAT_INVALID')
        west, south, east, north = item['bounds']
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError('VISUAL_QUALITY_GEOGRAPHIC_BOUNDS_INVALID')
        if item['role'] == 'regional_day_relief':
            # Exactly the existing 21600x10800 native source, no upsampling.
            if item['source_resolution'] != [21600, 10800] or abs(item['width'] / (east-west) - 60) > 1e-7 or abs(item['height'] / (north-south) - 60) > 1e-7:
                raise ValueError('VISUAL_QUALITY_SOURCE_GRID_INVALID')
        records.append(dict(item, exists=True, readable=True, non_zero=True, bytes=path.stat().st_size))
    if len(records) != 4 or len({r['region_id'] for r in records}) != 2:
        raise ValueError('VISUAL_QUALITY_REGIONS_INVALID')
    for region in {r['region_id'] for r in records}:
        pair = [r for r in records if r['region_id'] == region]
        if {r['role'] for r in pair} != {'regional_day_relief', 'regional_land_mask'} or pair[0]['bounds'] != pair[1]['bounds']:
            raise ValueError('VISUAL_QUALITY_REGION_PAIR_INVALID')
    return records


def hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def _contract():
    records = asset_records()
    return dict(version=VERSION, profile_url=PROFILE_URL,
                profile_sha256=_sha(ROOT / 'web/visual_quality_v018.json'),
                manifest_sha256=_sha(MANIFEST), source_hashes=hashes(),
                asset_hashes={r['file']: r['sha256'] for r in records})


def apply_quality(plan):
    from .second_event_camera import PRESET, validate_camera
    if plan.get('metadata', {}).get('camera_test_preset') != PRESET or not validate_camera(plan)['passed']:
        raise ValueError('VISUAL_QUALITY_CAMERA_BASELINE_REQUIRED')
    value = deepcopy(plan)
    contract = _contract()
    for scene in value['scenes']:
        scene['visual_quality'] = deepcopy(contract)
    value['metadata']['visual_quality'] = dict(version=VERSION, source_hashes=contract['source_hashes'])
    install_validation()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('VISUAL_QUALITY_PLAN_INVALID')
    return value


def validate_quality(plan):
    errors = []
    records = []
    try:
        contract = _contract()
        records = asset_records()
        if plan.get('metadata', {}).get('visual_quality') != dict(version=VERSION, source_hashes=contract['source_hashes']):
            errors.append(dict(code='VISUAL_QUALITY_METADATA_MISMATCH'))
        from .second_event_camera import PRESET, validate_camera
        if plan.get('metadata', {}).get('camera_test_preset') != PRESET or not validate_camera(plan)['passed']:
            errors.append(dict(code='VISUAL_QUALITY_CAMERA_BASELINE_REQUIRED'))
        for scene in plan.get('scenes', []):
            if scene.get('visual_quality') != contract:
                errors.append(dict(code='VISUAL_QUALITY_SOURCE_MISMATCH', scene_id=scene.get('scene_id')))
            for name in ('event1_camera', 'event2_camera'):
                camera = scene['second_event_camera'][name]
                if not any(r['role'] == 'regional_day_relief' and r['bounds'][0]+2 < camera['lon'] < r['bounds'][2]-2
                           and r['bounds'][1]+2 < camera['lat'] < r['bounds'][3]-2 for r in records):
                    errors.append(dict(code='VISUAL_QUALITY_REGION_NOT_COVERED'))
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'VISUAL_QUALITY_DEPENDENCY_INVALID'))
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION,
                assets=records, physical_gpu='NOT_RUN')


def install_validation():
    """Validate the additive field, then replay every original technical gate.

    Legacy input is sent to the original validator unchanged. No scene/camera,
    Origin, owner-code, GPU, pixel or retention gate is relaxed here.
    """
    from . import schema, gpu_preflight
    if getattr(schema.validate_plan, 'visual_quality_wrapper', False):
        gpu_preflight.validate_plan = schema.validate_plan
        return
    # The frozen camera admission clones a closure-free validator. Install it
    # first, including explicit saved QA requests when camera env flags are off.
    from .single_event_camera import install_validation as install_camera_validation
    install_camera_validation()
    original = schema.validate_plan
    def checked(plan):
        selected = plan.get('metadata', {}).get('visual_quality') is not None or any('visual_quality' in s for s in plan.get('scenes', []))
        if not selected:
            return original(plan)
        quality = validate_quality(plan)
        if not quality['passed']:
            return quality
        legacy = deepcopy(plan)
        legacy['metadata'].pop('visual_quality', None)
        for scene in legacy['scenes']:
            scene.pop('visual_quality', None)
        result = original(legacy)
        return {**result, 'visual_quality': dict(passed=True, version=VERSION)}
    checked.visual_quality_wrapper = True
    checked.single_test_wrapper = getattr(original, 'single_test_wrapper', False)
    schema.validate_plan = checked
    gpu_preflight.validate_plan = checked


def renderer_version(scene):
    from .assets import renderer_version as original
    base = original(scene)
    if not scene.get('visual_quality'):
        return base
    digest = hashlib.sha256(b'EARTH_VISUAL_QUALITY/v018' + bytes.fromhex(base))
    digest.update(json.dumps(scene['visual_quality'], sort_keys=True, separators=(',', ':')).encode())
    return digest.hexdigest()


def project_renderer_version(plan):
    return hashlib.sha256(json.dumps({s['scene_id']: renderer_version(s) for s in plan['scenes']},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def record_source_report(directory, plan, assets=None, *, original=None):
    """Augment only the new report made by this call, so retries read truthful data."""
    from .assets import write_source_report
    from .storage import atomic_json
    import os
    directory = Path(directory)
    result = (original or write_source_report)(directory, plan, assets)
    quality = validate_quality(plan)
    if not quality['passed']:
        raise ValueError('VISUAL_QUALITY_SOURCE_REPORT_INVALID')
    result['visual_quality'] = quality
    result['renderer_version'] = project_renderer_version(plan)
    result['license_notice'] += ' v018 regional land-cover/shaded-relief RGB and land masks use existing Natural Earth public-domain raster and 1:50m vector data; original global CC BY 4.0 textures remain included. No new elevation or night-emission detail is claimed.'
    atomic_json(directory / 'source_report.json', result)
    atomic_json(directory / 'visual_quality_sources.json', quality, exclusive=True)
    with (directory / 'source_report.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## v018 regional material detail\n\n' + result['license_notice'] + '\n')
        stream.write('\nRenderer SHA-256: `' + result['renderer_version'] + '`\n')
        for asset in quality['assets']:
            stream.write('\n- ' + asset['file'] + ': `' + asset['sha256'] + '`\n')
        stream.flush()
        os.fsync(stream.fileno())
    return result
