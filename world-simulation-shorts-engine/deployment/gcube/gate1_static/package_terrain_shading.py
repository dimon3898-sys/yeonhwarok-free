"""Package existing Software D-final bytes; never compiles or tunes a renderer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

HERE = Path(__file__).resolve().parent
APP = HERE.parents[2]
REPO = APP.parent
BASE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3e21084094f5ec4eab9962df0bc3c01082534b6ebe585cdefbe5ae5961596b8e'
RENDERER_SHA = 'e0108a8bf3cb3828529b9077925b9429455dbccd2c695f797f2578ac904b067d'
PROOF_SHA = '29323353b1e76af7dfbc54407a9cdbdbb559fbfefe9ffac08d70f65f54e98a8d'
HEIGHT_SHA = '08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8'
PARAMETERS = {'dem': True, 'correctedLight': True, 'verticalExaggeration': 2,
              'bakedSuppression': .1, 'shadingCorrection': 'OUTPUT'}


def sha_file(file):
    with Path(file).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(proof, output):
    start = time.monotonic()
    def report(stage, result='PASS'):
        print(json.dumps({'stage': stage, 'result': result, 'elapsed_seconds': round(time.monotonic()-start, 3)}), flush=True)
    proof, output = Path(proof), Path(output)
    if output.exists():
        raise ValueError('OUTPUT_MUST_BE_NEW_DIRECTORY')
    renderer = proof/'renderer-source.mjs'
    assert sha_file(renderer) == RENDERER_SHA
    assert renderer.read_bytes() == (APP/'web/map_infographic_v1/renderer.mjs').read_bytes()
    plan = json.loads((proof/'compiled-plan.json').read_bytes())
    assert plan['provenance']['shaderHash'] == RENDERER_SHA
    assert plan['kind'] == 'STATIC_ONLY' and plan['gate'] == 1
    assert sha_file(proof/'D-final.png') == PROOF_SHA
    height = json.loads((proof/'height-source.json').read_bytes())
    assert height['sha256'] == HEIGHT_SHA and height['dimensions'] == [7200, 7200]
    bundle = output/'bundle'
    bundle.mkdir(parents=True)
    files, routes = [], []
    def put(name, source, url=None):
        target = bundle/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({'file': name, 'bytes': target.stat().st_size, 'sha256': sha_file(target)})
        if url:
            routes.append({'url': url, 'file': name})
    def put_json(name, data):
        target = bundle/name
        target.write_text(json.dumps(data, indent=2)+'\n')
        files.append({'file': name, 'bytes': target.stat().st_size, 'sha256': sha_file(target)})
    for name in ['compiled-plan.json', 'source-scene-plan.json', 'asset-credits.json', 'D-final.png']:
        put(name, proof/name)
    assert sha_file(proof/'source-scene-plan.json') == plan['provenance']['sceneHash']
    put('renderer.mjs', renderer, '/static/map_infographic_v1/renderer.mjs')
    put('height-source.original.json', proof/'height-source.json')
    put('software-D-diagnostic.json', proof/'diagnostic.json')
    # Lossless transport chunks avoid Git's per-file limit. Reconstruct exact
    # already-admitted atlas bytes, without raster decode/resampling/conversion.
    chunks = proof/'height-parts.json'
    if chunks.exists():
        parts = json.loads(chunks.read_bytes())
        with (bundle/'height.f32').open('wb') as target:
            for row in parts:
                source = proof/row['file']
                assert sha_file(source) == row['sha256']
                with source.open('rb') as stream:
                    shutil.copyfileobj(stream, target, 1024*1024)
        assert sha_file(bundle/'height.f32') == HEIGHT_SHA
        files.append({'file': 'height.f32', 'bytes': (bundle/'height.f32').stat().st_size, 'sha256': HEIGHT_SHA})
        routes.append({'url': '/height.f32', 'file': 'height.f32'})
    else:
        assert sha_file(height['file']) == HEIGHT_SHA
        put('height.f32', height['file'], '/height.f32')
    height['file'], height['url'] = 'height.f32', '/height.f32'
    for row in height['originals']:
        name = Path(row['file']).name
        source = proof/'dem-originals'/name
        if not source.exists():
            source = Path(row['file'])
        assert sha_file(source) == row['sha256']
        put('dem-originals/'+name, source)
        row['file'] = 'dem-originals/'+name
    put_json('height-source.json', height)
    put_json('render-parameters.json', PARAMETERS)
    for key, asset in plan['assets'].items():
        source = (APP/asset['file']).resolve()
        assert sha_file(source) == asset['sha256'], key+'_ASSET_HASH_MISMATCH'
        put('assets/'+key+source.suffix, source, asset['url'])
    put('three.module.js', REPO/'cinematic-world-map/node_modules/three/build/three.module.js', '/three.js')
    registry = APP/'data/infographic/v022/registry.json'
    countries = REPO/'cinematic-world-map/assets/gis/countries_50m.geojson'
    assert sha_file(registry) == plan['provenance']['registryHash']
    assert sha_file(countries) == plan['provenance']['gisHash']
    put('data/registry.json', registry)
    put('data/countries_50m.geojson', countries)
    for source in sorted((proof/'licenses').glob('*')):
        if source.is_file():
            put('licenses/'+source.name, source)
    for name in ['server.py', 'worker.mjs', 'capability.mjs', 'diagnostic.mjs', 'bootstrap.py',
                 'browser_capture.py', 'index.html', 'ui.js', 'ui.css', 'README.md']:
        shutil.copyfile(HERE/name, output/name)
    for name in ['chromium_wrapper.py', 'graphics_runtime.py', 'gpu_access.py', 'gpu_runtime_facts.py']:
        shutil.copyfile(HERE.parent/name, output/name)
    identity = {**plan['provenance'], 'compiledPlanHash': sha_file(proof/'compiled-plan.json'),
                'seed': plan['seed'], 'softwareProofHash': PROOF_SHA, 'softwareDFinalHash': PROOF_SHA,
                'heightSourceHash': HEIGHT_SHA, 'demSourceHashes': [row['sha256'] for row in height['originals']],
                'originalHeightDescriptorHash': sha_file(proof/'height-source.json'),
                'shaderVersion': 'explicit-glsl-1-terrain-shading-correction', 'themeVersion': 'terrain-material-1',
                'threeVersion': '0.170.0', 'playwrightVersion': '1.62.1'}
    (output/'Dockerfile').write_text(f'''FROM {BASE}
COPY --chown=1000:1000 . /opt/gate1-static/
USER root
WORKDIR /opt/gate1-static
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000 \\
    STATIC_PROOF_BUNDLE=/opt/gate1-static/bundle \\
    STATIC_PROOF_PLAYWRIGHT_PACKAGE=/opt/world-engine/cinematic-world-map/package.json \\
    WORLD_ENGINE_RENDER_MODE=gpu-required WORLD_ENGINE_GPU_PROFILE=vulkan \\
    NVIDIA_DRIVER_CAPABILITIES=graphics,utility
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD ["python", "-c", "import json,urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({{}})); r=json.load(o.open('http://127.0.0.1:8000/healthz',timeout=3)); assert r['ok'] and r['authentication_required'] and not r['auto_render']"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "python", "/opt/gate1-static/server.py"]
CMD []
''')
    release_files = [{'file': str(p.relative_to(output)), 'sha256': sha_file(p), 'bytes': p.stat().st_size}
                     for p in sorted(output.rglob('*')) if p.is_file()]
    release_hash = hashlib.sha256(json.dumps(release_files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    manifest = {'version': 1, 'purpose': 'GATE1_TERRAIN_SHADING_STATIC_PROOF',
                'png_filename': 'SUEZ_TERRAIN_SHADING_RTX4080S.png',
                'release_source_hash': release_hash, 'source_identity': identity,
                'software_d_final_hash': PROOF_SHA, 'render_parameters': PARAMETERS,
                'shader_version': identity['shaderVersion'], 'theme_version': identity['themeVersion'],
                'files': files, 'routes': routes, 'release_files': release_files, 'base': BASE,
                'tag': 'gcube-map-renderer-v1-terrain-shading-'+release_hash[:12],
                'policy': {'frame_count': 1, 'gpu_required': True, 'software_fallback': False,
                           'check_gpu_required': True, 'user_visual_approval': True,
                           'video': False, 'audio': False, 'animation': False, 'gate2': False}}
    (bundle/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    for file in output.rglob('*'):
        file.chmod(0o755 if file.is_dir() or file.name in {'chromium_wrapper.py', 'browser_capture.py'} else 0o644)
    report('FROZEN_D_RELEASE_BUNDLE')
    print(json.dumps({'tag': manifest['tag'], 'renderer_hash': RENDERER_SHA,
                      'source_hash': release_hash, 'bundle_bytes': sum(r['bytes'] for r in release_files)}), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', default=str(HERE/'frozen_terrain'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    package(args.proof, args.output)
