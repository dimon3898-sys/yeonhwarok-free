"""Read-only checks against the original 307-file contract and every baseline Git file.

Only writes this task's own reports. Does not repair, delete, reset or alter sources.
The generated canonical Plan is restored with the existing inert source preparer.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
BASE_COMMIT = 'e39969cbc76a071d34a38440d9551425e6d5e545'
NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/'
SOURCE = ROOT / 'world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/reports/PROTECTION_BASELINE.json'
SOURCE_SHA = 'cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e'
OLD_CHECKOUT = Path('/workspace/yeonhwarok-free')
PLAN = Path('/workspace/universal-data-pipeline-v1-private-20261022/original-source-replay/PLAN.json')
BASELINE = HERE / 'reports/PROTECTION_BASELINE.json'


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', '-C', str(cwd), *args])


def sha_file(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'NONREGULAR_OR_MISSING: {path}')
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value, *, exclusive=False):
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    with os.fdopen(os.open(path, flags, 0o644), 'w') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n')


def source_contract():
    if sha_file(SOURCE) != SOURCE_SHA:
        raise RuntimeError('ORIGINAL_PROTECTION_MANIFEST_CHANGED')
    source = json.loads(SOURCE.read_bytes())
    if len(source['protectedFiles']) != 307:
        raise RuntimeError('ORIGINAL_PROTECTION_COUNT_CHANGED')
    return source


def check_protected(source):
    rows, errors = [], []
    for entry in source['protectedFiles']:
        if entry['scope'] == 'REPOSITORY':
            path = ROOT / entry['path']
        elif entry['scope'] == 'GENERATED_EXTERNAL' and entry['path'] == '@original-canonical-replay/PLAN.json':
            path = PLAN
        else:
            raise RuntimeError('UNSUPPORTED_PROTECTED_SCOPE')
        row = {'path': entry['path'], 'scope': entry['scope'], 'expectedSHA256': entry['sha256'],
               'expectedBytes': entry['bytes'], 'resolvedAuditPath': str(path)}
        try:
            row.update(actualSHA256=sha_file(path), actualBytes=path.stat().st_size)
            row['status'] = 'PASS' if (row['actualSHA256'] == entry['sha256'] and
                                      row['actualBytes'] == entry['bytes']) else 'FAIL'
        except (OSError, RuntimeError) as error:
            row.update(status='FAIL', error=str(error))
        rows.append(row)
        if row['status'] != 'PASS':
            errors.append(row)
    return rows, errors


def checkout_state():
    return {'path': str(OLD_CHECKOUT), 'HEAD': git('rev-parse', 'HEAD', cwd=OLD_CHECKOUT).decode().strip(),
            'porcelain': git('status', '--porcelain=v1', '--untracked-files=all', cwd=OLD_CHECKOUT).decode()}


def tracked_snapshot():
    rows = []
    for record in git('ls-tree', '-r', '-z', BASE_COMMIT).split(b'\0'):
        if not record:
            continue
        header, raw_path = record.split(b'\t', 1)
        mode, kind, oid = header.decode().split()
        name = raw_path.decode()
        path = ROOT / name
        if kind != 'blob' or path.is_symlink() or not path.is_file():
            raise RuntimeError(f'BASELINE_NOT_REGULAR_BLOB: {name}')
        # git hash-object is read-only without -w. It proves actual bytes equal the pinned blob.
        actual_oid = git('hash-object', '--', name).decode().strip()
        if actual_oid != oid:
            raise RuntimeError(f'BASELINE_ACTUAL_BYTES_DO_NOT_MATCH_GIT: {name}')
        rows.append({'path': name, 'sha256': sha_file(path), 'bytes': path.stat().st_size,
                     'gitBlobSHA1': oid, 'gitMode': mode})
    return rows


def acquire():
    source = source_contract()
    protected, errors = check_protected(source)
    if errors:
        raise RuntimeError('MANDATORY_307_PROTECTION_GATE_FAILED')
    if git('rev-parse', 'HEAD').decode().strip() != BASE_COMMIT:
        raise RuntimeError('BASELINE_ACQUISITION_MUST_PRECEDE_TASK_COMMITS')
    tracked = tracked_snapshot()
    old = checkout_state()
    if old['porcelain']:
        raise RuntimeError('ORIGINAL_CHECKOUT_NOT_CLEAN')
    baseline = {'schema': 'WORLD_ENGINE_UDP_PROTECTION_BASELINE_V1', 'baselineCommit': BASE_COMMIT,
                'acquiredAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'sourceManifest': str(SOURCE.relative_to(ROOT)), 'sourceManifestSHA256': SOURCE_SHA,
                'actualProtected307': protected, 'trackedFiles': tracked,
                'trackedCount': len(tracked), 'originalCheckout': old,
                'restoration': {'path': str(PLAN), 'method': 'EXISTING_INERT_PREPARE_SOURCE_PREVIEW',
                    'generatedFromPreservedTrackedSources': True, 'newDataInvented': False,
                    'existingFilesOverwritten': False, 'renderStarted': False},
                'generatedAliasesNotIncludedIn307': len(source['generatedAliases']),
                'gpuExecuted': False, 'paidWorkExecuted': False}
    write_json(BASELINE, baseline, exclusive=True)
    return verify('PROTECTION_INITIAL.json')


def verify(output='PROTECTION_CURRENT.json'):
    source = source_contract()
    baseline = json.loads(BASELINE.read_bytes())
    rows, errors = check_protected(source)
    tracked_errors = []
    for entry in baseline['trackedFiles']:
        path = ROOT / entry['path']
        try:
            actual = sha_file(path)
            if actual != entry['sha256'] or path.stat().st_size != entry['bytes']:
                tracked_errors.append({'path': entry['path'], 'reason': 'BASELINE_BYTES_CHANGED'})
        except (OSError, RuntimeError) as error:
            tracked_errors.append({'path': entry['path'], 'reason': str(error)})
    old = checkout_state()
    old_ok = old == baseline['originalCheckout']
    # Every original namespace is a subset of this complete pinned Git snapshot.
    namespaces = {}
    for entry in baseline['trackedFiles']:
        prefix = 'world-simulation-shorts-engine/recovery/'
        if entry['path'].startswith(prefix):
            name = entry['path'][len(prefix):].split('/')[0]
            namespaces[name] = namespaces.get(name, 0) + 1
    later = json.loads((ROOT / 'world-simulation-shorts-engine/recovery/g2-final-recovery-v1/reports/PROTECTION_BASELINE.json').read_bytes())
    caches = []
    for item in later['existingCacheMetadataSnapshots']:
        path = Path(item['root'])
        caches.append({'root': str(path), 'presentInThisEnvironment': path.exists(),
                       'status': 'ABSENT_IN_FRESH_ENVIRONMENT_NOT_DELETED_BY_THIS_TASK' if not path.exists()
                           else 'PRESENT_NOT_COMPARED_TO_OLD_MACHINE_INODE_MTIME',
                       'oldMetadataFileCount': item.get('filesCount', len(item.get('files', []))),
                       'oldInodeMtimePreservationClaimed': False})
    changed = git('diff', '--name-only', BASE_COMMIT, '--').decode().splitlines()
    changed.extend(git('ls-files', '--others', '--exclude-standard').decode().splitlines())
    outside = sorted(set(p for p in changed if not p.startswith(NAMESPACE)))
    ok = not errors and not tracked_errors and old_ok and not outside
    value = {'schema': 'WORLD_ENGINE_UDP_PROTECTION_RESULT_V1', 'status': 'PASS' if ok else 'FAIL',
             'checkedAtUTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'baselineCommit': BASE_COMMIT, 'sourceManifestSHA256': SOURCE_SHA,
             'protected307': {'status': 'PASS' if not errors else 'FAIL', 'actualBytesVerified': True,
                 'count': len(rows), 'repositoryCount': 306, 'generatedExternalCount': 1, 'errors': errors},
             'allPinnedTrackedFiles': {'status': 'PASS' if not tracked_errors else 'FAIL',
                 'count': len(baseline['trackedFiles']), 'errors': tracked_errors},
             'preservedRecoveryNamespaces': namespaces, 'originalCheckout': old,
             'originalCheckoutUnchanged': old_ok, 'changesOutsideNewNamespace': outside,
             'oldPrivateCaches': caches, 'oldCacheMetadataPreservationClaimed': False,
             'existingFinalAndMediaBytes': 'INCLUDED_IN_ALL_PINNED_TRACKED_FILES',
             'existingFilesDeleted': False if ok else None, 'gpuExecuted': False, 'paidWorkExecuted': False}
    write_json(HERE / 'reports' / output, value)
    print(json.dumps({'status': value['status'], 'protected307': value['protected307'],
                      'allTrackedCount': len(baseline['trackedFiles']), 'originalCheckoutUnchanged': old_ok,
                      'changesOutsideNewNamespace': outside, 'report': str(HERE / 'reports' / output)}))
    return 0 if ok else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--acquire', action='store_true')
    parser.add_argument('--output', default='PROTECTION_CURRENT.json')
    args = parser.parse_args()
    raise SystemExit(acquire() if args.acquire else verify(args.output))
