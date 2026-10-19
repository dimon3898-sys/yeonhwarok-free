#!/usr/bin/env python3
"""Read-only tracked-source and still-capture invariants; never grants GPU use."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
BASE = '3cd19dafe450666748ee16d4aed45c38b4fc65ed'


def check(root=ROOT, repo=REPO):
    allowed = root.relative_to(repo).as_posix() + '/'
    result = subprocess.run(['git', 'diff', '--name-only', '-z', BASE, '--'], cwd=repo,
                            capture_output=True, check=True)
    paths = [x.decode('utf-8') for x in result.stdout.split(b'\0') if x]
    forbidden = [p for p in paths if not p.startswith(allowed)]
    report_file = root / 'proof/FRAME_RENDER_REPORT.json'
    raw = report_file.read_bytes()
    report = json.loads(raw)
    expected = list(range(0, 2400, 150))
    assertions = {
        'oldFinalAndOutsideNamespaceTrackedChangesZero': not forbidden,
        'actualFrameRenderComplete': report.get('status') == 'FRAME_RENDER_PASS',
        'exact16GlobalSampleIndices': [r.get('globalFrame') for r in report.get('frames', [])] == expected,
        'exact9AdjacentSamples': len(report.get('adjacentFrames', [])) == 9,
        'oneRuntime': report.get('oneRuntime') is True,
        'noSceneReinitialization': report.get('sceneReinitializedPerFrame') is False,
        'noOldMovieOrFrameReuse': report.get('oldMovieOrFramesReused') is False,
        'noPaidGpu': report.get('paidGpuExecuted') is False,
        'noNvidiaClaim': report.get('nvidiaHardwareVerified') is False,
        'noMp4Produced': report.get('mp4Produced') is False,
        'noVisualQualityApproval': report.get('visualQualityApproved') is False,
        'actualDrawReadPixelsCapture': report.get('captureKind') == 'ACTUAL_WORLD_ENGINE_WEBGL2_DRAW_READPIXELS_CANVAS_PNG',
        'softwareBackendExplicit': 'SwiftShader' in report.get('backend', ''),
        'sourceCommitRecorded': bool(re.fullmatch('[a-f0-9]{40}', report.get('sourceCheckoutCommit', ''))),
    }
    movies = sorted(p.relative_to(root).as_posix() for p in root.rglob('*')
                    if p.is_file() and p.suffix.lower() in {'.mp4', '.mov', '.webm', '.avi', '.mkv'})
    assertions['noMovieArtifactsInTaskNamespace'] = not movies
    baseline = json.loads((root / 'BASELINE.json').read_bytes())
    assertions['imageGenerationForbiddenByRecordedMaster'] = baseline.get('imageGenerationAllowed') is False
    assertions['full80sAnd5sMp4ForbiddenByRecordedMaster'] = (baseline.get('full80sMp4Allowed') is False
                                                           and baseline.get('fiveSecondMp4Allowed') is False)
    assertions['paidGpuForbiddenByRecordedMaster'] = baseline.get('paidGpuAllowed') is False
    public = root / 'reports/PUBLIC_REVIEW_MANIFEST.json'
    if public.is_file():
        manifest = json.loads(public.read_bytes())
        assertions['noAiImagesInPublicReview'] = manifest.get('aiImagesUsed') is False
        assertions['noMovieFramesInPublicReview'] = manifest.get('movieFramesUsed') is False
        assertions['originalPngsNotModifiedForContactSheet'] = manifest.get('originalPngFilesModified') is False
    else:
        assertions['publicReviewManifestAvailable'] = False
    return {'schema': 'WORLD_ENGINE_DIRECTOR_PROTECTION_AND_INVARIANTS_V1',
            'status': 'PASS' if all(assertions.values()) else 'FAIL', 'baselineCommit': BASE,
            'scope': 'Read-only Git tracked-byte comparison plus actual capture provenance assertions; not a security audit or GPU proof.',
            'allowedNamespace': allowed, 'changedTrackedPaths': paths,
            'outsideNamespaceChanges': forbidden, 'existingFinalChangedFiles': len(forbidden),
            'assertions': assertions, 'movieArtifacts': movies,
            'captureReportSHA256': hashlib.sha256(raw).hexdigest(),
            'visualQualityApproved': False, 'nvidiaHardwareVerified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/PROTECTION_AND_INVARIANTS.json')
    args = parser.parse_args()
    value = check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': value['status'], 'outsideNamespaceChanges': value['outsideNamespaceChanges'],
                      'assertions': len(value['assertions'])}))
    raise SystemExit(0 if value['status'] == 'PASS' else 1)
