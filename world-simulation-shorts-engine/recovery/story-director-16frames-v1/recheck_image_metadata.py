#!/usr/bin/env python3
"""Anonymous GHCR manifest/config metadata only; never pulls layers or deploys.

The transient anonymous registry bearer is held only in memory and never emitted.
Configured account secrets, Docker credentials and gCube credentials are unused.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PACKAGE = 'dimon3898-sys/world-simulation-shorts-engine'
DIGEST = 'sha256:1bb399679bfaf1f3d6d57df67c139974e8c63862f07142e950b9b6d150281c9f'
RUN = HERE.parent / 'render-path-reconciliation-v1/runs/39317457661-1'
ACCEPT = ','.join(('application/vnd.oci.image.index.v1+json',
                   'application/vnd.docker.distribution.manifest.list.v2+json',
                   'application/vnd.oci.image.manifest.v1+json',
                   'application/vnd.docker.distribution.manifest.v2+json'))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def local_evidence():
    result = {}
    for name in ('IMAGE_PROOF.json', 'OLD_CAPTURE_COMPATIBILITY_IMAGE_PROOF.json', 'pull.json'):
        raw = (RUN / name).read_bytes()
        data = json.loads(raw)
        result[name] = {'path': str((RUN / name).relative_to(HERE.parents[2])),
                        'sha256': sha(raw), 'imageDigest': data.get('imageDigest'),
                        'sourceCommit': data.get('sourceCommit'),
                        'independentPullVerified': data.get('independentPullVerified', data.get('pullVerified')),
                        'sourceHashesVerified': data.get('sourceHashesVerified'),
                        'sourceManifestSHA256': data.get('sourceManifestSHA256')}
        if name == 'pull.json':
            result[name]['sourceVerification'] = data.get('imageHashes')
    return result


def fetch(url, token=None, accept=None, limit=2 * 1024 * 1024):
    headers = {'User-Agent': 'world-engine-anonymous-metadata-recheck/1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if accept:
        headers['Accept'] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('REGISTRY_METADATA_LIMIT_EXCEEDED')
        return raw, {'httpStatus': response.status,
                     'contentType': response.headers.get('Content-Type'),
                     'dockerContentDigest': response.headers.get('Docker-Content-Digest'),
                     'bytes': len(raw), 'sha256': sha(raw)}


def run():
    report = {'schema': 'WORLD_ENGINE_DIRECTOR_IMAGE_METADATA_RECHECK_V1',
              'checkedAtUTC': dt.datetime.now(dt.timezone.utc).isoformat(),
              'requestedImage': IMAGE + '@' + DIGEST, 'localAttestations': local_evidence(),
              'operation': 'ANONYMOUS_READ_ONLY_MANIFEST_AND_CONFIG',
              'imageLayersDownloaded': False, 'newImageBuilt': False, 'gCubeQueried': False,
              'gCubeActualDeployedImage': 'UNVERIFIED_NO_DEPLOYMENT_RESPONSE',
              'thisPreviewActuallyUsesContainer': False, 'actualPreviewMode': 'LOCAL_CHECKOUT_SWIFTSHADER',
              'nvidiaHardwareVerified': False, 'visualQualityApproved': False}
    try:
        url = 'https://ghcr.io/token?' + urllib.parse.urlencode({
            'service': 'ghcr.io', 'scope': 'repository:' + PACKAGE + ':pull'})
        token_raw, token_meta = fetch(url, limit=64 * 1024)
        token_data = json.loads(token_raw)
        token = token_data.get('token') or token_data.get('access_token')
        if not isinstance(token, str) or not token:
            raise ValueError('ANONYMOUS_REGISTRY_TOKEN_UNAVAILABLE')
        # No bearer value, raw token body, URL query credentials or env is saved.
        report['anonymousRegistryAuthorization'] = {'httpStatus': token_meta['httpStatus'],
                                                    'accountCredentialsUsed': False}
        manifest_raw, manifest_meta = fetch('https://ghcr.io/v2/' + PACKAGE + '/manifests/' + DIGEST,
                                             token, ACCEPT)
        manifest = json.loads(manifest_raw)
        if 'sha256:' + sha(manifest_raw) != DIGEST:
            raise ValueError('REGISTRY_MANIFEST_DIGEST_MISMATCH')
        report['manifest'] = {**manifest_meta, 'mediaType': manifest.get('mediaType'),
                              'schemaVersion': manifest.get('schemaVersion'),
                              'digestMatchesRequested': True,
                              'layerCount': len(manifest.get('layers', [])),
                              'layerCompressedBytes': sum(row.get('size', 0) for row in manifest.get('layers', []))}
        config_ref = manifest.get('config', {}).get('digest')
        if config_ref:
            config_raw, config_meta = fetch('https://ghcr.io/v2/' + PACKAGE + '/blobs/' + config_ref, token)
            if 'sha256:' + sha(config_raw) != config_ref:
                raise ValueError('REGISTRY_CONFIG_DIGEST_MISMATCH')
            config = json.loads(config_raw)
            report['config'] = {**config_meta, 'digest': config_ref,
                                'digestMatchesManifest': True, 'os': config.get('os'),
                                'architecture': config.get('architecture'),
                                'created': config.get('created'),
                                'entrypoint': config.get('config', {}).get('Entrypoint'),
                                'cmd': config.get('config', {}).get('Cmd')}
        else:
            report['platforms'] = [row.get('platform') for row in manifest.get('manifests', [])]
        report['status'] = 'PASS_METADATA_ONLY'
    except urllib.error.HTTPError as error:
        report.update(status='BLOCKED_METADATA_REQUEST', errorCode='REGISTRY_HTTP_' + str(error.code))
    except (urllib.error.URLError, TimeoutError, OSError):
        report.update(status='BLOCKED_METADATA_REQUEST', errorCode='REGISTRY_NETWORK_OR_TLS_UNAVAILABLE')
    except (ValueError, KeyError, TypeError) as error:
        code = str(error)
        report.update(status='FAIL_METADATA_VALIDATION', errorCode=code if code.isupper() else 'REGISTRY_METADATA_INVALID')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run()
    with args.output.open('x') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'status': report['status'], 'errorCode': report.get('errorCode'),
                      'output': str(args.output), 'noGpuOrLayersDownloaded': True}))
