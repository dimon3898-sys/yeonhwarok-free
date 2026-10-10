"""Versioned terrain-preserving styling of the admitted v023 native regions.

This child changes only the visual profile. Native GIS selection, event state,
camera/material snapshots and marker/text timing remain owned by the frozen
v022/v023 contracts. Legacy plans are never implicitly upgraded at render time.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

from . import bold_infographic as bold
from . import infographic_contract as parent

ROOT = parent.ROOT
VERSION = 'v024'
PROFILE_ID = 'VISUAL_TARGET_MAP_V024'
PROFILE_URL = '/static/infographic/v024/terrain_profile.json'
PROFILE_PATH = ROOT / 'data/infographic/v024/terrain_profile.json'
PUBLIC_PATH = ROOT / 'web/infographic/v024/terrain_profile.json'
SOURCES = ('engine/terrain_infographic.py', 'web/terrain_infographic_adapter.js',
           'web/render_terrain_infographic_earth.html',
           'data/infographic/v024/terrain_profile.json',
           'web/infographic/v024/terrain_profile.json')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _color(value):
    return isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) is not None


def profile():
    """Validate authored role tokens and a bounded, static native-country style."""
    if PROFILE_PATH.read_bytes() != PUBLIC_PATH.read_bytes():
        raise ValueError('TERRAIN_PROFILE_MIRROR_MISMATCH')
    value = json.loads(PROFILE_PATH.read_text())
    if (value.get('version') != VERSION or value.get('profile_id') != PROFILE_ID
            or value.get('parent_version') != bold.VERSION
            or value.get('role') != 'colorized_terrain_map_infographic'):
        raise ValueError('TERRAIN_PROFILE_VERSION_INVALID')
    geometry = value.get('geometry', {})
    if (geometry.get('preserve_holes') is not True
            or geometry.get('horizon_occlusion') is not True
            or geometry.get('boundary_draw') is not False
            or geometry.get('blend_mode') != 'color'
            or geometry.get('screen_space_reference_width') != 1080):
        raise ValueError('TERRAIN_GEOMETRY_POLICY_INVALID')
    primary, secondary = geometry['PRIMARY'], geometry['SECONDARY']
    if (not _number(primary['fill_alpha'], .72, .95)
            or not _number(secondary['fill_alpha'], .40, .80)
            or secondary['fill_alpha'] >= primary['fill_alpha']
            or not _number(primary['core_width_px'], 6, 12)
            or not _number(secondary['core_width_px'], 2, 5)
            or secondary['core_width_px'] >= primary['core_width_px']
            or primary['edge_alpha'] <= secondary['edge_alpha']):
        raise ValueError('TERRAIN_HIERARCHY_INVALID')
    for style in (primary, secondary):
        if (not all(_color(style[name]) for name in ('fill_color', 'core_color', 'edge_color', 'glow_color'))
                or not _number(style['edge_alpha'], 0, 1)
                or not _number(style['edge_width_px'], style['core_width_px'], 18)):
            raise ValueError('TERRAIN_STYLE_INVALID')
        if not _number(style['luminance_scale'], .80, 1):
            raise ValueError('TERRAIN_LOCAL_LUMINANCE_INVALID')
        rgb = [int(style['fill_color'][i:i+2], 16) for i in (1, 3, 5)]
        # Context remains a colored information role, never a neutral gray mask.
        if max(rgb) - min(rgb) < 24:
            raise ValueError('TERRAIN_ROLE_COLOR_INVALID')
    if (not _number(primary['glow_alpha'], 0, .25)
            or not _number(primary['glow_width_px'], 0, 12)
            or not _number(primary['glow_blur_px'], 0, 6)
            or (primary['glow_alpha'] > 0 and primary['glow_width_px'] == 0)
            or any(not _number(secondary[key], 0, 0)
                   for key in ('glow_alpha', 'glow_width_px', 'glow_blur_px'))):
        raise ValueError('TERRAIN_GLOW_POLICY_INVALID')
    if (value.get('marker_and_text') != 'TIMING_LAYOUT_V022_CONTRAST_V024'
            or value.get('glow_policy') != 'STATIC_PRIMARY_EDGE_ONLY'
            or value.get('semantic_roles') != {
                'PRIMARY': 'EVENT_GEOGRAPHY', 'SECONDARY': 'VERIFIED_GEOGRAPHIC_CONTEXT',
                'NEUTRAL': 'UNSELECTED_BASE_GEOGRAPHY'}):
        raise ValueError('TERRAIN_SEMANTIC_ROLE_INVALID')
    neutral = geometry.get('NEUTRAL', {})
    if any(not _number(neutral.get(key), expected, expected) for key, expected in (
            ('luminance_scale', 1), ('fill_alpha', 0), ('core_width_px', 0), ('glow_alpha', 0))):
        raise ValueError('TERRAIN_NEUTRAL_BASE_MUST_REMAIN_UNCHANGED')
    contrast = value.get('contrast', {})
    if (set(contrast) != {'scope', 'text_outline_px', 'text_outline_color', 'text_outline_alpha',
                         'text_shadow_color', 'text_shadow_alpha', 'text_shadow_px',
                         'marker_edge_px', 'marker_edge_color', 'marker_edge_alpha'}
            or contrast['scope'] != 'DRAW_ONLY_V022_TIMING_LAYOUT'
            or not _number(contrast['text_outline_px'], 2.5, 4)
            or not _number(contrast['marker_edge_px'], 3, 5.5)
            or not _number(contrast['text_outline_alpha'], 1, 1)
            or not _number(contrast['marker_edge_alpha'], 1, 1)
            or not _number(contrast['text_shadow_alpha'], .72, 1)
            or not _number(contrast['text_shadow_px'], 3, 3)
            or not all(_color(contrast[key]) for key in
                       ('text_outline_color', 'text_shadow_color', 'marker_edge_color'))):
        raise ValueError('TERRAIN_DRAW_ONLY_CONTRAST_INVALID')
    limits = value['limits']
    if (not _number(limits.get('primary_regions'), 1, 1)
            or not _number(limits.get('context_max_regions'), 6, 6)
            or any(not _number(limits.get(key), 0, 0)
                   for key in ('added_routes', 'added_entities', 'added_sfx'))):
        raise ValueError('TERRAIN_CONTENT_ADDITION_FORBIDDEN')
    return value


def source_hashes():
    return {name: _sha(ROOT / name) for name in SOURCES}


def compile_terrain_scene(scene):
    """Pin an existing native region selection without rebuilding or editing it."""
    profile()
    selected = scene['bold_infographic']
    return dict(version=VERSION, profile_id=PROFILE_ID, profile_url=PROFILE_URL,
        profile_sha256=_sha(PROFILE_PATH), registry_sha256=selected['registry_sha256'],
        source_hashes=source_hashes(), parent_bold_sha256=parent.canonical_sha(selected),
        parent_infographic_sha256=parent.canonical_sha(scene['infographic']),
        parent_camera_sha256=parent.canonical_sha(parent._camera_snapshot(scene)),
        parent_quality_sha256=parent.canonical_sha(parent._quality_snapshot(scene)),
        total_frames=selected['total_frames'], fps=selected['fps'])


def _metadata(plan):
    scenes = plan['scenes']
    return dict(version=VERSION, profile_id=PROFILE_ID, profile_url=PROFILE_URL,
        profile_sha256=_sha(PROFILE_PATH), registry_sha256=scenes[0]['bold_infographic']['registry_sha256'],
        source_hashes=source_hashes(),
        parent_bold_metadata_sha256=parent.canonical_sha(plan['metadata']['bold_infographic']),
        scene_contract_sha256={scene['scene_id']: parent.canonical_sha(scene['terrain_infographic'])
                               for scene in scenes})


def _report(errors):
    return dict(passed=not errors, errors=errors, warnings=[], version=VERSION,
                physical_gpu='NOT_RUN')


def _has_child(plan):
    if not isinstance(plan, dict):
        return False
    metadata = plan.get('metadata')
    return ((isinstance(metadata, dict) and 'terrain_infographic' in metadata)
            or any(isinstance(scene, dict) and 'terrain_infographic' in scene
                   for scene in plan.get('scenes', [])))


def _validate_child(plan):
    errors = []
    try:
        scenes = plan['scenes']
        if not scenes or not parent._strict(plan.get('metadata', {}).get('terrain_infographic'), _metadata(plan)):
            raise ValueError('TERRAIN_METADATA_MISMATCH')
        for scene in scenes:
            selected = scene.get('terrain_infographic')
            if not isinstance(selected, dict) or not parent._strict(selected, compile_terrain_scene(scene)):
                errors.append(dict(code='TERRAIN_SCENE_CONTRACT_MISMATCH', scene_id=scene['scene_id']))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'TERRAIN_PLAN_INVALID'))
    return _report(errors)


def validate_terrain_infographic(plan):
    # Native selection and the real Story/semantic/geometry proof are admitted
    # without stripping any proposed child fields. Only then check our pins.
    if not bold.validate_bold_infographic(plan)['passed']:
        return _report([dict(code='TERRAIN_V023_PLAN_INVALID')])
    return _validate_child(plan)


def validate_terrain_scene(scene):
    errors = []
    try:
        if not bold.validate_bold_scene(scene)['passed']:
            raise ValueError('TERRAIN_V023_SCENE_INVALID')
        selected = scene.get('terrain_infographic')
        if not isinstance(selected, dict) or not parent._strict(selected, compile_terrain_scene(scene)):
            raise ValueError('TERRAIN_SCENE_CONTRACT_MISMATCH')
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        errors.append(dict(code=str(error).split(':')[0] if isinstance(error, ValueError) else 'TERRAIN_SCENE_INVALID'))
    return _report(errors)


def _parent_plan_view(plan):
    # Used only AFTER native-parent admission AND the actual v024 source proof.
    # This removes our additive child, retaining the entire frozen v023 plan.
    value = deepcopy(plan)
    value['metadata'].pop('terrain_infographic', None)
    for scene in value['scenes']:
        scene.pop('terrain_infographic', None)
    return value


def prepare_terrain_infographic(plan, enabled=True):
    if type(enabled) is not bool:
        raise ValueError('TERRAIN_ENABLE_REQUIRES_BOOLEAN')
    if _has_child(plan):
        raise ValueError('TERRAIN_REQUIRES_UNMODIFIED_V023_BASELINE')
    if not enabled:
        return deepcopy(plan)
    if not bold.validate_bold_infographic(plan)['passed']:
        raise ValueError('TERRAIN_V023_BASELINE_REQUIRED')
    value = deepcopy(plan)
    for scene in value['scenes']:
        scene['terrain_infographic'] = compile_terrain_scene(scene)
    value['metadata']['terrain_infographic'] = _metadata(value)
    if not _validate_child(value)['passed']:
        raise ValueError('TERRAIN_PLAN_INVALID')
    install_runtime()
    from .schema import validate_plan
    value['gate'] = validate_plan(value)
    if not value['gate']['passed']:
        raise ValueError('TERRAIN_PLAN_INVALID')
    return value


def diagnostic_record(plan):
    return dict(version=VERSION, profile_id=PROFILE_ID, qc=validate_terrain_infographic(plan),
                profile=deepcopy(profile()),
                scenes=[dict(scene_id=scene['scene_id'], **deepcopy(scene['terrain_infographic']))
                        for scene in plan['scenes']], physical_gpu='NOT_RUN',
                quality_verdict='REQUIRES_ACTUAL_GPU_CAPTURE_AND_HUMAN_REVIEW',
                pixel_quality='CPU Canvas evidence and actual NVIDIA output are reported separately')


def install_runtime():
    """Fail-closed child admission; exact legacy mapping, cache and diagnostics."""
    from . import schema, gpu_preflight, infographic_backend, semantic_timeline
    bold.install_runtime()
    if not getattr(semantic_timeline.validate_production_plan, 'terrain_infographic_wrapper', False):
        original_production = semantic_timeline.validate_production_plan
        def measured(plan):
            if not _has_child(plan):
                return original_production(plan)
            report = validate_terrain_infographic(plan)
            if not report['passed']:
                return report
            technical = original_production(_parent_plan_view(plan))
            return {**technical, 'terrain_infographic': report} if technical['passed'] else technical
        measured.__dict__.update(original_production.__dict__)
        measured.terrain_infographic_wrapper = True
        semantic_timeline.validate_production_plan = measured
    if not getattr(schema.validate_plan, 'terrain_infographic_wrapper', False):
        original = schema.validate_plan
        def checked(plan):
            if not _has_child(plan):
                return original(plan)
            report = validate_terrain_infographic(plan)
            if not report['passed']:
                return report
            technical = original(_parent_plan_view(plan))
            return {**technical, 'terrain_infographic': report} if technical['passed'] else technical
        checked.__dict__.update(original.__dict__)
        checked.terrain_infographic_wrapper = True
        schema.validate_plan = checked
    gpu_preflight.validate_plan = schema.validate_plan
    if not getattr(infographic_backend.infographic_command, 'terrain_infographic_wrapper', False):
        original_command = infographic_backend.infographic_command
        def command(value):
            mapped = original_command(value)
            if '--scene-json' not in mapped:
                return mapped
            scene = json.loads(Path(mapped[mapped.index('--scene-json') + 1]).read_text())
            if 'terrain_infographic' not in scene:
                return mapped
            if not validate_terrain_scene(scene)['passed']:
                raise RuntimeError('TERRAIN_INFOGRAPHIC_SCENE_SOURCE_MISMATCH')
            index = mapped.index('--url') + 1
            url = urlsplit(mapped[index])
            if url.path != '/static/render_bold_infographic_earth.html':
                raise RuntimeError('TERRAIN_INFOGRAPHIC_PARENT_RENDER_PAGE_INVALID')
            mapped[index] = urlunsplit(url._replace(path='/static/render_terrain_infographic_earth.html'))
            return mapped
        command.__dict__.update(original_command.__dict__)
        command.terrain_infographic_wrapper = True
        infographic_backend.infographic_command = command
    if not getattr(parent.renderer_version, 'terrain_infographic_wrapper', False):
        original_version = parent.renderer_version
        def renderer_version(scene):
            baseline = original_version(scene)
            if 'terrain_infographic' not in scene:
                return baseline
            if not validate_terrain_scene(scene)['passed']:
                raise RuntimeError('TERRAIN_INFOGRAPHIC_CACHE_CONTRACT_INVALID')
            return hashlib.sha256(b'TERRAIN_INFOGRAPHIC/v024' + bytes.fromhex(baseline)
                + parent.canonical_json(scene['terrain_infographic'])).hexdigest()
        renderer_version.__dict__.update(original_version.__dict__)
        renderer_version.terrain_infographic_wrapper = True
        parent.renderer_version = renderer_version
    if not getattr(parent.diagnostic_record, 'terrain_infographic_wrapper', False):
        original_diagnostic = parent.diagnostic_record
        def recorded(plan):
            result = original_diagnostic(plan)
            if _has_child(plan):
                result['terrain_infographic'] = diagnostic_record(plan)
            return result
        recorded.__dict__.update(original_diagnostic.__dict__)
        recorded.terrain_infographic_wrapper = True
        parent.diagnostic_record = recorded
