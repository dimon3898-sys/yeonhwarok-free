#!/usr/bin/env python3
"""Publish one config-only derivative after targeted, actual CPU container checks."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
BASE = IMAGE + '@sha256:32c677d1dbeec3908b6790484b34905ad6818f8e5a9127106579f7dfd233342e'
BRANCH = 'refs/heads/recovery/world-engine-gpu-preflight-20261026'
DEPS = '/opt/rtx-package/repo/cinematic-world-map'
KEY = 'WORLD_ENGINE_NODE_DEPS'


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def authority():
    require(os.environ.get('GITHUB_REPOSITORY') == 'dimon3898-sys/yeonhwarok-free'
            and os.environ.get('GITHUB_REF') == BRANCH
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
            and os.environ.get('WORLD_ENGINE_PUBLIC_CPU_RUNNER') == 'ubuntu-24.04',
            'PREFLIGHT_PUBLIC_SINGLE_CPU_RUN_REQUIRED')
    commit, run = os.environ.get('GITHUB_SHA', ''), os.environ.get('GITHUB_RUN_ID', '')
    require(re.fullmatch('[a-f0-9]{40}', commit) and run.isdecimal(), 'PREFLIGHT_RUN_ID_REQUIRED')
    return IMAGE + ':preflight-fix-v1-20261026-' + commit[:12] + '-' + run


def execute(command, *, env=None, timeout=360):
    result = subprocess.run(command, capture_output=True, text=True, env=env,
                            stdin=subprocess.DEVNULL, timeout=timeout)
    require(result.returncode == 0, 'PREFLIGHT_IMAGE_COMMAND_FAILED')
    return result.stdout


def config_only(base, candidate):
    require(base['RootFS'] == candidate['RootFS'], 'PREFLIGHT_IMAGE_FILESYSTEM_CHANGED')
    old, new = dict(base['Config']), dict(candidate['Config'])
    old_env, new_env = old.pop('Env'), new.pop('Env')
    require(old == new, 'PREFLIGHT_UNRELATED_IMAGE_CONFIG_CHANGED')
    def environment(rows):
        pairs = [x.split('=', 1) for x in rows]
        require(all(len(x) == 2 for x in pairs) and len({x[0] for x in pairs}) == len(pairs),
                'PREFLIGHT_DUPLICATE_ENVIRONMENT')
        return dict(pairs)
    previous, current = environment(old_env), environment(new_env)
    require(KEY not in previous, 'PREFLIGHT_BASELINE_ENVIRONMENT_UNEXPECTED')
    require(current == dict(previous, **{KEY: DEPS}), 'PREFLIGHT_ENVIRONMENT_DELTA_INVALID')
    return {'rootFilesystemUnchanged': True, 'startupAuthRendererUnchanged': True,
            'environmentAddition': {KEY: DEPS}}


def helper(repo):
    path = repo / 'world-simulation-shorts-engine/recovery/studio-cold-start-v2/ci_image.py'
    spec = importlib.util.spec_from_file_location('_preserved_registry_read', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publish(args):
    image = authority()
    require(args.image == image, 'PREFLIGHT_UNIQUE_TAG_REQUIRED')
    baseline = json.loads(args.baseline_result.read_text())
    result = json.loads(args.result.read_text())
    for item, mode, expected_names in (
            (baseline, 'baseline', ['existing-root']),
            (result, 'candidate', ['inherited-root', 'decimal-2gb', 'binary-2gib', 'decimal-3gb'])):
        require(item.get('schema') == 'WORLD_ENGINE_GPU_PREFLIGHT_CPU_SUITE_V1'
                and item.get('mode') == mode and item.get('status') == 'PASS'
                and item.get('gpuExecuted') is False and item.get('renderExecuted') is False
                and item.get('fullPreflightRepeated') is False
                and item.get('automaticRetries') == 0,
                'PREFLIGHT_FOCUSED_CPU_PASS_REQUIRED')
        cases = item.get('cases', [])
        require([row.get('name') for row in cases] == expected_names
                and all(row.get('status') == 'PASS' and row.get('attempt') == 1
                        and row.get('exitCode') == 0 and row.get('exited') is True for row in cases)
                and len(item.get('removedOwnedContainers', [])) == len(cases),
                'PREFLIGHT_ALL_FOCUSED_CASES_REQUIRED')
    base = json.loads(execute(['docker', 'image', 'inspect', BASE]))[0]
    candidate = json.loads(execute(['docker', 'image', 'inspect', image]))[0]
    require(baseline.get('imageConfigDigest') == base['Id']
            and result.get('imageConfigDigest') == candidate['Id'], 'PREFLIGHT_TESTED_IMAGE_MISMATCH')
    facts = config_only(base, candidate)
    registry = helper(args.repo)
    tag = image.split(':', 1)[1]
    require(registry.registry_get(tag)['status'] == 404, 'PREFLIGHT_EXISTING_TAG_FORBIDDEN')
    token, actor = os.environ.get('GH_TOKEN', ''), os.environ.get('GITHUB_ACTOR', '')
    require(token and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?', actor),
            'PREFLIGHT_REGISTRY_AUTH_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='world-engine-preflight-registry-') as directory:
        env = dict(os.environ, DOCKER_CONFIG=directory)
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        login = subprocess.run(['docker', 'login', 'ghcr.io', '--username', actor, '--password-stdin'],
                               input=token, capture_output=True, text=True, env=env, timeout=60)
        require(login.returncode == 0, 'PREFLIGHT_REGISTRY_LOGIN_FAILED')
        execute(['docker', 'push', image], env=env)
    remote = registry.registry_get(tag)
    require(remote.get('status') == 200 and remote['configDigest'] == candidate['Id'],
            'PREFLIGHT_PUBLISHED_IMAGE_MISMATCH')
    immutable = registry.registry_get(remote['digest'])
    require(immutable == remote, 'PREFLIGHT_DIGEST_READBACK_FAILED')
    output = {'status': 'GPU_PREFLIGHT_FIX_CPU_VERIFIED', 'imageTag': image,
              'imageDigest': remote['digest'], 'imageConfigDigest': candidate['Id'],
              'baseImageDigest': BASE.split('@')[1], 'sourceCommit': os.environ['GITHUB_SHA'],
              'remoteTagAndDigestReadback': True, 'gcubeSharedMemoryGBRequired': 3,
              'gpuExecuted': False, 'renderExecuted': False, **facts}
    print('WORLD_ENGINE_PREFLIGHT_IMAGE_RESULT=' + json.dumps(output, sort_keys=True))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('```json\n' + json.dumps(output, indent=2) + '\n```\n')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    sub.add_parser('prepare')
    publish_parser = sub.add_parser('publish')
    publish_parser.add_argument('--image', required=True)
    publish_parser.add_argument('--repo', type=Path, required=True)
    publish_parser.add_argument('--baseline-result', type=Path, required=True)
    publish_parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            image = authority()
            with open(os.environ['GITHUB_ENV'], 'a') as stream:
                stream.write('CANDIDATE_IMAGE=' + image + '\n')
            print(json.dumps({'candidateImage': image, 'gpuExecuted': False}))
        else:
            publish(args)
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'PREFLIGHT_[A-Z0-9_]+', code):
            code = 'PREFLIGHT_IMAGE_OPERATION_BLOCKED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'gpuExecuted': False}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
