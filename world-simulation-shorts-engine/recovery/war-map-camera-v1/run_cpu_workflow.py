#!/usr/bin/env python3
"""Run only the new WAR map/camera contracts in an existing immutable image."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.parse
import urllib.request
import zipfile

REPO = 'dimon3898-sys/yeonhwarok-free'
DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@' + DIGEST
IMAGE_ID = 'sha256:68732e51a2a72bdfd796edfdc19968de497833695062f6e2c56e83c72d9a11c3'
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
BRANCH = 'recovery/g1-capture-diagnostic-contract-20261028'
TASK = Path('world-simulation-shorts-engine/recovery/war-map-camera-v1')
PRIOR = Path('world-simulation-shorts-engine/recovery/war-scene-contract-v1')
EVIDENCE = Path('war-map-evidence')
ARTIFACT = Path('war-map-artifact')
WORKSPACE = Path('war-map-workspace')
LIMIT = 5 * 1024**2


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    path.chmod(0o644)


def read(path):
    return json.loads(Path(path).read_text())


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def command_output(*args):
    return subprocess.check_output(args, text=True).strip()


def preflight():
    require(os.environ['GITHUB_REPOSITORY'] == REPO, 'WRONG_REPOSITORY')
    require(os.environ['GITHUB_REF'] == 'refs/heads/' + BRANCH, 'WRONG_BRANCH')
    require(os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'AUTOMATIC_RETRY_FORBIDDEN')
    cost = read('world-simulation-shorts-engine/recovery/capture-diagnostics-g2-v1/COST_EVIDENCE.json')
    require(cost['status'] == 'SATISFIED_USER_ATTESTED' and cost['actionsBudgetUSD'] == 0
            and cost['budgetScope'] == 'ENTIRE_ACCOUNT' and cost['stopUsageWhenBudgetLimitReached'] is True
            and cost['paymentMethodRegistered'] is False, 'EXISTING_COST_EVIDENCE_REQUIRED')
    lock = read(TASK / 'INPUT_LOCK.json')
    require(lock['image'] == IMAGE and lock['imageDigest'] == DIGEST and lock['imageRoot'] == ROOT
            and lock['branch'] == BRANCH, 'CURRENT_TASK_INPUT_LOCK_MISMATCH')
    for name in ['INPUT_LOCK.json', 'CONTINUATION_SCOPE.json']:
        shutil.copyfile(TASK / name, EVIDENCE / name)
    scope = 'repository:dimon3898-sys/world-simulation-shorts-engine:pull'
    url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': scope})
    with urllib.request.urlopen(url, timeout=45) as response:
        token = json.load(response)['token']
    request = urllib.request.Request('https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/' + DIGEST,
        headers={'Authorization': 'Bearer ' + token,
                 'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
        returned = response.headers.get('Docker-Content-Digest')
    require(returned == DIGEST and 'sha256:' + sha(raw) == DIGEST, 'PINNED_REGISTRY_DIGEST_MISMATCH')
    manifest = json.loads(raw)
    require(isinstance(manifest.get('layers'), list), 'SINGLE_PLATFORM_MANIFEST_REQUIRED')
    compressed = sum(layer['size'] for layer in manifest['layers'])
    docker_root = command_output('docker', 'info', '--format', '{{.DockerRootDir}}')
    free = shutil.disk_usage(docker_root).free
    estimate = compressed * 4 + 8 * 1024**3
    result = {'schema': 'WORLD_ENGINE_WAR_MAP_CPU_PREFLIGHT_V1', 'imageDigest': DIGEST,
              'status': 'PASS' if free >= estimate else 'BLOCKED_CAPACITY_ESTIMATE',
              'manifestBytes': len(raw), 'compressedLayerBytes': compressed,
              'dockerRootDir': docker_root, 'freeBytes': free, 'estimatedRequiredBytes': estimate,
              'estimateBasis': '4x compressed layers +8GiB reserve; declared estimate, not measured expansion',
              'costEvidenceReused': True, 'sharedCacheDeleted': False, 'imageBuild': False, 'gpuExecuted': False}
    write(EVIDENCE / 'PREFLIGHT.json', result)
    require(free >= estimate, 'INSUFFICIENT_DOCKER_SPACE_BEFORE_PULL')
    print('WAR_MAP_DISK_PREFLIGHT_PASS')


def run_contract():
    inspected = json.loads(command_output('docker', 'image', 'inspect', IMAGE))[0]
    require(IMAGE in inspected['RepoDigests'] and inspected['Id'] == IMAGE_ID, 'PULLED_IMAGE_IDENTITY_MISMATCH')
    write(EVIDENCE / 'IMAGE_IDENTITY.json', {'schema': 'WORLD_ENGINE_WAR_MAP_IMAGE_IDENTITY_V1',
          'image': IMAGE, 'imageDigest': DIGEST, 'imageId': inspected['Id'], 'imageRoot': ROOT,
          'readOnly': True, 'network': 'none', 'uid': 1000, 'gpuExecuted': False,
          'newBuild': False, 'imagePublished': False, 'priorG2SuiteRerun': False})
    input_file = PRIOR / 'WORLD_ENGINE_WAR_SYNTHETIC_6S_VALIDATED.json'
    scene_file = PRIOR / 'evidence/validated/COMPILED_SCENE.json'
    require(sha(input_file.read_bytes()) == 'b845bc57e2c47363608880320cc63ef4289b2528e2d7e4a0af6d4c9290ca1751', 'FIXED_INPUT_BYTES_CHANGED')
    require(sha(scene_file.read_bytes()) == 'cbdd4f42548294157ea5cb2728819220ef2b089f81713352f7e374083b663d95', 'PRIOR_COMPILED_SCENE_BYTES_CHANGED')
    mounts = [(TASK / 'validate_map_camera.mjs', '/work/validate_map_camera.mjs', True),
              (input_file, '/work/input.json', True), (scene_file, '/work/compiled.json', True),
              (WORKSPACE, '/workspace', False), (EVIDENCE, '/evidence', False)]
    args = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', '4', '--memory', '8g',
            '--tmpfs', '/tmp:rw,nosuid,nodev,mode=1777']
    for source, destination, readonly in mounts:
        args += ['--mount', 'type=bind,src=' + str(source.resolve()) + ',dst=' + destination + (',readonly' if readonly else '')]
    args += ['--entrypoint', 'node', IMAGE, '/work/validate_map_camera.mjs', '--root', ROOT,
             '--input', '/work/input.json', '--scene', '/work/compiled.json', '--out', '/evidence',
             '--private-root', '/workspace/private', '--public-root', '/workspace/public']
    started = now()
    result = subprocess.run(args, capture_output=True, text=True)
    (EVIDENCE / 'PROCESS_STDOUT.log').write_text(result.stdout)
    (EVIDENCE / 'PROCESS_STDERR.log').write_text(result.stderr)
    write(EVIDENCE / 'PROCESS_EXIT.json', {'schema': 'WORLD_ENGINE_WAR_MAP_PROCESS_V1',
          'startedAt': started, 'finishedAt': now(), 'exitCode': result.returncode,
          'command': args, 'execution': 'EXISTING_PINNED_IMAGE_CPU_ONLY', 'gpuExecuted': False})
    print(result.stdout, end='')
    print(result.stderr, end='')
    require(result.returncode == 0, 'WAR_MAP_CAMERA_CONTRACT_PROCESS_FAILED')


def collect(args):
    # Called with sudo only to read the newly created UID1000 private checkpoint.
    # No credential, renderer cache, browser profile or external directory is read.
    target = ARTIFACT / 'evidence'
    target.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in sorted(EVIDENCE.iterdir()):
        require(path.is_file() and not path.is_symlink() and path.suffix in {'.json', '.log', '.txt'}, 'UNEXPECTED_PUBLIC_EVIDENCE_ENTRY')
        raw = path.read_bytes()
        require(len(raw) <= 1024**2, 'PUBLIC_EVIDENCE_FILE_TOO_LARGE')
        raw.decode('utf-8')
        require(all(marker not in raw for marker in [b'ghp_', b'github_pat_', b'-----BEGIN PRIVATE KEY']), 'PUBLIC_EVIDENCE_SECRET_MARKER')
        destination = target / path.name
        destination.write_bytes(raw)
        destination.chmod(0o644)
        rows.append({'path': path.name, 'bytes': len(raw), 'sha256': sha(raw)})
    resume = None
    private = WORKSPACE / 'private'
    if args.validation_outcome != 'success' and private.exists() and any(private.iterdir()):
        archive = ARTIFACT / 'resume.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for file in sorted(private.rglob('*')):
                require(not file.is_symlink(), 'PRIVATE_CHECKPOINT_SYMLINK_FORBIDDEN')
                if file.is_file():
                    require(file.suffix in {'.json', '.gz', '.png'}, 'UNEXPECTED_PRIVATE_CHECKPOINT_FILE')
                    z.write(file, str(file.relative_to(private)))
        archive.chmod(0o644)
        resume = {'path': 'resume.zip', 'bytes': archive.stat().st_size, 'sha256': sha(archive.read_bytes()),
                  'scope': 'New task private plan checkpoints and exact source crop only',
                  'restore': 'Restore to fresh /workspace/private owner1000; dirs0700 files0600; reuse passed-stage receipts.'}
        # Never lose actual failure evidence merely because the optional private
        # continuation archive exceeds the inherited 5MiB artifact budget.
        if sum(row['bytes'] for row in rows) + archive.stat().st_size + 65536 > LIMIT:
            archive.unlink()
            resume = {**resume, 'included': False, 'reason': 'OPTIONAL_RESUME_EXCEEDS_COMBINED_5MIB_LIMIT',
                      'primaryFailureEvidencePreserved': True}
        else:
            resume['included'] = True
    index = {'schema': 'WORLD_ENGINE_WAR_MAP_EVIDENCE_V1', 'runId': args.run_id,
             'runURL': 'https://github.com/' + REPO + '/actions/runs/' + args.run_id,
             'sourceCommit': args.source_commit, 'validationOutcome': args.validation_outcome,
             'gpuExecuted': False, 'newBuild': False, 'existingPassSuitesRerun': False,
             'artifactRetentionDays': 1, 'maxUncompressedBytes': LIMIT, 'files': rows,
             'failedStageResumeArchive': resume}
    write(target / 'EVIDENCE_INDEX.json', index)
    sums = rows + [{'path': 'EVIDENCE_INDEX.json', 'sha256': sha((target / 'EVIDENCE_INDEX.json').read_bytes())}]
    (target / 'SHA256SUMS').write_text(''.join(r['sha256'] + '  ' + r['path'] + '\n' for r in sums))
    total = sum(f.stat().st_size for f in ARTIFACT.rglob('*') if f.is_file())
    require(total <= LIMIT, 'COMBINED_SAFE_EVIDENCE_AND_RESUME_SIZE_LIMIT')
    print('WAR_MAP_EVIDENCE_INDEX=' + json.dumps(index, separators=(',', ':')))
    for file in sorted(target.iterdir()):
        raw = file.read_bytes()
        encoded = base64.b64encode(raw).decode()
        pieces = [encoded[i:i+16000] for i in range(0, len(encoded), 16000)] or ['']
        for number, piece in enumerate(pieces):
            print('WAR_MAP_EVIDENCE_CHUNK=' + json.dumps({'path': file.name, 'sha256': sha(raw),
                  'bytes': len(raw), 'part': number, 'parts': len(pieces), 'base64': piece}, separators=(',', ':')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['preflight', 'run', 'collect'])
    parser.add_argument('--validation-outcome')
    parser.add_argument('--run-id')
    parser.add_argument('--source-commit')
    args = parser.parse_args()
    {'preflight': preflight, 'run': run_contract, 'collect': lambda: collect(args)}[args.action]()


if __name__ == '__main__':
    main()
