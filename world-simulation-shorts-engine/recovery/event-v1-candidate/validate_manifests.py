#!/usr/bin/env python3
"""Build/check independent Event candidate manifests without rendering or approving it.

Only --write-manifests mutates files, and only the candidate/manifests directory.
Historical Core, production data and Camera V5 manifests are never rewritten.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = 'world-simulation-shorts-engine'
BASE = ENGINE + '/recovery/event-v1-candidate'
CORE = ENGINE + '/recovery/event-v1'
DATA = ENGINE + '/recovery/event-data/suez-full-canal-20261012'
V5 = ENGINE + '/recovery/v5'
V5_FINAL = V5 + '/manifests/final'
BASELINES = {
    'event_core': '00ad07e4a6041ea4cc6369bfce8871762f61f152',
    'production_data': '69e6ed83',
    'camera_v5': '29b8ee294360812b55ef577b62411de58159003b',
}
ENTRY = ENGINE + '/web/map_infographic_v1/event_gpu_pipeline_v1.mjs'
AUTHORIZED_CORE_CHANGES = {
    ENTRY,
    ENGINE + '/web/map_infographic_v1/event_line_pass_v1.mjs',
}
BLOCKED_PARTS = {'.git', 'node_modules', '__pycache__', '.aws', '.ssh', '.codex',
                 '.env', '.npmrc', '.netrc', '.git-credentials', 'credentials',
                 'credentials.json', 'auth.json', 'tokens.json'}
LFS = re.compile(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n')
PINNED = {'node': '24.19.0', 'chromium': '154.0.8037.57',
          'python': '3.13.5', 'ffmpeg': '7.1.5'}
SECRET_SCAN_TOOL = {
    'name': 'gitleaks', 'version': '8.24.3',
    'binary_sha256': 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad',
    'official_release': 'https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3',
    'required_for_runtime': False, 'required_temporary_runtime_input': False,
    'use': 'Delivery verification; use a verified installed command or an explicitly supplied binary path.',
    'execution_evidence': 'Retained redacted secret-scan report; this manifest command does not execute the scanner.',
}
MANIFEST_NAMES = ('SOURCE_MANIFEST.json', 'FIXTURE_MANIFEST.json', 'EVIDENCE_MANIFEST.json',
                  'RUNTIME_ASSET_MANIFEST.json', 'BUILD_INPUT_MANIFEST.json',
                  'DEPENDENCY_MANIFEST.json', 'IMPORT_MANIFEST.json')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.DEVNULL)


def safe_file(relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise ValueError('UNSAFE_REQUIRED_PATH')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or any(
            p in BLOCKED_PARTS or p.startswith('.env.') for p in path.parts):
        raise ValueError('UNSAFE_REQUIRED_PATH: ' + relative)
    full = REPO
    for part in path.parts:
        full /= part
        if full.is_symlink():
            raise ValueError('REQUIRED_SYMLINK_FORBIDDEN: ' + relative)
    if not full.is_file():
        raise ValueError('REQUIRED_FILE_MISSING: ' + relative)
    return full


def record(relative, **extra):
    file = safe_file(relative)
    before = file.stat()
    digest = hashlib.sha256()
    with file.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    after = file.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('REQUIRED_FILE_CHANGED_DURING_SCAN: ' + relative)
    return {'path': relative, 'sha256': digest.hexdigest(), 'bytes': before.st_size, **extra}


def expected_body(ref, relative):
    raw = git('show', ref + ':' + relative)
    pointer = LFS.fullmatch(raw)
    return ({'sha256': pointer[1].decode(), 'bytes': int(pointer[2])}
            if pointer else {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})


def unchanged(ref, relative):
    actual = record(relative)
    if any(actual[key] != value for key, value in expected_body(ref, relative).items()):
        raise ValueError('PROTECTED_BASELINE_BODY_CHANGED: ' + relative)
    return actual


def protected_scope():
    baseline = BASELINES['camera_v5']
    original = set(git('ls-tree', '-r', '--name-only', baseline).decode().splitlines())
    changed = set(git('diff', '--name-only', baseline).decode().splitlines())
    protected_changed = sorted(original & changed)
    if protected_changed:
        raise ValueError('PROTECTED_V5_PATH_MODIFIED: ' + ', '.join(protected_changed))
    original_core = set(git('ls-tree', '-r', '--name-only', BASELINES['event_core'], '--',
                            CORE, ENGINE + '/web/map_infographic_v1', ENGINE + '/tests').decode().splitlines())
    core_changed = set(git('diff', '--name-only', BASELINES['event_core'], '--',
                          CORE, ENGINE + '/web/map_infographic_v1', ENGINE + '/tests').decode().splitlines())
    illegal = sorted((original_core & core_changed) - AUTHORIZED_CORE_CHANGES)
    if illegal:
        raise ValueError('PROTECTED_CORE_PATH_MODIFIED: ' + ', '.join(illegal))
    changed_data = git('diff', '--name-only', BASELINES['production_data'], '--',
                       ENGINE + '/recovery/event-data').decode().splitlines()
    if changed_data:
        raise ValueError('PROTECTED_PRODUCTION_DATA_MODIFIED: ' + ', '.join(changed_data))
    return {'camera_renderer_visual': 'UNCHANGED', 'production_geometry_metric': 'UNCHANGED',
            'historical_core_manifests': 'UNCHANGED',
            'authorized_changed_core_paths': sorted(original_core & core_changed)}


def files_under(base, exclude=()):
    root = REPO / base
    if not root.is_dir():
        raise ValueError('REQUIRED_DIRECTORY_MISSING: ' + base)
    result = []
    for file in root.rglob('*'):
        parts = file.relative_to(root).parts
        if any(part in {*exclude, '__pycache__'} for part in parts):
            continue
        if file.is_file():
            result.append(file.relative_to(REPO).as_posix())
    return sorted(result)


def core_paths():
    paths = set(files_under(CORE, exclude=('manifests',)))
    for root, pattern in [(ENGINE + '/web/map_infographic_v1', 'event_*_v1.mjs'),
                          (ENGINE + '/tests', 'event_*_v1.test.mjs')]:
        paths.update(p.relative_to(REPO).as_posix() for p in (REPO / root).glob(pattern))
    return sorted(paths)


def load_v5(name):
    path = V5_FINAL + '/' + name + '.json'
    ref = unchanged(BASELINES['camera_v5'], path)
    return ref, json.loads(safe_file(path).read_text())


def toolchain(dependency):
    recorded = {row['name']: row['version'] for row in dependency['interpreters']}
    if recorded != PINNED:
        raise ValueError('HISTORICAL_TOOLCHAIN_PINS_DIFFER')
    actual = {
        'node': subprocess.check_output(['node', '--version']).decode().strip().removeprefix('v'),
        'chromium': subprocess.check_output(['/usr/bin/chromium', '--version']).decode().split()[1],
        'python': '.'.join(map(str, sys.version_info[:3])),
        'ffmpeg': subprocess.check_output(['ffmpeg', '-version']).decode().splitlines()[0].split()[2].split('-')[0],
    }
    if actual != PINNED:
        raise ValueError('PINNED_CANDIDATE_TOOLCHAIN_CHANGED: ' + json.dumps(actual, sort_keys=True))
    lock = json.loads(safe_file('cinematic-world-map/package-lock.json').read_text())
    python_lock = safe_file(ENGINE + '/recovery/v4/runtime/python-requirements.lock').read_text()
    packages = []
    for row in dependency['dependencies']:
        name, version = row['name'], row['version']
        if row.get('ecosystem') == 'python':
            if not re.search(r'(?mi)^\s*' + re.escape(name) + r'\s*==\s*' + re.escape(version) + r'\s*(?:#.*)?$', python_lock):
                raise ValueError('PYTHON_PIN_MISSING_FROM_LOCK: ' + name)
            installed_version = importlib.metadata.version(name)
        else:
            if lock.get('packages', {}).get('node_modules/' + name, {}).get('version') != version:
                raise ValueError('NODE_PIN_MISSING_FROM_LOCK: ' + name)
            metadata = REPO / 'cinematic-world-map/node_modules' / name / 'package.json'
            installed = json.loads(metadata.read_text())
            if installed['name'] != name:
                raise ValueError('PINNED_NODE_PACKAGE_NAME_CHANGED: ' + name)
            installed_version = installed['version']
        if installed_version != version:
            raise ValueError('PINNED_PACKAGE_VERSION_CHANGED: ' + name)
        packages.append({'name': name, 'version': version, 'ecosystem': row.get('ecosystem', 'npm')})
    return {'interpreters': actual, 'packages': packages}


def import_graph(candidate_paths):
    helper_path = 'tools/v4_recovery_gate.py'
    unchanged(BASELINES['camera_v5'], helper_path)
    spec = importlib.util.spec_from_file_location('candidate_readonly_ast_helpers', safe_file(helper_path))
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    parser = REPO / helpers.AST_PARSER
    if hashlib.sha256(parser.read_bytes()).hexdigest() != helpers.AST_PARSER_SHA:
        raise ValueError('PINNED_SYNTAX_PARSER_CHANGED')
    roots = [ENTRY, V5 + '/harness.mjs']
    roots.extend(path for path in candidate_paths if path.endswith('.mjs'))
    records, edges, externals, pending = {}, [], [], list(roots)
    lock = json.loads(safe_file('cinematic-world-map/package-lock.json').read_text())
    while pending:
        path = pending.pop()
        if path in records:
            continue
        request = {'parser': str(parser), 'files': [{'path': path, 'absolute': str(safe_file(path))}]}
        rows = subprocess.check_output(['node', '-e', helpers.AST_PROGRAM], input=json.dumps(request).encode(), cwd=REPO)
        row = json.loads(rows)[0]
        # Node capture callers load the locked Playwright package with
        # createRequire rooted at the committed cinematic package.json. This is
        # deliberately separate from the browser's ESM-only runtime closure.
        known_requires = {'playwright', 'playwright/package.json'}
        allowed_commonjs = (path.startswith(BASE + '/') and
                            all(r['specifier'] in known_requires for r in row['requires']) and
                            "createRequire(path.join(repo,'cinematic-world-map/package.json'))" in safe_file(path).read_text())
        issues = [issue for issue in row['issues'] if not (
            issue['code'] == 'COMMONJS_RUNTIME_CLOSURE_REQUIRES_REVIEW' and allowed_commonjs)]
        if issues:
            raise ValueError('AST_IMPORT_ISSUE: ' + path + ': ' + json.dumps(issues))
        records[path] = row
        for required in row['requires']:
            package = lock['packages']['node_modules/playwright']
            externals.append({'from': path, 'specifier': required['specifier'], 'kind': 'LOCKED_NPM_COMMONJS_PACKAGE',
                              'version': package['version'], 'integrity': package['integrity'],
                              'line': required['line'], 'lock_path': 'cinematic-world-map/package-lock.json',
                              'resolution_root': 'cinematic-world-map/package.json'})
        for imported in row['imports']:
            source = imported['specifier']
            if not isinstance(source, str) or source.startswith(('file:', '/tmp/', 'http:', 'https:')):
                raise ValueError('UNSAFE_OR_TEMPORARY_RUNTIME_IMPORT: ' + path)
            if source.startswith('node:'):
                externals.append({'from': path, 'specifier': source, 'kind': 'NODE_BUILTIN', 'node_version': PINNED['node']})
                continue
            if source in ('playwright', 'playwright-core', 'three'):
                package = lock['packages']['node_modules/' + source]
                externals.append({'from': path, 'specifier': source, 'kind': 'LOCKED_NPM_PACKAGE',
                                  'version': package['version'], 'integrity': package['integrity'],
                                  'lock_path': 'cinematic-world-map/package-lock.json'})
                continue
            if source == '/three.js':
                target = ENGINE + '/web/vendor/three/0.170.0/three.module.js'
            elif source.startswith('/modules/'):
                target = ENGINE + '/web/map_infographic_v1/' + source.removeprefix('/modules/')
            elif source.startswith(('./', '../')):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), source))
            else:
                raise ValueError('UNRESOLVED_RUNTIME_IMPORT: ' + source)
            safe_file(target)
            edges.append({'from': path, 'to': target, **imported})
            pending.append(target)
    for edge in edges:
        missing = set(edge['names']) - set(records[edge['to']]['exports'])
        if missing or edge['default'] and not records[edge['to']]['default']:
            raise ValueError('RUNTIME_EXPORT_BINDING_MISSING: ' + edge['to'])
    runtime_modules = sorted(p for p in records if '/web/map_infographic_v1/' in p or '/web/vendor/' in p)
    return {'parser': 'PINNED_BABEL_AST', 'parser_sha256': helpers.AST_PARSER_SHA,
            'parser_provider_lock': 'cinematic-world-map/package-lock.json', 'helper': record(helper_path),
            'roots': sorted(roots), 'reachable_modules': sorted(records), 'browser_runtime_modules': runtime_modules,
            'edges': sorted(edges, key=lambda r: (r['from'], r['line'], r['to'])),
            'locked_or_builtin_imports': sorted(externals, key=lambda r: (r['from'], r['specifier'])),
            'issues': [], 'required_temp_only_files': []}


def common_source_guard(paths):
    for path in paths:
        if '/web/map_infographic_v1/event_' not in path:
            continue
        text = safe_file(path).read_text()
        if re.search(r'\b(?:suez|egypt|COUNTRY_[A-Z_]+)\b|193\s*\.\s*30', text, re.I):
            raise ValueError('FIXTURE_HARDCODE_IN_COMMON_ENGINE: ' + path)
        if re.search(r'\b(?:lon|longitude|lat|latitude)\s*:\s*[-+]?\d', text):
            raise ValueError('FIXED_GEOGRAPHIC_COORDINATE_IN_COMMON_ENGINE: ' + path)
        if re.search(r'(?:file://|/tmp/|/workspace/)[^\s\'"`]*', text):
            raise ValueError('TEMPORARY_OR_ABSOLUTE_RUNTIME_REFERENCE: ' + path)


def documents():
    protections = protected_scope()
    runtime_ref, runtime = load_v5('RUNTIME_ASSET_MANIFEST')
    build_ref, build = load_v5('BUILD_INPUT_MANIFEST')
    dependency_ref, dependency = load_v5('DEPENDENCY_MANIFEST')
    source_ref, inherited_source = load_v5('SOURCE_MANIFEST')
    installed = toolchain(dependency)
    candidate = files_under(BASE, exclude=('manifests',))
    core = core_paths()
    common_source_guard(core)
    graph = import_graph(candidate)
    baseline = BASELINES['camera_v5']
    protected_rows = []
    for row in [*runtime['entries'], *runtime['plan_inputs'], *runtime.get('verification_inputs', []),
                runtime['reveal_plan'], *build['entries'], *build['dependency_locks'], build['recipe'],
                *inherited_source['source_files'], *inherited_source.get('final_verification_files', [])]:
        actual = unchanged(baseline, row['path'])
        if any(actual[k] != row[k] for k in ('sha256', 'bytes')):
            raise ValueError('INHERITED_V5_MANIFEST_MISMATCH: ' + row['path'])
        protected_rows.append(actual)
    for row in runtime['runtime_routes']:
        protected_rows.append(unchanged(baseline, row['file']))
    # The ordered capture CLI checks both complete saved 250-frame inventories,
    # rather than silently falling back to the earlier four-frame Core proof.
    for path in [V5 + '/evidence/runtime-diagnostic.json',
                 V5 + '/evidence/final/clean-video/runtime-diagnostic.json',
                 'cinematic-world-map/package.json']:
        protected_rows.append(unchanged(baseline, path))
    history = [unchanged(BASELINES['event_core'], path) for path in files_under(CORE + '/manifests')]
    data = [unchanged(BASELINES['production_data'], path) for path in files_under(DATA)]
    graph_rows = []
    for path in graph['reachable_modules']:
        if '/event_' in path or path.startswith(BASE + '/'):
            graph_rows.append(record(path, origin='CANDIDATE_EVENT_SOURCE'))
        else:
            graph_rows.append({**unchanged(baseline, path), 'origin': 'PROTECTED_V5_BASELINE'})
    source_paths = sorted(p for p in set(core + candidate)
                          if '/fixtures/' not in p and '/evidence/' not in p and '/public-review/' not in p)
    fixtures = sorted(set([p for p in core if '/fixtures/' in p] + [p for p in candidate if '/fixtures/' in p]))
    evidence = [p for p in candidate if '/evidence/' in p or '/public-review/' in p]
    base = {'schema': 1, 'scope': 'EVENT_SYSTEM_V1_CANDIDATE', 'status': 'USER_VIDEO_REVIEW_REQUIRED',
            'baselines': BASELINES, 'event_final': False, 'user_video_approved': False,
            'protected_changes': protections, 'required_temp_only_files': []}
    routes = {row['url']: row for row in runtime['runtime_routes']}
    for path in graph['browser_runtime_modules']:
        if '/web/map_infographic_v1/' in path:
            routes['/modules/' + Path(path).name] = {'url': '/modules/' + Path(path).name, 'file': path}
    source = {**base, 'entry': ENTRY, 'entries': graph_rows,
              'candidate_source_and_procedures': [record(p) for p in source_paths],
              'inherited_source_manifest': source_ref,
              'historical_core_manifests': history,
              'history_semantics': 'Original Core manifests describe the earlier committed Core, not current Event candidate source.'}
    fixture = {**base, 'entries': [record(p) for p in fixtures], 'production_data_entries': data,
               'production_fixture': record(DATA + '/fixture.json'), 'data_researched_or_regenerated': False}
    evidence_doc = {**base, 'entries': [record(p) for p in evidence],
                    'historical_core_evidence': [record(p) for p in core if '/evidence/' in p],
                    'acceptance': 'Technical evidence never supplies user video approval.'}
    runtime_doc = {**base, 'parent': runtime_ref, 'entries': runtime['entries'],
                   'plan_inputs': runtime['plan_inputs'], 'verification_inputs': runtime.get('verification_inputs', []),
                   'reveal_plan': runtime['reveal_plan'], 'production_fixture': record(DATA + '/fixture.json'),
                   'runtime_routes': sorted(routes.values(), key=lambda r: r['url']),
                   'retained_required_files': sorted({r['path'] for r in protected_rows} | {p for p in graph['browser_runtime_modules']})}
    build_doc = {**base, 'parent': build_ref, 'entries': build['entries'],
                 'recipe': build['recipe'], 'dependency_locks': build['dependency_locks'],
                 'new_data_downloaded': False, 'derivatives_regenerated': False,
                 'retention': 'Original Git/LFS objects remain the authoritative build inputs; no temporary runtime input is required.'}
    dependency_doc = {**base, 'parent': dependency_ref, 'dependencies': dependency['dependencies'],
                      'interpreters': dependency['interpreters'], 'observed_toolchain': installed,
                      'dependency_locks': build['dependency_locks'],
                      'setup': ['npm', '--prefix', 'cinematic-world-map', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--strict-ssl=true'],
                      'parser_provider': {'package': 'playwright', 'version': '1.62.1', 'sha256': graph['parser_sha256']},
                      'optional_verification_tools': [SECRET_SCAN_TOOL],
                      'preserved_baseline_files': sorted({r['path']: r for r in protected_rows}.values(), key=lambda r: r['path'])}
    return {'SOURCE_MANIFEST.json': source, 'FIXTURE_MANIFEST.json': fixture, 'EVIDENCE_MANIFEST.json': evidence_doc,
            'RUNTIME_ASSET_MANIFEST.json': runtime_doc, 'BUILD_INPUT_MANIFEST.json': build_doc,
            'DEPENDENCY_MANIFEST.json': dependency_doc, 'IMPORT_MANIFEST.json': {**base, **graph}}


def encode(document):
    return (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()


def inventory_of(documents):
    rows = {}
    def visit(value):
        if isinstance(value, dict):
            if all(k in value for k in ('path', 'sha256', 'bytes')):
                current = {k: value[k] for k in ('path', 'sha256', 'bytes')}
                previous = rows.get(current['path'])
                if previous and previous != current:
                    raise ValueError('CONFLICTING_REQUIRED_HASH: ' + current['path'])
                rows[current['path']] = current
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for doc in documents.values():
        visit(doc)
    # All mounted route bodies are required even if a parent lists them only by URL.
    for row in documents['RUNTIME_ASSET_MANIFEST.json']['runtime_routes']:
        path = row['file']
        actual = record(path)
        if path in rows and rows[path] != actual:
            raise ValueError('RUNTIME_ROUTE_HASH_CONFLICT: ' + path)
        rows[path] = actual
    return rows


def persisted(relative):
    file = safe_file(relative)
    actual = record(relative)
    expected = expected_body('HEAD', relative)
    if any(actual[k] != expected[k] for k in ('sha256', 'bytes')):
        raise ValueError('CANDIDATE_FILE_NOT_PERSISTED: ' + relative)
    # The index must agree too: a staged mutation is not a durable candidate.
    raw = git('show', ':' + relative)
    pointer = LFS.fullmatch(raw)
    index = ({'sha256': pointer[1].decode(), 'bytes': int(pointer[2])} if pointer
             else {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    if index != expected:
        raise ValueError('CANDIDATE_INDEX_DIFFERS_FROM_HEAD: ' + relative)
    return file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifests', action='store_true', help='Write only separate candidate manifests after evidence files settle')
    parser.add_argument('--inspect-only', action='store_true', help='Validate source/dependencies/protections and show closure without requiring saved manifests')
    parser.add_argument('--require-persisted', action='store_true', help='Require every inventoried body and manifest in HEAD and unchanged index')
    parser.add_argument('--clean-checkout', type=Path, help='Read-only compare committed required files against a separate checkout of the same HEAD')
    args = parser.parse_args()
    if args.inspect_only and (args.write_manifests or args.require_persisted or args.clean_checkout):
        parser.error('--inspect-only cannot be combined with write/persistence options')
    docs = documents()
    rows = inventory_of(docs)
    encoded = {name: encode(doc) for name, doc in docs.items()}
    for name, raw in encoded.items():
        path = BASE + '/manifests/' + name
        rows[path] = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    inventory = sorted(rows.values(), key=lambda r: r['path'])
    encoded['HASH_MANIFEST.json'] = encode({'schema': 1, 'scope': 'EVENT_SYSTEM_V1_CANDIDATE',
                                          'status': 'USER_VIDEO_REVIEW_REQUIRED', 'event_final': False,
                                          'required_files': inventory, 'required_temp_only_files': [],
                                          'self_hash_policy': 'HASH_MANIFEST.json and SHA256SUMS are excluded to avoid recursive self-hashes.'})
    encoded['SHA256SUMS'] = ''.join(r['sha256'] + '  ' + r['path'] + '\n' for r in inventory).encode()
    target = REPO / BASE / 'manifests'
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, raw in encoded.items():
            (target / name).write_bytes(raw)
    if not args.inspect_only:
        for name, raw in encoded.items():
            if (target / name).read_bytes() != raw:
                raise ValueError('CANDIDATE_MANIFEST_STALE_OR_CHANGED: ' + name)
    persistence_paths = sorted(set(rows) | {BASE + '/manifests/' + n for n in encoded})
    if args.require_persisted or args.clean_checkout:
        for path in persistence_paths:
            persisted(path)
    clean_status = 'NOT_CHECKED'
    if args.clean_checkout:
        clean = args.clean_checkout.absolute()
        if clean.resolve() == REPO.resolve() or REPO.resolve() in clean.resolve().parents or clean.resolve() in REPO.resolve().parents:
            raise ValueError('SEPARATE_CLEAN_CHECKOUT_REQUIRED')
        if subprocess.check_output(['git', '-C', str(clean), 'rev-parse', 'HEAD']).strip() != git('rev-parse', 'HEAD').strip():
            raise ValueError('CLEAN_CHECKOUT_HEAD_DIFFERS')
        if subprocess.check_output(['git', '-C', str(clean), 'status', '--porcelain', '--untracked-files=all']).strip():
            raise ValueError('CLEAN_CHECKOUT_DIRTY')
        for path in persistence_paths:
            other = clean / path
            ancestors = [other, *other.parents]
            if not other.is_file() or any(p.is_symlink() for p in ancestors):
                raise ValueError('CLEAN_CHECKOUT_REQUIRED_FILE_MISSING: ' + path)
            expected = record(path)
            digest = hashlib.sha256()
            with other.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if other.stat().st_size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
                raise ValueError('CLEAN_CHECKOUT_REQUIRED_BODY_MISMATCH: ' + path)
        clean_status = 'PASS'
    print(json.dumps({'scope': 'EVENT_SYSTEM_V1_CANDIDATE', 'technical_manifest_status': 'PASS',
                      'manifest_mode': 'INSPECT_ONLY' if args.inspect_only else 'SAVED_MANIFESTS_VERIFIED',
                      'required_files': len(rows), 'source_files': len(docs['SOURCE_MANIFEST.json']['entries']),
                      'fixture_files': len(docs['FIXTURE_MANIFEST.json']['entries']),
                      'evidence_files': len(docs['EVIDENCE_MANIFEST.json']['entries']),
                      'import_edges': len(docs['IMPORT_MANIFEST.json']['edges']),
                      'required_temp_only_files': 0, 'source_persisted': bool(args.require_persisted or args.clean_checkout),
                      'clean_checkout_files': clean_status, 'fresh_render_reproduction': 'NOT_CHECKED_BY_THIS_COMMAND',
                      'status': 'USER_VIDEO_REVIEW_REQUIRED', 'event_final': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
