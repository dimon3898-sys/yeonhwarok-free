#!/usr/bin/env python3
"""Exact additive payload and immutable offline parent verification."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
NAME = 'PRODUCTION_FILES.json'
PARENT = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0'


def verify_sources(root=HERE, *, verify_parent=True):
    root = Path(root)
    raw = (root / NAME).read_bytes()
    data = json.loads(raw)
    if (data.get('schema') != 'WORLD_ENGINE_DROPBOX_GPU_PRODUCTION_FILES_V1'
            or data.get('parentImage') != PARENT
            or not re.fullmatch(r'[a-f0-9]{40}', str(data.get('sourceCommit', '')))):
        raise RuntimeError('PRODUCTION_EXPLICIT_SOURCE_REQUIRED')
    expected = {NAME}
    for entry in data.get('files', []):
        name, digest = entry['path'], entry['sha256']
        p = PurePosixPath(name)
        path = root / name
        if (p.is_absolute() or str(p) != name or '\\' in name or name in expected
                or any(c in {'', '.', '..'} for c in name.split('/'))
                or not re.fullmatch(r'[a-f0-9]{64}', str(digest))
                or any(p.is_symlink() for p in (path, *path.parents))
                or not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024**2
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise RuntimeError('PRODUCTION_PAYLOAD_SHA_MISMATCH')
        expected.add(name)
    if not {'production_entry.py', 'production_runtime.py', 'production_manifest.py',
            'key_encoding.py', 'restart_probe.py'} <= expected:
        raise RuntimeError('PRODUCTION_CONNECTED_RUNTIME_REQUIRED')
    if root.is_relative_to('/opt'):
        if (any(p.is_symlink() for p in root.rglob('*')) or
                {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != expected):
            raise RuntimeError('PRODUCTION_UNEXPECTED_PAYLOAD')
    parent = {'status': 'NOT_EXECUTED'}
    if verify_parent:
        from production_runtime import frozen
        parent = frozen().modules().manifest.verify_sources()
        if parent.get('status') != 'PASS':
            raise RuntimeError('PRODUCTION_PARENT_CHANGED')
    return {'status': 'PASS', 'sourceCommit': data['sourceCommit'], 'files': len(expected),
            'manifestSha256': hashlib.sha256(raw).hexdigest(), 'parentDurability': parent,
            'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(verify_sources(), sort_keys=True))
