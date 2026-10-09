"""Whole immutable v020 admission and authored v021 story contracts, without GPU.

The two new render resources are verified separately before an exact inherited
asset view is passed to the unchanged parent preflight. No old assets, sources,
test assertions or selectors are rewritten to accommodate the new layer.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from engine.assets import APP_ROOT
from deployment.gcube.event_quality_preflight import selected_environment
from deployment.gcube.reference_effects_preflight import REQUEST, pose_records

V020_FROZEN = {
    'engine/reference_effects.py': '0df0d207772493269f748575dfd618d52d9dd0b8a886bd05d1712fe1d7214a87',
    'engine/reference_effects_backend.py': '9d260626b0fc96d85fd6eac5d651391b370afd5be5c6a9a761a44dd39a202eae',
    'web/reference_effects_adapter.js': 'cd52f405cac6e8707a1c7dc6aca46735ff32d0d2bfbb44215ccebbb0785d43e1',
    'web/render_reference_effects_earth.html': '31863216d72fb76c139cf49f01c99b23047e1cb9af2a2e7359b47b2f29c30e0a',
    'data/reference_effects_v020.json': '2df0563abca82d8f0c71311d4eeb66feb9769e810504fc9d9b2bbe26d06e168f',
    'web/reference_effects_v020.json': '2df0563abca82d8f0c71311d4eeb66feb9769e810504fc9d9b2bbe26d06e168f',
    'tools/test_reference_effects_v020.mjs': '2d9b33b367ead8a58a6c19de709ab5c63bd9880f695d62417b40d856badab814',
    'deployment/gcube/reference_effects_preflight.py': '4d30f259f149c88929a49f3757605bbd114afedd0a5e1111d7e1336a3016d30b',
    'deployment/gcube/asset_audit.py': 'bb0e291456eefa8867714dc7441884ceaf08d14270efe3ead9b3969e4adcda35',
}
NEW_AUDITED_ASSETS = {
    'world-simulation-shorts-engine/web/story_progression_adapter.js',
    'world-simulation-shorts-engine/web/render_story_progression_earth.html',
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def inherited_asset_view(audit):
    """Keep the parent's fixed inventory, after the complete inventory is audited."""
    parent = {**audit, 'assets': [row for row in audit['assets']
                               if row['path'] not in NEW_AUDITED_ASSETS]}
    with patch('deployment.gcube.asset_audit.audit_assets', lambda: deepcopy(parent)):
        yield


def audit_parent_assets(require_container_assets):
    from deployment.gcube.asset_audit import audit_assets
    from deployment.gcube.reference_effects_preflight import audit_parent_assets as parent_audit
    audit = audit_assets()
    assert audit['passed'], 'V021_CONTAINER_ASSET_MISSING'
    added = [row for row in audit['assets'] if row['path'] in NEW_AUDITED_ASSETS]
    assert {row['path'] for row in added} == NEW_AUDITED_ASSETS, 'V021_NEW_RENDER_ASSET_MISSING'
    expected = 81 if require_container_assets else 72
    assert len(audit['assets']) == expected, 'V021_FINAL_ASSET_INVENTORY_CHANGED'
    frozen = []
    for name, expected_sha in V020_FROZEN.items():
        actual = _sha(APP_ROOT / name)
        assert actual == expected_sha, 'V021_V020_SOURCE_CHANGED:' + name
        frozen.append(dict(file=name, sha256=actual, unchanged=True))
    with inherited_asset_view(audit):
        inherited = parent_audit(require_container_assets)
    assert inherited['total_asset_count'] == expected - 2, 'V021_PARENT_ASSET_INVENTORY_CHANGED'
    canonical = sorted([dict(path=row['path'], size=row['size'], sha256=row['sha256'])
                        for row in audit['assets'] if row['path'] not in NEW_AUDITED_ASSETS],
                       key=lambda row: row['path'])
    return dict(passed=True, inherited_asset_count=expected-2, additional_asset_count=2,
                total_asset_count=expected, inherited_asset_identity_sha256=hashlib.sha256(
                    json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                required_container_assets=81,
                final_container_contract='PASS' if require_container_assets else 'NOT_RUN',
                preserved_v020=frozen, inherited_v019_and_v020_assets=inherited,
                assets=audit['assets']), audit


def audit_served_sources():
    from deployment.mobile_server import InternalHandler
    server = ThreadingHTTPServer(('127.0.0.1', 0), InternalHandler)
    server.application = SimpleNamespace(store=None)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    records = []
    try:
        for name in ('story_progression_v021.json', 'story_progression_adapter.js',
                     'render_story_progression_earth.html'):
            expected = (APP_ROOT / 'web' / name).read_bytes()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('GET', '/static/' + name)
            response = connection.getresponse()
            payload = response.read()
            connection.close()
            assert response.status == 200 and payload == expected, 'V021_STATIC_SERVING_FAILED:' + name
            records.append(dict(url='/static/' + name, status=response.status, identical=True,
                                sha256=hashlib.sha256(payload).hexdigest(),
                                content_type=response.getheader('Content-Type')))
        assert (APP_ROOT / 'data/story_progression_v021.json').read_bytes() == (
            APP_ROOT / 'web/story_progression_v021.json').read_bytes(), 'V021_SERVED_PROFILE_MISMATCH'
        return dict(passed=True, assets=records,
                    scope='Actual inherited readonly HTTP handler; no owner secret or render request')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def without_progression(plan):
    plain = deepcopy(plan)
    plain.pop('gate', None)
    plain.get('metadata', {}).pop('story_progression', None)
    for scene in plain.get('scenes', []):
        scene.pop('story_progression', None)
    return plain


def audit_timeline(scene, rows, *, enabled):
    from engine.story_progression import PHASES
    camera = scene['second_event_camera']['timeline']
    expected_camera = [row['state'] for row in camera for _ in range(row['frame_count'])]
    cursor, states = 0, []
    for row in rows:
        start, end = row['start_frame'], row['end_frame']
        assert type(start) is type(end) is int and start == cursor and start < end <= 720, 'V021_TIMELINE_GAP_OR_OVERLAP'
        assert row['frame_count'] == end-start, 'V021_TIMELINE_FRAME_COUNT_INVALID'
        assert (row['start_seconds'], row['end_seconds']) == (
            start/30, end/30), 'V021_TIMELINE_SECONDS_INVALID'
        assert row['story_state'] in {*PHASES, 'NONE'}, 'V021_UNSUPPORTED_STORY_STATE'
        assert row['visual_effect'] in {'NONE', 'TEXT_REVEAL_HALO', 'LOCATION_TEXT_HALO'}, 'V021_UNSUPPORTED_EFFECT'
        assert row['added_sfx'] == 'NONE', 'V021_AUDIO_CHANGED'
        if not enabled:
            assert row['story_state'] == row['visual_effect'] == 'NONE', 'V021_OFF_TIMELINE_CHANGED'
        states.extend([row['camera_state']] * (end-start))
        cursor = end
    assert cursor == 720 and states == expected_camera, 'V021_TIMELINE_CAMERA_OR_COVERAGE_CHANGED'
    for beat in scene.get('story_progression', {}).get('microbeats', []):
        assert beat['geometry_ref'] is beat['semantic_segment_ref'] is None, 'V021_FAKE_GEOMETRY'
        lock = beat['camera_lock_ref']
        assert lock['start_frame'] <= beat['start_frame'] < beat['end_frame'] <= lock['end_frame'], 'V021_EFFECT_OUTSIDE_CAMERA_LOCK'
        if beat['pattern'] != 'NONE':
            assert beat['end_frame']-beat['start_frame'] <= 17, 'V021_CONTINUOUS_EFFECT'
    return dict(passed=True, segments=len(rows), frames=720, gap=0, overlap=0,
                camera_states=states, added_sfx=0, added_geometry=0)


def audit_selected_progression(baseline, inherited, folder):
    from engine.story_progression import (apply_progression, validate_progression,
        progression_timeline, progression_qc, hashes, _contract, renderer_version,
        project_renderer_version)
    from engine import reference_effects
    from engine.qa_planner import generate_deployment_plan
    from engine.story_progression_backend import story_progression_command, StoryProgressionBackend
    from deployment.gcube.framegrid_preflight import check
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    original = deepcopy(baseline)
    off = apply_progression(baseline, enabled=False)
    assert off == original and baseline == original and off is not baseline, 'V021_OFF_PLAN_CHANGED'
    assert project_renderer_version(off) == reference_effects.project_renderer_version(original), 'V021_OFF_RENDERER_CHANGED'
    for scene in off['scenes']:
        assert renderer_version(scene) == reference_effects.renderer_version(scene), 'V021_OFF_SCENE_RENDERER_CHANGED'
    with selected_environment(WORLD_ENGINE_STORY_PROGRESSION_VERSION='legacy'):
        default_off = generate_deployment_plan(deepcopy(REQUEST))
    assert default_off == off, 'V021_OFF_DEFAULT_NOT_V020'
    selected = apply_progression(baseline, enabled=True)
    validation = validate_progression(selected)
    assert validation['passed'] and baseline == original, 'V021_SELECTED_PLAN_INVALID'
    assert without_progression(selected) == without_progression(off), 'V021_UNRELATED_PLAN_FIELDS_CHANGED'
    assert sum(scene['frame_count'] for scene in selected['scenes']) == 720, 'V021_FRAME_GRID_CHANGED'
    for old, new in zip(off['scenes'], selected['scenes']):
        for name in ('sound_events', 'reference_effects', 'event_quality', 'visual_quality',
                     'second_event_camera', 'camera_start', 'camera_end', 'visual_events',
                     'labels', 'text_events', 'routes', 'entities'):
            assert old.get(name) == new.get(name), 'V021_INHERITED_SCENE_FIELD_CHANGED:' + name
        assert progression_qc(new)['passed'], 'V021_STORY_QC_FAILED'
        assert new['story_progression']['boundary']['status'] == 'NOT_AVAILABLE', 'V021_UNSOURCED_BOUNDARY_DRAW'
    timelines = [progression_timeline(scene) for scene in selected['scenes']]
    off_timelines = [progression_timeline(scene) for scene in off['scenes']]
    timeline_qc = [audit_timeline(s, rows, enabled=True) for s, rows in zip(selected['scenes'], timelines)]
    off_timeline_qc = [audit_timeline(s, rows, enabled=False) for s, rows in zip(off['scenes'], off_timelines)]
    candidate = folder/'PLAN.json'
    candidate.write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    (folder/'PLAN_OFF.json').write_text(json.dumps(off, ensure_ascii=False, indent=2))
    (folder/'story-timelines.json').write_text(json.dumps(dict(selected=timelines, off=off_timelines), ensure_ascii=False, indent=2))
    node = subprocess.run(['node', 'tools/test_story_progression_v021.mjs', str(candidate)],
                          cwd=APP_ROOT, capture_output=True, text=True, check=True)
    adapter = json.loads(node.stdout)
    assert adapter['passed'] and adapter['frames'] == 720 and adapter['checks'] == 33, 'V021_ACTUAL_ADAPTER_CONTRACT_FAILED'
    assert all(adapter[key] == 'UNCHANGED' for key in ('camera_trajectory', 'material', 'wide', 'overlay_off', 'audio')), 'V021_PARENT_RENDER_CONTRACT_CHANGED'
    assert adapter['source_scene_immutable'] and adapter['boundary_draw'] == 'NONE', 'V021_SOURCE_OR_GEOMETRY_CHANGED'
    assert adapter['additional_texture_uploads'] == adapter['added_sfx'] == 0, 'V021_NEW_TEXTURE_OR_AUDIO'
    expected_receipts = {beat['id']: beat['end_frame']-beat['start_frame']
                         for scene in selected['scenes'] for beat in scene['story_progression']['microbeats']}
    assert adapter['microbeat_receipt_coverage'] == expected_receipts, 'V021_RECEIPTS_INCOMPLETE'
    assert adapter['primary_effect_peak'] <= 1, 'V021_PRIMARY_PRIORITY_INVALID'
    assert adapter['request_order_regression']['completion_order_reversed'] is True, 'V021_ASYNC_RESOURCE_ORDER_NOT_EXERCISED'
    assert adapter['request_order_regression']['request_identity'] == 'SAME_URL_MULTISET_AND_COUNTS', 'V021_RESOURCE_INVENTORY_CHANGED'
    assert adapter['GPU'] == 'NOT_RUN', 'V021_CPU_CONTRACT_MISREPORTED'
    native_on = check(selected, folder/'native-on')
    native_off = inherited['selected_effects']['native_collect_all_on']
    old_poses, new_poses = pose_records(native_off), pose_records(native_on)
    assert native_on['passed'] and native_on['gpu_draw'] == 'NOT_RUN', 'V021_NATIVE_COLLECT_ALL_FAILED'
    assert len(old_poses) == len(new_poses) == 720 and old_poses == new_poses, 'V021_CAMERA_POSES_CHANGED'
    sources = []
    for name, expected in hashes().items():
        path = APP_ROOT/name
        assert path.is_file() and path.stat().st_size and _sha(path) == expected, 'V021_SELECTED_SOURCE_INVALID:' + name
        sources.append(dict(file=name, sha256=expected, non_zero=True))
    scene_path = folder/'selected-scene.json'
    scene_path.write_text(json.dumps(selected['scenes'][0], ensure_ascii=False, indent=2))
    command = ['node', str(APP_ROOT/'tools/render_production_scene.mjs'), '--scene-json', str(scene_path),
               '--url', 'http://127.0.0.1/static/render_production_earth.html']
    mapped = story_progression_command(command)
    index = mapped.index('--url')+1
    assert urlsplit(mapped[index]).path == '/static/render_story_progression_earth.html', 'V021_RENDER_PAGE_NOT_SELECTED'
    stripped = list(mapped)
    stripped[index] = command[command.index('--url')+1]
    assert stripped == command, 'V021_RENDER_COMMAND_OTHER_ARGS_CHANGED'
    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
        assert StoryProgressionBackend().run(command, APP_ROOT, lambda event: None) == mapped, 'V021_GPU_TRANSPORT_CHANGED'
    with selected_environment(WORLD_ENGINE_STORY_PROGRESSION_VERSION='v021'):
        default_on = generate_deployment_plan(deepcopy(REQUEST))
    assert validate_progression(default_on)['passed'] and default_on == selected, 'V021_DEFAULT_ON_PLAN_MISMATCH'
    report = dict(passed=True, validation=validation, off_plan_exact_v020=True,
                  unrelated_plan_fields_unchanged=True, camera_pose_count=720,
                  camera_trajectory='UNCHANGED', native_collect_all_on=native_on,
                  adapter_contract=adapter, story_timelines=timelines, off_story_timelines=off_timelines,
                  timeline_qc=timeline_qc, off_timeline_qc=off_timeline_qc,
                  source_contract=_contract(), sources=sources, boundary_draw='NONE',
                  audio='Exact v020 preserved; no new SFX or TTS',
                  backend_page='/static/render_story_progression_earth.html',
                  transport='unchanged CPULocalBackend/strict GPU worker', physical_gpu='NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def run(folder, *, require_container_assets=False):
    from deployment.gcube.reference_effects_preflight import run as parent_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if require_container_assets:
        assert os.environ.get('WORLD_ENGINE_STORY_PROGRESSION_VERSION') == 'v021', 'V021_IMAGE_DEFAULT_MISSING'
    preserved, full_audit = audit_parent_assets(require_container_assets)
    with selected_environment(WORLD_ENGINE_STORY_PROGRESSION_VERSION='legacy',
                              WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='v020',
                              WORLD_ENGINE_EVENT_QUALITY_VERSION='v019',
                              WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                              WORLD_ENGINE_SECOND_EVENT_TEST='1', WORLD_ENGINE_DIRECTION_VERSION='v013'):
        with inherited_asset_view(full_audit):
            inherited = parent_run(folder/'v020-baseline', require_container_assets=require_container_assets)
        assert inherited['passed'], 'V021_INHERITED_V020_CONTRACT_FAILED'
        baseline = json.loads((folder/'v020-baseline/selected/PLAN.json').read_text())
        selected = audit_selected_progression(baseline, inherited, folder/'selected')
    serving = audit_served_sources()
    report = dict(passed=True, inherited_v020=inherited, preserved_parent=preserved,
                  selected_progression=selected, served_sources=serving, frames=720, gap=0, overlap=0,
                  camera_trajectory='UNCHANGED', boundary_draw='NONE', added_sfx=0, added_textures=0,
                  physical_gpu='NOT_RUN', output_quality='NOT_RUN',
                  scope=('Actual final-container resources' if require_container_assets else 'Actual native filesystem resources')
                        + '; whole v020 parent, OFF/ON story plans and native 720-frame camera/material/effects contracts; physical NVIDIA output NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('::notice title=Story progression preflight::' + json.dumps(
        {key:value for key,value in report.items() if key not in ('inherited_v020','preserved_parent','selected_progression')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    import sys
    report = run(sys.argv[1] if len(sys.argv)>1 else '/data/story-progression-preflight',
                 require_container_assets='--container' in sys.argv)
    raise SystemExit(0 if report['passed'] else 1)
