"""Stage a pinned label source overlay. No image operation or process launch.

The inherited 333 files are represented by the already verified G2 row metadata;
only the 22 changed/new sources and the three chain files are read and copied.
An actual image build and installed-image verification are separate gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

BASE_COMMIT = '5e4ed42496c45333126c08166571598d9fcf0495'
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
EVIDENCE = REC + 'capture-diagnostics-g2-v1/evidence/ci-40767632198/'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
PARENT = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
PINS = {
    RUNTIME: '1427779c7a52af90f37478de3ba11e1ddb664149f5b13dbd87fb05142be0252e',
    STARTUP: 'f8afb5c2f944dea13f7a990a7c2c8e8c65c9c028bd7228f501aa6feace98ef89',
    EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json': 'a4ef7cdca49e64881f737d4c88d949dafa502868fa6a1df7d392170e0170f314',
    EVIDENCE + 'STARTUP_MANIFEST.json': '3cac42a8da8fd76994b20035666e3f15c94779073deb0d0d4ae515a0b2da8407',
    EVIDENCE + 'image-config.json': '220e86cbcdc516a588a9ad5afa9934a27ca62094670914c1d8343131e7fb2357',
}
LABELS = frozenset(REC + 'universal-presentation-v2/' + name for name in (
    'presentation_labels.mjs', 'presentation_label_layer.mjs'))
MAX_FILE = 1024 * 1024
MAX_CONTEXT = 2 * 1024 * 1024


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'LABEL_PACKAGE_ABSOLUTE_PATH_REQUIRED')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'LABEL_PACKAGE_SYMLINK_FORBIDDEN')
    return path


def read_file(path):
    path = canonical(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_FILE,
            'LABEL_PACKAGE_BOUNDED_REGULAR_FILE_REQUIRED')
    raw = path.read_bytes()
    after = path.stat()
    require(len(raw) == info.st_size and (info.st_ino, info.st_mtime_ns, info.st_size) ==
            (after.st_ino, after.st_mtime_ns, after.st_size), 'LABEL_PACKAGE_FILE_CHANGED')
    return raw


def document(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'LABEL_PACKAGE_DUPLICATE_JSON_KEY')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: require(False, 'LABEL_PACKAGE_NONFINITE_JSON'))
    require(isinstance(value, dict), 'LABEL_PACKAGE_JSON_OBJECT_REQUIRED')
    return value


def rows(value, count):
    require(value.get('schema') == 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1'
            and isinstance(value.get('files'), list) and len(value['files']) == count,
            'LABEL_PACKAGE_SOURCE_COUNT_REQUIRED')
    result = {}
    for row in value['files']:
        require(isinstance(row, dict) and set(row) == {'path', 'sha256', 'bytes'},
                'LABEL_PACKAGE_ROW_INVALID')
        name = row['path']
        require(isinstance(name, str) and name.startswith(('world-simulation-shorts-engine/', 'cinematic-world-map/'))
                and str(PurePosixPath(name)) == name and not PurePosixPath(name).is_absolute()
                and '..' not in PurePosixPath(name).parts and '\\' not in name
                and re.fullmatch('[a-f0-9]{64}', str(row['sha256']))
                and type(row['bytes']) is int and row['bytes'] > 0,
                'LABEL_PACKAGE_ROW_INVALID')
        require(name not in result, 'LABEL_PACKAGE_DUPLICATE_SOURCE_PATH')
        result[name] = row
    require(not {RUNTIME, STARTUP, BOOTSTRAP}.intersection(result), 'LABEL_PACKAGE_HASH_CYCLE_FORBIDDEN')
    return result


def _plan(repo):
    repo = canonical(repo)
    require(repo.is_dir(), 'LABEL_PACKAGE_SOURCE_ROOT_REQUIRED')
    pinned = {}
    for name, expected in PINS.items():
        raw = read_file(repo / name)
        require(sha(raw) == expected, 'LABEL_PACKAGE_PIN_MISMATCH:' + name)
        pinned[name] = raw
    current = rows(document(pinned[RUNTIME]), 355)
    previous = rows(document(pinned[EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json']), 353)
    require(set(previous) <= set(current) and set(current) - set(previous) == LABELS,
            'LABEL_PACKAGE_EXACT_TWO_LABEL_MODULES_REQUIRED')
    delta = {name: row for name, row in current.items() if row != previous.get(name)}
    require(len(delta) == 22, 'LABEL_PACKAGE_OVERLAY_SCOPE_CHANGED')
    inherited = [row for name, row in current.items() if name not in delta]
    require(len(inherited) == 333, 'LABEL_PACKAGE_INHERITED_COUNT_CHANGED')
    startup = document(pinned[STARTUP])
    old_startup = document(pinned[EVIDENCE + 'STARTUP_MANIFEST.json'])
    require(startup.get('schema') == old_startup.get('schema') == 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2'
            and set(startup) == set(old_startup) == {'schema', 'baseImageDigest', 'runtimeManifestSHA256', 'files'}
            and startup['baseImageDigest'] == old_startup['baseImageDigest']
            and set(startup.get('files', {})) == {'bootstrap.py', 'worker.py'}
            and startup['files']['worker.py'] == old_startup['files']['worker.py']
            and startup['runtimeManifestSHA256'] == PINS[RUNTIME]
            and old_startup['runtimeManifestSHA256'] == PINS[EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json'],
            'LABEL_PACKAGE_STARTUP_CHAIN_INVALID')
    bootstrap = read_file(repo / BOOTSTRAP)
    require(startup['files']['bootstrap.py'] == {'sha256': sha(bootstrap), 'bytes': len(bootstrap)},
            'LABEL_PACKAGE_BOOTSTRAP_ROW_INVALID')
    require(re.findall(rb"(?m)^SOURCE_SHA = '([a-f0-9]{64})'$", bootstrap) == [PINS[RUNTIME].encode()],
            'LABEL_PACKAGE_BOOTSTRAP_SOURCE_PIN_INVALID')
    config = document(pinned[EVIDENCE + 'image-config.json'])
    old_entry = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B',
                 IMAGE_ROOT + '/' + BOOTSTRAP, '--startup-manifest', IMAGE_ROOT + '/' + STARTUP,
                 '--startup-manifest-sha256', PINS[EVIDENCE + 'STARTUP_MANIFEST.json'],
                 '--source-manifest', IMAGE_ROOT + '/' + RUNTIME, '--source-manifest-sha256',
                 PINS[EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json'], '--export-root', '/world-storage']
    require(config.get('Entrypoint') == old_entry and config.get('Cmd') is None
            and config.get('User') == '0', 'LABEL_PACKAGE_PARENT_ENTRYPOINT_INVALID')
    entry = [PINS[STARTUP] if part == PINS[EVIDENCE + 'STARTUP_MANIFEST.json'] else
             PINS[RUNTIME] if part == PINS[EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json'] else part
             for part in old_entry]
    overlay = {RUNTIME: pinned[RUNTIME], STARTUP: pinned[STARTUP], BOOTSTRAP: bootstrap}
    for name, row in delta.items():
        raw = read_file(repo / name)
        require(sha(raw) == row['sha256'] and len(raw) == row['bytes'],
                'LABEL_PACKAGE_OVERLAY_SOURCE_MISMATCH:' + name)
        overlay[name] = raw
    require(sum(map(len, overlay.values())) < MAX_CONTEXT, 'LABEL_PACKAGE_CONTEXT_TOO_LARGE')
    dockerfile = 'FROM ' + PARENT + '\n'
    for name in sorted(overlay):
        dockerfile += ('COPY --chown=0:0 --chmod=0644 ' +
                       json.dumps(['overlay/' + name, IMAGE_ROOT + '/' + name]) + '\n')
    dockerfile += 'ENTRYPOINT ' + json.dumps(entry) + '\n'
    report = {'schema': 'WORLD_ENGINE_LABEL_SOURCE_CONTEXT_V1', 'status': 'PASS',
              'scope': 'SOURCE_CONTEXT_AND_DECLARED_OCI_ENTRYPOINT_ONLY_NOT_IMAGE_VALIDATION',
              'baseCommit': BASE_COMMIT, 'parentImage': PARENT, 'runtimeSourceRows': 355,
              'changedExistingRows': 20, 'newLabelRows': 2, 'inheritedRowsReused': 333,
              'inheritedSourceFilesRead': 0, 'overlayFiles': len(overlay),
              'runtimeManifestSHA256': PINS[RUNTIME], 'startupManifestSHA256': PINS[STARTUP],
              'entrypoint': entry, 'entrypointChangedIndices': [10, 14],
              'dockerfileSHA256': sha(dockerfile.encode()),
              'overlay': [{'path': name, 'sha256': sha(raw), 'bytes': len(raw)}
                          for name, raw in sorted(overlay.items())],
              'inheritedRowsBindingSHA256': sha(json.dumps(inherited, sort_keys=True, separators=(',', ':')).encode()),
              'historicalParentImageEvidenceReused': True, 'actualParentImageInspected': False,
              'actualCandidateImageBuilt': False, 'actualCandidateOCIConfigVerified': False,
              'existingPASSSuitesRerun': False, 'gpuExecuted': False}
    return report, overlay, dockerfile.encode()


def plan(repo):
    return _plan(repo)[0]


def prepare(repo, context):
    repo, context = canonical(repo), canonical(context)
    require(not context.exists(), 'LABEL_PACKAGE_FRESH_CONTEXT_REQUIRED')
    require(not context.is_relative_to(repo) and not repo.is_relative_to(context),
            'LABEL_PACKAGE_SEPARATE_CONTEXT_REQUIRED')
    report, overlay, dockerfile = _plan(repo)
    context.mkdir(mode=0o755)
    context.chmod(0o755)
    for name, raw in {**{'overlay/' + n: b for n, b in overlay.items()}, 'Dockerfile': dockerfile}.items():
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o644)
    for directory in context.rglob('*'):
        if directory.is_dir():
            directory.chmod(0o755)
    return report


def verify(repo, context):
    context = canonical(context)
    require(context.is_dir(), 'LABEL_PACKAGE_CONTEXT_REQUIRED')
    report, overlay, dockerfile = _plan(repo)
    expected = {'overlay/' + name: raw for name, raw in overlay.items()}
    expected['Dockerfile'] = dockerfile
    actual = set()
    require(stat.S_IMODE(context.stat().st_mode) == 0o755, 'LABEL_PACKAGE_DIRECTORY_MODE_INVALID')
    for node in context.rglob('*'):
        require(not node.is_symlink(), 'LABEL_PACKAGE_SYMLINK_FORBIDDEN')
        if node.is_dir():
            require(stat.S_IMODE(node.stat().st_mode) == 0o755, 'LABEL_PACKAGE_DIRECTORY_MODE_INVALID')
        else:
            name = node.relative_to(context).as_posix()
            require(name in expected, 'LABEL_PACKAGE_UNEXPECTED_CONTEXT_FILE')
            require(stat.S_IMODE(node.stat().st_mode) == 0o644, 'LABEL_PACKAGE_FILE_MODE_INVALID')
            require(read_file(node) == expected[name], 'LABEL_PACKAGE_CONTEXT_FILE_MISMATCH:' + name)
            actual.add(name)
    require(actual == set(expected), 'LABEL_PACKAGE_CONTEXT_FILE_SET_MISMATCH')
    return {**report, 'contextReadback': 'PASS', 'contextFilesVerified': len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('plan', 'prepare', 'verify'))
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--context', type=Path)
    args = parser.parse_args()
    require(args.operation == 'plan' or args.context is not None, 'LABEL_PACKAGE_CONTEXT_ARGUMENT_REQUIRED')
    result = plan(args.repo) if args.operation == 'plan' else globals()[args.operation](args.repo, args.context)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
