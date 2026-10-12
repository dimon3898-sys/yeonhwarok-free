#!/usr/bin/env python3
"""Read-only, fail-closed validation of the World Engine permanent Gate.

Does not build, install, render, execute source/archive content, or change Git.
JSON declarations never replace actual committed files, hashes and evidence.
"""
import argparse
import datetime as dt
import hashlib
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

CONDITIONS = (
    'SOURCE_PERSISTED', 'ASSETS_PERSISTED', 'HASH_MANIFEST_PASS',
    'DEPENDENCY_MANIFEST_PASS', 'IMPORT_MANIFEST_PASS',
    'NO_REQUIRED_TEMP_FILES', 'CLEAN_ENV_REPRODUCIBLE',
)
KINDS = {'source', 'asset', 'input', 'procedure', 'dependency_lock'}
SHA = re.compile(r'[0-9a-f]{64}')
BLOCKED = {'.git', '.aws', '.ssh', '.gnupg', '.codex', '.docker', '.kube', '.env',
           '.npmrc', '.netrc', '.pypirc', '.git-credentials', 'credentials', 'credentials.json', 'auth.json'}
EXACT_VERSION = re.compile(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.-]*)?')


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=True)
    return result.stdout


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_file(root, value):
    root = Path(root).absolute()
    if any(parent.is_symlink() or forbidden_name(parent.name) for parent in [root, *root.parents]):
        raise ValueError('UNSAFE_ROOT_PATH')
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('UNSAFE_PATH')
    relative = PurePosixPath(value)
    if relative.is_absolute() or '..' in relative.parts or any(forbidden_name(part) for part in relative.parts):
        raise ValueError('UNSAFE_PATH')
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('SYMLINK_FORBIDDEN')
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('REGULAR_FILE_REQUIRED')
    return path


def forbidden_name(name):
    return name in BLOCKED or name.startswith('.env.')


def records(repo, command):
    output = {}
    for row in git(repo, *command).split(b'\x00'):
        if not row:
            continue
        info, path = row.split(b'\t', 1)
        mode, middle, last = info.decode().split()
        if command[0] == 'ls-files':
            if last != '0':
                raise ValueError('UNMERGED_INDEX')
            oid = middle
        else:
            if middle != 'blob':
                continue
            oid = last
        output[path.decode('utf-8')] = (mode, oid)
    return output


@lru_cache(maxsize=256)
def ast_source(source, parser_root=None):
    """Parse source with installed pinned Playwright Babel; never execute source.

    The previous approximate tokenizer misread valid regular expressions in the
    rebuilt glyph module. Babel owns literal/comment and module syntax parsing.
    """
    from v4_recovery_gate import AST_PROGRAM
    repo = Path(parser_root) if parser_root is not None else Path(__file__).absolute().parent.parent
    parser = repo / 'cinematic-world-map/node_modules/playwright/lib/transform/babelBundle.js'
    if not parser.is_file():
        raise ValueError('BABEL_AST_PARSER_UNAVAILABLE')
    package = json.loads((repo / 'cinematic-world-map/node_modules/playwright/package.json').read_text())
    lock = json.loads((repo / 'cinematic-world-map/package-lock.json').read_text())
    if package.get('version') != '1.62.1' or lock.get('packages', {}).get('node_modules/playwright', {}).get('version') != '1.62.1':
        raise ValueError('BABEL_AST_PARSER_VERSION_DIFFERS')
    if digest(parser) != '01511e45db7646e2a12890de8d7866caa0754c8799db6407a6345236f4bed0c4':
        raise ValueError('BABEL_AST_PARSER_HASH_DIFFERS')
    request = {'parser': str(parser), 'files': [{'path': 'gate-source.mjs',
               'absolute': str(repo / 'gate-source.mjs'), 'source': source}]}
    try:
        process = subprocess.run(['node', '-e', AST_PROGRAM], input=json.dumps(request).encode(),
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 check=True, timeout=120)
        record = json.loads(process.stdout)[0]
        if record['issues']:
            raise ValueError(record['issues'][0]['code'])
        return record
    except (OSError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        raise ValueError('BABEL_AST_PARSE_FAILED') from None


def module_imports(source, parser_root=None):
    return [(row['specifier'], row['names'], row['default'])
            for row in ast_source(source, parser_root)['imports']]


def exports(source, parser_root=None):
    record = ast_source(source, parser_root)
    names = set(record['exports'])
    if record['reexports']:
        raise ValueError('REEXPORT_REQUIRES_TRANSITIVE_BINDING_REVIEW')
    return names, record['default']


class Gate:
    def __init__(self, repo, manifest):
        self.repo, self.manifest_path = repo, manifest
        self.head = git(repo, 'rev-parse', 'HEAD').decode().strip()
        self.algorithm = git(repo, 'rev-parse', '--show-object-format').decode().strip()
        self.index = records(repo, ['ls-files', '--stage', '-z'])
        self.tree = records(repo, ['ls-tree', '-r', '-z', 'HEAD'])
        self.data = json.loads(safe_file(repo, manifest).read_text())
        self.result = {name: {'status': 'FAIL', 'reasons': []} for name in CONDITIONS}
        self.files, self.checked = {}, {}

    def reason(self, condition, code, path=None):
        row = {'code': code}
        if path is not None:
            row['path'] = path
        self.result[condition]['reasons'].append(row)

    def flag(self, name):
        return self.data.get('completeness', {}).get(name) is True

    def committed_file(self, relative):
        path = safe_file(self.repo, relative)
        indexed, committed = self.index.get(relative), self.tree.get(relative)
        if indexed is None or committed is None or indexed != committed or indexed[0] not in ('100644', '100755'):
            raise ValueError('FILE_NOT_COMMITTED_REGULAR')
        before = path.stat()
        sha, blob = hashlib.sha256(), hashlib.new(self.algorithm)
        blob.update(f'blob {before.st_size}\x00'.encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(chunk)
                blob.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('FILE_CHANGED_DURING_VALIDATION')
        if blob.hexdigest() != committed[1]:
            raise ValueError('WORKTREE_DIFFERS_FROM_HEAD')
        return {'sha256': sha.hexdigest(), 'bytes': before.st_size, 'path': path}

    def required_files(self):
        rows = self.data.get('required_files')
        if self.data.get('schema') != 1 or not isinstance(rows, list) or not rows:
            self.reason('HASH_MANIFEST_PASS', 'REQUIRED_INVENTORY_INVALID')
            return
        for row in rows:
            path = row.get('path') if isinstance(row, dict) else None
            try:
                if row.get('kind') not in KINDS or path in self.files or not isinstance(path, str):
                    raise ValueError('REQUIRED_RECORD_INVALID')
                self.files[path] = row
                sha, size = row.get('expected_sha256'), row.get('expected_size')
                if not isinstance(sha, str) or not SHA.fullmatch(sha) or type(size) is not int or size < 0:
                    raise ValueError('EXPECTED_HASH_OR_SIZE_UNKNOWN')
                actual = self.committed_file(path)
                if actual['sha256'] != sha or actual['bytes'] != size:
                    raise ValueError('ACTUAL_HASH_OR_SIZE_MISMATCH')
                self.checked[path] = actual
            except (OSError, ValueError, TypeError, AttributeError) as error:
                self.reason('HASH_MANIFEST_PASS', str(error) if isinstance(error, ValueError) else 'REQUIRED_FILE_UNAVAILABLE', path)
        try:
            self.manifest_actual = self.committed_file(self.manifest_path)
        except (OSError, ValueError):
            self.reason('HASH_MANIFEST_PASS', 'GATE_MANIFEST_NOT_COMMITTED')
            self.manifest_actual = None
        for kind in sorted(KINDS - {row['kind'] for row in self.files.values()}):
            self.reason('HASH_MANIFEST_PASS', 'REQUIRED_KIND_EMPTY', kind)
        if not self.flag('required_file_inventory_complete'):
            self.reason('HASH_MANIFEST_PASS', 'REQUIRED_INVENTORY_CLOSURE_UNCONFIRMED')
        self.result['HASH_MANIFEST_PASS']['status'] = 'FAIL' if self.result['HASH_MANIFEST_PASS']['reasons'] else 'PASS'
        for condition, kind, flag in [('SOURCE_PERSISTED', 'source', 'source_contracts_confirmed'),
                                      ('ASSETS_PERSISTED', 'asset', 'runtime_inputs_complete')]:
            selected = [path for path, row in self.files.items() if row['kind'] == kind]
            if not selected:
                self.reason(condition, 'REQUIRED_KIND_EMPTY', kind)
            for path in selected:
                if path not in self.checked:
                    self.reason(condition, 'REQUIRED_FILE_NOT_VERIFIED', path)
                provenance = str(self.files[path].get('status', '')).upper()
                if any(word in provenance for word in ('UNKNOWN', 'UNVERIFIED', 'PENDING', 'MISSING')):
                    self.reason(condition, 'REQUIRED_PROVENANCE_UNCONFIRMED', path)
            if not self.flag(flag):
                self.reason(condition, 'REQUIRED_CONTRACT_UNCONFIRMED')
            self.result[condition]['status'] = 'FAIL' if self.result[condition]['reasons'] else 'PASS'

    def dependencies(self):
        condition = 'DEPENDENCY_MANIFEST_PASS'
        if not self.flag('dependency_graph_complete'):
            self.reason(condition, 'DEPENDENCY_CLOSURE_UNCONFIRMED')
        rows = self.data.get('dependencies')
        if not isinstance(rows, list) or not rows:
            self.reason(condition, 'PINNED_DEPENDENCIES_EMPTY')
            rows = []
        seen = set()
        for row in rows:
            try:
                name, version, lock = row['name'], row['version'], row['lock_path']
                if not isinstance(name, str) or not name or name in seen or not isinstance(version, str) or not EXACT_VERSION.fullmatch(version) or row.get('verified') is not True:
                    raise ValueError('DEPENDENCY_UNVERIFIED')
                seen.add(name)
                if lock not in self.checked or self.files[lock]['kind'] != 'dependency_lock':
                    raise ValueError('DEPENDENCY_LOCK_NOT_VERIFIED')
                text = self.checked[lock]['path'].read_text()
                try:
                    document = json.loads(text)
                    package = document.get('packages', {}).get('node_modules/' + name, {})
                    item = document.get('dependencies', {}).get(name, {})
                    versions = {package.get('version'), item.get('version') if isinstance(item, dict) else item}
                    if version not in versions:
                        raise ValueError('PINNED_VERSION_NOT_IN_LOCK')
                except json.JSONDecodeError:
                    if not re.search(r'(?m)^\s*' + re.escape(name) + r'\s*==\s*' + re.escape(version) + r'\s*(?:#.*)?$', text):
                        raise ValueError('PINNED_VERSION_NOT_IN_LOCK')
                if row.get('artifact_path') and row['artifact_path'] not in self.checked:
                    raise ValueError('DEPENDENCY_ARTIFACT_NOT_VERIFIED')
            except (KeyError, TypeError, AttributeError, OSError, ValueError) as error:
                self.reason(condition, str(error) if isinstance(error, ValueError) else 'DEPENDENCY_RECORD_INVALID')
        routes = self.data.get('runtime_routes')
        if not isinstance(routes, list) or not routes:
            self.reason(condition, 'RUNTIME_ROUTE_INVENTORY_EMPTY')
            routes = []
        urls = set()
        for row in routes:
            try:
                url, target = row['url'], row['file']
                if not isinstance(url, str) or not url.startswith('/') or url.startswith('//') or url in urls or row.get('verified') is not True or target not in self.checked:
                    raise ValueError('RUNTIME_ROUTE_UNVERIFIED')
                urls.add(url)
            except (KeyError, TypeError, ValueError) as error:
                self.reason(condition, str(error) if isinstance(error, ValueError) else 'RUNTIME_ROUTE_INVALID')
        self.result[condition]['status'] = 'FAIL' if self.result[condition]['reasons'] else 'PASS'

    def imports(self):
        condition = 'IMPORT_MANIFEST_PASS'
        if not self.flag('import_graph_complete'):
            self.reason(condition, 'IMPORT_CLOSURE_UNCONFIRMED')
        declared = {}
        for row in self.data.get('imports', []):
            try:
                key = row['importer'], row['specifier']
                if key in declared or row.get('verified') is not True or row['resolved_path'] not in self.checked or key[0] not in self.checked:
                    raise ValueError('DECLARED_IMPORT_UNVERIFIED')
                if self.files[row['resolved_path']]['kind'] != 'source' or self.files[key[0]]['kind'] != 'source':
                    raise ValueError('IMPORT_MODULE_NOT_IN_SOURCE_INVENTORY')
                declared[key] = row['resolved_path']
            except (KeyError, TypeError, ValueError) as error:
                self.reason(condition, str(error) if isinstance(error, ValueError) else 'IMPORT_RECORD_INVALID')
        actual = set()
        for path, row in self.files.items():
            if row['kind'] != 'source':
                continue
            if path not in self.checked:
                self.reason(condition, 'REQUIRED_SOURCE_NOT_VERIFIED', path)
                continue
            try:
                if Path(path).suffix not in ('.mjs', '.js'):
                    raise ValueError('SOURCE_IMPORT_SYNTAX_UNSUPPORTED')
                for specifier, names, default in module_imports(self.checked[path]['path'].read_text(), self.repo):
                    key = path, specifier
                    actual.add(key)
                    if key not in declared:
                        raise ValueError('ACTUAL_IMPORT_NOT_IN_MANIFEST')
                    target = declared[key]
                    if specifier.startswith('.'):
                        expected = Path(path).parent.joinpath(specifier)
                        if expected.resolve() != Path(target).resolve():
                            raise ValueError('RELATIVE_IMPORT_TARGET_DIFFERS')
                    elif specifier.startswith('/'):
                        routes = {route.get('url'): route.get('file') for route in self.data.get('runtime_routes', []) if route.get('verified') is True}
                        if routes.get(specifier) != target:
                            raise ValueError('ABSOLUTE_IMPORT_ROUTE_UNVERIFIED')
                    elif not any(dependency.get('verified') is True and dependency.get('name') == specifier and
                                 dependency.get('artifact_path') == target for dependency in self.data.get('dependencies', [])):
                        raise ValueError('BARE_IMPORT_DEPENDENCY_TARGET_UNVERIFIED')
                    provided, has_default = exports(self.checked[target]['path'].read_text(), self.repo)
                    if not set(names) <= provided or default and not has_default:
                        raise ValueError('IMPORTED_BINDING_NOT_EXPORTED')
            except (OSError, UnicodeError, ValueError, TypeError) as error:
                self.reason(condition, str(error) if isinstance(error, ValueError) else 'SOURCE_IMPORT_INSPECTION_FAILED', path)
        if actual != set(declared):
            self.reason(condition, 'DECLARED_AND_ACTUAL_IMPORT_INVENTORY_DIFFER')
        self.result[condition]['status'] = 'FAIL' if self.result[condition]['reasons'] else 'PASS'

    def temporary_inputs(self):
        condition = 'NO_REQUIRED_TEMP_FILES'
        required = ('SOURCE_PERSISTED', 'ASSETS_PERSISTED', 'HASH_MANIFEST_PASS', 'DEPENDENCY_MANIFEST_PASS', 'IMPORT_MANIFEST_PASS')
        if not self.flag('required_file_inventory_complete') or any(self.result[key]['status'] != 'PASS' for key in required):
            self.result[condition]['status'] = 'NOT_RUN'
            self.reason(condition, 'REQUIRED_RUNTIME_CLOSURE_UNVERIFIED')
        else:
            self.result[condition]['status'] = 'PASS'

    def reproduction(self, receipt_path, checkout_path):
        condition = 'CLEAN_ENV_REPRODUCIBLE'
        self.result[condition]['status'] = 'NOT_RUN'
        fresh = self.data.get('fresh_reproduction', {})
        receipt = receipt_path or fresh.get('receipt_path')
        if not receipt:
            self.reason(condition, 'FRESH_RECEIPT_ABSENT')
            return
        if any(self.result[key]['status'] != 'PASS' for key in CONDITIONS[:-1]):
            self.reason(condition, 'REPRODUCTION_PREREQUISITES_INCOMPLETE')
            return
        try:
            path = Path(receipt)
            if path.is_absolute() and receipt_path is None:
                raise ValueError('EXTERNAL_RECEIPT_REQUIRES_EXPLICIT_CLI_PATH')
            if receipt_path is None:
                receipt_file = safe_file(self.repo, str(path))
            else:
                if not path.is_absolute():
                    path = self.repo / path
                receipt_file = safe_file(path.parent, path.name)
            record = json.loads(receipt_file.read_text())
            if record.get('schema') != 1 or record.get('kind') != 'fresh_clean_environment_reproduction':
                raise ValueError('FRESH_RECEIPT_SCHEMA_INVALID')
            if record.get('source_commit') != self.head or fresh.get('source_commit', self.head) != self.head:
                raise ValueError('FRESH_RECEIPT_SOURCE_COMMIT_STALE')
            if record.get('gate_manifest_sha256') != self.manifest_actual['sha256']:
                raise ValueError('FRESH_RECEIPT_GATE_MANIFEST_STALE')
            input_path = fresh['input_manifest_path']
            if input_path not in self.checked or self.files[input_path]['kind'] != 'input' or record.get('input_manifest_sha256') != self.checked[input_path]['sha256']:
                raise ValueError('FRESH_RECEIPT_INPUT_MANIFEST_STALE')
            expected = fresh['expected_output_sha256']
            if not isinstance(expected, str) or not SHA.fullmatch(expected):
                raise ValueError('APPROVED_REPRODUCTION_CRITERION_UNKNOWN')
            start = dt.datetime.fromisoformat(record['started_at_utc'].replace('Z', '+00:00'))
            end = dt.datetime.fromisoformat(record['completed_at_utc'].replace('Z', '+00:00'))
            if start.tzinfo is None or end.tzinfo is None or not start < end <= dt.datetime.now(dt.timezone.utc):
                raise ValueError('FRESH_RECEIPT_TIME_INVALID')
            environment = record['clean_environment']
            if checkout_path is None or environment.get('baseline_clean') is not True or environment.get('source_commit') != self.head:
                raise ValueError('EXPLICIT_CLEAN_CHECKOUT_EVIDENCE_REQUIRED')
            checkout = Path(checkout_path).absolute()
            if any(parent.is_symlink() or forbidden_name(parent.name) for parent in [checkout, *checkout.parents]):
                raise ValueError('CLEAN_CHECKOUT_INVALID')
            checkout, original = checkout.resolve(), self.repo.resolve()
            if checkout == original or checkout in original.parents or original in checkout.parents or Path(environment['checkout_path']).resolve() != checkout:
                raise ValueError('CLEAN_CHECKOUT_INVALID')
            if Path(git(checkout, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != checkout or git(checkout, 'rev-parse', 'HEAD').decode().strip() != self.head or git(checkout, 'status', '--porcelain', '--untracked-files=all').strip():
                raise ValueError('CLEAN_CHECKOUT_SOURCE_DIFFERS')
            for relative, actual in self.checked.items():
                file = safe_file(checkout, relative)
                if file.stat().st_size != actual['bytes'] or digest(file) != actual['sha256']:
                    raise ValueError('CLEAN_CHECKOUT_REQUIRED_INPUT_DIFFERS')
            if digest(safe_file(checkout, self.manifest_path)) != self.manifest_actual['sha256']:
                raise ValueError('CLEAN_CHECKOUT_GATE_MANIFEST_DIFFERS')
            command = record['command']
            if type(command.get('exit_code')) is not int or command['exit_code'] != 0 or not isinstance(command.get('argv'), list) or not command['argv'] or not all(isinstance(arg, str) and arg for arg in command['argv']):
                raise ValueError('FRESH_COMMAND_EVIDENCE_INVALID')
            procedure = fresh.get('procedure_path')
            approved = fresh.get('approved_command')
            if procedure not in self.checked or self.files[procedure]['kind'] != 'procedure' or not isinstance(approved, list) or not approved or not all(isinstance(arg, str) and arg for arg in approved):
                raise ValueError('APPROVED_REPRODUCTION_PROCEDURE_UNKNOWN')
            approved = [arg.replace('{checkout}', str(checkout)).replace('{evidence}', str(receipt_file.parent.resolve())) for arg in approved]
            if command['argv'] != approved or Path(command['cwd']).resolve() != checkout:
                raise ValueError('FRESH_COMMAND_DIFFERS_FROM_APPROVED_PROCEDURE')
            entrypoints = {str(checkout / relative) for relative, row in self.files.items() if row['kind'] in ('source', 'procedure')}
            entrypoints |= {relative for relative, row in self.files.items() if row['kind'] in ('source', 'procedure')}
            if not any(arg in entrypoints for arg in approved):
                raise ValueError('APPROVED_COMMAND_HAS_NO_PRESERVED_ENTRYPOINT')
            log = safe_file(receipt_file.parent, command['log_path'])
            if log.stat().st_size == 0 or digest(log) != command.get('log_sha256'):
                raise ValueError('FRESH_COMMAND_LOG_INVALID')
            output = record['output']
            artifact = safe_file(receipt_file.parent, output['path'])
            if artifact.name == '07_FINAL_HOLD.png' or artifact.resolve() in {value['path'].resolve() for value in self.checked.values()}:
                raise ValueError('PRESERVED_PROOF_REUSED_AS_FRESH_OUTPUT')
            if digest(artifact) != expected or output.get('sha256') != expected:
                raise ValueError('FRESH_OUTPUT_HASH_MISMATCH')
            if not start.timestamp() <= artifact.stat().st_mtime <= end.timestamp():
                raise ValueError('FRESH_OUTPUT_TIME_OUTSIDE_COMMAND_SESSION')
            self.result[condition]['status'] = 'PASS'
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError) as error:
            self.result[condition]['status'] = 'FAIL'
            self.reason(condition, str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z_]+', str(error)) else 'FRESH_REPRODUCTION_EVIDENCE_INVALID')

    def run(self, receipt=None, checkout=None):
        self.required_files()
        self.dependencies()
        self.imports()
        self.temporary_inputs()
        self.reproduction(receipt, checkout)
        complete = all(row['status'] == 'PASS' for row in self.result.values())
        return {'schema': 1, 'generic_scope': 'ALL_WORLD_ENGINE_DEVELOPMENT_GATES',
                'source_commit': self.head, 'conditions': self.result,
                'overall': 'GATE_COMPLETE' if complete else 'GATE_INCOMPLETE',
                'next_development_stage_allowed': complete,
                'advance_scope': 'Next development Gate or Camera V5; authorized repairs and phase-prerequisite reproduction within this Gate remain allowed',
                'validated_required_files': len(self.checked), 'declared_required_files': len(self.files),
                'render_executed_by_validator': False, 'git_mutations': 0,
                'receipt_limit': 'Evidence and bytes checked; not cryptographic execution attestation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--manifest', default='world-simulation-shorts-engine/recovery/v4/PERMANENT_GATE_MANIFEST.json')
    parser.add_argument('--receipt', type=Path, help='Explicit private fresh-reproduction receipt; external paths are never inferred')
    parser.add_argument('--clean-checkout', type=Path, help='Explicit separate clean checkout used for the actual reproduction')
    args = parser.parse_args()
    try:
        report = Gate(args.repo.absolute(), args.manifest).run(args.receipt, args.clean_checkout)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.CalledProcessError):
        report = {'schema': 1, 'generic_scope': 'ALL_WORLD_ENGINE_DEVELOPMENT_GATES',
                  'conditions': {name: {'status': 'FAIL', 'reasons': [{'code': 'GATE_INPUT_INVALID'}]} for name in CONDITIONS},
                  'overall': 'GATE_INCOMPLETE', 'next_development_stage_allowed': False,
                  'render_executed_by_validator': False, 'git_mutations': 0}
    print(json.dumps(report, indent=2))
    return 0 if report['overall'] == 'GATE_COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
