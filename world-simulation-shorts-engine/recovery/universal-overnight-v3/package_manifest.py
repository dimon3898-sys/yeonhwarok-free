"""Additive overnight source closure over the immutable completed V2 image."""
from pathlib import Path
import importlib.util
import json
import os
import re

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'universal-integration-completion-v2'
BASE_COMMIT = '57de569380644e0a14de62c86e8d8b4407826f37'
BASE_IMAGE = 'sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886'
PREVIOUS_MANIFEST_SHA = '99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9'
MANIFEST = HERE / 'OVERNIGHT_FILES.json'
ENV = 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_JSON'
spec = importlib.util.spec_from_file_location('_overnight_completed_manifest', PREVIOUS / 'package_manifest.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
read_regular, canonical, sha, parent_path = old.read_regular, old.canonical, old.sha, old.parent_path


def build_manifest():
    previous = old.verify_sources()
    if previous['manifestSHA256'] != PREVIOUS_MANIFEST_SHA:
        raise RuntimeError('OVERNIGHT_COMPLETED_PARENT_CHANGED')
    files = {p.name: sha(read_regular(p)) for p in sorted(HERE.iterdir())
             if p.is_file() and p.suffix in {'.py', '.mjs', '.json'}
             and p.name not in {'OVERNIGHT_FILES.json', 'RUNTIME_SOURCE_MANIFEST.json'}}
    value = {'schema': 'WORLD_ENGINE_OVERNIGHT_FILES_V1',
             'sourceBaseCommit': BASE_COMMIT, 'baseOperatingImageDigest': BASE_IMAGE,
             'previousManifestSHA256': PREVIOUS_MANIFEST_SHA, 'files': files,
             'registeredCandidateImageDigest': None, 'gpuVerified': False,
             'existingSourceChanged': False}
    MANIFEST.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


def verify_sources():
    raw = read_regular(MANIFEST)
    value = json.loads(raw)
    if (value.get('schema') != 'WORLD_ENGINE_OVERNIGHT_FILES_V1'
            or value.get('sourceBaseCommit') != BASE_COMMIT
            or value.get('baseOperatingImageDigest') != BASE_IMAGE
            or value.get('previousManifestSHA256') != PREVIOUS_MANIFEST_SHA
            or value.get('registeredCandidateImageDigest') is not None
            or value.get('gpuVerified') is not False
            or value.get('existingSourceChanged') is not False
            or not isinstance(value.get('files'), dict) or not value['files']):
        raise RuntimeError('OVERNIGHT_SOURCE_MANIFEST_INVALID')
    parent = old.verify_sources()
    if parent['manifestSHA256'] != PREVIOUS_MANIFEST_SHA:
        raise RuntimeError('OVERNIGHT_COMPLETED_PARENT_CHANGED')
    for name, digest in value['files'].items():
        if (not isinstance(name, str) or Path(name).name != name or '\\' in name
                or name in {'.', '..'} or not re.fullmatch('[a-f0-9]{64}', str(digest))
                or sha(read_regular(HERE / name)) != digest):
            raise RuntimeError('OVERNIGHT_SOURCE_HASH_MISMATCH')
    return {'status': 'PASS', 'manifestSHA256': sha(raw), 'files': len(value['files']),
            'parentFiles': parent['files'] + parent['parentFiles'],
            'previousManifestSHA256': parent['manifestSHA256'], 'sourceCommit': BASE_COMMIT,
            'registeredCandidateImageDigest': None, 'gpuVerified': False}


def validate_image_proof(value, *, source_manifest_sha256=None, image_digest=None):
    keys = {'schema', 'imageDigest', 'sourceManifestSHA256', 'sourceCommit',
            'independentPullVerified', 'sourceHashesVerified', 'baseDigest', 'result'}
    if (not isinstance(value, dict) or set(value) != keys
            or value.get('schema') != 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_V1'
            or value.get('result') != 'PASS' or value.get('baseDigest') != BASE_IMAGE
            or value.get('independentPullVerified') is not True
            or value.get('sourceHashesVerified') is not True
            or not re.fullmatch('sha256:[a-f0-9]{64}', str(value.get('imageDigest', '')))
            or value['imageDigest'] == BASE_IMAGE
            or not re.fullmatch('[a-f0-9]{64}', str(value.get('sourceManifestSHA256', '')))
            or not re.fullmatch('[a-f0-9]{40}', str(value.get('sourceCommit', '')))):
        raise RuntimeError('OVERNIGHT_INDEPENDENT_IMAGE_PROOF_INVALID')
    if source_manifest_sha256 is not None and value['sourceManifestSHA256'] != source_manifest_sha256:
        raise RuntimeError('OVERNIGHT_IMAGE_SOURCE_BINDING_MISMATCH')
    if image_digest is not None and value['imageDigest'] != image_digest:
        raise RuntimeError('OVERNIGHT_IMAGE_DIGEST_BINDING_MISMATCH')
    return value


def read_image_proof(control_root, *, source_manifest_sha256, image_digest):
    if control_root is None:
        return None
    control_root = Path(control_root)
    if tuple(control_root.parts[-2:]) != ('universal-overnight-v3', 'universal-integration-v1'):
        raise RuntimeError('OVERNIGHT_OPERATOR_SCOPE_REQUIRED')
    authority = control_root.parents[1]
    file = authority / 'overnight_image_proof.json'
    if not file.exists():
        return None
    spec = importlib.util.spec_from_file_location('_overnight_private_image_receipt',
        HERE.parent / 'universal-integration-v1/quality_gate.py')
    quality = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quality)
    value = quality._private_receipt(file, authority, os.geteuid())
    return validate_image_proof(value, source_manifest_sha256=source_manifest_sha256,
                                image_digest=image_digest)


def install_image_proof(raw, config, source_manifest_sha256, original_bootstrap, *, uid=1000, gid=1000):
    if raw is None:
        return False
    if not isinstance(raw, str) or not 0 < len(raw.encode()) <= 16384:
        raise RuntimeError('OVERNIGHT_IMAGE_PROOF_JSON_INVALID')
    value = validate_image_proof(json.loads(raw), source_manifest_sha256=source_manifest_sha256)
    original_bootstrap._private_file(Path(config['root']) / 'production/overnight_image_proof.json',
        (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode(), uid, gid)
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    if parser.parse_args().build:
        build_manifest()
    print(json.dumps(verify_sources(), sort_keys=True))
