"""Build a deterministic, selective public review bundle without private job state."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parents[1]


def sha(file):
    digest = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sums(directory):
    files = sorted(file for file in directory.iterdir() if file.is_file() and file.name != 'SHA256SUMS')
    (directory / 'SHA256SUMS').write_text(''.join(sha(file) + '  ' + file.name + '\n' for file in files))


if __name__ == '__main__':
    gates = json.loads((HERE / 'reports/GATES.json').read_bytes())
    if (gates['phaseF'].get('status') != 'PASS' or gates['phaseG'].get('status') != 'PASS'
            or gates.get('historicalG3') != 'BLOCKED' or gates.get('paidGpuExecuted') is not False):
        raise ValueError('VERIFIED_FREE_STUDIO_AND_REGRESSION_GATES_REQUIRED')
    sums(HERE / 'public-review')
    review = HERE / 'review-package'
    review.mkdir(exist_ok=True)
    archive = review / 'WORLD_ENGINE_UNIVERSAL_DATA_REVIEW.zip'
    if archive.exists():
        raise ValueError('REFUSE_EXISTING_REVIEW_ARCHIVE')
    files = []
    for file in sorted(HERE.rglob('*')):
        if file.is_symlink():
            raise ValueError('REVIEW_SYMLINK_FORBIDDEN')
        if not file.is_file():
            continue
        relative = file.relative_to(HERE)
        if relative.parts[0] == 'review-package' or file.name in {'DOWNLOAD_VERIFICATION.json', 'SHA256SUMS'}:
            continue
        # Avoid duplicating large full-resolution checkpoints. The public Git
        # paths retain those originals; include actual comparison sheets and
        # full movies in the mobile review ZIP.
        if file.suffix.lower() == '.png' and ('COMPARISON' not in file.name and 'CONTACT_SHEET' not in file.name):
            continue
        files.append(file)
    manifest = [{'path': file.relative_to(HERE).as_posix(), 'bytes': file.stat().st_size,
                 'sha256': sha(file)} for file in files]
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for file in files:
            info = zipfile.ZipInfo(file.relative_to(HERE).as_posix(), (2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, file.read_bytes())
        output.writestr('BUNDLE_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None:
            raise ValueError('REVIEW_ZIP_CRC_FAILED')
        for item in manifest:
            if hashlib.sha256(check.read(item['path'])).hexdigest() != item['sha256']:
                raise ValueError('REVIEW_ZIP_CONTENT_SHA_FAILED')
    # One short file is enough for mobile users to check the primary downloads.
    primary = [archive, *(HERE / 'public-review' / name for name in [
        'AVIATION_DEMO.mp4', 'FICTIONAL_AREA_DEMO.mp4', 'TRADE_DEMO.mp4',
        'STUDIO_THREE_TOPIC_CONTACT_SHEET.png'])]
    text = ''.join(sha(file) + '  ' + file.relative_to(HERE).as_posix() + '\n' for file in primary)
    (HERE / 'SHA256SUMS').write_text(text)
    (review / 'SHA256SUMS').write_text(text)
    print(json.dumps({'archive': str(archive.relative_to(HERE)), 'bytes': archive.stat().st_size,
                      'sha256': sha(archive), 'files': len(manifest), 'zipCRC': 'PASS',
                      'allBundledFileSHA256': 'PASS', 'privateJobStateIncluded': False}))
