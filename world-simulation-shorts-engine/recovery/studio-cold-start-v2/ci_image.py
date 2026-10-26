#!/usr/bin/env python3
"""One-shot public CPU packaging/publication; no GPU, credentials or render payloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

BASE_DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
SOURCE_SHA = '138f5ff4761e2fa3589e15493ded5401afe1ec4dfa0dc5ad5a725e03e53b9270'
REL = 'world-simulation-shorts-engine/recovery/studio-cold-start-v2'
SOURCE = 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
IN_REPO = '/opt/world-engine-handoffs/studio-v2/repo'
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(argv, timeout=1200, env=None):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, env=env, text=True)
    require(result.returncode == 0, 'IMAGE_COMMAND_FAILED')
    return result.stdout


def regular(repo, relative):
    part = PurePosixPath(relative)
    require(not part.is_absolute() and '..' not in part.parts and part.as_posix() == relative,
            'IMAGE_CANONICAL_SOURCE_REQUIRED')
    path = repo / relative
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            'IMAGE_REGULAR_SOURCE_REQUIRED')
    return path.read_bytes()


def stage(args):
    repo, context = args.repo.resolve(strict=True), args.context
    require(not context.exists(), 'IMAGE_NEW_BUILD_CONTEXT_REQUIRED')
    source = regular(repo, SOURCE)
    require(sha(source) == SOURCE_SHA, 'IMAGE_FROZEN_MANIFEST_REQUIRED')
    rows = json.loads(source)['files']
    require(len(rows) == 350 and len({r['path'] for r in rows}) == 350,
            'IMAGE_RUNTIME_INVENTORY_REQUIRED')
    startup = regular(repo, REL + '/STARTUP_MANIFEST.json')
    new = json.loads(startup)
    require(new['schema'] == 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2'
            and new['baseImageDigest'] == BASE_DIGEST
            and new['runtimeManifestSHA256'] == SOURCE_SHA
            and set(new['files']) == {'bootstrap.py', 'worker.py'}, 'IMAGE_STARTUP_CONTRACT_REQUIRED')
    members = [(r['path'], r) for r in rows]
    members += [(SOURCE, {'sha256': SOURCE_SHA, 'bytes': len(source)}),
                (REL + '/STARTUP_MANIFEST.json', {'sha256': sha(startup), 'bytes': len(startup)})]
    members += [(REL + '/' + name, row) for name, row in new['files'].items()]
    context.mkdir(mode=0o700, parents=True)
    for name, expected in members:
        data = regular(repo, name)
        require(len(data) == expected['bytes'] and sha(data) == expected['sha256'],
                'IMAGE_PACKAGED_SOURCE_CHANGED')
        target = context / 'repo' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        target.chmod(0o644)
    entry = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B',
             IN_REPO + '/' + REL + '/bootstrap.py',
             '--startup-manifest', IN_REPO + '/' + REL + '/STARTUP_MANIFEST.json',
             '--startup-manifest-sha256', sha(startup),
             '--source-manifest', IN_REPO + '/' + SOURCE,
             '--source-manifest-sha256', SOURCE_SHA, '--export-root', '/world-storage']
    dockerfile = '\n'.join([
        'FROM ' + IMAGE + '@' + BASE_DIGEST,
        'USER 0',
        'RUN test ! -e /opt/world-engine-handoffs/studio-v2 && test ! -e /var/lib/world-engine-studio-v2',
        'COPY --chown=0:0 repo/ ' + IN_REPO + '/',
        'RUN find /opt/world-engine-handoffs/studio-v2 -type d -exec chmod 0755 {} + && '
        'find /opt/world-engine-handoffs/studio-v2 -type f -exec chmod 0644 {} + && '
        'mkdir -m 0755 /var/lib/world-engine-studio-v2',
        'ENV GPU_BACKEND=vulkan WORLD_ENGINE_STUDIO_PORT=8080 '
        'WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-studio-v2/auth '
        'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN="" WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST="" '
        'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST="" PYTHONDONTWRITEBYTECODE=1',
        'LABEL org.opencontainers.image.source="https://github.com/dimon3898-sys/yeonhwarok-free"',
        'LABEL world-engine.studio-v2.base-digest="' + BASE_DIGEST + '"',
        'ENTRYPOINT ' + json.dumps(entry), 'CMD []', ''])
    (context / 'Dockerfile').write_text(dockerfile)
    print(json.dumps({'status': 'STAGED', 'files': len(members), 'baseImageDigest': BASE_DIGEST,
                      'startupManifestSHA256': sha(startup), 'sourceManifestPreserved': True}))


def registry_get(reference):
    # Preserve the bounded anonymous-read protocol used by the existing image CI.
    token_url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io',
        'scope': 'repository:dimon3898-sys/world-simulation-shorts-engine:pull'})
    with urllib.request.urlopen(token_url, timeout=30) as response:
        token = json.loads(response.read(65537))['token']
    url = 'https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/' + reference
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json',
        'Accept-Encoding': 'identity'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(4 * 1024**2 + 1)
            digest = response.headers.get('Docker-Content-Digest')
        require(len(raw) <= 4 * 1024**2 and DIGEST.fullmatch(str(digest))
                and sha(raw) == digest[7:], 'IMAGE_REMOTE_MANIFEST_SHA_REQUIRED')
        value = json.loads(raw)
        require(value.get('schemaVersion') == 2
                and DIGEST.fullmatch(str(value.get('config', {}).get('digest'))),
                'IMAGE_SINGLE_PLATFORM_REQUIRED')
        return {'status': 200, 'digest': digest, 'configDigest': value['config']['digest']}
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {'status': 404}
        raise RuntimeError('IMAGE_REGISTRY_READ_FAILED') from None


def publish(args):
    require(os.environ.get('GITHUB_REPOSITORY') == 'dimon3898-sys/yeonhwarok-free'
            and os.environ.get('GITHUB_REF') == 'refs/heads/recovery/world-engine-studio-deploy-20261026'
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
            and os.environ.get('WORLD_ENGINE_PUBLIC_CPU_RUNNER') == 'ubuntu-24.04',
            'IMAGE_APPROVED_PUBLIC_CPU_RUN_REQUIRED')
    tag = args.image.removeprefix(IMAGE + ':')
    expected = 'studio-setup-v2-20261026-' + os.environ['GITHUB_SHA'][:12] + '-' + os.environ['GITHUB_RUN_ID']
    require(args.image == IMAGE + ':' + tag and tag == expected, 'IMAGE_UNIQUE_NEW_TAG_REQUIRED')
    facts = json.loads(args.result.read_text())
    require(facts.get('status') == 'PASS' and facts.get('gpuExecuted') is False
            and facts.get('renderExecuted') is False and facts.get('defaultEntrypointVerified') is True,
            'IMAGE_CPU_DELTA_PASS_REQUIRED')
    local = json.loads(run(['docker', 'image', 'inspect', args.image]))[0]
    require(facts.get('imageConfigDigest') == local['Id'], 'IMAGE_TESTED_CONFIG_MISMATCH')
    require(registry_get(tag)['status'] == 404, 'IMAGE_EXISTING_TAG_MUST_NOT_BE_OVERWRITTEN')
    token, actor = os.environ.get('GH_TOKEN', ''), os.environ.get('GITHUB_ACTOR', '')
    require(token and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?', actor),
            'IMAGE_REGISTRY_AUTH_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='world-engine-registry-') as directory:
        env = dict(os.environ, DOCKER_CONFIG=directory)
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        login = subprocess.run(['docker', 'login', 'ghcr.io', '--username', actor, '--password-stdin'],
                               input=token, text=True, env=env, capture_output=True, timeout=60)
        require(login.returncode == 0, 'IMAGE_REGISTRY_LOGIN_FAILED')
        run(['docker', 'push', args.image], env=env)
    remote = registry_get(tag)
    require(remote.get('status') == 200 and remote.get('configDigest') == local['Id'],
            'IMAGE_PUBLISHED_CONFIG_MISMATCH')
    immutable = registry_get(remote['digest'])
    require(immutable == remote, 'IMAGE_TAG_DIGEST_READBACK_MISMATCH')
    value = {'status': 'PUBLISHED_CPU_VERIFIED_GPU_PENDING', 'imageTag': args.image,
             'imageDigest': remote['digest'], 'imageConfigDigest': local['Id'],
             'baseImageDigest': BASE_DIGEST, 'sourceCommit': os.environ['GITHUB_SHA'],
             'publicRegistryReadbackVerified': True, 'gpuExecuted': False, 'renderExecuted': False}
    print('WORLD_ENGINE_IMAGE_RESULT=' + json.dumps(value, sort_keys=True))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('```json\n' + json.dumps(value, indent=2) + '\n```\n')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('stage')
    s.add_argument('--repo', type=Path, required=True)
    s.add_argument('--context', type=Path, required=True)
    p = sub.add_parser('publish')
    p.add_argument('--image', required=True)
    p.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        {'stage': stage, 'publish': publish}[args.mode](args)
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'IMAGE_[A-Z0-9_]+', code):
            code = 'IMAGE_OPERATION_BLOCKED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'gpuExecuted': False}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
