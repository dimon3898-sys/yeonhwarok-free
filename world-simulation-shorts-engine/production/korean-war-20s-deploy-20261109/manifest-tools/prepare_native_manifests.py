"""Assemble source pins over the exact published v16 image, without running it.

Inputs are explicit immutable source directories. Outputs contain no host paths,
private registry, pixels, credentials, or assertion of NVIDIA visual approval.
The separately verified build gate owns CPU/private-package qualification.
"""
from pathlib import Path, PurePosixPath
import argparse
import copy
import hashlib
import json
import re

IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT = IMAGE + '@sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b'
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
RECOVERY = 'world-simulation-shorts-engine/recovery/'
HANDOFF = RECOVERY + 'codex-to-gcube-handoff-v1/'
OFFICIAL = RECOVERY + 'official-candidate-v1/'
COLD = RECOVERY + 'studio-cold-start-v2/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
GENERATED = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
BOOTSTRAP = COLD + 'bootstrap.py'
STARTUP = COLD + 'STARTUP_MANIFEST.json'
WORKER = HANDOFF + 'controller/nvidia_worker.py'
BASE_RUNTIME = '659654d1cdb3b1a004e80b4fd67baa7d1b2a750abec4b66fce141dae0d2f7fa5'
BASE_STARTUP = '08f6bd6ac10d69d9f2ac31f8cacd87673f18319eba314e741195bb8878b217f6'
BASE_BOOTSTRAP = 'e75475e943f47759279463d2df083a934ca1a4bc66af0b9de338e5fab93b3ded'
EXPECTED = {
    OFFICIAL + 'presentation_runtime.mjs': 'c766de85267f7ae30e3b76af9fef4168a786baafa93c03bdbdc39da476e4cf49',
    OFFICIAL + 'presentation_plan.mjs': '3f2442ea576b015679b57adbc42da4432c4afa423b4678ae067f76e85ad1adc7',
    OFFICIAL + 'presentation_runtime_nvidia.generated.mjs': '0c24611b921d602fa3c09ad8ab238c4b6f905355917d5fd1c13383f46885cd8c',
    HANDOFF + 'capture_vulkan.generated.mjs': 'd2f000675bc75f4bfbf27df8c0c744e1fecd96440e8eb71ab31046e704db7f4c',
    HANDOFF + 'presentation_runtime_vulkan.generated.mjs': 'a5e5e6c58c6eefd221c22573d1d52383cd95984c2c01794a042c6811557434b7',
    HANDOFF + 'backend/capture_nvidia.mjs': '768b6b352b0ccf72b5c7dd701c4d07b6a2249b12a7d02cb155960b0d035e2ce9',
}
LABEL_SHA = '6153c5a1e06f2c0e83ba4ef9e73ad623149a5e8b704ade03fb13996827fdcdf0'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def need(value, code):
    if not value:
        raise ValueError(code)


def pin(path, raw):
    return {'path': path, 'bytes': len(raw), 'sha256': sha(raw)}


def read_pinned(path, expected):
    raw = path.read_bytes()
    need(sha(raw) == expected, 'SOURCE_PIN_MISMATCH:' + path.name)
    return raw


def safe_relative(name):
    p = PurePosixPath(name)
    need(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'UNSAFE_RELATIVE_PATH')


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o644)


def prepare(args):
    base, source, deps = args.v16_overlay, args.native_overlay, args.dependency_repository
    need(not args.output.exists(), 'FRESH_OUTPUT_REQUIRED')
    runtime_raw = read_pinned(base / RUNTIME, BASE_RUNTIME)
    runtime = json.loads(runtime_raw)
    baseline = {r['path']: copy.deepcopy(r) for r in runtime['files']}
    need(len(baseline) == len(runtime['files']) == 361, 'EXACT_V16_INTERNAL_ROWS')
    base_startup_raw = read_pinned(base / STARTUP, BASE_STARTUP)
    startup = json.loads(base_startup_raw)
    bootstrap = read_pinned(base / BOOTSTRAP, BASE_BOOTSTRAP)
    overlay = {}
    for file in source.rglob('*'):
        if file.is_file():
            need(not file.is_symlink(), 'SOURCE_SYMLINK_FORBIDDEN')
            name = file.relative_to(source).as_posix()
            safe_relative(name)
            need(name.startswith(RECOVERY) and name.endswith(('.py', '.mjs', '.json', '.LICENSE')), 'SOURCE_SCOPE')
            need(not name.endswith('CANDIDATE_SOURCE_CREDITS_REFERENCE.json'), 'PRIVATE_SOURCE_FORBIDDEN')
            overlay[name] = file.read_bytes()
    need(len(overlay) == 46, 'EXACT_NATIVE_OVERLAY_FILE_COUNT')
    for name, expected in EXPECTED.items():
        need(sha(overlay[name]) == expected, 'A12_NATIVE_PIN:' + name)
    overlay[OFFICIAL + 'presentation_label_layer.mjs'] = read_pinned(args.label, LABEL_SHA)

    # The v16 publication barrier is preserved byte-for-byte in the native worker.
    old_worker = (base / WORKER).read_bytes()
    marker = b'    # The worker can read initial state before the parent publishes its PID.\n'
    start = old_worker.index(marker)
    stop = old_worker.index(b'    original = lease_helper()\n', start)
    need(old_worker[start:stop] in overlay[WORKER], 'V16_LAUNCH_BARRIER_MUST_SURVIVE')

    # Only dependencies not already exactly supplied by v16 enter the layer.
    dependency_manifest = json.loads(overlay[OFFICIAL + 'OFFICIAL_ENTRY_DEPENDENCIES.json'])
    dependency_rows = dependency_manifest['files']
    need(len(dependency_rows) == 37, 'OFFICIAL_DEPENDENCY_COUNT')
    for row in dependency_rows:
        name = row['path']
        safe_relative(name)
        raw = read_pinned(deps / name, row['sha256'])
        need(len(raw) == row['bytes'], 'DEPENDENCY_BYTES')
        if baseline.get(name) != pin(name, raw):
            need(name not in overlay or overlay[name] == raw, 'DEPENDENCY_COLLISION')
            overlay[name] = raw

    generated_raw = read_pinned(args.parent_generated, baseline[GENERATED]['sha256'])
    generated = json.loads(generated_raw)
    need(len(generated['variants']) == 3, 'EXACT_THREE_LEGACY_VARIANTS')
    changes = []
    for row in generated['variants']:
        need(baseline[row['original']]['sha256'] == row['originalSHA256'], 'FROZEN_ORIGINAL_PIN')
        name = HANDOFF + row['variant']
        if name in overlay:
            changes.append({'variant': row['variant'], 'beforeSHA256': row['variantSHA256'], 'afterSHA256': sha(overlay[name])})
            row['variantSHA256'] = sha(overlay[name])
        else:
            need(baseline[name]['sha256'] == row['variantSHA256'], 'UNCHANGED_VARIANT_PIN')
    need(len(changes) == 2, 'EXACT_TWO_VARIANT_UPDATES')
    overlay[GENERATED] = encoded(generated)

    rows = copy.deepcopy(baseline)
    for name, raw in overlay.items():
        rows[name] = pin(name, raw)
    runtime['files'] = sorted(rows.values(), key=lambda row: row['path'])
    # Metadata does not claim runtime or NVIDIA validation from a hash check.
    runtime['candidateSourceBinding'] = {
        'schema': 'WORLD_ENGINE_NATIVE_CANDIDATE_IMAGE_BINDING_V1',
        'integrationCommit': '5d749200684406ad66a6a381e04d5a31a3ef7b05',
        'visualSourceCommit': args.source_commit,
        'parentRuntimeManifestSHA256': BASE_RUNTIME,
        'nativeRuntimeSHA256': EXPECTED[OFFICIAL + 'presentation_runtime_nvidia.generated.mjs'],
        'gpuExecuted': False,
    }
    runtime_raw = encoded(runtime)
    old_pin = ("SOURCE_SHA = '" + BASE_RUNTIME + "'").encode()
    need(bootstrap.count(old_pin) == 1, 'EXACT_BOOTSTRAP_SOURCE_PIN')
    bootstrap = bootstrap.replace(old_pin, ("SOURCE_SHA = '" + sha(runtime_raw) + "'").encode())
    startup['runtimeManifestSHA256'] = sha(runtime_raw)
    startup['files']['bootstrap.py'] = {'bytes': len(bootstrap), 'sha256': sha(bootstrap)}
    startup_raw = encoded(startup)
    overlay.update({RUNTIME: runtime_raw, BOOTSTRAP: bootstrap, STARTUP: startup_raw})

    entry = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B', ROOT + '/' + BOOTSTRAP,
             '--startup-manifest', ROOT + '/' + STARTUP, '--startup-manifest-sha256', sha(startup_raw),
             '--source-manifest', ROOT + '/' + RUNTIME, '--source-manifest-sha256', sha(runtime_raw),
             '--export-root', '/world-storage']
    context = {
        'schema': 'WORLD_ENGINE_NATIVE_IMAGE_CONTEXT_V1',
        'status': 'PUBLIC_SOURCES_ASSEMBLED_PRIVATE_STARTUP_BINDING_PENDING',
        'parentImage': PARENT, 'entrypoint': entry,
        'runtimeManifestSHA256': sha(runtime_raw), 'startupManifestSHA256': sha(startup_raw),
        'generatedManifestSHA256': sha(overlay[GENERATED]),
        'overlay': [pin(name, raw) for name, raw in sorted(overlay.items())],
        'gpuExecuted': False, 'oldPASSReruns': 0, 'imageBuilt': False,
        'deploymentReady': False, 'privateRegistryIncluded': False,
        'privateAssetInstallationRequired': True,
    }
    installed_rows = copy.deepcopy(rows)
    for name, raw in overlay.items():
        installed_rows[name] = pin(name, raw)
    for name, value in startup['files'].items():
        installed_rows[COLD + name] = {'path': COLD + name, **value}
    source_closure = {
        'schema': 'WORLD_ENGINE_PUBLIC_SOURCE_CLOSURE_V1',
        'status': 'SOURCE_METADATA_CLOSED_INSTALLED_BYTES_PENDING',
        'parentImage': PARENT, 'parentRuntimeManifestSHA256': BASE_RUNTIME,
        'parentStartupManifestSHA256': BASE_STARTUP,
        'runtimeManifestSHA256': sha(runtime_raw), 'startupManifestSHA256': sha(startup_raw),
        'files': sorted(installed_rows.values(), key=lambda row: row['path']),
        'externalFiles': runtime['externalFiles'],
        'conditionalExternalFiles': runtime['conditionalExternalFiles'],
        'conditionalExternalPolicy': runtime['conditionalExternalPolicy'],
        'changes': [dict(pin(name, raw), baselineSHA256=baseline.get(name, {}).get('sha256'))
                    for name, raw in sorted(overlay.items())],
        'variantPinChanges': changes,
        'frozenOriginalPins': [{'path': r['original'], 'sha256': r['originalSHA256']} for r in generated['variants']],
        'sourceRows': len(rows), 'baselineSourceRows': len(baseline),
        'sourceIntegrityOnly': True, 'installedImageValidated': False, 'gpuExecuted': False,
        'privateRegistryVerification': 'SEPARATE_PINNED_PACKAGE_REQUIRED',
    }
    for name, raw in sorted(overlay.items()):
        write(args.output / 'overlay' / name, raw)
    write(args.output / 'Dockerfile', ('FROM ' + PARENT + '\nCOPY --chown=0:0 ' + json.dumps(['overlay/', ROOT + '/']) + '\nENTRYPOINT ' + json.dumps(entry) + '\n').encode())
    write(args.output / 'CONTEXT.json', encoded(context))
    write(args.output / 'PUBLIC_SOURCE_CLOSURE.json', encoded(source_closure))
    return {key: context[key] for key in ['status', 'runtimeManifestSHA256', 'startupManifestSHA256', 'generatedManifestSHA256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('v16-overlay', 'native-overlay', 'dependency-repository', 'parent-generated', 'label', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    need(re.fullmatch('[0-9a-f]{40}', args.source_commit), 'EXACT_SOURCE_COMMIT_REQUIRED')
    print(json.dumps(prepare(args), sort_keys=True))
