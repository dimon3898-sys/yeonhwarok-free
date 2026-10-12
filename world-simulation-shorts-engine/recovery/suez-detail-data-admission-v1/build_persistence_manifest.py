#!/usr/bin/env python3
"""Inventory retained research and reproduction inputs without acquiring or admitting data.

--write changes only DATA_RESEARCH_MANIFEST.json. Large pre-existing DEM inputs
reuse the explicitly identified native audit by default; all new task bytes are
hashed on every invocation. --rehash-retained-large-assets independently hashes
those old originals too. This command neither renders nor changes Git.
"""
import argparse
import ast
import hashlib
import json
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[3]
ENGINE = 'world-simulation-shorts-engine'
BASE = ENGINE + '/recovery/suez-detail-data-admission-v1'
MANIFEST = BASE + '/DATA_RESEARCH_MANIFEST.json'
MODULE = ENGINE + '/web/map_infographic_v1/detail_data_profile_v1.mjs'
TEST = ENGINE + '/tests/detail_data_profile_v1.test.mjs'
DATA = ENGINE + '/recovery/event-data/suez-full-canal-20261012'
BASELINES = {
    'v5': '29b8ee294360812b55ef577b62411de58159003b',
    'event_v2': '8cbbbd64573ea87aa56decbc0fb5218071e45bbe',
    'suez_data': '69e6ed83acac00bfa7ab1853722f873792a813e1',
    'v3_block': '9cf4661a56db0334bc1d9e936a6671f643562112',
}
DEM_AUDIT = BASE + '/research/dem/EXISTING_DEM_AUDIT.json'
FORBIDDEN = {'.git', 'node_modules', '__pycache__', '.env', '.aws', '.ssh',
             '.codex', '.npmrc', '.netrc', '.git-credentials', 'credentials',
             'credentials.json', 'auth.json', 'tokens.json'}
FINAL_EVIDENCE = re.compile(r'^(?:SECRET_SCAN|PERSISTENCE|POST[_-]?SCAN|POST[_-]?COMMIT|FINAL[_-]?SAVE)', re.I)
LFS = re.compile(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n')
HASH = re.compile(r'[0-9a-f]{64}')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.DEVNULL)


def file(relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise ValueError('UNSAFE_REQUIRED_PATH')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or any(p in FORBIDDEN or p.startswith('.env.') for p in parts.parts):
        raise ValueError('UNSAFE_REQUIRED_PATH: ' + relative)
    current = REPO
    for part in parts.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('SYMLINK_FORBIDDEN: ' + relative)
    if not current.is_file():
        raise ValueError('REQUIRED_FILE_MISSING: ' + relative)
    return current


def record(relative, **extra):
    source = file(relative)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('INPUT_CHANGED_DURING_SCAN: ' + relative)
    return {'path': relative, 'sha256': digest.hexdigest(), 'bytes': before.st_size,
            'hash_verification': 'ACTUAL_FILE_BYTES_THIS_BUILD', **extra}


def blob_ref(ref, relative):
    rows = git('ls-tree', ref, '--', relative).decode().strip().split('\t')
    if len(rows) != 2:
        raise ValueError('BASELINE_REQUIRED_FILE_MISSING: ' + relative)
    mode, kind, oid = rows[0].split()
    if kind != 'blob' or mode not in ('100644', '100755'):
        raise ValueError('REGULAR_GIT_BLOB_REQUIRED: ' + relative)
    return {'commit': ref, 'git_oid': oid, 'mode': mode}


def unchanged(relative, ref):
    row = record(relative)
    raw = git('show', ref + ':' + relative)
    pointer = LFS.fullmatch(raw)
    expected = ({'sha256': pointer[1].decode(), 'bytes': int(pointer[2])} if pointer else
                {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    if any(row[k] != expected[k] for k in ('sha256', 'bytes')):
        raise ValueError('PROTECTED_BASELINE_BODY_CHANGED: ' + relative)
    return {**row, 'protected_baseline': blob_ref(ref, relative)}


def task_paths():
    included, excluded = [], []
    for source in (REPO / BASE).rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts:
            continue
        relative = source.relative_to(REPO).as_posix()
        under = source.relative_to(REPO / BASE).parts
        if relative == MANIFEST or ('evidence' in under and FINAL_EVIDENCE.match(source.name)):
            excluded.append(relative)
        else:
            included.append(relative)
    return sorted(included), sorted(excluded)


def baseline_guard():
    protections = {}
    for name, ref in BASELINES.items():
        # The older data commit predates authorized Event V2 implementation;
        # freeze its data scope, rather than falsely rejecting that later Core.
        scope = ['--', ENGINE + '/recovery/event-data'] if name == 'suez_data' else []
        original = set(git('ls-tree', '-r', '--name-only', ref, *scope).decode().splitlines())
        changed = sorted(original & set(git('diff', '--name-only', ref, *scope).decode().splitlines()))
        if changed:
            raise ValueError('PROTECTED_BASELINE_FILES_CHANGED: ' + name + ': ' + ', '.join(changed))
        protections[name] = {'commit': ref, 'status': 'PASS', 'changed_paths': []}
    return protections


def js_graph(roots):
    helper = 'tools/v4_recovery_gate.py'
    helper_ref = unchanged(helper, BASELINES['v5'])
    # Read only literal AST/parser constants. Do not import the Python helper or
    # create its __pycache__, and do not change the inherited parser program.
    literals = {}
    for item in ast.parse(file(helper).read_text()).body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id in ('AST_PROGRAM', 'AST_PARSER', 'AST_PARSER_SHA'):
                    literals[target.id] = ast.literal_eval(item.value)
    parser = REPO / literals['AST_PARSER']
    if hashlib.sha256(parser.read_bytes()).hexdigest() != literals['AST_PARSER_SHA']:
        raise ValueError('PINNED_AST_PARSER_CHANGED')
    pending, parsed, edges, builtins = list(roots), {}, [], []
    while pending:
        path = pending.pop()
        if path in parsed:
            continue
        request = {'parser': str(parser), 'files': [{'path': path, 'absolute': str(file(path))}]}
        result = json.loads(subprocess.check_output(['node', '-e', literals['AST_PROGRAM']],
                                                    input=json.dumps(request).encode(), cwd=REPO))[0]
        if result['issues']:
            raise ValueError('AST_IMPORT_ISSUE: ' + path + ': ' + json.dumps(result['issues']))
        parsed[path] = result
        for imported in result['imports']:
            specifier = imported['specifier']
            if specifier.startswith('node:'):
                builtins.append({'from': path, 'specifier': specifier, 'kind': 'NODE_BUILTIN'})
                continue
            if not specifier.startswith(('./', '../')):
                raise ValueError('UNRESOLVED_OR_EXTERNAL_SOURCE_IMPORT: ' + str(specifier))
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), specifier))
            file(target)
            edges.append({'from': path, 'to': target, **imported})
            pending.append(target)
    for edge in edges:
        exports = parsed[edge['to']]
        if set(edge['names']) - set(exports['exports']) or edge['default'] and not exports['default']:
            raise ValueError('IMPORT_EXPORT_BINDING_MISSING: ' + edge['to'])
    return {'method': 'UNCHANGED_PINNED_BABEL_AST', 'helper': helper_ref,
            'parser_package': 'playwright', 'parser_version': '1.62.1',
            'parser_sha256': literals['AST_PARSER_SHA'], 'roots': sorted(roots),
            'reachable_modules': sorted(parsed),
            'edges': sorted(edges, key=lambda r: (r['from'], r['line'], r['to'])),
            'node_builtins': sorted(builtins, key=lambda r: (r['from'], r['specifier'])),
            'issues': []}


def task_kind(path):
    if path.endswith(('.py', '.mjs')):
        return 'PROCEDURE_OR_SOURCE'
    if path.endswith('.geojson'):
        return 'NATIVE_SOURCE_COMPARISON_DERIVATIVE_NOT_ADMITTED'
    if '/research/' in path and path.endswith(('.response', '.md', '.yaml', '.txt', '.ipynb')):
        return 'DOCUMENTATION_OR_RETRIEVAL_RESPONSE_BYTES_NOT_IMAGERY'
    if '/research/' in path:
        return 'SOURCE_RESEARCH_OR_RETRIEVAL_RECEIPT'
    if '/evidence/' in path:
        return 'PRIVATE_AUDIT_OR_VALIDATION_EVIDENCE'
    return 'PROFILE_OR_TASK_DOCUMENTATION'


def retained_large(dem, rehash):
    rows = []
    for audited in [dem['actual_native_height'], *dem['actual_cogs']]:
        path = ENGINE + '/' + audited['path']
        expected = {k: audited[k] for k in ('sha256', 'bytes')}
        source = file(path)
        if not HASH.fullmatch(expected['sha256']) or source.stat().st_size != expected['bytes']:
            raise ValueError('RETAINED_NATIVE_AUDIT_SIZE_OR_HASH_INVALID: ' + path)
        baseline = blob_ref(BASELINES['v5'], path)
        current = blob_ref('HEAD', path)
        if baseline['git_oid'] != current['git_oid']:
            raise ValueError('RETAINED_NATIVE_GIT_OBJECT_CHANGED: ' + path)
        git_size = int(git('cat-file', '-s', baseline['git_oid']))
        if git_size < 1024:
            pointer = LFS.fullmatch(git('cat-file', 'blob', baseline['git_oid']))
            if not pointer or pointer[1].decode() != expected['sha256'] or int(pointer[2]) != expected['bytes']:
                raise ValueError('RETAINED_NATIVE_LFS_POINTER_DIFFERS: ' + path)
        elif git_size != expected['bytes']:
            raise ValueError('RETAINED_NATIVE_GIT_SIZE_DIFFERS: ' + path)
        if rehash:
            measured = record(path)
            if any(measured[k] != expected[k] for k in ('sha256', 'bytes')):
                raise ValueError('RETAINED_NATIVE_AUDIT_BODY_DIFFERS: ' + path)
        else:
            measured = {'path': path, **expected,
                        'hash_verification': 'EXISTING_NATIVE_AUDIT_HASH_REFERENCED_NOT_REHASHED_THIS_BUILD'}
        rows.append({**measured, 'kind': 'RETAINED_ORIGINAL_DEM_INPUT_NOT_NEW_ACQUISITION',
                     'protected_baseline': baseline, 'hash_evidence': DEM_AUDIT,
                     'local_body_size_checked_this_build': True})
    return rows


def build(rehash=False):
    protections = baseline_guard()
    paths, excluded = task_paths()
    profile = json.loads(file(BASE + '/DETAIL_DATA_PROFILE.json').read_text())
    quality = json.loads(file(BASE + '/evidence/DETAIL_QUALITY_AUDIT.json').read_text())
    dem = json.loads(file(DEM_AUDIT).read_text())
    if quality['status'] != 'DETAIL_DATA_ADMISSION_BLOCKED' or quality.get('safeDetailExtent') is not None:
        raise ValueError('UNEXPECTED_ADMISSION_OR_SAFE_EXTENT')
    if profile.get('terrainDetailVerified') or profile.get('gisDetailVerified') or profile.get('safeScaleRange') is not None:
        raise ValueError('UNEXPECTED_PROFILE_CERTIFICATION')
    if any(quality.get(flag) for flag in ('staticProofCreated', 'cameraAnimationStarted', 'eventAnimationStarted')):
        raise ValueError('UNAUTHORIZED_PROOF_OR_ANIMATION_REPORTED')
    if any(Path(path).suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.mp4') for path in paths):
        raise ValueError('UNEXPECTED_NEW_RASTER_OR_PUBLIC_PROOF_IN_TASK')
    graph_roots = [MODULE, TEST, BASE + '/audit_detail_candidates.mjs', BASE + '/replay_final_audit.mjs']
    graph = js_graph(graph_roots)
    task_rows = [record(path, kind=task_kind(path)) for path in paths]
    source_rows = [record(MODULE, kind='NEW_GENERIC_DETAIL_ADMISSION_SOURCE'),
                   record(TEST, kind='SYNTHETIC_TEST_ONLY_NOT_PRODUCTION_QUALITY_EVIDENCE')]
    retained = set(graph['reachable_modules']) - set(graph_roots)
    retained.update({
        ENGINE + '/recovery/v4/equivalent-plans/REGIONAL-plan.json',
        ENGINE + '/recovery/v4/V4-state-records/input-manifest.json',
        ENGINE + '/recovery/v4/past-paths/tmp/world-korean-layout-micro/iteration-01/height-source.json',
        ENGINE + '/recovery/v5/inputs/scene.json',
        ENGINE + '/recovery/v5/inputs/camera-plan.json',
        ENGINE + '/recovery/event-v1-candidate-v2/evidence/on150/REPORT.json',
        ENGINE + '/web/map_infographic_v1/renderer.mjs',
        ENGINE + '/web/map_infographic_v1/event_line_pass_v1.mjs',
        ENGINE + '/web/map_infographic_v1/graphic_motion_pass_v4.mjs',
        'cinematic-world-map/package.json', 'cinematic-world-map/package-lock.json',
        ENGINE + '/recovery/v4/runtime/python-requirements.lock',
        'tools/v4_recovery_gate.py',
        ENGINE + '/recovery/v5/manifests/final/DEPENDENCY_MANIFEST.json',
    })
    # Preserve the fixture's entire original source/provenance closure, without
    # re-investigating or changing any source selection or geometry.
    retained.update(source.relative_to(REPO).as_posix() for source in (REPO / DATA).rglob('*')
                    if source.is_file() and '__pycache__' not in source.parts)
    baseline_rows = [unchanged(path, BASELINES['v3_block']) for path in sorted(retained)]
    large_rows = retained_large(dem, rehash)
    rows = sorted([*task_rows, *source_rows, *baseline_rows, *large_rows], key=lambda r: r['path'])
    if len({row['path'] for row in rows}) != len(rows):
        raise ValueError('DUPLICATE_REQUIRED_INPUT')
    dependency = json.loads(file(ENGINE + '/recovery/v5/manifests/final/DEPENDENCY_MANIFEST.json').read_text())
    return {
        'schema': 1, 'scope': 'SUEZ_DETAIL_DATA_ADMISSION_V1_RESEARCH_PERSISTENCE',
        'status': 'DETAIL_DATA_ADMISSION_BLOCKED', 'admission_status': 'NOT_ADMITTED',
        'SAFE_DETAIL_EXTENT': None, 'safeScaleRange': None,
        'new_imagery_raster_acquired': 0, 'new_dem_acquired': 0,
        'static_proof_created': False, 'static_proof_url': None, 'public_review_url': None,
        'camera_animation_started': False, 'event_animation_started': False,
        'baselines': BASELINES, 'protected_baselines': protections,
        'required_temp_only_files': [], 'required_temp_only_count': 0,
        'canonical_path_root': 'REPOSITORY_ROOT',
        'retained_path_clarification': 'Historical past-paths/tmp names are committed canonical repository paths, not live temporary directories.',
        'task_files': task_rows, 'new_source_and_tests': source_rows,
        'retained_protected_reproduction_inputs': baseline_rows,
        'retained_existing_native_originals': large_rows,
        'required_files': rows, 'required_file_count': len(rows),
        'actual_task_bytes_hashed': sum(row['bytes'] for row in [*task_rows, *source_rows]),
        'source_import_closure': graph,
        'dependency_pins': {'interpreters': dependency['interpreters'], 'packages': dependency['dependencies'],
                            'new_runtime_dependency': False},
        'hash_policy': {
            'task_and_small_inputs': 'Actual SHA256/byte count recomputed on every build.',
            'retained_large_inputs': 'Actual source audit hashes; preserved Git object/pointer and current local size checked. Explicit rehash flag available.',
            'document_limit': 'Documentation grids and native-coordinate preservation do not prove source positional accuracy or data admission.',
        },
        # Use stable exclusion patterns: the later arrival of a final receipt
        # must not itself make the pre-commit inventory stale or circular.
        'excluded_self_or_final_receipts': [MANIFEST,
            *[BASE + '/evidence/' + name + '*' for name in
              ('SECRET_SCAN', 'PERSISTENCE', 'POST_SCAN', 'POST_COMMIT', 'FINAL_SAVE')]],
        'exclusion_policy': 'Exclude self and final SECRET_SCAN/PERSISTENCE/POST_SCAN/POST_COMMIT/FINAL_SAVE evidence; root verifies their Git persistence separately to avoid circular evidence hashes.',
        'persistence_verification': 'Run this builder with --require-persisted after root commits. This inventory alone is not a commit or remote-availability claim.',
        'reproduction': {
            'node_tests': ['node', '--test', TEST],
            'data_only_candidate_audit': {'original_creation_recipe': ['node', BASE + '/audit_detail_candidates.mjs'],
                                        'behavior': 'Creation-only; rejects existing saved profile/audit. Recompute final quality through the preserved module with the saved profile; never delete saved outputs to rerun creation.'},
            'final_saved_profile_replay': ['node', BASE + '/replay_final_audit.mjs'],
            'saved_osm_comparison': ['/usr/bin/python3', '-B', BASE + '/research/gis/audit_saved_osm.py'],
            'existing_dem_audit': ['/usr/bin/python3', '-B', BASE + '/research/dem/audit_existing_dem.py', '--output', 'NEW_PRIVATE_DEM_AUDIT.json'],
            'manifest': ['/usr/bin/python3', '-B', BASE + '/build_persistence_manifest.py', '--write'],
            'execution_limit': 'Recipes read protected originals. Research output procedures may write only their separate task output paths; do not overwrite preserved outputs during reproduction.',
        },
    }


def require_persisted(document):
    deferred_large = {row['path'] for row in document['retained_existing_native_originals']
                      if row['hash_verification'] != 'ACTUAL_FILE_BYTES_THIS_BUILD'}
    for row in document['required_files']:
        relative = row['path']
        head = blob_ref('HEAD', relative)
        indexed = git('ls-files', '--stage', '--', relative).decode().strip().split()
        if len(indexed) < 3 or indexed[1] != head['git_oid'] or indexed[2] != '0':
            raise ValueError('REQUIRED_FILE_NOT_COMMITTED_OR_INDEX_CHANGED: ' + relative)
        if relative in deferred_large:
            continue
        raw = git('show', 'HEAD:' + relative)
        pointer = LFS.fullmatch(raw)
        expected = ({'sha256': pointer[1].decode(), 'bytes': int(pointer[2])} if pointer else
                    {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        if any(row[k] != expected[k] for k in ('sha256', 'bytes')):
            raise ValueError('REQUIRED_FILE_WORKTREE_DIFFERS_FROM_HEAD: ' + relative)
    actual_manifest = file(MANIFEST).read_bytes()
    if git('show', 'HEAD:' + MANIFEST) != actual_manifest or git('show', ':' + MANIFEST) != actual_manifest:
        raise ValueError('MANIFEST_NOT_PERSISTED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--inspect-only', action='store_true')
    parser.add_argument('--require-persisted', action='store_true')
    parser.add_argument('--rehash-retained-large-assets', action='store_true')
    args = parser.parse_args()
    if args.inspect_only and (args.write or args.require_persisted):
        parser.error('--inspect-only cannot write or require persistence')
    document = build(args.rehash_retained_large_assets)
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    if args.write:
        (REPO / MANIFEST).write_bytes(encoded)
    if not args.inspect_only and file(MANIFEST).read_bytes() != encoded:
        raise ValueError('DATA_RESEARCH_MANIFEST_STALE; rerun --write after task files settle')
    if args.require_persisted:
        require_persisted(document)
    print(json.dumps({'status': 'PASS', 'decision': document['status'],
                      'required_files': len(document['required_files']),
                      'task_files_actual_bytes_hashed': len(document['task_files']) + len(document['new_source_and_tests']),
                      'task_bytes_hashed': document['actual_task_bytes_hashed'],
                      'retained_large_hashes': 'REHASHED' if args.rehash_retained_large_assets else 'EXPLICIT_EXISTING_AUDIT_REFERENCES',
                      'required_temp_only_files': 0, 'SAFE_DETAIL_EXTENT': None,
                      'new_imagery_raster_acquired': 0, 'static_proof_url': None,
                      'manifest_persisted': bool(args.require_persisted),
                      'manifest_sha256': hashlib.sha256(encoded).hexdigest()}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
