"""Restore only neutral pinned test inputs; never alter a preexisting file."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import zipfile

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
PRIVATE = Path('/workspace/universal-data-pipeline-v1-private-20261022')
PROBES = PRIVATE / 'g2-generic-probes'
SEED_ALIAS = Path('/workspace/exact-65422-capsule-20261020/world-simulation-shorts-engine/recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json')
PDF_ALIAS = Path('/workspace/astra-history-p0-research-20261021/GOVINFO_UN_OFFENSIVE_1950.pdf')
PDF_SHA = '34d1bf77b29304711cef0ca41a9fcbddec0f04bc14ec11d3088f6373b238f41b'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(path, data):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('TEST_FIXTURE_SYMLINK_FORBIDDEN')
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise RuntimeError('TEST_FIXTURE_EXISTING_BYTES_DIFFER')
        return 'REUSED_ACTUAL_IDENTICAL_BYTES'
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)
    return 'NEW_ABSENT_ALIAS_FROM_PINNED_SOURCE'


def setup(pdf=None):
    report = {'schema': 'WORLD_ENGINE_UDP_REGRESSION_FIXTURE_RESTORE_V1', 'files': [],
              'existingFilesOverwritten': False, 'oldCachesReadOrChanged': False,
              'gpuExecuted': False, 'paidWorkExecuted': False}
    manifest_path = ROOT / 'world-simulation-shorts-engine/recovery/exact-65422-reproduction-v1/reports/SOURCE_CAPSULE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes())
    seed_row = next(r for r in manifest['files'] if r['path'].endswith('/reference-reproduction-v1/fixtures/REGIONAL-plan.json'))
    seed = (ROOT / seed_row['path']).read_bytes()
    if sha(seed) != seed_row['sha256'] or len(seed) != seed_row['bytes']:
        raise RuntimeError('ORIGINAL_SEED_PINNED_BYTES_MISMATCH')
    report['files'].append({'target': str(SEED_ALIAS), 'source': seed_row['path'], 'sha256': sha(seed),
                            'bytes': len(seed), 'operation': put(SEED_ALIAS, seed)})
    archive = ROOT / 'world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/fixtures/GENERIC_PROBE_INPUTS.zip'
    archive_raw = archive.read_bytes()
    # The archive itself is protected by the pinned all-tracked-file baseline.
    baseline = json.loads((HERE / 'reports/PROTECTION_BASELINE.json').read_bytes())
    expected = next(r['sha256'] for r in baseline['trackedFiles'] if r['path'] == str(archive.relative_to(ROOT)))
    if sha(archive_raw) != expected:
        raise RuntimeError('ORIGINAL_GENERIC_PROBE_ARCHIVE_CHANGED')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('ORIGINAL_GENERIC_PROBE_ARCHIVE_CORRUPT')
        for info in z.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or '..' in relative.parts or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('UNSAFE_ORIGINAL_FIXTURE_ARCHIVE_PATH')
            if info.is_dir():
                continue
            raw = z.read(info)
            report['files'].append({'target': str(PROBES / relative), 'source': str(archive.relative_to(ROOT)) + ':' + info.filename,
                                   'sha256': sha(raw), 'bytes': len(raw), 'operation': put(PROBES / relative, raw)})
    if pdf:
        raw = Path(pdf).read_bytes()
        if sha(raw) != PDF_SHA or len(raw) != 918062:
            raise RuntimeError('ORIGINAL_OFFICIAL_PDF_HASH_OR_SIZE_MISMATCH')
        report['files'].append({'target': str(PDF_ALIAS), 'source': 'PINNED_OFFICIAL_GOVINFO_CMH_19_7_PDF',
                               'sha256': sha(raw), 'bytes': len(raw), 'operation': put(PDF_ALIAS, raw)})
    report['originalPDF'] = {'path': str(PDF_ALIAS), 'expectedSHA256': PDF_SHA,
                            'status': 'PRESENT_ACTUAL_SHA_MATCH' if PDF_ALIAS.is_file() and sha(PDF_ALIAS.read_bytes()) == PDF_SHA else 'MISSING_REQUIRES_PINNED_ORIGINAL_FOR_ONE_LIVE_SOURCE_TEST'}
    report['status'] = 'PASS' if report['originalPDF']['status'] == 'PRESENT_ACTUAL_SHA_MATCH' else 'PARTIAL_SOURCE_PDF_REQUIRED'
    target = HERE / 'reports/regressions/FIXTURE_RESTORE.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'files': len(report['files']), 'probeRoot': str(PROBES),
                      'originalPDF': report['originalPDF'], 'report': str(target)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-pdf', type=Path)
    setup(parser.parse_args().source_pdf)
