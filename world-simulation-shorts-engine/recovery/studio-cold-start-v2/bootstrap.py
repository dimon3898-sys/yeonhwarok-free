#!/usr/bin/env python3
"""Packaged, single-use cold start with the preserved authenticated setup UI.

No running service is replaced. No rendering, retry or provider operation is
initiated here. The old image, auth helpers and runtime manifest stay frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROXY = Path('/opt/world-engine-studio-https-proxy-fix')
HTTPS = Path('/opt/world-engine-studio-https-bootstrap')
RUN = Path('/run/world-engine-cold-start')
SOURCE_SHA = '138f5ff4761e2fa3589e15493ded5401afe1ec4dfa0dc5ad5a725e03e53b9270'
IMAGE = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
SOURCE_SUFFIX = 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
SERVE_SUFFIX = 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/serve.py'
CODE = re.compile(r'[A-Z][A-Z0-9_]{0,119}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def fail(code):
    raise RuntimeError(code)


def record(stage, **fields):
    print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_COLD_START_V2',
                     'stage': stage, 'renderAutomaticallyStarted': False,
                     'gpuRenderingVerified': False, **fields}, sort_keys=True), flush=True)


def safe_error(error):
    value = getattr(error, 'code', None) or str(error)
    return value if isinstance(value, str) and CODE.fullmatch(value) else 'COLD_START_FAILED'


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        fail('COLD_START_ARGUMENTS_INVALID')


def absolute(path):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        fail('COLD_START_CANONICAL_PATH_REQUIRED')
    return path


def regular(path, maximum=8 * 1024**2):
    path = absolute(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            fail('COLD_START_BOUNDED_REGULAR_FILE_REQUIRED')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) != before.st_size or
            (before.st_size, before.st_mtime_ns, before.st_ino) !=
            (after.st_size, after.st_mtime_ns, after.st_ino)):
        fail('COLD_START_SOURCE_CHANGED_DURING_READ')
    return raw


def document(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                fail('COLD_START_DUPLICATE_JSON_KEY')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: fail('COLD_START_FINITE_JSON_REQUIRED'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_startup(path, expected):
    path = absolute(path)
    if path.parent != HERE or path.name != 'STARTUP_MANIFEST.json' or not SHA.fullmatch(str(expected)):
        fail('COLD_START_PINNED_MANIFEST_REQUIRED')
    raw = regular(path)
    if digest(raw) != expected:
        fail('COLD_START_MANIFEST_CHANGED')
    value = document(raw)
    if (not isinstance(value, dict)
            or set(value) != {'schema', 'runtimeManifestSHA256', 'baseImageDigest', 'files'}
            or value['schema'] != 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2'
            or value['runtimeManifestSHA256'] != SOURCE_SHA or value['baseImageDigest'] != IMAGE
            or set(value['files']) != {'bootstrap.py', 'worker.py'}):
        fail('COLD_START_MANIFEST_CONTRACT_INVALID')
    for name, row in value['files'].items():
        if (not isinstance(row, dict) or set(row) != {'bytes', 'sha256'}
                or type(row['bytes']) is not int or not SHA.fullmatch(str(row['sha256']))):
            fail('COLD_START_MANIFEST_ROW_INVALID')
        file = HERE / name
        body = regular(file)
        info = file.stat()
        # The container may read a host checkout owned by UID1001. Its code
        # must never be writable by the Studio's UID/GID1000 or everyone.
        if (info.st_mode & 0o002 or info.st_uid == 1000 and info.st_mode & 0o200
                or info.st_gid == 1000 and info.st_mode & 0o020):
            fail('COLD_START_ENGINE_WRITABLE_SOURCE_FORBIDDEN')
        for directory in file.parents:
            mode = directory.stat()
            if (mode.st_mode & 0o002 or mode.st_uid == 1000 and mode.st_mode & 0o200
                    or mode.st_gid == 1000 and mode.st_mode & 0o020):
                fail('COLD_START_ENGINE_WRITABLE_SOURCE_PARENT_FORBIDDEN')
        if len(body) != row['bytes'] or digest(body) != row['sha256']:
            fail('COLD_START_SOURCE_CHANGED')
    return value


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_contract(path, expected):
    path = absolute(path)
    if expected != SOURCE_SHA or not path.as_posix().endswith('/' + SOURCE_SUFFIX):
        fail('COLD_START_APPROVED_RUNTIME_REQUIRED')
    raw = regular(path)
    if digest(raw) != expected:
        fail('HANDOFF_SOURCE_MANIFEST_CHANGED')
    rows = document(raw).get('files', [])
    matches = [row for row in rows if row.get('path') == SERVE_SUFFIX]
    if len(matches) != 1:
        fail('COLD_START_SERVE_SOURCE_REQUIRED')
    repo = path.parents[3]
    file = repo / SERVE_SUFFIX
    data = regular(file)
    if len(data) != matches[0]['bytes'] or digest(data) != matches[0]['sha256']:
        fail('COLD_START_SERVE_SOURCE_CHANGED')
    serve = load('_cold_start_verified_serve', file)
    contract = serve.verify_preimport_sources(path, expected, repo=repo)
    return serve, contract


def process(pid):
    raw = Path('/proc') / str(pid)
    fields = (raw / 'stat').read_text().rsplit(')', 1)[1].split()
    command = (raw / 'cmdline').read_bytes().split(b'\0')
    return {'pid': pid, 'ppid': int(fields[1]), 'startTicks': fields[19],
            'command': [x.decode('utf-8', 'strict') for x in command if x]}


def container_parent():
    if os.geteuid() != 0 or not sys.flags.isolated or os.getppid() != 1:
        fail('COLD_START_ROOT_TINI_ENTRYPOINT_REQUIRED')
    init = process(1)
    if (Path(os.readlink('/proc/1/exe')).name not in {'tini', 'tini-static'}
            or '-g' not in init['command'] or str(HERE / 'bootstrap.py') not in init['command']):
        fail('COLD_START_TINI_PROCESS_GROUP_REQUIRED')
    return process(os.getpid())


def no_previous_studio():
    old = {str(PROXY / 'proxy_bootstrap.py'), str(PROXY / 'proxy_server.py'),
           str(HTTPS / 'https_bootstrap.py'), str(HTTPS / 'https_server.py')}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            command = (entry / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        for arg in command:
            text = arg.decode('utf-8', 'replace')
            if text in old or text.endswith('/codex-to-gcube-handoff-v1/controller/serve.py'):
                fail('COLD_START_EXISTING_STUDIO_FORBIDDEN')


def ports_free(ports):
    held = []
    try:
        for port in sorted(set(ports)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            held.append(sock)
            sock.bind(('0.0.0.0', port))
    except OSError:
        fail('COLD_START_PORT_ALREADY_IN_USE')
    finally:
        for sock in held:
            sock.close()


def fresh_lock():
    absolute(RUN)
    try:
        RUN.mkdir(mode=0o750)
    except FileExistsError:
        fail('COLD_START_ALREADY_ATTEMPTED')
    os.chown(RUN, 0, 1000)
    os.chmod(RUN, 0o750, follow_symlinks=False)
    # Deliberately never remove this one-attempt marker inside a container.


def prepare_private(parent, environ, export_root):
    root_value = environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT')
    if not root_value:
        fail('COLD_START_EXPLICIT_PRIVATE_ROOT_REQUIRED')
    root = absolute(root_value)
    exports = absolute(export_root)
    if root.exists():
        fail('COLD_START_FRESH_PRIVATE_ROOT_REQUIRED')
    if (not root.parent.is_dir() or not exports.is_dir() or root == Path('/world-storage')
            or root.is_relative_to('/world-storage') or root.is_relative_to(exports)
            or exports.is_relative_to(root)):
        fail('HANDOFF_PRIVATE_PUBLIC_ROOTS_MUST_BE_DISJOINT')
    deployed = environ.get('WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST', '')
    if (environ.get('GPU_BACKEND') != 'vulkan'
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', deployed)
            or deployed == IMAGE
            or environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') != deployed):
        fail('COLD_START_PINNED_NVIDIA_PROFILE_REQUIRED')
    if environ.get('WORLD_ENGINE_STUDIO_PORT', '8080') != '8080':
        fail('COLD_START_ORIGINAL_SERVICE_PORT_REQUIRED')
    if not environ.get('WORLD_ENGINE_STUDIO_OWNER_CODE'):
        fail('STUDIO_OWNER_CONFIGURATION_REQUIRED')
    policy = parent.bootstrap._json_policy(environ.get('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'))
    parent.bootstrap._validate_policy(policy)
    # Reuse the existing owner-authenticated SETUP state when the provider
    # reveals its URL after deployment. Never infer an origin or bypass auth.
    setup = sys.modules.get('setup_core')
    if setup is None:
        fail('COLD_START_FIXED_SETUP_MODULE_REQUIRED')
    origin = environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN')
    if origin not in (None, ''):
        setup.canonical_origin(origin)
    config = parent.bootstrap.prepare_configuration(environ)
    if config.get('configuration_error'):
        fail(config['configuration_error'])
    return config


def main(argv=None):
    parser = Parser()
    parser.add_argument('--startup-manifest', type=Path, required=True)
    parser.add_argument('--startup-manifest-sha256', required=True)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--source-manifest-sha256', required=True)
    parser.add_argument('--export-root', type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        bundle = verify_startup(args.startup_manifest, args.startup_manifest_sha256)
        identity = container_parent()
        fresh_lock()
        no_previous_studio()
        ports_free((8080, 8000))
        _, contract = source_contract(args.source_manifest, args.source_manifest_sha256)
        sys.path.insert(0, str(PROXY))
        parent_module = load('parent', PROXY / 'parent.py')
        parent = parent_module.modules()
        load('_cold_start_frozen_proxy_manifest', PROXY / 'manifest.py').verify_sources()
        config = prepare_private(parent, os.environ, args.export_root)
        environment = parent.bootstrap.child_environment(os.environ, studio=True, config=config)
        for name in parent.bootstrap.original.SECRET_ENV:
            os.environ.pop(name, None)
        launched = False

        def spawn_latest(command, **kwargs):
            nonlocal launched
            expected = ['/usr/bin/python3', '-B', str(HTTPS / 'https_server.py')]
            if command[:3] != expected:
                if command != parent.bootstrap.original.LEGACY_COMMAND:
                    fail('COLD_START_UNEXPECTED_CHILD_COMMAND')
                child = subprocess.Popen(command, **kwargs)
                record('COLD_START_GPU_ADMISSION_CHILD_STARTED', pid=child.pid)
                return child
            if launched:
                fail('COLD_START_SECOND_STUDIO_FORBIDDEN')
            launched = True
            read_fd, write_fd = os.pipe()
            child = None
            try:
                child = subprocess.Popen(['/usr/bin/python3', '-I', '-B', str(HERE / 'worker.py'),
                    '--startup-manifest', str(args.startup_manifest),
                    '--startup-manifest-sha256', args.startup_manifest_sha256,
                    '--source-manifest', str(args.source_manifest),
                    '--source-manifest-sha256', args.source_manifest_sha256,
                    '--export-root', str(args.export_root), '--startup-proof-fd', str(read_fd)],
                    pass_fds=(read_fd,), **kwargs)
                proof = {'schema': 'WORLD_ENGINE_STUDIO_COLD_START_PROOF_V1',
                         'parentPid': identity['pid'], 'parentStartTicks': identity['startTicks'],
                         'childPid': child.pid, 'startupManifestSHA256': args.startup_manifest_sha256,
                         'runtimeManifestSHA256': contract.expected_sha256,
                         'bootstrapSHA256': bundle['files']['bootstrap.py']['sha256'],
                         'stateRoot': str(config['root']), 'port': config['port']}
                raw = json.dumps(proof, sort_keys=True, separators=(',', ':')).encode()
                if len(raw) > 4096 or os.write(write_fd, raw) != len(raw):
                    fail('COLD_START_PROOF_DELIVERY_FAILED')
                record('COLD_START_STUDIO_CHILD_STARTED', pid=child.pid)
                return child
            except BaseException:
                # supervise() cannot own this child until the adapter returns.
                # Reap it here if proof delivery or safe logging fails first.
                parent.bootstrap.original.stop_child(child)
                raise
            finally:
                os.close(read_fd)
                os.close(write_fd)

        record('COLD_START_SUPERVISOR_STARTED', pid=os.getpid(),
               startupManifestSHA256=args.startup_manifest_sha256)
        return parent.bootstrap.supervise(config, environment, spawn=spawn_latest)
    except Exception as error:
        record('COLD_START_BLOCKED', status='BLOCKED', errorCode=safe_error(error), listenerStarted=False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
