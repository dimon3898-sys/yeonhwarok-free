#!/usr/bin/env python3
"""Stream an explicit public allowlist into immutable review ZIPs and checksums.

No Scene/assets/private files are traversed into a ZIP. PNG bytes are unchanged.
The source renderer/proof is validated, not recreated; this tool cannot render.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_ZIP = 95 * 1024 * 1024
FIXED_TIME = (2026, 10, 20, 0, 0, 0)
FRAME_NAMES = [f'public-review/FRAME_{i:02d}_T{i*5:03d}.png' for i in range(16)]
SHEETS = ['public-review/CONTACT_SHEET_4X4.png', 'public-review/ADJACENT_TRANSITIONS_3X3.png']
REQUIRED_DOCUMENTS = [
    'BASELINE.json', 'STORYBOARD_12_SCENES.md', 'STORY_80S_SOURCE_LEDGER.csv',
    'CAMERA_AND_FRONT_TRACE.csv', 'FRAME_REVIEW_16.csv', 'ADJACENT_FRAME_REVIEW.csv',
    'FRAME_APPLICABILITY_151.csv', 'FRAME_APPLICABILITY_151_BY_FRAME.csv',
    'FRAME_REVIEW_README.md', 'proof/FRAME_RENDER_REPORT.json',
    'reports/HISTORY_AND_SCENE.json', 'reports/ACTUAL_FRAME_REVIEW.json',
    'reports/10_CRITERIA_REVIEW.json', 'reports/FRAME_APPLICABILITY_SUMMARY.json',
    'reports/PUBLIC_REVIEW_MANIFEST.json', 'reports/PROTECTION_AND_INVARIANTS.json',
]
OPTIONAL_DOCUMENTS = [
    'BROWSER_BINDINGS.json', 'DIRECTOR_CAMERA_PROFILE.json', 'CAMERA_DIRECTOR_CONTRACT.md',
    'CAMERA_METADATA_NOTE.md', 'EXACT_REPLAY_INPUTS.md', 'RENDER_PATH_REUSE.md',
    'FINALIZATION.md', 'VALIDATION.json', 'RESULT.json', 'FINAL_RESULT.json',
    'RESULT.md', 'DOWNLOADS.md',
    'IMAGE_METADATA_RECHECK.json', 'IMAGE_METADATA_RECHECK_RETRY.json',
    'reports/HISTORY_CAMERA_TARGETS.json', 'reports/CAMERA_CPU_CONTRACT.json',
    'reports/FINAL_NATIVE_CAMERA_CPU_CONTRACT.json', 'reports/FREE_TEST_RESULTS.json',
    'reports/TEST_RESULTS.json', 'reports/VALIDATION.json', 'reports/RESULT.json',
    'reports/FINAL_RESULT.json', 'reports/SOURCE_PROTECTION.json',
    'reports/SECRET_SCAN.json', 'reports/SECRET_SCAN_RESULT.json',
    'reports/DOWNLOAD_VERIFICATION.json', 'reports/RENDER_PROVENANCE.json',
    'reports/SOURCE_ASSET_MANIFEST.json', 'reports/CAMERA_ACTUAL_PREVIEW_CONTRACT.json',
    'reports/MANUAL_VISUAL_INSPECTION.json', 'reports/PERSISTENCE_RECEIPT.json',
    'proof/SOURCE_CONSUMER_ORACLE.json',
    'reports/CAMERA_ACTUAL_LAYOUT_AFTER_HEADLINE_POLICY.json',
    'runtime_adapter.mjs', 'camera_director.mjs', 'camera_plan.mjs', 'capture_frames.mjs',
    'recheck_image_metadata.py', 'tests/test_actual_frame_review.py',
    'tests/test_camera_plan.mjs', 'tests/test_frame_applicability.py',
    'tests/test_runtime_adapter.mjs', 'tools/build_frame_applicability.py',
    'tools/build_public_review.py', 'tools/build_story_ledger.py',
    'tools/review_actual_frames.py', 'tools/verify_downloads.py',
    'tools/check_protection.py', 'tools/package_review.py', 'tools/verify_source_consumers.mjs',
]


def sha_file(file):
    digest = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file(root, name):
    value = PurePosixPath(name)
    if value.is_absolute() or any(x in ('', '.', '..') for x in value.parts) or '\\' in name or '\0' in name:
        raise ValueError('REVIEW_CANONICAL_RELATIVE_PATH_REQUIRED')
    current = root
    for component in value.parts:
        current /= component
        if current.is_symlink():
            raise ValueError('REVIEW_SYMLINK_FORBIDDEN')
    if not current.is_file() or not stat.S_ISREG(current.stat().st_mode):
        raise ValueError('REVIEW_REGULAR_FILE_REQUIRED_' + name)
    if any(x in {'.private', '__pycache__', 'assets', 'inputs', 'failed_boot', 'probes'} for x in value.parts):
        raise ValueError('REVIEW_PRIVATE_OR_ORIGINAL_ASSET_FORBIDDEN')
    return current


def source_list(root=ROOT):
    report = json.loads(safe_file(root, 'proof/FRAME_RENDER_REPORT.json').read_bytes())
    if report.get('status') != 'FRAME_RENDER_PASS' or len(report.get('frames', [])) != 16:
        raise ValueError('PACKAGE_REQUIRES_COMPLETED_16_ACTUAL_FRAMES')
    if [r.get('globalFrame') for r in report['frames']] != list(range(0, 2400, 150)):
        raise ValueError('PACKAGE_REQUIRES_ORIGINAL_GLOBAL_SAMPLE_INDICES')
    if any(report.get(k) is not False for k in ('oldMovieOrFramesReused', 'paidGpuExecuted',
                                               'nvidiaHardwareVerified', 'mp4Produced', 'visualQualityApproved')):
        raise ValueError('PACKAGE_CAPTURE_SCOPE_MISMATCH')
    adjacent = report.get('adjacentFrames', [])
    if len(adjacent) != 9:
        raise ValueError('PACKAGE_REQUIRES_9_ADJACENT_FRAMES')
    adjacent_names = []
    for row in report['frames'] + adjacent:
        name = row.get('file', '')
        if name not in FRAME_NAMES and not re.fullmatch(r'adjacent/ADJACENT_GLOBAL_[0-9]{4}\.png', name):
            raise ValueError('PACKAGE_UNEXPECTED_FRAME_FILENAME')
        file = safe_file(root, name)
        with file.open('rb') as stream:
            header = stream.read(24)
        if (header[:8] != b'\x89PNG\r\n\x1a\n' or int.from_bytes(header[16:20], 'big') != 1080
                or int.from_bytes(header[20:24], 'big') != 1920):
            raise ValueError('PACKAGE_NATIVE_PNG_DIMENSIONS_REQUIRED')
        if row.get('directRendererOutput') is not True or sha_file(file) != row.get('png_sha256'):
            raise ValueError('PACKAGE_ACTUAL_FRAME_SHA_MISMATCH')
        if name.startswith('adjacent/'):
            adjacent_names.append(name)
    if len(set(adjacent_names)) != 9:
        raise ValueError('PACKAGE_UNIQUE_ADJACENT_FRAMES_REQUIRED')
    for name in FRAME_NAMES + SHEETS + REQUIRED_DOCUMENTS:
        safe_file(root, name)
    protection = json.loads((root / 'reports/PROTECTION_AND_INVARIANTS.json').read_bytes())
    if protection.get('status') != 'PASS' or protection.get('outsideNamespaceChanges'):
        raise ValueError('PACKAGE_PROTECTED_SOURCE_GATE_FAILED')
    if protection.get('captureReportSHA256') != sha_file(root / 'proof/FRAME_RENDER_REPORT.json'):
        raise ValueError('PACKAGE_PROTECTION_RECEIPT_STALE')
    review = json.loads((root / 'reports/10_CRITERIA_REVIEW.json').read_bytes())
    if review.get('visualQualityApproved') is not False or review.get('userReviewRequired') is not True:
        raise ValueError('PACKAGE_MUST_PRESERVE_USER_REVIEW_GATE')
    names = sorted(set(FRAME_NAMES + SHEETS + adjacent_names + REQUIRED_DOCUMENTS +
                       [name for name in OPTIONAL_DOCUMENTS if (root / name).is_file()]))
    return names, {name: {'sha256': sha_file(safe_file(root, name)),
                         'bytes': (root / name).stat().st_size} for name in names}


def zip_entry(archive, name, stream, *, is_png=False):
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o444) << 16
    info.compress_type = zipfile.ZIP_STORED if is_png else zipfile.ZIP_DEFLATED
    with archive.open(info, 'w', force_zip64=True) as output:
        shutil.copyfileobj(stream, output, length=1024 * 1024)


def make_zip(root, target, names, records, temporary):
    staged = temporary / target.name
    with zipfile.ZipFile(staged, 'w', allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in names:
            file = safe_file(root, name)
            before = file.stat()
            with file.open('rb') as stream:
                zip_entry(archive, name, stream, is_png=file.suffix.lower() == '.png')
            after = file.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('PACKAGE_SOURCE_CHANGED_DURING_STREAM')
            if sha_file(file) != records[name]['sha256']:
                raise ValueError('PACKAGE_SOURCE_SHA_CHANGED_DURING_STREAM')
        checksums = ''.join(records[name]['sha256'] + '  ' + name + '\n' for name in names).encode()
        zip_entry(archive, 'SHA256SUMS', io.BytesIO(checksums))
    with zipfile.ZipFile(staged) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(names) | {'SHA256SUMS'}:
            raise ValueError('PACKAGE_ZIP_INTEGRITY_FAILED')
    return staged


def install_immutable(source, target):
    if target.exists():
        if target.is_symlink() or sha_file(source) != sha_file(target):
            raise ValueError('REFUSE_DIFFERENT_EXISTING_ZIP_OVERWRITE_' + target.name)
        return 'EXISTING_IDENTICAL_PRESERVED'
    with target.open('xb') as output, source.open('rb') as stream:
        shutil.copyfileobj(stream, output, length=1024 * 1024)
    if sha_file(target) != sha_file(source):
        raise ValueError('PACKAGE_INSTALLED_SHA_MISMATCH')
    return 'NEW_IMMUTABLE_PACKAGE'


def write_checksums(root=ROOT):
    public = root / 'public-review'
    public_names = [name for name in FRAME_NAMES + SHEETS if (root / name).is_file()]
    if len(public_names) != 18:
        raise ValueError('CHECKSUMS_REQUIRE_18_REVIEW_PNGS')
    (public / 'SHA256SUMS').write_text(''.join(sha_file(safe_file(root, name)) + '  ' + Path(name).name + '\n'
                                             for name in sorted(public_names)))
    handoff = root / 'handoff'
    archives = sorted(p for p in handoff.glob('*.zip') if p.is_file())
    if not archives:
        raise ValueError('CHECKSUMS_REQUIRE_HANDOFF_ARCHIVE')
    (handoff / 'SHA256SUMS').write_text(''.join(sha_file(p) + '  ' + p.name + '\n' for p in archives))
    names = sorted(set(FRAME_NAMES + SHEETS + REQUIRED_DOCUMENTS +
                       [name for name in OPTIONAL_DOCUMENTS if (root / name).is_file()] +
                       [p.relative_to(root).as_posix() for p in archives] +
                       [p.relative_to(root).as_posix() for p in (root / 'adjacent').glob('ADJACENT_GLOBAL_*.png')] +
                       ['public-review/SHA256SUMS', 'handoff/SHA256SUMS'] +
                       (['reports/PACKAGE_MANIFEST.json'] if (root / 'reports/PACKAGE_MANIFEST.json').is_file() else [])))
    (root / 'SHA256SUMS').write_text(''.join(sha_file(safe_file(root, name)) + '  ' + name + '\n' for name in names))
    return {'publicFiles': 18, 'archives': len(archives), 'rootFiles': len(names)}


def package(root=ROOT):
    names, records = source_list(root)
    handoff = root / 'handoff'
    handoff.mkdir(exist_ok=True)
    private = root / '.private'
    private.mkdir(exist_ok=True)
    produced = []
    with tempfile.TemporaryDirectory(prefix='review-package-', dir=private) as location:
        temporary = Path(location)
        candidate_name = 'WORLD_ENGINE_80S_16_ACTUAL_FRAMES_HANDOFF.zip'
        staged = make_zip(root, handoff / candidate_name, names, records, temporary)
        if staged.stat().st_size <= MAX_ZIP:
            groups = [(candidate_name, names, staged)]
        else:
            pictures = [n for n in names if n.endswith('.png')]
            documents = [n for n in names if not n.endswith('.png')]
            balanced = [[], []]
            sizes = [0, 0]
            for name in sorted(pictures, key=lambda n: records[n]['bytes'], reverse=True):
                index = min(range(2), key=sizes.__getitem__)
                balanced[index].append(name)
                sizes[index] += records[name]['bytes']
            groups = []
            for index, members in enumerate(balanced, 1):
                name = f'WORLD_ENGINE_80S_ACTUAL_FRAMES_PART_{index}.zip'
                groups.append((name, sorted(members), make_zip(root, handoff / name, sorted(members), records, temporary)))
            name = 'WORLD_ENGINE_80S_16_ACTUAL_FRAMES_REPORTS.zip'
            groups.append((name, documents, make_zip(root, handoff / name, documents, records, temporary)))
        if any(staged.stat().st_size > MAX_ZIP for _, _, staged in groups):
            raise ValueError('PACKAGE_EXCEEDS_95MIB_SAFE_DOWNLOAD_LIMIT')
        for name, members, staged in groups:
            target = handoff / name
            state = install_immutable(staged, target)
            produced.append({'file': 'handoff/' + name, 'sha256': sha_file(target),
                             'bytes': target.stat().st_size, 'members': len(members), 'state': state})
    manifest = {'schema': 'WORLD_ENGINE_DIRECTOR_PUBLIC_PACKAGE_V1', 'status': 'PASS_PACKAGING_ONLY',
                'artifacts': produced, 'sourceFiles': records,
                'explicitAllowlist': True, 'privateFilesIncluded': False,
                'rawLicensedMapsIncluded': False, 'fullNativeSceneIncluded': False,
                'originalPngBytesUnchanged': True, 'streamedZip': True,
                'nvidiaHardwareVerified': False, 'visualQualityApproved': False,
                'downloadVerification': 'PENDING_ANONYMOUS_HTTP200_AND_SHA_AFTER_REMOTE_COMMIT'}
    (root / 'reports/PACKAGE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    counts = write_checksums(root)
    return {'status': manifest['status'], 'artifacts': produced, 'checksums': counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checksums-only', action='store_true',
                        help='Refresh checksum receipts after a later download-validation receipt; do not rebuild the immutable ZIP.')
    args = parser.parse_args()
    result = write_checksums() if args.checksums_only else package()
    print(json.dumps(result, ensure_ascii=False))
