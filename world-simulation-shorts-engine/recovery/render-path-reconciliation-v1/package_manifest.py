"""Manifest only the additive reconciliation layer; verify all frozen parents."""
from pathlib import Path
import importlib.util
import json
import re

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'universal-overnight-v3'
BASE_COMMIT = '1c34f688908e87520d60b578484eea3d9940ed6e'
BASE_IMAGE = 'sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645'
PREVIOUS_MANIFEST_SHA = 'ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7'
MANIFEST = HERE / 'RECONCILIATION_FILES.json'
SCHEMA = 'WORLD_ENGINE_RECONCILIATION_FILES_V1'
spec = importlib.util.spec_from_file_location('_reconciliation_frozen_manifest', PREVIOUS / 'package_manifest.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
read_regular, canonical, sha, parent_path = old.read_regular, old.canonical, old.sha, old.parent_path


def _verify_parent():
    value = old.verify_sources()
    if (value.get('manifestSHA256') != PREVIOUS_MANIFEST_SHA
            or value.get('files') != 27 or value.get('parentFiles') != 55):
        raise RuntimeError('RECONCILIATION_FROZEN_PARENT_CHANGED')
    return value


def build_manifest():
    _verify_parent()
    files = {p.name: sha(read_regular(p)) for p in sorted(HERE.iterdir())
        if p.is_file() and p.suffix in {'.py', '.mjs', '.json'}
        and p.name not in {'RECONCILIATION_FILES.json', 'RUNTIME_SOURCE_MANIFEST.json'}}
    value = {'schema': SCHEMA, 'sourceBaseCommit': BASE_COMMIT,
        'baseOperatingImageDigest': BASE_IMAGE, 'previousManifestSHA256': PREVIOUS_MANIFEST_SHA,
        'files': files, 'registeredCandidateImageDigest': None,
        'gpuVerified': False, 'existingSourceChanged': False}
    MANIFEST.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


def verify_sources():
    raw = read_regular(MANIFEST)
    value = json.loads(raw)
    if (set(value) != {'schema', 'sourceBaseCommit', 'baseOperatingImageDigest',
            'previousManifestSHA256', 'files', 'registeredCandidateImageDigest',
            'gpuVerified', 'existingSourceChanged'}
            or value['schema'] != SCHEMA or value['sourceBaseCommit'] != BASE_COMMIT
            or value['baseOperatingImageDigest'] != BASE_IMAGE
            or value['previousManifestSHA256'] != PREVIOUS_MANIFEST_SHA
            or value['registeredCandidateImageDigest'] is not None
            or value['gpuVerified'] is not False or value['existingSourceChanged'] is not False
            or not isinstance(value['files'], dict) or not value['files']):
        raise RuntimeError('RECONCILIATION_SOURCE_MANIFEST_INVALID')
    parent = _verify_parent()
    actual = {p.name for p in HERE.iterdir() if p.is_file()
        and p.suffix in {'.py', '.mjs', '.json'}
        and p.name not in {'RECONCILIATION_FILES.json', 'RUNTIME_SOURCE_MANIFEST.json'}}
    if actual != set(value['files']):
        raise RuntimeError('RECONCILIATION_UNMANIFESTED_RUNTIME_SOURCE')
    for name, digest in value['files'].items():
        if (not isinstance(name, str) or Path(name).name != name or '\\' in name
                or name in {'.', '..'} or not re.fullmatch('[a-f0-9]{64}', str(digest))
                or sha(read_regular(HERE / name)) != digest):
            raise RuntimeError('RECONCILIATION_SOURCE_HASH_MISMATCH')
    return {'status': 'PASS', 'manifestSHA256': sha(raw), 'files': len(value['files']),
        'parentFiles': parent['files'] + parent['parentFiles'],
        'previousManifestSHA256': parent['manifestSHA256'],
        'sourceBaseCommit': BASE_COMMIT, 'registeredCandidateImageDigest': None,
        'gpuVerified': False, 'existingSourceChanged': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    if parser.parse_args().build:
        build_manifest()
    print(json.dumps(verify_sources(), sort_keys=True))
