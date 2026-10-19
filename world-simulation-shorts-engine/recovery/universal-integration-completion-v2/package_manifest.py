"""Immutable additive completion closure; original V1 manifests stay untouched."""
from pathlib import Path
import hashlib
import importlib.util
import json

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'universal-integration-v1'
BASE_COMMIT = '61c7fc3a36cc987c3f88844aba98c57bb62fe22e'
BASE_IMAGE = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
MANIFEST = HERE / 'COMPLETION_FILES.json'
spec = importlib.util.spec_from_file_location('_completion_old_manifest', PREVIOUS / 'package_manifest.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
read_regular, canonical, sha, parent_path = old.read_regular, old.canonical, old.sha, old.parent_path


def build_manifest():
    old_proof = old.verify_sources()
    files = {p.name: sha(read_regular(p)) for p in sorted(HERE.iterdir())
             if p.is_file() and p.suffix in {'.py', '.mjs', '.json'}
             and p.name not in {'COMPLETION_FILES.json', 'RUNTIME_SOURCE_MANIFEST.json'}}
    value = {'schema': 'WORLD_ENGINE_COMPLETION_FILES_V2', 'sourceBaseCommit': BASE_COMMIT,
        'baseOperatingImageDigest': BASE_IMAGE, 'registeredCandidateImageDigest': None,
        'previousManifestSHA256': old_proof['manifestSHA256'], 'files': files,
        'parentFiles': json.loads(read_regular(PREVIOUS / 'INTEGRATION_FILES.json'))['parentFiles'],
        'gpuVerified': False, 'existingSourceChanged': False}
    MANIFEST.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


def verify_sources():
    raw = read_regular(MANIFEST)
    value = json.loads(raw)
    if (value.get('schema') != 'WORLD_ENGINE_COMPLETION_FILES_V2'
            or value.get('sourceBaseCommit') != BASE_COMMIT
            or not isinstance(value.get('files'), dict) or not value['files']):
        raise RuntimeError('COMPLETION_SOURCE_MANIFEST_INVALID')
    parent = old.verify_sources()
    if parent['manifestSHA256'] != value.get('previousManifestSHA256'):
        raise RuntimeError('COMPLETION_PREVIOUS_SOURCE_CHANGED')
    for name, expected in value['files'].items():
        if (not isinstance(name, str) or Path(name).name != name or '\\' in name
                or name in {'.', '..'} or sha(read_regular(HERE / name)) != expected):
            raise RuntimeError('COMPLETION_SOURCE_HASH_MISMATCH')
    # The digest is written only after a real immutable build/pull receipt exists.
    image = value.get('registeredCandidateImageDigest')
    return {'status': 'PASS', 'manifestSHA256': sha(raw), 'files': len(value['files']),
        'parentFiles': parent['parentFiles'], 'previousManifestSHA256': parent['manifestSHA256'],
        'registeredCandidateImageDigest': image, 'gpuVerified': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--build', action='store_true')
    if parser.parse_args().build:
        build_manifest()
    print(json.dumps(verify_sources(), sort_keys=True))
