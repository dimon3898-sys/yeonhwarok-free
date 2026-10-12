#!/usr/bin/env python3
"""Record V5 candidate inputs without building, rendering, installing or committing."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import posixpath
import subprocess
from pathlib import Path

BASELINE = '1bcd9d0b5ecc5385a61317ce70fa6927565c3d24'
BASELINE_SOURCE = '786521b87b5edd65dfd7ff507d2f0fbaa08f0152'
BASELINE_SHA = '24bf44dc623991cc8c8fabf00a3f8df6f1f66af083b13b1c2953d00a058693b0'
ENGINE = 'world-simulation-shorts-engine'
V4 = ENGINE + '/recovery/v4'
V5 = ENGINE + '/recovery/v5'
OUT = V5 + '/manifests'
NAMES = ('SOURCE_MANIFEST.json', 'HASH_MANIFEST.json', 'DEPENDENCY_MANIFEST.json', 'IMPORT_MANIFEST.json', 'SHA256SUMS')
TOOLS = ('tools/build_v5_candidate_manifests.py', 'tools/validate_v5_candidate.py')
LEGACY = 'tools/v4_recovery_gate.py'


def legacy(repo):
    spec = importlib.util.spec_from_file_location('v4_candidate_readonly_helpers', repo / LEGACY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.DEVNULL)


def document(repo, revision, path):
    return json.loads(git(repo, 'show', revision + ':' + path))


def tree(repo, revision):
    result = {}
    for row in git(repo, 'ls-tree', '-r', '-z', revision).split(b'\0'):
        if row:
            metadata, name = row.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            if kind == 'blob':
                result[name.decode()] = {'mode': mode, 'git_oid': oid}
    return result


def pinned_baseline(repo, module):
    dependency = document(repo, BASELINE, V4 + '/runtime/DEPENDENCY_MANIFEST.json')
    paths = [r['path'] for r in dependency['required_files']] + dependency['inventory_manifests'] + [
        V4 + '/runtime/DEPENDENCY_MANIFEST.json', V4 + '/runtime/IMPORT_MANIFEST.json',
        V4 + '/BASELINE_MANIFEST.json', V4 + '/BASELINE_POLICY.md']
    expected = {r['path']: r for r in dependency['required_files']}
    original, current = tree(repo, BASELINE), tree(repo, 'HEAD')
    result = []
    for path in paths:
        value = module.hash_file(module.safe_file(repo, path))
        if current.get(path) != original.get(path):
            raise ValueError('IMMUTABLE_BASELINE_GIT_OBJECT_CHANGED: ' + path)
        raw = git(repo, 'cat-file', 'blob', original[path]['git_oid']) if path not in expected else None
        wanted = expected.get(path, {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}) if raw is not None else expected[path]
        if value != {'sha256': wanted['sha256'], 'bytes': wanted['bytes']}:
            raise ValueError('IMMUTABLE_BASELINE_BODY_CHANGED: ' + path)
        result.append({'path': path, 'kind': wanted.get('kind', 'evidence'), **value, **original[path]})
    if len(result) != 98 or next(x for x in result if x['path'] == V4 + '/BASELINE_MANIFEST.json')['sha256'] != BASELINE_SHA:
        raise ValueError('BASELINE_IDENTITY_OR_98_SCOPE_INVALID')
    return dependency, result


def new_paths(repo):
    paths = set(TOOLS)
    directory = repo / V5
    for file in directory.rglob('*'):
        relative = file.relative_to(repo).as_posix()
        if any(part in ('manifests', 'public-review', 'evidence', '__pycache__') for part in file.relative_to(directory).parts):
            continue
        if file.is_file():
            paths.add(relative)
    paths.update(p.relative_to(repo).as_posix() for p in (repo / ENGINE / 'tests').rglob('*v5*') if p.is_file())
    paths.update(ENGINE + '/web/map_infographic_v1/' + n for n in ('camera_director_v5.mjs', 'camera_gpu_pipeline_v5.mjs'))
    return sorted(paths)


def kind(path):
    if '/inputs/' in path or '/fixtures/' in path:
        return 'input'
    if '/tests/' in path or path.startswith('tools/') or path.endswith(('.py', 'compile_inputs.mjs', 'render_candidate.mjs')):
        return 'procedure'
    if path.endswith(('.mjs', '.js')):
        return 'source'
    return 'input'


def parse_js(repo, module, parser, paths):
    installed = module.hash_file(module.safe_file(repo, parser['path']))
    if installed != {'sha256': parser['sha256'], 'bytes': parser['bytes']}:
        raise ValueError('PINNED_BABEL_PARSER_CHANGED')
    request = {'parser': str(module.safe_file(repo, parser['path'])), 'files': [
        {'path': p, 'absolute': str(module.safe_file(repo, p))} for p in paths]}
    result = subprocess.run(['node', '-e', module.AST_PROGRAM], input=json.dumps(request).encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=120)
    return {r['path']: r for r in json.loads(result.stdout)}


def graph(repo, module, parser, rows, routes):
    entry = V5 + '/harness.mjs'
    route_map = {r['url']: r['file'] for r in routes}
    records, edges, pending = {}, [], [entry]
    while pending:
        path = pending.pop()
        if path in records:
            continue
        if path not in rows or rows[path]['kind'] not in ('source', 'dependency'):
            raise ValueError('RUNTIME_IMPORT_NOT_IN_INVENTORY: ' + path)
        record = parse_js(repo, module, parser, [path])[path]
        if record['issues']:
            raise ValueError('RUNTIME_AST_UNRESOLVED_IMPORT_OR_PARSE: ' + path)
        records[path] = record
        for item in record['imports']:
            specifier = item['specifier']
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), specifier)) if specifier.startswith('.') else route_map.get(specifier)
            if not target:
                raise ValueError('RUNTIME_IMPORT_ROUTE_UNRESOLVED: ' + path)
            edges.append({'importer': path, 'specifier': specifier, 'resolved_path': target, 'kind': item['kind'], 'line': item['line']})
            pending.append(target)
    return {'schema': 1, 'scope': 'V5_CANDIDATE', 'parser': copy.deepcopy(parser), 'entrypoints': [entry],
            'modules': sorted(records), 'imports': sorted(edges, key=lambda x: (x['importer'], x['line'], x['specifier'])),
            'review': {'method': 'BABEL_AST_ACTUAL_SOURCE', 'engine_executed': False,
                       'binding_validation': 'Required by validate_v5_candidate.py; generation alone is not approval'}}


def serialize(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def build(repo):
    module = legacy(repo)
    baseline, protected = pinned_baseline(repo, module)
    paths = new_paths(repo)
    shared = {row['path']: row for row in protected}
    added = [{'path': path, 'kind': kind(path), **module.hash_file(module.safe_file(repo, path))} for path in paths]
    if any(row['path'] in shared for row in added):
        raise ValueError('V5_NEW_SCOPE_OVERLAPS_IMMUTABLE_BASELINE')
    rows = {row['path']: row for row in protected + added}
    routes = {row['url']: copy.deepcopy(row) for row in baseline['runtime_routes']}
    overrides = {'/': V5 + '/index.html', '/index.html': V5 + '/index.html', '/harness.mjs': V5 + '/harness.mjs',
                 '/inputs/scene.json': V5 + '/inputs/scene.json', '/inputs/camera-plan.json': V5 + '/inputs/camera-plan.json'}
    overrides.update({'/modules/' + name: ENGINE + '/web/map_infographic_v1/' + name for name in ('camera_director_v5.mjs', 'camera_gpu_pipeline_v5.mjs')})
    routes.update({url: {'url': url, 'file': path} for url, path in overrides.items()})
    routes = sorted(routes.values(), key=lambda row: row['url'])
    parser = document(repo, BASELINE, V4 + '/runtime/IMPORT_MANIFEST.json')['parser']
    imports = graph(repo, module, parser, rows, routes)
    build_paths = [p for p in paths if p.endswith(('.mjs', '.js')) and p not in imports['modules']]
    build_records = parse_js(repo, module, parser, build_paths)
    imports['build_files'] = [{'path': p, 'imports': r['imports'], 'requires': r['requires'], 'issues': r['issues']}
                             for p, r in sorted(build_records.items())]
    imports['python_build_files'] = []
    for path in paths:
        if path.endswith('.py'):
            syntax = ast.parse(module.safe_file(repo, path).read_text(), filename=path)
            names = []
            for node in ast.walk(syntax):
                if isinstance(node, ast.Import):
                    names.extend(item.name for item in node.names)
                elif isinstance(node, ast.ImportFrom):
                    names.append(node.module)
            imports['python_build_files'].append({'path': path, 'imports': names,
                                                  'reviewed_helper_loads': [LEGACY] if path == TOOLS[0] else [TOOLS[0]] if path == TOOLS[1] else []})
    source = {'schema': 1, 'state': 'V5_CANDIDATE', 'baseline': {'metadata_commit': BASELINE, 'source_commit': BASELINE_SOURCE,
              'manifest_sha256': BASELINE_SHA, 'name': 'V4_RECOVERED_EQUIVALENT_BASELINE'},
              'immutable_baseline_files': protected, 'new_files': added,
              'permanent_status': 'PENDING_COMMIT_AND_USER_VIDEO_REVIEW', 'automatic_next_stage_allowed': False}
    hashes = {'schema': 1, 'scope': 'V5_CANDIDATE_RUNTIME_AND_BUILD', 'payload_files': sorted(rows.values(), key=lambda r: r['path']),
              'manifest_binding': 'SOURCE and IMPORT metadata bound by DEPENDENCY; DEPENDENCY and SHA256SUMS are verified from actual Git HEAD to avoid a self-hash cycle'}
    objects = {'SOURCE_MANIFEST.json': serialize(source), 'HASH_MANIFEST.json': serialize(hashes), 'IMPORT_MANIFEST.json': serialize(imports)}
    dependency = {'schema': 1, 'scope': 'V5_CANDIDATE', 'state': 'V5_CANDIDATE',
                  'baseline_commit': BASELINE, 'required_files': sorted(rows.values(), key=lambda r: r['path']),
                  'dependencies': copy.deepcopy(baseline['dependencies']), 'interpreters': copy.deepcopy(baseline['interpreters']),
                  'runtime_routes': routes, 'inventory_manifests': [OUT + '/' + name for name in ('SOURCE_MANIFEST.json', 'HASH_MANIFEST.json')],
                  'manifest_bindings': {OUT + '/' + name: {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)} for name, body in objects.items()},
                  'completeness': {'source_contracts_confirmed': True, 'runtime_inputs_complete': True,
                                   'required_file_inventory_complete': True, 'dependency_graph_complete': True, 'import_graph_complete': True},
                  'stage_validation': {'status': 'USER_VIDEO_REVIEW_REQUIRED', 'functional_approval_confirmed': False,
                                       'final_permanent_gate': 'NOT_RUN_PENDING_USER_VIDEO_APPROVAL', 'automatic_next_stage_authorized': False},
                  'fresh_reproduction': {'receipt_path': None, 'procedure_path': V5 + '/render_candidate.mjs',
                                         'approved_command': ['node', '{checkout}/' + V5 + '/render_candidate.mjs', '--phase', 'video', '--output-dir', '{evidence}'],
                                         'scope': 'New V5 capture; no V4 receipt certifies V5'},
                  'limits': ['Candidate body/AST preflight is separate from actual committed persistence and postapproval seven-condition Gate.',
                             'No engine or archived procedure is executed by either manifest tool.',
                             'Shared baseline LFS bodies are hashed; remote availability requires separate actual clone evidence.',
                             'Internal evidence is separate from public-review, whose permitted files are MP4, PNG and SHA256SUMS.']}
    objects['DEPENDENCY_MANIFEST.json'] = serialize(dependency)
    sums = {row['path']: row['sha256'] for row in rows.values()}
    sums.update({OUT + '/' + name: hashlib.sha256(body).hexdigest() for name, body in objects.items()})
    objects['SHA256SUMS'] = ''.join(sha + '  ' + path + '\n' for path, sha in sorted(sums.items())).encode()
    out = repo / OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, body in objects.items():
        target = out / name
        if target.is_symlink():
            raise ValueError('MANIFEST_SYMLINK_FORBIDDEN')
        target.write_bytes(body)
    return {'state': 'V5_CANDIDATE', 'immutable_baseline': len(protected), 'new_payload_files': len(added),
            'required_files': len(rows), 'runtime_modules': len(imports['modules']), 'runtime_imports': len(imports['imports']),
            'outputs': [OUT + '/' + name for name in NAMES], 'engine_executed': False, 'render_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).absolute().parent.parent)
    args = parser.parse_args()
    print(json.dumps(build(args.repo.absolute()), ensure_ascii=False))


if __name__ == '__main__':
    main()
