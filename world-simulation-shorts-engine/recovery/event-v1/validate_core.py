#!/usr/bin/env python3
"""Validate the independent Event Core closure; never approve production Event Final."""
import argparse
import hashlib
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = 'world-simulation-shorts-engine'
BASE = ENGINE + '/recovery/event-v1'
PARENT = ENGINE + '/recovery/v5/manifests/final'
BASELINE = '29b8ee294360812b55ef577b62411de58159003b'
ENTRY = ENGINE + '/web/map_infographic_v1/event_gpu_pipeline_v1.mjs'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.DEVNULL)


def safe_file(relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or any(x in p.parts for x in ('.git', 'node_modules')):
        raise ValueError('UNSAFE_REQUIRED_PATH: ' + relative)
    full = REPO / p
    for ancestor in [full, *full.parents]:
        if ancestor == REPO:
            break
        if ancestor.is_symlink():
            raise ValueError('REQUIRED_SYMLINK_FORBIDDEN: ' + relative)
    if not full.is_file():
        raise ValueError('REQUIRED_FILE_MISSING: ' + relative)
    return full


def record(relative):
    file = safe_file(relative)
    digest = hashlib.sha256()
    with file.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': relative, 'sha256': digest.hexdigest(), 'bytes': file.stat().st_size}


def baseline_unchanged(relative):
    raw = git('show', BASELINE + ':' + relative)
    pointer = re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n', raw)
    expected = {'sha256': pointer[1].decode(), 'bytes': int(pointer[2])} if pointer else {
        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    actual = record(relative)
    if any(actual[key] != value for key, value in expected.items()):
        raise ValueError('PROTECTED_BASELINE_BODY_CHANGED: ' + relative)
    return actual


def load_parent(name):
    path = PARENT + '/' + name + '.json'
    return baseline_unchanged(path), json.loads(safe_file(path).read_text())


def import_graph():
    spec = importlib.util.spec_from_file_location('existing_readonly_ast_helpers', REPO / 'tools/v4_recovery_gate.py')
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    baseline_unchanged('tools/v4_recovery_gate.py')
    parser = REPO / helpers.AST_PARSER
    if hashlib.sha256(parser.read_bytes()).hexdigest() != helpers.AST_PARSER_SHA:
        raise ValueError('PINNED_SYNTAX_PARSER_CHANGED')
    records, edges, pending = {}, [], [ENTRY]
    while pending:
        path = pending.pop()
        if path in records:
            continue
        request = {'parser': str(parser), 'files': [{'path': path, 'absolute': str(safe_file(path))}]}
        rows = subprocess.check_output(['node', '-e', helpers.AST_PROGRAM], input=json.dumps(request).encode(), cwd=REPO)
        row = json.loads(rows)[0]
        if row['issues']:
            raise ValueError('RUNTIME_AST_IMPORT_ISSUE: ' + path)
        records[path] = row
        for imported in row['imports']:
            source = imported['specifier']
            if source == '/three.js':
                target = ENGINE + '/web/vendor/three/0.170.0/three.module.js'
            elif source.startswith('./') or source.startswith('../'):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), source))
            else:
                raise ValueError('UNRESOLVED_RUNTIME_IMPORT: ' + source)
            safe_file(target)
            edges.append({'from': path, 'to': target, **imported})
            pending.append(target)
    for edge in edges:
        # The active closure's imports use direct named exports; reexport-only
        # exports would need explicit resolution rather than an optimistic stamp.
        missing = set(edge['names']) - set(records[edge['to']]['exports'])
        if missing or edge['default'] and not records[edge['to']]['default']:
            raise ValueError('RUNTIME_EXPORT_BINDING_MISSING: ' + edge['to'])
    return {'parser': 'PINNED_BABEL_AST', 'parser_sha256': helpers.AST_PARSER_SHA,
            'entry': ENTRY, 'reachable_modules': sorted(records), 'edges': edges, 'issues': []}


def core_paths():
    roots = [REPO / BASE]
    files = {p.relative_to(REPO).as_posix() for root in roots for p in root.rglob('*')
             if p.is_file() and 'manifests' not in p.relative_to(root).parts and '__pycache__' not in p.parts}
    files.update(p.relative_to(REPO).as_posix() for p in (REPO / ENGINE / 'web/map_infographic_v1').glob('event_*_v1.mjs'))
    files.update(p.relative_to(REPO).as_posix() for p in (REPO / ENGINE / 'tests').glob('event_*_v1.test.mjs'))
    return sorted(files)


def documents():
    runtime_ref, runtime = load_parent('RUNTIME_ASSET_MANIFEST')
    build_ref, build = load_parent('BUILD_INPUT_MANIFEST')
    dependency_ref, dependency = load_parent('DEPENDENCY_MANIFEST')
    pinned = {row['name']: row['version'] for row in dependency['interpreters']}
    node = subprocess.check_output(['node', '--version']).decode().strip().removeprefix('v')
    chromium = subprocess.check_output(['/usr/bin/chromium', '--version']).decode().split()[1]
    python = '.'.join(map(str, sys.version_info[:3]))
    if node != pinned['node'] or chromium != pinned['chromium'] or python != pinned['python']:
        raise ValueError('PINNED_CORE_TOOLCHAIN_CHANGED')
    for package in ('three', 'playwright', 'playwright-core'):
        installed = json.loads((REPO / 'cinematic-world-map/node_modules' / package / 'package.json').read_text())
        expected = next(row['version'] for row in dependency['dependencies'] if row['name'] == package)
        if installed['name'] != package or installed['version'] != expected:
            raise ValueError('PINNED_NODE_PACKAGE_CHANGED: ' + package)
    graph = import_graph()
    source_rows = []
    for path in graph['reachable_modules']:
        origin = 'NEW_COMMON_CORE' if Path(path).name.startswith('event_') else 'PROTECTED_V5_BASELINE'
        row = record(path) if origin == 'NEW_COMMON_CORE' else baseline_unchanged(path)
        source_rows.append({**row, 'origin': origin})
    for row in [*runtime['entries'], *runtime['plan_inputs'], *build['entries'], *build['dependency_locks']]:
        actual = baseline_unchanged(row['path'])
        if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
            raise ValueError('INHERITED_ASSET_MANIFEST_MISMATCH: ' + row['path'])
    lock = baseline_unchanged('cinematic-world-map/package-lock.json')
    for path in core_paths():
        if '/web/map_infographic_v1/' in path:
            text = safe_file(path).read_text()
            if re.search(r'\b(?:Suez|Egypt|COUNTRY_[A-Z_]+)\b|85\s*m', text, re.I):
                raise ValueError('FIXTURE_HARDCODE_IN_COMMON_ENGINE: ' + path)
    common = {'schema': 1, 'status': 'CORE_IMPLEMENTED_DATA_BLOCKED', 'baseline_commit': BASELINE,
              'production_fixture_complete': False, 'production_proof_complete': False, 'event_final': False}
    routes = {row['url']: row for row in runtime['runtime_routes']}
    for path in graph['reachable_modules']:
        if path.startswith(ENGINE + '/web/map_infographic_v1/'):
            url = '/modules/' + Path(path).name
            routes[url] = {'url': url, 'file': path}
    inherited_runtime = {'parent': runtime_ref, 'entries': runtime['entries'], 'plan_inputs': runtime['plan_inputs'],
                         'runtime_routes': sorted(routes.values(), key=lambda row: row['url']), 'required_temp_only_files': []}
    inherited_build = {'parent': build_ref, 'entries': build['entries'], 'recipe': build['recipe'],
                       'dependency_locks': build['dependency_locks'], 'new_data_downloaded': False,
                       'derivatives_regenerated': False}
    dependency_info = {'parent': dependency_ref, 'dependencies': dependency['dependencies'],
                       'interpreters': dependency['interpreters'], 'lock': lock,
                       'setup': ['npm', '--prefix', 'cinematic-world-map', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--strict-ssl=true']}
    return {
        'SOURCE_MANIFEST.json': {**common, 'entry': ENTRY, 'entries': source_rows, 'new_core_files': [record(p) for p in core_paths()]},
        'RUNTIME_ASSET_MANIFEST.json': {**common, **inherited_runtime},
        'BUILD_INPUT_MANIFEST.json': {**common, **inherited_build},
        'DEPENDENCY_MANIFEST.json': {**common, **dependency_info},
        'IMPORT_MANIFEST.json': {**common, **graph},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifests', action='store_true')
    parser.add_argument('--require-persisted', action='store_true')
    args = parser.parse_args()
    # Existing files can never be edited by this Event scope.
    changed = git('diff', '--name-only', BASELINE).decode().splitlines()
    original = set(git('ls-tree', '-r', '--name-only', BASELINE).decode().splitlines())
    if any(path in original for path in changed):
        raise ValueError('PROTECTED_EXISTING_PATH_MODIFIED')
    docs = documents()
    target = REPO / BASE / 'manifests'
    encoded = {name: (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode() for name, data in docs.items()}
    payload = docs['SOURCE_MANIFEST.json']['new_core_files'] + docs['SOURCE_MANIFEST.json']['entries']
    payload += docs['RUNTIME_ASSET_MANIFEST.json']['entries'] + docs['RUNTIME_ASSET_MANIFEST.json']['plan_inputs']
    payload += docs['BUILD_INPUT_MANIFEST.json']['entries'] + docs['BUILD_INPUT_MANIFEST.json']['dependency_locks']
    inventory = {r['path']: r for r in payload}
    for name, raw in encoded.items():
        path = BASE + '/manifests/' + name
        inventory[path] = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    encoded['HASH_MANIFEST.json'] = (json.dumps({'schema': 1, 'scope': 'INDEPENDENT_COMMON_CORE',
                                              'entries': sorted(inventory.values(), key=lambda r: r['path'])}, indent=2) + '\n').encode()
    encoded['SHA256SUMS'] = ''.join(r['sha256'] + '  ' + r['path'] + '\n' for r in sorted(inventory.values(), key=lambda r: r['path'])).encode()
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, raw in encoded.items():
            (target / name).write_bytes(raw)
    for name, raw in encoded.items():
        if (target / name).read_bytes() != raw:
            raise ValueError('CORE_MANIFEST_STALE_OR_CHANGED: ' + name)
    if args.require_persisted:
        paths = core_paths() + [BASE + '/manifests/' + n for n in encoded]
        for path in paths:
            if git('show', 'HEAD:' + path) != safe_file(path).read_bytes():
                raise ValueError('CORE_FILE_NOT_PERSISTED: ' + path)
    print(json.dumps({'scope': 'INDEPENDENT_COMMON_CORE', 'status': 'PASS', 'baseline': BASELINE,
                      'source_files': len(docs['SOURCE_MANIFEST.json']['entries']),
                      'new_core_files': len(core_paths()), 'import_edges': len(docs['IMPORT_MANIFEST.json']['edges']),
                      'hash_entries': len(inventory), 'required_temp_only_files': 0,
                      'source_persisted': bool(args.require_persisted), 'production_event_gate': 'BLOCKED',
                      'decision': 'SUEZ_EVENT_FIXTURE_BLOCKED', 'event_final': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
