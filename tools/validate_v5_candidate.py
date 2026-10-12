#!/usr/bin/env python3
"""Check V5 candidate bytes, actual AST closure and persistence; never render."""
import argparse
import ast
import hashlib
import importlib.util
import json
import posixpath
import subprocess
import sys
from pathlib import Path


def helpers():
    spec = importlib.util.spec_from_file_location('v5_manifest_helpers', Path(__file__).with_name('build_v5_candidate_manifests.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(repo):
    h = helpers()
    v4 = h.legacy(repo)
    _, baseline = h.pinned_baseline(repo, v4)
    manifest = h.OUT + '/DEPENDENCY_MANIFEST.json'
    imports = h.OUT + '/IMPORT_MANIFEST.json'
    gate = v4.Gate(repo, manifest, imports)
    problems, checked = [], {}
    for row in gate.manifest['required_files']:
        path = row['path']
        try:
            value = gate.file(path)
            if value['sha256'] != row['sha256'] or value['bytes'] != row['bytes'] or path in checked:
                raise ValueError('PAYLOAD_HASH_SIZE_OR_UNIQUENESS_MISMATCH')
            checked[path] = value
        except (OSError, ValueError, KeyError, TypeError):
            problems.append({'path': path, 'code': 'PAYLOAD_HASH_SIZE_OR_UNIQUENESS_MISMATCH'})
    expected = {r['path'] for r in baseline} | set(h.new_paths(repo))
    if set(checked) != expected:
        problems.append({'code': 'V5_PAYLOAD_INVENTORY_DOES_NOT_MATCH_CURRENT_ALLOWED_SCOPE'})
    bindings = gate.manifest['manifest_bindings']
    for path, expected_body in bindings.items():
        if v4.hash_file(v4.safe_file(repo, path)) != expected_body:
            problems.append({'path': path, 'code': 'MANIFEST_BINDING_MISMATCH'})
    source = json.loads(v4.safe_file(repo, h.OUT + '/SOURCE_MANIFEST.json').read_text())
    hashes = json.loads(v4.safe_file(repo, h.OUT + '/HASH_MANIFEST.json').read_text())
    if source['immutable_baseline_files'] != baseline or hashes['payload_files'] != gate.manifest['required_files']:
        problems.append({'code': 'SOURCE_HASH_DEPENDENCY_ROWS_DIFFER'})
    if sorted(source['new_files'], key=lambda r: r['path']) != [r for r in gate.manifest['required_files'] if r['path'] not in {b['path'] for b in baseline}]:
        problems.append({'code': 'SOURCE_NEW_SCOPE_ROWS_DIFFER'})
    expected_sums = {r['path']: r['sha256'] for r in gate.manifest['required_files']}
    expected_sums.update({h.OUT + '/' + name: v4.hash_file(v4.safe_file(repo, h.OUT + '/' + name))['sha256'] for name in h.NAMES if name != 'SHA256SUMS'})
    actual_sums = {}
    for line in v4.safe_file(repo, h.OUT + '/SHA256SUMS').read_text().splitlines():
        sha, path = line.split('  ', 1)
        if path in actual_sums:
            problems.append({'code': 'SHA256SUMS_DUPLICATE'})
        actual_sums[path] = sha
    if actual_sums != expected_sums:
        problems.append({'code': 'SHA256SUMS_FULL_BINDINGS_DIFFER'})
    # The original Gate methods below inspect actual source and pinned metadata.
    # Body-verified candidate rows are passed only to its dependency/AST methods,
    # never to its persistence or reproduction methods. HEAD is never changed.
    gate.rows = {row['path']: row for row in gate.manifest['required_files']}
    gate.checked = checked
    gate.dependencies()
    gate.ast()
    build_paths = [p for p in h.new_paths(repo) if p.endswith(('.mjs', '.js')) and p not in gate.imports_manifest['modules']]
    build = h.parse_js(repo, v4, gate.imports_manifest['parser'], build_paths)
    build_errors = []
    actual_build = [{'path': p, 'imports': r['imports'], 'requires': r['requires'], 'issues': r['issues']} for p, r in sorted(build.items())]
    if actual_build != gate.imports_manifest.get('build_files'):
        build_errors.append({'code': 'DECLARED_AND_ACTUAL_BUILD_AST_RECORDS_DIFFER'})
    runtime_records = h.parse_js(repo, v4, gate.imports_manifest['parser'], gate.imports_manifest['modules'])
    all_records = {**runtime_records, **build}
    declared = {(row['importer'], row['specifier']): row['resolved_path'] for row in gate.imports_manifest['imports']}
    ambiguous = object()

    def binding(path, name, seen=frozenset()):
        if (path, name) in seen or path not in all_records:
            return None
        seen = seen | {(path, name)}
        record = all_records[path]
        if name in record['localbindings']:
            return path, record['localbindings'][name]
        for row in record['reexports']:
            target = declared.get((path, row['specifier']))
            for pair in row['names'] or []:
                if pair['exported'] == name:
                    return (target, '*namespace*') if pair['imported'] == '*' and target in all_records else binding(target, pair['imported'], seen)
        if name == 'default':
            return None
        answer = None
        for row in record['reexports']:
            if row['names'] is not None:
                continue
            value = binding(declared.get((path, row['specifier'])), name, seen)
            if value is ambiguous or answer is not None and value is not None and answer != value:
                return ambiguous
            if value is not None:
                answer = value
        return answer

    builtins = set(json.loads(subprocess.check_output(['node', '-e', "process.stdout.write(JSON.stringify(require('node:module').builtinModules.map(x=>x.replace(/^node:/,''))))"])))
    builtin_names = sorted({entry['specifier'] for record in build.values() for entry in record['imports'] + record['requires']
                            if entry['specifier'].startswith('node:') and entry['specifier'][5:] in builtins})
    builtin_program = "const fs=require('node:fs'),out={};for(const name of JSON.parse(fs.readFileSync(0,'utf8')))out[name]=Object.keys(require(name));process.stdout.write(JSON.stringify(out));"
    builtin_exports = json.loads(subprocess.run(['node', '-e', builtin_program], input=json.dumps(builtin_names).encode(),
                                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=30).stdout)
    package_names = {r['name'] for r in gate.manifest['dependencies']}
    for path, record in build.items():
        for issue in record['issues']:
            if issue['code'] != 'COMMONJS_RUNTIME_CLOSURE_REQUIRES_REVIEW':
                build_errors.append({'path': path, 'code': issue['code']})
        for item in record['imports'] + record['requires']:
            name = item['specifier']
            if name.startswith('node:') and name[5:] in builtins:
                if not set(item.get('names', [])) <= set(builtin_exports[name]):
                    build_errors.append({'path': path, 'code': 'NODE_BUILD_BUILTIN_BINDING_MISSING'})
                continue
            if name.startswith('.'):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), name))
                if target in checked:
                    required_names = set(item.get('names', [])) | ({'default'} if item.get('default') else set())
                    if any(binding(target, n) in (None, ambiguous) for n in required_names):
                        build_errors.append({'path': path, 'code': 'LOCAL_BUILD_IMPORT_BINDING_MISSING_OR_AMBIGUOUS'})
                    continue
            if name.removesuffix('/package.json') in package_names:
                continue
            build_errors.append({'path': path, 'code': 'BUILD_IMPORT_NOT_IN_INVENTORY_OR_PINNED'})
    python_records = []
    for path in h.new_paths(repo):
        if path.endswith('.py'):
            tree = ast.parse(v4.safe_file(repo, path).read_text(), filename=path)
            declared_names = []
            for node in ast.walk(tree):
                names = [r.name for r in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    declared_names.append(name)
                    if (name or '').split('.')[0] not in sys.stdlib_module_names | set(sys.builtin_module_names):
                        build_errors.append({'path': path, 'code': 'PYTHON_BUILD_IMPORT_NOT_STANDARD_LIBRARY'})
            python_records.append({'path': path, 'imports': declared_names,
                                   'reviewed_helper_loads': [h.LEGACY] if path == h.TOOLS[0] else [h.TOOLS[0]] if path == h.TOOLS[1] else []})
    if python_records != gate.imports_manifest.get('python_build_files'):
        build_errors.append({'code': 'DECLARED_AND_ACTUAL_PYTHON_BUILD_IMPORTS_DIFFER'})
    public = repo / h.V5 / 'public-review'
    public_errors = [p.relative_to(repo).as_posix() for p in public.rglob('*') if p.is_file() and p.suffix.lower() not in ('.mp4', '.png') and p.name != 'SHA256SUMS'] if public.exists() else []
    persistence = []
    algorithm = v4.git(repo, 'rev-parse', '--show-object-format').decode().strip()
    for path in sorted(expected | {h.OUT + '/' + name for name in h.NAMES}):
        indexed, head = gate.index.get(path), gate.tree.get(path)
        if not indexed or not head or indexed != head or head[0] not in ('100644', '100755'):
            persistence.append(path)
            continue
        file = v4.safe_file(repo, path)
        size = file.stat().st_size
        if int(v4.git(repo, 'cat-file', '-s', head[1])) < 1024:
            pointer = v4.LFS.fullmatch(v4.git(repo, 'cat-file', 'blob', head[1]))
            if pointer:
                actual = checked.get(path) or v4.hash_file(file)
                if actual['sha256'] != pointer[1].decode() or actual['bytes'] != int(pointer[2]):
                    persistence.append(path)
                continue
        oid = hashlib.new(algorithm)
        oid.update(('blob ' + str(size) + '\0').encode())
        with file.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                oid.update(chunk)
        if oid.hexdigest() != head[1]:
            persistence.append(path)
    ast_reasons = gate.conditions['IMPORT_MANIFEST_PASS']['reasons'] + build_errors
    preflight = {'BASELINE_98_UNCHANGED': 'PASS', 'HASH_MANIFEST_PASS': 'FAIL' if problems else 'PASS',
                 'ASSETS_BOUND_TO_BASELINE': 'PASS' if not problems else 'FAIL',
                 'DEPENDENCY_MANIFEST_PASS': gate.conditions['DEPENDENCY_MANIFEST_PASS']['status'],
                 'IMPORT_MANIFEST_PASS': 'FAIL' if ast_reasons else 'PASS',
                 'NO_REQUIRED_TEMP_FILES': 'PASS' if not problems else 'FAIL',
                 'PUBLIC_REVIEW_POLICY': 'FAIL' if public_errors else 'PASS'}
    complete = all(x == 'PASS' for x in preflight.values())
    conditions = {name: {'status': 'NOT_RUN_PENDING_USER_VIDEO_APPROVAL'} for name in v4.CONDITIONS}
    conditions['SOURCE_PERSISTED'] = {'status': 'FAIL' if persistence else 'PASS', 'unpersisted_paths': persistence}
    conditions['ASSETS_PERSISTED'] = {'status': 'NOT_RUN_PENDING_USER_VIDEO_APPROVAL',
                                    'local_git_body_status': 'PASS' if not any(persistence_path in {r['path'] for r in gate.manifest['required_files'] if r['kind'] == 'asset'} for persistence_path in persistence) else 'FAIL',
                                    'remote_clean_clone_availability': 'BASELINE_ONLY_V5_CURRENT_COMMIT_NOT_REVERIFIED'}
    return {'schema': 1, 'state': 'V5_CANDIDATE', 'source_commit': gate.head, 'baseline_metadata_commit': h.BASELINE,
            'candidate_preflight': preflight, 'preflight_status': 'PASS' if complete else 'FAIL',
            'immutable_baseline_files': len(baseline), 'required_payload_files': len(checked),
            'ast_import_graph': gate.graph, 'build_ast_files': len(build),
            'problems': problems, 'import_problems': ast_reasons,
            'dependency_problems': gate.conditions['DEPENDENCY_MANIFEST_PASS']['reasons'],
            'public_review_policy_failures': public_errors, 'permanent_conditions': conditions,
            'final_permanent_gate': 'NOT_RUN_PENDING_USER_VIDEO_APPROVAL', 'overall': 'V5_CANDIDATE',
            'user_review': 'USER_VIDEO_REVIEW_REQUIRED', 'next_development_stage_allowed': False,
            'engine_executed': False, 'render_executed': False, 'git_mutations': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--require-persisted', action='store_true')
    args = parser.parse_args()
    report = check(args.repo.absolute())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['preflight_status'] == 'PASS' and (not args.require_persisted or report['permanent_conditions']['SOURCE_PERSISTED']['status'] == 'PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
