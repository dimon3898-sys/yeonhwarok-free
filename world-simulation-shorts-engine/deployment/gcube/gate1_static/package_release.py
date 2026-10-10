"""Freeze existing iteration-05 bytes. Does not invoke any renderer."""
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
BASE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:60108bcc6f5c097eafb5003d78050ec97996702eda8458ec85a2adb208551bb6'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def package(proof, output):
    start = time.monotonic()
    def report(stage, result='PASS'):
        print(json.dumps({'stage': stage, 'result': result, 'elapsed_seconds': round(time.monotonic() - start, 3)}), flush=True)
    proof, output = Path(proof), Path(output)
    if output.exists():
        raise ValueError('OUTPUT_MUST_BE_NEW_DIRECTORY')
    plan_bytes = (proof / 'compiled-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    renderer = (proof / 'renderer-source.mjs').read_bytes()
    assert renderer == (APP / 'web/map_infographic_v1/renderer.mjs').read_bytes()
    assert sha(renderer) == plan['provenance']['shaderHash']
    assert plan['kind'] == 'STATIC_ONLY' and plan['gate'] == 1
    output.mkdir(parents=True)
    bundle = output / 'bundle'
    bundle.mkdir()
    files, routes = [], []
    def put(file, content, url=None):
        target = bundle / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files.append({'file': file, 'bytes': len(content), 'sha256': sha(content)})
        if url:
            routes.append({'url': url, 'file': file})
    put('compiled-plan.json', plan_bytes)
    put('renderer.mjs', renderer, '/static/map_infographic_v1/renderer.mjs')
    put('source-scene-plan.json', (proof / 'source-scene-plan.json').read_bytes())
    assert sha((proof / 'source-scene-plan.json').read_bytes()) == plan['provenance']['sceneHash']
    for key, asset in plan['assets'].items():
        source = (APP / asset['file']).resolve()
        content = source.read_bytes()
        assert sha(content) == asset['sha256'], key + '_ASSET_HASH_MISMATCH'
        put('assets/' + key + source.suffix, content, asset['url'])
    put('three.module.js', (REPO / 'cinematic-world-map/node_modules/three/build/three.module.js').read_bytes(), '/three.js')
    registry = (APP / 'data/infographic/v022/registry.json').read_bytes()
    countries = (REPO / 'cinematic-world-map/assets/gis/countries_50m.geojson').read_bytes()
    assert sha(registry) == plan['provenance']['registryHash']
    assert sha(countries) == plan['provenance']['gisHash']
    put('data/registry.json', registry)
    put('data/countries_50m.geojson', countries)
    put('asset-credits.json', (proof / 'asset-credits.json').read_bytes())
    for source in sorted((proof / 'licenses').glob('*')):
        if source.is_file():
            put('licenses/' + source.name, source.read_bytes())
    for name in ['server.py', 'worker.mjs', 'capability.mjs', 'index.html', 'ui.js', 'ui.css', 'README.md']:
        shutil.copyfile(HERE / name, output / name)
    for name in ['chromium_wrapper.py', 'graphics_runtime.py', 'gpu_access.py']:
        shutil.copyfile(HERE.parent / name, output / name)
    (output / 'chromium_wrapper.py').chmod(0o755)
    identity = {**plan['provenance'], 'compiledPlanHash': sha(plan_bytes), 'seed': plan['seed'],
                'softwareProofHash': sha((proof / 'proof.png').read_bytes()),
                'shaderVersion': 'explicit-glsl-1', 'themeVersion': 'terrain-material-1',
                'threeVersion': '0.170.0', 'playwrightVersion': '1.62.1'}
    dockerfile = f'''FROM {BASE}
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
'''
    (output / 'Dockerfile').write_text(dockerfile)
    release_files = [{'file': str(p.relative_to(output)), 'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                     for p in sorted(output.rglob('*')) if p.is_file()]
    release_hash = sha(json.dumps(release_files, sort_keys=True, separators=(',', ':')).encode())
    manifest = {'version': 1, 'release_source_hash': release_hash, 'source_identity': identity,
                'shader_version': identity['shaderVersion'], 'theme_version': identity['themeVersion'],
                'files': files, 'routes': routes, 'release_files': release_files,
                'base': BASE, 'tag': 'gcube-map-renderer-v1-gate1-static-' + release_hash[:12],
                'policy': {'frame_count': 1, 'gpu_required': True, 'software_fallback': False, 'user_visual_approval': True,
                           'video': False, 'audio': False, 'animation': False, 'gate2': False}}
    (bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    # Readability inside the provider's UID 1000 runtime; original files untouched.
    for file in output.rglob('*'):
        file.chmod(0o755 if file.is_dir() or file.name == 'chromium_wrapper.py' else 0o644)
    report('FROZEN_RELEASE_BUNDLE')
    print(json.dumps({'tag': manifest['tag'], 'source_hash': release_hash, 'bundle_bytes': sum(r['bytes'] for r in release_files)}), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', default='/tmp/world-map-gate1/iteration-05')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    package(args.proof, args.output)
