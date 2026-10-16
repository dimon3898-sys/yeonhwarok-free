#!/usr/bin/env python3
"""Test-only camera hold proof against an immutable image; never builds or deploys."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/reference-visual-master-v2'
WORKFLOW = '.github/workflows/reference-visual-master-v2-camera-proof.yml'
BRANCH = 'development/reference-visual-master-v2-20261016'
SOURCE = 'e9feafc785fbd138cbac3ca4db090380968dc37e'
DIGEST = 'sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@' + DIGEST
MANIFEST_SHA = '28de18a52014ba56e91c31f91af40bc4f81c81b92e0fcf85bd83a651f7da3606'
CONFIG_DIGEST = 'sha256:1e8e13cdcbf072213a1bfb049b89996fa09c8f80da93c179d6da31a441a6073a'
SCRIPT_SHA = '454bbca943d83470d2b5259cac0e942866a838d059924eaa701163eecf903bd7'
AUDITOR_SHA = '7ac866bde978fc09338eb3d318e61c9914f1684308fbd6f4b5a7ba2aa30b541b'
PNG_NAMES = frozenset({'A_100.png', 'E_100.png'})
MAX_PNG_BYTES = 12 * 1024**2
MAX_JSON_BYTES = 1024**2
FROZEN_HELPERS = (
    NAMESPACE + '/ci.py',
    'world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1/ci.py',
    'world-simulation-shorts-engine/recovery/astra-gpu-activation-v1/ci.py',
    'world-simulation-shorts-engine/recovery/gcube-diagnostic-result-v1/ci.py',
    'world-simulation-shorts-engine/recovery/rtx-image-build-v1/pipeline.py',
    'world-simulation-shorts-engine/recovery/rtx-image-build-v1/image_checks.py',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, *, timeout=120, **kwargs):
    return subprocess.run(args, text=True, check=True, capture_output=True,
                          timeout=timeout, **kwargs).stdout


def frozen_manifest():
    evidence = json.loads((LANE / 'runs/38831714161-1/build.json').read_text())
    manifest = evidence.get('referenceManifest')
    if (evidence.get('imageDigest') != DIGEST or evidence.get('ciCommit') != SOURCE
            or evidence.get('referenceManifestSha256') != MANIFEST_SHA
            or not isinstance(manifest, dict) or manifest.get('sourceCommit') != SOURCE
            or hashlib.sha256((json.dumps(manifest, indent=2) + '\n').encode()).hexdigest() != MANIFEST_SHA):
        raise RuntimeError('IMMUTABLE_PUBLISHED_MANIFEST_REQUIRED')
    return manifest


def frozen_ci():
    """Configure a new imported object; no old file or source receipt is rewritten."""
    if sha(LANE / 'ci.py') != AUDITOR_SHA:
        raise RuntimeError('FROZEN_REFERENCE_AUDITOR_REQUIRED')
    manifest = frozen_manifest()
    spec = importlib.util.spec_from_file_location('_camera_immutable_reference_ci', LANE / 'ci.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate_manifest = lambda: copy.deepcopy(manifest)
    return module


def state_path():
    return Path(os.environ.get('RESULT_CI_STATE') or str(Path(os.environ['RUNNER_TEMP']) /
        ('reference-camera-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '.json')))


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_REFERENCE_CAMERA_FOLLOWUP_CI_V1', 'status': 'IN_PROGRESS',
            'ciCommit': os.environ.get('GITHUB_SHA'), 'imageSourceCommit': SOURCE,
            'immutableImage': IMAGE, 'referenceManifestSha256': MANIFEST_SHA,
            'testOnly': True, 'gpuExecuted': False, 'gCubeDeployed': False,
            'paidWorkExecuted': False, 'imageBuilt': False, 'imagePushed': False,
            'productionSourcesModified': False, 'finalModified': False,
            'videoQualityApproved': False, 'rawReferencePublished': False}


def save(value):
    target = state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, indent=2) + '\n').encode()
    if len(body) > MAX_JSON_BYTES:
        raise RuntimeError('BOUNDED_CAMERA_RESULT_REQUIRED')
    pending = target.with_suffix('.writing')
    pending.write_bytes(body)
    pending.replace(target)


def safe_log(value):
    value = str(value or '')[:65536]
    value = re.sub(r'(?i)(authorization|token|password|secret|credential)(\s*[:=]\s*)[^\s,}\"\']+',
                   r'\1\2[REDACTED]', value)
    value = re.sub(r'https?://[^\s]+', '[URL_REDACTED]', value)
    return re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+)', '[REDACTED]', value)


def verify_checkout_sources():
    manifest = frozen_manifest()
    expected = dict(manifest['repoDependencies'])
    expected.update({NAMESPACE + '/' + name: digest for name, digest in manifest['files'].items()})
    expected.update({NAMESPACE + '/' + name: digest for name, digest in manifest['testFiles'].items()})
    if len(expected) != 56:
        raise RuntimeError('FROZEN_FIFTY_SIX_SOURCE_HASHES_REQUIRED')
    for relative, digest in expected.items():
        path = REPO / relative
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise RuntimeError('IMMUTABLE_RENDERING_SOURCE_CHANGED')
    for relative in FROZEN_HELPERS:
        committed = subprocess.run(['git', 'show', SOURCE + ':' + relative], cwd=REPO,
                                   check=True, capture_output=True, timeout=30).stdout
        if (REPO / relative).read_bytes() != committed:
            raise RuntimeError('IMMUTABLE_AUDITOR_SOURCE_CHANGED')
    if sha(HERE / 'camera_hold_followup.mjs') != SCRIPT_SHA:
        raise RuntimeError('EXPLICIT_FOLLOWUP_SCRIPT_REQUIRED')
    return {'status': 'PASS', 'sourceCommit': SOURCE, 'frozenHashes': len(expected),
            'frozenAuditorFiles': len(FROZEN_HELPERS), 'referenceManifestSha256': MANIFEST_SHA}


def preflight():
    if (os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
            or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'
            or os.environ.get('RESULT_RUNNER_LABEL') != 'ubuntu-24.04'
            or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH
            or os.environ.get('GITHUB_EVENT_NAME') not in ('workflow_dispatch', 'push')):
        raise RuntimeError('OPT_IN_FREE_PUBLIC_STANDARD_RUNNER_REQUIRED')
    if not all(re.fullmatch('[1-9][0-9]*', os.environ[key]) for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')):
        raise RuntimeError('TRUSTED_RUN_ID_REQUIRED')
    if run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip() != os.environ['GITHUB_SHA']:
        raise RuntimeError('CHECKOUT_COMMIT_MISMATCH')
    if run(['git', 'status', '--porcelain'], cwd=REPO).strip():
        raise RuntimeError('CLEAN_CHECKOUT_REQUIRED')
    changed = run(['git', 'diff', '--name-only', SOURCE, 'HEAD'], cwd=REPO).splitlines()
    if any(path != WORKFLOW and not path.startswith(NAMESPACE + '/') for path in changed):
        raise RuntimeError('EXISTING_SOURCE_CHANGED')
    value = state()
    value.update(protection=verify_checkout_sources(),
                 builder=frozen_ci().helpers().require_space(),
                 freeRunner={'publicRepository': True, 'label': 'ubuntu-24.04', 'largerRunner': False},
                 changedFiles=changed, followupScriptSha256=SCRIPT_SHA)
    save(value)


def validate_image_facts(facts):
    config = facts.get('Config', {})
    labels = config.get('Labels', {})
    if (facts.get('Id') != CONFIG_DIGEST or facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64'
            or IMAGE not in facts.get('RepoDigests', [])
            or labels.get('world-engine.reference-v2.source-revision') != SOURCE
            or labels.get('world-engine.reference-v2.parent-digest') !=
                'sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae'):
        raise RuntimeError('IMMUTABLE_CAMERA_IMAGE_PROVENANCE_REQUIRED')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('IMMUTABLE_PARENT_ENTRYPOINT_REQUIRED')
    if {row.partition('=')[0] for row in config.get('Env', [])} & {
            'GH_TOKEN', 'GITHUB_TOKEN', 'DOCKER_AUTH_CONFIG', 'GITHUB_AUTHORIZATION'}:
        raise RuntimeError('CREDENTIAL_ENV_IN_IMAGE')
    return {'status': 'PASS', 'manifestDigest': DIGEST, 'configDigest': facts['Id'],
            'imageSourceCommit': SOURCE, 'os': 'linux', 'architecture': 'amd64'}


def verify():
    value = state()
    if value.get('protection', {}).get('status') != 'PASS':
        raise RuntimeError('PREFLIGHT_PASS_REQUIRED')
    # The only registry operation is a digest-pinned read. No docker login,
    # build, tag, push or delete is performed by this workflow.
    run(['docker', 'pull', '--platform=linux/amd64', IMAGE], timeout=900)
    facts = json.loads(run(['docker', 'image', 'inspect', IMAGE]))[0]
    value['imageProvenance'] = validate_image_facts(facts)
    save(value)
    module = frozen_ci()
    # Reuse the original strict union auditor with the archived manifest, not
    # a manifest generated from this new validation-only checkout commit.
    report = module.composed_image_check(IMAGE, hashes_only=True)
    extension = module.image_hashes(IMAGE)
    value = state()
    value.update(originalSources=report, sourceVerification=extension, immutablePullVerified=True)
    save(value)


def collect_pngs(folder):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or {item.name for item in folder.iterdir()} != PNG_NAMES:
        raise RuntimeError('EXACT_TWO_CAMERA_PNGS_REQUIRED')
    records = []
    for name in sorted(PNG_NAMES):
        path = folder / name
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 33 <= before.st_size <= MAX_PNG_BYTES:
            raise RuntimeError('UNSAFE_CAMERA_PNG')
        raw = path.read_bytes()
        after = path.lstat()
        attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
        if tuple(getattr(before, key) for key in attrs) != tuple(getattr(after, key) for key in attrs):
            raise RuntimeError('CAMERA_PNG_CHANGED_DURING_READ')
        if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR' or struct.unpack('>II', raw[16:24]) != (1080, 1920):
            raise RuntimeError('CAMERA_PNG_DIMENSIONS_REQUIRED')
        records.append({'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'width': 1080, 'height': 1920})
    return records


def validate_probe_report(report, records):
    true_fields = ('testOnly', 'actualShaderCompile', 'actualWebGL2DrawExecuted', 'actualReadPixelsExecuted',
                   'softwareWebGLDrawExecuted', 'materialAndSourceAndEventAndWorldUnitsEqual',
                   'holdLocked', 'eventAdvances', 'pixelsDiffer')
    false_fields = ('physicalNvidiaExecuted', 'gpuRenderingVerified', 'actualNvidiaVideoGenerated',
                    'imageBuilt', 'productionSourcesModified', 'videoQualityApproved', 'productionRenderAllowed')
    if (not isinstance(report, dict) or report.get('schema') != 'REFERENCE_CAMERA_HOLD_FOLLOWUP_SW_V1'
            or report.get('status') != 'PASS' or report.get('immutableImage') != IMAGE
            or report.get('followupScriptSha256') != SCRIPT_SHA
            or report.get('selectedComparisonFrame') != 100
            or any(report.get(key) is not True for key in true_fields)
            or any(report.get(key) is not False for key in false_fields)):
        raise RuntimeError('ACTUAL_TEST_ONLY_CAMERA_PROOF_REQUIRED')
    delta = report.get('actualCameraDeltaPixels')
    if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(delta) or delta <= 1:
        raise RuntimeError('ACTUAL_CAMERA_DELTA_GREATER_THAN_ONE_PIXEL_REQUIRED')
    verification = report.get('sourceVerification', {})
    if verification.get('status') != 'PASS' or verification.get('manifestSha256') != MANIFEST_SHA:
        raise RuntimeError('IMMUTABLE_PROBE_SOURCE_VERIFICATION_REQUIRED')
    stated = report.get('files')
    keys = ('file', 'bytes', 'sha256', 'width', 'height')
    if (not isinstance(stated, list) or len(stated) != 2 or len(records) != 2
            or any(not isinstance(row, dict) or row.get('scope') != 'CPU_SW_NOT_NVIDIA' for row in stated)
            or sorted(({key: row.get(key) for key in keys} for row in stated), key=lambda row: str(row['file'])) != records):
        raise RuntimeError('ACTUAL_CAMERA_PNG_HASH_BINDING_REQUIRED')


def probe_command(output):
    return ['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--memory=8g', '--cpus=2',
            '--pids-limit=512', '--restart=no', '--shm-size=2g',
            '--tmpfs', '/workspace:rw,mode=1777', '--tmpfs', '/tmp:rw,mode=1777',
            '--mount', 'type=bind,source=' + str(HERE / 'camera_hold_followup.mjs') + ',target=/__ci/camera_hold_followup.mjs,readonly',
            '--mount', 'type=bind,source=' + str(HERE / 'test_camera_hold_followup.mjs') + ',target=/__ci/test_camera_hold_followup.mjs,readonly',
            '--mount', 'type=bind,source=' + str(output) + ',target=/workspace/reference-followup',
            '--env', 'WORLD_ENGINE_REFERENCE_FOLLOWUP_DIR=/workspace/reference-followup',
            '--entrypoint=/usr/local/bin/node', IMAGE, '/__ci/camera_hold_followup.mjs']


def probe():
    value = state()
    if value.get('immutablePullVerified') is not True:
        raise RuntimeError('IMMUTABLE_PULL_AND_SOURCE_VERIFICATION_REQUIRED')
    output = Path(tempfile.mkdtemp(prefix='reference-camera-png-', dir=os.environ['RUNNER_TEMP']))
    output.chmod(0o777)
    tests = subprocess.run(probe_command(output)[:-1] + ['--test', '--test-isolation=none',
                           '/__ci/test_camera_hold_followup.mjs'], text=True, capture_output=True,
                           check=False, timeout=60)
    value['focusedCameraValidation'] = {'exitCode': tests.returncode, 'stdout': safe_log(tests.stdout),
                                       'stderr': safe_log(tests.stderr), 'scope': 'PURE_CPU_REJECTION_TESTS'}
    save(value)
    if tests.returncode:
        raise RuntimeError('FOCUSED_CAMERA_VALIDATION_TESTS_FAILED')
    result = subprocess.run(probe_command(output), text=True, capture_output=True, check=False, timeout=900)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value['actualCameraSoftwareProbe'] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr),
        'scope': 'ACTUAL_CPU_SWIFTSHADER_CAMERA_HOLD_NOT_NVIDIA'}
    save(value)
    if result.returncode:
        raise RuntimeError('ACTUAL_CAMERA_SOFTWARE_PROBE_FAILED')
    records = collect_pngs(output)
    validate_probe_report(report, records)
    value = state()
    value['actualCameraSoftwareProbe'].update(pngRoot=str(output), pngs=records)
    value['status'] = 'REFERENCE_CAMERA_HOLD_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING'
    save(value)


def evidence_paths(value):
    folder = NAMESPACE + '/runs/' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '/camera-followup'
    paths = {folder + '/result.json': (json.dumps(value, indent=2) + '\n').encode()}
    proof = value.get('actualCameraSoftwareProbe', {})
    if value['status'] == 'REFERENCE_CAMERA_HOLD_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING':
        records = collect_pngs(proof['pngRoot'])
        validate_probe_report(proof['report'], records)
        if records != proof.get('pngs'):
            raise RuntimeError('CAMERA_EVIDENCE_CHANGED')
        for row in records:
            paths[folder + '/public-review/' + row['file']] = (Path(proof['pngRoot']) / row['file']).read_bytes()
        paths[folder + '/public-review/SHA256SUMS'] = ''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in records).encode()
    if len(paths[folder + '/result.json']) > MAX_JSON_BYTES:
        raise RuntimeError('BOUNDED_CAMERA_RESULT_REQUIRED')
    return paths


def persist():
    value = state()
    value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if value['status'] == 'IN_PROGRESS' or any(item in ('failure', 'cancelled') for item in value['stepOutcomes'].values()):
        value['status'] = 'REFERENCE_CAMERA_FOLLOWUP_BLOCKED'
    paths = evidence_paths(value)
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO, timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    for relative, body in paths.items():
        target = REPO / relative
        if target.exists() or target.is_symlink():
            raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(body)
    run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    # New run folders are intentionally outside the checkout's old evidence
    # allowlist. Stage only these explicit paths without expanding the checkout.
    run(['git', 'add', '--sparse', '--', *sorted(paths)], cwd=REPO)
    if run(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines() != sorted(paths):
        raise RuntimeError('BOUNDED_CAMERA_EVIDENCE_ONLY_REQUIRED')
    run(['git', 'commit', '-m', 'docs: persist immutable image camera hold proof [skip ci]'], cwd=REPO)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=REPO, timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'verify', 'probe', 'persist'))
    arguments = parser.parse_args()
    try:
        globals()[arguments.phase]()
    except Exception as error:
        reason = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', reason):
            reason = 'CAMERA_FOLLOWUP_CI_FAILED'
        value = state()
        value.update(status='REFERENCE_CAMERA_FOLLOWUP_BLOCKED', failedPhase=arguments.phase,
                     reasonCode=reason, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            value['failedCommandExitCode'] = error.returncode
        save(value)
        print(json.dumps({'status': value['status'], 'phase': arguments.phase, 'reasonCode': reason}))
        raise SystemExit(1)
