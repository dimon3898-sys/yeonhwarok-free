"""Read protected bytes/old cache metadata; write receipts only in this new namespace.

The 307-file baseline is inherited from the previously pinned audit. Prior recovery
artifacts are independently hash-bound too. No credential-cache contents are read.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
BASE = '3913ad8e90885c769cdccc91f396072d83e356f2'
PIN = '08d6ae6deab6e0fb26a3d32dae439e652957206664d7bf783976fa33bdb8be76'
PRIOR_PIN = 'cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e'
TEXT_SUFFIXES = {'.py', '.mjs', '.js', '.json', '.md', '.csv', '.txt', '.html', '.yml', '.yaml'}
PATTERNS = [
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    rb'gh[pousr]_[A-Za-z0-9]{30,}',
    rb'github_pat_[A-Za-z0-9_]{40,}',
    rb'\bAKIA[A-Z0-9]{16}\b',
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(stage='CURRENT', report='reports/PROTECTION_CURRENT.json'):
    output = (HERE / report).resolve()
    if not output.is_relative_to(HERE / 'reports') or output.name == 'PROTECTION_BASELINE.json':
        raise ValueError('PROTECTION_REPORT_LOCATION_REJECTED')
    raw = (HERE / 'reports/PROTECTION_BASELINE.json').read_bytes()
    if sha(raw) != PIN:
        raise ValueError('PROTECTION_BASELINE_BYTES_CHANGED')
    baseline = json.loads(raw)
    errors = []
    prior = REPO / baseline['priorBaselinePath']
    if sha(prior.read_bytes()) != PRIOR_PIN:
        errors.append({'kind': 'PRIOR_BASELINE', 'error': 'BYTE_CHANGE'})

    def check(file, row, kind):
        if file.is_symlink() or not file.is_file():
            errors.append({'kind': kind, 'path': str(file), 'error': 'MISSING_OR_SYMLINK'})
            return
        if file.stat().st_size != row['bytes'] or sha(file.read_bytes()) != row['sha256']:
            errors.append({'kind': kind, 'path': str(file), 'error': 'BYTE_CHANGE'})

    for row in baseline['protectedFiles']:
        f = REPO / row['path'] if row['scope'] == 'REPOSITORY' else Path(row['resolvedAuditPath'])
        check(f, row, 'PROTECTED')
    for name, namespace in baseline['existingNamespaces'].items():
        for row in namespace['files']:
            check(REPO / row['path'], row, 'OLD_NAMESPACE')
    metadata_count = 0
    for snapshot in baseline['existingCacheMetadataSnapshots']:
        root = Path(snapshot['root'])
        for row in snapshot['files']:
            f = root / row['path']
            metadata_count += 1
            if not f.exists() and not f.is_symlink():
                errors.append({'kind': 'OLD_CACHE_METADATA', 'path': str(f), 'error': 'REMOVED'})
                continue
            stat = f.lstat()
            observed = (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_mode, f.is_symlink())
            expected = (row['bytes'], row['mtimeNS'], row['inode'], row['mode'], row['symlink'])
            if observed != expected:
                errors.append({'kind': 'OLD_CACHE_METADATA', 'path': str(f), 'error': 'METADATA_CHANGED'})

    prefix = HERE.relative_to(REPO).as_posix() + '/'
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    outside = sorted(set(n for n in changed + untracked if not n.startswith(prefix)))
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=REPO, text=True).strip()
    if branch != baseline['branch']:
        errors.append({'kind': 'BRANCH', 'error': 'UNEXPECTED_BRANCH', 'observed': branch})

    findings = []
    text_checked = 0
    zip_checked = 0

    def scan(data, name):
        if any(re.search(pattern, data) for pattern in PATTERNS):
            findings.append({'path': name, 'error': 'STRONG_SECRET_PATTERN'})

    for f in sorted(HERE.rglob('*')):
        if not f.is_file() or f.is_symlink() or any(n in f.relative_to(HERE).parts for n in ('captures', '__pycache__')):
            continue
        name = f.relative_to(HERE).as_posix()
        if f.suffix in TEXT_SUFFIXES:
            text_checked += 1
            scan(f.read_bytes(), name)
        elif f.suffix == '.zip':
            with zipfile.ZipFile(f) as archive:
                for entry in archive.infolist():
                    if not entry.is_dir() and Path(entry.filename).suffix in TEXT_SUFFIXES:
                        zip_checked += 1
                        scan(archive.read(entry), name + '!' + entry.filename)

    result = {
        'schema': 'WORLD_ENGINE_G2_FINAL_RECOVERY_PROTECTION_V1',
        'stage': stage, 'checkedAtUTC': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS' if not (errors or outside or findings) else 'FAIL',
        'baselineCommit': BASE, 'branch': branch, 'baselineSHA256': PIN,
        'priorBaselineSHA256': PRIOR_PIN,
        'protectedUniqueFiles': len(baseline['protectedFiles']),
        'protectedFilesChanged': sum(e['kind'] == 'PROTECTED' for e in errors),
        'oldNamespaceFilesVerified': sum(len(v['files']) for v in baseline['existingNamespaces'].values()),
        'oldCacheFilesMetadataVerified': metadata_count,
        'errors': errors, 'outsideNamespaceChanges': outside,
        'secretScan': {'strongPatternTextFilesChecked': text_checked,
                       'strongPatternZipTextPayloadsChecked': zip_checked,
                       'findings': findings,
                       'sensitiveOldCacheContentsRead': False},
        'existingSourceAssetCacheDeletionPerformed': False,
        'paidGpuExecuted': False, 'finalPromoted': False,
    }
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'stage', 'protectedUniqueFiles',
          'protectedFilesChanged', 'oldNamespaceFilesVerified', 'oldCacheFilesMetadataVerified',
          'outsideNamespaceChanges')}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', default='CURRENT')
    parser.add_argument('--report', default='reports/PROTECTION_CURRENT.json')
    args = parser.parse_args()
    result = verify(args.stage, args.report)
    if result['status'] != 'PASS':
        raise SystemExit(1)
