"""Arrange real PNGs only, then package allowlisted review evidence. No frame is edited."""
from pathlib import Path
import hashlib
import json
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((ROOT / 'proof/FRAME_RENDER_REPORT.json').read_text())
    assert report['status'] == 'FRAME_RENDER_PASS' and len(report['frames']) == 16
    assert [r['globalFrame'] for r in report['frames']] == list(range(0, 2400, 150))
    for row in [*report['frames'], *report['adjacentFrames']]:
        path = ROOT / row['file']
        assert row['directRendererOutput'] and sha(path) == row['png_sha256']
        with Image.open(path) as image:
            assert image.size == (1080, 1920)
    public = ROOT / 'public-review'
    sheet = public / 'CONTACT_SHEET_4X4.png'
    assert not sheet.exists(), 'REFUSE_EXISTING_CONTACT_SHEET_OVERWRITE'
    canvas = Image.new('RGB', (2160, 3840))
    for index, row in enumerate(report['frames']):
        with Image.open(ROOT / row['file']) as image:
            thumbnail = image.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS)
            canvas.paste(thumbnail, ((index % 4) * 540, (index // 4) * 960))
    canvas.save(sheet, optimize=True)
    adjacent = public / 'ADJACENT_TRANSITIONS_3X3.png'
    assert not adjacent.exists(), 'REFUSE_EXISTING_ADJACENT_SHEET_OVERWRITE'
    canvas = Image.new('RGB', (1620, 2880))
    for index, row in enumerate(report['adjacentFrames']):
        with Image.open(ROOT / row['file']) as image:
            canvas.paste(image.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS),
                         ((index % 3) * 540, (index // 3) * 960))
    canvas.save(adjacent, optimize=True)
    manifest = {'schema': 'ACTUAL_16_FRAME_PUBLIC_REVIEW_V1', 'previewKind': 'SOFTWARE_PREVIEW',
        'sourceCheckoutCommit': report['sourceCheckoutCommit'], 'sourcePlanSHA256': report['sourcePlanSHA256'],
        'frames': [{k: row[k] for k in ('sampleIndex', 'globalFrame', 'timeSeconds', 'file', 'png_sha256', 'bytes')}
                   for row in report['frames']],
        'contactSheet': {'file': sheet.name, 'sha256': sha(sheet), 'layout': '4x4 source order, no labels or synthesized content'},
        'adjacentSheet': {'file': adjacent.name, 'sha256': sha(adjacent),
                          'globalFrames': [row['globalFrame'] for row in report['adjacentFrames']]},
        'originalPngFilesModified': False, 'aiImagesUsed': False, 'movieFramesUsed': False,
        'mp4Created': False, 'nvidiaHardwareVerified': False, 'visualQualityApproved': False}
    (ROOT / 'reports/PUBLIC_REVIEW_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    files = sorted(p for p in public.iterdir() if p.is_file() and p.suffix == '.png')
    assert len(files) == 18
    (public / 'SHA256SUMS').write_text(''.join(sha(f) + '  ' + f.name + '\n' for f in files))
    print(json.dumps({'status': 'ACTUAL_PNG_SHEETS_PREPARED', 'individualFrames': 16,
                      'contactSheet': str(sheet), 'adjacentSamples': 9}))


if __name__ == '__main__':
    main()
