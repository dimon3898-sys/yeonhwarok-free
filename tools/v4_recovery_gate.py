#!/usr/bin/env python3
"""Read-only V4 persistence, AST import and fresh-reproduction evidence checker.

Never installs, builds, renders, imports engine modules or changes Git. Uncommitted
files may be inspected, but cannot satisfy a permanent persistence condition.
The AST child only parses source text with the pinned installed Babel parser.
"""
import argparse
import ast
import datetime as dt
import hashlib
import importlib.metadata
import json
import posixpath
import platform
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

CONDITIONS = ('SOURCE_PERSISTED', 'ASSETS_PERSISTED', 'HASH_MANIFEST_PASS',
              'DEPENDENCY_MANIFEST_PASS', 'IMPORT_MANIFEST_PASS',
              'NO_REQUIRED_TEMP_FILES', 'CLEAN_ENV_REPRODUCIBLE')
BASE = 'world-simulation-shorts-engine/recovery/v4'
RECOVERY = BASE + '/RECOVERY_MANIFEST.json'
RECOVERY_SHA = '35029465f7712bd930bec3d297692aed218354d9ccbabda8b900c22bbfe09029'
GLYPH = 'world-simulation-shorts-engine/web/map_infographic_v1/glyph_atlas.mjs'
GLYPH_SHA = '34c30d6fd57e9a9821ec8058ec65285a2402f6b72a30a534773a044dbe770386'
GOLDEN = BASE + '/approved-proof/07_FINAL_HOLD.png'
GOLDEN_SHA = 'fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673'
GOLDEN_RGBA_SHA = 'cee0e480f1a0941f13d7bbe675952abe5a3bef53dd0bcc44c001f856982e7376'
AST_PARSER = 'cinematic-world-map/node_modules/playwright/lib/transform/babelBundle.js'
AST_PARSER_SHA = '01511e45db7646e2a12890de8d7866caa0754c8799db6407a6345236f4bed0c4'
SHA = re.compile(r'[0-9a-f]{64}')
LFS = re.compile(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n')
BLOCKED = {'.git', '.env', '.aws', '.ssh', '.gnupg', '.codex', '.docker', '.kube',
           '.npmrc', '.netrc', '.pypirc', '.git-credentials', 'credentials',
           'credentials.json', 'auth.json', 'tokens.json', 'passwords.dat'}
KINDS = {'source', 'asset', 'input', 'procedure', 'dependency_lock', 'dependency', 'evidence'}

AST_PROGRAM = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const parser = require(input.parser);
function boundNames(n, out = []) {
  if (!n) return out;
  if (n.type === 'Identifier') out.push(n.name);
  else if (n.type === 'RestElement') boundNames(n.argument, out);
  else if (n.type === 'AssignmentPattern') boundNames(n.left, out);
  else if (n.type === 'ArrayPattern') n.elements.forEach(x => boundNames(x, out));
  else if (n.type === 'ObjectPattern') n.properties.forEach(x => boundNames(x.value || x.argument, out));
  return out;
}
function literal(n) {
  if (n && n.type === 'StringLiteral') return n.value;
  if (n && n.type === 'TemplateLiteral' && n.expressions.length === 0)
    return n.quasis[0].value.cooked;
  return null;
}
const results = [];
for (const item of input.files) {
  const output = {path:item.path, imports:[], requires:[], exports:[], localbindings:{}, reexports:[], default:false, issues:[]};
  let ast;
  try { ast = parser.babelParse(typeof item.source === 'string' ? item.source : fs.readFileSync(item.absolute, 'utf8'), item.absolute, true); }
  catch (_) { output.issues.push({code:'BABEL_PARSE_FAILED'}); results.push(output); continue; }
  function importRow(n, kind) {
    const source = literal(n.source);
    const named = []; let def = false;
    for (const s of n.specifiers || []) {
      if (s.type === 'ImportDefaultSpecifier') def = true;
      else if (s.type === 'ImportSpecifier') named.push(s.imported.name || s.imported.value);
    }
    output.imports.push({specifier:source, kind, names:named, default:def, line:n.loc.start.line});
  }
  function visit(n) {
    if (!n || typeof n !== 'object') return;
    if (n.type === 'ImportDeclaration') importRow(n, 'static');
    if (n.type === 'ExportDefaultDeclaration') {
      output.default = true;
      output.localbindings.default = ['FunctionDeclaration','ClassDeclaration'].includes(n.declaration.type) && n.declaration.id ? n.declaration.id.name : '*default*';
    }
    if (n.type === 'ExportNamedDeclaration') {
      if (n.declaration) {
        const d=n.declaration;
        const names=[];
        if (d.type === 'VariableDeclaration') d.declarations.forEach(x => boundNames(x.id, names));
        else if (d.id) names.push(d.id.name);
        for (const name of names) { output.exports.push(name); output.localbindings[name]=name; }
      }
      if (n.source) {
        output.imports.push({specifier:literal(n.source), kind:'reexport', names:[], default:false, line:n.loc.start.line});
        output.reexports.push({specifier:literal(n.source), names:(n.specifiers || []).map(s => ({
          imported:s.local ? (s.local.name || s.local.value) : '*',
          exported:s.exported.name || s.exported.value}))});
      } else for (const s of n.specifiers || []) {
        const name=s.exported.name || s.exported.value;
        output.exports.push(name); output.localbindings[name]=s.local.name || s.local.value;
      }
    }
    if (n.type === 'ExportAllDeclaration') {
      output.imports.push({specifier:literal(n.source), kind:'reexport', names:[], default:false, line:n.loc.start.line});
      output.reexports.push({specifier:literal(n.source), names:null});
    }
    if (n.type === 'ImportExpression' || n.type === 'CallExpression' && n.callee.type === 'Import') {
      const source=literal(n.type === 'ImportExpression' ? n.source : n.arguments[0]);
      if (source === null) output.issues.push({code:'NON_LITERAL_DYNAMIC_IMPORT', line:n.loc.start.line});
      else output.imports.push({specifier:source, kind:'dynamic', names:[], default:false, line:n.loc.start.line});
    }
    if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && n.callee.name === 'require') {
      const specifier=literal(n.arguments[0]);
      if (specifier === null) output.issues.push({code:'NON_LITERAL_COMMONJS_IMPORT', line:n.loc.start.line});
      else output.requires.push({specifier,line:n.loc.start.line});
      output.issues.push({code:'COMMONJS_RUNTIME_CLOSURE_REQUIRES_REVIEW', line:n.loc.start.line});
    }
    if (n.type === 'NewExpression' && n.callee.type === 'Identifier' && ['Worker','SharedWorker'].includes(n.callee.name))
      output.issues.push({code:'WORKER_RUNTIME_CLOSURE_REQUIRES_REVIEW', line:n.loc.start.line});
    for (const [key, value] of Object.entries(n)) {
      if (['loc','tokens','comments'].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === 'object') visit(value);
    }
  }
  visit(ast); output.exports=[...new Set(output.exports)]; results.push(output);
}
process.stdout.write(JSON.stringify(results));
'''


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def safe_file(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise ValueError('UNSAFE_PATH')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or any(x in BLOCKED or x.startswith('.env.') for x in parts.parts):
        raise ValueError('UNSAFE_PATH')
    root = Path(root).absolute()
    if any(x.is_symlink() or x.name in BLOCKED or x.name.startswith('.env.') for x in [root, *root.parents]):
        raise ValueError('SYMLINK_ROOT_FORBIDDEN')
    path = root
    for part in parts.parts:
        path /= part
        if path.is_symlink():
            raise ValueError('SYMLINK_FORBIDDEN')
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('REGULAR_FILE_REQUIRED')
    return path


def hash_file(path):
    before = path.stat()
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('FILE_CHANGED_DURING_SCAN')
    return {'sha256': sha.hexdigest(), 'bytes': before.st_size}


def inventory(repo, tree=False):
    result = {}
    command = ['ls-tree', '-r', '-z', 'HEAD'] if tree else ['ls-files', '--stage', '-z']
    for row in git(repo, *command).split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, middle, last = metadata.decode().split()
        if tree and middle != 'blob':
            continue
        if not tree and last != '0':
            raise ValueError('UNMERGED_INDEX')
        result[name.decode()] = (mode, last if tree else middle)
    return result


class Gate:
    def __init__(self, repo, manifest, import_manifest, lfs_checkout=None, lfs_receipt=None):
        self.repo, self.manifest_path, self.import_path = repo, manifest, import_manifest
        self.head = git(repo, 'rev-parse', 'HEAD').decode().strip()
        self.algorithm = git(repo, 'rev-parse', '--show-object-format').decode().strip()
        self.index, self.tree = inventory(repo), inventory(repo, True)
        self.conditions = {x: {'status': 'FAIL', 'reasons': []} for x in CONDITIONS}
        self.checked, self.rows, self.cache = {}, {}, {}
        self.guards, self.graph = {}, {}
        self.validated_parser = None
        self.lfs_checkout, self.lfs_receipt = lfs_checkout, lfs_receipt
        self.manifest = json.loads(safe_file(repo, manifest).read_text())
        self.imports_manifest = json.loads(safe_file(repo, import_manifest).read_text())

    def reason(self, condition, code, path=None):
        row = {'code': code}
        if path is not None:
            row['path'] = path
        if row not in self.conditions[condition]['reasons']:
            self.conditions[condition]['reasons'].append(row)

    def finish(self, condition):
        self.conditions[condition]['status'] = 'FAIL' if self.conditions[condition]['reasons'] else 'PASS'

    def file(self, relative):
        if relative not in self.cache:
            path = safe_file(self.repo, relative)
            self.cache[relative] = {**hash_file(path), 'path': path}
        return self.cache[relative]

    def persisted(self, relative):
        actual = self.file(relative)
        indexed, head = self.index.get(relative), self.tree.get(relative)
        if not indexed or not head or indexed != head or head[0] not in ('100644', '100755'):
            raise ValueError('FILE_NOT_COMMITTED_IN_HEAD')
        # Git's canonical object bytes are inspected without filters or LFS fetch.
        size = int(git(self.repo, 'cat-file', '-s', head[1]))
        if size < 1024:
            body = git(self.repo, 'cat-file', 'blob', head[1])
            pointer = LFS.fullmatch(body)
            if pointer:
                if actual['sha256'] != pointer[1].decode() or actual['bytes'] != int(pointer[2]):
                    raise ValueError('LFS_LOCAL_OBJECT_DIFFERS_FROM_POINTER')
                # A local hydrated object does not prove remote or clean-clone availability.
                if self.lfs_checkout is None or self.lfs_receipt is None:
                    raise ValueError('LFS_CLEAN_CLONE_AVAILABILITY_UNVERIFIED')
                receipt_path = Path(self.lfs_receipt).absolute()
                receipt = json.loads(safe_file(receipt_path.parent, receipt_path.name).read_text())
                checkout = Path(self.lfs_checkout).absolute()
                if receipt.get('schema') != 1 or receipt.get('kind') != 'lfs_clean_clone_verification' or receipt.get('source_commit') != self.head:
                    raise ValueError('LFS_RECEIPT_SCHEMA_OR_COMMIT_INVALID')
                if checkout.resolve() == self.repo.resolve() or checkout.resolve() in self.repo.resolve().parents or self.repo.resolve() in checkout.resolve().parents:
                    raise ValueError('LFS_SEPARATE_CLEAN_CHECKOUT_REQUIRED')
                if Path(receipt['checkout_path']).resolve() != checkout.resolve() or git(checkout, 'rev-parse', 'HEAD').decode().strip() != self.head:
                    raise ValueError('LFS_CLEAN_CHECKOUT_COMMIT_DIFFERS')
                if git(checkout, 'status', '--porcelain', '--untracked-files=all').strip():
                    raise ValueError('LFS_CLEAN_CHECKOUT_DIRTY')
                expected = {'sha256': actual['sha256'], 'bytes': actual['bytes']}
                if receipt.get('files', {}).get(relative) != expected or hash_file(safe_file(checkout, relative)) != expected:
                    raise ValueError('LFS_CLEAN_CHECKOUT_BODY_DIFFERS')
                actual = {**actual, 'storage': 'git_lfs', 'git_oid': head[1]}
                return actual
        oid = hashlib.new(self.algorithm)
        oid.update(('blob ' + str(actual['bytes']) + '\0').encode())
        with actual['path'].open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                oid.update(chunk)
        if oid.hexdigest() != head[1]:
            raise ValueError('WORKTREE_DIFFERS_FROM_HEAD')
        return {**actual, 'storage': 'git_blob', 'git_oid': head[1]}

    def protected(self):
        rows = []
        try:
            actual = self.file(RECOVERY)
            if actual['sha256'] != RECOVERY_SHA:
                raise ValueError('RECOVERY_MANIFEST_PROTECTION_FAILED')
            data = json.loads(actual['path'].read_text())
            rows = data['restored_files']
            if not isinstance(rows, list) or len(rows) != 43:
                raise ValueError('PROTECTED43_INVENTORY_INVALID')
            failures = []
            persistence_failures = []
            for row in rows:
                value = self.file(row['target_path'])
                if value['sha256'] != row['sha256'] or value['bytes'] != row['bytes']:
                    failures.append(row['target_path'])
                try:
                    self.persisted(row['target_path'])
                except (OSError, ValueError, KeyError, TypeError):
                    persistence_failures.append(row['target_path'])
            self.guards['protected43'] = {'status': 'FAIL' if failures else 'PASS', 'count': len(rows), 'changed_paths': failures,
                                           'persistence_status': 'FAIL' if persistence_failures else 'PASS', 'unpersisted_paths': persistence_failures}
            self.guards['recovery_manifest'] = {'status': 'PASS', 'sha256': RECOVERY_SHA}
            try:
                self.persisted(RECOVERY)
                self.guards['recovery_manifest']['persistence_status'] = 'PASS'
            except (OSError, ValueError, KeyError, TypeError):
                self.guards['recovery_manifest']['persistence_status'] = 'FAIL'
        except (OSError, ValueError, KeyError, TypeError):
            self.guards['protected43'] = {'status': 'FAIL', 'count': 0}
            self.guards['recovery_manifest'] = {'status': 'FAIL'}
        for name, path, sha in [('glyph', GLYPH, GLYPH_SHA), ('golden', GOLDEN, GOLDEN_SHA)]:
            try:
                value = self.file(path)
                self.guards[name] = {'status': 'PASS' if value['sha256'] == sha else 'FAIL', 'path': path,
                                     'sha256': value['sha256'], 'bytes': value['bytes']}
                try:
                    self.persisted(path)
                    self.guards[name]['persistence_status'] = 'PASS'
                except (OSError, ValueError, KeyError, TypeError):
                    self.guards[name]['persistence_status'] = 'FAIL'
            except (OSError, ValueError):
                self.guards[name] = {'status': 'FAIL', 'path': path}
        if any(x['status'] != 'PASS' for x in self.guards.values()):
            self.reason('SOURCE_PERSISTED', 'PROTECTED_BASELINE_CHANGED')
        if any(x.get('persistence_status') != 'PASS' for x in self.guards.values()):
            self.reason('SOURCE_PERSISTED', 'PROTECTED_BASELINE_NOT_PERSISTED')
        return rows

    def required(self):
        rows = self.manifest.get('required_files', [])
        if self.manifest.get('schema') != 1 or not isinstance(rows, list) or not rows:
            self.reason('HASH_MANIFEST_PASS', 'RUNTIME_INVENTORY_INVALID')
            rows = []
        for row in rows:
            path = row.get('path') if isinstance(row, dict) else None
            try:
                if row.get('kind') not in KINDS or path in self.rows:
                    raise ValueError('REQUIRED_RECORD_INVALID')
                self.rows[path] = row
                sha, size = row.get('sha256'), row.get('bytes')
                if not isinstance(sha, str) or not SHA.fullmatch(sha) or type(size) is not int or size < 0:
                    raise ValueError('REQUIRED_HASH_OR_SIZE_UNKNOWN')
                actual = self.persisted(path)
                if actual['sha256'] != sha or actual['bytes'] != size:
                    raise ValueError('REQUIRED_HASH_OR_SIZE_MISMATCH')
                self.checked[path] = actual
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.reason('HASH_MANIFEST_PASS', str(error) if isinstance(error, ValueError) else 'REQUIRED_FILE_UNAVAILABLE', path)
        for path in (self.manifest_path, self.import_path, *self.manifest.get('inventory_manifests', [])):
            try:
                self.persisted(path)
            except (OSError, ValueError, KeyError, TypeError):
                self.reason('HASH_MANIFEST_PASS', 'RUNTIME_MANIFEST_NOT_COMMITTED', path)
        complete = self.manifest.get('completeness', {})
        if complete.get('required_file_inventory_complete') is not True:
            self.reason('HASH_MANIFEST_PASS', 'RUNTIME_INVENTORY_CLOSURE_UNCONFIRMED')
        for condition, kind, flag in [('SOURCE_PERSISTED', 'source', 'source_contracts_confirmed'),
                                       ('ASSETS_PERSISTED', 'asset', 'runtime_inputs_complete')]:
            selected = [p for p, r in self.rows.items() if r['kind'] == kind]
            if not selected or any(p not in self.checked for p in selected):
                self.reason(condition, 'REQUIRED_FILES_NOT_PERSISTED')
            if complete.get(flag) is not True:
                self.reason(condition, 'RUNTIME_CONTRACT_UNCONFIRMED')
            self.finish(condition)
        self.finish('HASH_MANIFEST_PASS')

    def dependencies(self):
        condition = 'DEPENDENCY_MANIFEST_PASS'
        if self.manifest.get('completeness', {}).get('dependency_graph_complete') is not True:
            self.reason(condition, 'DEPENDENCY_GRAPH_UNCONFIRMED')
        rows = self.manifest.get('dependencies', [])
        if not isinstance(rows, list) or not rows:
            self.reason(condition, 'DEPENDENCIES_EMPTY')
            rows = []
        names = set()
        for row in rows:
            try:
                name, version, lock = row['name'], row['version'], row['lock_path']
                if name in names or not isinstance(version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?', version):
                    raise ValueError('EXACT_DEPENDENCY_PIN_REQUIRED')
                names.add(name)
                if lock not in self.checked or self.rows[lock]['kind'] != 'dependency_lock':
                    raise ValueError('DEPENDENCY_LOCK_NOT_PERSISTED')
                text = self.checked[lock]['path'].read_text()
                if row.get('ecosystem', 'npm') == 'python':
                    if not re.search(r'(?mi)^\s*' + re.escape(name) + r'\s*==\s*' + re.escape(version) + r'\s*(?:#.*)?$', text):
                        raise ValueError('PYTHON_EXACT_PIN_NOT_IN_LOCK')
                    if importlib.metadata.version(name) != version:
                        raise ValueError('INSTALLED_PYTHON_DEPENDENCY_VERSION_DIFFERS')
                else:
                    document = json.loads(text)
                    package = document.get('packages', {}).get('node_modules/' + name, {})
                    if package.get('version') != version or not package.get('integrity'):
                        raise ValueError('DEPENDENCY_PIN_OR_INTEGRITY_NOT_IN_LOCK')
                if row.get('artifact_path'):
                    artifact = self.checked.get(row['artifact_path'])
                    if artifact is None or artifact['sha256'] != row.get('sha256') or artifact['bytes'] != row.get('bytes'):
                        raise ValueError('VENDORED_DEPENDENCY_NOT_PERSISTED')
                if row.get('installed_package_path'):
                    installed = json.loads(self.file(row['installed_package_path'])['path'].read_text())
                    if installed.get('name') != name or installed.get('version') != version:
                        raise ValueError('INSTALLED_DEPENDENCY_VERSION_DIFFERS')
            except (OSError, ValueError, KeyError, TypeError, importlib.metadata.PackageNotFoundError):
                self.reason(condition, 'DEPENDENCY_RECORD_UNVERIFIED', row.get('name') if isinstance(row, dict) else None)
        routes = self.manifest.get('runtime_routes', [])
        seen = set()
        for row in routes:
            try:
                url, path = row['url'], row['file']
                if not isinstance(url, str) or not url.startswith('/') or url.startswith('//') or url in seen or path not in self.checked:
                    raise ValueError('RUNTIME_ROUTE_UNVERIFIED')
                seen.add(url)
            except (ValueError, KeyError, TypeError):
                self.reason(condition, 'RUNTIME_ROUTE_UNVERIFIED')
        if not routes:
            self.reason(condition, 'RUNTIME_ROUTES_EMPTY')
        for row in self.manifest.get('interpreters', []):
            try:
                if row['name'] == 'python':
                    actual = platform.python_version()
                elif row['name'] == 'node':
                    actual = subprocess.run(['node', '--version'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                            timeout=10, check=True).stdout.decode().strip().removeprefix('v')
                elif row['name'] == 'chromium':
                    text = subprocess.run(['chromium', '--version'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          timeout=10, check=True).stdout.decode().split()
                    actual = text[1]
                elif row['name'] == 'ffmpeg':
                    text = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          timeout=10, check=True).stdout.decode().split()
                    actual = text[2].split('-', 1)[0]
                else:
                    raise ValueError('INTERPRETER_KIND_UNSUPPORTED')
                if actual != row['version']:
                    raise ValueError('INTERPRETER_VERSION_DIFFERS')
            except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
                self.reason(condition, 'INTERPRETER_VERSION_UNVERIFIED', row.get('name'))
        self.finish(condition)

    def ast(self):
        condition = 'IMPORT_MANIFEST_PASS'
        declared, modules = {}, self.imports_manifest.get('modules', [])
        try:
            parser = self.imports_manifest['parser']
            value = self.file(parser['path'])
            if parser['path'] != AST_PARSER or value['sha256'] != AST_PARSER_SHA or value['sha256'] != parser['sha256'] or value['bytes'] != parser['bytes']:
                raise ValueError('AST_PARSER_HASH_MISMATCH')
            installed = json.loads(self.file(parser['package_json'])['path'].read_text())
            if installed.get('name') != parser['package'] or installed.get('version') != parser['version']:
                raise ValueError('AST_PARSER_VERSION_MISMATCH')
            lock = json.loads(self.file(parser['lock_path'])['path'].read_text())
            if lock['packages']['node_modules/' + parser['package']]['version'] != parser['version']:
                raise ValueError('AST_PARSER_LOCK_MISMATCH')
            for extra in parser.get('support_files', []):
                value = self.file(extra['path'])
                if value['sha256'] != extra['sha256'] or value['bytes'] != extra['bytes']:
                    raise ValueError('AST_PARSER_SUPPORT_HASH_MISMATCH')
            files = []
            if self.imports_manifest.get('schema') != 1 or not isinstance(modules, list) or not modules or len(modules) != len(set(modules)):
                raise ValueError('AST_MODULE_INVENTORY_INVALID')
            for path in modules:
                if path not in self.rows or self.rows[path]['kind'] not in ('source', 'dependency'):
                    raise ValueError('AST_MODULE_NOT_IN_REQUIRED_INVENTORY')
                value = self.file(path)
                files.append({'path': path, 'absolute': str(value['path'])})
            self.validated_parser = self.file(parser['path'])['path']
            result = subprocess.run(['node', '-e', AST_PROGRAM], input=json.dumps({'parser': str(self.file(parser['path'])['path']), 'files': files}).encode(),
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120, check=True)
            records = {x['path']: x for x in json.loads(result.stdout)}
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            self.reason(condition, 'BABEL_AST_INSPECTION_FAILED')
            self.finish(condition)
            return
        for row in self.imports_manifest.get('imports', []):
            key = row.get('importer'), row.get('specifier')
            if key in declared or row.get('resolved_path') not in records:
                self.reason(condition, 'DECLARED_IMPORT_INVALID', key[0])
            else:
                declared[key] = row['resolved_path']
        actual = set()
        ambiguous = object()

        def binding(path, name, seen=None):
            # ECMAScript-style resolution: explicit exports win; export-star
            # ambiguity is a failure only when that binding is requested.
            seen = set() if seen is None else seen
            if (path, name) in seen or path not in records:
                return None
            seen = seen | {(path, name)}
            record = records[path]
            if name in record['localbindings']:
                return (path, record['localbindings'][name])
            for row in record['reexports']:
                if row['names'] is None:
                    continue
                target = declared.get((path, row['specifier']))
                for pair in row['names']:
                    if pair['exported'] == name:
                        return (target, '*namespace*') if pair['imported'] == '*' and target in records else binding(target, pair['imported'], seen)
            if name == 'default':
                return None
            result = None
            for row in record['reexports']:
                if row['names'] is not None:
                    continue
                value = binding(declared.get((path, row['specifier'])), name, seen)
                if value is ambiguous or result is not None and value is not None and result != value:
                    return ambiguous
                if value is not None:
                    result = value
            return result

        for path, record in records.items():
            for row in record['reexports']:
                for pair in row['names'] or []:
                    value = binding(path, pair['exported'])
                    if value is None or value is ambiguous:
                        self.reason(condition, 'REEXPORTED_BINDING_MISSING_OR_AMBIGUOUS', path)
        routes = {x['url']: x['file'] for x in self.manifest.get('runtime_routes', []) if isinstance(x, dict) and 'url' in x and 'file' in x}
        for path, record in records.items():
            for issue in record['issues']:
                self.reason(condition, issue['code'], path)
            for row in record['imports']:
                specifier = row['specifier']; key = path, specifier; actual.add(key)
                target = declared.get(key)
                if target is None:
                    self.reason(condition, 'ACTUAL_IMPORT_NOT_DECLARED', path)
                    continue
                if specifier.startswith('.'):
                    expected = posixpath.normpath(posixpath.join(posixpath.dirname(path), specifier))
                elif specifier.startswith('/') and not specifier.startswith('//'):
                    expected = routes.get(specifier)
                else:
                    expected = next((x.get('artifact_path') for x in self.manifest.get('dependencies', []) if x.get('name') == specifier), None)
                if expected != target:
                    self.reason(condition, 'IMPORT_TARGET_DIFFERS_FROM_ROUTE_OR_PATH', path)
                required = set(row['names']) | ({'default'} if row['default'] else set())
                if any(binding(target, name) is None or binding(target, name) is ambiguous for name in required):
                    self.reason(condition, 'IMPORTED_BINDING_NOT_EXPORTED', path)
                if path not in self.checked or target not in self.checked:
                    self.reason(condition, 'IMPORT_MODULE_NOT_PERSISTED', path)
        if actual != set(declared):
            self.reason(condition, 'DECLARED_AND_ACTUAL_IMPORT_SETS_DIFFER')
        reached, pending = set(), list(self.imports_manifest.get('entrypoints', []))
        while pending:
            path = pending.pop()
            if path in reached:
                continue
            reached.add(path)
            pending += [declared[(path, x['specifier'])] for x in records.get(path, {}).get('imports', []) if (path, x['specifier']) in declared]
        if not reached or reached != set(modules):
            self.reason(condition, 'DECLARED_MODULE_CLOSURE_DIFFERS_FROM_ENTRYPOINT_GRAPH')
        if self.manifest.get('completeness', {}).get('import_graph_complete') is not True:
            self.reason(condition, 'IMPORT_GRAPH_REVIEW_UNCONFIRMED')
        self.graph = {'parser': 'BABEL_AST', 'modules': len(records), 'actual_imports': len(actual),
                      'declared_imports': len(declared), 'reachable_modules': len(reached),
                      'parse_issue_count': sum(len(x['issues']) for x in records.values())}
        self.finish(condition)

    def temporary(self):
        condition = 'NO_REQUIRED_TEMP_FILES'
        if any(self.conditions[x]['status'] != 'PASS' for x in CONDITIONS[:5]):
            self.conditions[condition]['status'] = 'NOT_RUN'
            self.reason(condition, 'REQUIRED_RUNTIME_CLOSURE_INCOMPLETE')
            return
        # safe_file and HEAD object checks prohibit external, symlink and temp-only inputs.
        # A repository path named past-paths/tmp is a preserved historical name.
        self.conditions[condition]['status'] = 'PASS'

    def build_imports(self):
        """Inspect repository build procedures; never import those procedures.

        Python standard-library modules and pinned distribution import names are
        separate from repository modules. Shell procedures are hash-protected
        reviewed commands, not claimed as a Python/ESM dependency graph.
        """
        condition = 'IMPORT_MANIFEST_PASS'
        count = 0
        mappings = {'numpy': 'numpy', 'PIL': 'Pillow', 'osgeo': 'GDAL'}
        deps = {x.get('name') for x in self.manifest.get('dependencies', [])}
        node_paths = []
        for path, row in self.rows.items():
            if row['kind'] != 'procedure':
                continue
            if path.endswith(('.mjs', '.js')):
                node_paths.append(path)
            elif path.endswith('.py'):
                try:
                    tree = ast.parse(self.file(path)['path'].read_text(), filename=path)
                    for node in ast.walk(tree):
                        modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
                        for module in modules:
                            count += 1
                            root = (module or '').split('.')[0]
                            if root in sys.stdlib_module_names or root in sys.builtin_module_names:
                                continue
                            if root in mappings and mappings[root] in deps:
                                continue
                            relative = posixpath.join(posixpath.dirname(path), (module or '').replace('.', '/') + '.py')
                            if isinstance(node, ast.ImportFrom) and node.level:
                                self.reason(condition, 'RELATIVE_PYTHON_BUILD_IMPORT_REQUIRES_REVIEW', path)
                            elif relative not in self.rows or relative not in self.checked:
                                self.reason(condition, 'PYTHON_BUILD_IMPORT_NOT_PERSISTED_OR_PINNED', path)
                        if isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id == '__import__' or isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
                            self.reason(condition, 'DYNAMIC_PYTHON_BUILD_IMPORT_REQUIRES_REVIEW', path)
                except (OSError, ValueError, SyntaxError):
                    self.reason(condition, 'PYTHON_BUILD_AST_INSPECTION_FAILED', path)
        if node_paths:
            try:
                if self.validated_parser is None:
                    raise ValueError('PINNED_AST_PARSER_NOT_VERIFIED')
                parser = self.validated_parser
                files = [{'path': p, 'absolute': str(self.file(p)['path'])} for p in node_paths]
                request = {'parser': str(parser), 'files': files}
                result = subprocess.run(['node', '-e', AST_PROGRAM], input=json.dumps(request).encode(),
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120, check=True)
                records = json.loads(result.stdout)
                names = sorted({entry['specifier'] for row in records for entry in row['imports'] + row['requires']
                                if isinstance(entry['specifier'], str) and entry['specifier'].startswith('node:')})
                builtin_program = "const fs=require('node:fs');const allowed=new Set(require('node:module').builtinModules.map(x=>x.replace(/^node:/,'')));const out={};for(const name of JSON.parse(fs.readFileSync(0,'utf8'))){out[name]=allowed.has(name.slice(5))?Object.keys(require(name)):null;}process.stdout.write(JSON.stringify(out));"
                result = subprocess.run(['node', '-e', builtin_program], input=json.dumps(names).encode(),
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=True)
                builtins = json.loads(result.stdout)
                for row in records:
                    for issue in row['issues']:
                        if issue['code'] != 'COMMONJS_RUNTIME_CLOSURE_REQUIRES_REVIEW':
                            self.reason(condition, issue['code'], row['path'])
                    for entry in row['imports'] + row['requires']:
                        count += 1
                        name = entry['specifier']
                        if isinstance(name, str) and name.startswith('node:'):
                            available = builtins.get(name)
                            if available is None or not set(entry.get('names', [])) <= set(available):
                                self.reason(condition, 'NODE_BUILTIN_OR_BINDING_UNAVAILABLE', row['path'])
                            continue
                        package = name.removesuffix('/package.json') if isinstance(name, str) else None
                        if package not in deps:
                            self.reason(condition, 'NODE_BUILD_IMPORT_NOT_PINNED', row['path'])
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                self.reason(condition, 'NODE_BUILD_AST_INSPECTION_FAILED')
        self.graph['build_import_occurrences'] = count
        self.graph['build_source_execution'] = False
        self.finish(condition)

    def reproduction(self, receipt, checkout):
        condition = 'CLEAN_ENV_REPRODUCIBLE'
        self.conditions[condition]['status'] = 'NOT_RUN'
        if not receipt:
            self.reason(condition, 'FRESH_REPRODUCTION_RECEIPT_ABSENT')
            return
        if any(self.conditions[x]['status'] != 'PASS' for x in CONDITIONS[:-1]):
            self.reason(condition, 'REPRODUCTION_PREREQUISITES_INCOMPLETE')
            return
        try:
            receipt = Path(receipt).absolute()
            record = json.loads(safe_file(receipt.parent, receipt.name).read_text())
            fresh = self.manifest['fresh_reproduction']
            if record.get('schema') != 1 or record.get('kind') != 'fresh_clean_environment_reproduction' or record.get('source_commit') != self.head:
                raise ValueError('FRESH_RECEIPT_SCHEMA_OR_COMMIT_DIFFERS')
            bindings = {path: self.file(path)['sha256'] for path in
                        (self.manifest_path, self.import_path, *self.manifest.get('inventory_manifests', []))}
            if record.get('manifest_sha256') != bindings:
                raise ValueError('FRESH_RECEIPT_MANIFEST_BINDINGS_DIFFER')
            expected_inputs = {p: {'sha256': self.checked[p]['sha256'], 'bytes': self.checked[p]['bytes']} for p in self.checked}
            if record.get('required_inputs') != expected_inputs:
                raise ValueError('FRESH_RECEIPT_FULL_INPUT_BINDINGS_DIFFER')
            start = dt.datetime.fromisoformat(record['started_at_utc'].replace('Z', '+00:00'))
            end = dt.datetime.fromisoformat(record['completed_at_utc'].replace('Z', '+00:00'))
            if start.tzinfo is None or end.tzinfo is None or not start < end <= dt.datetime.now(dt.timezone.utc):
                raise ValueError('FRESH_RECEIPT_TIME_INVALID')
            clean = record['clean_environment']; checkout = Path(checkout).absolute().resolve()
            if checkout == self.repo.resolve() or checkout in self.repo.resolve().parents or self.repo.resolve() in checkout.parents:
                raise ValueError('SEPARATE_CLEAN_CHECKOUT_REQUIRED')
            if Path(clean['checkout_path']).resolve() != checkout or clean.get('baseline_clean') is not True or clean.get('source_commit') != self.head:
                raise ValueError('CLEAN_BASELINE_EVIDENCE_REQUIRED')
            if git(checkout, 'rev-parse', 'HEAD').decode().strip() != self.head or git(checkout, 'status', '--porcelain', '--untracked-files=all').strip():
                raise ValueError('CLEAN_CHECKOUT_HEAD_OR_STATUS_DIFFERS')
            for path, actual in self.checked.items():
                if hash_file(safe_file(checkout, path)) != {'sha256': actual['sha256'], 'bytes': actual['bytes']}:
                    raise ValueError('CLEAN_CHECKOUT_INPUT_DIFFERS')
            for path, sha in bindings.items():
                if hash_file(safe_file(checkout, path))['sha256'] != sha:
                    raise ValueError('CLEAN_CHECKOUT_MANIFEST_DIFFERS')
            command = record['command']
            validation = record['validation']
            if validation.get('status') != 'PASS' or any(type(validation.get(key)) is not int or validation[key] != 0
                                                       for key in ('required_failures', 'required_errors', 'unverified_required_inputs', 'gl_error')):
                raise ValueError('FRESH_REQUIRED_VALIDATION_DID_NOT_PASS')
            if not isinstance(fresh.get('approved_command'), list) or not fresh['approved_command'] or not all(isinstance(x, str) and x for x in fresh['approved_command']):
                raise ValueError('APPROVED_COMMAND_UNKNOWN')
            approved = [x.replace('{checkout}', str(checkout)).replace('{evidence}', str(receipt.parent)) for x in fresh['approved_command']]
            if command.get('argv') != approved or type(command.get('exit_code')) is not int or command['exit_code'] != 0 or Path(command['cwd']).resolve() != checkout:
                raise ValueError('FRESH_COMMAND_DIFFERS_FROM_APPROVED_PROCEDURE')
            if fresh['procedure_path'] not in self.checked or self.rows[fresh['procedure_path']]['kind'] != 'procedure':
                raise ValueError('REPRODUCTION_PROCEDURE_NOT_PERSISTED')
            procedure = fresh['procedure_path']
            if procedure not in approved and str(checkout / procedure) not in approved:
                raise ValueError('APPROVED_COMMAND_HAS_NO_PERSISTED_ENTRYPOINT')
            log = safe_file(receipt.parent, command['log_path'])
            if not log.stat().st_size or hash_file(log)['sha256'] != command.get('log_sha256'):
                raise ValueError('FRESH_COMMAND_LOG_INVALID')
            output = safe_file(receipt.parent, record['output']['path'])
            if output.resolve() in {x['path'].resolve() for x in self.checked.values()} | {self.file(GOLDEN)['path'].resolve()}:
                raise ValueError('PRESERVED_INPUT_CANNOT_BE_FRESH_OUTPUT')
            output_sha = hash_file(output)['sha256']
            if record['output'].get('sha256') != output_sha:
                raise ValueError('FRESH_OUTPUT_RECEIPT_HASH_DIFFERS')
            acceptance = fresh['acceptance']
            if acceptance.get('mode') != 'PIXEL_EXACT' or acceptance.get('expected_png_sha256') != GOLDEN_SHA or acceptance.get('expected_rgba_sha256') != GOLDEN_RGBA_SHA:
                raise ValueError('APPROVED_ACCEPTANCE_CRITERION_DIFFERS')
            comparator = acceptance['comparator_path']
            if comparator not in self.checked or self.rows[comparator]['kind'] != 'procedure':
                raise ValueError('PIXEL_COMPARATOR_NOT_PERSISTED')
            # This is PNG decoding only, not engine execution or rendering. The
            # actual supplied output and immutable Golden are both decoded here;
            # a receipt's claimed pixel result never replaces these bytes.
            from PIL import Image
            rgba_sha = []
            for image_path in (output, self.file(GOLDEN)['path']):
                with Image.open(image_path) as image:
                    if image.format != 'PNG' or image.size != (1080, 1920):
                        raise ValueError('REPRODUCTION_PNG_DIMENSIONS_OR_FORMAT_DIFFER')
                    rgba_sha.append(hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest())
            if rgba_sha != [GOLDEN_RGBA_SHA, GOLDEN_RGBA_SHA]:
                raise ValueError('FRESH_OUTPUT_PIXELS_DO_NOT_MATCH_APPROVED_GOLDEN')
            self.guards['fresh_output'] = {'status': 'PASS', 'equivalence': 'BIT_EXACT' if output_sha == GOLDEN_SHA else 'PIXEL_EXACT',
                                            'png_sha256': output_sha, 'rgba_sha256': GOLDEN_RGBA_SHA}
            if not start.timestamp() <= output.stat().st_mtime <= end.timestamp():
                raise ValueError('FRESH_OUTPUT_TIME_OUTSIDE_SESSION')
            self.conditions[condition]['status'] = 'PASS'
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            self.conditions[condition]['status'] = 'FAIL'
            self.reason(condition, str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else 'FRESH_RECEIPT_UNVERIFIED')

    def run(self, receipt=None, checkout=None):
        self.protected(); self.required(); self.dependencies(); self.ast(); self.build_imports(); self.temporary(); self.reproduction(receipt, checkout)
        complete = all(x['status'] == 'PASS' for x in self.conditions.values())
        stage = self.manifest.get('stage_validation', {'status': 'USER_VISUAL_REVIEW_REQUIRED'})
        functional_approval = stage.get('status') == 'USER_APPROVED' and stage.get('functional_approval_confirmed') is True
        return {'schema': 1, 'scope': 'V4_ACTUAL_RUNTIME_RECOVERY', 'source_scope': 'REGIONAL_STATIC_ONLY', 'source_commit': self.head,
                'conditions': self.conditions, 'guards': self.guards, 'ast_import_graph': self.graph,
                'required_files': len(self.rows), 'persisted_verified_files': len(self.checked),
                'permanent_state': 'PERMANENT_STATE_READY' if complete else 'PERMANENT_STATE_INCOMPLETE',
                'acceptance_scope': 'REGIONAL_FINAL_HOLD_ONLY', 'stage_validation': stage,
                'overall': 'GATE_COMPLETE' if complete and functional_approval else 'GATE_INCOMPLETE',
                'next_development_stage_allowed': False, 'render_executed': False,
                'engine_executed': False, 'git_mutations': 0,
                'receipt_limit': 'Actual evidence bytes are checked; this is not cryptographic execution attestation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--manifest', default=BASE + '/runtime/DEPENDENCY_MANIFEST.json')
    parser.add_argument('--imports', default=BASE + '/runtime/IMPORT_MANIFEST.json')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--clean-checkout', type=Path)
    parser.add_argument('--lfs-checkout', type=Path, help='Explicit separate clean checkout containing verified hydrated LFS bodies')
    parser.add_argument('--lfs-receipt', type=Path, help='Explicit private lfs_clean_clone_verification receipt bound to current HEAD and body hashes')
    args = parser.parse_args()
    try:
        report = Gate(args.repo.absolute(), args.manifest, args.imports, args.lfs_checkout, args.lfs_receipt).run(args.receipt, args.clean_checkout)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        report = {'schema': 1, 'scope': 'V4_ACTUAL_RUNTIME_RECOVERY',
                  'conditions': {x: {'status': 'FAIL', 'reasons': [{'code': 'GATE_INPUT_INVALID'}]} for x in CONDITIONS},
                  'overall': 'GATE_INCOMPLETE', 'next_development_stage_allowed': False,
                  'render_executed': False, 'engine_executed': False, 'git_mutations': 0}
    print(json.dumps(report, indent=2))
    return 0 if report['overall'] == 'GATE_COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
