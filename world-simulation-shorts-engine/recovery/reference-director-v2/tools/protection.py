"""Preserve the immutable 307 contract; record one explicitly authorized change.

Only reports/backups in the new namespace are written. Original manifests,
source files, caches and prior worktrees are never restored or updated here.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
BASE_COMMIT = '5cc9b98c628324814e1e63f9d0f8c6254ee84174'
NAMESPACE = HERE.relative_to(ROOT).as_posix() + '/'
ALLOWED = 'world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs'
ORIGINAL_SHA = 'e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38'
BASELINE = HERE / 'reports/PROTECTION_BASELINE.json'
BACKUP = HERE / 'backups/renderer.5cc9b98.original.mjs'
AUTHORIZATION_SOURCE = Path('/workspace/attachments/87137ec0-621f-4afb-b76b-f48c9cd2a39b/WORLD_ENGINE_NEXT_CODEX_INSTRUCTION.txt')
AUTHORIZATION_SHA = '166b980f02c6ccf8fdecf51b79a8412560a565e8802ba81cb4bc8821268d6142'
LEGACY = ROOT / 'world-simulation-shorts-engine/recovery/universal-presentation-v2/tools/protection.py'
spec = importlib.util.spec_from_file_location('_rd2_preserved_protection', LEGACY)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
reused = legacy.reused
reused.BASE_COMMIT = BASE_COMMIT
reused.NAMESPACE = NAMESPACE
legacy.CACHE_ROOTS += [Path('/workspace/universal-presentation-v2-private-20261022'),
                       Path('/workspace/reference-director-v1-private-20261022')]
legacy.CHECKOUTS += [Path('/workspace/world-engine-universal-presentation'),
                     Path('/workspace/world-engine-reference-director')]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o644), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def renderer_diff(original, current):
    return ''.join(difflib.unified_diff(original.decode().splitlines(True),
        current.decode().splitlines(True), fromfile=ALLOWED + '@' + BASE_COMMIT,
        tofile=ALLOWED + '@current'))


def acquire():
    if reused.git('rev-parse', 'HEAD').decode().strip() != BASE_COMMIT:
        raise RuntimeError('R2_ACQUIRE_REQUIRES_PINNED_5CC9B98')
    source = reused.source_contract()
    protected, errors = reused.check_protected(source)
    if errors:
        raise RuntimeError('R2_ORIGINAL_307_HASH_GATE_FAILED')
    renderer = ROOT / ALLOWED
    original = renderer.read_bytes()
    if digest(original) != ORIGINAL_SHA or original != reused.git('show', BASE_COMMIT + ':' + ALLOWED):
        raise RuntimeError('R2_RENDERER_BACKUP_REQUIRES_ORIGINAL_BYTES')
    authorization = AUTHORIZATION_SOURCE.read_bytes()
    if digest(authorization) != AUTHORIZATION_SHA:
        raise RuntimeError('R2_UPLOADED_AUTHORIZATION_CHANGED')
    tracked = reused.tracked_snapshot()
    checkouts = legacy.checkout_snapshot()
    if any(row['porcelain'] for row in checkouts):
        raise RuntimeError('R2_OLD_WORKTREE_NOT_CLEAN')
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    with BACKUP.open('xb') as stream:
        stream.write(original)
    BACKUP.chmod(0o444)
    authfile = HERE / 'authorization/WORLD_ENGINE_NEXT_CODEX_INSTRUCTION.txt'
    authfile.parent.mkdir(parents=True, exist_ok=True)
    with authfile.open('xb') as stream:
        stream.write(authorization)
    data = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_PROTECTION_BASELINE_V2',
        'baselineCommit': BASE_COMMIT, 'acquiredAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sourceManifest': reused.SOURCE.relative_to(ROOT).as_posix(),
        'sourceManifestSHA256': reused.SOURCE_SHA,
        'originalProtected307': protected, 'originalProtectedHashContractUpdated': False,
        'trackedFiles': tracked, 'trackedCount': len(tracked),
        'checkouts': checkouts, 'cacheMetadata': legacy.cache_snapshot(),
        'allowedModification': {'path': ALLOWED, 'originalSHA256': ORIGINAL_SHA,
            'originalBytes': len(original), 'backupPath': BACKUP.relative_to(ROOT).as_posix(),
            'backupSHA256': digest(original), 'backupMode': '0444',
            'authorizationFile': authfile.relative_to(ROOT).as_posix(),
            'authorizationSHA256': AUTHORIZATION_SHA,
            'scope': 'Opt-in shared map similarity/forward/inverse/terrain sampling/source envelope only; all default/globe/admission behavior retained'},
        'paidGpuOrApiUsed': False}
    write_json(BASELINE, data)
    return verify('PROTECTION_INITIAL.json', require_original=True)


def verify(filename, *, require_original=False):
    if not re.fullmatch(r'[A-Z0-9_]+\.json', filename):
        raise ValueError('R2_REPORT_BASENAME_REQUIRED')
    baseline = json.loads(BASELINE.read_bytes())
    if reused.sha_file(BACKUP) != ORIGINAL_SHA:
        raise RuntimeError('R2_ORIGINAL_RENDERER_BACKUP_CHANGED')
    source = reused.source_contract()
    protected, protected_errors = reused.check_protected(source)
    authorized, forbidden_protected = [], []
    for row in protected_errors:
        if row['path'] == ALLOWED and row.get('actualSHA256') and not require_original:
            authorized.append({**row, 'status': 'EXPLICIT_AUTHORIZED_MODIFICATION',
                'originalHashRetained': True})
        else:
            forbidden_protected.append(row)
    tracked_errors, authorized_tracked = [], []
    for row in baseline['trackedFiles']:
        file = ROOT / row['path']
        try:
            actual = reused.sha_file(file)
            if actual != row['sha256'] or file.stat().st_size != row['bytes']:
                change = {'path': row['path'], 'originalSHA256': row['sha256'],
                    'actualSHA256': actual, 'originalBytes': row['bytes'], 'actualBytes': file.stat().st_size}
                (authorized_tracked if row['path'] == ALLOWED and not require_original else tracked_errors).append(change)
        except (OSError, RuntimeError) as error:
            tracked_errors.append({'path': row['path'], 'error': str(error)})
    current_renderer = (ROOT / ALLOWED).read_bytes()
    diff = renderer_diff(BACKUP.read_bytes(), current_renderer)
    diffname = Path(filename).stem + '_RENDERER.patch'
    diffpath = HERE / 'reports' / diffname
    with diffpath.open('x') as stream:
        stream.write(diff)
    checkouts = legacy.checkout_snapshot()
    cache = legacy.cache_snapshot()
    cache_changes = []
    for before, after in zip(baseline['cacheMetadata'], cache):
        if before != after:
            a = {row['path']: row for row in before['entries']}
            b = {row['path']: row for row in after['entries']}
            cache_changes.append({'root': before['root'], 'changedPaths': [p for p in sorted(a.keys() | b.keys()) if a.get(p) != b.get(p)]})
    changes = reused.git('diff', '--name-only', BASE_COMMIT, '--').decode().splitlines()
    changes += reused.git('ls-files', '--others', '--exclude-standard').decode().splitlines()
    outside = sorted(set(p for p in changes if not p.startswith(NAMESPACE) and p != ALLOWED))
    good = not forbidden_protected and not tracked_errors and checkouts == baseline['checkouts'] and not cache_changes and not outside
    status = 'PASS_WITH_EXPLICIT_AUTHORIZED_RENDERER_CHANGE' if good and authorized else 'PASS' if good else 'FAIL'
    result = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_PROTECTION_RESULT_V2',
        'baselineCommit': BASE_COMMIT, 'status': status,
        'checkedAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'originalProtectedHashContractUpdated': False,
        'protected307': {'count': len(protected), 'unchangedCount': len(protected) - len(protected_errors),
            'allOriginalSHAEqual': not protected_errors, 'authorizedModifiedCount': len(authorized),
            'authorizedModifications': authorized, 'forbiddenChanges': forbidden_protected},
        'baselineTrackedFiles': {'count': len(baseline['trackedFiles']),
            'unchangedCount': len(baseline['trackedFiles']) - len(authorized_tracked) - len(tracked_errors),
            'authorizedModifications': authorized_tracked, 'forbiddenChanges': tracked_errors},
        'renderer': {'path': ALLOWED, 'originalSHA256': ORIGINAL_SHA,
            'modifiedSHA256': digest(current_renderer), 'modifiedBytes': len(current_renderer),
            'diffPath': diffpath.relative_to(ROOT).as_posix(), 'diffSHA256': digest(diff.encode()),
            'backupSHA256Matched': True, 'backupMode': oct(stat.S_IMODE(BACKUP.stat().st_mode)),
            'authorizationSHA256': AUTHORIZATION_SHA},
        'oldWorktrees': {'unchanged': checkouts == baseline['checkouts'], 'current': checkouts},
        'cacheMetadata': {'unchanged': not cache_changes, 'roots': len(cache),
            'entryCount': sum(len(r['entries']) for r in cache), 'changes': cache_changes,
            'cacheContentsRehashed': False},
        'forbiddenChangesOutsideNewNamespace': outside,
        'featureOrPixelPassClaimedByProtectionTool': False,
        'semanticScopeRequiresPatchReviewAndPixelRegression': True,
        'paidGpuOrApiUsed': False}
    write_json(HERE / 'reports' / filename, result)
    print(json.dumps({'status': status, 'protectedUnchanged': result['protected307']['unchangedCount'],
        'authorizedProtectedChanges': len(authorized), 'allTracked': len(baseline['trackedFiles']),
        'oldWorktreesUnchanged': result['oldWorktrees']['unchanged'], 'cacheChanges': cache_changes,
        'outside': outside, 'report': filename}))
    return 0 if good else 1


def proposal(path, report):
    baseline = json.loads(BASELINE.read_bytes())
    if reused.sha_file(ROOT / ALLOWED) != ORIGINAL_SHA:
        raise RuntimeError('R2_FIRST_PROPOSAL_MUST_PRECEDE_PROTECTED_CHANGE')
    if reused.sha_file(BACKUP) != ORIGINAL_SHA:
        raise RuntimeError('R2_ORIGINAL_BACKUP_CHANGED')
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(HERE):
        raise RuntimeError('R2_CANDIDATE_MUST_BE_NEW_NAMESPACE_FILE')
    if not re.fullmatch(r'[A-Z0-9_]+', report):
        raise RuntimeError('R2_SAFE_PROPOSAL_REPORT_NAME_REQUIRED')
    raw = candidate.read_bytes()
    diff = renderer_diff(BACKUP.read_bytes(), raw)
    target = HERE / 'reports' / (report + '.patch')
    with target.open('x') as stream:
        stream.write(diff)
    data = {'schema': 'WORLD_ENGINE_REFERENCE_RENDERER_PRE_CHANGE_PROPOSAL_V1',
        'baselineCommit': BASE_COMMIT, 'targetPath': ALLOWED,
        'candidatePath': candidate.relative_to(ROOT).as_posix(),
        'originalSHA256': ORIGINAL_SHA, 'candidateSHA256': digest(raw),
        'originalBytes': baseline['allowedModification']['originalBytes'], 'candidateBytes': len(raw),
        'diffPath': target.relative_to(ROOT).as_posix(), 'diffSHA256': digest(diff.encode()),
        'protectedFileStillOriginal': True, 'original307ManifestChanged': False,
        'approvalAlreadyProvidedInUserAttachment': True, 'authorizationSHA256': AUTHORIZATION_SHA,
        'rollback': 'The immutable backup can be reviewed against the original Git blob; this tool never restores or overwrites the live renderer.'}
    write_json(HERE / 'reports' / (report + '.json'), data)
    print(json.dumps(data))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--acquire', action='store_true')
    group.add_argument('--proposal', type=Path)
    parser.add_argument('--output', default='PROTECTION_CURRENT.json')
    parser.add_argument('--proposal-report', default='RENDERER_PRE_CHANGE_PROPOSAL')
    parser.add_argument('--require-original', action='store_true')
    args = parser.parse_args()
    raise SystemExit(acquire() if args.acquire else proposal(args.proposal, args.proposal_report)
        if args.proposal else verify(args.output, require_original=args.require_original))
