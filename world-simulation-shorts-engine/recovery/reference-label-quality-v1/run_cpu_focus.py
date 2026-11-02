#!/usr/bin/env python3
"""Run only new quality integration checks in the pinned parent, without a build/GPU."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = 'world-simulation-shorts-engine/recovery/reference-label-quality-v1'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
PARENT = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf'

def main():
    repo = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    out = Path(os.environ['RUNNER_TEMP']) / 'quality-cpu-evidence'
    out.mkdir(mode=0o777); out.chmod(0o777)
    seal = json.loads((repo / HERE / 'SEALED_OVERLAY.json').read_text())
    assert seal['sourceBaseCommit'] == 'f276f19fc3c61c77e17e3683a8b8302523a379dc'
    mounts = []
    for row in seal['overlay']:
        file = repo / row['path']; raw = file.read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
        mounts += ['--mount', f'type=bind,src={file},dst={IMAGE_ROOT}/{row["path"]},readonly']
    mounts += ['--mount', f'type=bind,src={repo / HERE},dst={IMAGE_ROOT}/{HERE},readonly',
               '--mount', f'type=bind,src={out},dst=/out']
    reused = json.loads((repo / HERE / 'evidence/UNIT_PASS_REUSE.json').read_text())
    for row in reused['files']:
        assert hashlib.sha256((repo / row['path']).read_bytes()).hexdigest() == row['sha256'], 'UNIT_PASS_INVALIDATED'
    print('UNCHANGED_NEW_UNIT_CHECKS_REUSED_FROM_41530820590', flush=True)
    tests = IMAGE_ROOT + '/' + HERE + '/tests/'
    command = '\n'.join([
        'set -euo pipefail',
        'mkdir -m 700 /workspace/quality-private',
        'node ' + tests + 'test_quality_scene.mjs --private-root=/workspace/quality-private --public-root=/out --output=/out/scene',
        'node ' + tests + 'pixel_quality.mjs --prepared=/out/scene/PREPARED.json --output=/out/pixels --deps-root=/opt/rtx-package/repo/cinematic-world-map --chromium=/usr/bin/chromium',
    ])
    args = ['docker', 'run', '--rm', '--name', 'we-quality-cpu-' + os.environ['GITHUB_RUN_ID'],
            '--network', 'none', '--read-only', '--user', '1000:1000', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--shm-size', '1g',
            '--tmpfs', '/tmp:rw,nosuid,size=512m',
            '--tmpfs', '/home/engine:rw,nosuid,uid=1000,gid=1000,mode=0700,size=128m',
            '--tmpfs', '/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=1536m',
            '-e', 'NVIDIA_VISIBLE_DEVICES=void', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map', *mounts,
            '--entrypoint', '/bin/bash', PARENT, '-c', command]
    result = subprocess.run(args, timeout=600)
    # Only public new test evidence; private working sources stay inside disposable tmpfs.
    subprocess.run(['sudo', 'chmod', '-R', 'a+rX', str(out)], check=True)
    summary = {'schema':'WORLD_ENGINE_QUALITY_CPU_WORKFLOW_V1',
               'status':'PASS' if result.returncode == 0 else 'FAIL',
               'sourceCommit':os.environ['GITHUB_SHA'], 'sourceBaseCommit':seal['sourceBaseCommit'],
               'overlay':seal['overlay'], 'scene':seal['scene'], 'parentImage':PARENT,
               'exitCode':result.returncode, 'gpuStarts':0, 'imageBuilds':0, 'imagePublications':0,
               'oldPASSReruns':0, 'fullVideoRenders':0,
               'scope':'NEW_INPUT_AND_CHANGED_LABEL_MAP_CONSUMERS_ON_CPU_SWIFTSHADER',
               'referenceVideoQuality':'NOT_RUN'}
    (out / 'CPU_WORKFLOW_RESULT.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print('QUALITY_CPU_RESULT=' + json.dumps(summary), flush=True)
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())
