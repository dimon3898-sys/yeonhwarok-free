"""One metadata-only capacity gate for this local candidate attempt.

No Docker pull/build/push, no GPU, no retries. Secret values are never persisted.
This is a conservative estimate, not a measured expanded image footprint.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
IMAGE = 'dimon3898-sys/world-simulation-shorts-engine'
DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'

def main():
    preflight = json.loads((ROOT / 'docker-preflight.json').read_text())
    if preflight['exitCode'] != 0:
        raise RuntimeError('LOCAL_DOCKER_ACCESS_NOT_CONFIRMED')
    facts = json.loads(preflight['stdout'])
    inventory = json.loads((ROOT / 'image-space-inventory.json').read_text())
    if inventory['exitCode'] != 0:
        raise RuntimeError('LOCAL_IMAGE_INVENTORY_NOT_CONFIRMED')
    # Anonymous pull-scope token remains only in process memory, never logs.
    query = urllib.parse.urlencode({'service': 'ghcr.io', 'scope': 'repository:' + IMAGE + ':pull'})
    with urllib.request.urlopen('https://ghcr.io/token?' + query, timeout=30) as response:
        token = json.load(response)['token']
    request = urllib.request.Request('https://ghcr.io/v2/' + IMAGE + '/manifests/' + DIGEST,
        headers={'Authorization': 'Bearer ' + token,
                 'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(1024 * 1024 + 1)
        returned = response.headers.get('Docker-Content-Digest')
    if len(raw) > 1024 * 1024 or returned != DIGEST or 'sha256:' + hashlib.sha256(raw).hexdigest() != DIGEST:
        raise RuntimeError('PARENT_REGISTRY_MANIFEST_IDENTITY_MISMATCH')
    manifest = json.loads(raw)
    layers = manifest.get('layers')
    if not isinstance(layers, list) or not layers or any(type(x.get('size')) is not int or x['size'] < 0 for x in layers):
        raise RuntimeError('PARENT_SINGLE_PLATFORM_MANIFEST_REQUIRED')
    (ROOT / 'parent-registry-manifest.json').write_bytes(raw)
    compressed = sum(x['size'] for x in layers)
    # vfs retains deep filesystem copies per layer. Account for repeated prefix
    # copies; deletion/whiteout and compression ratios make this an estimate.
    weighted = sum((len(layers) - i) * x['size'] for i, x in enumerate(layers))
    reserve = 8 * 1024**3
    estimated = (weighted if facts['driver'] == 'vfs' else compressed) * 4 + reserve
    disk = shutil.disk_usage(facts['dockerRootDir'])
    parent_cached = any(x.get('Digest') == DIGEST for x in inventory['images'])
    if parent_cached:
        estimated = reserve
    result = {'schema': 'WORLD_ENGINE_SURFACE_LOCAL_CAPACITY_PREFLIGHT_V1',
        'parentDigest': DIGEST, 'registryManifestVerified': True,
        'driver': facts['driver'], 'parentCached': parent_cached,
        'layerCount': len(layers), 'compressedLayerBytes': compressed,
        'vfsWeightedCompressedLayerBytes': weighted, 'freeBytes': disk.free,
        'estimatedRequiredBytes': estimated, 'reserveBytes': reserve,
        'estimateBasis': '4x cumulative compressed prefixes for vfs (otherwise 4x compressed bytes), plus 8 GiB reserve; not measured expansion',
        'status': 'PASS_CAPACITY_ESTIMATE' if disk.free >= estimated else 'BLOCKED_CAPACITY_ESTIMATE',
        'localCpuOnly': True, 'externalPaidRunnerRequested': False,
        'gpuExecuted': False, 'pullAttempts': 0, 'buildAttempts': 0, 'retryCount': 0}
    (ROOT / 'capacity-preflight.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if disk.free >= estimated else 2

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        result = {'stage': 'REGISTRY_CAPACITY_PREFLIGHT', 'status': 'BLOCKED',
            'errorType': type(error).__name__,
            'code': str(error) if isinstance(error, RuntimeError) else 'PREFLIGHT_REQUEST_OR_STORAGE_FAILED',
            'pullAttempts': 0, 'buildAttempts': 0, 'retryCount': 0, 'gpuExecuted': False}
        (ROOT / 'capacity-preflight.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        raise SystemExit(1) from None
