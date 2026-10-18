#!/usr/bin/env python3
"""Verify the additive payload and the frozen, recursively verified parent."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

HERE = Path(__file__).resolve().parent
NAME = 'DURABILITY_FILES.json'
BASE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
BASE_COMMIT = 'f983adc247363b06e8e0f29bd7d5b2e74d73e8c0'


def verify_sources(root=HERE, *, verify_parent=True):
    root = Path(root)
    raw = (root / NAME).read_bytes()
    manifest = json.loads(raw)
    if (manifest.get('schema') != 'WORLD_ENGINE_STUDIO_DURABILITY_FILES_V1'
            or manifest.get('parentImage') != BASE
            or manifest.get('protectedBaseCommit') != BASE_COMMIT
            or not re.fullmatch('[a-f0-9]{40}', str(manifest.get('sourceCommit', '')))):
        raise RuntimeError('DURABILITY_EXPLICIT_PROVENANCE_REQUIRED')
    expected = {NAME}
    for group in ('files', 'testFiles'):
        entries = manifest.get(group)
        if not isinstance(entries, dict) or not entries:
            raise RuntimeError('DURABILITY_EXPLICIT_PAYLOAD_REQUIRED')
        for name, digest in entries.items():
            if (not isinstance(name, str) or PurePosixPath(name).is_absolute()
                    or str(PurePosixPath(name)) != name or '\\' in name or name in expected
                    or any(p in {'', '.', '..'} for p in name.split('/'))
                    or not re.fullmatch('[a-f0-9]{64}', str(digest))):
                raise RuntimeError('DURABILITY_CANONICAL_PATH_REQUIRED')
            file = root / name
            if (any(p.is_symlink() for p in (file, *file.parents)) or not file.is_file()
                    or not 0 < file.stat().st_size <= 4 * 1024**2
                    or hashlib.sha256(file.read_bytes()).hexdigest() != digest):
                raise RuntimeError('DURABILITY_SOURCE_SHA_MISMATCH')
            expected.add(name)
    if not {'manifest.py', 'bootstrap.py', 'runtime_entry.py', 'durable_server.py',
            'durable_backend.py', 'durable_coordinator.py', 'checkpoint.py', 'vault.py',
            'stores.py', 'preflight.py', 'cli.py', 'startup_restore.py', 'parent.py',
            'requirements.txt'} <= set(manifest['files']):
        raise RuntimeError('DURABILITY_CONNECTED_RUNTIME_REQUIRED')
    if root.is_relative_to('/opt'):
        if any(p.is_symlink() for p in root.rglob('*')):
            raise RuntimeError('DURABILITY_SOURCE_SYMLINK_FORBIDDEN')
        if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != expected:
            raise RuntimeError('DURABILITY_UNEXPECTED_PAYLOAD_FILE')
    parent = {'status': 'NOT_EXECUTED', 'reason': 'SOURCE_CHECKOUT_ONLY'}
    if verify_parent:
        from parent import PROXY, load_file
        previous = sys.modules.get('parent')
        try:
            sys.modules['parent'] = load_file('_durability_protected_parent', PROXY / 'parent.py',
                '20f6e5fe6badce1bbdcda88fab17d42f8f629b487e88981815361ac0fce62f63')
            parent = load_file('_durability_protected_manifest', PROXY / 'manifest.py',
                '05f53386267811dbbc2b3a499a5b9114972361ec908636d9af2b2882f98642a1').verify_sources()
        finally:
            if previous is None:
                sys.modules.pop('parent', None)
            else:
                sys.modules['parent'] = previous
        if parent.get('status') != 'PASS' or parent.get('gpuExecuted') is not False:
            raise RuntimeError('DURABILITY_FROZEN_PARENT_CHANGED')
    return {'status': 'PASS', 'manifestSha256': hashlib.sha256(raw).hexdigest(),
            'sourceCommit': manifest['sourceCommit'], 'files': len(expected),
            'parentProxy': parent, 'gpuExecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', required=True)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.source_only and HERE.is_relative_to('/opt'):
            raise RuntimeError('DURABILITY_PARENT_VERIFICATION_REQUIRED')
        print(json.dumps(verify_sources(verify_parent=not args.source_only), sort_keys=True))
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'DURABILITY_MANIFEST_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'gpuExecuted': False}))
        raise SystemExit(1)
