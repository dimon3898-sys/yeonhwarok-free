"""Attach feature-specific software consumer witnesses to the preserved 151 rows.

No literal GL draw-call counter is inferred from frame counts. Shader selection,
material upload, source-front draw reports, pixel contribution and visual quality
remain different evidence levels. This tool cannot authorize production or GPU.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEX = re.compile(r"[0-9a-f]{64}\Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def finite_bounds(value):
    return (isinstance(value, list) and len(value) == 4
        and all(type(x) in (int, float) for x in value)
        and value[0] < value[2] and value[1] < value[3])


def expected_capture_frames(document):
    frames = set(document.get('stillsRequested', []))
    if document.get('stillsRequested') != list(range(0, 2400, 150)):
        raise ValueError('ACTUAL_COMPLETE_16_STILL_SELECTION_REQUIRED')
    clips = document.get('clipsRequested')
    if not isinstance(clips, list) or [(x.get('id'), x.get('startFrame'), x.get('endFrame')) for x in clips] != [
            ('M1', 600, 700), ('M2', 865, 965), ('M3', 965, 1100)]:
        raise ValueError('ACTUAL_EXACT_SOURCE_REVIEW_WINDOWS_REQUIRED')
    for clip in clips:
        frames.update(range(clip['startFrame'], clip['endFrame']))
    return frames


def load_capture(file):
    raw = file.read_bytes()
    document = json.loads(raw)
    if (document.get('schema') != 'WORLD_ENGINE_ASTRA_V2_ACTUAL_CAPTURE_V1'
            or document.get('status') != 'ACTUAL_SOURCE_REVIEW_DRAW_COMPLETE'
            or document.get('purpose') != 'QUALIFIED_SOURCE_REVIEW'
            or 'SwiftShader' not in document.get('backend', '')
            or document.get('paidGPUExecuted') is not False
            or document.get('nvidiaHardwareVerified') is not False
            or document.get('visualQualityApproved') is not False
            or document.get('full80SecondVideoProduced') is not False
            or document.get('oldMovieOrFramesReused') is not False):
        raise ValueError('COMPLETED_EXPLICIT_SOFTWARE_SOURCE_REVIEW_REQUIRED')
    expected = expected_capture_frames(document)
    rows = document.get('frames')
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or [x.get('globalFrame') for x in rows] != sorted(expected)):
        raise ValueError('ACTUAL_COMPLETE_UNIQUE_GLOBAL_FRAME_SET_REQUIRED')
    for row in rows:
        if (row.get('newActualDraw') is not True or row.get('glError') != 0
                or not HEX.fullmatch(row.get('pngSHA256', ''))
                or not HEX.fullmatch(row.get('rawRGBASHA256', ''))
                or row.get('eventDirector', {}).get('globalFrame') != row['globalFrame']):
            raise ValueError('ACTUAL_NEW_DRAW_AND_SOURCE_DIRECTOR_WITNESS_REQUIRED')
    return document, rows, {'path': str(file.relative_to(ROOT)), 'sha256': digest(raw), 'frames': len(rows)}


def additional_draws(row):
    extra = row.get('eventDirector', {}).get('additionalFront') or {}
    graphics = extra.get('graphics') or {}
    return [item for item in graphics.get('fronts', []) if item.get('drawn') is True]


def has_source_front(row):
    return row.get('frontCount', 0) > 0 or bool(additional_draws(row))


def has_area(row):
    return row.get('areaCount', 0) > 0


def native_camera(row):
    camera = row.get('camera') or {}
    return (finite_bounds(row.get('actualBounds')) and bool(camera.get('actualNativeCamera'))
        and len(camera.get('actualGeographicToPixelMatrix', [])) == 9
        and camera.get('sourceGlobalClockPreserved') is True)


def astra_upload(row):
    astra = (row.get('terrain') or {}).get('astra') or {}
    return (astra.get('actualMaterialFactorySelected') is True
        and astra.get('gpuUploadExecuted') is True and astra.get('testOnly') is True
        and astra.get('uploadedTextureCount', 0) > 0
        and astra.get('combinedOutputTexture') is True)


def astra_role(row, role):
    return astra_upload(row) and role in row['terrain']['astra'].get('selectedSourceRoles', [])


def composed_texture(row):
    texture = row.get('eventDirector', {}).get('composedTerrainTexture') or {}
    return (texture.get('frame') == row['globalFrame']
        and texture.get('actualCombinedTexture') is True
        and texture.get('bounds') == row.get('actualBounds'))


def annotation_reports(row):
    director = row.get('eventDirector') or {}
    reports = []
    for field in ('sourceAvailability', 'additionalFront'):
        item = director.get(field) or {}
        reports.extend(x for x in (item.get('event'), item.get('qualification'))
            if isinstance(x, dict) and x.get('drawn') is True and finite_bounds(x.get('roi')))
    return reports


def matching_source_clock(row, profile):
    frame = row['globalFrame']
    source = next(x for x in profile['sourceSchedule'] if x['startFrame'] <= frame < x['endFrame'])
    chapter = next(x for x in profile['chapters'] if x['startFrame'] <= frame < x['endFrame'])
    return (row.get('sourceAsOfDate') == source['sourceDate']
        and row.get('truthKind') == source['truthKind']
        and row.get('chapterId') == chapter['chapterId']
        and row.get('eventId') == chapter['eventId'])


def intervals(values):
    values = sorted(set(values))
    result = []
    for frame in values:
        if result and frame == result[-1][1] + 1:
            result[-1][1] = frame
        else:
            result.append([frame, frame])
    return json.dumps(result, separators=(',', ':'))


def witnesses(feature_id, frames, profile):
    """Return positive reports only; no pixel influence or quality inference."""
    predicates = {
        'AREA.FRONT_LINE': (has_source_front, 'SOURCE_FRONT_DRAW_REPORTED_NOT_VISUAL_APPROVAL'),
        'AREA.HOLD': (lambda r: has_source_front(r) or has_area(r), 'QUALIFIED_SNAPSHOT_DRAW_REPORTED_NOT_MORPH'),
        'AREA.LONG_FORM_SOURCE_CLOCK': (lambda r: matching_source_clock(r, profile), 'ACTUAL_DIRECTOR_GLOBAL_SOURCE_CLOCK'),
        'AREA.NATIVE_PROTECTION': (lambda r: (r.get('camera') or {}).get('protectedGraphicsSafe') is True,
            'NATIVE_RESERVATION_AND_LAYOUT_PATH_REPORTED'),
        'AREA.POLYGON_VALIDATION': (has_area, 'SUPPLIED_AREA_DRAW_REPORTED_NOT_FULL_OWNERSHIP'),
        'AREA.PRODUCTION_WHITE_GOLD': (has_source_front, 'SOURCE_FRONT_STYLE_CONSUMER_REPORTED_NO_ABLATION'),
        'ASTRA.GPU_UPLOAD_CONTRACT': (astra_upload, 'ACTUAL_SOFTWARE_UPLOAD_AND_COMPOSITION_SELECTED'),
        'ASTRA.BATHYMETRY_COLOR': (lambda r: astra_role(r, 'bathymetry'), 'ROLE_SELECTED_NO_PIXEL_ABLATION'),
        'ASTRA.SURFACE_TEXTURE': (lambda r: astra_role(r, 'surfaceTexture'), 'ROLE_SELECTED_NO_PIXEL_ABLATION'),
        'ASTRA.TERRAIN_NORMAL_LIGHTING': (lambda r: astra_role(r, 'terrain'), 'ROLE_SELECTED_NO_PIXEL_ABLATION'),
        'ASTRA.NODATA_FALLBACK': (lambda r: astra_upload(r)
            and r['terrain']['astra'].get('boundary', {}).get('internalNoDataSupportDistance') is True,
            'NODATA_SUPPORT_COMPOSITOR_REPORTED_NO_PIXEL_ABLATION'),
        'ASTRA.SUPPORT_DISTANCE_BLEND': (lambda r: astra_upload(r)
            and r['terrain']['astra'].get('boundary', {}).get('enabled') is True,
            'SUPPORT_BLEND_COMPOSITOR_REPORTED_NO_PIXEL_ABLATION'),
        'CAMERA.GUIDED_LAYOUT_SCALE': (native_camera, 'ACTUAL_NATIVE_CAMERA_AND_PROJECTION_SAMPLES'),
        'CAMERA.MINIMUM_CONTEXT': (native_camera, 'ACTUAL_NATIVE_CAMERA_REGIONAL_PURPOSE_ONLY'),
        'EVENT.MARKER_OCCLUSION': (lambda r: bool(additional_draws(r))
            and r['eventDirector']['additionalFront'].get('protectedGraphicMasksRetained') is True,
            'NEW_SOURCE_FRONT_MASK_CONSUMER_REPORTED'),
        'EVENT.METRIC_GLYPH_PRIMITIVE': (lambda r: bool(r.get('visibleText')), 'ANNOTATION_TEXT_RETURNED_BY_RENDER_PIPELINE'),
        'EVENT.METRIC_LAYOUT': (lambda r: bool(annotation_reports(r)), 'MEASURED_ANNOTATION_ROI_REPORTED_QUALITY_NOT_APPROVED'),
        'FRONTIER.PRODUCTION_FRONT_STYLE': (has_source_front, 'SOURCE_FRONT_STYLE_CONSUMER_REPORTED_NO_ABLATION'),
        'MAP.BAKED_RELIEF': (lambda r: (r.get('terrain') or {}).get('actualMaterialSnapshot') is True,
            'ACTUAL_SOURCE_MATERIAL_SNAPSHOT_NOT_SEPARATE_ABLATION'),
        'MAP.GIS_LAND_COVERAGE': (lambda r: astra_upload(r)
            and r['terrain']['astra'].get('actualNativeCoverage') is True, 'NATIVE_COVERAGE_REPORTED_BY_MATERIAL_CONSUMER'),
        'MAP.NATIVE_WEBGL_FACTORY': (native_camera, 'ACTUAL_NATIVE_CAMERA_DRAW_AND_READPIXELS'),
        'MAP.PROJECTION': (native_camera, 'ACTUAL_NATIVE_PROJECT_SAMPLE_MATRIX'),
        'MAP.SOURCE_GRADE': (lambda r: (r.get('terrain') or {}).get('sourceGrade', {}).get('enabled') is True,
            'SOURCE_GRADE_CONSUMER_REPORTED_NO_PIXEL_ABLATION'),
        'MAP.WARM_TERRAIN_TREATMENT': (lambda r: 'WARM_RELIEF' in (r.get('terrain') or {}).get('profileName', ''),
            'WARM_RELIEF_MATERIAL_PROFILE_SELECTED_NO_ABLATION'),
        'PLANNER.DATED_CHAPTERS': (lambda r: matching_source_clock(r, profile) and bool(r.get('visibleText')),
            'ACTUAL_CHAPTER_METADATA_AND_TEXT_REPORTED'),
        'PLANNER.SOURCE_GEOMETRY_CLOCK': (lambda r: matching_source_clock(r, profile), 'ACTUAL_DIRECTOR_SOURCE_CLOCK'),
        'PLANNER.SOURCE_MANIFEST': (lambda r: matching_source_clock(r, profile)
            and HEX.fullmatch(r.get('sceneHash', '')) is not None, 'ACTUAL_DERIVED_SCENE_BINDING_NOT_GENERAL_MANIFEST_AUDIT'),
        'PLANNER.V3_VISUAL_PROFILE': (lambda r: has_source_front(r) or has_area(r),
            'AREA_FRONT_STYLE_PATH_REPORTED_NO_ABLATION'),
        'PLANNER.V4_PARTIAL_ARCHIVAL_PROFILE': (lambda r: (r.get('frontSource') or {}).get('sourceActiveFrame') is True,
            'PRESERVED_ARCHIVAL_FRONT_SELECTOR_REPORTED'),
        'TERRITORY.ARCHIVAL_FRONT_ONLY': (lambda r: has_source_front(r)
            and (r.get('truthKind') == 'observed'), 'OBSERVED_PARTIAL_SOURCE_FRONT_DRAW_REPORTED'),
        'TERRITORY.SUPPLIED_AREA_COLOR': (has_area, 'SCHEMATIC_HELD_CORE_DRAW_REPORTED_NOT_COMPLETE_OWNERSHIP'),
    }
    definition = predicates.get(feature_id)
    if definition is None:
        return [], 'NO_FEATURE_SPECIFIC_CURRENT_WITNESS'
    predicate, level = definition
    return [row for row in frames if predicate(row)], level


def annotation_relocations(frames):
    """Report measurements, not a newly invented quality acceptance threshold."""
    by_frame = {row['globalFrame']: row for row in frames}
    result = []
    for frame, row in by_frame.items():
        previous = by_frame.get(frame - 1)
        if previous is None or previous.get('eventId') != row.get('eventId'):
            continue
        before = {x.get('id'): x for x in annotation_reports(previous)}
        for item in annotation_reports(row):
            old = before.get(item.get('id'))
            if old is None or old.get('text') != item.get('text'):
                continue
            a, b = old['roi'], item['roi']
            distance = ((((a[0]+a[2])-(b[0]+b[2]))/2)**2
                + (((a[1]+a[3])-(b[1]+b[3]))/2)**2)**0.5
            if distance:
                result.append({'fromGlobalFrame': frame-1, 'toGlobalFrame': frame,
                    'annotationId': item.get('id'), 'centerDisplacementPixels': distance,
                    'fromROI': a, 'toROI': b})
    return sorted(result, key=lambda x: x['centerDisplacementPixels'], reverse=True)


def update(capture_file, boundary_file=None, dry_run=False):
    capture, frames, receipt = load_capture(capture_file)
    profile = json.loads((ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes())
    if any(not matching_source_clock(row, profile) for row in frames):
        raise ValueError('ACTUAL_CAPTURE_PROFILE_CLOCK_OR_CHAPTER_MISMATCH')
    bindings = json.loads((ROOT / 'reports/DERIVATION.json').read_bytes())
    if any(row.get('sceneHash') != bindings['derivedSceneSHA256'] for row in frames):
        raise ValueError('ACTUAL_CAPTURE_DERIVED_SCENE_SHA_MISMATCH')
    boundary_receipt = None
    if boundary_file is not None and boundary_file.exists():
        raw = boundary_file.read_bytes()
        boundary = json.loads(raw)
        boundary_receipt = {'path': str(boundary_file.relative_to(ROOT)), 'sha256': digest(raw),
            'status': boundary.get('status'), 'importedIntoFeatureFrameCounts': False,
            'reason': 'Separate boundary proof is recorded; feature counts use the exact main 348-frame capture only.'}
    file = ROOT / 'reports/FEATURE_STATUS_151.csv'
    rows = list(csv.DictReader(file.open()))
    if len(rows) != 151 or len({x['id'] for x in rows}) != 151:
        raise ValueError('EXACT_151_FEATURE_ID_SET_REQUIRED')
    for row in rows:
        observed, level = witnesses(row['id'], frames, profile)
        # Source absence remains absence even when a generic pipeline ran.
        if row['currentStatus'].startswith('BLOCKED') or row['requirementStatus'] == 'NOT_APPLICABLE':
            observed, level = [], 'BLOCKED_OR_NOT_APPLICABLE_NO_EFFECT_DRAW'
        row['currentActualObservedFrameCount'] = len(observed)
        row['currentActualObservedFrameRangesInclusive'] = intervals(x['globalFrame'] for x in observed)
        row['currentActualEvidenceLevel'] = level
        row['newFeatureSpecificActualDrawCount'] = 'NOT_INSTRUMENTED'
        row['newFeatureSpecificActualDrawCountMeasured'] = 'false'
        row['currentPixelContributionAblationVerified'] = 'false'
        row['currentVisualQualityApproved'] = 'false'
        row['currentCaptureSHA256'] = receipt['sha256']
        if observed:
            row['currentActualRenderStatus'] = 'SOFTWARE_CONSUMER_WITNESS_NOT_VISUAL_PASS'
            if row['currentStatus'] in {'BOUND_SOURCE_ACTUAL_RENDER_PENDING', 'CPU_BOUND_ACTUAL_RENDER_PENDING'}:
                row['currentStatus'] = 'SOFTWARE_CONSUMER_OBSERVED_VISUAL_UNAPPROVED'
            evidence = [x for x in row['currentEvidence'].split(';') if x]
            for value in ['proof/ACTUAL_CAPTURE.json:frames[]', level]:
                if value not in evidence:
                    evidence.append(value)
            row['currentEvidence'] = ';'.join(evidence)
        elif row['currentStatus'].startswith('BLOCKED'):
            row['currentActualRenderStatus'] = 'BLOCKED_NO_REQUESTED_EFFECT_DRAW'
        else:
            row['currentActualRenderStatus'] = 'NO_FEATURE_SPECIFIC_CURRENT_DRAW_WITNESS'
            if row['currentStatus'] == 'BOUND_SOURCE_ACTUAL_RENDER_PENDING':
                row['currentStatus'] = 'PRESERVED_BOUND_NO_FEATURE_SPECIFIC_DRAW_WITNESS'
            elif row['currentStatus'] == 'CPU_BOUND_ACTUAL_RENDER_PENDING':
                row['currentStatus'] = 'CPU_BOUND_NO_FEATURE_SPECIFIC_DRAW_WITNESS'
        if row['id'] in {'FRONTIER.MOVING_SCALAR_LIGHT', 'FRONTIER.OUTER_DOMAIN_GOLD', 'FRONTIER.TERRAIN_DESTINATION_LIGHT'}:
            row['newFeatureSpecificActualDrawCount'] = 0
            row['currentActualEvidenceLevel'] = 'HISTORICAL_LIGHT_GUARD_REPORTED_ZERO_NO_GL_COUNTER'
    fieldnames = list(rows[0])
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = output.getvalue().encode()
    summary_file = ROOT / 'reports/FEATURE_STATUS_SUMMARY.json'
    summary = json.loads(summary_file.read_bytes())
    relocations = annotation_relocations(frames)
    source_fragments = [{'globalFrame': row['globalFrame'],
        'drawnSourceFragmentEntries': len(additional_draws(row)),
        'sourceFrontId': row['eventDirector']['additionalFront']['stateId'],
        'literalGLDrawCallsMeasured': False, 'visibilityAndQualityApproved': False}
        for row in frames if additional_draws(row)]
    summary.update(status='ACTUAL_SOFTWARE_CONSUMER_AUDIT_VISUAL_REWORK_REQUIRED',
        currentStatusCounts=dict(collections.Counter(x['currentStatus'] for x in rows)),
        requiredCurrentStatusCounts=dict(collections.Counter(x['currentStatus'] for x in rows if x['requirementStatus']=='REQUIRED')),
        actualNewFeatureDrawProofImported=True, actualCapture=receipt, boundaryCapture=boundary_receipt,
        actualObservedFrameSetCount=len(frames),
        featureRowsWithPositiveSoftwareConsumerWitness=sum(x['currentActualObservedFrameCount'] > 0 for x in rows),
        actualObservedFrameCountIsGLDrawCount=False, literalGLDrawCallsInstrumented=False,
        astraPixelAblationVerified=False, nvidiaHardwareVerified=False, visualQualityApproved=False,
        deployedStudioVerified=False, productionReady=False, historicalLightV3ActualDrawCount=0,
        composedTextureIdentityObservedFrames=sum(composed_texture(row) for row in frames),
        newPartialSourceFrontReports=source_fragments,
        annotationRelocations=relocations[:20],
        annotationStabilityStatus='FAIL_OBSERVED_RELOCATION_641_TO_642' if any(
            x['fromGlobalFrame']==641 and x['toGlobalFrame']==642 for x in relocations) else 'REQUIRES_VISUAL_REVIEW',
        requestedVisualContractStatus=capture.get('requestedVisualContractStatus'),
        currentFeatureCSV_SHA256=digest(csv_bytes), csvSHA256=digest(csv_bytes),
        nextProofStep='User visual review. Complete Local source admission and ownership/transition evidence before claiming requested camera/control/frontier effects. No production execution authorized.')
    if not dry_run:
        file.write_bytes(csv_bytes)
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=ROOT/'proof/ACTUAL_CAPTURE.json')
    parser.add_argument('--boundary', type=Path, default=ROOT/'proof/BOUNDARY_CAPTURE.json')
    parser.add_argument('--dry-run', action='store_true')
    arguments = parser.parse_args()
    result = update(arguments.capture.resolve(), arguments.boundary.resolve(), arguments.dry_run)
    print(json.dumps({key: result[key] for key in ['status', 'actualObservedFrameSetCount',
        'featureRowsWithPositiveSoftwareConsumerWitness', 'composedTextureIdentityObservedFrames',
        'annotationStabilityStatus', 'nvidiaHardwareVerified', 'visualQualityApproved', 'productionReady']}, ensure_ascii=False))
