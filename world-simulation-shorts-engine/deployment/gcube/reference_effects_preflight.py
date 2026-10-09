"""v020 whole-parent and OFF/ON container admission without a GPU draw.

Reference SFX is unconfirmed: this version keeps the existing audio events.
The actual adapter and all 720 native camera poses are exercised, while physical
NVIDIA pixels, GPU timing/memory and perceived output quality remain NOT_RUN.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

from engine.assets import APP_ROOT
from deployment.gcube.event_quality_preflight import selected_environment

V019_FROZEN = {
    'engine/event_quality.py': 'ed3a64e59656327eeb8ad661ba3b94429d0a847d16b3b759c4f316a58e6bfb05',
    'engine/event_quality_backend.py': 'ed6698ce19bb09a5aebe254014c6acfa26953cf014965f9a2d72fae6325d058a',
    'web/event_quality_adapter.js': 'bab46f0ed430b275193fde8e9df9e216b16a23659005bb02903c318ddce029b2',
    'web/render_event_quality_earth.html': 'ea7b9834dd5a2ef348d6d6a58ed17605ebf407cab41cb658b0c611e9005fb56d',
    'data/event_quality_v019.json': '3def1eb34d8de4be8bd04cc86cdeb3198d3181dfdc786d073f1259e1a4d001fd',
    'web/event_quality_v019.json': '3def1eb34d8de4be8bd04cc86cdeb3198d3181dfdc786d073f1259e1a4d001fd',
    'tools/test_event_quality_v019.mjs': 'a4b947f0f2d5902dc852bad62d7f7fef1d592caa855f2e295d2429b3e5012cca',
    'deployment/gcube/event_quality_preflight.py': '01c46e05e3d89452d0b2fb37fafb0e6267415fe6a155c6c2cc68475f355ebcb6',
}
PARENT_CONTAINER_ASSET_IDENTITY = '34474924f3b21c9956b947813dc3a7b43ea120030f5def585c68324f8bba22f4'
PARENT_NATIVE_ASSET_IDENTITY = '61dc0d739e47604c46d1344edc0c45e4c45fa17d9989c122e1dc4d839d7c6bd4'
NEW_AUDITED_ASSETS = {
    'world-simulation-shorts-engine/web/reference_effects_adapter.js',
    'world-simulation-shorts-engine/web/render_reference_effects_earth.html',
}
REQUEST = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
               qa_mode=False, quality='HIGH', tts=False, subtitles=False,
               bgm=True, sfx=True)


def audit_parent_assets(require_container_assets):
    from deployment.gcube.asset_audit import audit_assets
    audit = audit_assets()
    assert audit['passed'], 'V020_CONTAINER_ASSET_MISSING'
    parent = [row for row in audit['assets'] if row['path'] not in NEW_AUDITED_ASSETS]
    added = [row for row in audit['assets'] if row['path'] in NEW_AUDITED_ASSETS]
    identities = sorted([dict(path=row['path'], size=row['size'], sha256=row['sha256'])
                         for row in parent], key=lambda row: row['path'])
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    expected = PARENT_CONTAINER_ASSET_IDENTITY if require_container_assets else PARENT_NATIVE_ASSET_IDENTITY
    expected_count = 77 if require_container_assets else 68
    assert len(parent) == expected_count and digest == expected, 'V020_INHERITED_ASSET_IDENTITY_CHANGED'
    assert {row['path'] for row in added} == NEW_AUDITED_ASSETS, 'V020_NEW_RENDER_ASSET_MISSING'
    frozen = []
    for name, expected_sha in V019_FROZEN.items():
        actual_sha = hashlib.sha256((APP_ROOT / name).read_bytes()).hexdigest()
        assert actual_sha == expected_sha, 'V020_V019_SOURCE_CHANGED:' + name
        frozen.append(dict(file=name, sha256=actual_sha, unchanged=True))
    return dict(passed=True, inherited_asset_count=len(parent), additional_asset_count=len(added),
                total_asset_count=len(audit['assets']), inherited_asset_identity_sha256=digest,
                required_container_assets=77, final_container_contract='PASS' if require_container_assets else 'NOT_RUN',
                preserved_v019=frozen, assets=audit['assets'])


def audit_served_sources():
    from deployment.mobile_server import InternalHandler
    server = ThreadingHTTPServer(('127.0.0.1', 0), InternalHandler)
    server.application = SimpleNamespace(store=None)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    records = []
    try:
        for name in ('reference_effects_v020.json', 'reference_effects_adapter.js', 'render_reference_effects_earth.html'):
            expected = (APP_ROOT / 'web' / name).read_bytes()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('GET', '/static/' + name)
            response = connection.getresponse()
            payload = response.read()
            connection.close()
            assert response.status == 200 and payload == expected, 'V020_STATIC_SERVING_FAILED:' + name
            records.append(dict(url='/static/' + name, status=response.status, identical=True,
                                sha256=hashlib.sha256(payload).hexdigest(), content_type=response.getheader('Content-Type')))
        assert (APP_ROOT / 'data/reference_effects_v020.json').read_bytes() == (APP_ROOT / 'web/reference_effects_v020.json').read_bytes(), 'V020_SERVED_PROFILE_MISMATCH'
        return dict(passed=True, assets=records, scope='Actual inherited static HTTP handler; no owner secret or render operation')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def without_effects(plan):
    plain = deepcopy(plan)
    plain.pop('gate', None)
    plain.get('metadata', {}).pop('reference_effects', None)
    for scene in plain.get('scenes', []):
        scene.pop('reference_effects', None)
    return plain


def pose_records(report):
    scenes = report['scenes']
    return [pose for scene in scenes for check in scene['checks']
            for pose in check.get('report', {}).get('pose_records', [])]


def audit_timeline(scene, rows, *, effects_on):
    """Expand exclusive-end segments and retain the exact authored audio onsets."""
    total = scene['frame_count']
    fps = float(scene.get('frame_grid', {}).get('fps', scene.get('fps', 30)))
    assert total == 720 and fps == 30, 'V020_TIMELINE_FRAME_GRID_CHANGED'
    cursor = 0
    camera_states, audio = [], []
    for row in rows:
        start, end = row['start_frame'], row['end_frame']
        assert type(start) is type(end) is int and start == cursor and start < end <= total, 'V020_TIMELINE_GAP_OR_OVERLAP'
        assert row['frame_count'] == end - start, 'V020_TIMELINE_FRAME_COUNT_INVALID'
        assert (row['start_seconds'], row['end_seconds'], row['duration_seconds']) == (start / fps, end / fps, (end - start) / fps), 'V020_TIMELINE_SECONDS_INVALID'
        assert row['visual_effect'] in {'NONE', 'MARKER_POP'} and row['text_effect'] in {'NONE', 'TEXT_CHARACTER_REVEAL'}, 'V020_UNOBSERVED_TIMELINE_PATTERN'
        assert not (row['visual_effect'] != 'NONE' and row['text_effect'] != 'NONE'), 'V020_SIMULTANEOUS_PRIMARY_EFFECTS'
        if not effects_on:
            assert row['visual_effect'] == row['text_effect'] == 'NONE' and row['story_events'] == ['NONE'], 'V020_OFF_EFFECT_TIMELINE_CHANGED'
        if 'ZOOM' in row['camera_state']:
            assert row['visual_effect'] == row['text_effect'] == 'NONE', 'V020_EFFECT_DURING_CAMERA_MOTION'
        if row['sfx'] != 'NONE':
            assert end == start + 1, 'V020_EXISTING_SFX_ONSET_BOUNDARY_INVALID'
            audio.append((start, row['sfx']))
        camera_states.extend([row['camera_state']] * (end - start))
        cursor = end
    assert cursor == total and len(camera_states) == total, 'V020_TIMELINE_INCOMPLETE'
    expected_audio = [(round(float(sound['time']) * fps), 'EXISTING_' + sound['kind'])
                      for sound in scene.get('sound_events', [])]
    assert audio == expected_audio == [(60, 'EXISTING_soft_pulse'), (180, 'EXISTING_low_impact')], 'V020_UNCONFIRMED_REFERENCE_SFX_CHANGED'
    assert any(row['visual_effect'] == row['text_effect'] == row['sfx'] == 'NONE' for row in rows), 'V020_NONE_COVERAGE_MISSING'
    return dict(passed=True, segments=len(rows), frames=total, gap=0, overlap=0,
                existing_sfx_onsets=audio, added_sfx=0, camera_states=camera_states)


def audit_selected_effects(baseline, folder):
    from engine.reference_effects import apply_effects, validate_effects, effect_timeline, hashes, _contract
    from engine.reference_effects_backend import reference_effects_command, ReferenceEffectsBackend
    from engine.qa_planner import generate_deployment_plan
    from deployment.gcube.framegrid_preflight import check
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    original = deepcopy(baseline)
    off = apply_effects(baseline, enabled=False)
    assert off == original and baseline == original, 'V020_OFF_PLAN_CHANGED'
    assert off is not baseline, 'V020_OFF_PLAN_NOT_COPIED'
    with selected_environment(WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='legacy'):
        default_off = generate_deployment_plan(deepcopy(REQUEST))
    assert default_off == off, 'V020_OFF_DEFAULT_NOT_V019'
    selected = apply_effects(baseline, enabled=True)
    assert baseline == original, 'V020_BASELINE_PLAN_MUTATED'
    validation = validate_effects(selected)
    assert validation['passed'], validation
    assert without_effects(selected) == without_effects(off), 'V020_NON_EFFECT_PLAN_FIELD_CHANGED'
    assert sum(scene['frame_count'] for scene in selected['scenes']) == 720, 'V020_FRAME_GRID_CHANGED'
    for old_scene, new_scene in zip(off['scenes'], selected['scenes']):
        assert old_scene.get('sound_events') == new_scene.get('sound_events'), 'V020_UNCONFIRMED_REFERENCE_SFX_CHANGED'
        assert old_scene['event_quality'] == new_scene['event_quality'], 'V020_V019_MATERIAL_PROFILE_CHANGED'
        assert old_scene['visual_quality'] == new_scene['visual_quality'], 'V020_V018_PROFILE_CHANGED'
    timelines = [effect_timeline(scene) for scene in selected['scenes']]
    off_timelines = [effect_timeline(scene) for scene in off['scenes']]
    timeline_qc = [audit_timeline(scene, rows, effects_on=True) for scene, rows in zip(selected['scenes'], timelines)]
    off_timeline_qc = [audit_timeline(scene, rows, effects_on=False) for scene, rows in zip(off['scenes'], off_timelines)]
    assert [row['camera_states'] for row in timeline_qc] == [row['camera_states'] for row in off_timeline_qc], 'V020_TIMELINE_CAMERA_STATES_CHANGED'
    candidate = folder / 'PLAN.json'
    candidate.write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    (folder / 'PLAN_OFF.json').write_text(json.dumps(off, ensure_ascii=False, indent=2))
    (folder / 'effect-timelines.json').write_text(json.dumps(dict(selected=timelines, off=off_timelines), ensure_ascii=False, indent=2))
    node = subprocess.run(['node', 'tools/test_reference_effects_v020.mjs', str(candidate)],
                          cwd=APP_ROOT, capture_output=True, text=True, check=True)
    adapter = json.loads(node.stdout)
    assert adapter['passed'] and adapter['frames'] == 720 and adapter['camera_trajectory'] == 'UNCHANGED', 'V020_ACTUAL_ADAPTER_CONTRACT_FAILED'
    assert all(adapter[key] == 'UNCHANGED' for key in ('material', 'wide', 'overlay_off', 'sfx')), 'V020_PARENT_RENDER_CONTRACT_CHANGED'
    assert adapter['additional_texture_uploads'] == 0 and adapter['receipt_coverage'], 'V020_ACTUAL_EFFECT_RECEIPTS_MISSING'
    assert adapter['GPU'] == 'NOT_RUN', 'V020_CPU_CONTRACT_MISREPORTED'
    native_off = check(off, folder / 'native-off')
    native_on = check(selected, folder / 'native-on')
    assert native_off['passed'] and native_on['passed'], dict(off=native_off, on=native_on)
    assert native_off['gpu_draw'] == native_on['gpu_draw'] == 'NOT_RUN'
    old_poses, new_poses = pose_records(native_off), pose_records(native_on)
    assert len(old_poses) == len(new_poses) == 720 and old_poses == new_poses, 'V020_CAMERA_POSES_CHANGED'
    sources = []
    for name, expected in hashes().items():
        path = APP_ROOT / name
        data = path.read_bytes()
        assert data and hashlib.sha256(data).hexdigest() == expected, 'V020_SELECTED_SOURCE_INVALID:' + name
        sources.append(dict(file=name, sha256=expected, non_zero=True))
    scene_path = folder / 'selected-scene.json'
    scene_path.write_text(json.dumps(selected['scenes'][0], ensure_ascii=False, indent=2))
    command = ['node', str(APP_ROOT / 'tools/render_production_scene.mjs'), '--scene-json', str(scene_path),
               '--url', 'http://127.0.0.1/static/render_production_earth.html']
    mapped = reference_effects_command(command)
    index = mapped.index('--url') + 1
    assert urlsplit(mapped[index]).path == '/static/render_reference_effects_earth.html', 'V020_RENDER_PAGE_NOT_SELECTED'
    stripped = list(mapped)
    stripped[index] = command[command.index('--url') + 1]
    assert stripped == command, 'V020_RENDER_COMMAND_OTHER_ARGS_CHANGED'
    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
        actual = ReferenceEffectsBackend().run(command, APP_ROOT, lambda event: None)
    assert actual == mapped, 'V020_EXISTING_GPU_TRANSPORT_NOT_REUSED'
    with selected_environment(WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='v020'):
        default_on = generate_deployment_plan(deepcopy(REQUEST))
    default_validation = validate_effects(default_on)
    assert default_validation['passed'] and default_on == selected, 'V020_DEFAULT_ON_PLAN_MISMATCH'
    report = dict(passed=True, validation=validation, default_validation=default_validation,
                  off_plan_exact_v019=True, unrelated_plan_fields_unchanged=True,
                  camera_pose_count=720, camera_trajectory='UNCHANGED', native_collect_all_off=native_off,
                  native_collect_all_on=native_on, adapter_contract=adapter, effect_timelines=timelines,
                  off_effect_timelines=off_timelines, timeline_qc=timeline_qc, off_timeline_qc=off_timeline_qc,
                  source_contract=_contract(), sources=sources,
                  reference_sfx='UNCONFIRMED; existing events preserved',
                  backend_page='/static/render_reference_effects_earth.html',
                  transport='unchanged CPULocalBackend/strict GPU worker', physical_gpu='NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def run(folder, *, require_container_assets=False):
    from deployment.gcube.event_quality_preflight import run as parent_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if require_container_assets:
        assert os.environ.get('WORLD_ENGINE_REFERENCE_EFFECTS_VERSION') == 'v020', 'V020_IMAGE_DEFAULT_MISSING'
    preserved = audit_parent_assets(require_container_assets)
    with selected_environment(WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='legacy', WORLD_ENGINE_EVENT_QUALITY_VERSION='v019',
                              WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018', WORLD_ENGINE_SECOND_EVENT_TEST='1',
                              WORLD_ENGINE_DIRECTION_VERSION='v013'):
        inherited = parent_run(folder / 'v019-baseline')
        assert inherited['passed'], 'V020_INHERITED_V019_CONTRACT_FAILED'
        baseline = json.loads((folder / 'v019-baseline/selected/PLAN.json').read_text())
        selected = audit_selected_effects(baseline, folder / 'selected')
    serving = audit_served_sources()
    report = dict(passed=True, inherited_v019=inherited, preserved_parent=preserved, selected_effects=selected,
                  served_sources=serving, frames=720, gap=0, overlap=0, camera_trajectory='UNCHANGED',
                  reference_sfx='UNCONFIRMED; existing 2s/6s accents preserved', physical_gpu='NOT_RUN',
                  output_quality='NOT_RUN',
                  scope=('Actual final-container resources' if require_container_assets else 'Actual native filesystem resources') + '; whole v019 parent, OFF/ON plans and native 720-frame camera/material/effects contracts; physical NVIDIA output NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('::notice title=Reference effects preflight::' + json.dumps({key:value for key,value in report.items()
          if key not in ('inherited_v019','preserved_parent','selected_effects')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    import sys
    run(sys.argv[1], require_container_assets='--container' in sys.argv[2:])
