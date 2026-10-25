#!/usr/bin/env python3
"""Single UID1000 Studio child authorized only by the new cold-start parent."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys
import threading

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def fail(code):
    raise RuntimeError(code)


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        fail('COLD_START_WORKER_ARGUMENTS_INVALID')


def bootstrap(path, expected):
    if (path != HERE / 'STARTUP_MANIFEST.json'
            or not re.fullmatch('[a-f0-9]{64}', str(expected))
            or any(p.is_symlink() for p in (path, *path.parents))):
        fail('COLD_START_WORKER_PIN_REQUIRED')
    raw = path.read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected:
        fail('COLD_START_MANIFEST_CHANGED')
    value = json.loads(raw)
    file = HERE / 'bootstrap.py'
    body = file.read_bytes()
    row = value['files']['bootstrap.py']
    if len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
        fail('COLD_START_PARENT_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location('_verified_cold_start_bootstrap', file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.verify_startup(path, expected)
    return module


def proof_from_parent(fd, helpers, args):
    if os.getuid() != 1000 or os.getgid() != 1000 or not sys.flags.isolated:
        fail('COLD_START_ENGINE_IDENTITY_REQUIRED')
    if fd < 3 or not stat.S_ISFIFO(os.fstat(fd).st_mode):
        fail('COLD_START_PARENT_PIPE_REQUIRED')
    try:
        if not select.select([fd], [], [], 10)[0]:
            fail('COLD_START_PARENT_PROOF_TIMEOUT')
        raw = os.read(fd, 4097)
    finally:
        os.close(fd)
    if not raw or len(raw) > 4096:
        fail('COLD_START_BOUNDED_PROOF_REQUIRED')
    proof = helpers.document(raw)
    parent = helpers.process(os.getppid())
    lock = helpers.RUN.lstat()
    if (not stat.S_ISDIR(lock.st_mode) or lock.st_uid != 0 or lock.st_gid != 1000
            or stat.S_IMODE(lock.st_mode) != 0o750 or helpers.RUN.is_symlink()):
        fail('COLD_START_ROOT_LOCK_REQUIRED')
    expected_keys = {'schema', 'parentPid', 'parentStartTicks', 'childPid',
                     'startupManifestSHA256', 'runtimeManifestSHA256',
                     'bootstrapSHA256', 'stateRoot', 'port'}
    status = (Path('/proc') / str(os.getppid()) / 'status').read_text()
    uid_line = next(line.split()[1:] for line in status.splitlines() if line.startswith('Uid:'))
    parent_file = str(HERE / 'bootstrap.py')
    if (not isinstance(proof, dict) or set(proof) != expected_keys
            or proof['schema'] != 'WORLD_ENGINE_STUDIO_COLD_START_PROOF_V1'
            or proof['parentPid'] != os.getppid() or parent['ppid'] != 1
            or proof['parentStartTicks'] != parent['startTicks'] or proof['childPid'] != os.getpid()
            or set(uid_line) != {'0'} or parent_file not in parent['command']
            or proof['bootstrapSHA256'] != helpers.digest(helpers.regular(Path(parent_file)))
            or proof['startupManifestSHA256'] != args.startup_manifest_sha256
            or proof['runtimeManifestSHA256'] != args.source_manifest_sha256
            or proof['stateRoot'] != os.environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT')
            or proof['port'] != 8080):
        fail('COLD_START_PARENT_OWNERSHIP_REQUIRED')
    # Verify init lineage as well as an arbitrary process's command string.
    init = helpers.process(1)
    # UID1000 must not require ptrace access to root's /proc/1/exe. The root
    # bootstrap already verified that executable before creating this pipe.
    if (parent_file not in init['command'] or '-g' not in init['command']
            or Path(init['command'][0]).name not in {'tini', 'tini-static'}):
        fail('COLD_START_TINI_PROCESS_GROUP_REQUIRED')
    helpers.no_previous_studio()
    helpers.ports_free((8080,))
    return proof


def main(argv=None):
    parser = Parser()
    parser.add_argument('--startup-manifest', type=Path, required=True)
    parser.add_argument('--startup-manifest-sha256', required=True)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--source-manifest-sha256', required=True)
    parser.add_argument('--export-root', type=Path, required=True)
    parser.add_argument('--startup-proof-fd', type=int, required=True)
    helpers = None
    try:
        args = parser.parse_args(argv)
        helpers = bootstrap(args.startup_manifest, args.startup_manifest_sha256)
        proof_from_parent(args.startup_proof_fd, helpers, args)
        serve, contract = helpers.source_contract(args.source_manifest, args.source_manifest_sha256)
        config = serve.configuration(os.environ, export_root=args.export_root)
        if config.get('configuration_error') or not config.get('initial_origin'):
            fail(config.get('configuration_error') or 'STUDIO_HTTPS_ORIGIN_REQUIRED')
        app, server_type = serve.application(contract, config)
        if app.normal is None or app.configuration_error:
            fail(app.configuration_error or 'COLD_START_CONFIGURED_STUDIO_REQUIRED')
        controller = app.controller._controller()
        if (type(controller).__name__ != 'NvidiaPresentationController'
                or Path(sys.modules[type(controller).__module__].__file__).resolve()
                != contract.repo / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_controller.py'):
            fail('COLD_START_LATEST_CONTROLLER_REQUIRED')
        try:
            server = server_type((config['host'], config['port']), app.handler())
        except OSError:
            fail('COLD_START_PORT_ALREADY_IN_USE')
        stopping = threading.Event()

        def stop(signum, _frame):
            if not stopping.is_set():
                stopping.set()
                threading.Thread(target=server.shutdown, daemon=True).start()

        old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
        helpers.record('WORLD_ENGINE_COLD_START_WEB_STARTED', pid=os.getpid(), listenerStarted=True,
                       mode='CONFIGURED', latestController=type(controller).__name__,
                       exampleName='AVIATION_EUROPE_NL.json', servicePort=config['port'],
                       startupManifestSHA256=args.startup_manifest_sha256)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            server.server_close()
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
        helpers.record('COLD_START_WEB_STOPPED', listenerStarted=False)
        return 0
    except Exception as error:
        value = getattr(error, 'code', None) or str(error)
        code = value if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,119}', value) else 'COLD_START_WORKER_FAILED'
        print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_COLD_START_V1',
                          'stage': 'COLD_START_WORKER_BLOCKED', 'errorCode': code,
                          'listenerStarted': False, 'renderAutomaticallyStarted': False,
                          'gpuRenderingVerified': False}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
