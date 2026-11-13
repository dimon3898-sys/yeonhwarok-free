"""Scene-independent admission in the actual image; no service/GPU/render entry."""
import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import sys
import tempfile

def require(ok, code):
    if not ok:
        raise RuntimeError(code)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def regular(path):
    require(path.is_file(), 'REQUIRED_FILE_MISSING')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'SOURCE_SYMLINK_FORBIDDEN')
    st = path.stat()
    require(st.st_nlink == 1 and not st.st_mode & 0o022 and not (st.st_uid == os.getuid() and st.st_mode & 0o200), 'SOURCE_PERMISSION_INVALID')
    return path.read_bytes()

def probe(request):
    policy, entry = request['policy'], request['entrypoint']
    root = Path(policy['installedRepoRoot'])
    rec = root / 'world-simulation-shorts-engine/recovery'
    controller = rec / 'codex-to-gcube-handoff-v1/controller'
    worker = controller / 'nvidia_worker.py'
    require(os.getuid() == 1000, 'GATE_UID1000_REQUIRED')
    require(worker.is_file(), 'REQUIRED_WORKER_MISSING')
    raw = regular(worker)
    tree = ast.parse(raw)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    require('_read_frame_evidence' in functions, 'BOUNDED_READER_MISSING')
    require('HANDOFF_LAUNCH_IDENTITY_MISMATCH' in raw.decode() and 'state = published' in raw.decode(), 'WORKER_PUBLICATION_FIX_MISSING')
    require(sha(raw) == policy['requiredWorkerSHA256'], 'REQUIRED_WORKER_FIX_CHANGED')
    for name, expected in policy['preservedCodePins'].items():
        require(sha(regular(root / name)) == expected, 'PRESERVED_SECURITY_SOURCE_CHANGED')
    backend = (controller / 'nvidia_backend.py').read_text()
    require("str(HERE / 'nvidia_worker.py')" in backend, 'NVIDIA_WORKER_PATH_CHANGED')
    calls = [n for n in ast.walk(functions['_validate_capture']) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_read_frame_evidence']
    require(len(calls) == 1 and ast.unparse(calls[0]) == "_read_frame_evidence(directory, receipt.get('frameEvidence'), total_frames)", 'NVIDIA_READER_NOT_CONNECTED')
    require(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_validate_capture' for n in ast.walk(functions['_run'])), 'NVIDIA_VALIDATION_NOT_CONNECTED')
    bootpath = rec / 'studio-cold-start-v2/bootstrap.py'
    startup = bootpath.parent / 'STARTUP_MANIFEST.json'
    manifest = rec / 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
    def arg(name):
        require(entry.count(name) == 1, 'ENTRYPOINT_REQUIRED_PIN_MISSING')
        return entry[entry.index(name) + 1]
    require(entry[:6] == ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B'] and entry[6] == str(bootpath), 'FORMAL_ENTRYPOINT_REQUIRED')
    require(arg('--source-manifest') == str(manifest) and arg('--startup-manifest') == str(startup), 'ENTRYPOINT_SOURCE_PATH_INVALID')
    require(arg('--source-manifest-sha256') == sha(regular(manifest)), 'SOURCE_MANIFEST_MISMATCH')
    require(arg('--startup-manifest-sha256') == sha(regular(startup)), 'STARTUP_MANIFEST_MISMATCH')
    boot = load('_release_guard_boot', bootpath)
    boot.verify_startup(startup, arg('--startup-manifest-sha256'))
    child = load('_release_guard_child', bootpath.parent / 'worker.py')
    child.bootstrap(startup, arg('--startup-manifest-sha256'))
    boot.source_contract(manifest, arg('--source-manifest-sha256'))
    sys.path.insert(0, str(controller))
    import nvidia_worker
    require(Path(nvidia_worker.__file__) == worker, 'IMPORTED_WORKER_ORIGIN_INVALID')
    require(nvidia_worker._validate_capture.__globals__['_read_frame_evidence'] is nvidia_worker._read_frame_evidence, 'IMPORTED_READER_BINDING_INVALID')
    cache = nvidia_worker.cache()
    require(cache.MAX_JSON == policy['genericJSONLimitBytes'] == 33554432, 'GENERIC_JSON_LIMIT_CHANGED')
    cases = []
    # New gate fixture, not a previous visual/reader unit-test rerun.
    # Large valid frame metadata, never treated as a rendered frame or GPU proof.
    with tempfile.TemporaryDirectory(prefix='release-admission-') as folder:
        directory = Path(folder)
        f = directory / 'FRAME_EVIDENCE.json'
        payload = json.dumps({'frames': [{'frame': i, 'diagnostic': {'glError': 0}} for i in range(180)], 'gateFixture': 'x' * (33 * 1024**2)}, separators=(',', ':')).encode()
        f.write_bytes(payload)
        f.chmod(0o600)
        ref = {'file': f.name, 'sha256': sha(payload)}
        def reject(call, code):
            try:
                call()
            except RuntimeError as error:
                require(str(error) == code, 'UNEXPECTED_REJECTION_CODE')
            else:
                raise RuntimeError('UNSAFE_DOCUMENT_ACCEPTED')
        with cache.PrivateTree(directory) as private:
            reject(lambda: private.json(f.name), 'JSON_SIZE_INVALID')
            cases.append('generic_32MiB_limit_preserved')
            value = nvidia_worker._read_frame_evidence(private, ref, 180)
            require(len(value['frames']) == 180 and len(value['gateFixture']) == 33 * 1024**2, 'LARGE_LEDGER_TRUNCATED')
            cases.append('imported_reader_over_32MiB')
            reject(lambda: nvidia_worker._read_frame_evidence(private, {**ref, 'sha256': '0' * 64}, 180), 'HANDOFF_FRAME_EVIDENCE_SHA256_MISMATCH')
            cases.append('wrong_SHA_rejected')
            f.chmod(0o644)
            reject(lambda: nvidia_worker._read_frame_evidence(private, ref, 180), 'PRIVATE_PATH_REQUIRED')
            f.chmod(0o600)
            cases.append('unsafe_mode_rejected')
            alias = directory / 'other.json'
            os.link(f, alias)
            reject(lambda: nvidia_worker._read_frame_evidence(private, ref, 180), 'PRIVATE_PATH_REQUIRED')
            alias.unlink()
            cases.append('hardlink_rejected')
            require(sha(f.read_bytes()) == ref['sha256'], 'LEDGER_BYTES_CHANGED')
    return {'status': 'PASS', 'scope': policy['scope'], 'workerSHA256': sha(raw),
            'runtimeManifestSHA256': arg('--source-manifest-sha256'),
            'startupManifestSHA256': arg('--startup-manifest-sha256'),
            'largeFixtureBytes': len(payload), 'newGateCases': cases,
            'nativeRouteBinding': 'PASS', 'workerPublicationFix': 'PASS',
            'parentChildStartupPins': 'PASS', 'sourceClosure': 'PASS',
            'GPUExecutions': 0, 'rendererExecutions': 0, 'oldPassReruns': 0}

if __name__ == '__main__':
    try:
        print(json.dumps(probe(json.load(sys.stdin))))
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{2,120}', code):
            code = 'GATE_PROBE_EXCEPTION_' + type(error).__name__.upper()
        print(json.dumps({'status': 'FAIL', 'code': code, 'GPUExecutions': 0, 'rendererExecutions': 0}))
        raise SystemExit(1)
