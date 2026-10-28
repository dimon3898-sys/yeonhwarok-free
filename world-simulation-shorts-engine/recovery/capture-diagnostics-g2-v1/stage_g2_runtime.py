#!/usr/bin/env python3
"""Stage the G1-proven diagnostic delta on the immutable capture-pin parent.

Run only in the exact digest-pinned parent, with its filesystem read-only.
This is packaging, not a rerun of the parent/G1 tests. The candidate image's
353-file integrity and runtime checks are a separate G2 gate before publication.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil

PARENT_IMAGE_DIGEST = 'sha256:bedf23b0315666ea702f719a509147d6c97dc27f7b529de918e2708f8928997f'
PARENT_ROOT = Path('/opt/world-engine-handoffs/studio-page-stage-v1/repo')
PARENT_MANIFEST_SHA = '0d286d6a2fcb8692a2ba48d444c0fd362ad52f55471331407d7a931e22a9ac6e'
PARENT_STARTUP_SHA = '587265a57ddfe0eb64ce4f691a0cbb6c271aeca20e7c1f32e968e988938f3387'
G1_SOURCE_COMMIT = 'af2acfc5f0ceb7200d70a4ea668b717fa6a72d32'
G1_PASS_RUN = 40674899782
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
MANIFEST = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
VARIANT = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/'
HELPER = HANDOFF + 'backend/capture_operation_diagnostics.mjs'

# These five old/new pairs are preserved G1 PROTECTED_CONTRACTS evidence.
# The sixth (new) file's hash is the G1 REMOTE_SOURCE_VERIFICATION receipt.
# Only the capture source has a distinct checkout path and installed path.
SOURCES = (
    (REC + 'capture-page-evaluation-evidence-v1/candidate_capture_vulkan.mjs',
     HANDOFF + 'capture_vulkan.generated.mjs',
     '9ca02075ff5b1796dbfe6da8b8e2ef251024c8cc4e391c09366af1692524c92a',
     '4ba377dd2c530e22565184de3f383d9e495ef5acd8fa910c18a780482462748d', 26355),
    (HANDOFF + 'backend/native_guard.mjs', HANDOFF + 'backend/native_guard.mjs',
     '3dcdaa11158402b6c681438cad7b7d08a47f2adece9f45a2af4a6bb3a2c96598',
     '49718b6d1745aa9154e4456bbde7d9ca0747cb1e3957007ecab132696a32e429', 3084),
    (HANDOFF + 'controller/capture_diagnostics_safe.py', HANDOFF + 'controller/capture_diagnostics_safe.py',
     '8f9a60661e4617a54b948831b8603af2bad49e67b9b82f317ac3410a36d3d1f2',
     'e33da36d22a84717fa3b005f68f675b5f78fe8e1cd3f49702e7e27f1d38bf00a', 1970),
    (HANDOFF + 'controller/safe_capture_export.py', HANDOFF + 'controller/safe_capture_export.py',
     'a475a21e2bc4f8f7657f9f8edf62a22714209f1cbe59e63872c8456fc2a1d8c2',
     '3e66aef47d482e9b56acc88c74bf00db3d5c4b89de016c4d3d95ac6afeea3b9b', 13435),
    (HANDOFF + 'presentation_runtime_vulkan.generated.mjs', HANDOFF + 'presentation_runtime_vulkan.generated.mjs',
     'fbb35cd2f3c2a1bc66b1e104b6da4708fd5aadebe60165ee2fa587784bc9d2c4',
     '8977446517ddd85edff9fcd43771110bd4089d204bf46507cc387b64a89b0bbf', 17821),
    (HELPER, HELPER, None,
     '4d6c47cc5655c3444258276490a3be51abe05d76ac73d0e08d51160ad9cb297b', 12242),
)


def require(value, code):
    if not value:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def safe_path(root, relative):
    parts = PurePosixPath(relative)
    require(isinstance(relative, str) and not parts.is_absolute()
            and '..' not in parts.parts and str(parts) == relative,
            'G2_SOURCE_PATH_INVALID')
    file = root / relative
    require(not any(p.is_symlink() for p in (file, *file.parents)),
            'G2_SOURCE_SYMLINK_FORBIDDEN')
    return file


def read(root, relative):
    file = safe_path(root, relative)
    require(file.is_file(), 'G2_SOURCE_FILE_REQUIRED')
    return file.read_bytes()


def stage(parent, sources, destination, parent_image_digest):
    require(parent == PARENT_ROOT and parent_image_digest == PARENT_IMAGE_DIGEST,
            'G2_EXACT_PARENT_REQUIRED')
    require(not destination.exists() and destination.is_absolute()
            and parent not in destination.parents and sources not in destination.parents
            and not any(p.is_symlink() for p in destination.parents),
            'G2_FRESH_ISOLATED_DESTINATION_REQUIRED')

    # Pinned metadata identifies the immutable parent closure. No parent 352-file
    # runtime test or G1 test suite is repeated here.
    parent_manifest_raw = read(parent, MANIFEST)
    parent_startup_raw = read(parent, STARTUP + 'STARTUP_MANIFEST.json')
    require(digest(parent_manifest_raw) == PARENT_MANIFEST_SHA,
            'G2_PARENT_MANIFEST_PIN_MISMATCH')
    require(digest(parent_startup_raw) == PARENT_STARTUP_SHA,
            'G2_PARENT_STARTUP_PIN_MISMATCH')
    manifest = json.loads(parent_manifest_raw)
    startup = json.loads(parent_startup_raw)
    require(manifest.get('schema') == 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1'
            and len(manifest.get('files', [])) == 352,
            'G2_PARENT_SOURCE_MANIFEST_CONTRACT_CHANGED')
    require(startup.get('schema') == 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2'
            and startup.get('runtimeManifestSHA256') == PARENT_MANIFEST_SHA
            and set(startup.get('files', {})) == {'bootstrap.py', 'worker.py'},
            'G2_PARENT_STARTUP_CONTRACT_CHANGED')
    rows = {row['path']: copy.deepcopy(row) for row in manifest['files']}
    require(len(rows) == 352 and HELPER not in rows and VARIANT in rows,
            'G2_PARENT_SOURCE_ROWS_CHANGED')
    for row in rows.values():
        safe_path(parent, row['path'])
        require(re.fullmatch('[a-f0-9]{64}', row['sha256'])
                and type(row['bytes']) is int and row['bytes'] >= 0,
                'G2_PARENT_SOURCE_ROW_INVALID')

    replacements = {}
    for source, target, old_sha, new_sha, size in SOURCES:
        if old_sha is not None:
            require(target in rows and rows[target]['sha256'] == old_sha,
                    'G2_PARENT_DELTA_BASELINE_MISMATCH')
        else:
            require(target == HELPER and target not in rows,
                    'G2_ONLY_DIAGNOSTIC_HELPER_MAY_BE_ADDED')
        raw = read(sources, source)
        # Copy integrity of the exact, already-proven G1 delta, not a new G1 test.
        require(len(raw) == size and digest(raw) == new_sha,
                'G2_G1_PROVEN_SOURCE_REQUIRED')
        replacements[target] = raw

    variants_raw = read(parent, VARIANT)
    require(digest(variants_raw) == rows[VARIANT]['sha256']
            and len(variants_raw) == rows[VARIANT]['bytes'],
            'G2_PARENT_VARIANT_METADATA_PIN_MISMATCH')
    variants = json.loads(variants_raw)
    require(variants.get('schema') == 'WORLD_ENGINE_PINNED_GPU_ADAPTER_VARIANTS_V1'
            and len(variants.get('variants', [])) == 3,
            'G2_VARIANT_SCHEMA_CHANGED')
    expected_variant_names = {'capture_vulkan.generated.mjs',
                              'presentation_runtime_vulkan.generated.mjs',
                              'region_source_vulkan.generated.mjs'}
    require({v['variant'] for v in variants['variants']} == expected_variant_names,
            'G2_VARIANT_SET_CHANGED')
    for variant in variants['variants']:
        target = HANDOFF + variant['variant']
        require(target in rows and variant['variantSHA256'] == rows[target]['sha256'],
                'G2_PARENT_VARIANT_CHAIN_MISMATCH')
        if target in replacements:
            variant['variantSHA256'] = digest(replacements[target])
    replacements[VARIANT] = wire(variants)

    bootstrap_raw = read(parent, STARTUP + 'bootstrap.py')
    require(digest(bootstrap_raw) == startup['files']['bootstrap.py']['sha256']
            and len(bootstrap_raw) == startup['files']['bootstrap.py']['bytes'],
            'G2_PARENT_BOOTSTRAP_PIN_MISMATCH')
    old_pin = "SOURCE_SHA = '" + PARENT_MANIFEST_SHA + "'"
    require(bootstrap_raw.decode().count(old_pin) == 1,
            'G2_BOOTSTRAP_SOURCE_PIN_ANCHOR_CHANGED')

    original_rows = copy.deepcopy(rows)
    shutil.copytree(parent, destination, symlinks=False)
    for target, raw in replacements.items():
        file = safe_path(destination, target)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(raw)
        rows[target] = {**rows.get(target, {}), 'path': target,
                        'sha256': digest(raw), 'bytes': len(raw)}
    require(len(rows) == 353, 'G2_353_SOURCE_CONTRACT_REQUIRED')
    untouched = set(original_rows) - set(replacements)
    require(all(rows[name] == original_rows[name] for name in untouched),
            'G2_UNAPPROVED_SOURCE_ROW_CHANGE')
    manifest['files'] = sorted(rows.values(), key=lambda row: row['path'])
    manifest['derivation'] = {
        'parentImageDigest': PARENT_IMAGE_DIGEST,
        'parentRuntimeManifestSHA256': PARENT_MANIFEST_SHA,
        'g1SourceCommit': G1_SOURCE_COMMIT,
        'g1PassRun': G1_PASS_RUN,
        'diagnosticOnly': True,
        'parentPreserved': True,
    }
    runtime_raw = wire(manifest)
    runtime_sha = digest(runtime_raw)
    (destination / MANIFEST).write_bytes(runtime_raw)
    new_bootstrap = bootstrap_raw.decode().replace(old_pin, "SOURCE_SHA = '" + runtime_sha + "'", 1).encode()
    (destination / STARTUP / 'bootstrap.py').write_bytes(new_bootstrap)
    startup['runtimeManifestSHA256'] = runtime_sha
    startup['files']['bootstrap.py'] = {'bytes': len(new_bootstrap), 'sha256': digest(new_bootstrap)}
    startup_raw = wire(startup)
    (destination / STARTUP / 'STARTUP_MANIFEST.json').write_bytes(startup_raw)

    result = {
        'schema': 'WORLD_ENGINE_G2_STAGE_RECEIPT_V1',
        'status': 'G2_DIAGNOSTIC_DERIVATIVE_STAGED_NOT_VALIDATED',
        'parentImageDigest': PARENT_IMAGE_DIGEST,
        'parentRuntimeManifestSHA256': PARENT_MANIFEST_SHA,
        'parentStartupManifestSHA256': PARENT_STARTUP_SHA,
        'g1SourceCommit': G1_SOURCE_COMMIT,
        'g1PassRun': G1_PASS_RUN,
        'runtimeManifestSHA256': runtime_sha,
        'startupManifestSHA256': digest(startup_raw),
        'generatedSourceManifestSHA256': digest(replacements[VARIANT]),
        'bootstrapSHA256': digest(new_bootstrap),
        'sourceFiles': len(rows),
        'changedSourceFiles': sorted(set(replacements) - {HELPER}),
        'addedSourceFiles': [HELPER],
        'unchangedSourceRows': len(untouched),
        'protectedFilesUnchanged': 'BY_CONSTRUCTION_PENDING_CANDIDATE_353_FILE_VERIFICATION',
        'parentPreserved': True,
        'g0g1TestsRerun': False,
        'imageInternalValidation': 'NOT_RUN',
        'gpuExecuted': False,
        'renderExecuted': False,
        'deployReady': False,
    }
    (destination.parent / 'STAGE_RECEIPT.json').write_bytes(wire(result))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, default=PARENT_ROOT)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--parent-image-digest', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.parent, args.sources, args.destination, args.parent_image_digest), sort_keys=True))
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch('G2_[A-Z0-9_]+', code):
            code = 'G2_DERIVATIVE_STAGING_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'gpuExecuted': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
