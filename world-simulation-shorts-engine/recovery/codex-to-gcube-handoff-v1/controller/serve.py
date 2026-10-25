#!/usr/bin/env python3
"""Pinned opt-in Studio wiring; check-only unless exclusive activation is proven.

This entry does not initialize credentials, repair ownership, stop a process,
replace a proxy, create a GPU workload or relax the frozen HTTPS/GPU guards.
Only standard-library code runs before the complete source contract is checked.
"""
from __future__ import annotations
import argparse
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ENGINE = 'world-simulation-shorts-engine'
RECOVERY = ENGINE + '/recovery/'
NAMESPACE = RECOVERY + 'codex-to-gcube-handoff-v1/'
SCHEMA = 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1'
SHA = re.compile(r'[a-f0-9]{64}\Z')
MAX_SOURCE = 128 * 1024 ** 2
ENV_NAMES = ('GPU_BACKEND', 'WORLD_ENGINE_STUDIO_STATE_ROOT',
    'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON',
    'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', 'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST',
    'WORLD_ENGINE_STUDIO_PORT', 'WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR')
REQUIRED = tuple(NAMESPACE + x for x in (
    'controller/serve.py', 'controller/common.py', 'controller/preserved_mvp_sources.json',
    'controller/nvidia_controller.py', 'controller/nvidia_backend.py',
    'controller/nvidia_worker.py', 'controller/lease_supervisor.py',
    'backend/capture_nvidia.mjs', 'backend/profile_contract.mjs',
    'backend/native_guard.mjs', 'backend/private_workspace.mjs',
    'mobile/handler.py', 'mobile/index.html', 'mobile/app.js',
    'docs/EXPECTED_EXTERNAL_HTTPS_PAYLOADS.json',
    'docs/expected-manifests/PROXY_EXTENSION_FILES.json',
    'docs/expected-manifests/EXTENSION_FILES.json',
    'docs/expected-manifests/STUDIO_FILES.json'))
CONDITIONAL = {
    '/opt/world-engine-storage-fix/storage.py': RECOVERY + 'gcube-storage-fix-v1/storage.py',
    **{'/opt/world-engine-startup-diagnostics/' + n: RECOVERY + 'gcube-diagnostic-image-v1/' + n
       for n in ('startup.py', 'records.py', 'service.py')},
    **{'/opt/world-engine-detached-render/' + n: RECOVERY + 'gcube-detached-render-v1/' + n
       for n in ('job_manager.py', 'job_store.py', 'inspect_existing.py')},
}
GENERATED = {
    '/opt/world-engine-production-studio/STUDIO_FILES.json': '1f4129faaeb59027429d4d531da2b7e7b50156ca7c1652e700dd542c935b88de',
    '/opt/world-engine-studio-https-bootstrap/EXTENSION_FILES.json': 'b46b2bff3e8ef5887e1e61b9c0d835d1135b57f2810ddcc94e36e7c461eec665',
    '/opt/world-engine-studio-https-proxy-fix/PROXY_EXTENSION_FILES.json': 'b25c07f5aefdf63c3919f2ab439c978308d9304e92a8e2c6e92c991259ee0d56',
}


def fail(code):
    raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\0' in value
            or value.startswith('/') or any(x in {'', '.', '..'} for x in value.split('/'))
            or PurePosixPath(value).as_posix() != value):
        fail('HANDOFF_SOURCE_MANIFEST_PATH')
    return value


def _path(path):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        fail('HANDOFF_ABSOLUTE_NOFOLLOW_PATH_REQUIRED')
    return path


def _read_regular(path, maximum=MAX_SOURCE):
    path = _path(path)
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= maximum:
            fail('HANDOFF_BOUNDED_REGULAR_SOURCE_REQUIRED')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            raw = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        if len(raw) != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            fail('HANDOFF_SOURCE_CHANGED_DURING_READ')
        return raw
    except OSError:
        fail('HANDOFF_REQUIRED_SOURCE_UNAVAILABLE')
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail('HANDOFF_SOURCE_JSON_DUPLICATE_KEY')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: fail('HANDOFF_FINITE_SOURCE_JSON_REQUIRED'))
    except (ValueError, UnicodeError, RecursionError):
        fail('HANDOFF_SOURCE_MANIFEST_JSON_INVALID')


def _row(row, *, absolute=False):
    if (not isinstance(row, dict) or not {'path', 'sha256', 'bytes'} <= row.keys()
            or not SHA.fullmatch(str(row.get('sha256')))
            or type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= MAX_SOURCE):
        fail('HANDOFF_SOURCE_MANIFEST_ROW_INVALID')
    if absolute:
        path = row['path']
        if not isinstance(path, str) or not path.startswith('/opt/'):
            fail('HANDOFF_FIXED_INSTALLED_SOURCE_PATH_REQUIRED')
        _canonical_relative(path[1:])
    else:
        _canonical_relative(row['path'])
    return row


def _expected_external(local, data):
    """Derive the same complete fixed-parent payload using already checked bytes."""
    expected = {}
    def add(relative, absolute):
        if relative not in local:
            fail('HANDOFF_FIXED_PARENT_LOCAL_MIRROR_MISSING')
        expected[absolute] = local[relative]
    proof_path = NAMESPACE + 'docs/EXPECTED_EXTERNAL_HTTPS_PAYLOADS.json'
    proof = _json(data[proof_path])
    if (not isinstance(proof, dict) or proof.get('schema') != 'WORLD_ENGINE_EXPECTED_EXTERNAL_HTTPS_PAYLOADS_V1'
            or not isinstance(proof.get('payloads'), list) or not isinstance(proof.get('rows'), list)):
        fail('HANDOFF_EXACT_EXTERNAL_PAYLOAD_EVIDENCE_REQUIRED')
    declared_paths, roots, source_namespaces = {}, set(), {}
    for payload in proof['payloads']:
        if not isinstance(payload, dict):
            fail('HANDOFF_FIXED_PARENT_INVENTORY_REQUIRED')
        alias, name = payload.get('externalRoot'), payload.get('manifestName')
        full = str(alias) + '/' + str(name)
        if full not in GENERATED or alias in roots:
            fail('HANDOFF_FIXED_PARENT_PATH_SET_CHANGED')
        roots.add(alias)
        source_namespace = payload.get('sourceNamespace')
        if not isinstance(source_namespace, str):
            fail('HANDOFF_FIXED_PARENT_INVENTORY_REQUIRED')
        source_namespaces[alias] = _canonical_relative(source_namespace)
        body = NAMESPACE + 'docs/expected-manifests/' + name
        if payload.get('manifestBodyRepoPath') != body or body not in local or sha(data[body]) != GENERATED[full]:
            fail('HANDOFF_FROZEN_GENERATED_MANIFEST_CHANGED')
        declared = _json(data[body])
        if not isinstance(declared.get('files'), dict) or not isinstance(declared.get('testFiles'), dict):
            fail('HANDOFF_FIXED_PARENT_INVENTORY_REQUIRED')
        files = {**declared['files'], **declared['testFiles'], name: GENERATED[full]}
        if files != payload.get('expectedFiles'):
            fail('HANDOFF_FIXED_PARENT_PATH_SET_CHANGED')
        for filename, digest in files.items():
            path = alias + '/' + _canonical_relative(filename)
            if path in declared_paths or not SHA.fullmatch(str(digest)):
                fail('HANDOFF_FIXED_PARENT_PATH_SET_CHANGED')
            declared_paths[path] = digest
    if roots != {str(Path(path).parent) for path in GENERATED}:
        fail('HANDOFF_COMPLETE_INSTALLED_PARENT_CONTRACT_REQUIRED')
    seen = set()
    for row in proof['rows']:
        _row(row, absolute=True)
        path, relative = row['path'], _canonical_relative(row.get('repoPath'))
        if path in seen or path not in declared_paths or row['sha256'] != declared_paths[path]:
            fail('HANDOFF_FIXED_PARENT_PATH_SET_CHANGED')
        if relative in local:
            add(relative, path)
            if (local[relative]['sha256'], local[relative]['bytes']) != (row['sha256'], row['bytes']):
                fail('HANDOFF_FIXED_PARENT_MIRROR_CHANGED')
        else:
            # The old frozen verifier also hashes its installed test payloads.
            # They are not imported or shipped as new runtime code, but every
            # byte is still checked against the exact historical manifest.
            alias = row.get('payloadRoot')
            prefix = source_namespaces.get(alias, '') + '/tests/'
            if (alias not in source_namespaces or not relative.startswith(prefix)
                    or path != alias + '/tests/' + relative[len(prefix):]):
                fail('HANDOFF_FIXED_PARENT_LOCAL_MIRROR_MISSING')
            expected[path] = row
        seen.add(path)
    if seen != declared_paths.keys():
        fail('HANDOFF_COMPLETE_INSTALLED_PARENT_CONTRACT_REQUIRED')
    pending, seen = [RECOVERY + 'rtx-gpu-package-v1/gpu_launcher.py'], set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        add(relative, '/opt/rtx-package/repo/' + relative)
        try:
            tree = ast.parse(data[relative])
        except (SyntaxError, UnicodeError):
            fail('HANDOFF_NATIVE_IMPORT_SOURCE_INVALID')
        for node in ast.walk(tree):
            modules = [x.name for x in node.names] if isinstance(node, ast.Import) else (
                [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            for name in modules:
                if isinstance(node, ast.ImportFrom) and node.level:
                    parts = list(PurePosixPath(relative).parent.parts)
                    for _ in range(node.level - 1):
                        if not parts:
                            fail('HANDOFF_NATIVE_IMPORT_OUTSIDE_REPOSITORY')
                        parts.pop()
                    target = '/'.join(parts + name.split('.')) if name else '/'.join(parts) + '/__init__'
                    pending.append(_canonical_relative(target + '.py'))
                elif name.startswith('deployment.'):
                    pending += [ENGINE + '/' + name.replace('.', '/') + '.py',
                        ENGINE + '/deployment/__init__.py', ENGINE + '/deployment/gcube/__init__.py']
                elif name.startswith('astra_cpu.'):
                    fail('HANDOFF_NATIVE_IMPORT_CLOSURE_NEEDS_REVIEW')
    return expected


@dataclass(frozen=True)
class VerifiedSources:
    repo: Path
    manifest: Path
    expected_sha256: str
    files: dict
    external: dict
    summary: dict


def verify_preimport_sources(manifest, expected_sha256, *, repo=REPO):
    repo, manifest = _path(repo), _path(manifest)
    if not SHA.fullmatch(str(expected_sha256)):
        fail('HANDOFF_SOURCE_MANIFEST_SHA_REQUIRED')
    raw = _read_regular(manifest, 8 * 1024 ** 2)
    if sha(raw) != expected_sha256:
        fail('HANDOFF_SOURCE_MANIFEST_CHANGED')
    value = _json(raw)
    if (not isinstance(value, dict) or value.get('schema') != SCHEMA
            or not isinstance(value.get('files'), list) or not value['files']
            or not isinstance(value.get('externalFiles'), list) or not value['externalFiles']):
        fail('HANDOFF_SOURCE_MANIFEST_SCHEMA')
    local, bodies = {}, {}
    for item in value['files']:
        row = _row(item)
        if row['path'] in local:
            fail('HANDOFF_SOURCE_MANIFEST_DUPLICATE_PATH')
        data = _read_regular(repo / row['path'])
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            fail('HANDOFF_REQUIRED_SOURCE_CHANGED')
        local[row['path']], bodies[row['path']] = row, data
    if not set(REQUIRED) <= local.keys():
        fail('HANDOFF_CONNECTED_ENTRYPOINT_SOURCE_REQUIRED')
    expected_external = _expected_external(local, bodies)
    external = {}
    for item in value['externalFiles']:
        row = _row(item, absolute=True)
        if row['path'] in external or row['path'] not in expected_external:
            fail('HANDOFF_FIXED_PARENT_PATH_SET_CHANGED')
        mirror = expected_external[row['path']]
        if (row['sha256'], row['bytes']) != (mirror['sha256'], mirror['bytes']):
            fail('HANDOFF_FIXED_PARENT_MIRROR_CHANGED')
        data = _read_regular(Path(row['path']))
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            fail('HANDOFF_INSTALLED_PARENT_CHANGED')
        external[row['path']] = row
    if external.keys() != expected_external.keys():
        fail('HANDOFF_COMPLETE_INSTALLED_PARENT_CONTRACT_REQUIRED')
    conditional = value.get('conditionalExternalFiles')
    if (not isinstance(conditional, list)
            or value.get('conditionalExternalPolicy') != 'VERIFY_EXACT_BYTES_IF_PRESENT_ELSE_ORIGINAL_PINNED_NEW_REPO_FALLBACK'):
        fail('HANDOFF_CONDITIONAL_PARENT_POLICY_REQUIRED')
    checked = set()
    for item in conditional:
        row = _row(item, absolute=True)
        path = row['path']
        if path in checked or path not in CONDITIONAL or CONDITIONAL[path] not in local:
            fail('HANDOFF_CONDITIONAL_PARENT_PATH_SET_CHANGED')
        mirror = local[CONDITIONAL[path]]
        if (row['sha256'], row['bytes']) != (mirror['sha256'], mirror['bytes']):
            fail('HANDOFF_CONDITIONAL_PARENT_MIRROR_CHANGED')
        target = Path(path)
        if target.exists() or target.is_symlink():
            data = _read_regular(target)
            if len(data) != row['bytes'] or sha(data) != row['sha256']:
                fail('HANDOFF_CONDITIONAL_PARENT_CHANGED')
        checked.add(path)
    if checked != CONDITIONAL.keys():
        fail('HANDOFF_COMPLETE_CONDITIONAL_PARENT_CONTRACT_REQUIRED')
    return VerifiedSources(repo, manifest, expected_sha256, local, external,
        {'newSourceFilesVerified': len(local), 'mandatoryInstalledFilesVerified': len(external),
         'conditionalInstalledPathsChecked': len(checked), 'generatedManifestHashesVerified': len(GENERATED),
         'sourceManifestSHA256': expected_sha256, 'gpuExecuted': False})


def _private(path, *, directory=False, uid=1000, gid=1000):
    path = _path(path)
    try:
        info = path.lstat()
    except OSError:
        fail('HANDOFF_EXISTING_PRIVATE_STATE_REQUIRED')
    if ((not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or info.st_uid != uid or info.st_gid != gid or stat.S_IMODE(info.st_mode) & 0o077
            or (not directory and info.st_nlink != 1)):
        fail('HANDOFF_EXISTING_OWNED_PRIVATE_STATE_REQUIRED')
    return path


def configuration(environ, *, export_root, host='0.0.0.0', uid=None, gid=None):
    uid, gid = os.getuid() if uid is None else uid, os.getgid() if gid is None else gid
    if uid != 1000 or gid != 1000:
        fail('STUDIO_ENGINE_UID_GID_1000_REQUIRED')
    if environ.get('GPU_BACKEND') != 'vulkan':
        fail('HANDOFF_EXPLICIT_VULKAN_PROFILE_REQUIRED')
    if host not in {'0.0.0.0', '127.0.0.1'}:
        fail('HANDOFF_SERVICE_BIND_HOST_INVALID')
    root_text = environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT')
    if not isinstance(root_text, str) or not root_text:
        fail('HANDOFF_EXISTING_STATE_ROOT_REQUIRED')
    root = _private(root_text, directory=True)
    if root == Path('/world-storage') or root.is_relative_to('/world-storage'):
        fail('STUDIO_PRIVATE_LOCAL_STATE_REQUIRED')
    owner = _private(root / 'owner-code')
    production = _private(root / 'production', directory=True)
    policy = production / 'operator_policy.json'
    if policy.exists() or policy.is_symlink():
        _private(policy)
    exports = _path(export_root)
    if not exports.is_dir() or exports.resolve().is_relative_to(root.resolve()) or root.resolve().is_relative_to(exports.resolve()):
        fail('HANDOFF_PRIVATE_PUBLIC_ROOTS_MUST_BE_DISJOINT')
    port = environ.get('WORLD_ENGINE_STUDIO_PORT', '8080')
    if not isinstance(port, str) or not re.fullmatch(r'[1-9][0-9]{3,4}', port) or not 1024 <= int(port) <= 65535 or int(port) == 8000:
        fail('STUDIO_DISTINCT_PORT_REQUIRED')
    digest = environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST')
    if digest is not None and not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        fail('STUDIO_IMAGE_DIGEST_REQUIRED')
    error = environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR')
    if error is not None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', error):
        fail('STUDIO_CONFIGURATION_INVALID')
    # Never read or copy OWNER_CODE/OPERATOR_POLICY_JSON environment values.
    # Existing private files remain the only authority; missing policy blocks
    # production but does not fabricate a replacement or crash HTTPS setup.
    if error is None and not policy.exists():
        error = 'STUDIO_OPERATOR_POLICY_REQUIRED'
    origin = environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN') or None
    return {'state_root': root, 'owner_file': owner, 'export_root': exports,
            'image_digest': digest, 'port': int(port), 'host': host,
            'initial_origin': origin, 'configuration_error': error,
            'environmentPresence': {name: name in environ for name in ENV_NAMES}}


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def application(contract, config):
    """Call only after full local/fixed-parent verification; no listener here."""
    if not isinstance(contract, VerifiedSources):
        fail('HANDOFF_PREIMPORT_SOURCE_VERIFICATION_REQUIRED')
    if Path(__file__).resolve() != contract.repo / (NAMESPACE + 'controller/serve.py'):
        fail('HANDOFF_DEPLOYED_REPOSITORY_LOCATION_CHANGED')
    controller_dir = contract.repo / (NAMESPACE + 'controller')
    for name, filename in [('common', 'common.py'), ('nvidia_backend', 'nvidia_backend.py')]:
        cached = sys.modules.get(name)
        if cached is not None and Path(getattr(cached, '__file__', '')) != controller_dir / filename:
            fail('HANDOFF_NEW_CONTROLLER_MODULE_ORIGIN_CHANGED')
    common = _load('common', controller_dir / 'common.py')
    common.verify_manifest(contract.manifest, contract.expected_sha256,
                           repo=contract.repo, require_external=True)
    # Fixed imports in the frozen proxy are allowed only at these already
    # verified locations. Refuse a cached same-name module from any other path.
    aliases = {'parent': '/opt/world-engine-studio-https-proxy-fix/parent.py',
        'proxy_policy': '/opt/world-engine-studio-https-proxy-fix/proxy_policy.py',
        'frozen': '/opt/world-engine-studio-https-bootstrap/frozen.py',
        'setup_core': '/opt/world-engine-studio-https-bootstrap/setup_core.py'}
    for name, expected in aliases.items():
        cached = sys.modules.get(name)
        if cached is not None and Path(getattr(cached, '__file__', '')) != Path(expected):
            fail('HANDOFF_FROZEN_MODULE_ORIGIN_CHANGED')
    for directory in ['/opt/world-engine-studio-https-bootstrap', '/opt/world-engine-studio-https-proxy-fix']:
        if directory not in sys.path:
            sys.path.insert(0, directory)
    proxy = _load('_handoff_verified_existing_proxy', Path('/opt/world-engine-studio-https-proxy-fix/proxy_server.py'))
    # Run the existing complete manifest chain, including its frozen generated
    # file inventories. We do not replace that check with the new source list.
    verifier = _load('_handoff_verified_proxy_manifest', Path('/opt/world-engine-studio-https-proxy-fix/manifest.py'))
    verifier.verify_sources()
    if str(controller_dir) not in sys.path:
        sys.path.insert(0, str(controller_dir))
    controller = _load('_handoff_verified_nvidia_controller', controller_dir / 'nvidia_controller.py')
    mobile = _load('_handoff_verified_mobile_handler', contract.repo / (NAMESPACE + 'mobile/handler.py'))
    def factory(**kwargs):
        return controller.NvidiaPresentationController(**kwargs,
            source_manifest=contract.manifest, expected_manifest_sha256=contract.expected_sha256)
    class NvidiaApplication(proxy.Application):
        def handler(self):
            return mobile.wrap_handler(super().handler(),
                example_file=contract.repo / (RECOVERY + 'universal-presentation-v2/examples/AVIATION_EUROPE_NL.json'),
                expected_example_sha256='91c244b48cdbc9465d5ee1e38683fde8fe3888b101d1ea255c4a85ba28fc973e')
    app = NvidiaApplication(config['state_root'], config['owner_file'], config['export_root'],
        config['image_digest'], config['port'], controller_factory=factory,
        initial_origin=config['initial_origin'], configuration_error=config['configuration_error'])
    return app, proxy.original.StudioHTTPServer


def _process_start(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[19]
    except FileNotFoundError:
        return None
    except (OSError, IndexError):
        fail('HANDOFF_PROCESS_STATE_UNVERIFIED')


def _listening(port):
    seen = False
    for file in (Path('/proc/net/tcp'), Path('/proc/net/tcp6')):
        try:
            rows = file.read_text().splitlines()[1:]
        except FileNotFoundError:
            continue
        except OSError:
            fail('HANDOFF_PORT_STATE_UNVERIFIED')
        seen = True
        for line in rows:
            fields = line.split()
            if len(fields) >= 4 and fields[3] == '0A' and int(fields[1].rsplit(':', 1)[1], 16) == port:
                return True
    if not seen:
        fail('HANDOFF_PORT_STATE_UNVERIFIED')
    return False


def controlled_activation(file, expected_sha256, contract, config):
    """Validate a separately verified operator plan; never manufacture one.

    This is deliberately unavailable for PID1/unknown-supervisor deployments.
    A boolean assertion alone is not accepted as evidence of exclusive use.
    """
    if file is None or not SHA.fullmatch(str(expected_sha256)):
        fail('HANDOFF_CONTROLLED_ACTIVATION_REQUIRED')
    path = _private(file)
    raw = _read_regular(path, 64 * 1024)
    if sha(raw) != expected_sha256:
        fail('HANDOFF_ACTIVATION_PLAN_CHANGED')
    plan = _json(raw)
    if (not isinstance(plan, dict) or plan.get('schema') != 'WORLD_ENGINE_CONTROLLED_SINGLE_STUDIO_PLAN_V1'
            or plan.get('sourceManifestSHA256') != contract.expected_sha256
            or plan.get('stateRoot') != str(config['state_root']) or plan.get('servicePort') != config['port']
            or plan.get('operatorConsent') != 'CONTROLLED_SINGLE_STUDIO_TRANSITION'
            or plan.get('status') != 'EXTERNALLY_VERIFIED_PLAN'):
        fail('HANDOFF_CONTROLLED_ACTIVATION_REQUIRED')
    # Both exact process identities and their pinned scripts must be known.
    # If either supervised process is PID1, or still the same live instance,
    # this entry cannot safely replace it and must not bind another port.
    for name in ('priorStudio', 'priorSupervisor'):
        identity = plan.get(name)
        if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or identity['pid'] <= 1
                or not re.fullmatch(r'[0-9]+', str(identity.get('startTicks')))
                or identity.get('scriptPath') not in contract.external
                or identity.get('scriptSHA256') != contract.external[identity['scriptPath']]['sha256']):
            fail('HANDOFF_CONTROLLED_ACTIVATION_REQUIRED')
        if _process_start(identity['pid']) == str(identity['startTicks']):
            fail('HANDOFF_PRIOR_STUDIO_OR_SUPERVISOR_STILL_ACTIVE')
    # The known prior Studio default must also be clear when a selected port
    # differs; another port is never an escape from an active original server.
    if any(_listening(port) for port in sorted({8080, config['port']})):
        fail('HANDOFF_SERVICE_PORT_ALREADY_IN_USE')
    return {'declaredControlledPlanValidated': True,
            'automaticSupervisorBehaviorProvenByThisCode': False,
            'providerDeploymentOrBillingStopControlled': False}


class ClosedArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        # Never echo an accidentally supplied credential as an unknown argument.
        fail('HANDOFF_CLI_ARGUMENTS_INVALID')


def main(argv=None):
    parser = ClosedArgumentParser()
    parser.add_argument('--source-manifest', required=True, type=Path)
    parser.add_argument('--source-manifest-sha256', required=True)
    parser.add_argument('--export-root', required=True, type=Path)
    parser.add_argument('--host', default='0.0.0.0', choices=['0.0.0.0', '127.0.0.1'])
    parser.add_argument('--activation-plan', type=Path)
    parser.add_argument('--activation-plan-sha256')
    parser.add_argument('--check-only', action='store_true')
    try:
        args = parser.parse_args(argv)
        if not sys.flags.isolated:
            fail('HANDOFF_ISOLATED_PYTHON_REQUIRED')
        contract = verify_preimport_sources(args.source_manifest, args.source_manifest_sha256)
        config = configuration(os.environ, export_root=args.export_root, host=args.host)
        if args.check_only or args.activation_plan is None:
            print(json.dumps({'stage': 'HANDOFF_SOURCE_AND_PRIVATE_CONFIG_CHECKED',
                'mode': 'CHECK_ONLY', 'source': contract.summary,
                'environmentPresence': config['environmentPresence'],
                'activation': 'NEEDS_INPUT_CONTROLLED_SINGLE_STUDIO_PLAN',
                'renderAllowed': False, 'gpuRenderingVerified': False, 'listenerStarted': False}))
            return 0
        activation = controlled_activation(args.activation_plan, args.activation_plan_sha256, contract, config)
        app, server_type = application(contract, config)
        try:
            server = server_type((config['host'], config['port']), app.handler())
        except OSError:
            fail('HANDOFF_SERVICE_PORT_UNAVAILABLE_NO_TAKEOVER')
        print(json.dumps({'stage': 'HANDOFF_STUDIO_WEB_STARTED', 'mode': 'CONFIGURED' if app.normal else 'SETUP',
            'environmentPresence': config['environmentPresence'], 'activation': activation,
            'renderAllowed': False, 'gpuRenderingVerified': False, 'listenerStarted': True}), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,119}', code):
            code = 'HANDOFF_STUDIO_START_BLOCKED'
        print(json.dumps({'status': 'BLOCKED', 'stage': 'HANDOFF_SOURCE_CONFIG_OR_ACTIVATION',
            'errorCode': code, 'renderAllowed': False, 'gpuRenderingVerified': False,
            'listenerStarted': False}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
