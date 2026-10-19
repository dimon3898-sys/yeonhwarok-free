"""Operator-installed immutable build/pull receipt, separate from user prompts."""
from pathlib import Path
import importlib.util
import json
import os
import re

HERE = Path(__file__).resolve().parent
ENV = 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_JSON'
BASE_IMAGE = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
KEYS = {'schema', 'imageDigest', 'sourceManifestSHA256', 'sourceCommit',
        'independentPullVerified', 'sourceHashesVerified', 'baseDigest', 'result'}


def validate(value, *, source_manifest_sha256=None, image_digest=None):
    if (not isinstance(value, dict) or set(value) != KEYS
            or value.get('schema') != 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1'
            or value.get('result') != 'PASS' or value.get('baseDigest') != BASE_IMAGE
            or value.get('independentPullVerified') is not True
            or value.get('sourceHashesVerified') is not True
            or not re.fullmatch('sha256:[a-f0-9]{64}', str(value.get('imageDigest', '')))
            or value['imageDigest'] == BASE_IMAGE
            or not re.fullmatch('[a-f0-9]{64}', str(value.get('sourceManifestSHA256', '')))
            or not re.fullmatch('[a-f0-9]{40}', str(value.get('sourceCommit', '')))):
        raise RuntimeError('COMPLETION_INDEPENDENT_IMAGE_PROOF_INVALID')
    if source_manifest_sha256 is not None and value['sourceManifestSHA256'] != source_manifest_sha256:
        raise RuntimeError('COMPLETION_IMAGE_SOURCE_BINDING_MISMATCH')
    if image_digest is not None and value['imageDigest'] != image_digest:
        raise RuntimeError('COMPLETION_IMAGE_DIGEST_BINDING_MISMATCH')
    return value


def read(control_root, *, source_manifest_sha256, image_digest):
    if control_root is None:
        return None
    control_root = Path(control_root)
    if tuple(control_root.parts[-2:]) != ('universal-integration-completion-v2', 'universal-integration-v1'):
        raise RuntimeError('COMPLETION_OPERATOR_SCOPE_REQUIRED')
    authority = control_root.parents[1]
    file = authority / 'completion_image_proof.json'
    if not file.exists():
        return None
    spec = importlib.util.spec_from_file_location('_completion_private_image_receipt', HERE.parent / 'universal-integration-v1/quality_gate.py')
    quality = importlib.util.module_from_spec(spec); spec.loader.exec_module(quality)
    value = quality._private_receipt(file, authority, os.geteuid())
    return validate(value, source_manifest_sha256=source_manifest_sha256, image_digest=image_digest)


def install(raw, config, source_manifest_sha256, original_bootstrap, *, uid=1000, gid=1000):
    if raw is None:
        return False
    if not isinstance(raw, str) or not 0 < len(raw.encode()) <= 16384:
        raise RuntimeError('COMPLETION_IMAGE_PROOF_JSON_INVALID')
    value = validate(json.loads(raw), source_manifest_sha256=source_manifest_sha256)
    original_bootstrap._private_file(Path(config['root']) / 'production/completion_image_proof.json',
        (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode(), uid, gid)
    return True
