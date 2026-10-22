"""Deterministic source/evidence handoff; no reference media or invented movie.

Prepare the actual authorized source and copied license notices first, then run
the bounded scanner, and package only the identical scanned file snapshot.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
LIVE = REPO / 'world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs'
NAME = 'WORLD_ENGINE_REFERENCE_DIRECTOR_V2_REVIEW.zip'
EXCLUDED = {'SHA256SUMS', 'reports/PUBLIC_DOWNLOAD_VERIFICATION.json'}
NOTICES = {
    'THREE_LICENSE.txt': 'world-simulation-shorts-engine/web/vendor/three/0.170.0/LICENSE',
    'NOTO_CJK_LICENSE.txt': 'world-simulation-shorts-engine/web/fonts/LICENSE_Noto_CJK.txt',
    'GLOBAL_RGB_SOURCE_README.md': 'cinematic-world-map/assets/v3/earth/SOURCE_README.md',
    'EARTH_CREDITS_V3.txt': 'cinematic-world-map/assets/v3/CREDITS_V3.txt',
    'NATURAL_EARTH_PUBLIC_DOMAIN.txt': 'world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/source-provenance/NATURAL_EARTH_PUBLIC_DOMAIN.txt',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new_or_identical(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise RuntimeError('R2_PUBLIC_PREPARED_FILE_CONFLICT:' + str(path.relative_to(HERE)))
        return
    with path.open('xb') as stream:
        stream.write(raw)


def prepare(expected):
    if not re.fullmatch(r'[0-9a-f]{64}', expected or ''):
        raise RuntimeError('R2_EXPECTED_RENDERER_SHA256_REQUIRED')
    if LIVE.is_symlink() or not LIVE.is_file():
        raise RuntimeError('R2_LIVE_RENDERER_MUST_BE_REGULAR_FILE')
    raw = LIVE.read_bytes()
    if sha(raw) != expected:
        raise RuntimeError('R2_LIVE_RENDERER_SHA_CHANGED')
    write_new_or_identical(HERE / 'authorized-source/renderer.mjs', raw)
    rows = []
    for name, original in NOTICES.items():
        data = (REPO / original).read_bytes()
        destination = 'licenses/' + name
        write_new_or_identical(HERE / destination, data)
        rows.append({'path': destination, 'copiedFrom': original, 'sha256': sha(data),
            'scope': 'Existing retained notice; not a license grant for missing detailed source data'})
    receipt = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_REVIEW_SOURCE_SNAPSHOT_V2',
        'liveSourcePath': LIVE.relative_to(REPO).as_posix(), 'liveSourceSHA256': expected,
        'includedExactCopy': 'authorized-source/renderer.mjs',
        'originalPreservedBackup': 'backups/renderer.5cc9b98.original.mjs',
        'licenseNotices': rows, 'referenceVideoOrKeyframesCopied': False,
        'privateFilesCopied': False, 'gpuOrQualityPassClaimed': False}
    write_new_or_identical(HERE / 'AUTHORIZED_SOURCE_RECEIPT.json',
        (json.dumps(receipt, indent=2) + '\n').encode())
    print(json.dumps({'preparedActualRendererSHA256': expected, 'noticesCopied': len(rows)}))


def files():
    result = []
    for path in sorted(HERE.rglob('*')):
        relative = path.relative_to(HERE).as_posix()
        if relative.startswith('public-review/') or relative in EXCLUDED:
            continue
        if path.is_symlink():
            raise RuntimeError('R2_PUBLIC_SYMLINK_FORBIDDEN:' + relative)
        if not path.is_file():
            continue
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            raise RuntimeError('R2_PUBLIC_BYTECODE_FORBIDDEN:' + relative)
        result.append((relative, path.read_bytes()))
    return result


def package():
    receipt = json.loads((HERE / 'AUTHORIZED_SOURCE_RECEIPT.json').read_bytes())
    if sha(LIVE.read_bytes()) != receipt['liveSourceSHA256']:
        raise RuntimeError('R2_LIVE_RENDERER_CHANGED_AFTER_PUBLIC_PREPARE')
    if sha((HERE / receipt['includedExactCopy']).read_bytes()) != receipt['liveSourceSHA256']:
        raise RuntimeError('R2_PUBLIC_RENDERER_COPY_CHANGED')
    scan = json.loads((HERE / 'reports/SECRET_SCAN.json').read_bytes())
    if scan['status'] != 'PASS' or scan['findings']:
        raise RuntimeError('R2_CURRENT_PUBLIC_SECRET_PATTERN_SCAN_REQUIRED')
    snapshot = files()
    current_scan = {p: sha(raw) for p, raw in snapshot if p != 'reports/SECRET_SCAN.json'}
    expected_scan = {r['path']: r['sha256'] for r in scan['fileSnapshot']}
    if current_scan != expected_scan:
        raise RuntimeError('R2_PUBLIC_FILES_CHANGED_AFTER_SCAN')
    allow = json.loads((HERE / 'PUBLIC_MEDIA_ALLOWLIST.json').read_bytes())
    allowed = {r['path']: r for r in allow['files']}
    images = []
    for relative, raw in snapshot:
        suffix = Path(relative).suffix.lower()
        if suffix in {'.mp4', '.mov', '.jpg', '.jpeg', '.webp', '.gif'}:
            raise RuntimeError('R2_NO_ORIGINAL_REFERENCE_OR_UNRENDERED_MEDIA:' + relative)
        if suffix == '.png':
            row = allowed.get(relative)
            if not row or row['sha256'] != sha(raw) or row['origin'] != 'ACTUAL_NEW_NATIVE_OR_COMPONENT_DRAW':
                raise RuntimeError('R2_PNG_NOT_EXPLICITLY_REVIEWED:' + relative)
            images.append(relative)
    if set(images) != set(allowed):
        raise RuntimeError('R2_MEDIA_ALLOWLIST_CONTAINS_MISSING_OR_NON_PNG_ENTRY')
    checksums = ''.join(f'{sha(raw)}  {relative}\n' for relative, raw in snapshot).encode()
    with (HERE / 'SHA256SUMS').open('xb') as stream:
        stream.write(checksums)
    snapshot.append(('SHA256SUMS', checksums))
    output = HERE / 'public-review'
    output.mkdir(exist_ok=False)
    with zipfile.ZipFile(output / NAME, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, raw in sorted(snapshot):
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    archive_raw = (output / NAME).read_bytes()
    with zipfile.ZipFile(output / NAME) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('R2_ZIP_CRC_FAILED')
        for relative, raw in snapshot:
            if archive.read(relative) != raw:
                raise RuntimeError('R2_ZIP_INTERNAL_SHA_MISMATCH')
    summary = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_REVIEW_PACKAGE_V2',
        'sourceCheckpoint': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'name': NAME, 'sha256': sha(archive_raw), 'bytes': len(archive_raw), 'entries': len(snapshot),
        'internalSHA256AndZipCRCVerified': True,
        'actualRendererSHA256': receipt['liveSourceSHA256'],
        'originalVideoOrReferenceKeyframesIncluded': False, 'studioMP4Included': False,
        'actualNewNativeOrComponentImages': images, 'paidGpuOrApiUsed': False,
        'qualityPassClaimedByPackager': False,
        'checksumScope': 'Root SHA256SUMS covers enumerated source/evidence files; archive checksum and subsequent external-download receipt are outside the archive to avoid circular hashes.'}
    with (output / 'SHA256SUMS').open('x') as stream:
        stream.write(f'{sha(archive_raw)}  {NAME}\n')
    with (output / 'PACKAGE_RECEIPT.json').open('x') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    with (output / 'FILE_INVENTORY.csv').open('x') as stream:
        import csv
        writer = csv.writer(stream)
        writer.writerow(['relativePath', 'bytes', 'sha256'])
        writer.writerows((name, len(raw), sha(raw)) for name, raw in sorted(snapshot))
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-renderer', action='store_true')
    parser.add_argument('--expected-renderer-sha256')
    args = parser.parse_args()
    prepare(args.expected_renderer_sha256) if args.prepare_renderer else package()
