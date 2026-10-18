#!/usr/bin/env python3
"""Free CPU packaging and immutable independent pull for the HTTPS extension.

This file never calls gCube, requests GPU devices, deletes existing Docker data,
or reports NVIDIA/video quality validation from CPU test results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1'
WORKFLOW = '.github/workflows/studio-https-bootstrap-v1.yml'
BRANCH = 'development/studio-https-bootstrap-20261018'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
BASE_DIGEST = 'sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94'
BASE = IMAGE + '@' + BASE_DIGEST
DEST = '/opt/world-engine-studio-https-bootstrap'
OLD_DEST = '/opt/world-engine-production-studio'
PARENT_MANIFEST_SHA = '1f4129faaeb59027429d4d531da2b7e7b50156ca7c1652e700dd542c935b88de'
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
HASH = re.compile(r'[a-f0-9]{64}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')
DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
TAG = re.compile(r'studio-https-v1-85aef26-[1-9][0-9]*-[1-9][0-9]*\Z')
SENSITIVE = re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|[?&](?:token|sig)=', re.I)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-https-package-v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def state():
    path = location() / 'state.json'
    if path.exists():
        return json.loads(path.read_text())
    return {'schema': 'WORLD_ENGINE_STUDIO_HTTPS_PACKAGE_V1', 'status': 'IN_PROGRESS',
        'sourceCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE,
        'gpuExecuted': False, 'nvidiaHardwareVerified': False, 'paidWorkExecuted': False,
        'gCubeDeployed': False, 'finalModified': False, 'rendererModified': False,
        'oldImagesDeleted': False, 'imageBuilt': False, 'imagePushed': False,
        'pullVerified': False, 'videoQualityApproved': False}


def save(value):
    (location() / 'state.json').write_text(json.dumps(value, indent=2) + '\n')


def bounded(text):
    text = SENSITIVE.sub('[REDACTED]', text)
    for name in ('GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN', 'WORLD_ENGINE_STUDIO_OWNER_CODE'):
        value = os.environ.get(name)
        if value:
            text = text.replace(value, '[REDACTED]')
    return text[-65536:]


def run(command, *, timeout=120, environment=None, check=True):
    result = subprocess.run(command, cwd=REPO, env=environment, text=True,
        capture_output=True, timeout=timeout, check=False)
    if check and result.returncode:
        raise RuntimeError('HTTPS_CI_COMMAND_FAILED')
    return result


def require_free_runner():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
            or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH
            or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'
            or os.environ.get('RESULT_RUNNER_LABEL') != 'ubuntu-24.04'):
        raise RuntimeError('HTTPS_FREE_PUBLIC_STANDARD_RUNNER_REQUIRED')
    if shutil.disk_usage('/var/lib/docker').free < 20 * 1024**3:
        raise RuntimeError('HTTPS_DOCKER_20_GIB_FREE_REQUIRED')
    driver = run(['docker', 'info', '--format', '{{.Driver}}']).stdout.strip()
    if driver == 'vfs':
        raise RuntimeError('HTTPS_OVERLAY_BUILDER_REQUIRED')
    return {'status': 'PASS', 'dockerDriver': driver,
        'freeBytes': shutil.disk_usage('/var/lib/docker').free,
        'minimumFreeBytes': 20 * 1024**3, 'existingDataDeleted': False}


def preflight():
    value = state(); value['builder'] = require_free_runner()
    commit = os.environ.get('GITHUB_SHA', '')
    if not COMMIT.fullmatch(commit):
        raise RuntimeError('HTTPS_SOURCE_COMMIT_REQUIRED')
    value.update(tag='studio-https-v1-85aef26-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
    if not TAG.fullmatch(value['tag']):
        raise RuntimeError('HTTPS_UNIQUE_TAG_REQUIRED')
    value['image'] = IMAGE + ':' + value['tag']; save(value)


def registry_get(reference):
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
            if len(raw) > 4 * 1024**2 or not DIGEST.fullmatch(str(digest)) or hashlib.sha256(raw).hexdigest() != digest[7:]:
                raise RuntimeError('HTTPS_REMOTE_MANIFEST_SHA_REQUIRED')
            document = json.loads(raw)
            if document.get('schemaVersion') != 2 or not DIGEST.fullmatch(str(document.get('config', {}).get('digest'))):
                raise RuntimeError('HTTPS_SINGLE_PLATFORM_IMAGE_MANIFEST_REQUIRED')
            return {'status': 200, 'digest': digest, 'configDigest': document['config']['digest']}
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {'status': 404}
        raise RuntimeError('HTTPS_REGISTRY_READ_FAILED') from None


def guard():
    value = state()
    if not TAG.fullmatch(str(value.get('tag'))):
        raise RuntimeError('HTTPS_UNIQUE_TAG_REQUIRED')
    result = registry_get(value['tag'])
    if result['status'] != 404:
        raise RuntimeError('HTTPS_EXISTING_TAG_OVERWRITE_FORBIDDEN')
    value['tagGuard'] = {'status': 'PASS', 'remoteHTTP': 404, 'tag': value['tag']}; save(value)


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='https-payload-', dir=location()))
    payload = context / 'extension'; payload.mkdir()
    files = sorted(p.name for p in HERE.glob('*.py') if p.name != 'ci_package.py')
    for folder in ('web',):
        files += sorted(path.relative_to(HERE).as_posix() for path in (HERE / folder).rglob('*') if path.is_file())
    tests = sorted(path.relative_to(HERE).as_posix() for path in (HERE / 'tests').rglob('*')
        if path.is_file() and path.suffix in ('.py', '.mjs', '.js') and '__pycache__' not in path.parts)
    if not {'https_bootstrap.py', 'https_server.py', 'manifest.py', 'setup_core.py', 'frozen.py'} <= set(files) or not tests:
        raise RuntimeError('HTTPS_CONNECTED_EXTENSION_AND_TESTS_REQUIRED')
    for name in (*files, *tests):
        source = HERE / name
        if (any(path.is_symlink() for path in (source, *source.parents))
                or not 0 < source.stat().st_size <= 4 * 1024**2):
            raise RuntimeError('HTTPS_BOUNDED_REGULAR_PAYLOAD_REQUIRED')
        target = payload / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest = {'schema': 'WORLD_ENGINE_STUDIO_HTTPS_EXTENSION_FILES_V1', 'profileId': 'STUDIO_HTTPS_BOOTSTRAP_V1',
        'sourceCommit': os.environ['GITHUB_SHA'], 'parentImage': BASE,
        'parentStudioManifestSha256': PARENT_MANIFEST_SHA,
        'files': {name: sha(payload / name) for name in sorted(files)},
        'testFiles': {name: sha(payload / name) for name in tests}}
    (payload / 'EXTENSION_FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    return context


def container(image, *, context=None, evidence=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=8g',
        '--cpus=2', '--pids-limit=512', '--restart=no', '--shm-size=2g',
        '--tmpfs', '/workspace:rw,mode=1777', '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / 'extension') + ',target=' + DEST + ',readonly']
    if evidence is not None:
        command += ['--mount', 'type=bind,source=' + str(evidence) + ',target=/ci-evidence',
            '--env', 'WORLD_ENGINE_STUDIO_EVIDENCE_DIR=/ci-evidence']
    return command + ['--entrypoint=/usr/bin/python3', image, '-B']


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/tmp/studio-https-test-home');p.mkdir(mode=0o700);os.chown(p,1000,1000);"
        "os.environ['HOME']=str(p);os.environ['XDG_CONFIG_HOME']=str(p/'config');os.environ['XDG_CACHE_HOME']=str(p/'cache');"
        "os.setgroups([]);os.setgid(1000);os.setuid(1000);" + body)


def record(name, command, timeout=600):
    result = run(command, timeout=timeout, check=False)
    value = state(); row = {'name': name, 'exitCode': result.returncode,
        'stdout': bounded(result.stdout), 'stderr': bounded(result.stderr),
        'scope': 'CPU_CONTAINER_OR_MOBILE_NOT_NVIDIA', 'gpuExecuted': False}
    value.setdefault('focusedTests', []).append(row); save(value)
    if result.returncode:
        raise RuntimeError('HTTPS_FOCUSED_TEST_FAILED')
    return result


def image_hashes(image, context=None):
    result = run(container(image, context=context) + [DEST + '/manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('HTTPS_SOURCE_REPORT_REQUIRED') from None
    if context is not None:
        expected = sha(context / 'extension/EXTENSION_FILES.json')
    else:
        generated = payload_context()
        expected = sha(generated / 'extension/EXTENSION_FILES.json')
    parent = report.get('parentStudio', {})
    if (report.get('status') != 'PASS' or report.get('manifestSha256') != expected
            or report.get('sourceCommit') != os.environ['GITHUB_SHA']
            or parent.get('manifestSha256') != PARENT_MANIFEST_SHA
            or parent.get('files') != 51 or parent.get('parentInventoryFiles') != 373
            or report.get('gpuExecuted') is not False):
        raise RuntimeError('HTTPS_SOURCE_VERIFICATION_FAILED')
    return report


def test():
    require_free_runner(); run(['docker', 'pull', BASE], timeout=900)
    context = payload_context(); value = state(); value['testContext'] = str(context); save(value)
    report = image_hashes(BASE, context)
    value = state(); value['originalAndExtensionSourceHashes'] = report; save(value)
    code = "import sys,unittest;sys.path.insert(0,'" + DEST + "');s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='test_*.py');r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)"
    record('focused-python', container(BASE, context=context) + ['-c', uid_code(code)])
    if not (HERE / 'tests' / 'container_probe.py').is_file():
        raise RuntimeError('HTTPS_EXACT_CONTAINER_STARTUP_PROBE_REQUIRED')
    probe_output = location() / 'container-probe'; probe_output.mkdir(mode=0o700, exist_ok=True)
    environment = dict(os.environ, WORLD_ENGINE_STUDIO_EXTENSION_DIR=str(context / 'extension'),
        WORLD_ENGINE_STUDIO_BASE_IMAGE=BASE, WORLD_ENGINE_STUDIO_CONTAINER_EVIDENCE_DIR=str(probe_output))
    result = run([sys.executable, '-B', str(HERE / 'tests/container_probe.py'),
        '--image', BASE, '--extension', str(context / 'extension'),
        '--output', str(probe_output / 'CONTAINER_REPORT.json')],
        environment=environment, timeout=900, check=False)
    value = state(); value['containerProbe'] = {'exitCode': result.returncode,
        'stdout': bounded(result.stdout), 'stderr': bounded(result.stderr)}; save(value)
    if result.returncode or not (probe_output / 'CONTAINER_REPORT.json').is_file():
        raise RuntimeError('HTTPS_CONTAINER_STARTUP_PROBE_FAILED')
    report = json.loads((probe_output / 'CONTAINER_REPORT.json').read_text())
    if report.get('status') != 'PASS':
        raise RuntimeError('HTTPS_CONTAINER_STARTUP_PROBE_FAILED')
    value = state(); value['containerProbe']['report'] = report; save(value)
    evidence = location() / 'mobile'; evidence.mkdir(mode=0o777, exist_ok=True); evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/tests/mobile_probe.mjs']).returncode)"
    result = record('actual-mobile-chromium', container(BASE, context=context, evidence=evidence) + ['-c', uid_code(code)])
    try:
        mobile = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('HTTPS_MOBILE_REPORT_REQUIRED') from None
    if mobile.get('status') != 'PASS' or mobile.get('gpuExecuted') is not False:
        raise RuntimeError('HTTPS_ACTUAL_MOBILE_CPU_PASS_REQUIRED')
    value = state(); value.update(mobileProbe=mobile, testsStatus='PASS'); save(value)


def stage():
    value = state()
    if value.get('testsStatus') != 'PASS':
        raise RuntimeError('HTTPS_FOCUSED_CONTAINER_MOBILE_PASS_REQUIRED')
    context = payload_context()
    if (context / 'extension/EXTENSION_FILES.json').read_bytes() != (Path(value['testContext']) / 'extension/EXTENSION_FILES.json').read_bytes():
        raise RuntimeError('HTTPS_TESTED_CONTEXT_CHANGED')
    value.update(context=str(context), extensionManifestSha256=sha(context / 'extension/EXTENSION_FILES.json'),
        dockerfileSha256=sha(context / 'Dockerfile')); save(value)


def inspect_image(image):
    report = json.loads(run(['docker', 'image', 'inspect', image]).stdout)[0]
    config = report.get('Config', {}); labels = config.get('Labels', {})
    if (report.get('Os') != 'linux' or report.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', DEST + '/https_bootstrap.py']
            or labels.get('world-engine.studio-https.parent-digest') != BASE_DIGEST
            or labels.get('world-engine.studio-https.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('HTTPS_IMAGE_PROVENANCE_REQUIRED')
    if set(item.partition('=')[0] for item in config.get('Env', [])) & {
            'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
            'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}:
        raise RuntimeError('HTTPS_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('HTTPS_INDEPENDENT_SERVICE_HEALTH_REQUIRED')
    return {'status': 'PASS', 'configDigest': report['Id'], 'sizeBytes': report['Size'],
        'entrypoint': config['Entrypoint'], 'healthcheck': config['Healthcheck'],
        'platform': 'linux/amd64', 'secretEnvironmentPresent': False}


def build():
    value = state(); require_free_runner()
    if value.get('testsStatus') != 'PASS' or not value.get('context'):
        raise RuntimeError('HTTPS_TESTED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (sha(context / 'extension/EXTENSION_FILES.json') != value['extensionManifestSha256']
            or sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('HTTPS_FROZEN_CONTEXT_SHA_REQUIRED')
    command = ['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
        '--label', 'world-engine.studio-https.source-revision=' + os.environ['GITHUB_SHA'],
        '--tag', value['image'], str(context)]
    result = run(command, timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode, 'stdout': bounded(result.stdout), 'stderr': bounded(result.stderr)}; save(value)
    if result.returncode:
        raise RuntimeError('HTTPS_IMAGE_BUILD_FAILED')
    value = state(); value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image'])); save(value)


def secret_scan():
    directory = location() / 'scanner'; directory.mkdir(mode=0o700, exist_ok=True)
    url = 'https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz'
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read(32 * 1024**2 + 1)
    if len(raw) > 32 * 1024**2:
        raise RuntimeError('HTTPS_SCANNER_ARCHIVE_SIZE_LIMIT')
    archive = directory / 'archive.tar.gz'; archive.write_bytes(raw)
    with tarfile.open(archive, 'r:gz') as tar:
        member = tar.getmember('gitleaks')
        if not member.isfile() or not 0 < member.size < 64 * 1024**2:
            raise RuntimeError('HTTPS_SCANNER_REGULAR_BINARY_REQUIRED')
        extracted = tar.extractfile(member)
        (directory / 'gitleaks').write_bytes(extracted.read())
    scanner = directory / 'gitleaks'
    if sha(scanner) != SCANNER_SHA:
        raise RuntimeError('HTTPS_SCANNER_SHA_MISMATCH')
    scanner.chmod(0o700)
    root = directory / 'scope'; root.mkdir()
    shutil.copytree(HERE, root / 'extension', ignore=shutil.ignore_patterns('runs', '__pycache__'))
    shutil.copyfile(REPO / WORKFLOW, root / 'workflow.yml')
    config = directory / 'defaults.toml'; config.write_text('[extend]\nuseDefault = true\n')
    ignore = directory / 'empty-ignore'; ignore.write_text('')
    output = directory / 'findings.json'
    result = run([str(scanner), 'dir', str(root), '--config', str(config), '--gitleaks-ignore-path', str(ignore),
        '--ignore-gitleaks-allow', '--redact=100', '--report-format=json', '--report-path', str(output), '--no-banner'])
    findings = json.loads(output.read_text()) if output.exists() and output.stat().st_size <= 16 * 1024**2 else None
    if result.returncode or findings != []:
        raise RuntimeError('HTTPS_SECRET_SCAN_FAILED')
    return {'status': 'PASS', 'findings': 0, 'scannerSha256': SCANNER_SHA,
        'scope': 'all new extension source/tests/docs/workflow; inherited image scan reused'}


def verify():
    value = state()
    if not value.get('imageBuilt'):
        raise RuntimeError('HTTPS_BUILT_IMAGE_REQUIRED')
    report = image_hashes(value['image'])
    value = state(); value.update(imageHashes=report, secretScan=secret_scan(), verification='PASS'); save(value)


def publish():
    value = state()
    if value.get('verification') != 'PASS':
        raise RuntimeError('HTTPS_VERIFIED_IMAGE_REQUIRED')
    guard()
    token = os.environ.get('GH_TOKEN', '')
    actor = os.environ.get('GITHUB_ACTOR', '')
    if not token or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?', actor):
        raise RuntimeError('HTTPS_REGISTRY_AUTH_REQUIRED')
    auth = Path(tempfile.mkdtemp(prefix='https-registry-auth-', dir=location()))
    environment = dict(os.environ, DOCKER_CONFIG=str(auth))
    environment.pop('GH_TOKEN', None); environment.pop('GITHUB_TOKEN', None)
    try:
        result = subprocess.run(['docker', 'login', 'ghcr.io', '--username', actor, '--password-stdin'],
            input=token, text=True, env=environment, capture_output=True, timeout=60, check=False)
        if result.returncode:
            raise RuntimeError('HTTPS_REGISTRY_LOGIN_FAILED')
        result = run(['docker', 'push', value['image']], environment=environment, timeout=900)
    finally:
        # Remove only this job's new authentication directory, never existing credentials.
        shutil.rmtree(auth)
    remote = registry_get(value['tag'])
    if remote.get('status') != 200 or remote.get('configDigest') != value['imageConfiguration']['configDigest']:
        raise RuntimeError('HTTPS_PUBLISHED_CONFIG_SHA_MISMATCH')
    value = state(); value.update(imagePushed=True, imageDigest=remote['digest'],
        imageReference=IMAGE + '@' + remote['digest'], registryVerification=remote,
        status='STUDIO_HTTPS_CANDIDATE_CPU_VERIFIED_HARDWARE_PENDING'); save(value)
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as stream:
            stream.write('tag=' + value['tag'] + '\ndigest=' + remote['digest'] + '\n')


def pull():
    value = state(); tag = os.environ.get('RESULT_PUBLISHED_TAG', ''); digest = os.environ.get('RESULT_PUBLISHED_DIGEST', '')
    if not TAG.fullmatch(tag) or not DIGEST.fullmatch(digest):
        raise RuntimeError('HTTPS_PUBLISHED_IMMUTABLE_REFERENCE_REQUIRED')
    remote = registry_get(digest)
    if remote.get('status') != 200 or remote['digest'] != digest or registry_get(tag).get('digest') != digest:
        raise RuntimeError('HTTPS_TAG_DIGEST_MISMATCH')
    image = IMAGE + '@' + digest
    run(['docker', 'pull', image], timeout=900)
    config = inspect_image(image)
    if config['configDigest'] != remote['configDigest']:
        raise RuntimeError('HTTPS_INDEPENDENT_PULL_CONFIG_SHA_MISMATCH')
    hashes = image_hashes(image)
    value.update(tag=tag, imageReference=image, imageDigest=digest, imageConfiguration=config,
        imageHashes=hashes, registryVerification=remote, imagePushed=True,
        pullVerified=True, status='STUDIO_HTTPS_CANDIDATE_CPU_VERIFIED_HARDWARE_PENDING'); save(value)


def persist():
    value = state(); value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if any(item == 'failure' for item in value['stepOutcomes'].values()):
        value['status'] = 'STUDIO_HTTPS_CANDIDATE_BLOCKED'
    for name in ('context', 'testContext'):
        value.pop(name, None)
    phase = os.environ.get('RESULT_PHASE')
    if phase not in ('build', 'pull'):
        raise RuntimeError('HTTPS_BOUNDED_RESULT_PHASE_REQUIRED')
    run_id = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*', run_id):
        raise RuntimeError('HTTPS_RESULT_RUN_ID_REQUIRED')
    relative = Path(NAMESPACE) / 'runs' / run_id
    artifacts = {str(relative / (phase + '.json')): (json.dumps(value, indent=2) + '\n').encode()}
    if phase == 'build' and value.get('testsStatus') == 'PASS':
        for path in (location() / 'mobile').iterdir():
            if path.is_file() and not path.is_symlink() and re.fullmatch(r'[A-Za-z0-9_-]{1,96}\.(?:json|png)', path.name):
                if not 0 < path.stat().st_size <= 12 * 1024**2:
                    raise RuntimeError('HTTPS_BOUNDED_MOBILE_ARTIFACT_REQUIRED')
                artifacts[str(relative / 'mobile' / path.name)] = path.read_bytes()
    for name, raw in artifacts.items():
        if len(raw) > 16 * 1024**2 or (name.endswith('.json') and SENSITIVE.search(raw.decode())):
            raise RuntimeError('HTTPS_SAFE_BOUNDED_EVIDENCE_REQUIRED')
    artifacts[str(relative / (phase + '.SHA256SUMS'))] = ''.join(
        hashlib.sha256(raw).hexdigest() + '  ' + str(Path(name).relative_to(relative)) + '\n'
        for name, raw in sorted(artifacts.items())).encode()
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'])
    for name, raw in artifacts.items():
        destination = REPO / name
        if destination.exists():
            raise RuntimeError('HTTPS_EXISTING_EVIDENCE_OVERWRITE_FORBIDDEN')
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(raw)
    run(['git', 'config', 'user.name', 'github-actions[bot]'])
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    run(['git', 'add', '--', *sorted(artifacts)])
    if sorted(run(['git', 'diff', '--cached', '--name-only']).stdout.splitlines()) != sorted(artifacts):
        raise RuntimeError('HTTPS_BOUNDED_EVIDENCE_COMMIT_REQUIRED')
    run(['git', 'diff', '--cached', '--check'])
    run(['git', 'commit', '-m', 'docs(studio): persist HTTPS ' + phase + ' CPU evidence [skip ci]'])
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'))
    args = parser.parse_args()
    try:
        globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'HTTPS_CI_FAILED'
        value = state(); value.update(status='STUDIO_HTTPS_CANDIDATE_BLOCKED',
            failedPhase=args.phase, reasonCode=code, errorType=type(error).__name__); save(value)
        print(json.dumps({'status': value['status'], 'phase': args.phase, 'reasonCode': code}))
        raise SystemExit(1)
