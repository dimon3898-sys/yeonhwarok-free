#!/usr/bin/env python3
"""G2 image packaging and bounded public evidence; no GPU execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

REPOSITORY = 'dimon3898-sys/yeonhwarok-free'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
DIGEST = 'sha256:bedf23b0315666ea702f719a509147d6c97dc27f7b529de918e2708f8928997f'
PARENT = IMAGE + '@' + DIGEST
OLD_ROOT = '/opt/world-engine-handoffs/studio-page-stage-v1/repo'
NEW_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
REL = 'world-simulation-shorts-engine/recovery/'
G1 = Path(REL + 'capture-diagnostics-g1-v1')
G2 = Path(REL + 'capture-diagnostics-g2-v1')
LIMIT = 5242880
BRANCH = 'recovery/g1-capture-diagnostic-contract-20261028'
SAFE_NAMES = {'COST_EVIDENCE.json', 'PREFLIGHT.json', 'STAGE_RECEIPT.json',
              'BUILD_CONTEXT.json', 'IMAGE_IDENTITY.json', 'image-config.json',
              'VALIDATION_RESULT.json', 'IMAGE_BROWSER_PROBE.json',
              'SAFE_CAPTURE_DIAGNOSTIC.json', 'SAFE_CAPTURE_SHA256SUMS',
              'RUNTIME_SOURCE_MANIFEST.json', 'STARTUP_MANIFEST.json',
              'GENERATED_SOURCE_MANIFEST.json', 'RELEASE_LOCK.json',
              'ARTIFACT_RECEIPT.json', 'EVIDENCE_INDEX.json', 'SHA256SUMS'}


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text_atomic(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=Path(path).parent, prefix='.g2-', delete=False) as handle:
        handle.write(text)
        temporary = handle.name
    os.replace(temporary, path)


def write(path, value):
    text_atomic(path, json.dumps(value, sort_keys=True, indent=2) + '\n')


def read(path):
    return json.loads(Path(path).read_text())


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def registry(reference):
    scope = 'repository:dimon3898-sys/world-simulation-shorts-engine:pull'
    url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': scope})
    with urllib.request.urlopen(url, timeout=45) as response:
        token = json.load(response)['token']
    request = urllib.request.Request('https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/' + reference,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()
        returned = response.headers.get('Docker-Content-Digest')
    require(returned == 'sha256:' + sha(data), 'REGISTRY_BODY_DIGEST_MISMATCH')
    return data, returned


def preflight():
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'WRONG_REPOSITORY')
    require(os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'AUTOMATIC_RETRY_FORBIDDEN')
    cost = read(G2 / 'COST_EVIDENCE.json')
    require(cost['status'] == 'SATISFIED_USER_ATTESTED'
            and cost['actionsBudgetUSD'] == 0 and cost['budgetScope'] == 'ENTIRE_ACCOUNT'
            and cost['stopUsageWhenBudgetLimitReached'] is True
            and cost['paymentMethodRegistered'] is False, 'COST_GATE_NOT_SATISFIED')
    raw, actual = registry(DIGEST)
    require(actual == DIGEST, 'PARENT_REGISTRY_DIGEST_MISMATCH')
    manifest = json.loads(raw)
    require(isinstance(manifest.get('layers'), list), 'PARENT_SINGLE_PLATFORM_MANIFEST_REQUIRED')
    compressed = sum(layer['size'] for layer in manifest['layers'])
    root = output('docker', 'info', '--format', '{{.DockerRootDir}}')
    free = shutil.disk_usage(root).free
    # Registry manifests do not expose expanded layer sizes. This is a declared
    # conservative capacity estimate, followed by actual free-space checks.
    estimated = compressed * 4 + 8 * 1024**3
    result = {'schema': 'WORLD_ENGINE_G2_DISK_PREFLIGHT_V1', 'parentDigest': actual,
              'manifestBytes': len(raw), 'layerCount': len(manifest['layers']),
              'compressedLayerBytes': compressed, 'dockerRootDir': root,
              'freeBytes': free, 'estimatedRequiredBytes': estimated,
              'estimateBasis': '4x compressed layers + 8 GiB stage/build reserve; estimate, not measured expansion',
              'daemonAccess': True, 'sharedCacheDeleted': False,
              'status': 'PASS' if free >= estimated else 'BLOCKED_CAPACITY_ESTIMATE',
              'gpuExecuted': False}
    write('g2-evidence/PREFLIGHT.json', result)
    require(free >= estimated, 'INSUFFICIENT_DOCKER_SPACE_BEFORE_PULL')
    print('G2_DISK_PREFLIGHT_PASS')


def construct():
    inspect = json.loads(output('docker', 'image', 'inspect', PARENT))[0]
    require(PARENT in inspect['RepoDigests'], 'PULLED_PARENT_IDENTITY_MISMATCH')
    config = inspect['Config']
    stage = read('out/STAGE_RECEIPT.json')
    require(stage['parentImageDigest'] == DIGEST and stage['sourceFiles'] == 353, 'STAGE_IDENTITY_MISMATCH')
    entry = config['Entrypoint']
    require(isinstance(entry, list) and sum(OLD_ROOT in part for part in entry) >= 3, 'PARENT_ENTRYPOINT_STRUCTURE_CHANGED')
    old_runtime, old_startup = stage['parentRuntimeManifestSHA256'], stage['parentStartupManifestSHA256']
    require(old_runtime in entry and old_startup in entry, 'PARENT_ENTRYPOINT_PINS_CHANGED')
    new_entry = [part.replace(OLD_ROOT, NEW_ROOT).replace(old_runtime, stage['runtimeManifestSHA256']).replace(old_startup, stage['startupManifestSHA256']) for part in entry]
    require(all(OLD_ROOT not in part for part in new_entry), 'OLD_ENTRYPOINT_ROOT_REMAINS')
    require(config.get('User', '') in ('', '0', 'root', '0:0'), 'PARENT_BUILD_USER_CHANGED')
    runtime = Path('out/runtime')
    runtime_bytes = sum(p.stat().st_size for p in runtime.rglob('*') if p.is_file())
    free = shutil.disk_usage(output('docker', 'info', '--format', '{{.DockerRootDir}}')).free
    require(free >= runtime_bytes * 3 + 2 * 1024**3, 'INSUFFICIENT_SPACE_FOR_CANDIDATE_LAYER')
    dockerfile = 'FROM ' + PARENT + '\nCOPY --chown=0:0 runtime/ ' + NEW_ROOT + '/\n'
    dockerfile += 'RUN find ' + NEW_ROOT + ' -type d -exec chmod 0755 {} + && find ' + NEW_ROOT + ' -type f -exec chmod 0644 {} +\n'
    dockerfile += 'ENTRYPOINT ' + json.dumps(new_entry) + '\n'
    if config.get('Cmd') is not None:
        dockerfile += 'CMD ' + json.dumps(config['Cmd']) + '\n'
    Path('out/Dockerfile').write_text(dockerfile)
    write('g2-evidence/BUILD_CONTEXT.json', {'status': 'CONSTRUCTED_NOT_YET_VALIDATED',
        'parentDigest': DIGEST, 'parentImageId': inspect['Id'], 'parentImageBytes': inspect['Size'],
        'runtimeBytes': runtime_bytes, 'freeBytesBeforeBuild': free,
        'runtimeManifestSHA256': stage['runtimeManifestSHA256'], 'startupManifestSHA256': stage['startupManifestSHA256'],
        'parentRoot': OLD_ROOT, 'candidateRoot': NEW_ROOT, 'sourceFiles': 353,
        'entrypointChange': 'root and manifest pins only', 'parentPreserved': True, 'gpuExecuted': False})
    print('G2_BUILD_CONTEXT_READY')


def identity(tag):
    inspect = json.loads(output('docker', 'image', 'inspect', tag))[0]
    parent = json.loads(output('docker', 'image', 'inspect', PARENT))[0]
    cfg, base = inspect['Config'], parent['Config']
    for key in ['Env', 'Cmd', 'User', 'WorkingDir', 'ExposedPorts', 'Healthcheck']:
        require(cfg.get(key) == base.get(key), 'PARENT_CONFIG_CHANGED_' + key.upper())
    filtered = {key: cfg.get(key) for key in ['Entrypoint', 'Cmd', 'User', 'WorkingDir', 'ExposedPorts']}
    write('out/image-config.json', filtered)
    write('g2-evidence/IMAGE_IDENTITY.json', {'schema': 'WORLD_ENGINE_G2_IMAGE_IDENTITY_V1',
        'imageTag': tag, 'testedImageId': inspect['Id'], 'parentImageId': parent['Id'],
        'parentDigest': DIGEST, 'configPreservedExceptEntrypointPins': True, 'gpuExecuted': False})


def collect(validation_outcome):
    target = Path('g2-evidence')
    target.mkdir(exist_ok=True)
    inputs = {G2 / 'COST_EVIDENCE.json': 'COST_EVIDENCE.json',
              Path('out/STAGE_RECEIPT.json'): 'STAGE_RECEIPT.json', Path('out/image-config.json'): 'image-config.json'}
    for source, name in inputs.items():
        if source.is_file():
            shutil.copyfile(source, target / name)
    root = Path('out/runtime') / REL
    for source in [root/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json',
                   root/'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json',
                   root/'studio-cold-start-v2/STARTUP_MANIFEST.json']:
        if source.is_file():
            shutil.copyfile(source, target / source.name)
    files = []
    for file in sorted(target.iterdir()):
        require(file.is_file() and not file.is_symlink() and file.name in SAFE_NAMES, 'UNEXPECTED_EVIDENCE_FILE')
        if file.name in {'SHA256SUMS', 'EVIDENCE_INDEX.json'}:
            continue
        data = file.read_bytes()
        require(len(data) <= 1024**2, 'EVIDENCE_FILE_TOO_LARGE')
        require(all(marker not in data for marker in (
            b'SYNTHETIC_SECRET_NOT_FOR_EXPORT', b'G2_PRIVATE_SENTINEL_NOT_FOR_EXPORT',
            b'private.invalid', b'ghp_', b'github_pat_')), 'UNSAFE_EVIDENCE_CONTENT')
        files.append({'path': file.name, 'bytes': len(data), 'sha256': sha(data)})
    require(sum(row['bytes'] for row in files) <= LIMIT - 65536, 'EVIDENCE_SIZE_LIMIT')
    index = {'schema': 'WORLD_ENGINE_G2_EVIDENCE_V1', 'runId': int(os.environ['GITHUB_RUN_ID']),
        'runURL': 'https://github.com/' + REPOSITORY + '/actions/runs/' + os.environ['GITHUB_RUN_ID'],
        'sourceCommit': os.environ['GITHUB_SHA'], 'G1PassReused': 40674899782,
        'validationOutcome': validation_outcome, 'gpuExecuted': False, 'gpuRootCause': 'UNKNOWN',
        'artifactRetentionDays': 1, 'maxUncompressedBytes': LIMIT, 'files': files}
    write(target / 'EVIDENCE_INDEX.json', index)
    rows = files + [{'path': 'EVIDENCE_INDEX.json', 'sha256': sha((target/'EVIDENCE_INDEX.json').read_bytes())}]
    # UID1000 image files may be read-only to the host runner. Replace only the
    # new checksum path atomically inside the writable task evidence directory.
    text_atomic(target/'SHA256SUMS', ''.join(row['sha256'] + '  ' + row['path'] + '\n' for row in rows))
    print('G2_SAFE_EVIDENCE_JSON=' + json.dumps(index, separators=(',', ':')))


def artifact(artifact_id, artifact_digest, artifact_url):
    require(artifact_id.isdigit() and len(artifact_digest.removeprefix('sha256:')) == 64, 'ARTIFACT_RECEIPT_REQUIRED')
    write('g2-evidence/ARTIFACT_RECEIPT.json', {'schema': 'WORLD_ENGINE_G2_ARTIFACT_RECEIPT_V1',
        'artifactId': int(artifact_id), 'artifactDigest': artifact_digest, 'artifactURL': artifact_url,
        'retentionDays': 1, 'uncompressedByteLimit': LIMIT})


def publish_receipt(tag):
    identity = read('g2-evidence/IMAGE_IDENTITY.json')
    actual_id = output('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
    require(actual_id == identity['testedImageId'], 'CANDIDATE_CHANGED_AFTER_VALIDATION')
    tag_raw, digest = registry(tag.rsplit(':', 1)[1])
    digest_raw, resolved = registry(digest)
    require(tag_raw == digest_raw and resolved == digest, 'PUBLISHED_TAG_DIGEST_MISMATCH')
    manifest = json.loads(tag_raw)
    require(manifest['config']['digest'] == actual_id, 'PUBLISHED_IMAGE_DIFFERS_FROM_TESTED_IMAGE')
    stage = read('out/STAGE_RECEIPT.json')
    lock = {'schema': 'WORLD_ENGINE_RELEASE_LOCK_V1', 'status': 'G2_IMAGE_PUBLISHED_CPU_VERIFIED',
        'sourceCommit': os.environ['GITHUB_SHA'], 'runURL': 'https://github.com/' + REPOSITORY + '/actions/runs/' + os.environ['GITHUB_RUN_ID'],
        'baselineImageDigest': DIGEST, 'candidateImageTag': tag, 'candidateImageDigest': digest,
        'testedImageId': actual_id, 'registryManifestBytes': len(tag_raw),
        'tagDigestBodyIdentical': True, 'manifestBodySHA256': sha(tag_raw),
        'runtimeManifestSHA256': stage['runtimeManifestSHA256'], 'startupManifestSHA256': stage['startupManifestSHA256'],
        'generatedSourceManifestSHA256': stage['generatedSourceManifestSHA256'], 'sourceFiles': 353,
        'sceneSHA256': None, 'gpuExecuted': False, 'gpuRootCause': 'UNKNOWN'}
    write('g2-evidence/RELEASE_LOCK.json', lock)
    print('G2_PUBLISHED_RELEASE_JSON=' + json.dumps(lock, separators=(',', ':')))


def backup(phase):
    # Synchronize before writing, and never force-push. The exact staged runtime
    # and image are outside Git; only bounded, allowlisted CPU evidence is copied.
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', BRANCH], check=True)
    subprocess.run(['git', 'checkout', '-B', BRANCH, 'origin/' + BRANCH], check=True)
    run = os.environ['GITHUB_RUN_ID']
    dest = G2 / 'evidence' / ('ci-' + run)
    dest.mkdir(parents=True, exist_ok=True)
    files = []
    for source in Path('g2-evidence').iterdir():
        require(source.is_file() and source.name in SAFE_NAMES and not source.is_symlink(), 'UNSAFE_BACKUP_PATH')
        require(source.stat().st_size <= 1024**2, 'BACKUP_FILE_SIZE_LIMIT')
        target = dest/source.name
        shutil.copyfile(source, target)
        files.append(target)
    require(sum(p.stat().st_size for p in files) <= LIMIT, 'BACKUP_TOTAL_SIZE_LIMIT')
    cp = read(G1/'CHECKPOINT.json')
    outcome = read('g2-evidence/EVIDENCE_INDEX.json')['validationOutcome']
    published = phase == 'published'
    gate_status = 'IMAGE_EVIDENCE_PASS_PENDING_WORKFLOW_COMPLETION' if published else ('VALIDATED_PENDING_PUBLICATION' if outcome == 'success' else 'BLOCKED')
    cp['gates']['G2'].update({'status': gate_status, 'imagePackaged': outcome == 'success',
        'reasons': ['Confirm whole Actions run completion before final G2 PASS'] if published else ['Publication pending' if outcome == 'success' else 'See G2 run evidence for exact failed step'],
        'evidenceDirectory': str(dest)})
    cp['cpuCostBasis']['artifactUpload'] = 'PASS'
    cp['G2Evidence'] = {'runURL': 'https://github.com/' + REPOSITORY + '/actions/runs/' + run,
        'sourceCommit': os.environ['GITHUB_SHA'], 'G1Reexecuted': False,
        'imageInternalValidation': outcome, 'artifact': read('g2-evidence/ARTIFACT_RECEIPT.json'),
        'gitEvidenceDirectory': str(dest), 'gpuExecuted': False, 'gpuRootCause': 'UNKNOWN'}
    if published:
        lock = read('g2-evidence/RELEASE_LOCK.json')
        cp['G2Evidence']['release'] = lock
        cp['runtimeClosureUpdate'].update({'status': 'PASS', 'expectedFileCount': 353,
            'actualFileCount': 353, 'expectedCountIsNotVerified': False, 'pinRegenerationRequired': False})
        cp['nextOwner'] = 'ASTRA'
        cp['nextAction'] = 'Confirm whole Actions run success and final Git backup before final G2 PASS. G3 GPU execution remains blocked; separate explicit approval is required before deployment or rendering.'
        write(G2/'RELEASE_LOCK.json', lock)
        files.append(G2/'RELEASE_LOCK.json')
    else:
        cp['nextOwner'] = 'ASTRA'
        cp['nextAction'] = 'Publish this exact validated candidate only after artifact and Git evidence backup succeed.' if outcome == 'success' else 'Inspect G2 failure and fix only affected step; do not rerun G0/G1.'
    write(G1/'CHECKPOINT.json', cp)
    checks = G1/'SHA256SUMS'
    lines = checks.read_text().splitlines()
    checks.write_text('\n'.join(sha((G1/'CHECKPOINT.json').read_bytes())+'  CHECKPOINT.json' if line.endswith('  CHECKPOINT.json') else line for line in lines)+'\n')
    files.extend([G1/'CHECKPOINT.json', checks])
    subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
    subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    subprocess.run(['git', 'add', '--', *map(str, files)], check=True)
    subprocess.run(['git', 'commit', '-m', 'Preserve G2 '+phase+' evidence for run '+run+' [skip ci]'], check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/'+BRANCH], check=True)
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', BRANCH], check=True)
    for file in files:
        remote = subprocess.check_output(['git', 'show', 'origin/'+BRANCH+':'+str(file)])
        require(remote == file.read_bytes(), 'NEW_G2_EVIDENCE_READBACK_MISMATCH')
    print('G2_NEW_EVIDENCE_BACKUP_PASS='+json.dumps({'commit': output('git', 'rev-parse', 'HEAD'), 'files': len(files), 'phase': phase}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preflight', 'construct', 'identity', 'collect', 'artifact', 'publish-receipt', 'backup'])
    parser.add_argument('--tag')
    parser.add_argument('--validation-outcome', default='failure')
    parser.add_argument('--artifact-id')
    parser.add_argument('--artifact-digest')
    parser.add_argument('--artifact-url')
    parser.add_argument('--phase', choices=['validated', 'published'])
    args = parser.parse_args()
    if args.mode == 'preflight': preflight()
    elif args.mode == 'construct': construct()
    elif args.mode == 'identity': identity(args.tag)
    elif args.mode == 'collect': collect(args.validation_outcome)
    elif args.mode == 'artifact': artifact(args.artifact_id, args.artifact_digest, args.artifact_url)
    elif args.mode == 'publish-receipt': publish_receipt(args.tag)
    elif args.mode == 'backup': backup(args.phase)
