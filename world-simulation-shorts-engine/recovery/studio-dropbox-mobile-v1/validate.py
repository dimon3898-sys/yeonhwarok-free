#!/usr/bin/env python3
"""Offline source, protection and default-scanner validation. No credentials."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = '5b0478f0aafeb03f4a05ae47f41dcbd154712ee1'
WORKFLOW = '.github/workflows/studio-dropbox-mobile-v1.yml'
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
VENDOR = 'web/vendor/libsodium-wrappers.js'
# Exact exported algorithm names in an unchanged official npm distribution.
# The default rules remain enabled. New/different findings are never accepted.
VENDOR_MATCHES = {
    'crypto_aead_aegis128l_keygen","REDACTED"',
    'crypto_aead_aegis256_keygen","REDACTED"',
    'crypto_aead_chacha20poly1305_ietf_keygen","REDACTED"',
    'crypto_kdf_KEYBYTES","REDACTED"',
    'crypto_kdf_hkdf_sha256_KEYBYTES","REDACTED"',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    data = json.loads((HERE / 'MOBILE_FILES.json').read_bytes())
    if data.get('schema') != 'WORLD_ENGINE_MOBILE_SOURCE_V1' or data.get('protectedParent') != BASE:
        raise RuntimeError('MOBILE_PROVENANCE_REQUIRED')
    rows = data.get('files')
    if not isinstance(rows, dict) or not rows:
        raise RuntimeError('MOBILE_EXPLICIT_FILES_REQUIRED')
    for name, digest in rows.items():
        p = PurePosixPath(name)
        path = HERE / name
        if (p.is_absolute() or str(p) != name or '..' in p.parts or '\\' in name
                or any(node.is_symlink() for node in (path, *path.parents))
                or not path.is_file() or sha(path) != digest):
            raise RuntimeError('MOBILE_SOURCE_HASH_FAILED')
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=name)
    workflow = REPO / WORKFLOW
    if workflow.is_symlink() or sha(workflow) != data.get('workflowSha256'):
        raise RuntimeError('MOBILE_WORKFLOW_HASH_FAILED')
    tracked = subprocess.run(['git', 'diff', '--name-only', BASE, '--'], cwd=REPO,
                             check=True, text=True, capture_output=True).stdout.splitlines()
    prefix = HERE.relative_to(REPO).as_posix() + '/'
    if any(not (name.startswith(prefix) or name == WORKFLOW) for name in tracked):
        raise RuntimeError('MOBILE_PROTECTED_FILE_CHANGED')
    return data, len(rows) + 1


def scan(scanner, data):
    scanner = Path(scanner).resolve()
    if sha(scanner) != SCANNER_SHA:
        raise RuntimeError('MOBILE_SCANNER_HASH_FAILED')
    vendor_manifest = json.loads((HERE / 'VENDOR_MANIFEST.json').read_bytes())
    official = next(package['files'][VENDOR]['sha256'] for package in vendor_manifest['packages']
                    if VENDOR in package['files'])
    if sha(HERE / VENDOR) != official or data['files'].get(VENDOR) != official:
        raise RuntimeError('MOBILE_VENDOR_SOURCE_CHANGED')
    with tempfile.TemporaryDirectory(prefix='world-mobile-scan-') as raw:
        temp = Path(raw)
        scope = temp / 'scope'
        shutil.copytree(HERE, scope / 'extension', ignore=shutil.ignore_patterns('runs', '__pycache__'))
        shutil.copyfile(REPO / WORKFLOW, scope / 'workflow.yml')
        config, ignore, report = temp / 'rules.toml', temp / 'empty-ignore', temp / 'report.json'
        config.write_text('[extend]\nuseDefault = true\n')
        ignore.write_text('')
        result = subprocess.run([str(scanner), 'dir', str(scope), '--config', str(config),
            '--gitleaks-ignore-path', str(ignore), '--ignore-gitleaks-allow', '--redact=100',
            '--report-format=json', '--report-path', str(report), '--no-banner'],
            capture_output=True, timeout=90)
        findings = json.loads(report.read_bytes()) if report.exists() else None
        if result.returncode not in {0, 1} or not isinstance(findings, list):
            raise RuntimeError('MOBILE_SECRET_SCAN_FAILED')
        classified = set()
        for row in findings:
            path = Path(row.get('File', '')).resolve()
            match = row.get('Match')
            if (path != (scope / 'extension' / VENDOR).resolve()
                    or row.get('RuleID') != 'generic-api-key' or row.get('StartLine') != 1
                    or row.get('EndLine') != 1 or match not in VENDOR_MATCHES or match in classified):
                raise RuntimeError('MOBILE_UNRESOLVED_SECRET_FINDING')
            classified.add(match)
        if classified != VENDOR_MATCHES or len(findings) != 5:
            raise RuntimeError('MOBILE_VENDOR_SCANNER_EXPECTATION_CHANGED')
    return {'status': 'PASS', 'findings': 0, 'rawFindings': 5,
            'classifiedVendorFunctionNames': 5, 'defaultRulesChanged': False,
            'scannerSha256': SCANNER_SHA}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scanner', required=True)
    args = parser.parse_args()
    try:
        data, count = sources()
        print(json.dumps({'status': 'PASS', 'files': count, 'protectedChanges': 0,
                          'secretScan': scan(args.scanner, data), 'gpuExecuted': False}, sort_keys=True))
    except Exception as error:
        code = str(error)
        if not code or not all(ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in code):
            code = 'MOBILE_SOURCE_VALIDATION_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
