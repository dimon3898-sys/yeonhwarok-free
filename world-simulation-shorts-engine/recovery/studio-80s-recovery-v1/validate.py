#!/usr/bin/env python3
"""Free, CPU-only recovery tests in an unchanged, immutable existing image.

Never build/push an image, submit a GPU job, access gCube credentials, or read
the operator's retained production files. Container fixtures are synthetic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
TARGET = '/opt/world-engine-studio-cpu-recovery'
PARENT_MANIFEST = '/opt/world-engine-studio-https-proxy-fix/manifest.py'
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
WORKFLOWS = ('.github/workflows/studio-80s-recovery-cpu.yml', '.github/workflows/studio-80s-recovery-v1.yml')
PAYLOAD = ('recover.py', 'policy.py', 'validate.py', 'tests/test_recover.py', 'tests/test_policy.py')
MAX_REPORT_BYTES = 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def command(arguments, *, timeout=900, check=True):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode:
        # Docker/test commands do not receive credentials. Still keep arbitrary
        # child output out of persisted reports; inspect the bounded CI console.
        print(result.stdout[-24000:], end='')
        print(result.stderr[-24000:], end='', file=sys.stderr)
        raise RuntimeError('CPU_RECOVERY_COMMAND_FAILED')
    return result


def location():
    run = os.environ.get('GITHUB_RUN_ID', '') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '')
    if not re.fullmatch(r'[0-9]+-[0-9]+', run):
        raise RuntimeError('CPU_RECOVERY_EXPLICIT_CI_RUN_REQUIRED')
    root = Path(os.environ['RUNNER_TEMP']) / ('studio-80s-cpu-' + run)
    root.mkdir(mode=0o700, exist_ok=True)
    return root


def guard():
    if (os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
            or os.environ.get('GITHUB_REF') != 'refs/heads/development/studio-80s-recovery-20261018'
            or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'
            or os.environ.get('RESULT_RUNNER_LABEL') != 'ubuntu-24.04'
            or not re.fullmatch(r'[a-f0-9]{40}', os.environ.get('GITHUB_SHA', ''))):
        raise RuntimeError('CPU_RECOVERY_FREE_PUBLIC_STANDARD_RUNNER_REQUIRED')
    usage = shutil.disk_usage(os.environ['RUNNER_TEMP'])
    if usage.free < 20 * 1024**3:
        raise RuntimeError('CPU_RECOVERY_TWENTY_GIB_REQUIRED_NO_DELETION')
    driver = command(['docker', 'info', '--format', '{{.Driver}}'], timeout=30).stdout.strip()
    if driver != 'overlay2':
        raise RuntimeError('CPU_RECOVERY_STANDARD_OVERLAY2_BUILDER_REQUIRED')
    return {'status': 'PASS', 'runner': 'ubuntu-24.04', 'publicRepository': True,
            'freeBytesBeforePull': usage.free, 'dockerStorageDriver': driver,
            'existingImagesCachesVolumesDeleted': False, 'imageBuilds': 0, 'imagePushes': 0}


class Counts(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)


def suite_result(patterns):
    start = time.monotonic()
    suite = unittest.TestSuite()
    for pattern in patterns:
        suite.addTests(unittest.defaultTestLoader.discover(str(HERE / 'tests'), pattern=pattern))
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=Counts).run(suite)
    print(output.getvalue(), end='')
    passed = len(result.passed_ids)
    summary = {'status': 'PASS' if result.wasSuccessful() and not result.skipped and passed > 0 else 'FAIL',
               'testsRun': result.testsRun, 'passed': passed, 'failed': len(result.failures),
               'errors': len(result.errors), 'skipped': len(result.skipped),
               'expectedFailures': len(result.expectedFailures), 'elapsedSeconds': round(time.monotonic() - start, 3),
               'testIds': result.passed_ids, 'gpuExecuted': False}
    if summary['status'] != 'PASS' or result.expectedFailures or result.unexpectedSuccesses:
        summary['status'] = 'FAIL'
    return summary


def verify_parent():
    result = command([sys.executable, '-B', PARENT_MANIFEST, '--verify'], timeout=60)
    if len(result.stdout) > MAX_REPORT_BYTES:
        raise RuntimeError('CPU_RECOVERY_PARENT_REPORT_LIMIT')
    value = json.loads(result.stdout)
    https = value.get('parentHttps', {})
    studio = https.get('parentStudio', {})
    if (value.get('status') != 'PASS' or value.get('files') != 12 or https.get('files') != 21
            or studio.get('files') != 51 or studio.get('parentInventoryFiles') != 373
            or value.get('gpuExecuted') is not False):
        raise RuntimeError('CPU_RECOVERY_PROTECTED_PARENT_VERIFICATION_REQUIRED')
    return value


def container_tests(output):
    if (str(HERE) != TARGET or os.geteuid() != 1000 or os.getegid() != 1000
            or Path(output).parent != HERE / 'test-output'):
        raise RuntimeError('CPU_RECOVERY_UID_1000_ISOLATED_OUTPUT_REQUIRED')
    out = Path(output).parent
    out.mkdir(mode=0o700, exist_ok=False)
    evidence = out / 'SYNTHETIC_80S.json'
    os.environ['CPU_RECOVERY_EVIDENCE_PATH'] = str(evidence)
    before = verify_parent()
    result = suite_result(('test_recover.py', 'test_policy.py'))
    after = verify_parent()
    if before != after:
        raise RuntimeError('CPU_RECOVERY_PARENT_CHANGED')
    if result['status'] != 'PASS' or result['testsRun'] != 39:
        raise RuntimeError('CPU_RECOVERY_FOCUSED_CONTAINER_TESTS_REQUIRED')
    proof = json.loads(evidence.read_text()) if evidence.is_file() and evidence.stat().st_size <= MAX_REPORT_BYTES else None
    if (not isinstance(proof, dict) or proof.get('testOnly') is not True or proof.get('gpuExecuted') is not False
            or proof.get('durationSeconds') != 80 or proof.get('frames') != 2400):
        raise RuntimeError('CPU_RECOVERY_REAL_SYNTHETIC_80S_EVIDENCE_REQUIRED')
    report = {'status': 'PASS', 'scope': 'SYNTHETIC_CPU_FIXTURES_IN_IMMUTABLE_IMAGE',
              'executedAtUTC': datetime.now(timezone.utc).isoformat(), 'uid': os.geteuid(), 'gid': os.getegid(),
              'tests': result, 'synthetic80SecondProof': proof,
              'protection': {'before': before, 'after': after, 'unchanged': True},
              'actualWorkloadCacheVerified': False, 'actualNvidiaRenderingVerified': False,
              'actualDropboxExternalDownloadVerified': False, 'gpuExecuted': False, 'paidOperations': 0}
    write_json(output, report)


def test():
    root = location()
    report = {'schema': 'WORLD_ENGINE_STUDIO_80S_CPU_RECOVERY_VALIDATION_V1', 'status': 'RUNNING',
              'sourceCommit': os.environ['GITHUB_SHA'], 'image': IMAGE,
              'actualNvidiaRenderingVerified': False, 'actualWorkloadCacheVerified': False,
              'paidOperations': 0, 'imageBuilds': 0, 'imagePushes': 0}
    try:
        report['preflight'] = guard()
        report['readOnlyCollectorTests'] = suite_result(('test_remote.py',))
        if report['readOnlyCollectorTests']['status'] != 'PASS' or report['readOnlyCollectorTests']['testsRun'] != 10:
            raise RuntimeError('CPU_RECOVERY_FOCUSED_READONLY_TESTS_REQUIRED')
        command(['docker', 'pull', '--platform=linux/amd64', IMAGE], timeout=600)
        image = json.loads(command(['docker', 'image', 'inspect', IMAGE], timeout=30).stdout)[0]
        if IMAGE not in image.get('RepoDigests', []) or image.get('Architecture') != 'amd64' or image.get('Os') != 'linux':
            raise RuntimeError('CPU_RECOVERY_IMMUTABLE_LINUX_AMD64_REQUIRED')
        report['pulledImage'] = {'id': image['Id'], 'repoDigest': IMAGE, 'sizeBytes': image['Size'], 'platform': 'linux/amd64'}
        extension = root / 'extension'
        extension.mkdir(mode=0o700)
        for relative in PAYLOAD:
            path = HERE / relative
            if not path.is_file() or path.is_symlink():
                raise RuntimeError('CPU_RECOVERY_EXPLICIT_SOURCE_REQUIRED')
            target = extension / relative
            target.parent.mkdir(mode=0o700, exist_ok=True, parents=True)
            shutil.copyfile(path, target)
            target.chmod(0o600)
        report['testedSourceFiles'] = {relative: sha(extension / relative) for relative in PAYLOAD}
        # This dedicated, newly-created fixture copy is the only ownership
        # change. Never chmod/chown a checkout, cache, mount or retained job.
        command(['sudo', 'chown', '-R', '1000:1000', str(extension)], timeout=30)
        args = ['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--user=1000:1000', '--pids-limit=256',
                '--memory=4g', '--cpus=2', '--tmpfs=/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=1777',
                '--mount', 'type=bind,src=' + str(extension) + ',dst=' + TARGET,
                '--workdir', TARGET, '--env=PYTHONDONTWRITEBYTECODE=1', '--entrypoint=/usr/bin/python3',
                IMAGE, '-B', TARGET + '/validate.py', 'container-tests', '--output', TARGET + '/test-output/CPU_RESULT.json']
        try:
            result = command(args, timeout=900, check=False)
        finally:
            # Standard hosted runners need not themselves be UID 1000. Return
            # ownership of this fresh synthetic copy only, so the host can
            # read private (0700/0600) fixture evidence without widening modes.
            command(['sudo', 'chown', '-R', str(os.getuid()) + ':' + str(os.getgid()), str(extension)], timeout=30)
        report['containerExitCode'] = result.returncode
        print(result.stdout[-30000:], end='')
        print(result.stderr[-30000:], end='', file=sys.stderr)
        if result.returncode:
            raise RuntimeError('CPU_RECOVERY_IMMUTABLE_CONTAINER_TESTS_FAILED')
        source = extension / 'test-output/CPU_RESULT.json'
        if not source.is_file() or source.stat().st_size > MAX_REPORT_BYTES:
            raise RuntimeError('CPU_RECOVERY_BOUNDED_CONTAINER_REPORT_REQUIRED')
        report['container'] = json.loads(source.read_text())
        if report['container'].get('status') != 'PASS':
            raise RuntimeError('CPU_RECOVERY_CONTAINER_PASS_REQUIRED')
        for relative, digest in report['testedSourceFiles'].items():
            if sha(extension / relative) != digest or sha(HERE / relative) != digest:
                raise RuntimeError('CPU_RECOVERY_TESTED_SOURCE_CHANGED')
        report['status'] = 'PASS'
    except Exception as error:
        report['status'] = 'FAIL'
        code = str(error)
        report['errorCode'] = code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code) else 'CPU_RECOVERY_VALIDATION_FAILED'
        raise
    finally:
        write_json(root / 'CPU_RESULT.json', report)


def secret_scan():
    root = location()
    guard()
    scanner_root = root / 'secret-scan'
    scanner_root.mkdir(mode=0o700, exist_ok=False)
    with urllib.request.urlopen('https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz', timeout=30) as response:
        archive = response.read(32 * 1024**2 + 1)
    if len(archive) > 32 * 1024**2:
        raise RuntimeError('CPU_RECOVERY_SCANNER_ARCHIVE_LIMIT')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        member = tar.getmember('gitleaks')
        if not member.isfile() or not 0 < member.size < 64 * 1024**2:
            raise RuntimeError('CPU_RECOVERY_SCANNER_BINARY_REQUIRED')
        scanner = scanner_root / 'gitleaks'
        scanner.write_bytes(tar.extractfile(member).read())
    if sha(scanner) != SCANNER_SHA:
        raise RuntimeError('CPU_RECOVERY_SCANNER_SHA_MISMATCH')
    scanner.chmod(0o700)
    scope = scanner_root / 'scope'
    shutil.copytree(HERE, scope / 'extension', ignore=shutil.ignore_patterns('runs', 'remote-runs', '__pycache__', '.cpu-*', 'test-output'))
    for relative in WORKFLOWS:
        target = scope / Path(relative).name
        shutil.copyfile(REPO / relative, target)
    config, ignore, findings = scanner_root / 'defaults.toml', scanner_root / 'empty-ignore', scanner_root / 'findings.json'
    config.write_text('[extend]\nuseDefault = true\n')
    ignore.write_text('')
    result = command([str(scanner), 'dir', str(scope), '--config', str(config), '--gitleaks-ignore-path', str(ignore),
                      '--ignore-gitleaks-allow', '--redact=100', '--report-format=json', '--report-path', str(findings), '--no-banner'], check=False)
    observed = json.loads(findings.read_text()) if findings.is_file() and findings.stat().st_size <= MAX_REPORT_BYTES else None
    report = {'status': 'PASS' if result.returncode == 0 and observed == [] else 'FAIL',
              'findings': 0 if observed == [] else None, 'scannerSha256': SCANNER_SHA,
              'scope': 'all new recovery runtime, tests, source, docs and two new workflows; no ignore/allow annotations honored'}
    write_json(root / 'SECRET_SCAN.json', report)
    if report['status'] != 'PASS':
        raise RuntimeError('CPU_RECOVERY_SECRET_SCAN_FAILED')


def bundle():
    root = location()
    files = [root / 'CPU_RESULT.json', root / 'SECRET_SCAN.json']
    for file in files:
        if not file.is_file() or file.stat().st_size > MAX_REPORT_BYTES:
            raise RuntimeError('CPU_RECOVERY_SAFE_REPORT_REQUIRED')
        value = json.loads(file.read_text())
        if value.get('status') != 'PASS':
            raise RuntimeError('CPU_RECOVERY_SUCCESS_REPORTS_REQUIRED')
    (root / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in files))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('report-path=' + str(root) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('test', 'container-tests', 'secret-scan', 'bundle'))
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.action == 'container-tests':
        container_tests(args.output)
    elif args.action == 'test':
        test()
    elif args.action == 'secret-scan':
        secret_scan()
    else:
        bundle()
