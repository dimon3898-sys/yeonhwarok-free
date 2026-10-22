"""Deterministic public handoff, no source reference media or fabricated output."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
NAME = 'WORLD_ENGINE_REFERENCE_DIRECTOR_V1_REVIEW.zip'
POST_DOWNLOAD_RECEIPTS = {'reports/PUBLIC_DOWNLOAD_VERIFICATION.json'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def package():
    snapshot = []
    for path in sorted(HERE.rglob('*')):
        relative = path.relative_to(HERE).as_posix()
        if (not path.is_file() or relative.startswith('public-review/')
                or relative in POST_DOWNLOAD_RECEIPTS or relative == 'SHA256SUMS'):
            continue
        if path.is_symlink() or '__pycache__' in path.parts:
            raise RuntimeError('RD_UNSAFE_PUBLIC_FILE')
        if path.suffix.lower() in {'.mp4', '.mov', '.jpg', '.jpeg'}:
            raise RuntimeError('RD_NO_UNLICENSED_REFERENCE_OR_UNRENDERED_MOVIE')
        if path.suffix.lower() == '.png' and relative != 'evidence/EVENT_COMPONENT_DRAW.png':
            raise RuntimeError('RD_NO_REFERENCE_SCREENSHOT_OR_FAKE_COMPARISON')
        raw = path.read_bytes()
        snapshot.append((relative, raw))
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
    raw = (output / NAME).read_bytes()
    (output / 'SHA256SUMS').write_text(f'{sha(raw)}  {NAME}\n')
    with zipfile.ZipFile(output / NAME) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('RD_ZIP_CRC_FAILED')
        for relative, expected in snapshot:
            if archive.read(relative) != expected:
                raise RuntimeError('RD_ZIP_INTERNAL_SHA_MISMATCH')
    return {'schema': 'WORLD_ENGINE_REFERENCE_REVIEW_PACKAGE_V1',
            'sourceCheckpoint': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            'name': NAME, 'sha256': sha(raw), 'bytes': len(raw), 'entries': len(snapshot),
            'internalSHA256AndZipCRCVerified': True, 'sourceVideoIncluded': False,
            'referenceScreenshotsIncluded': False, 'studioMP4Included': False,
            'componentImageOnly': 'evidence/EVENT_COMPONENT_DRAW.png',
            'checksumScope': 'Files enumerated in root SHA256SUMS; public archive/checksum and subsequent external-download receipts excluded'}


if __name__ == '__main__':
    result = package()
    with (HERE / 'public-review/PACKAGE_RECEIPT.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
