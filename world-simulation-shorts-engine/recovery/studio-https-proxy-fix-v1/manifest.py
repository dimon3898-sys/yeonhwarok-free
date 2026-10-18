#!/usr/bin/env python3
"""Strict additive payload plus unchanged HTTPS21/Studio51/engine373 checks."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from parent import modules

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'b46b2bff3e8ef5887e1e61b9c0d835d1135b57f2810ddcc94e36e7c461eec665'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833'


def verify_sources(root=HERE):
    root = Path(root)
    raw = (root / 'PROXY_EXTENSION_FILES.json').read_bytes()
    manifest = json.loads(raw)
    if (manifest.get('schema') != 'WORLD_ENGINE_STUDIO_HTTPS_PROXY_FILES_V1'
            or manifest.get('profileId') != 'STUDIO_HTTPS_PROXY_FIX_V1'
            or manifest.get('parentImage') != PARENT_IMAGE
            or manifest.get('parentHttpsManifestSha256') != PARENT_SHA
            or not re.fullmatch('[a-f0-9]{40}', str(manifest.get('sourceCommit', '')))):
        raise RuntimeError('PROXY_EXPLICIT_PROVENANCE_REQUIRED')
    expected = {'PROXY_EXTENSION_FILES.json'}
    for group in ('files', 'testFiles'):
        entries = manifest.get(group)
        if not isinstance(entries, dict) or not entries:
            raise RuntimeError('PROXY_EXPLICIT_PAYLOAD_REQUIRED')
        for name, digest in entries.items():
            if (not isinstance(name, str) or PurePosixPath(name).is_absolute()
                    or str(PurePosixPath(name)) != name or '\\' in name or name in expected
                    or any(part in {'', '.', '..'} for part in name.split('/'))
                    or not re.fullmatch('[a-f0-9]{64}', str(digest))):
                raise RuntimeError('PROXY_CANONICAL_PATH_REQUIRED')
            file = root / name
            if (any(p.is_symlink() for p in (file, *file.parents)) or not file.is_file()
                    or not 0 < file.stat().st_size <= 4 * 1024**2
                    or hashlib.sha256(file.read_bytes()).hexdigest() != digest):
                raise RuntimeError('PROXY_SOURCE_SHA_MISMATCH')
            expected.add(name)
    if not {'parent.py', 'proxy_bootstrap.py', 'proxy_server.py', 'proxy_policy.py', 'manifest.py'} <= set(manifest['files']):
        raise RuntimeError('PROXY_CONNECTED_RUNTIME_REQUIRED')
    if any(p.is_symlink() for p in root.rglob('*')):
        raise RuntimeError('PROXY_SOURCE_SYMLINK_FORBIDDEN')
    if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != expected:
        raise RuntimeError('PROXY_UNEXPECTED_PAYLOAD_FILE')
    parent = modules().manifest.verify_sources()
    studio = parent.get('parentStudio', {})
    if (parent.get('manifestSha256') != PARENT_SHA or parent.get('files') != 21
            or studio.get('files') != 51 or studio.get('parentInventoryFiles') != 373):
        raise RuntimeError('PROXY_FROZEN_PARENT_CHANGED')
    return {'status': 'PASS', 'manifestSha256': hashlib.sha256(raw).hexdigest(),
            'sourceCommit': manifest['sourceCommit'], 'files': len(expected),
            'parentHttps': parent, 'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', required=True)
    parser.parse_args()
    try:
        print(json.dumps(verify_sources(), sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'PROXY_MANIFEST_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
