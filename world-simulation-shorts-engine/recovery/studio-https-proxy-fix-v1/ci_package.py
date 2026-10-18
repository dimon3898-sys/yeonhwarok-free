#!/usr/bin/env python3
"""Additive proxy-fix packaging, reusing the frozen HTTPS CI implementation.

No gCube deployment, GPU command, paid runner, baseline mutation or cache prune
is performed here. Only new source and bounded safe evidence are persisted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FROZEN_CI = HERE.parent / 'studio-https-bootstrap-v1' / 'ci_package.py'
if hashlib.sha256(FROZEN_CI.read_bytes()).hexdigest() != '93f588a9f1df0763814d42c8842495fd7733dcd3bbb97304c16a264d4cc6b393':
    raise RuntimeError('PROXY_FROZEN_CI_SHA_MISMATCH')
spec = importlib.util.spec_from_file_location('_studio_https_frozen_ci', FROZEN_CI)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

ci.HERE = HERE
ci.NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-https-proxy-fix-v1'
ci.WORKFLOW = '.github/workflows/studio-https-proxy-fix-v1.yml'
ci.BRANCH = 'development/studio-https-proxy-fix-20261018'
ci.BASE_DIGEST = 'sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833'
ci.BASE = ci.IMAGE + '@' + ci.BASE_DIGEST
ci.DEST = '/opt/world-engine-studio-https-proxy-fix'
ci.TAG = re.compile(r'studio-proxy-v1-4589328-[1-9][0-9]*-[1-9][0-9]*\Z')
PARENT_HTTPS_SHA = 'b46b2bff3e8ef5887e1e61b9c0d835d1135b57f2810ddcc94e36e7c461eec665'


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-https-proxy-package-v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


ci.location = location
original_state = ci.state


def state():
    value = original_state()
    value['schema'] = 'WORLD_ENGINE_STUDIO_HTTPS_PROXY_PACKAGE_V1'
    value['status'] = value['status'].replace('STUDIO_HTTPS_CANDIDATE', 'STUDIO_HTTPS_PROXY_CANDIDATE').replace('CPU_VERIFIED_HARDWARE_PENDING', 'CPU_VERIFIED_GCUBE_CONFIRMATION_PENDING')
    value.setdefault('actualGcubeProxyCauseConfirmed', False)
    value.setdefault('actualGcubeRegistrationVerified', False)
    return value


ci.state = state


def preflight():
    value = ci.state()
    value['builder'] = ci.require_free_runner()
    if not ci.COMMIT.fullmatch(os.environ.get('GITHUB_SHA', '')):
        raise RuntimeError('PROXY_SOURCE_COMMIT_REQUIRED')
    value['tag'] = 'studio-proxy-v1-4589328-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not ci.TAG.fullmatch(value['tag']):
        raise RuntimeError('PROXY_UNIQUE_TAG_REQUIRED')
    value['image'] = ci.IMAGE + ':' + value['tag']
    ci.save(value)


def payload_context():
    context = Path(tempfile.mkdtemp(prefix='proxy-payload-', dir=location()))
    payload = context / 'extension'
    payload.mkdir()
    files = sorted(p.name for p in HERE.glob('*.py') if p.name not in {'ci_package.py', 'remote.py'})
    files += sorted(p.relative_to(HERE).as_posix() for p in (HERE / 'web').rglob('*') if p.is_file())
    tests = sorted(p.relative_to(HERE).as_posix() for p in (HERE / 'tests').rglob('*')
                   if p.is_file() and p.name != 'test_remote.py' and p.suffix in ('.py', '.js', '.mjs') and '__pycache__' not in p.parts)
    if not {'proxy_bootstrap.py', 'proxy_server.py', 'proxy_policy.py', 'parent.py', 'manifest.py'} <= set(files) or not tests:
        raise RuntimeError('PROXY_CONNECTED_RUNTIME_AND_TESTS_REQUIRED')
    for name in (*files, *tests):
        source = HERE / name
        if (any(p.is_symlink() for p in (source, *source.parents))
                or not 0 < source.stat().st_size <= 4 * 1024**2):
            raise RuntimeError('PROXY_BOUNDED_REGULAR_PAYLOAD_REQUIRED')
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest = {
        'schema': 'WORLD_ENGINE_STUDIO_HTTPS_PROXY_FILES_V1',
        'profileId': 'STUDIO_HTTPS_PROXY_FIX_V1',
        'sourceCommit': os.environ['GITHUB_SHA'],
        'parentImage': ci.BASE,
        'parentHttpsManifestSha256': PARENT_HTTPS_SHA,
        'files': {name: ci.sha(payload / name) for name in sorted(files)},
        'testFiles': {name: ci.sha(payload / name) for name in tests},
    }
    (payload / 'PROXY_EXTENSION_FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    return context


ci.payload_context = payload_context


def image_hashes(image, context=None):
    result = ci.run(ci.container(image, context=context) + [ci.DEST + '/manifest.py', '--verify'])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('PROXY_SOURCE_REPORT_REQUIRED') from None
    generated = context if context is not None else payload_context()
    parent = report.get('parentHttps', {})
    studio = parent.get('parentStudio', {})
    if (report.get('status') != 'PASS'
            or report.get('manifestSha256') != ci.sha(generated / 'extension/PROXY_EXTENSION_FILES.json')
            or report.get('sourceCommit') != os.environ['GITHUB_SHA']
            or parent.get('manifestSha256') != PARENT_HTTPS_SHA
            or parent.get('files') != 21
            or studio.get('manifestSha256') != ci.PARENT_MANIFEST_SHA
            or studio.get('files') != 51 or studio.get('parentInventoryFiles') != 373
            or report.get('gpuExecuted') is not False):
        raise RuntimeError('PROXY_FROZEN_SOURCE_VERIFICATION_FAILED')
    return report


ci.image_hashes = image_hashes


def inspect_image(image):
    row = json.loads(ci.run(['docker', 'image', 'inspect', image]).stdout)[0]
    config = row.get('Config', {})
    labels = config.get('Labels', {})
    entrypoint = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', ci.DEST + '/proxy_bootstrap.py']
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64'
            or config.get('Entrypoint') != entrypoint
            or labels.get('world-engine.studio-proxy.parent-digest') != ci.BASE_DIGEST
            or labels.get('world-engine.studio-proxy.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('PROXY_IMAGE_PROVENANCE_REQUIRED')
    if set(item.partition('=')[0] for item in config.get('Env', [])) & {
            'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
            'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}:
        raise RuntimeError('PROXY_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('PROXY_SERVICE_HEALTH_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
            'entrypoint': entrypoint, 'healthcheck': config['Healthcheck'],
            'platform': 'linux/amd64', 'secretEnvironmentPresent': False}


ci.inspect_image = inspect_image


def stage():
    value = ci.state()
    if value.get('testsStatus') != 'PASS':
        raise RuntimeError('PROXY_FOCUSED_CONTAINER_MOBILE_PASS_REQUIRED')
    context = payload_context()
    frozen_manifest = Path(value['testContext']) / 'extension/PROXY_EXTENSION_FILES.json'
    if (context / 'extension/PROXY_EXTENSION_FILES.json').read_bytes() != frozen_manifest.read_bytes():
        raise RuntimeError('PROXY_TESTED_CONTEXT_CHANGED')
    value.update(context=str(context), extensionManifestSha256=ci.sha(frozen_manifest),
                 dockerfileSha256=ci.sha(context / 'Dockerfile'))
    ci.save(value)


ci.stage = stage


def build():
    value = ci.state()
    ci.require_free_runner()
    if value.get('testsStatus') != 'PASS' or not value.get('context'):
        raise RuntimeError('PROXY_TESTED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (ci.sha(context / 'extension/PROXY_EXTENSION_FILES.json') != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('PROXY_FROZEN_CONTEXT_SHA_REQUIRED')
    command = ['docker', 'build', '--platform=linux/amd64', '--file', str(context / 'Dockerfile'),
               '--label', 'world-engine.studio-proxy.source-revision=' + os.environ['GITHUB_SHA'],
               '--tag', value['image'], str(context)]
    result = ci.run(command, timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode,
                           'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    ci.save(value)
    if result.returncode:
        raise RuntimeError('PROXY_IMAGE_BUILD_FAILED')
    value = ci.state()
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    ci.save(value)


ci.build = build


def test():
    ci.require_free_runner()
    ci.run(['docker', 'pull', ci.BASE], timeout=900)
    context = payload_context()
    value = ci.state()
    value['testContext'] = str(context)
    value['originalAndExtensionSourceHashes'] = image_hashes(ci.BASE, context)
    ci.save(value)
    code = ("import sys,unittest;sys.path.insert(0,'" + ci.DEST + "');"
            "s=unittest.defaultTestLoader.discover('" + ci.DEST + "/tests',pattern='test_*.py');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);"
            "raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
    ci.record('focused-proxy-python', ci.container(ci.BASE, context=context) + ['-c', ci.uid_code(code)])
    probe_output = location() / 'container-probe'
    probe_output.mkdir(mode=0o700, exist_ok=True)
    result = ci.run([sys.executable, '-B', str(HERE / 'tests/container_probe.py'),
        '--image', ci.BASE, '--extension', str(context / 'extension'),
        '--output', str(probe_output / 'CONTAINER_REPORT.json')], timeout=600, check=False)
    value = ci.state()
    value['containerProbe'] = {'exitCode': result.returncode,
        'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    if (probe_output / 'CONTAINER_REPORT.json').is_file():
        value['containerProbe']['report'] = json.loads((probe_output / 'CONTAINER_REPORT.json').read_text())
    ci.save(value)
    if result.returncode or value['containerProbe'].get('report', {}).get('status') != 'PASS':
        raise RuntimeError('PROXY_ACTUAL_CONTAINER_STARTUP_FAILED')
    evidence = location() / 'mobile'
    evidence.mkdir(mode=0o777, exist_ok=True)
    evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + ci.DEST + "/tests/mobile_probe.mjs']).returncode)"
    result = ci.record('actual-mobile-proxy-chromium',
                       ci.container(ci.BASE, context=context, evidence=evidence) + ['-c', ci.uid_code(code)])
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('PROXY_MOBILE_REPORT_REQUIRED') from None
    if (report.get('status') != 'PASS' or report.get('gpuExecuted') is not False
            or report.get('actualChromium') is not True
            or not isinstance(report.get('passCount'), int) or report['passCount'] < 1):
        raise RuntimeError('PROXY_ACTUAL_MOBILE_CPU_PASS_REQUIRED')
    value = ci.state()
    value.update(mobileProbe=report, testsStatus='PASS')
    ci.save(value)


ci.test = test


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'))
    arguments = parser.parse_args()
    try:
        (preflight if arguments.phase == 'preflight' else getattr(ci, arguments.phase))()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'PROXY_CI_FAILED'
        value = ci.state()
        value.update(status='STUDIO_HTTPS_PROXY_CANDIDATE_BLOCKED', failedPhase=arguments.phase,
                     reasonCode=code, errorType=type(error).__name__)
        ci.save(value)
        print(json.dumps({'status': value['status'], 'phase': arguments.phase, 'reasonCode': code}))
        raise SystemExit(1)
