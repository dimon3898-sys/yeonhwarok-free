"""Manual-only Actions orchestrator. No publish, GPU, renderer or retry commands.

Importing this module does nothing. Local prep tests inject no Docker calls.
Only fixed JSON evidence is emitted; raw Docker output/configs stay private.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = 'dimon3898-sys/yeonhwarok-free'
BRANCH = 'refs/heads/recovery/g1-capture-diagnostic-contract-20261028'
PARENT_DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
REGISTRY_REPO = 'dimon3898-sys/world-simulation-shorts-engine'
PARENT = 'ghcr.io/' + REGISTRY_REPO + '@' + PARENT_DIGEST
SOURCE_COMMIT = 'd259e61c96e83a97a8b97e797670786a434a240d'
PROFILE = 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/profile_contract.mjs'
PROFILE_SHA = 'f55758af58a7c8724bddc097f05586b6d4cfdfa81133fa093636e335bca171c5'
INSTALLED = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
DOCKER = ['docker', '--host=unix:///var/run/docker.sock']
RESERVE = 8 * 1024**3
SAFE_FILES = {'PREFLIGHT.json', 'PULL.json', 'STAGE_RECEIPT.json', 'BUILD.json',
              'CONNECTION_VERIFY.json', 'IMAGE_SCOPE.json', 'FAILURE.json', 'RUN_STATE.json'}

def require(value, code):
    if not value: raise RuntimeError(code)

def digest(data): return hashlib.sha256(data).hexdigest()

def write(path, value):
    path = Path(path)
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    require(len(raw) <= 256 * 1024, 'EVIDENCE_FILE_TOO_LARGE')
    tmp = path.with_name('.' + path.name + '.tmp')
    with tmp.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)

def docker_env():
    env = dict(os.environ)
    for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        env.pop(key, None)
    env.pop('BUILDX_BUILDER', None)
    env['DOCKER_BUILDKIT'] = '1'
    return env

def run(args, *, seconds=60):
    # Never echo arbitrary command output, env, credentials or Docker Config.Env.
    result = subprocess.run(args, env=docker_env(), stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=seconds)
    require(result.returncode == 0, 'COMMAND_EXIT_' + str(result.returncode))
    require(len(result.stdout) <= 2 * 1024**2, 'COMMAND_OUTPUT_TOO_LARGE')
    return result.stdout

def validate_dispatch(env, cost, head):
    expected = {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
        'GITHUB_REPOSITORY': REPO, 'GITHUB_REF': BRANCH, 'GITHUB_RUN_ATTEMPT': '1',
        'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64',
        'SIGNAL_APPROVAL': 'BUILD_SURFACE_CANDIDATE_LOCAL_ONLY', 'ZERO_COST_CONFIRMED': 'true'}
    require(all(env.get(k) == v for k, v in expected.items()), 'MANUAL_FREE_RUNNER_APPROVAL_REQUIRED')
    require(re.fullmatch(r'[0-9a-f]{40}', env.get('APPROVED_HEAD_SHA', ''))
            and head == env['APPROVED_HEAD_SHA'] == env.get('GITHUB_SHA'), 'REVIEWED_WORKFLOW_HEAD_REQUIRED')
    require(re.fullmatch(r'[0-9]+', env.get('GITHUB_RUN_ID', '')), 'ACTIONS_RUN_ID_REQUIRED')
    require(cost.get('status') == 'SATISFIED_USER_ATTESTED'
            and type(cost.get('actionsBudgetUSD')) is int and cost['actionsBudgetUSD'] == 0
            and cost.get('budgetScope') == 'ENTIRE_ACCOUNT'
            and cost.get('stopUsageWhenBudgetLimitReached') is True
            and cost.get('paymentMethodRegistered') is False, 'HISTORICAL_COST_CONTROLS_NOT_SATISFIED')

def capacity(driver, compressed, free):
    require(driver == 'overlay2', 'COPY_ON_WRITE_OVERLAY2_REQUIRED_VFS_FORBIDDEN')
    need = compressed * 4 + RESERVE
    require(free >= need, 'INSUFFICIENT_ESTIMATED_DOCKER_CAPACITY')
    return need

def claim(work, name, prerequisite=None):
    if prerequisite:
        row = json.loads((work / 'evidence' / prerequisite).read_text())
        accepted = {'PREPARED_NOT_BUILT'} if prerequisite == 'STAGE_RECEIPT.json' else {'PASS'}
        require(row.get('status') in accepted, 'PREVIOUS_STAGE_NOT_PASS')
    require(not (work / 'evidence/FAILURE.json').exists(), 'ATTEMPT_ALREADY_BLOCKED')
    # Before the command, claim the stage. A failure cannot silently retry it.
    with (work / 'attempts' / name).open('x') as stream: stream.write('1\n')

def registry_manifest():
    query = urllib.parse.urlencode({'service': 'ghcr.io', 'scope': 'repository:' + REGISTRY_REPO + ':pull'})
    with urllib.request.urlopen('https://ghcr.io/token?' + query, timeout=30) as response:
        token = json.load(response)['token']
    request = urllib.request.Request('https://ghcr.io/v2/' + REGISTRY_REPO + '/manifests/' + PARENT_DIGEST,
        headers={'Authorization': 'Bearer ' + token,
                 'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(1024 * 1024 + 1)
        returned = response.headers.get('Docker-Content-Digest')
    require(len(raw) <= 1024 * 1024 and returned == PARENT_DIGEST
            and 'sha256:' + digest(raw) == PARENT_DIGEST, 'REGISTRY_PARENT_IDENTITY_MISMATCH')
    obj = json.loads(raw)
    require(isinstance(obj.get('layers'), list) and obj['layers'], 'SINGLE_PLATFORM_PARENT_REQUIRED')
    require(all(type(x.get('size')) is int and x['size'] >= 0 for x in obj['layers']), 'LAYER_SIZE_INVALID')
    return obj

def preflight(work):
    work.mkdir(mode=0o700)
    for name in ('evidence', 'private', 'attempts', 'context-out'):
        (work / name).mkdir(mode=0o700)
    # Staging is root in an isolated CPU container; verifier UID1000 receives RO context.
    os.chmod(work / 'context-out', 0o755)
    claim(work, 'preflight')
    checkout = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    cost = json.loads((checkout / 'world-simulation-shorts-engine/recovery/capture-diagnostics-g2-v1/COST_EVIDENCE.json').read_text())
    head = run(['git', '-C', str(checkout), 'rev-parse', 'HEAD']).decode().strip()
    validate_dispatch(os.environ, cost, head)
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    require(event.get('repository', {}).get('private') is False, 'PUBLIC_REPOSITORY_REQUIRED')
    require(digest((checkout / PROFILE).read_bytes()) == PROFILE_SHA, 'APPROVED_PROFILE_BYTES_REQUIRED')
    info = json.loads(run(DOCKER + ['info', '--format', '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}}}']))
    write(work / 'evidence/PREFLIGHT.json', {'status': 'PENDING', 'driver': info['driver'],
        'dockerRoot': info['root'], 'freeBytes': shutil.disk_usage(info['root']).free,
        'parentDigest': PARENT_DIGEST, 'costControlsConfirmed': True})
    # Reject vfs before any registry/pull request. No daemon repair or image prune.
    capacity(info['driver'], 0, shutil.disk_usage(info['root']).free)
    manifest = registry_manifest()
    compressed = sum(x['size'] for x in manifest['layers'])
    free = shutil.disk_usage(info['root']).free
    write(work / 'evidence/PREFLIGHT.json', {'status': 'PENDING', 'driver': info['driver'],
        'dockerRoot': info['root'], 'freeBytes': free, 'compressedBytes': compressed,
        'estimatedRequiredBytes': compressed * 4 + RESERVE,
        'estimateIsNotMeasuredExpansion': True, 'parentDigest': PARENT_DIGEST})
    estimate = capacity(info['driver'], compressed, free)
    row = {'status': 'PASS', 'parentDigest': PARENT_DIGEST, 'reviewedHead': head,
        'sourceCommit': SOURCE_COMMIT, 'profileSHA256': PROFILE_SHA, 'driver': info['driver'],
        'dockerRoot': info['root'], 'freeBytes': free, 'compressedBytes': compressed,
        'estimatedRequiredBytes': estimate, 'estimateIsNotMeasuredExpansion': True,
        'costBasis': 'PUBLIC_STANDARD_UBUNTU_24_04_PLUS_FRESH_MANUAL_CONFIRMATION',
        'artifactUploads': False, 'packageWrites': False, 'gpuExecuted': False}
    write(work / 'evidence/PREFLIGHT.json', row)

def pull(work):
    claim(work, 'pull', 'PREFLIGHT.json')
    run(DOCKER + ['pull', PARENT], seconds=450)
    inspect = json.loads(run(DOCKER + ['image', 'inspect', PARENT]))[0]
    require(PARENT in inspect.get('RepoDigests', []), 'PULLED_PARENT_DIGEST_MISMATCH')
    write(work / 'private/parent-inspect.json', inspect)
    write(work / 'private/parent-config.json', inspect['Config'])
    (work / 'private/parent-config.json').chmod(0o644)
    pre = json.loads((work / 'evidence/PREFLIGHT.json').read_text())
    free = shutil.disk_usage(pre['dockerRoot']).free
    require(free >= RESERVE, 'INSUFFICIENT_DOCKER_RESERVE_AFTER_PULL')
    write(work / 'evidence/PULL.json', {'status': 'PASS', 'parentDigest': PARENT_DIGEST,
        'parentImageId': inspect['Id'], 'remainingFreeBytes': free, 'pullAttempts': 1})

def stage(work):
    claim(work, 'stage', 'PULL.json')
    checkout = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    args = DOCKER + ['run', '--rm', '--network=none', '--read-only', '--user', str(os.getuid()) + ':' + str(os.getgid()),
        '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--mount', 'type=bind,src=' + str(HERE / 'package_candidate.py') + ',dst=/tool.py,readonly',
        '--mount', 'type=bind,src=' + str(checkout / PROFILE) + ',dst=/candidate.mjs,readonly',
        '--mount', 'type=bind,src=' + str(work / 'private') + ',dst=/input,readonly',
        '--mount', 'type=bind,src=' + str(work / 'context-out') + ',dst=/out',
        '--entrypoint', '/usr/bin/python3', PARENT, '-I', '-B', '/tool.py', 'stage',
        '--parent-root', INSTALLED, '--candidate', '/candidate.mjs',
        '--context', '/out/context', '--image-config', '/input/parent-config.json']
    run(args, seconds=120)
    context = work / 'context-out/context'
    receipt = json.loads((context / 'STAGE_RECEIPT.json').read_text())
    require(receipt.get('status') == 'PREPARED_NOT_BUILT', 'STAGE_NOT_PREPARED')
    write(work / 'evidence/STAGE_RECEIPT.json', receipt)

def validate_build_context(context):
    # Reject extra build instructions/files BEFORE the one authorized build.
    spec = importlib.util.spec_from_file_location('_surface_fixed_packager', HERE / 'package_candidate.py')
    package = importlib.util.module_from_spec(spec); spec.loader.exec_module(package)
    receipt = package.read_json(context / 'STAGE_RECEIPT.json')
    require(receipt.get('status') == 'PREPARED_NOT_BUILT'
            and receipt.get('parentImageDigest') == PARENT_DIGEST
            and receipt.get('sourceCommit') == SOURCE_COMMIT, 'BUILD_CONTEXT_IDENTITY_INVALID')
    require(package.read_file(context / 'Dockerfile').decode()
            == package.expected_dockerfile(receipt['entrypoint']), 'BUILD_INSTRUCTIONS_CHANGED')
    overlay = context / 'overlay'
    require(not any(p.is_symlink() for p in context.rglob('*')), 'BUILD_CONTEXT_SYMLINK_FORBIDDEN')
    actual = {str(p.relative_to(overlay)) for p in overlay.rglob('*') if p.is_file()}
    require(actual == package.OVERLAY_FILES and set(receipt.get('overlayFiles', {})) == actual,
            'BUILD_OVERLAY_SCOPE_CHANGED')
    for name, row in receipt['overlayFiles'].items():
        raw = package.read_file(overlay / name)
        require(row == {'bytes': len(raw), 'sha256': digest(raw)}, 'BUILD_OVERLAY_BYTES_CHANGED')
    require(digest(package.read_file(overlay / PROFILE)) == PROFILE_SHA, 'BUILD_PROFILE_BYTES_CHANGED')
    require(receipt['entrypoint'] == package.expected_entrypoint(receipt['runtimeManifestSHA256'],
            receipt['startupManifestSHA256']), 'BUILD_ENTRYPOINT_CHANGED')

def build(work):
    claim(work, 'build', 'STAGE_RECEIPT.json')
    pre = json.loads((work / 'evidence/PREFLIGHT.json').read_text())
    require(shutil.disk_usage(pre['dockerRoot']).free >= RESERVE, 'INSUFFICIENT_DOCKER_RESERVE_BEFORE_BUILD')
    tag = 'world-engine-surface-candidate:d259e61c96e8-' + os.environ['GITHUB_RUN_ID'] + '-a1'
    context = work / 'context-out/context'
    validate_build_context(context)
    iidfile = work / 'private/candidate.iid'
    run(DOCKER + ['build', '--network=none', '--pull=false', '--no-cache',
        '--iidfile', str(iidfile), '-t', tag, str(context)], seconds=270)
    image = json.loads(run(DOCKER + ['image', 'inspect', tag]))[0]
    require(iidfile.read_text().strip() == image['Id'], 'BUILT_IMAGE_ID_MISMATCH')
    write(work / 'private/candidate-inspect.json', image)
    write(work / 'private/candidate-config.json', image['Config'])
    (work / 'private/candidate-config.json').chmod(0o644)
    write(work / 'evidence/BUILD.json', {'status': 'PASS', 'candidateTag': tag,
        'candidateImageID': image['Id'], 'parentDigest': PARENT_DIGEST,
        'buildAttempts': 1, 'pushed': False, 'gpuExecuted': False})

def verify(work):
    claim(work, 'verify', 'BUILD.json')
    b = json.loads((work / 'evidence/BUILD.json').read_text())
    before = json.loads((work / 'private/parent-inspect.json').read_text())
    after = json.loads((work / 'private/candidate-inspect.json').read_text())
    parent_layers = before['RootFS']['Layers']; candidate_layers = after['RootFS']['Layers']
    require(candidate_layers[:len(parent_layers)] == parent_layers
            and len(candidate_layers) == len(parent_layers) + 4, 'ONLY_FOUR_FILE_COPY_LAYERS_REQUIRED')
    output_dir = work / 'verify-out'
    output_dir.mkdir(mode=0o777); output_dir.chmod(0o777)
    run(DOCKER + ['run', '--rm', '--network=none', '--read-only', '--user', '1000:1000',
        '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--mount', 'type=bind,src=' + str(HERE / 'package_candidate.py') + ',dst=/tool.py,readonly',
        '--mount', 'type=bind,src=' + str(work / 'private/parent-config.json') + ',dst=/parent-config.json,readonly',
        '--mount', 'type=bind,src=' + str(work / 'private/candidate-config.json') + ',dst=/candidate-config.json,readonly',
        '--mount', 'type=bind,src=' + str(work / 'context-out/context') + ',dst=/context,readonly',
        '--mount', 'type=bind,src=' + str(output_dir) + ',dst=/result',
        '--entrypoint', '/usr/bin/python3', b['candidateImageID'], '-I', '-B', '/tool.py', 'verify',
        '--root', INSTALLED, '--context', '/context', '--parent-config', '/parent-config.json',
        '--candidate-config', '/candidate-config.json', '--output', '/result/CONNECTION_VERIFY.json'], seconds=90)
    output = output_dir / 'CONNECTION_VERIFY.json'
    require(output.is_file() and not output.is_symlink() and output.stat().st_size <= 65536, 'VERIFY_OUTPUT_INVALID')
    result = json.loads(output.read_text())
    require(result.get('status') == 'PASS', 'CONNECTION_VERIFY_NOT_PASS')
    write(work / 'evidence/CONNECTION_VERIFY.json', result)
    current = json.loads(run(DOCKER + ['image', 'inspect', PARENT]))[0]
    require(current['Id'] == before['Id'] and current['Config'] == before['Config']
            and current['RootFS'] == before['RootFS'], 'PARENT_IMAGE_CHANGED')
    write(work / 'evidence/IMAGE_SCOPE.json', {'status': 'PASS', 'parentPreserved': True,
        'parentImageID': before['Id'], 'candidateImageID': after['Id'],
        'parentLayerCount': len(parent_layers), 'candidateLayerCount': len(candidate_layers),
        'additionalCopyLayers': 4, 'priorPassTestsRerun': False, 'gpuExecuted': False})

def collect(work):
    # No upload-artifact/cache, Git writes or package publication. Logs alone
    # preserve a bounded safe bundle for subsequent authorized Git backup.
    entries = []; total = 0
    for name in sorted(SAFE_FILES):
        p = work / 'evidence' / name
        if not p.exists(): continue
        require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 256 * 1024, 'SAFE_EVIDENCE_INVALID')
        raw = p.read_bytes(); json.loads(raw)
        total += len(raw); require(total <= 512 * 1024, 'SAFE_BUNDLE_TOO_LARGE')
        entries.append({'name': name, 'sha256': digest(raw), 'bytes': len(raw),
                        'base64': base64.b64encode(raw).decode()})
    bundle = json.dumps({'schema': 'WORLD_ENGINE_SURFACE_ACTIONS_LOG_EVIDENCE_V1', 'files': entries}, separators=(',', ':'))
    for i in range(0, len(bundle), 3000): print('SURFACE_SAFE_EVIDENCE_CHUNK=' + bundle[i:i + 3000])
    print('SURFACE_SAFE_EVIDENCE_FILES=' + str(len(entries)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['preflight', 'pull', 'stage', 'build', 'verify', 'collect'])
    parser.add_argument('--work', required=True)
    args = parser.parse_args()
    # Manual workflow only. Local module imports/tests cannot accidentally build.
    workspace = Path(os.environ.get('GITHUB_WORKSPACE', '/INVALID')).resolve()
    work = (workspace / args.work).resolve()
    require(args.work == 'surface-candidate-work' and work.parent == workspace, 'FIXED_ACTIONS_WORK_PATH_REQUIRED')
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'ACTIONS_EXECUTION_ONLY')
    if args.stage == 'collect':
        collect(work); return
    started = time.monotonic()
    try:
        globals()[args.stage](work)
        write(work / 'evidence/RUN_STATE.json', {'status': 'PASS', 'lastStage': args.stage,
            'elapsedSeconds': round(time.monotonic() - started, 3), 'retryCount': 0,
            'gpuExecuted': False, 'published': False})
    except Exception as error:
        if (work / 'evidence').is_dir():
            message = str(error)
            code = message if re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', message) else 'CANDIDATE_STAGE_FAILED'
            write(work / 'evidence/FAILURE.json', {'status': 'BLOCKED', 'stage': args.stage,
                'code': code, 'errorType': type(error).__name__, 'retryCount': 0,
                'buildAttempts': int((work / 'attempts/build').exists()), 'gpuExecuted': False})
        raise SystemExit('SURFACE_CANDIDATE_BLOCKED_' + args.stage.upper()) from None

if __name__ == '__main__': main()
