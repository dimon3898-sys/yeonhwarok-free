"""Common image admission, immutable promotion, and deployment digest gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / 'REQUIRED_FIXES.json').read_bytes())
sha = lambda raw: hashlib.sha256(raw).hexdigest()

def need(value, code):
    if not value:
        raise RuntimeError(code)

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def policy_sha():
    # A policy or executable guard change invalidates old approval receipts.
    return sha(b''.join((HERE / name).read_bytes() for name in ('REQUIRED_FIXES.json', 'probe.py', 'control.py', 'command.py')))

def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180, **kwargs).stdout.strip()

def inspect_image(image, docker='docker'):
    return json.loads(run([docker, 'image', 'inspect', image]))[0]

def verify(image, evidence, docker='docker', mounts=(), reuse=True):
    info = inspect_image(image, docker)
    image_id = info['Id']
    key = re.sub(r'[^a-zA-Z0-9]', '', image_id)
    receipt = Path(evidence) / ('admission-' + key + '.json')
    if reuse and not mounts and receipt.exists():
        prior = json.loads(receipt.read_bytes())
        if prior.get('status') == 'PASS' and prior.get('policySHA256') == policy_sha() and prior.get('imageId') == image_id:
            return prior
    command = [docker, 'run', '--rm', '-i', '--network', 'none', '--read-only', '--user', '1000:1000',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
               '-e', 'NVIDIA_VISIBLE_DEVICES=void', '-e', 'PYTHONDONTWRITEBYTECODE=1',
               '--mount', 'type=bind,src=' + str(HERE / 'probe.py') + ',dst=/release-probe.py,readonly']
    for source, target in mounts:
        command += ['--mount', 'type=bind,src=' + str(Path(source).resolve()) + ',dst=' + target + ',readonly']
    command += ['--entrypoint', '/usr/bin/python3', image, '-I', '-B', '/release-probe.py']
    process = subprocess.run(command, input=json.dumps({'policy': POLICY, 'entrypoint': info['Config'].get('Entrypoint')}), text=True, capture_output=True, timeout=180)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        result = {'status': 'FAIL', 'code': 'ACTUAL_IMAGE_PROBE_OUTPUT_INVALID'}
    if process.returncode and result.get('status') == 'PASS':
        result = {'status': 'FAIL', 'code': 'ACTUAL_IMAGE_PROBE_EXIT_INVALID'}
    result.update(imageId=image_id, policySHA256=policy_sha(), imageReference=image,
                  GPUExecutions=0, rendererExecutions=0, oldPassReruns=0,
                  deploymentApproved=False, candidateOnly=True)
    # Fault injection receipts must never replace the genuine image admission.
    path = receipt if not mounts else Path(evidence) / ('injected-' + sha(json.dumps(mounts, default=str).encode())[:12] + '.json')
    write(path, result)
    need(result['status'] == 'PASS', result.get('code', 'IMAGE_ADMISSION_FAILED'))
    return result

def promote(image, evidence, docker='docker'):
    admission = verify(image, evidence, docker)
    info = inspect_image(image, docker)
    need(info['Id'] == admission['imageId'], 'IMAGE_CHANGED_AFTER_ADMISSION')
    prefix = POLICY['imageRepository'] + '@sha256:'
    digests = [v for v in info.get('RepoDigests', []) if v.startswith(prefix)]
    need(len(digests) == 1, 'PUBLISHED_DIGEST_REQUIRED')
    pinned = digests[0]
    run([docker, 'pull', pinned])
    confirmed = inspect_image(pinned, docker)
    need(confirmed['Id'] == admission['imageId'], 'REMOTE_DIGEST_IMAGE_MISMATCH')
    result = {'schema': 'WORLD_ENGINE_RELEASE_APPROVAL_V1', 'status': 'PASS',
              'imageReference': image, 'imageByDigest': pinned, 'digest': pinned.split('@')[1],
              'imageId': admission['imageId'], 'policySHA256': policy_sha(),
              'admission': admission, 'deploymentApproved': True,
              'candidateOnly': False, 'GPUExecutions': 0, 'actualNvidiaRenderVerified': False}
    write(Path(evidence) / 'RELEASE_APPROVAL.json', result)
    return result

def deployment(approval, config):
    need(approval.get('status') == 'PASS' and approval.get('deploymentApproved') is True and approval.get('policySHA256') == policy_sha(), 'CURRENT_RELEASE_APPROVAL_REQUIRED')
    digest = approval['digest']
    need(re.fullmatch(r'sha256:[a-f0-9]{64}', digest), 'RELEASE_DIGEST_INVALID')
    need(config.get('imageTag') == approval['imageReference'] and config.get('digest') == digest, 'DEPLOYMENT_IMAGE_MISMATCH')
    env = config.get('environment', config.get('environmentChanges', {}))
    need(env.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') == env.get('WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST') == digest, 'DEPLOYMENT_DIGEST_MISMATCH')
    need(config.get('observedStatus') == 'Stopped', 'STOPPED_WORKLOAD_REQUIRED')
    return {'status': 'PASS', 'digest': digest, 'policySHA256': policy_sha(), 'GPUStartAuthorized': False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('operation', choices=['verify', 'promote', 'deployment'])
    p.add_argument('--image'); p.add_argument('--docker', default='docker')
    p.add_argument('--evidence', required=True); p.add_argument('--config'); p.add_argument('--approval')
    a = p.parse_args()
    try:
        if a.operation == 'deployment':
            value = deployment(json.loads(Path(a.approval).read_bytes()), json.loads(Path(a.config).read_bytes()))
            write(Path(a.evidence) / 'DEPLOYMENT_GATE.json', value)
        else:
            value = globals()[a.operation](a.image, a.evidence, a.docker)
        print(json.dumps(value))
    except Exception as error:
        code = str(error) if isinstance(error, RuntimeError) else 'RELEASE_CONTROL_' + type(error).__name__.upper()
        write(Path(a.evidence) / 'BLOCKED.json', {'status': 'FAIL', 'code': code, 'GPUExecutions': 0, 'deploymentApproved': False})
        print(code, file=sys.stderr)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
