#!/usr/bin/env python3
"""Compose proven free controls for an additive mobile Studio image."""
from __future__ import annotations
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
import sys
import tempfile
from types import SimpleNamespace
import urllib.request
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/production-studio-mvp-v1'
WORKFLOW = '.github/workflows/production-studio-mvp-v1.yml'
BRANCH = 'development/production-studio-mvp-v1-20261016'
BASELINE = '344dc2da48e15230725d687a4343456cbbae89a8'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:4f2daf520eed2331a1b6ea0d3644e6f7d65854e7d4f3368d43af5f96d1ff6ab4'
BASE = IMAGE + '@' + PARENT_DIGEST
DEST = '/opt/world-engine-production-studio'
TAG_PATTERN = re.compile(r'studio-v1-344dc2d-[1-9][0-9]*-[1-9][0-9]*', re.ASCII)
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


files = load('_studio_source_contract', HERE / 'studio_manifest.py')
controls = load('_studio_safe_ci_controls', HERE.parent / 'gcube-diagnostic-result-v1/ci.py')
run, save, state_path, sha, safe_log = controls.run, controls.save, controls.state_path, controls.sha, controls.safe_log
native = load('_studio_native_ci_helpers', HERE.parent / 'rtx-image-build-v1/pipeline.py')
parent = load('_studio_frozen_v4_ci', HERE.parent / 'verified-front-data-v4-recovery/ci_recovery.py')
# The strict parent audit uses the ACTUAL image's frozen manifest, never a
# regenerated V4 manifest attributed to the new Studio source commit.
frozen_path = HERE.parent / 'verified-front-data-v4-recovery/FRONT_FILES.json'
if sha(frozen_path) != files.PARENT_MANIFEST_SHA:
    raise RuntimeError('STUDIO_FROZEN_PARENT_MANIFEST_CHANGED')
frozen = json.loads(frozen_path.read_text())
parent.generate_manifest = lambda: frozen


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_PRODUCTION_STUDIO_IMAGE_V1', 'status': 'IN_PROGRESS',
        'ciCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE,
        'gpuExecuted': False, 'nvidiaHardwareVerified': False, 'gCubeDeployed': False,
        'paidWorkExecuted': False, 'finalModified': False, 'rendererModified': False,
        'oldImagesDeleted': False, 'imageBuilt': False, 'imagePushed': False,
        'pullVerified': False, 'videoQualityApproved': False,
        'actual80SecondNvidiaVideoGenerated': False, 'externalDropboxDeliveryVerified': False,
        'priorV4TestsAndSourceResearchReused': True}


def parent_image_check(image, *, hashes_only=True):
    report = parent.composed_image_check(image, hashes_only=hashes_only)
    if report.get('source', {}).get('composedInventoryFiles') != files.PARENT_INVENTORY_FILES:
        raise RuntimeError('STUDIO_EXACT_PARENT373_FILES_REQUIRED')
    return report


for key, value in {'HERE': HERE, 'REPO': REPO, 'NAMESPACE': NAMESPACE, 'WORKFLOW': WORKFLOW,
        'BRANCH': BRANCH, 'BASELINE': BASELINE, 'BASE': BASE, 'PARENT_DIGEST': PARENT_DIGEST,
        'DEST': DEST, 'PATCHES': {}, 'state': state}.items():
    setattr(controls, key, value)
controls.helpers = lambda: SimpleNamespace(require_space=native.require_space, login=native.login, check_image=parent_image_check)


def configure_registry():
    path = str(HERE.parent / 'rtx-image-build-v1')
    if path not in sys.path:
        sys.path.insert(0, path)
    import registry_guard
    registry_guard.TAG_PATTERN = TAG_PATTERN
    return registry_guard


def preflight():
    controls.preflight()
    value = state()
    value.update(tag='studio-v1-344dc2d-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
    value['image'] = IMAGE + ':' + value['tag']
    files.inventory(HERE)
    save(value)


def guard():
    configure_registry(); controls.guard()


def generate_manifest():
    commit = os.environ.get('GITHUB_SHA') or run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip()
    if not files.COMMIT.fullmatch(commit):
        raise RuntimeError('STUDIO_SOURCE_COMMIT_REQUIRED')
    declared = files.inventory(HERE)
    return {'schema': files.SCHEMA, 'profileId': files.PROFILE_ID, 'sourceCommit': commit,
        'baselineCommit': BASELINE, 'parentImage': BASE, 'parentManifestSha256': files.PARENT_MANIFEST_SHA,
        'parentSourceCommit': files.PARENT_SOURCE_COMMIT, 'parentInventoryFiles': files.PARENT_INVENTORY_FILES,
        'files': {name: sha(HERE / name) for name in declared['files']},
        'testFiles': {name: sha(HERE / name) for name in declared['testFiles']}}


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='studio-payload-', dir=os.environ['RUNNER_TEMP']))
    payload = context / 'studio'; payload.mkdir()
    manifest = generate_manifest()
    for name in (*manifest['files'], *manifest['testFiles']):
        destination = payload / name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / name, destination)
    (payload / files.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    files.verify_payload(payload)
    return context


def container(*, context=None, evidence=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=8g', '--cpus=2',
        '--pids-limit=512', '--restart=no', '--shm-size=2g', '--tmpfs', '/workspace:rw,mode=1777',
        '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / 'studio') + ',target=' + DEST + ',readonly']
    if evidence is not None:
        command += ['--mount', 'type=bind,source=' + str(evidence) + ',target=/workspace/studio-evidence',
            '--env', 'WORLD_ENGINE_STUDIO_EVIDENCE_DIR=/workspace/studio-evidence']
    return command


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/var/lib/world-engine-private/engine/production-studio-mvp-v1');"
        "p.mkdir(mode=0o700,parents=True,exist_ok=True);os.chown(p,1000,1000);os.setgroups([]);os.setgid(1000);os.setuid(1000);" + body)


def record_case(name, command, *, timeout=300):
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    row = {'name': name, 'exitCode': result.returncode, 'stdout': safe_log(result.stdout),
        'stderr': safe_log(result.stderr), 'scope': 'STUDIO_CHANGED_CPU_ONLY', 'gpuExecuted': False}
    value = state(); value.setdefault('focusedTests', {}).setdefault('cases', []).append(row); save(value)
    if result.returncode:
        raise RuntimeError('STUDIO_FOCUSED_TEST_FAILED')
    return row


def focused_tests(image, context):
    for path in sorted((HERE / 'tests').glob('test_*.py')):
        if path.name == 'test_ci_studio.py':
            continue
        code = ("import sys,unittest;sys.path.insert(0,'" + DEST + "');"
            "s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + path.name + "');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        record_case(path.name, container(context=context) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)], timeout=600)
    for path in sorted((HERE / 'tests').glob('test_*.mjs')):
        code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + '/tests/' + path.name + "']).returncode)"
        record_case(path.name, container(context=context) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)])


def mobile_probe(image, *, context=None):
    if not (HERE / 'tests/mobile_probe.mjs').is_file():
        raise RuntimeError('STUDIO_ACTUAL_MOBILE_PROBE_REQUIRED')
    evidence = Path(tempfile.mkdtemp(prefix='studio-mobile-', dir=os.environ['RUNNER_TEMP'])); evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/tests/mobile_probe.mjs']).returncode)"
    result = subprocess.run(container(context=context, evidence=evidence) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=600)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state(); value['mobileProbe'] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr), 'evidenceFolder': str(evidence),
        'scope': 'ACTUAL_MOBILE_BROWSER_CPU_NOT_NVIDIA', 'gpuExecuted': False}; save(value)
    if (result.returncode or not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'WORLD_ENGINE_STUDIO_MOBILE_UI_CPU_TEST_V1'
            or report.get('testOnly') is not True or report.get('gpuExecuted') is not False
            or report.get('gpuRenderingVerified') is not False):
        raise RuntimeError('STUDIO_ACTUAL_MOBILE_BROWSER_REQUIRED')
    return report


def software_probe(image):
    # One existing image-local V4 draw proves inherited rendering, rather than
    # re-running old source/history/full CPU audits. This is never NVIDIA PASS.
    evidence = Path(tempfile.mkdtemp(prefix='studio-v4-draw-', dir=os.environ['RUNNER_TEMP'])); evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','/opt/world-engine-front-v4/software_probe_front.mjs']).returncode)"
    command = container() + ['--mount', 'type=bind,source=' + str(evidence) + ',target=/workspace/front-evidence',
        '--env', 'WORLD_ENGINE_FRONT_EVIDENCE_DIR=/workspace/front-evidence', '--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)]
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=1200)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state(); value['inheritedActualSoftwareDraw'] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr), 'evidenceFolder': str(evidence),
        'scope': 'ACTUAL_UNCHANGED_V4_SWIFTSHADER_DRAW_NOT_NVIDIA', 'gpuExecuted': False}; save(value)
    if result.returncode:
        raise RuntimeError('STUDIO_INHERITED_SOFTWARE_DRAW_FAILED')
    audit = parent.validate_software_report(report)
    if report.get('frontManifestSha256') != files.PARENT_MANIFEST_SHA:
        raise RuntimeError('STUDIO_SOFTWARE_PARENT_MANIFEST_CHANGED')
    bindings = parent.validate_source_bindings(report, HERE.parent / 'verified-front-data-v4-recovery')
    records = parent.collect_png_evidence(evidence, report)
    value = state(); value['inheritedActualSoftwareDraw'].update(audit=audit, sourceBindings=bindings, files=records); save(value)


def test():
    native.require_space()
    record_case('CI-safety', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'), '-p', 'test_ci_studio.py', '-v'])
    run(['docker', 'pull', BASE], timeout=900)
    context = payload_context(); focused_tests(BASE, context); mobile_probe(BASE, context=context)
    value = state(); value['focusedTests']['status'] = 'PASS'; save(value)


def stage():
    value = state()
    if value.get('focusedTests', {}).get('status') != 'PASS' or value.get('mobileProbe', {}).get('exitCode') != 0:
        raise RuntimeError('STUDIO_FOCUSED_AND_MOBILE_TESTS_REQUIRED')
    context = payload_context(); manifest = json.loads((context / 'studio' / files.MANIFEST_NAME).read_text())
    value.update(context=str(context), studioManifest=manifest, studioManifestSha256=sha(context / 'studio' / files.MANIFEST_NAME),
        dockerfileSha256=sha(context / 'Dockerfile')); save(value)


def inspect_image(image):
    facts = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    config = facts.get('Config', {}); labels = config.get('Labels', {})
    if (facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64'
            or labels.get('world-engine.studio.parent-digest') != PARENT_DIGEST
            or labels.get('world-engine.studio.source-revision') != os.environ['GITHUB_SHA']
            or labels.get('world-engine.front-v4.source-revision') != files.PARENT_SOURCE_COMMIT):
        raise RuntimeError('STUDIO_IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', DEST + '/bootstrap.py']:
        raise RuntimeError('STUDIO_FIXED_BOOTSTRAP_REQUIRED')
    if {row.partition('=')[0] for row in config.get('Env', [])} & {'GH_TOKEN', 'GITHUB_TOKEN', 'DOCKER_AUTH_CONFIG',
            'GCUBE_API_TOKEN', 'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_SESSION_KEY'}:
        raise RuntimeError('STUDIO_CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value = state(); value['builderBeforeBuild'] = native.require_space(); save(value)
    if value.get('focusedTests', {}).get('status') != 'PASS':
        raise RuntimeError('STUDIO_TESTS_REQUIRED')
    context = Path(value['context']); report = files.verify_payload(context / 'studio')
    if report['manifestSha256'] != value['studioManifestSha256']:
        raise RuntimeError('STUDIO_FROZEN_CONTEXT_SHA_REQUIRED')
    subprocess.run(['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
        '--label', 'world-engine.studio.source-revision=' + os.environ['GITHUB_SHA'], '--tag', value['image'], str(context)], check=True, timeout=600)
    facts = inspect_image(value['image']); value.update(imageBuilt=True, configDigest=facts['Id'], imageSizeBytes=facts['Size']); save(value)


def image_hashes(image):
    code = "import sys,json;sys.path.insert(0,'" + DEST + "');import studio_manifest;print(json.dumps(studio_manifest.verify_sources()))"
    report = json.loads(run(['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--entrypoint=/usr/bin/python3', image, '-B', '-c', code]))
    expected = hashlib.sha256((json.dumps(generate_manifest(), indent=2) + '\n').encode()).hexdigest()
    if report.get('status') != 'PASS' or report.get('manifestSha256') != expected or report.get('parentInventoryFiles') != files.PARENT_INVENTORY_FILES:
        raise RuntimeError('STUDIO_IMAGE_PAYLOAD_SHA_MISMATCH')
    return report


def secret_scan(image):
    value = state(); root = Path(tempfile.mkdtemp(prefix='studio-secret-source-', dir=os.environ['RUNNER_TEMP']))
    inspector = run(['docker', 'create', '--entrypoint=/bin/true', image]).strip()
    try:
        run(['docker', 'cp', inspector + ':' + DEST, str(root / 'actual-image-studio')], timeout=120)
    finally:
        run(['docker', 'rm', inspector])
    shutil.copytree(HERE, root / 'new-namespace', ignore=shutil.ignore_patterns('runs', '__pycache__'))
    shutil.copyfile(REPO / WORKFLOW, root / 'workflow.yml')
    scanner_dir = Path(tempfile.mkdtemp(prefix='studio-scanner-', dir=os.environ['RUNNER_TEMP']))
    with urllib.request.urlopen('https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz', timeout=30) as response:
        body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2:
        raise RuntimeError('STUDIO_SCANNER_ARCHIVE_SIZE_LIMIT')
    archive = scanner_dir / 'scanner.tar.gz'; archive.write_bytes(body)
    run(['tar', '-xzf', str(archive), '-C', str(scanner_dir), 'gitleaks']); scanner = scanner_dir / 'gitleaks'
    if sha(scanner) != SCANNER_SHA:
        raise RuntimeError('STUDIO_SCANNER_SHA_MISMATCH')
    config = scanner_dir / 'defaults.toml'; config.write_text('[extend]\nuseDefault = true\n')
    ignore = scanner_dir / 'empty-ignore'; ignore.write_text(''); report = scanner_dir / 'findings.json'
    result = subprocess.run([str(scanner), 'dir', str(root), '--config', str(config), '--gitleaks-ignore-path', str(ignore),
        '--ignore-gitleaks-allow', '--redact=100', '--report-format=json', '--report-path', str(report), '--no-banner'],
        text=True, capture_output=True, check=False, timeout=180)
    findings = json.loads(report.read_text()) if report.exists() and report.stat().st_size < 16 * 1024**2 else None
    value = state(); value['secretScan'] = {'status': 'PASS' if result.returncode == 0 and findings == [] else 'FAIL',
        'findings': len(findings) if isinstance(findings, list) else None, 'scannerExitCode': result.returncode,
        'scannerSha256': SCANNER_SHA, 'scope': 'actual Studio payload, new namespace and workflow; immutable parent scan reused'}; save(value)
    if value['secretScan']['status'] != 'PASS':
        raise RuntimeError('STUDIO_SECRET_SCAN_FAILED')


def verify():
    value = state(); value.update(originalSources=parent_image_check(value['image']), imageHashes=image_hashes(value['image'])); save(value)
    software_probe(value['image']); secret_scan(value['image'])
    value = state(); value['verification'] = 'PASS'; save(value)


controls.inspect_image, controls.image_hashes = inspect_image, image_hashes


def publish():
    configure_registry(); controls.publish()


def read_only_registry():
    """Only adapt token scope; reuse all frozen manifest/config/TLS checks."""
    registry = configure_registry()
    class ReadOnlyRegistryGuard(registry.RegistryGuard):
        def _authenticate(self):
            actor = self._environ.get('GITHUB_ACTOR')
            if not isinstance(actor, str) or not registry.ACTOR_PATTERN.fullmatch(actor):
                raise registry.GuardError('GITHUB_ACTOR_REQUIRED_OR_INVALID')
            try:
                secret = registry._token_string(self._environ.get('GH_TOKEN'))
            except registry.GuardError:
                raise registry.GuardError('GH_TOKEN_REQUIRED_OR_INVALID') from None
            basic = base64.b64encode((actor + ':' + secret).encode('ascii')).decode('ascii')
            url = registry.REGISTRY + '/token?' + urlencode({'service': 'ghcr.io',
                'scope': 'repository:' + registry.REPOSITORY + ':pull'})
            response = self._get(url, {'Authorization': 'Basic ' + basic, 'Accept': 'application/json',
                'Accept-Encoding': 'identity'}, registry.MAX_TOKEN_RESPONSE_BYTES)
            if response.status != 200:
                raise registry.GuardError('TOKEN_HTTP_NOT_200')
            document = registry._json_object(response.body)
            if 'token' in document and 'access_token' in document and document['token'] != document['access_token']:
                raise registry.GuardError('CONFLICTING_ISSUED_TOKENS')
            token = registry._token_string(document.get('token', document.get('access_token')))
            # Do not parse opaque JWT data or claim push rights from a read job.
            return token, {'status': 'TOKEN_SCOPE_NOT_INFERRED', 'requestedScope': 'pull',
                'pull': None, 'push': False, 'pushVerified': False}
        def check_tag(self, tag):
            raise registry.GuardError('READ_ONLY_REGISTRY_CANNOT_RESERVE_OR_PUBLISH')
    return ReadOnlyRegistryGuard


def pull():
    registry = configure_registry(); value = state()
    value['tag'] = registry.validate_tag(os.environ['RESULT_PUBLISHED_TAG'])
    value['imageDigest'] = registry.validate_digest(os.environ['RESULT_PUBLISHED_DIGEST'])
    remote = read_only_registry()().inspect_digest(value['imageDigest'])
    value['imageReference'] = IMAGE + '@' + remote['digest']; save(value)
    auth, environment = native.login(value)
    try:
        run(['docker', 'pull', value['imageReference']], env=environment, timeout=900)
    finally:
        controls.clean_auth(auth)
    facts = inspect_image(value['imageReference'])
    if facts['Id'] != remote['configDigest']:
        raise RuntimeError('STUDIO_PULLED_CONFIG_SHA_MISMATCH')
    value.update(originalSources=parent_image_check(value['imageReference']), imageHashes=image_hashes(value['imageReference']),
        configDigest=facts['Id'], registryVerification=remote, pullVerified=True, imagePushed=True,
        status='PRODUCTION_STUDIO_MVP_IMAGE_CPU_SOFTWARE_READY_HARDWARE_PENDING')
    save(value)


def persist():
    value = state(); value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if value['status'] == 'IN_PROGRESS' or any(item == 'failure' for item in value['stepOutcomes'].values()):
        value['status'] = 'PRODUCTION_STUDIO_MVP_IMAGE_BLOCKED'
    relative = NAMESPACE + '/runs/' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '/' + os.environ['RESULT_PHASE'] + '.json'
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 16 * 1024**2:
        raise RuntimeError('STUDIO_BOUNDED_EVIDENCE_REQUIRED')
    artifacts = {}
    for key in ('mobileProbe', 'inheritedActualSoftwareDraw'):
        probe = value.get(key, {})
        if os.environ['RESULT_PHASE'] != 'build' or probe.get('exitCode') != 0 or not probe.get('evidenceFolder'):
            continue
        folder = Path(probe['evidenceFolder'])
        for path in folder.iterdir():
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r'(?:[A-Za-z0-9_-]{1,96}\.(?:png|json)|SHA256SUMS)', path.name):
                raise RuntimeError('STUDIO_BOUNDED_TEST_ARTIFACT_REQUIRED')
            if not 0 < path.stat().st_size <= 12 * 1024**2:
                raise RuntimeError('STUDIO_ARTIFACT_SIZE_LIMIT')
            artifacts[str(Path(relative).parent / key / path.name)] = path.read_bytes()
    if sum(map(len, artifacts.values())) > 140 * 1024**2:
        raise RuntimeError('STUDIO_ARTIFACT_TOTAL_SIZE_LIMIT')
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO, timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    for name, body in {relative: raw, **artifacts}.items():
        destination = REPO / name
        if destination.exists():
            raise RuntimeError('STUDIO_OLD_EVIDENCE_OVERWRITE_FORBIDDEN')
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(body)
    run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    expected = sorted([relative, *artifacts]); run(['git', 'add', '--', *expected], cwd=REPO)
    if sorted(run(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines()) != expected:
        raise RuntimeError('STUDIO_BOUNDED_EVIDENCE_ONLY_REQUIRED')
    run(['git', 'commit', '-m', 'docs: persist Studio MVP ' + os.environ['RESULT_PHASE'] + ' evidence [skip ci]'], cwd=REPO)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=REPO, timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'])
    args = parser.parse_args()
    try:
        globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_CI_FAILED'
        value = state(); value.update(status='PRODUCTION_STUDIO_MVP_IMAGE_BLOCKED', failedPhase=args.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            value['failedCommandExitCode'] = error.returncode
        save(value); print(json.dumps({'status': value['status'], 'phase': args.phase, 'reasonCode': code})); raise SystemExit(1)
