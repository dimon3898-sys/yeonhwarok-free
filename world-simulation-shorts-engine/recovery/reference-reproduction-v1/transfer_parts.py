#!/usr/bin/env python3
"""Split/reassemble original file bytes; no media decoding or transcoding."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def split_file(source, folder, chunk_mib):
    source = source.resolve(strict=True)
    if not source.is_file() or not 1 <= chunk_mib <= 20:
        raise ValueError('Input must be a file; chunks must be 1–20 MiB.')
    # Refuse overwriting previous transfers or the source directory.
    folder.mkdir(parents=True, exist_ok=False)
    original_sha = digest(source)
    original_bytes = source.stat().st_size
    parts = []
    with source.open('rb') as stream:
        while block := stream.read(chunk_mib * 1024 * 1024):
            name = 'reference.part.%04d' % len(parts)
            with (folder / name).open('xb') as target:
                target.write(block)
            parts.append({'name': name, 'bytes': len(block),
                          'sha256': hashlib.sha256(block).hexdigest()})
    if not parts or sum(p['bytes'] for p in parts) != original_bytes or digest(source) != original_sha:
        raise ValueError('Source empty or changed during transfer; retained parts are unverified.')
    manifest = {'format': 'RAW_BYTE_PARTS_V1', 'original_name': source.name,
                'original_bytes': original_bytes, 'original_sha256': original_sha,
                'chunk_mib': chunk_mib, 'media_transcoded': False, 'parts': parts}
    with (folder / 'PARTS_MANIFEST.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return manifest


def join_file(manifest_path, target):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 'RAW_BYTE_PARTS_V1' or not manifest.get('parts'):
        raise ValueError('Unsupported/empty manifest.')
    parts = []
    for index, entry in enumerate(manifest['parts']):
        if entry['name'] != 'reference.part.%04d' % index:
            raise ValueError('Invalid part name or order.')
        path = manifest_path.parent / entry['name']
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('Part size/SHA mismatch: ' + entry['name'])
        parts.append(path)
    if sum(p.stat().st_size for p in parts) != manifest['original_bytes']:
        raise ValueError('Original size mismatch.')
    # Existing originals/outputs are never overwritten.
    with target.open('xb') as output:
        result = hashlib.sha256()
        for path in parts:
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    output.write(block)
                    result.update(block)
    if result.hexdigest() != manifest['original_sha256'] or target.stat().st_size != manifest['original_bytes']:
        raise ValueError('Reassembled file failed original-byte verification; retained for diagnosis.')
    return {'status': 'PASS', 'sha256': result.hexdigest(), 'bytes': target.stat().st_size,
            'media_transcoded': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    split = commands.add_parser('split')
    split.add_argument('source', type=Path)
    split.add_argument('folder', type=Path)
    split.add_argument('--chunk-mib', type=int, default=20)
    join = commands.add_parser('join')
    join.add_argument('manifest', type=Path)
    join.add_argument('output', type=Path)
    args = parser.parse_args()
    result = split_file(args.source, args.folder, args.chunk_mib) if args.command == 'split' else join_file(args.manifest, args.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
