"""Package only the new namespace's public, non-secret recovery evidence."""
from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile

HERE = Path(__file__).resolve().parents[1]
EXCLUDED = {'SHA256SUMS', 'public-review/SHA256SUMS', 'reports/CHANGE_FILES.csv',
            'reports/DOWNLOAD_VERIFICATION.json', 'reports/SESSION_CHECKPOINT.json',
            'reports/PACKAGE_MANIFEST.json'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def selected_files():
    for f in sorted(HERE.rglob('*')):
        if not f.is_file() or f.is_symlink():
            continue
        name = f.relative_to(HERE).as_posix()
        if name in EXCLUDED or name.split('/')[0] in {'captures', '__pycache__', 'review-package'}:
            continue
        if '__pycache__' in f.parts:
            continue
        yield name, f

def main():
    gates = json.loads((HERE / 'reports/GATES.json').read_text())
    assert gates['phase2']['status'] == 'FAIL'
    assert gates['phase3']['actualStudio180FrameJobStarted'] is False
    assert not list((HERE / 'public-review').glob('*.mp4'))
    files = list(selected_files())
    rows = [{'path': n, 'bytes': f.stat().st_size, 'sha256': sha(f.read_bytes())} for n, f in files]
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=['path', 'bytes', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)
    (HERE / 'reports/CHANGE_FILES.csv').write_text(csv_buffer.getvalue())
    # Large native terrain PNGs stay individually hash-bound in Git. No source TIFF,
    # private auth/session files, job roots, old caches or fabricated MP4 enter this ZIP.
    archive_files = [(n, f) for n, f in files if not n.startswith('assets/')]
    archive_files.append(('reports/CHANGE_FILES.csv', HERE / 'reports/CHANGE_FILES.csv'))
    manifest = {'schema': 'WORLD_ENGINE_G2_RECOVERY_PACKAGE_V1',
                'status': 'G2_NEEDS_REWORK_PHASE3_NOT_STARTED',
                'excludedLargeAssetsAvailableInRepository': [r for r in rows if r['path'].startswith('assets/')],
                'excludedPrivateFiles': True, 'newMP4Included': False,
                'files': [{'path': n, 'bytes': f.stat().st_size, 'sha256': sha(f.read_bytes())}
                          for n, f in archive_files]}
    manifest_raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode()
    (HERE / 'reports/PACKAGE_MANIFEST.json').write_bytes(manifest_raw)
    archive = HERE / 'review-package/G2_RECOVERY_EVIDENCE.zip'
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n, f in archive_files:
            info = zipfile.ZipInfo(n, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, f.read_bytes())
        z.writestr('PACKAGE_MANIFEST.json', manifest_raw)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(sha(z.read(r['path'])) == r['sha256'] for r in manifest['files'])
        assert not any(n.startswith('/') or '..' in Path(n).parts for n in z.namelist())
    assert archive.stat().st_size < 32 * 1024 * 1024
    public_rows = [(p.name, p) for p in sorted((HERE / 'public-review').glob('*.png'))]
    (HERE / 'public-review/SHA256SUMS').write_text(''.join(sha(f.read_bytes()) + '  ' + n + '\n' for n, f in public_rows))
    deliverables = [(f'public-review/{n}', f) for n, f in public_rows]
    deliverables += [('review-package/G2_RECOVERY_EVIDENCE.zip', archive)]
    deliverables += [(n, HERE / n) for n in ['README.md', 'ROOT_CAUSE_REPORT.md', 'CHANGE_MANIFEST.md',
        'TEST_REPORT.md', 'FRAME_AUDIT.md', 'G2_GATE_DECISION.md', 'reports/GATES.json',
        'reports/PROTECTION_FINAL.json', 'reports/CHANGE_FILES.csv', 'reports/PACKAGE_MANIFEST.json']]
    (HERE / 'SHA256SUMS').write_text(''.join(sha(f.read_bytes()) + '  ' + n + '\n' for n, f in deliverables))
    print(json.dumps({'status': 'PASS', 'archiveBytes': archive.stat().st_size,
                      'archiveSHA256': sha(archive.read_bytes()), 'zipFiles': len(archive_files) + 1,
                      'newMP4': False, 'sourceAssetFilesInGit': 3}))

if __name__ == '__main__':
    main()
