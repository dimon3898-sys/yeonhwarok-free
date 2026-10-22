"""Reuse the preserved whole-video audit and add actual current-camera layout proof.

This tool decodes an already completed Studio output. It does not render, change
terrain, relax the frozen support-edge thresholds, or approve visual quality.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
PREVIOUS = HERE.parent / 'g2-renderer-recovery-v1'
BASELINE_MEASUREMENTS_SHA256 = '4e14f9d0728808a4b59a9726023e27888347584403906a973d78fadbc4bb5910'
LAYOUT_SOURCE = 'SAME_FACTORY_GLYPH_MEASURE_CALLBACK_AND_CALLER_CURRENT_FACTORY_SCREEN'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_preserved_auditor():
    spec = importlib.util.spec_from_file_location(
        '_g2_final_preserved_frame_audit', PREVIOUS / 'tools/audit_recovery_video.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    # OLD still identifies the original immutable source-pipeline movie/report;
    # REPO remains the same repository root. Only new report outputs relocate.
    return module


def layout_checks(capture, semantic_equal):
    rows = []
    for index, frame in enumerate(capture.get('frames', [])):
        diagnostic = frame.get('diagnostic', {})
        layout = diagnostic.get('layoutAudit', {})
        location = layout.get('location', {})
        dimensions = location.get('inkDimensions')
        checks = {
            'frameOrder': frame.get('frame') == index,
            'actualCurrentCameraAndGlyphMeasurements': (
                layout.get('schema') == 'WORLD_ENGINE_DYNAMIC_LAYOUT_AUDIT_V1'
                and layout.get('measurement') == 'SAME_FACTORY_GLYPH_MEASURE_CALLBACK'
                and layout.get('projection') == 'CALLER_CURRENT_FACTORY_SCREEN'),
            'valid': layout.get('valid') is True,
            'noFailures': layout.get('failures') == [],
            'noGraphicCollisions': layout.get('collisions') == [],
            'noBoundaryCollisions': layout.get('boundaryCollisions') == [],
            'noSafeAreaViolations': layout.get('safeArea', {}).get('violations') == [],
            'sameProjectedGeographicAnchor': semantic_equal(layout.get('anchor'), diagnostic.get('projectEventPoint')),
            'selectedLocationRetained': location.get('role') == 'LOCATION_LABEL',
            'actualMeasuredGlyphDimensions': isinstance(dimensions, list) and len(dimensions) == 2 and all(type(n) in (float, int) and n > 0 for n in dimensions),
            'selectedPlacementPassed': location.get('placement', {}).get('fit') is True,
            # The inherited runtime deliberately renders only its marker and
            # SYNTHETIC caption. These layout measurements must not be labelled
            # as visible LOCATION_LABEL pixels.
            'nativeLocationVisibilityReportedHonestly': layout.get('nativeLocationRendered') is False,
            'layoutMeasurementNotClaimedAsDrawnPixels': layout.get('visibleLabelRenderingClaimed') is False and layout.get('diagnosticOnly') is True,
        }
        rows.append({'frame': frame.get('frame'), 'checks': checks,
                     'status': 'PASS' if all(checks.values()) else 'FAIL',
                     'locationInkBox': location.get('inkBox'),
                     'locationPlacement': location.get('placement'),
                     'locationRecovery': layout.get('locationRecovery')})
    passed = len(rows) == 180 and all(r['status'] == 'PASS' for r in rows)
    return {'schema': 'WORLD_ENGINE_G2_FINAL_LAYOUT_FRAME_AUDIT_V1',
            'status': 'PASS' if passed else 'FAIL', 'framesChecked': len(rows),
            'source': LAYOUT_SOURCE, 'actualLocationGlyphPixelsRendered': False,
            'visibleGraphics': ['UNCHANGED_NATIVE_MARKER', 'UNCHANGED_SYNTHETIC_CAPTION'],
            'qualityApproved': False,
            'scope': 'Actual font measurements and actual current runtime projection; collision-safe hypothetical active-location placement, not a new visible-label render path.',
            'frames': rows}


def audit(capture_root, decoded_root, baseline_decoded_root, terrain_receipt):
    gates = json.loads((HERE / 'reports/GATES.json').read_bytes())
    if any(gates.get(name, {}).get('status') != 'PASS' for name in ('phaseA', 'phaseB', 'phaseC')):
        raise ValueError('FINAL_FRAME_AUDIT_PREREQUISITE_GATES_REQUIRED')
    if gates.get('historicalG3') != 'BLOCKED':
        raise ValueError('FINAL_FRAME_AUDIT_G3_MUST_REMAIN_BLOCKED')
    capture_path = Path(capture_root) / 'proof/CAPTURE_REPORT.json'
    capture = json.loads(capture_path.read_bytes())
    if capture.get('video', {}).get('file') != 'G2_FINAL_DEMO_6S.mp4':
        raise ValueError('FINAL_FRAME_AUDIT_EXACT_STUDIO_VIDEO_REQUIRED')
    baseline_raw = (PREVIOUS / 'reports/BASELINE_VIDEO_AUDIT.json').read_bytes()
    if sha(baseline_raw) != BASELINE_MEASUREMENTS_SHA256:
        raise ValueError('FINAL_FRAME_AUDIT_BASELINE_MEASUREMENTS_CHANGED')
    copied = HERE / 'reports/BASELINE_VIDEO_AUDIT.json'
    if copied.exists():
        if copied.is_symlink() or copied.read_bytes() != baseline_raw:
            raise ValueError('FINAL_FRAME_AUDIT_BASELINE_COPY_CONFLICT')
    else:
        copied.write_bytes(baseline_raw)
    reused = load_preserved_auditor()
    result = reused.audit(capture_root, decoded_root, baseline_decoded_root, terrain_receipt)
    layout = layout_checks(capture, reused.semantic_equal)
    layout_path = HERE / 'reports/FINAL_LAYOUT_FRAME_AUDIT.json'
    if layout_path.exists():
        raise ValueError('FINAL_FRAME_AUDIT_REFUSE_EXISTING_LAYOUT_OUTPUT')
    layout_path.write_text(json.dumps(layout, indent=2) + '\n')
    result['schema'] = 'WORLD_ENGINE_G2_FINAL_FRAME_AUDIT_V1'
    result['technicalChecks']['actualCurrentCameraLayoutAdmission'] = layout['status'] == 'PASS'
    result['technicalStatus'] = 'PASS' if all(result['technicalChecks'].values()) else 'NEEDS_REWORK'
    result['qualityDecision'] = 'QUALITY_REVIEW_REQUIRED' if result['technicalStatus'] == 'PASS' else 'NEEDS_REWORK'
    result['actualCurrentCameraLayout'] = {
        'report': 'reports/FINAL_LAYOUT_FRAME_AUDIT.json',
        'sha256': sha(layout_path.read_bytes()), 'status': layout['status'],
        'framesChecked': layout['framesChecked'],
        'nativeLocationLabelPixelsRendered': False,
        'visibleGraphics': layout['visibleGraphics'],
    }
    result['baselineMeasurementSHA256'] = BASELINE_MEASUREMENTS_SHA256
    result['preservedAuditSourceSHA256'] = sha((PREVIOUS / 'tools/audit_recovery_video.py').read_bytes())
    result['manualVisualReviewPerformedByThisScript'] = False
    (HERE / 'reports/RECOVERY_FRAME_AUDIT.json').write_text(json.dumps(result, indent=2) + '\n')
    md = HERE / 'FRAME_AUDIT.md'
    text = md.read_text()
    text += ('\n\n## Final recovery layout evidence\n\n'
             f"Overall technical status after current-camera layout checks: {result['technicalStatus']}. "
             f"Visual status: {result['qualityDecision']}; user approval remains required.\n\n"
             f"Current-camera layout checks: {layout['status']}, {layout['framesChecked']}/180 frames. "
             'The original location label stays selected and is measured with the actual font and projection. '
             'The unchanged source runtime does not draw its native LOCATION_LABEL; it draws the marker and '
             'the SYNTHETIC caption. These checks prove layout admission and collision safety, not visible '
             'location-label pixel quality. No label deletion or collision-check bypass is inferred.\n\n'
             'Detailed per-frame evidence: `reports/FINAL_LAYOUT_FRAME_AUDIT.json`. '
             'All 180 original comparison measurements and support-edge thresholds were reused unchanged.\n')
    md.write_text(text)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-root', type=Path, required=True)
    parser.add_argument('--decoded-root', type=Path, default=Path('/workspace/g2-final-recovery-decoded-video-20261022'))
    parser.add_argument('--baseline-decoded-root', type=Path, default=Path('/workspace/g2-recovery-baseline-video/decoded-frames'))
    parser.add_argument('--terrain-receipt', type=Path, default=PREVIOUS / 'fixtures/RECOVERY_STYLE_RECEIPT.json')
    args = parser.parse_args()
    result = audit(args.capture_root, args.decoded_root, args.baseline_decoded_root, args.terrain_receipt)
    print(json.dumps({'technicalStatus': result['technicalStatus'], 'qualityDecision': result['qualityDecision'],
                      'checks': result['technicalChecks'], 'formerEdgeDiagnostics': result['formerEdgeDiagnostics']}))
