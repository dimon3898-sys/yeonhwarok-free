"""Pure candidate-publication contract; no Docker, network or registry writes.

The namespace is deliberately separate from the successful-image package. GHCR
tags are mutable: exclusive publisher ACL evidence is an external prerequisite,
not something a local existence check or this module can prove.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SUCCESS_PACKAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
SUCCESS_DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
CANDIDATE_PACKAGE = 'ghcr.io/dimon3898-sys/world-engine-vulkan-surface-candidates'
SOURCE_COMMIT = 'd259e61c96e83a97a8b97e797670786a434a240d'
PROFILE_SHA = 'f55758af58a7c8724bddc097f05586b6d4cfdfa81133fa093636e335bca171c5'
OLD_RUNTIME_SHA = 'a4ef7cdca49e64881f737d4c88d949dafa502868fa6a1df7d392170e0170f314'
OLD_STARTUP_SHA = '3cac42a8da8fd76994b20035666e3f15c94779073deb0d0d4ae515a0b2da8407'
ROOT = 'world-simulation-shorts-engine/recovery/'
PROFILE = ROOT + 'codex-to-gcube-handoff-v1/backend/profile_contract.mjs'
OVERLAY_FILES = frozenset({PROFILE,
    ROOT + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json',
    ROOT + 'studio-cold-start-v2/bootstrap.py',
    ROOT + 'studio-cold-start-v2/STARTUP_MANIFEST.json'})
MAX_MANIFEST = 1024 * 1024
MAX_CONFIG = 4 * 1024 * 1024
MAX_LAYER = 4 * 1024**3
MAX_EXPANDED_LAYER = 8 * 1024**3
MAX_TOTAL_BLOB_BYTES = 12 * 1024**3
MANIFEST_TYPES = frozenset({'application/vnd.oci.image.manifest.v1+json',
    'application/vnd.docker.distribution.manifest.v2+json'})
CONFIG_TYPES = frozenset({'application/vnd.oci.image.config.v1+json',
    'application/vnd.docker.container.image.v1+json'})
GZIP_LAYER_TYPES = frozenset({'application/vnd.oci.image.layer.v1.tar+gzip',
    'application/vnd.docker.image.rootfs.diff.tar.gzip'})
RAW_LAYER_TYPES = frozenset({'application/vnd.oci.image.layer.v1.tar',
    'application/vnd.docker.image.rootfs.diff.tar'})


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def valid_digest(value):
    return type(value) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', value) is not None


def _hex(value):
    return type(value) is str and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def candidate_tag(run_id, run_attempt, reviewed_head):
    require(type(run_id) is str and re.fullmatch(r'[1-9][0-9]{0,19}', run_id),
            'PUBLISH_RUN_ID_INVALID')
    require(type(run_attempt) in (str, int) and str(run_attempt) == '1',
            'PUBLISH_RETRY_FORBIDDEN')
    require(type(reviewed_head) is str and re.fullmatch(r'[a-f0-9]{40}', reviewed_head),
            'PUBLISH_REVIEWED_HEAD_INVALID')
    return 'surface-v1-d259e61c96e8-' + run_id + '-a1'


def candidate_destination(run_id, run_attempt, reviewed_head):
    return CANDIDATE_PACKAGE + ':' + candidate_tag(run_id, run_attempt, reviewed_head)


def validate_destination(destination, run_id, run_attempt, reviewed_head):
    expected = candidate_destination(run_id, run_attempt, reviewed_head)
    require(destination == expected and not destination.startswith(SUCCESS_PACKAGE + ':'),
            'PUBLISH_DESTINATION_NOT_FIXED_CANDIDATE_NAMESPACE')
    return expected


def validate_evidence(evidence, *, reviewed_head=None):
    """Bind all original new-image PASS receipts before permitting preparation.

    This consumes receipts; it never repeats their tests or runs a renderer.
    """
    require(isinstance(evidence, dict) and 'FAILURE' not in evidence,
            'PUBLISH_PRIOR_FAILURE_PRESENT')
    names = ('PREFLIGHT', 'BUILD', 'CONNECTION_VERIFY', 'IMAGE_SCOPE', 'STAGE_RECEIPT')
    require(all(isinstance(evidence.get(name), dict) for name in names),
            'PUBLISH_REQUIRED_EVIDENCE_MISSING')
    pre, built, verify, scope, stage = (evidence[name] for name in names)
    require(all(row.get('status') == 'PASS' for row in (pre, built, verify, scope))
            and stage.get('status') == 'PREPARED_NOT_BUILT', 'PUBLISH_VALIDATION_NOT_PASS')
    image_id = built.get('candidateImageID')
    require(valid_digest(image_id) and image_id == scope.get('candidateImageID'),
            'PUBLISH_TESTED_IMAGE_ID_MISMATCH')
    require(pre.get('parentDigest') == SUCCESS_DIGEST
            and built.get('parentDigest') == SUCCESS_DIGEST
            and stage.get('parentImageDigest') == SUCCESS_DIGEST,
            'PUBLISH_PARENT_IDENTITY_MISMATCH')
    require(pre.get('profileSHA256') == PROFILE_SHA, 'PUBLISH_PROFILE_NOT_APPROVED')
    require(type(pre.get('reviewedHead')) is str
            and re.fullmatch(r'[a-f0-9]{40}', pre['reviewedHead']), 'PUBLISH_REVIEWED_HEAD_INVALID')
    if reviewed_head is not None:
        require(pre.get('reviewedHead') == reviewed_head, 'PUBLISH_REVIEWED_HEAD_MISMATCH')
    require(type(built.get('buildAttempts')) is int and built['buildAttempts'] == 1
            and built.get('pushed') is False and built.get('gpuExecuted') is False,
            'PUBLISH_BUILD_ATTEMPT_OR_STATE_INVALID')
    require(verify.get('scope') == 'NEW_OVERLAY_AND_PIN_CONNECTIONS_ONLY'
            and verify.get('sourceFiles') == 353 and verify.get('unchangedSourceRows') == 352
            and verify.get('overlayFilesVerified') == 4
            and verify.get('entrypointPinsVerified') is True
            and verify.get('parentConfigPreservedExceptEntrypoint') is True,
            'PUBLISH_CONNECTION_SCOPE_INVALID')
    require(scope.get('parentPreserved') is True
            and type(scope.get('parentLayerCount')) is int
            and type(scope.get('candidateLayerCount')) is int
            and scope['candidateLayerCount'] == scope['parentLayerCount'] + 4
            and scope.get('additionalCopyLayers') == 4,
            'PUBLISH_PARENT_OR_LAYER_SCOPE_INVALID')
    require(stage.get('sourceCommit') == SOURCE_COMMIT
            and stage.get('sourceFiles') == 353 and stage.get('unchangedSourceRows') == 352
            and stage.get('changedRuntimeRows') == [PROFILE]
            and set(stage.get('overlayFiles', {})) == OVERLAY_FILES
            and stage.get('parentPreserved') is True
            and stage.get('imageBuilt') is False and stage.get('imagePublished') is False,
            'PUBLISH_STAGE_SCOPE_INVALID')
    require(stage.get('parentRuntimeManifestSHA256') == OLD_RUNTIME_SHA
            and stage.get('parentStartupManifestSHA256') == OLD_STARTUP_SHA,
            'PUBLISH_PARENT_PIN_BINDING_INVALID')
    require(_hex(stage.get('runtimeManifestSHA256')) and _hex(stage.get('startupManifestSHA256'))
            and verify.get('runtimeManifestSHA256') == stage['runtimeManifestSHA256']
            and verify.get('startupManifestSHA256') == stage['startupManifestSHA256'],
            'PUBLISH_NEW_PIN_BINDING_INVALID')
    require(verify.get('browserLaunched') is False and verify.get('gpuExecuted') is False
            and verify.get('priorPassSuitesRerun') is False
            and scope.get('gpuExecuted') is False and scope.get('priorPassTestsRerun') is False
            and stage.get('browserLaunched') is False and stage.get('gpuExecuted') is False
            and stage.get('priorPassSuitesRerun') is False,
            'PUBLISH_FORBIDDEN_EXECUTION_EVIDENCE')
    binding = hashlib.sha256(json.dumps({name: evidence[name] for name in names},
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return {'status': 'PASS', 'candidateImageID': image_id, 'evidenceBindingSHA256': binding,
            'parentDigest': SUCCESS_DIGEST, 'runtimeManifestSHA256': stage['runtimeManifestSHA256'],
            'startupManifestSHA256': stage['startupManifestSHA256'],
            'sourceFiles': 353, 'overlayFilesVerified': 4, 'gpuExecuted': False}


def _safe_file(path, limit, *, materialize=False):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)),
            'PUBLISH_LAYOUT_PATH_UNSAFE')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 <= before.st_size <= limit, 'PUBLISH_LAYOUT_FILE_INVALID')
        h = hashlib.sha256(); total = 0; parts = []
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block: break
            total += len(block)
            require(total <= limit, 'PUBLISH_LAYOUT_FILE_TOO_LARGE')
            h.update(block)
            if materialize: parts.append(block)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                and total == before.st_size, 'PUBLISH_LAYOUT_FILE_CHANGED')
        return {'bytes': total, 'digest': 'sha256:' + h.hexdigest(),
                'raw': b''.join(parts) if materialize else None}
    finally:
        os.close(fd)


def _descriptor(value, allowed_types):
    require(isinstance(value, dict) and set(value) == {'mediaType', 'digest', 'size'}
            and value.get('mediaType') in allowed_types and valid_digest(value.get('digest'))
            and type(value.get('size')) is int and value['size'] >= 0,
            'PUBLISH_DESCRIPTOR_INVALID')
    return value


def parse_registry_manifest(raw, candidate_id):
    require(type(raw) is bytes and len(raw) <= MAX_MANIFEST and valid_digest(candidate_id),
            'PUBLISH_MANIFEST_INPUT_INVALID')
    obj = json.loads(raw)
    require(isinstance(obj, dict) and set(obj) == {'schemaVersion', 'mediaType', 'config', 'layers'}
            and obj.get('schemaVersion') == 2 and obj.get('mediaType') in MANIFEST_TYPES,
            'PUBLISH_SINGLE_IMAGE_MANIFEST_REQUIRED')
    config = _descriptor(obj.get('config'), CONFIG_TYPES)
    require(config['digest'] == candidate_id, 'PUBLISH_MANIFEST_CONFIG_NOT_TESTED_IMAGE')
    require(isinstance(obj.get('layers'), list) and 1 <= len(obj['layers']) <= 128,
            'PUBLISH_LAYER_COUNT_INVALID')
    for layer in obj['layers']:
        _descriptor(layer, GZIP_LAYER_TYPES | RAW_LAYER_TYPES)
    return obj


def validate_registry_ready(layout_dir, candidate_id, *, expected_diff_ids=None):
    """Validate exact skopeo dir: bytes before any network publication.

    Config content digest is the tested Docker image ID. The registry manifest
    digest is separately computed from manifest.json; those identities differ.
    """
    root = Path(layout_dir)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            'PUBLISH_LAYOUT_DIRECTORY_INVALID')
    manifest_info = _safe_file(root / 'manifest.json', MAX_MANIFEST, materialize=True)
    obj = parse_registry_manifest(manifest_info['raw'], candidate_id)
    names = {'manifest.json', 'version'}
    config_desc = obj['config']; names.add(config_desc['digest'][7:])
    config_info = _safe_file(root / config_desc['digest'][7:], MAX_CONFIG, materialize=True)
    require(config_info['digest'] == config_desc['digest'] and config_info['bytes'] == config_desc['size'],
            'PUBLISH_CONFIG_BYTES_MISMATCH')
    config = json.loads(config_info['raw'])
    require(isinstance(config, dict) and isinstance(config.get('rootfs'), dict)
            and config['rootfs'].get('type') == 'layers'
            and isinstance(config['rootfs'].get('diff_ids'), list), 'PUBLISH_CONFIG_ROOTFS_INVALID')
    diff_ids = config['rootfs']['diff_ids']
    require(len(diff_ids) == len(obj['layers']) and all(valid_digest(v) for v in diff_ids),
            'PUBLISH_CONFIG_DIFF_IDS_INVALID')
    if expected_diff_ids is not None:
        require(diff_ids == expected_diff_ids, 'PUBLISH_TESTED_DIFF_IDS_MISMATCH')
    total = config_info['bytes']; layers = []
    for index, desc in enumerate(obj['layers']):
        name = desc['digest'][7:]; names.add(name)
        layer_file = root / name
        info = _safe_file(layer_file, MAX_LAYER)
        total += info['bytes']
        require(total <= MAX_TOTAL_BLOB_BYTES, 'PUBLISH_LAYOUT_TOTAL_TOO_LARGE')
        require(info['bytes'] == desc['size'] and info['digest'] == desc['digest'],
                'PUBLISH_LAYER_BYTES_MISMATCH')
        h = hashlib.sha256(); expanded = 0
        # The file has just passed no-follow checks. Open again with NOFOLLOW;
        # no decompressed tar file is created or extracted.
        fd = os.open(layer_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                reader = gzip.GzipFile(fileobj=stream, mode='rb') if desc['mediaType'] in GZIP_LAYER_TYPES else stream
                try:
                    while True:
                        block = reader.read(1024 * 1024)
                        if not block: break
                        expanded += len(block)
                        require(expanded <= MAX_EXPANDED_LAYER, 'PUBLISH_EXPANDED_LAYER_TOO_LARGE')
                        h.update(block)
                finally:
                    if reader is not stream: reader.close()
        finally:
            os.close(fd)
        require('sha256:' + h.hexdigest() == diff_ids[index], 'PUBLISH_LAYER_DIFF_ID_MISMATCH')
        layers.append({'digest': info['digest'], 'bytes': info['bytes'], 'diffID': diff_ids[index]})
    actual = {p.name for p in root.iterdir()}
    require(actual <= names and 'manifest.json' in actual
            and all(p.is_file() and not p.is_symlink() for p in root.iterdir()),
            'PUBLISH_LAYOUT_EXTRA_FILES_FORBIDDEN')
    if 'version' in actual: _safe_file(root / 'version', 1024)
    return {'status': 'PASS', 'scope': 'REGISTRY_READY_EXACT_BYTES_NOT_PUBLISHED',
            'expectedRegistryDigest': manifest_info['digest'], 'candidateImageID': candidate_id,
            'manifestBytes': manifest_info['bytes'], 'configDigest': config_info['digest'],
            'layerCount': len(layers), 'layers': layers, 'totalBlobBytes': total,
            'gpuExecuted': False, 'published': False}


def validate_publish_preconditions(destination, run_id, run_attempt, reviewed_head,
                                   *, tag_exists, parent_manifest_raw):
    target = validate_destination(destination, run_id, run_attempt, reviewed_head)
    require(type(tag_exists) is bool and tag_exists is False, 'PUBLISH_TAG_ALREADY_EXISTS_OR_UNKNOWN')
    require(type(parent_manifest_raw) is bytes and len(parent_manifest_raw) <= MAX_MANIFEST
            and sha(parent_manifest_raw) == SUCCESS_DIGEST, 'PUBLISH_SUCCESS_BASELINE_CHANGED')
    return {'status': 'PASS', 'destination': target, 'tagAbsentBefore': True,
            'parentRegistryDigestBefore': SUCCESS_DIGEST,
            'atomicRegistryTagCreationClaimed': False}


def validate_registry_readback(expected_digest, candidate_id, tag_raw, digest_raw,
                               parent_before_raw, parent_after_raw):
    require(valid_digest(expected_digest) and valid_digest(candidate_id), 'PUBLISH_READBACK_ID_INVALID')
    require(type(tag_raw) is bytes and type(digest_raw) is bytes
            and tag_raw == digest_raw and sha(tag_raw) == expected_digest,
            'PUBLISH_REGISTRY_MANIFEST_DIGEST_MISMATCH')
    parse_registry_manifest(tag_raw, candidate_id)
    require(type(parent_before_raw) is bytes and type(parent_after_raw) is bytes
            and parent_before_raw == parent_after_raw and sha(parent_before_raw) == SUCCESS_DIGEST,
            'PUBLISH_SUCCESS_BASELINE_CHANGED')
    return {'status': 'PASS', 'registryDigest': expected_digest, 'candidateImageID': candidate_id,
            'tagAndDigestBodiesIdentical': True, 'expectedRegistryDigestMatched': True,
            'parentDigestUnchanged': SUCCESS_DIGEST, 'gpuExecuted': False}
