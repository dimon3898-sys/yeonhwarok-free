"""v019 final-container admission, without any browser or GPU draw.

The inherited v018 audit runs first with only v019 selection disabled. The
new contract must then retain every approved camera/event/asset byte and
exercise the current 720-frame plan, real static HTTP handler and GPU worker
command selection. CPU-only planning is never reported as rendered quality.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from contextlib import contextmanager
from engine.assets import APP_ROOT

V018_FROZEN = {
    "engine/visual_quality.py": "171abfc112f510acf3b4b92e3ee2aeca4898e3a5b2142dec0ea275c5ca1caf0b",
    "engine/visual_quality_backend.py": "e2f269a3fb32cf007f8688f8966ec87231110aaaaecf90fb7f90accf21e19fd5",
    "web/visual_quality_adapter.js": "c86494cc4f300e83c8633b7788b501400589abade2ec7f8a000e67f9d640da10",
    "web/render_visual_quality_earth.html": "6e67c5a1a1f0b4ac6796da6e3cef890b540a4629d6ed07ad67a1d331ebf7f69e",
    "data/visual_quality_v018.json": "5e504ecb58db272387d8606455dd5b6d9e09d7f2270143c487817eeab709f822",
    "web/visual_quality_v018.json": "5e504ecb58db272387d8606455dd5b6d9e09d7f2270143c487817eeab709f822",
    "tools/test_visual_quality_v018.mjs": "6861b60e818ea4dbfd46a451bd5d9967887e1fe6a524c18c04cc4dc29abe2e5e",
    "tools/build_visual_quality_assets.py": "7daf0da934b78baf6d52e885ec1fa5543d206ec7e1fd939b825e0be436476eb9",
    "deployment/gcube/visual_quality_preflight.py": "6447df7512cbf55e68dc055a40f1c13f4ca416b60f02a489cd9e2cdd5760372b",
    "web/earth-detail/v018/LICENSE.txt": "ac0e1aa5b7a0cddaf5e634f168129c42883f51d8a48df2fd1f7bcc469d2e2320",
    "web/earth-detail/v018/detail_0.png": "24771c49e24a939f4dfbaf1ed85ba2283b92b5f0ddc7f00d91fe36ad48bd9a13",
    "web/earth-detail/v018/detail_0_land.png": "70abef962eea585520540f5a573523845f0f968877038bc8013e93149ecd4c13",
    "web/earth-detail/v018/detail_1.png": "673b8249fef4acb228cabd566895fd761ed1ab23b53afc08cee96b4ba1ff222f",
    "web/earth-detail/v018/detail_1_land.png": "bdcbc8170861054801856c36b334be1326ab51d24fdd98a149857dfeb94be83c",
    "web/earth-detail/v018/manifest.json": "4ad2b6ec9a1a5c3d0803bbec33648eb1fe474757fdcc1b279459201113f630c6"
}


@contextmanager
def selected_environment(**values):
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def audit_v018_unchanged():
    records = []
    for name, expected in V018_FROZEN.items():
        path = APP_ROOT / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        records.append(dict(file=name, expected_sha256=expected, actual_sha256=actual,
                            unchanged=actual == expected))
    actual_files = {str(path.relative_to(APP_ROOT)) for path in (APP_ROOT / 'web/earth-detail/v018').iterdir() if path.is_file()}
    expected_files = {name for name in V018_FROZEN if name.startswith('web/earth-detail/v018/')}
    assert actual_files == expected_files, 'V019_REGIONAL_TEXTURE_SET_CHANGED'
    assert all(record['unchanged'] for record in records), 'V019_V018_SOURCE_CHANGED'
    return dict(passed=True, sources=records, regional_textures='unchanged original 4 PNGs',
                additional_texture_count=0, additional_texture_bytes=0)


def audit_served_profile():
    """Fetch exact new bytes through the unchanged read-only internal handler."""
    import http.client
    import threading
    from http.server import ThreadingHTTPServer
    from types import SimpleNamespace
    from deployment.mobile_server import InternalHandler
    server = ThreadingHTTPServer(('127.0.0.1', 0), InternalHandler)
    server.application = SimpleNamespace(store=None)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    records = []
    try:
        for name in ('event_quality_v019.json', 'event_quality_adapter.js', 'render_event_quality_earth.html'):
            expected = (APP_ROOT / 'web' / name).read_bytes()
            url = '/static/' + name
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('GET', url)
            response = connection.getresponse()
            payload = response.read()
            connection.close()
            assert response.status == 200 and payload == expected, 'V019_STATIC_SERVING_FAILED'
            records.append(dict(url=url, status=response.status, identical=True,
                                sha256=hashlib.sha256(payload).hexdigest(),
                                content_type=response.getheader('Content-Type')))
        return dict(passed=True, assets=records, scope='Actual unchanged HTTP handler; no owner secret or render operation')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def audit_selected_quality(baseline, folder):
    """Require the new planner to add only the explicit material response."""
    import subprocess
    from urllib.parse import urlsplit
    from unittest.mock import patch
    from engine.event_quality import VERSION, SOURCES, apply_quality, validate_quality
    from engine.event_quality_backend import event_quality_command, EventQualityBackend
    from engine.qa_planner import generate_deployment_plan
    from deployment.gcube.framegrid_preflight import check
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    original = deepcopy(baseline)
    selected = apply_quality(deepcopy(original))
    validation = validate_quality(selected)
    assert validation['passed'], validation
    assert baseline == original, 'V019_BASELINE_PLAN_MUTATED'
    plain = deepcopy(selected)
    plain['metadata'].pop('event_quality')
    plain.pop('gate', None)
    expected = deepcopy(original)
    expected.pop('gate', None)
    for scene in plain['scenes']:
        scene.pop('event_quality')
    assert plain == expected, 'V019_NON_MATERIAL_PLAN_FIELD_CHANGED'
    assert all(scene['visual_quality']['version'] == 'v018' and scene['event_quality']['version'] == VERSION
               for scene in selected['scenes']), 'V019_REGIONAL_PROFILE_NOT_PRESERVED'
    candidate = folder / 'PLAN.json'
    candidate.write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    node = subprocess.run(['node', 'tools/test_event_quality_v019.mjs', str(candidate)],
                          cwd=APP_ROOT, capture_output=True, text=True, check=True)
    material = json.loads(node.stdout)
    assert material['passed'] and material['frames'] == 720 and material['camera_trajectory'] == 'UNCHANGED', 'V019_MATERIAL_CAMERA_CONTRACT_FAILED'
    assert material['wide_response'] == 'UNCHANGED', 'V019_WIDE_MATERIAL_CHANGED'
    assert material['additional_texture_uploads'] == 0, 'V019_UNEXPECTED_TEXTURE_UPLOAD'
    native = check(selected, folder / 'collect-all')
    assert native['passed'] and native['gpu_draw'] == 'NOT_RUN', native
    poses = native['scenes'][0]['checks'][1]['report']['pose_records']
    assert len(poses) == 720, 'V019_CAMERA_FRAME_COUNT_CHANGED'
    assert sum(scene['frame_count'] for scene in selected['scenes']) == 720, 'V019_FRAME_GRID_CHANGED'
    scene_path = folder / 'selected-scene.json'
    scene_path.write_text(json.dumps(selected['scenes'][0], ensure_ascii=False, indent=2))
    command = ['node', str(APP_ROOT / 'tools/render_production_scene.mjs'), '--scene-json', str(scene_path),
               '--url', 'http://127.0.0.1/static/render_production_earth.html']
    transformed = event_quality_command(command)
    index = transformed.index('--url') + 1
    assert urlsplit(transformed[index]).path == '/static/render_event_quality_earth.html', 'V019_RENDER_PAGE_NOT_SELECTED'
    stripped = list(transformed)
    stripped[index] = command[command.index('--url') + 1]
    assert stripped == command, 'V019_RENDER_COMMAND_OTHER_ARGS_CHANGED'
    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
        actual = EventQualityBackend().run(command, APP_ROOT, lambda event: None)
    assert actual == transformed, 'V019_EXISTING_GPU_TRANSPORT_NOT_REUSED'
    default = generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                                          qa_mode=False, quality='HIGH', tts=False, subtitles=False,
                                          bgm=True, sfx=True))
    default_validation = validate_quality(default)
    assert default_validation['passed'], default_validation
    assert default == selected, 'V019_DEFAULT_REQUEST_PLAN_MISMATCH'
    sources = []
    for name in SOURCES:
        path = APP_ROOT / name
        assert path.is_file() and path.stat().st_size > 0, 'V019_SELECTED_SOURCE_MISSING'
        sources.append(dict(file=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), non_zero=True))
    report = dict(passed=True, validation=validation, default_validation=default_validation,
                  material_contract=material, native_collect_all=native, sources=sources,
                  explicit_profile=selected['scenes'][0]['event_quality'],
                  camera_and_event_fields_unchanged=True,
                  regional_detail='v018 original assets, blend, profile and filtering unchanged',
                  backend_page='/static/render_event_quality_earth.html',
                  transport='unchanged CPULocalBackend/strict GPU worker', physical_gpu='NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def run(folder):
    from deployment.gcube.visual_quality_preflight import run as visual_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    preserved = audit_v018_unchanged()
    with selected_environment(WORLD_ENGINE_EVENT_QUALITY_VERSION='legacy', WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                              WORLD_ENGINE_SECOND_EVENT_TEST='1', WORLD_ENGINE_DIRECTION_VERSION='v013'):
        inherited = visual_run(folder / 'v018-baseline')
    assert inherited['passed'], 'V019_INHERITED_V018_CONTRACT_FAILED'
    baseline = json.loads((folder / 'v018-baseline/quality/PLAN.json').read_text())
    with selected_environment(WORLD_ENGINE_EVENT_QUALITY_VERSION='v019', WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                              WORLD_ENGINE_SECOND_EVENT_TEST='1', WORLD_ENGINE_DIRECTION_VERSION='v013'):
        selected = audit_selected_quality(baseline, folder / 'selected')
    serving = audit_served_profile()
    report = dict(passed=True, inherited_v018=inherited, preserved_v018=preserved,
                  selected_quality=selected, served_profile=serving,
                  frames=720, gap=0, overlap=0, camera_trajectory='UNCHANGED',
                  wide_response='unchanged v018 outside close material weight',
                  additional_textures=0, physical_gpu='NOT_RUN', output_quality='NOT_RUN',
                  scope='Actual final-container files, unchanged native 720-frame camera and collect-all geometry; NVIDIA shader draw/visual output NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('::notice title=EVENT VIEW quality preflight::' + json.dumps({key: value for key, value in report.items()
          if key not in ('inherited_v018', 'preserved_v018', 'selected_quality')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
