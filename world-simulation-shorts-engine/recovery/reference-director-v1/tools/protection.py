"""Read-only preservation gate for every pinned 82854af file and existing caches.

Reuses original 307-file verification, never restores or writes old sources.
Only writes new reference-director-v1 reports. Run with Python -B.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
import time

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
BASE_COMMIT = '82854af429d09aebb4b31c2f168e2f0ddc9560c9'
NAMESPACE = HERE.relative_to(ROOT).as_posix() + '/'
BASELINE = HERE / 'reports/PROTECTION_BASELINE.json'
LEGACY = ROOT / 'world-simulation-shorts-engine/recovery/universal-presentation-v2/tools/protection.py'
spec = importlib.util.spec_from_file_location('_rdv1_preserved_protection', LEGACY)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.HERE = HERE
legacy.ROOT = ROOT
legacy.BASE_COMMIT = BASE_COMMIT
legacy.NAMESPACE = NAMESPACE
legacy.BASELINE = BASELINE
legacy.reused.BASE_COMMIT = BASE_COMMIT
legacy.reused.NAMESPACE = NAMESPACE
legacy.CACHE_ROOTS += [Path('/workspace/universal-presentation-v2-private-20261022')]
legacy.CHECKOUTS += [Path('/workspace/world-engine-universal-presentation')]


def acquire():
    if legacy.reused.git('rev-parse', 'HEAD').decode().strip() != BASE_COMMIT:
        raise RuntimeError('ACQUIRE_REQUIRES_PINNED_82854AF_BEFORE_FIRST_COMMIT')
    source = legacy.reused.source_contract()
    protected, errors = legacy.reused.check_protected(source)
    if errors:
        raise RuntimeError('ORIGINAL_307_REQUIRED_SHA_FAILED')
    tracked = legacy.reused.tracked_snapshot()
    checkouts = legacy.checkout_snapshot()
    if any(row['porcelain'] for row in checkouts):
        raise RuntimeError('PRESERVED_CHECKOUT_NOT_CLEAN')
    value = {
        'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_PROTECTION_BASELINE_V1',
        'baselineCommit': BASE_COMMIT,
        'acquiredAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sourceManifest': legacy.reused.SOURCE.relative_to(ROOT).as_posix(),
        'sourceManifestSHA256': legacy.reused.SOURCE_SHA,
        'reusedVerifier': LEGACY.relative_to(ROOT).as_posix(),
        'reusedVerifierSHA256': legacy.reused.sha_file(LEGACY),
        'protected307': protected,
        'trackedFiles': tracked, 'trackedCount': len(tracked),
        'checkouts': checkouts, 'cacheMetadata': legacy.cache_snapshot(),
        'canonicalPlan': {'operation': 'READ_EXISTING_BYTES_NO_RESTORATION',
                          'path': str(legacy.reused.PLAN)},
        'oldFilesWritten': False, 'paidGpuExecuted': False, 'paidApiUsed': False,
    }
    legacy.write(BASELINE, value, exclusive=True)
    return legacy.verify('PROTECTION_INITIAL.json')


def verify(filename):
    return legacy.verify(filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--acquire', action='store_true')
    parser.add_argument('--output', default='PROTECTION_CURRENT.json')
    args = parser.parse_args()
    raise SystemExit(acquire() if args.acquire else verify(args.output))
