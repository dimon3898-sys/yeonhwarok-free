"""Verify only this extension and the unchanged immutable Studio/engine payloads."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
from frozen import ORIGINAL

HERE = Path(__file__).resolve().parent
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94'
PARENT_SHA = '1f4129faaeb59027429d4d531da2b7e7b50156ca7c1652e700dd542c935b88de'


def verify_sources(root=HERE):
    root = Path(root)
    raw = (root / 'EXTENSION_FILES.json').read_bytes()
    value = json.loads(raw)
    if (value.get('schema') != 'WORLD_ENGINE_STUDIO_HTTPS_EXTENSION_FILES_V1'
            or value.get('parentImage') != PARENT_IMAGE
            or value.get('parentStudioManifestSha256') != PARENT_SHA
            or not re.fullmatch(r'[a-f0-9]{40}', str(value.get('sourceCommit', '')))):
        raise RuntimeError('STUDIO_HTTPS_PROVENANCE_REQUIRED')
    expected = {'EXTENSION_FILES.json'}
    for group in ('files', 'testFiles'):
        rows = value.get(group)
        if not isinstance(rows, dict) or not rows:
            raise RuntimeError('STUDIO_HTTPS_EXPLICIT_INVENTORY_REQUIRED')
        for name, digest in rows.items():
            if (not isinstance(name, str) or PurePosixPath(name).is_absolute()
                    or str(PurePosixPath(name)) != name or '\\' in name
                    or any(part in {'', '.', '..'} for part in name.split('/'))
                    or name in expected or not re.fullmatch(r'[a-f0-9]{64}', str(digest))):
                raise RuntimeError('STUDIO_HTTPS_CANONICAL_PATH_REQUIRED')
            file = root / name
            if any(part.is_symlink() for part in (file, *file.parents)) or not file.is_file():
                raise RuntimeError('STUDIO_HTTPS_REGULAR_SOURCE_REQUIRED')
            if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                raise RuntimeError('STUDIO_HTTPS_SOURCE_SHA_MISMATCH')
            expected.add(name)
    required = {'https_bootstrap.py', 'https_server.py', 'setup_core.py', 'manifest.py', 'frozen.py',
                'web/setup.html', 'web/setup.js', 'web/setup.css'}
    if not required <= set(value['files']):
        raise RuntimeError('STUDIO_HTTPS_CONNECTED_RUNTIME_REQUIRED')
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('STUDIO_HTTPS_SYMLINK_FORBIDDEN')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise RuntimeError('STUDIO_HTTPS_UNEXPECTED_PAYLOAD_FILE')
    spec = importlib.util.spec_from_file_location('_https_original_manifest', ORIGINAL / 'studio_manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parent = module.verify_sources()
    if parent.get('manifestSha256') != PARENT_SHA or parent.get('files') != 51 or parent.get('parentInventoryFiles') != 373:
        raise RuntimeError('STUDIO_HTTPS_FROZEN_PARENT_CHANGED')
    return {'status': 'PASS', 'manifestSha256': hashlib.sha256(raw).hexdigest(),
            'sourceCommit': value['sourceCommit'], 'files': len(expected),
            'parentStudio': parent, 'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', required=True)
    parser.parse_args()
    try:
        print(json.dumps(verify_sources(), sort_keys=True))
    except Exception as error:
        code = str(error)
        code = code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code) else 'STUDIO_HTTPS_MANIFEST_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
