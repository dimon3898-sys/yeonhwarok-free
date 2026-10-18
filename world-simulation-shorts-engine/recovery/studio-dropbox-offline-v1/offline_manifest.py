#!/usr/bin/env python3
"""Verify the additive OAuth payload and unchanged durability parent."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from offline_frozen import modules

HERE = Path(__file__).resolve().parent
NAME = 'OFFLINE_FILES.json'
PARENT_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b'
PARENT_COMMIT = '165a3489eede6e6f66c20f2d6ca1d70fd8c79560'


def verify_sources(root=HERE, *, verify_parent=True):
    root = Path(root)
    raw = (root / NAME).read_bytes()
    data = json.loads(raw)
    if (data.get('schema') != 'WORLD_ENGINE_DROPBOX_OFFLINE_FILES_V1'
            or data.get('parentImage') != PARENT_IMAGE or data.get('parentCommit') != PARENT_COMMIT
            or not re.fullmatch(r'[a-f0-9]{40}', str(data.get('sourceCommit', '')))):
        raise RuntimeError('OFFLINE_EXPLICIT_PROVENANCE_REQUIRED')
    expected = {NAME}
    for group in ('files', 'testFiles'):
        entries = data.get(group)
        if not isinstance(entries, dict) or not entries:
            raise RuntimeError('OFFLINE_EXPLICIT_PAYLOAD_REQUIRED')
        for name, digest in entries.items():
            if (not isinstance(name, str) or PurePosixPath(name).is_absolute()
                    or str(PurePosixPath(name)) != name or '\\' in name or name in expected
                    or any(p in {'', '.', '..'} for p in name.split('/'))
                    or not re.fullmatch(r'[a-f0-9]{64}', str(digest))):
                raise RuntimeError('OFFLINE_CANONICAL_PATH_REQUIRED')
            path = root / name
            if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
                    or not 0 < path.stat().st_size <= 4 * 1024**2
                    or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
                raise RuntimeError('OFFLINE_SOURCE_SHA_MISMATCH')
            expected.add(name)
    if not {'offline_frozen.py', 'PARENT_SOURCES.json', 'renewal.py', 'offline_runtime.py',
            'offline_entry.py', 'offline_manifest.py', 'consent.py'} <= set(data['files']):
        raise RuntimeError('OFFLINE_CONNECTED_RUNTIME_REQUIRED')
    if root.is_relative_to('/opt'):
        if any(p.is_symlink() for p in root.rglob('*')):
            raise RuntimeError('OFFLINE_SOURCE_SYMLINK_FORBIDDEN')
        if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != expected:
            raise RuntimeError('OFFLINE_UNEXPECTED_PAYLOAD_FILE')
    parent = {'status': 'NOT_EXECUTED', 'reason': 'SOURCE_ONLY_CHECK'}
    if verify_parent:
        parent = modules().manifest.verify_sources()
        if parent.get('status') != 'PASS' or parent.get('gpuExecuted') is not False:
            raise RuntimeError('OFFLINE_PROTECTED_PARENT_CHANGED')
    return {'status': 'PASS', 'sourceCommit': data['sourceCommit'], 'files': len(expected),
            'manifestSha256': hashlib.sha256(raw).hexdigest(), 'parentDurability': parent,
            'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', required=True)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.source_only and HERE.is_relative_to('/opt'):
            raise RuntimeError('OFFLINE_PARENT_VERIFICATION_REQUIRED')
        print(json.dumps(verify_sources(verify_parent=not args.source_only), sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'OFFLINE_MANIFEST_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
