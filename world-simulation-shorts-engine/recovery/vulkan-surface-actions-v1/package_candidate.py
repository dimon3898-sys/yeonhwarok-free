"""Prepare/verify a four-file surface-option overlay; no browser or GPU calls.

Production pins are fixed. The private _stage pins seam exists only for the new
synthetic packaging tests and is deliberately unavailable from the CLI.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import stat

REPO_ROOT = Path('/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo')
SOURCE_COMMIT = 'd259e61c96e83a97a8b97e797670786a434a240d'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
PARENT = IMAGE + '@' + PARENT_DIGEST
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
PROFILE = HANDOFF + 'backend/profile_contract.mjs'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
GENERATED = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
OVERLAY_FILES = frozenset({PROFILE, RUNTIME, BOOTSTRAP, STARTUP})
OLD_FRAGMENT = "'--use-angle=vulkan','--enable-features='+features.join(','),'--disable-vulkan-surface',"
NEW_FRAGMENT = "'--use-angle=vulkan','--enable-features='+features.join(','),"
FROZEN_STARTUP_IMAGE = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
PRODUCTION_PINS = {
    'runtime': 'a4ef7cdca49e64881f737d4c88d949dafa502868fa6a1df7d392170e0170f314',
    'startup': '3cac42a8da8fd76994b20035666e3f15c94779073deb0d0d4ae515a0b2da8407',
    'oldProfile': '92a05474a162ffd41238abc24cc5e433838c80192d77f462f67990178fc08809',
    'newProfile': 'f55758af58a7c8724bddc097f05586b6d4cfdfa81133fa093636e335bca171c5',
    'oldBytes': 10696,
    'newBytes': 10669,
    'generated': '2fc89c792de8ebb49eae00241bf5cc10acd78c80934dbc1ada21c9d62d21438e',
    'startupImage': FROZEN_STARTUP_IMAGE,
}
MAX_SOURCE_BYTES = 8 * 1024 * 1024


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'SURFACE_ABSOLUTE_PATH_REQUIRED')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'SURFACE_SYMLINK_FORBIDDEN')
    return path


def read_file(path):
    path = safe_path(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_SOURCE_BYTES,
            'SURFACE_REGULAR_BOUNDED_FILE_REQUIRED')
    raw = path.read_bytes()
    require(len(raw) == info.st_size and len(raw) <= MAX_SOURCE_BYTES,
            'SURFACE_SOURCE_CHANGED_DURING_READ')
    return raw


def read_json(path):
    value = json.loads(read_file(path))
    require(isinstance(value, dict), 'SURFACE_JSON_OBJECT_REQUIRED')
    return value


def rows_by_path(value):
    rows = value.get('files')
    require(isinstance(rows, list) and len(rows) == 353, 'SURFACE_353_FILE_CONTRACT_REQUIRED')
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'path', 'sha256', 'bytes'},
                'SURFACE_RUNTIME_ROW_INVALID')
        name = row.get('path')
        require(isinstance(name, str) and name.startswith('world-simulation-shorts-engine/')
                and not Path(name).is_absolute() and '..' not in Path(name).parts
                and re.fullmatch('[a-f0-9]{64}', str(row.get('sha256')))
                and type(row.get('bytes')) is int and row['bytes'] >= 0,
                'SURFACE_RUNTIME_ROW_INVALID')
    result = {row['path']: row for row in rows}
    require(len(result) == 353, 'SURFACE_DUPLICATE_RUNTIME_PATH')
    require(PROFILE in result and GENERATED in result, 'SURFACE_REQUIRED_RUNTIME_ROWS_MISSING')
    require(not OVERLAY_FILES.intersection(result).difference({PROFILE}),
            'SURFACE_STARTUP_MANIFEST_HASH_CYCLE_FORBIDDEN')
    return result


def expected_entrypoint(runtime_sha, startup_sha):
    return ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B',
            str(REPO_ROOT / BOOTSTRAP), '--startup-manifest', str(REPO_ROOT / STARTUP),
            '--startup-manifest-sha256', startup_sha, '--source-manifest', str(REPO_ROOT / RUNTIME),
            '--source-manifest-sha256', runtime_sha, '--export-root', '/world-storage']


def expected_dockerfile(entrypoint):
    # Copy files individually so directory modes remain inherited from parent.
    result = 'FROM ' + PARENT + '\n'
    for name in sorted(OVERLAY_FILES):
        result += ('COPY --chown=0:0 --chmod=0644 '
                   + json.dumps(['overlay/' + name, str(REPO_ROOT / name)]) + '\n')
    return result + 'ENTRYPOINT ' + json.dumps(entrypoint) + '\n'


def _stage(parent_root, candidate_file, dest_context, image_config, *, pins):
    parent, candidate, context = map(safe_path, (parent_root, candidate_file, dest_context))
    require(parent.is_dir() and not context.exists(), 'SURFACE_FRESH_CONTEXT_REQUIRED')
    require(not context.is_relative_to(parent) and not parent.is_relative_to(context),
            'SURFACE_CONTEXT_MUST_BE_SEPARATE')
    runtime_raw = read_file(parent / RUNTIME)
    startup_raw = read_file(parent / STARTUP)
    require(digest(runtime_raw) == pins['runtime'], 'SURFACE_PARENT_RUNTIME_PIN_MISMATCH')
    require(digest(startup_raw) == pins['startup'], 'SURFACE_PARENT_STARTUP_PIN_MISMATCH')
    runtime, startup = json.loads(runtime_raw), json.loads(startup_raw)
    require(runtime.get('schema') == 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1',
            'SURFACE_RUNTIME_SCHEMA_INVALID')
    rows = rows_by_path(runtime)
    require(startup.get('schema') == 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2'
            and startup.get('runtimeManifestSHA256') == pins['runtime']
            and startup.get('baseImageDigest') == pins['startupImage']
            and set(startup.get('files', {})) == {'bootstrap.py', 'worker.py'},
            'SURFACE_PARENT_STARTUP_CONTRACT_MISMATCH')
    require(isinstance(image_config, dict)
            and image_config.get('Entrypoint') == expected_entrypoint(pins['runtime'], pins['startup'])
            and image_config.get('Cmd') is None
            and image_config.get('User') in ('0', 'root', '0:0', ''),
            'SURFACE_PARENT_IMAGE_CONFIG_MISMATCH')
    profile = read_file(parent / PROFILE)
    changed = read_file(candidate)
    require(digest(profile) == pins['oldProfile'] and len(profile) == pins['oldBytes']
            and rows[PROFILE] == {'path': PROFILE, 'sha256': pins['oldProfile'], 'bytes': pins['oldBytes']},
            'SURFACE_PARENT_PROFILE_PIN_MISMATCH')
    require(digest(changed) == pins['newProfile'] and len(changed) == pins['newBytes'],
            'SURFACE_CANDIDATE_PROFILE_PIN_MISMATCH')
    old_text, new_text = profile.decode(), changed.decode()
    require(old_text.count(OLD_FRAGMENT) == 1
            and new_text == old_text.replace(OLD_FRAGMENT, NEW_FRAGMENT, 1),
            'SURFACE_UNAPPROVED_PROFILE_DELTA')
    require(rows[GENERATED]['sha256'] == pins['generated'],
            'SURFACE_PARENT_GENERATED_ROW_MISMATCH')
    bootstrap = read_file(parent / BOOTSTRAP)
    bootstrap_row = startup['files']['bootstrap.py']
    require(bootstrap_row == {'bytes': len(bootstrap), 'sha256': digest(bootstrap)},
            'SURFACE_PARENT_BOOTSTRAP_PIN_MISMATCH')
    needle = "SOURCE_SHA = '" + pins['runtime'] + "'"
    require(bootstrap.decode().count(needle) == 1, 'SURFACE_BOOTSTRAP_SOURCE_PIN_AMBIGUOUS')
    updated_runtime = copy.deepcopy(runtime)
    updated_rows = rows_by_path(updated_runtime)
    updated_rows[PROFILE].update(bytes=len(changed), sha256=digest(changed))
    runtime_new = wire(updated_runtime)
    runtime_sha = digest(runtime_new)
    bootstrap_new = bootstrap.decode().replace(needle, "SOURCE_SHA = '" + runtime_sha + "'", 1).encode()
    updated_startup = copy.deepcopy(startup)
    updated_startup['runtimeManifestSHA256'] = runtime_sha
    updated_startup['files']['bootstrap.py'] = {'bytes': len(bootstrap_new), 'sha256': digest(bootstrap_new)}
    startup_new = wire(updated_startup)
    startup_sha = digest(startup_new)
    unchanged_rows = [row for row in runtime['files'] if row['path'] != PROFILE]
    require(unchanged_rows == [row for row in updated_runtime['files'] if row['path'] != PROFILE],
            'SURFACE_UNRELATED_RUNTIME_ROW_CHANGED')
    require(updated_startup['baseImageDigest'] == startup['baseImageDigest']
            and updated_startup['files']['worker.py'] == startup['files']['worker.py'],
            'SURFACE_FROZEN_STARTUP_IDENTITY_CHANGED')
    replacements = {PROFILE: changed, RUNTIME: runtime_new, BOOTSTRAP: bootstrap_new, STARTUP: startup_new}
    context.mkdir(parents=False, mode=0o755)
    context.chmod(0o755)  # Only this fresh output, irrespective of the runner umask.
    for name, raw in replacements.items():
        target = context / 'overlay' / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        target.write_bytes(raw)
        target.chmod(0o644)
    for directory in (context / 'overlay').rglob('*'):
        if directory.is_dir():
            directory.chmod(0o755)
    (context / 'overlay').chmod(0o755)
    entrypoint = expected_entrypoint(runtime_sha, startup_sha)
    # Copy files individually: recursive --chmod=0644 could remove directory
    # traversal permission. All four destination directories already exist in
    # the pinned parent, so no directory metadata needs to be replaced.
    (context / 'Dockerfile').write_text(expected_dockerfile(entrypoint))
    (context / 'Dockerfile').chmod(0o644)
    receipt = {'schema': 'WORLD_ENGINE_SURFACE_OVERLAY_STAGE_V1',
        'status': 'PREPARED_NOT_BUILT', 'sourceCommit': SOURCE_COMMIT,
        'parentImage': PARENT, 'parentImageDigest': PARENT_DIGEST, 'installedRoot': str(REPO_ROOT),
        'sourceFiles': 353, 'changedRuntimeRows': [PROFILE], 'unchangedSourceRows': 352,
        'unchangedRuntimeRowsSHA256': digest(wire(unchanged_rows)),
        'generatedManifestSHA256': pins['generated'],
        'parentRuntimeManifestSHA256': pins['runtime'], 'parentStartupManifestSHA256': pins['startup'],
        'runtimeManifestSHA256': runtime_sha, 'startupManifestSHA256': startup_sha,
        'bootstrapSHA256': digest(bootstrap_new), 'frozenStartupImageDigest': startup['baseImageDigest'],
        'workerRow': startup['files']['worker.py'], 'entrypoint': entrypoint,
        'overlayFiles': {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in replacements.items()},
        'parentPreserved': True, 'browserLaunched': False, 'gpuExecuted': False,
        'priorPassSuitesRerun': False, 'imageBuilt': False, 'imagePublished': False}
    (context / 'STAGE_RECEIPT.json').write_bytes(wire(receipt))
    (context / 'STAGE_RECEIPT.json').chmod(0o644)
    return receipt


def stage(parent_root, candidate_file, dest_context, image_config):
    require(Path(parent_root) == REPO_ROOT, 'SURFACE_INSTALLED_PARENT_ROOT_REQUIRED')
    return _stage(parent_root, candidate_file, dest_context, image_config, pins=PRODUCTION_PINS)


def verify(candidate_root, context_root, parent_config, candidate_config):
    root, context = map(safe_path, (candidate_root, context_root))
    receipt = read_json(context / 'STAGE_RECEIPT.json')
    require(receipt.get('schema') == 'WORLD_ENGINE_SURFACE_OVERLAY_STAGE_V1'
            and receipt.get('parentImageDigest') == PARENT_DIGEST
            and receipt.get('sourceCommit') == SOURCE_COMMIT
            and receipt.get('parentRuntimeManifestSHA256') == PRODUCTION_PINS['runtime']
            and receipt.get('parentStartupManifestSHA256') == PRODUCTION_PINS['startup']
            and set(receipt.get('overlayFiles', {})) == OVERLAY_FILES,
            'SURFACE_STAGE_RECEIPT_INVALID')
    overlay = context / 'overlay'
    actual_names = {str(p.relative_to(overlay)) for p in overlay.rglob('*') if p.is_file()}
    require(actual_names == OVERLAY_FILES and not any(p.is_symlink() for p in overlay.rglob('*')),
            'SURFACE_OVERLAY_SCOPE_CHANGED')
    for name, expected in receipt['overlayFiles'].items():
        raw = read_file(root / name)
        require({'bytes': len(raw), 'sha256': digest(raw)} == expected,
                'SURFACE_CANDIDATE_INSTALLED_OVERLAY_MISMATCH')
    runtime = read_json(root / RUNTIME)
    rows = rows_by_path(runtime)
    require(rows[PROFILE]['sha256'] == PRODUCTION_PINS['newProfile']
            and rows[PROFILE]['bytes'] == PRODUCTION_PINS['newBytes']
            and rows[GENERATED]['sha256'] == PRODUCTION_PINS['generated']
            and digest(read_file(root / RUNTIME)) == receipt['runtimeManifestSHA256'],
            'SURFACE_CANDIDATE_INSTALLED_PROFILE_MISMATCH')
    unchanged_rows = [row for row in runtime['files'] if row['path'] != PROFILE]
    require(digest(wire(unchanged_rows)) == receipt['unchangedRuntimeRowsSHA256'],
            'SURFACE_CANDIDATE_UNRELATED_ROWS_CHANGED')
    startup = read_json(root / STARTUP)
    bootstrap_raw = read_file(root / BOOTSTRAP)
    require(startup['runtimeManifestSHA256'] == receipt['runtimeManifestSHA256']
            and digest(read_file(root / STARTUP)) == receipt['startupManifestSHA256']
            and digest(bootstrap_raw) == receipt['bootstrapSHA256']
            and startup['baseImageDigest'] == FROZEN_STARTUP_IMAGE
            and startup['files']['worker.py'] == receipt['workerRow']
            and startup['files']['bootstrap.py'] == {'bytes': len(bootstrap_raw), 'sha256': digest(bootstrap_raw)}
            and ("SOURCE_SHA = '" + receipt['runtimeManifestSHA256'] + "'") in bootstrap_raw.decode(),
            'SURFACE_CANDIDATE_PIN_CHAIN_INVALID')
    require(candidate_config.get('Entrypoint') == receipt['entrypoint']
            and receipt['entrypoint'] == expected_entrypoint(receipt['runtimeManifestSHA256'], receipt['startupManifestSHA256']),
            'SURFACE_CANDIDATE_ENTRYPOINT_MISMATCH')
    require(read_file(context / 'Dockerfile').decode() == expected_dockerfile(receipt['entrypoint']),
            'SURFACE_DOCKERFILE_SCOPE_CHANGED')
    parent_other = {k: v for k, v in parent_config.items() if k != 'Entrypoint'}
    candidate_other = {k: v for k, v in candidate_config.items() if k != 'Entrypoint'}
    require(parent_other == candidate_other, 'SURFACE_CANDIDATE_UNRELATED_IMAGE_CONFIG_CHANGED')
    return {'schema': 'WORLD_ENGINE_SURFACE_PACKAGING_CONNECTION_VERIFY_V1',
        'status': 'PASS', 'scope': 'NEW_OVERLAY_AND_PIN_CONNECTIONS_ONLY',
        'sourceFiles': 353, 'unchangedSourceRows': 352, 'overlayFilesVerified': 4,
        'runtimeManifestSHA256': receipt['runtimeManifestSHA256'],
        'startupManifestSHA256': receipt['startupManifestSHA256'],
        'entrypointPinsVerified': True, 'parentConfigPreservedExceptEntrypoint': True,
        'browserLaunched': False, 'gpuExecuted': False, 'priorPassSuitesRerun': False,
        'gpuInitialization': 'NOT_RUN_NOT_CLAIMED'}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('stage')
    p.add_argument('--parent-root', type=Path, default=REPO_ROOT)
    p.add_argument('--candidate', '--candidate-file', dest='candidate', type=Path, required=True)
    p.add_argument('--context', '--destination', dest='context', type=Path, required=True)
    p.add_argument('--image-config', type=Path, required=True)
    p = sub.add_parser('verify')
    p.add_argument('--root', type=Path, default=REPO_ROOT)
    p.add_argument('--context', type=Path, required=True)
    p.add_argument('--parent-config', type=Path, required=True)
    p.add_argument('--candidate-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'stage':
        result = stage(args.parent_root, args.candidate, args.context, read_json(args.image_config))
    else:
        result = verify(args.root, args.context, read_json(args.parent_config), read_json(args.candidate_config))
        output = safe_path(args.output)
        require(not output.exists(), 'SURFACE_FRESH_VERIFY_OUTPUT_REQUIRED')
        output.write_bytes(wire(result))
        output.chmod(0o644)
    print(json.dumps({'status': result['status'], 'gpuExecuted': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No original exception/path/config text is disclosed.
        print(json.dumps({'status': 'BLOCKED', 'code': 'SURFACE_PACKAGING_CONTRACT_FAILED', 'gpuExecuted': False}))
        raise SystemExit(1) from None
