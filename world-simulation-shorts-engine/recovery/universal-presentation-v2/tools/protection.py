"""Reuse original SHA checks; snapshot every b0d0138 blob and existing caches.

Only this new extension's reports are written. No old source/cache is repaired,
restored, overwritten, initialized or deleted by this tool.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
BASE_COMMIT = 'b0d013832ee38571f9d3dfe685ce63f7083ba90f'
NAMESPACE = HERE.relative_to(ROOT).as_posix() + '/'
BASELINE = HERE / 'reports/PROTECTION_BASELINE.json'
LEGACY = ROOT / 'world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/tools/protection.py'
spec = importlib.util.spec_from_file_location('_up2_preserved_protection', LEGACY)
reused = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reused)
reused.BASE_COMMIT = BASE_COMMIT
reused.NAMESPACE = NAMESPACE
CACHE_ROOTS = [Path('/workspace/universal-data-pipeline-v1-private-20261022'),
               Path('/workspace/exact-65422-capsule-20261020'),
               Path('/workspace/astra-history-p0-research-20261021')]
CHECKOUTS = [Path('/workspace/yeonhwarok-free'), Path('/workspace/world-engine-universal-data-pipeline')]


def write(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_EXCL if exclusive else os.O_TRUNC)
    with os.fdopen(os.open(path, flags, 0o644), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def cache_snapshot():
    result = []
    for root in CACHE_ROOTS:
        rows = []
        if root.exists():
            for parent, dirs, files in os.walk(root, followlinks=False):
                for name in sorted([*dirs, *files]):
                    path = Path(parent) / name
                    value = path.lstat()
                    rows.append({'path': path.relative_to(root).as_posix(), 'bytes': value.st_size,
                                 'inode': value.st_ino, 'mtimeNs': value.st_mtime_ns,
                                 'mode': stat.S_IMODE(value.st_mode), 'uid': value.st_uid,
                                 'kind': 'symlink' if stat.S_ISLNK(value.st_mode) else 'directory' if stat.S_ISDIR(value.st_mode) else 'file'})
        result.append({'root': str(root), 'present': root.exists(), 'entries': sorted(rows, key=lambda item: item['path'])})
    return result


def checkout_snapshot():
    return [{'path': str(path), 'HEAD': reused.git('rev-parse', 'HEAD', cwd=path).decode().strip(),
             'porcelain': reused.git('status', '--porcelain=v1', '--untracked-files=all', cwd=path).decode()}
            for path in CHECKOUTS]


def acquire():
    if reused.git('rev-parse', 'HEAD').decode().strip() != BASE_COMMIT:
        raise RuntimeError('ACQUIRE_REQUIRES_B0D0138_BEFORE_FIRST_COMMIT')
    contract = reused.source_contract()
    protected, errors = reused.check_protected(contract)
    if errors:
        raise RuntimeError('ORIGINAL_307_REQUIRED_SHA_FAILED')
    tracked = reused.tracked_snapshot()
    checkouts = checkout_snapshot()
    if any(row['porcelain'] for row in checkouts):
        raise RuntimeError('PRESERVED_CHECKOUT_NOT_CLEAN')
    result = {'schema': 'WORLD_ENGINE_UP2_PROTECTION_BASELINE_V1', 'baselineCommit': BASE_COMMIT,
              'acquiredAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'sourceManifest': str(reused.SOURCE.relative_to(ROOT)), 'sourceManifestSHA256': reused.SOURCE_SHA,
              'reusedVerifier': str(LEGACY.relative_to(ROOT)), 'reusedVerifierSHA256': reused.sha_file(LEGACY),
              'protected307': protected, 'trackedFiles': tracked, 'trackedCount': len(tracked),
              'checkouts': checkouts, 'cacheMetadata': cache_snapshot(),
              'canonicalPlan': {'operation': 'REUSED_EXISTING_CANONICAL_BYTES_NO_RESTORATION', 'path': str(reused.PLAN)},
              'paidGpuExecuted': False, 'paidApiUsed': False, 'oldFilesWritten': False}
    write(BASELINE, result, exclusive=True)
    return verify('PROTECTION_INITIAL.json')


def verify(filename):
    if Path(filename).name != filename or not filename.endswith('.json'):
        raise ValueError('REPORT_BASENAME_REQUIRED')
    baseline = json.loads(BASELINE.read_bytes())
    contract = reused.source_contract()
    protected, errors = reused.check_protected(contract)
    tracked_errors = []
    for row in baseline['trackedFiles']:
        path = ROOT / row['path']
        try:
            if reused.sha_file(path) != row['sha256'] or path.stat().st_size != row['bytes']:
                tracked_errors.append({'path': row['path'], 'reason': 'BASELINE_BYTES_CHANGED'})
        except (OSError, RuntimeError) as error:
            tracked_errors.append({'path': row['path'], 'reason': str(error)})
    checkout_now = checkout_snapshot()
    cache_now = cache_snapshot()
    cache_changes = []
    for before, after in zip(baseline['cacheMetadata'], cache_now):
        if before != after:
            first = {row['path']: row for row in before['entries']}
            second = {row['path']: row for row in after['entries']}
            names = sorted(set(first) | set(second))
            cache_changes.append({'root': before['root'], 'changedPaths': [name for name in names if first.get(name) != second.get(name)],
                                  'presentBefore': before['present'], 'presentAfter': after['present']})
    changed = reused.git('diff', '--name-only', BASE_COMMIT, '--').decode().splitlines()
    changed += reused.git('ls-files', '--others', '--exclude-standard').decode().splitlines()
    outside = sorted(set(path for path in changed if not path.startswith(NAMESPACE)))
    good = not errors and not tracked_errors and checkout_now == baseline['checkouts'] and not cache_changes and not outside
    result = {'schema': 'WORLD_ENGINE_UP2_PROTECTION_RESULT_V1', 'baselineCommit': BASE_COMMIT,
              'status': 'PASS' if good else 'FAIL', 'checkedAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'protected307': {'status': 'PASS' if not errors else 'FAIL', 'count': len(protected), 'actualBytesVerified': True, 'errors': errors},
              'allBaselineTrackedFiles': {'status': 'PASS' if not tracked_errors else 'FAIL', 'count': len(baseline['trackedFiles']), 'errors': tracked_errors},
              'preservedCheckouts': {'status': 'PASS' if checkout_now == baseline['checkouts'] else 'FAIL', 'current': checkout_now},
              'cacheMetadata': {'status': 'PASS' if not cache_changes else 'FAIL', 'roots': len(cache_now),
                                'entryCount': sum(len(item['entries']) for item in cache_now), 'changes': cache_changes,
                                'contentsReadByThisMetadataCheck': False},
              'changesOutsideNewNamespace': outside, 'existingFinalMediaPreserved': not tracked_errors,
              'oldFilesDeletedOrOverwritten': False if good else None, 'paidGpuExecuted': False, 'paidApiUsed': False}
    write(HERE / 'reports' / filename, result)
    print(json.dumps({'status': result['status'], 'protected': len(protected), 'allTracked': len(baseline['trackedFiles']),
                      'cacheEntries': result['cacheMetadata']['entryCount'], 'cacheChanges': cache_changes,
                      'outside': outside, 'report': str(HERE / 'reports' / filename)}))
    return 0 if good else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--acquire', action='store_true')
    parser.add_argument('--output', default='PROTECTION_CURRENT.json')
    args = parser.parse_args()
    raise SystemExit(acquire() if args.acquire else verify(args.output))
