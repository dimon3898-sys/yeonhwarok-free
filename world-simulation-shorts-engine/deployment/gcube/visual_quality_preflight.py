"""Read-only v018 container contract; physical NVIDIA output remains NOT_RUN.

The frozen v017 camera/shader/transport hashes identify the exact approved
baseline. This audit never launches Chromium or admits CPU rendering.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from engine.assets import APP_ROOT, REPOSITORY_ROOT
from engine.backends import quality_settings

FROZEN_SOURCES = {
    "world-simulation-shorts-engine/web/single_event_camera.js": "483d0372c092b42c96beafbd2aabb3616eb7e7d6f8e9de4ad88cd06df59ff937",
    "world-simulation-shorts-engine/web/return_wide_camera.js": "13ac2b757e78e4d7416d0a48ca6f056b737e0b556a54522eb673f3417bf98c29",
    "world-simulation-shorts-engine/web/second_event_camera.js": "3f197ea2fc5004dad4ca8ea3a5419bc3b7606afdf74ab74282c1409fd59ba975",
    "world-simulation-shorts-engine/engine/single_event_camera.py": "b2ee7983599cdb386e937b9625a35bba1448e6a5aa62ab60d4ce337182b031eb",
    "world-simulation-shorts-engine/engine/return_wide_camera.py": "5a6dc56bceaa7c1a3f20108b0e55ec7fd454d0b9834539c7155a7fea0e45b584",
    "world-simulation-shorts-engine/engine/second_event_camera.py": "93bc4ce36e4cc6d2bb239602e986050c1a8caaa0bdd5302b966c36923419818b",
    "world-simulation-shorts-engine/engine/adaptive_wide.py": "d86c4ae9ea6a936bafb87e0366af52a992f593494b39652469de591df5b2920a",
    "world-simulation-shorts-engine/engine/second_event_qc.py": "f22c6569161c2681bd021a146e1cb24b795604e0fc9af91a378285bdf94202e0",
    "world-simulation-shorts-engine/engine/qc.py": "a05b4fbb1563644ae5b241f2610e16052f920d3060b91d8d51979d15b0237ab1",
    "world-simulation-shorts-engine/engine/retention.py": "003fa57bc28381183f06767a7770d172d3b1461a41d5f45bdcc8a49d27971e22",
    "world-simulation-shorts-engine/engine/backends.py": "779865d03abd2bcf87c12a9633de8e344367cdfd22690d6f20349d4904f12043",
    "world-simulation-shorts-engine/engine/gpu_bundle.py": "19ec3284fd8de32dd3d50e2f41f3fa199242d72a9b814ae07b7e3680aaeecb1c",
    "world-simulation-shorts-engine/engine/gpu_preflight.py": "5cb00a259bcd1ff071168cbb3214863a4b625a65ad4c14dc64860ce0843bef07",
    "world-simulation-shorts-engine/engine/frame_grid.py": "0b674358fc775e149406c9362de7671df808c498411cb44753c7def2a7f5ab1c",
    "world-simulation-shorts-engine/engine/audio_stability.py": "606c93410246a3605aacb267df237def9ded5c5963a9b3f723aabf259bbc01bd",
    "world-simulation-shorts-engine/engine/reference_master.py": "654bdc8204826cd10271361dce2acb02561abcc50926a4d69b35aa5a585b8a61",
    "world-simulation-shorts-engine/web/earth_adapter.js": "c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9",
    "world-simulation-shorts-engine/web/earth_polish_adapter.js": "667c8079db74356300a1f97c0fae9a0ac56553abf7e6160d9a7f090a7e953d5e",
    "world-simulation-shorts-engine/web/production_visual_adapter.js": "841eab94e44ed043cefd4c756315bc40564d49670ea18b4df8ef029371eacc51",
    "world-simulation-shorts-engine/web/reference_visual_adapter.js": "5061d5f30c1decd22055895dd927ff1cb9de5ea566029dd610ec3ea11593fe5a",
    "world-simulation-shorts-engine/web/app.js": "d6a25dd6c03594ac85b6bf64d3d2997ef38d83d084e97fe85bd16d02808f6050",
    "world-simulation-shorts-engine/deployment/gcube/start.py": "7db606d8783d84e493c182e8c064eb803b788b0335113cdbd8853994757a2123",
    "world-simulation-shorts-engine/deployment/gcube/proxy.py": "634679f2dc4b836c521d9d46d4cbaacacbe0c844ddd557d90afa5e6ca879f9d8",
    "world-simulation-shorts-engine/deployment/security.py": "3f7ea527f7209e4d3effc22b9a7b935db2e9642f135d064ff6c701c12131f704",
    "world-simulation-shorts-engine/tools/scene_diagnostic_journal.mjs": "7abbd6d8f89bf33c4f8b94c0e4309e5232dc3c5f6fa895b7bc06f55267664a7c",
    "world-simulation-shorts-engine/tools/scene_frame_contract.mjs": "59ceba07fb56b2ea3e5103a211f695ee1e695635869ddc9cbe0396892e5bf7bf",
    "world-simulation-shorts-engine/tools/render_production_stable_scene.mjs": "b8b699d1f4d59773d892f214232c32646848aaf07865674da70a0b9897897de1",
    "world-simulation-shorts-engine/deployment/gcube/asset_audit.py": "bb0e291456eefa8867714dc7441884ceaf08d14270efe3ead9b3969e4adcda35",
    "cinematic-world-map/src/renderer_v3.js": "b378269674833f9a79cbbbb2d9c24b004d5ca398063ca897ec1a5359eed0d6d3",
    "cinematic-world-map/src/engine_v3.js": "7e35b088d7de740d61c2e0c8765f0b941839b8896bc297e8765adf991f4f4aad",
    "cinematic-world-map/src/core_v1_preserved.js": "551a2816b29162621fd26b51620dd7c6671bbca7962bebcf152163d63eff8b9f",
    "cinematic-world-map/src/aircraft_v3.js": "fe23bb1b297f0fb16bbe492fcfc5245ab9461c9991195bbd6fe7a616ab12404b",
    "cinematic-world-map/assets/v3/earth/earth-day-8k.jpg": "88ab060b6e7d241cfc590c69f528fab2b3247b738d40124cb590999a6fe44abc",
    "cinematic-world-map/assets/v3/earth/earth-night-8k.jpg": "9894e83a585a22c1c425e7ca4f987a9ba625bf08ecee45d3c9dcacae3c2ad5f7",
    "cinematic-world-map/assets/v3/earth/earth-clouds-8k.jpg": "c792eca228989d36ebb45d3ea6ff1198be5e21a25d70d2fbcb2124ffd14ba7f5",
    "cinematic-world-map/assets/gis/earth-topology.png": "839b12da2e4dd346b256cebae72e10c479a102c8980a22084c41275e4b9a0e12"
}

SOURCE_DIMENSIONS = {
    'cinematic-world-map/assets/v3/earth/earth-day-8k.jpg': (8192, 4096),
    'cinematic-world-map/assets/v3/earth/earth-night-8k.jpg': (8192, 4096),
    'cinematic-world-map/assets/v3/earth/earth-clouds-8k.jpg': (8192, 4096),
    'cinematic-world-map/assets/gis/earth-topology.png': (2048, 1024),
}


def audit_frozen_sources():
    records = []
    for relative, expected in FROZEN_SOURCES.items():
        path = REPOSITORY_ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        records.append(dict(file=relative, expected_sha256=expected, actual_sha256=actual, unchanged=actual == expected))
    dimensions = []
    for relative, expected in SOURCE_DIMENSIONS.items():
        with Image.open(REPOSITORY_ROOT / relative) as source:
            dimensions.append(dict(file=relative, dimensions=list(source.size), expected=list(expected), unchanged=source.size == expected))
    return dict(passed=all(row['unchanged'] for row in records + dimensions), sources=records, dimensions=dimensions)


def audit_detail_sources():
    """Decode the exact deployed PNGs, and require their manifest hashes.

    Original sources are checked above. New local assets must additionally be
    present in their own immutable provenance manifest before publication.
    """
    directory = APP_ROOT / 'web/earth-detail/v018'
    manifest_path = directory / 'manifest.json'
    profile_path = APP_ROOT / 'data/visual_quality_v018.json'
    manifest = json.loads(manifest_path.read_text())
    profile = json.loads(profile_path.read_text())
    declared = {}

    def visit(value):
        if isinstance(value, dict):
            name = value.get('file', value.get('path'))
            digest = value.get('sha256')
            if isinstance(name, str) and name.lower().endswith('.png') and isinstance(digest, str):
                declared[Path(name).name] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(manifest)
    records = []
    files = sorted(directory.glob('*.png'))
    assert files, 'V018_DETAIL_TEXTURES_MISSING'
    assert set(declared) == {path.name for path in files}, 'V018_DETAIL_MANIFEST_FILES_MISMATCH'
    for path in files:
        descriptor = declared[path.name]
        data = path.read_bytes()
        assert data, 'V018_DETAIL_TEXTURE_EMPTY'
        digest = hashlib.sha256(data).hexdigest()
        assert digest == descriptor['sha256'], 'V018_DETAIL_TEXTURE_SHA_MISMATCH'
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            assert image.format == 'PNG' and width > 0 and height > 0, 'V018_DETAIL_TEXTURE_INVALID'
            expected = descriptor.get('resolution', descriptor.get('dimensions'))
            if expected is not None:
                assert list(expected) == [width, height], 'V018_DETAIL_TEXTURE_RESOLUTION_MISMATCH'
            if 'width' in descriptor:
                assert descriptor['width'] == width and descriptor['height'] == height, 'V018_DETAIL_TEXTURE_RESOLUTION_MISMATCH'
            records.append(dict(file=str(path.relative_to(APP_ROOT)), referenced=True, exists=True,
                                readable=True, non_zero=True, size=len(data), sha256=digest,
                                width=width, height=height, mode=image.mode, url=descriptor.get('url')))
    return dict(passed=True, assets=records, manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(), profile=profile,
                scope='Actual final-container decoded asset bytes and dimensions; GPU upload/render NOT_RUN')


def audit_served_detail(detail):
    """GET exactly the shipped texture URLs through the unchanged HTTP handler.

    The fixture has no user store, owner secret or render operation. This checks
    that a file audited in the container is also actually fetchable by Chromium.
    """
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
        for asset in detail['assets']:
            url = asset.get('url')
            assert isinstance(url, str) and url.startswith(('/static/', '/v3/assets/')) and url.endswith('.png'), 'V018_DETAIL_STATIC_URL_INVALID'
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('GET', url)
            response = connection.getresponse()
            payload = response.read()
            digest = hashlib.sha256(payload).hexdigest()
            record = dict(url=url, status=response.status, served_sha256=digest,
                          content_type=response.getheader('Content-Type'), identical=digest == asset['sha256'])
            connection.close()
            assert record['status'] == 200 and record['identical'], 'V018_DETAIL_STATIC_SERVING_FAILED'
            records.append(record)
        return dict(passed=True, assets=records, scope='Unchanged read-only HTTP handler; no auth/render request')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)


def audit_selected_quality(baseline_plan, folder):
    """Exercise explicit v018 planning and page selection without a GPU process."""
    import copy
    from urllib.parse import urlsplit
    from unittest.mock import patch
    from engine.visual_quality import apply_quality, validate_quality, SOURCES
    from engine.visual_quality_backend import quality_command, VisualQualityBackend
    from engine.qa_planner import generate_deployment_plan
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    original = copy.deepcopy(baseline_plan)
    selected = apply_quality(copy.deepcopy(original))
    assert isinstance(selected, dict), 'V018_SELECTED_PLAN_INVALID'
    validation = validate_quality(selected)
    assert validation['passed'], validation
    assert original == baseline_plan, 'V018_BASELINE_PLAN_MUTATED'
    assert len(selected['scenes']) == len(original['scenes']), 'V018_SCENES_CHANGED'
    protected = ('scene_id', 'start', 'end', 'duration', 'start_frame', 'end_frame', 'frame_count',
                 'camera', 'camera_preset', 'second_event_camera', 'single_event_camera',
                 'return_wide_camera', 'camera_path', 'camera_track', 'labels', 'visual_events',
                 'routes', 'entities', 'entity', 'sfx_events', 'lighting_preset')
    for previous, current in zip(original['scenes'], selected['scenes']):
        for name in protected:
            assert previous.get(name) == current.get(name), 'V018_PROTECTED_PLAN_FIELD_CHANGED:' + name
        assert current.get('visual_quality'), 'V018_SCENE_PROFILE_MISSING'
    plain = copy.deepcopy(selected)
    plain['metadata'].pop('visual_quality')
    plain.pop('gate', None)
    baseline = copy.deepcopy(original)
    baseline.pop('gate', None)
    for scene in plain['scenes']:
        scene.pop('visual_quality')
    assert plain == baseline, 'V018_NON_QUALITY_PLAN_FIELD_CHANGED'
    import subprocess
    candidate_path = folder / 'PLAN.json'
    candidate_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    node = subprocess.run(['node', 'tools/test_visual_quality_v018.mjs', str(candidate_path)],
                          cwd=APP_ROOT, capture_output=True, text=True, check=True)
    material = json.loads(node.stdout)
    assert material['passed'] and material['frames'] == 720 and material['camera_trajectory'] == 'UNCHANGED', 'V018_MATERIAL_CAMERA_CONTRACT_FAILED'
    source_records = []
    for name in SOURCES:
        path = APP_ROOT / name
        assert path.is_file() and path.stat().st_size > 0, 'V018_QUALITY_SOURCE_MISSING'
        source_records.append(dict(file=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), non_zero=True))
    scene_path = folder / 'selected-scene.json'
    scene_path.write_text(json.dumps(selected['scenes'][0], ensure_ascii=False, indent=2))
    command = ['node', str(APP_ROOT / 'tools/render_production_scene.mjs'), '--scene-json', str(scene_path),
               '--url', 'http://127.0.0.1/static/render_production_earth.html']
    transformed = quality_command(command)
    assert urlsplit(transformed[transformed.index('--url') + 1]).path == '/static/render_visual_quality_earth.html', 'V018_QUALITY_PAGE_NOT_SELECTED'
    stripped = list(transformed)
    stripped[stripped.index('--url') + 1] = command[command.index('--url') + 1]
    assert stripped == command, 'V018_RENDER_COMMAND_OTHER_ARGS_CHANGED'
    with patch('engine.backends.CPULocalBackend.run', lambda self, values, cwd, progress: values):
        actual = VisualQualityBackend().run(command, APP_ROOT, lambda event: None)
    assert actual == transformed, 'V018_EXISTING_GPU_TRANSPORT_NOT_REUSED'
    default = generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                                          qa_mode=False, quality='HIGH', tts=False, subtitles=False,
                                          bgm=True, sfx=True))
    assert all(scene.get('visual_quality') for scene in default['scenes']), 'V018_IMAGE_DEFAULT_PROFILE_MISSING'
    default_validation = validate_quality(default)
    assert default_validation['passed'], default_validation
    (folder / 'PLAN.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    report = dict(passed=True, validation=validation, default_validation=default_validation,
                  material_contract=material,
                  explicit_profile=selected['scenes'][0]['visual_quality'], sources=source_records,
                  camera_and_event_fields_unchanged=True, backend_page='/static/render_visual_quality_earth.html',
                  transport='unchanged CPULocalBackend/strict GPU worker', gpu='NOT_RUN')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def run(folder):
    from deployment.gcube.asset_audit import audit_assets
    from deployment.gcube.second_camera_preflight import run as camera_run
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    preserved = audit_frozen_sources()
    assert preserved['passed'], 'V018_PROTECTED_SOURCE_CHANGED'
    settings = quality_settings('HIGH')
    assert (settings['internal_width'], settings['output_width'], settings['output_height'], settings['fps']) == (2160, 1080, 1920, 30), 'V018_RENDER_RESOLUTION_CHANGED'
    assets = audit_assets()
    assert assets['passed'], 'V018_CONTAINER_ASSET_MISSING'
    detail = audit_detail_sources()
    serving = audit_served_detail(detail)
    import os
    previous_version = os.environ.get('WORLD_ENGINE_VISUAL_QUALITY_VERSION')
    os.environ['WORLD_ENGINE_VISUAL_QUALITY_VERSION'] = 'legacy'
    try:
        camera = camera_run(folder / 'camera')
    finally:
        if previous_version is None:
            os.environ.pop('WORLD_ENGINE_VISUAL_QUALITY_VERSION', None)
        else:
            os.environ['WORLD_ENGINE_VISUAL_QUALITY_VERSION'] = previous_version
    baseline_plan = json.loads((folder / 'camera/plan.json').read_text())
    quality = audit_selected_quality(baseline_plan, folder / 'quality')
    assert camera['passed'], 'V018_CAMERA_TRAJECTORY_INVALID'
    report = dict(passed=True, preserved=preserved, asset_count=len(assets['assets']), assets=assets,
                  camera=camera, detail=detail, selected_quality=quality, served_detail=serving, render_settings=settings, physical_gpu='NOT_RUN', output_quality='NOT_RUN',
                  scope='Container filesystem, exact 720-frame native camera/geometry and static quality contracts; NVIDIA pixel output unverified')
    (folder / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('::notice title=Frozen-camera visual-quality preflight::' + json.dumps({key: value for key, value in report.items() if key not in ('preserved','assets','camera','detail','selected_quality')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
