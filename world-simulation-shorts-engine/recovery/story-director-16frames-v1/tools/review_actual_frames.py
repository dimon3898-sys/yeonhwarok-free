#!/usr/bin/env python3
"""Review actual software stills and provenance without synthesizing pictures.

PIL/NumPy only decode the renderer PNGs, measure repeated frames and differences,
and inspect the renderer's own native projection/geometry witnesses. No output
image or map feature is generated here. Objective render checks never imply a
visual-quality approval or exact historical survey certification.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, pathlib, subprocess
import numpy as np
from PIL import Image
import build_frame_applicability as applicability

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]


def load(path):
    return json.loads(path.read_bytes())


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def vec(value, n):
    return isinstance(value, list) and len(value) == n and all(isinstance(v, (int, float)) and math.isfinite(v) for v in value)


def camera_actual(d):
    camera = d.get('camera') or {}
    native = applicability.dig(camera, 'gpu', 'actualCamera') or {}
    director = applicability.dig(camera, 'productionCamera', 'storyDirector') or {}
    return camera, native, director


def unit_counts(d):
    # Original native location markers are a separate category from national
    # military flag tablets. Never turn a location dot into a military unit.
    foreground = d.get('foreground') or {}
    visible = foreground.get('visibleRoles')
    native = [x for x in foreground.get('items', []) if x.get('kind') == 'MARKER' and (not isinstance(visible, list) or x.get('role') in visible)]
    count = applicability.dig(d, 'productionV3', 'nationalUnitPositions')
    if count is None:
        count = 0 if (applicability.dig(d, 'productionV3', 'noInferredHistoricalUnits') or applicability.dig(d, 'frontV4', 'noInferredHistoricalUnits')) else None
    return len(native), count


def labels_and_layout(d):
    camera = d.get('camera') or {}
    foreground = d.get('foreground') or {}
    visible = foreground.get('visibleRoles')
    labels = [str(x['text']) for x in foreground.get('items', []) if isinstance(x.get('text'), str) and (not isinstance(visible, list) or x.get('role') in visible)]
    date = applicability.dig(d, 'area', 'date') or {}
    for key in ('event', 'geometry'):
        text = applicability.dig(date, key, 'text')
        if isinstance(text, str) and text not in labels:
            labels.append(text)
    validation = applicability.dig(camera, 'gpu', 'layoutValidation') or {}
    failures = validation.get('failures')
    return labels, validation.get('valid'), failures


def active_front(d):
    front = d.get('frontV4') or d.get('frontSource') or {}
    selection = front.get('selection') or {}
    return front, selection


def compare_source(expected, d):
    chapter = applicability.dig(d, 'productionV3', 'chapter') or {}
    controls = applicability.dig(d, 'area', 'controls') or {}
    areas, fronts = controls.get('areas') or [], controls.get('fronts') or []
    front, selection = active_front(d)
    chapter_ok = chapter.get('chapterId') == expected['chapterId'] and chapter.get('eventId') == expected['eventId']
    truth = expected['geometryTruthKind']
    if truth == 'NO_EVENT_GEOMETRY':
        source_ok = not areas and not fronts
    elif truth == 'ARCHIVAL_PARTIAL_FRONT':
        ids = [x.get('id') for x in fronts]
        source_ok = not areas and bool(fronts) and (expected.get('frontId') in ids or expected.get('frontId') == selection.get('frontId'))
    else:
        # The supplied source state may be in a deliberate crossfade. It remains
        # a schematic snapshot, even when its date differs from the event title.
        source_ok = (bool(areas) and bool(fronts) and d.get('sourceIntegrity', {}).get('fictional65422SceneUsed') is False
                     and (expected.get('sourceStateId') is None or controls.get('stateId') == expected['sourceStateId']))
    return chapter_ok, source_ok, areas, fronts, selection


def image_stats(row, previous):
    path = ROOT / row['_png'] if not pathlib.Path(row['_png']).is_absolute() else pathlib.Path(row['_png'])
    with Image.open(path) as image:
        image.load()
        pixels = np.asarray(image.convert('RGB'), dtype=np.uint8)
    result = {'meanRGB': np.mean(pixels, axis=(0, 1)).round(6).tolist(),
              'nearlyBlackPixelFraction': float(np.mean(np.max(pixels, axis=2) <= 2)),
              'standardDeviationRGB': np.std(pixels, axis=(0, 1)).round(6).tolist()}
    if previous is not None:
        difference = np.abs(pixels.astype(np.int16) - previous.astype(np.int16))
        result.update({'meanAbsoluteRGBDifferenceFromPreviousSample': float(np.mean(difference)),
                       'changedPixelFractionFromPreviousSample': float(np.mean(np.any(difference != 0, axis=2))),
                       'maximumChannelDifferenceFromPreviousSample': int(np.max(difference))})
    else:
        result.update({'meanAbsoluteRGBDifferenceFromPreviousSample': None,
                       'changedPixelFractionFromPreviousSample': None,
                       'maximumChannelDifferenceFromPreviousSample': None})
    return result, pixels


def protection():
    baseline_path = ROOT / 'BASELINE.json'
    if not baseline_path.is_file():
        return {'status': 'UNKNOWN', 'reason': 'Baseline receipt unavailable.'}
    baseline = load(baseline_path)
    reference = baseline.get('sourceCheckoutCommit')
    if not isinstance(reference, str):
        return {'status': 'UNKNOWN', 'reason': 'Baseline source commit not recorded.'}
    result = subprocess.run(['git', 'diff', '--name-only', reference, '--'], cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        return {'status': 'UNKNOWN', 'reason': 'Read-only Git comparison unavailable.'}
    allowed = str(ROOT.relative_to(REPO)) + '/'
    changed = result.stdout.splitlines()
    forbidden = [p for p in changed if not p.startswith(allowed)]
    return {'status': 'FAIL' if forbidden else 'PASS', 'sourceCommit': reference,
            'changedTrackedPaths': changed, 'protectedOrOutsideNamespaceChanges': forbidden,
            'scope': 'Read-only tracked-byte diff, includes staged and working tree changes.'}


def build(report_path=ROOT / 'proof/FRAME_RENDER_REPORT.json'):
    frames, proof, report = applicability.verified_rows(report_path)
    if report is None or len(frames) != 16:
        raise ValueError('REVIEW_REQUIRES_16_VERIFIED_ACTUAL_RENDERER_PNGS')
    history = load(ROOT / 'reports/HISTORY_AND_SCENE.json')
    oracle_file = ROOT / 'proof/SOURCE_CONSUMER_ORACLE.json'
    oracle = load(oracle_file)
    if (oracle.get('status') != 'PASS' or oracle.get('frameRenderReportSHA256') != proof['sha256']
            or oracle.get('sourcePlanSHA256') != report.get('sourcePlanSHA256')):
        raise ValueError('REVIEW_EXISTING_EVALUATOR_SOURCE_ORACLE_REQUIRED')
    oracle_rows = {r['globalFrame']: r for r in oracle['rows']}
    if any(not r.get('exactSuppliedGeographicGeometryAlphaAndStateMatch') for r in oracle_rows.values()):
        raise ValueError('REVIEW_SOURCE_CONSUMER_MISMATCH')
    samples = {x['frame']: x for x in history['samples16']}
    manual_file = ROOT / 'reports/MANUAL_VISUAL_INSPECTION.json'
    manual = load(manual_file) if manual_file.is_file() else None
    manual_by_frame = {x['globalFrame']: x for x in manual.get('frames', [])} if manual else {}
    trace, reviews, stats, previous_pixels = [], [], [], None
    previous_native, previous_hash, previous_map_hash = None, None, None
    initial_height, previous_height = None, None
    unique_raw, unique_map_states = set(), set(); all_source_ok = True; all_chapter_ok = True; layout_ok = True
    actual_bounds, anchor_points, scale_ratios = [], [], []
    for frame in applicability.FRAMES:
        row, expected = frames[frame], samples[frame]
        d = row['diagnostic']; camera, native, director = camera_actual(d)
        chapter_ok, source_ok, areas, fronts, selection = compare_source(expected, d)
        source_oracle = oracle_rows.get(frame)
        if source_oracle is None:
            raise ValueError('REVIEW_SOURCE_ORACLE_GLOBAL_FRAME_MISSING')
        source_ok = (source_oracle.get('exactExistingGeometryClockMatch') is True
                     and source_oracle.get('exactExistingFrontSelectionMatch') is True
                     and source_oracle.get('exactSuppliedGeographicGeometryAlphaAndStateMatch') is True)
        all_source_ok &= source_ok; all_chapter_ok &= chapter_ok
        stat, pixels = image_stats(row, previous_pixels); previous_pixels = pixels
        labels, valid_layout, failures = labels_and_layout(d)
        layout_ok &= valid_layout is True
        native_marker_count, national_count = unit_counts(d)
        bounds = native.get('bounds'); anchor = native.get('anchorCanonical')
        targets = director.get('targetLocations') or []
        valid_targets = [x for x in targets if vec(x.get('anchor'), 2) and vec(x.get('actualTargetPixel'), 2)]
        target_record = [{'id': x.get('id'), 'geographicAnchor': x['anchor'], 'actualNativeProjectedPixel': x['actualTargetPixel']} for x in valid_targets]
        height = bounds[3] - bounds[1] if vec(bounds, 4) else None
        if height is not None:
            if initial_height is None:
                initial_height = height
            scale = initial_height / height
            scale_ratios.append(scale); actual_bounds.append(bounds)
        else:
            scale = None
        anchor_delta = math.dist(anchor, previous_native['anchorCanonical']) if vec(anchor, 2) and previous_native and vec(previous_native.get('anchorCanonical'), 2) else None
        if vec(anchor, 2):
            anchor_points.append(anchor)
        matrix = director.get('geographicToPixelMatrix')
        matrix_residuals = []
        if vec(matrix, 9):
            for target in valid_targets:
                x, y = target['anchor']; w = matrix[6]*x + matrix[7]*y + matrix[8]
                if w:
                    prediction = [(matrix[0]*x + matrix[1]*y + matrix[2])/w,
                                  (matrix[3]*x + matrix[4]*y + matrix[5])/w]
                    matrix_residuals.append(math.dist(prediction, target['actualTargetPixel']))
        source_clock = applicability.dig(d, 'productionV3', 'geometryClock') or {}
        raw_hash = row.get('raw_rgba_sha256') or row.get('rawRgbaSha256')
        map_state = {'actualNativeBoundsAt1e9DegreeReviewPrecision': [round(v, 9) for v in bounds] if vec(bounds, 4) else bounds,
                     'sourceStateId': applicability.dig(d, 'area', 'controls', 'stateId'),
                     'archivalSourceGeometrySHA256': active_front(d)[0].get('sourceGeometrySha256'),
                     'areas': [{k: a.get(k) for k in ('id', 'alpha', 'coverage', 'coverageMode', 'transform')} for a in areas],
                     'fronts': [{k: a.get(k) for k in ('id', 'alpha', 'revealFraction')} for a in fronts]}
        map_hash = digest(map_state)
        unique_map_states.add(map_hash); unique_raw.add(raw_hash)
        source_mode = selection.get('mode') or source_clock.get('mode')
        source_date = selection.get('mapDate') or selection.get('sourceDate') or source_clock.get('snapshotDate')
        diagnostic_pointer = f'proof/FRAME_RENDER_REPORT.json:frames[globalFrame={frame}].diagnostic'
        trace_row = {'globalFrame': frame, 'timeSeconds': frame / 30, 'png': row['_png'], 'pngSha256': row['_sha'],
                     'rawRGBAHash': raw_hash, 'chapterId': expected['chapterId'], 'eventId': expected['eventId'],
                     'eventTitle': expected['title'], 'sourceGeometryTruth': expected['geometryTruthKind'],
                     'sourceGeometryDate': source_date, 'sourceGeometryDateRole': 'ARCHIVAL_MAP_DATE' if selection.get('sourceActiveFrame') else 'SOURCE_SCHEDULE_TARGET_DATE_NOT_DAILY_FRONT',
                     'sourceGeometryMode': source_mode, 'sourceSnapshotWindowLabel': source_clock.get('snapshotLabel'),
                     'actualChosenSourceStateId': source_oracle.get('actualChosenStateId'), 'sourceTargetMetadataStateId': source_oracle.get('targetMetadataStateId'),
                     'exactGeographicStateSHA256': source_oracle.get('actualGeographicStateWitnessSHA256'),
                     'sourceGeometryRefs': compact(expected['geometryRefs']),
                     'actualSourceGeometryFrame': source_clock.get('sourceGeometryFrame'),
                     'actualAreaIds': compact([x.get('id') for x in areas]),
                     'actualFrontIds': compact([x.get('id') for x in fronts]),
                     'actualFrontRevealFractions': compact([x.get('revealFraction') for x in fronts]),
                     'actualAreaCoverage': compact([x.get('coverage') for x in areas]),
                     'actualAreaAlpha': compact([x.get('alpha') for x in areas]),
                     'actualCameraProjection': native.get('projection'), 'actualNativeBounds': compact(bounds),
                     'actualNativeCenter': compact(native.get('center')), 'actualFixedContextAnchorPixel': compact(anchor),
                     'fixedContextAnchorDeltaPixelsFromPreviousSample': anchor_delta,
                     'nativeBoundsHeightRatioFromFirstSample': scale,
                     'zoomRatioFromPreviousSample': previous_height / height if previous_height and height else None,
                     'actualTargetPixelRecords': compact(target_record),
                     'directorDeclaredGeographicToPixelMatrix': compact(matrix),
                     'matrixComparedToActualNativeProjectionMaxResidualPixels': max(matrix_residuals) if matrix_residuals else None,
                     'rotationDegrees': director.get('rotationDegrees'),
                     'rotationStatus': director.get('rotationStatus', 'NOT_WITNESSED'),
                     'nativeLayoutValid': valid_layout, 'nativeLayoutFailures': compact(failures),
                     'sourceDataMatch': source_ok, 'chapterMatch': chapter_ok,
                     'frontierMotion': compact(applicability.dig(d, 'area', 'graphics', 'completionFrontier', 'motion')),
                     'continuousHistoricalExpansionClaimed': False, 'nvidiaHardwareVerified': False,
                     'evidence': diagnostic_pointer}
        trace.append(trace_row)
        defects = []
        if expected['geometryTruthKind'] == 'SCHEMATIC_HELD_CORE':
            defects.append('도식 held-core; 실제 일별 점령 확장/양측 전체 영토가 아님')
        if expected['geometryTruthKind'] == 'ARCHIVAL_PARTIAL_FRONT':
            defects.append('근사·부분 전선만 제공; 전체 점령 색상 채우기 차단')
        if national_count in (None, 0):
            defects.append('국가별 군대 표식은 검증된 위치 자료 없음으로 BLOCKED')
        if source_oracle.get('targetStateMetadataIsNotCurrentCrossfadeState') is True:
            defects.append('전환 시작점은 원본 evaluator의 이전 상태; 목표 날짜 메타데이터와 현재 상태를 구분')
        if not source_ok:
            defects.append('기대 자료와 실제 consumer 상태 불일치')
        if valid_layout is not True:
            defects.append('실제 native 레이아웃 보호 결과 미확인/실패')
        if raw_hash == previous_hash:
            defects.append('직전 5초 샘플과 원시 픽셀 완전 동일')
        elif map_hash == previous_map_hash:
            defects.append('직전 5초 샘플과 실제 카메라·공급 지도 상태 동일; 텍스트 차이만으로 사건 움직임을 증명하지 않음')
        source_relationship = '이벤트와 지도 기준일이 다를 수 있음; 표시된 자료 날짜 우선'
        review = {'sampleIndex': frame // 150, 'timeSeconds': frame / 30, 'globalFrame': frame,
                  'file': row['_png'], 'pngSha256': row['_sha'], 'expectedEvent': expected['title'],
                  'actualEvent': applicability.dig(d, 'productionV3', 'chapter', 'title'),
                  'eventChapterMatchesFrozenScene': chapter_ok,
                  'expectedDataKind': expected['geometryTruthKind'], 'expectedSourceDate': expected['sourceDate'],
                  'actualSourceDate': source_date, 'actualSourceDateRole': 'ARCHIVAL_MAP_DATE' if selection.get('sourceActiveFrame') else 'SOURCE_SCHEDULE_TARGET_DATE_NOT_DAILY_FRONT',
                  'actualSourceWindowLabel': source_clock.get('snapshotLabel'),
                  'actualChosenSourceStateId': source_oracle.get('actualChosenStateId'),
                  'sourceTargetMetadataStateId': source_oracle.get('targetMetadataStateId'),
                  'exactExistingSourceEvaluatorMatch': source_ok, 'dataDatePolicy': source_relationship,
                  'expectedSourceRefs': compact(expected['geometryRefs']), 'actualAreaCount': len(areas),
                  'actualFrontCount': len(fronts), 'sourceDataMatch': source_ok,
                  'expectedCamera': '출처 자료 범위와 기존 지명 맥락을 보존하는 독립 director camera; 원본 V5/65422 reference adapter 재사용',
                  'actualCameraBounds': compact(bounds), 'actualTargetPixels': compact(target_record),
                  'fixedContextAnchorDeltaPixels': anchor_delta, 'zoomRatioFromFirst': scale,
                  'rotation': director.get('rotationStatus', 'NOT_WITNESSED'),
                  'nativeLocationMarkerCount': native_marker_count, 'historicalNationalUnitCount': national_count,
                  'actuallyDrawnText': compact(labels), 'nativeLayoutValid': valid_layout,
                  'pixelMeanDifferenceFromPreviousSample': stat['meanAbsoluteRGBDifferenceFromPreviousSample'],
                  'changedPixelFraction': stat['changedPixelFractionFromPreviousSample'],
                  'exactDuplicatePreviousSample': raw_hash == previous_hash,
                  'actualCameraAndSuppliedMapStateHash': map_hash, 'mapStateHashCameraPrecisionDegrees': 1e-9, 'cameraAndMapStateSameAsPreviousSample': map_hash == previous_map_hash,
                  'visibleChangeEvidence': 'Actual PNG pixel delta plus actual native projection trace; effect adequacy requires visual review.',
                  'defectsOrBlocked': ' | '.join(defects), 'frameTechnicalState': 'ACTUAL_SOFTWARE_PNG_VERIFIED',
                  'visualState': 'VISUAL_REVIEW_REQUIRED', 'visualQualityApproved': False,
                  'evidence': diagnostic_pointer}
        manual_row = manual_by_frame.get(frame)
        if manual_row:
            if manual_row['pngSha256'] != row['_sha']:
                raise ValueError('REVIEW_MANUAL_IMAGE_SHA_MISMATCH')
            review.update({'actualImageVisualObservation': manual_row['observedMapContent'],
                           'actualImageTruthQualification': manual_row['truthQualification'],
                           'actualImageStoryReadabilityDefect': manual_row['storyReadabilityDefect'],
                           'manualInspection': 'ACTUAL_IMAGE_INSPECTION_USER_APPROVAL_PENDING'})
        reviews.append(review); stats.append({'globalFrame': frame, 'file': row['_png'], **stat})
        previous_native, previous_height, previous_hash, previous_map_hash = native, height, raw_hash, map_hash
    def write_csv(name, rows):
        with (ROOT / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
    write_csv('FRAME_REVIEW_16.csv', reviews); write_csv('CAMERA_AND_FRONT_TRACE.csv', trace)
    projection_motion = max((math.dist(a, b) for a in anchor_points for b in anchor_points), default=0)
    zoom = max(scale_ratios) / min(scale_ratios) if scale_ratios else None
    protection_result = protection()
    camera_proven = len({compact(b) for b in actual_bounds}) > 1 and projection_motion > 0.602065 and zoom is not None and zoom > 1
    adjacency = report.get('adjacentFrames') or []
    adjacent_indices = [applicability.frame_number(r) for r in adjacency]
    adjacent_verified, adjacent_proof, _ = applicability.verified_rows(report_path,
        row_key='adjacentFrames', expected_frames=adjacent_indices)
    adjacent_review, previous_adjacent, previous_adjacent_row = [], None, None
    official_dates = set()
    for row in list(frames.values()) + list(adjacent_verified.values()):
        _, selection = active_front(row['diagnostic'])
        if selection.get('sourceActiveFrame') is True:
            date = selection.get('mapDate')
            if isinstance(date, str):
                official_dates.add(date)
    for frame in sorted(adjacent_verified):
        row = adjacent_verified[frame]; d = row['diagnostic']
        _, native, director = camera_actual(d); front, selection = active_front(d)
        same_window = previous_adjacent_row is not None and frame == applicability.frame_number(previous_adjacent_row) + 1
        stat, pixels = image_stats(row, previous_adjacent if same_window else None)
        before = previous_adjacent_row['diagnostic'] if same_window else {}
        _, previous_native, _ = camera_actual(before)
        anchor, previous_anchor = native.get('anchorCanonical'), previous_native.get('anchorCanonical')
        before_front, _ = active_front(before)
        source_geometry_changed = (front.get('sourceGeometrySha256') != before_front.get('sourceGeometrySha256')) if same_window else None
        adjacent_review.append({'globalFrame': frame, 'timeSeconds': frame/30, 'file': row['_png'],
            'pngSha256': row['_sha'], 'rawRGBAHash': row.get('raw_rgba_sha256'),
            'continuesPreviousFrame': same_window,
            'actualSourceFrontId': selection.get('frontId'), 'actualSourceMapDate': selection.get('mapDate'),
            'actualSourceGeometrySHA256': front.get('sourceGeometrySha256'),
            'sourceGeometryChangedFromPreviousAdjacentFrame': source_geometry_changed,
            'sourceEndpointPolicy': 'SUPPLIED_SNAPSHOT_HOLD_OR_ENDPOINT_SWITCH_NO_COORDINATE_INTERPOLATION',
            'actualNativeBounds': compact(native.get('bounds')),
            'actualFixedContextAnchorPixel': compact(anchor),
            'actualAnchorStepPixels': math.dist(anchor, previous_anchor) if vec(anchor,2) and vec(previous_anchor,2) and same_window else None,
            'meanAbsoluteRGBDifference': stat['meanAbsoluteRGBDifferenceFromPreviousSample'],
            'changedPixelFraction': stat['changedPixelFractionFromPreviousSample'],
            'sceneClockReset': director.get('sceneClockReset'),
            'nvidiaHardwareVerified': False, 'visualQualityApproved': False})
        previous_adjacent, previous_adjacent_row = pixels, row
    if adjacent_review:
        write_csv('ADJACENT_FRAME_REVIEW.csv', adjacent_review)
    global_clock_ok = report.get('oneRuntime') is True and report.get('sceneReinitializedPerFrame') is False and report.get('requestedGlobalFrames') == applicability.FRAMES
    no_paid_or_video = report.get('paidGpuExecuted') is False and report.get('mp4Produced') is False and report.get('nvidiaHardwareVerified') is False
    criterion = [
        {'id': 1, 'criterion': '원본 FINAL 보호', 'status': protection_result['status'], 'evidence': 'reports/ACTUAL_FRAME_REVIEW.json#protection', 'detail': '기준 Git commit 대비 새 director namespace 밖의 tracked byte 변경을 검사.'},
        {'id': 2, 'criterion': '실제 12장면 시점 일치', 'status': 'PASS' if all_chapter_ok and history['chapterCount'] == 12 else 'FAIL', 'evidence': 'FRAME_REVIEW_16.csv;STORY_80S_SOURCE_LEDGER.csv', 'detail': '16개 전역 프레임의 이벤트 ID/장면 ID가 동결 원본과 일치; 감독 구간과의 충돌은 원본을 우선.'},
        {'id': 3, 'criterion': '역사 자료 근거', 'status': 'UNKNOWN', 'evidence': 'reports/HISTORY_AND_SCENE.json', 'detail': '8개 공식 지도 날짜·부분 선 근거는 보존. 초기 사건 원문 검증 및 원본 투영법/전체 위치 정확도는 미확인; 도식 영역은 정밀 실측 아님.'},
        {'id': 4, 'criterion': '16장 각각 진짜 렌더러 출력', 'status': 'PASS', 'evidence': 'proof/FRAME_RENDER_REPORT.json;reports/ACTUAL_FRAME_REVIEW.json#renderEvidence', 'detail': '16개 actual draw/readPixels PNG의 전역 frame, SHA, 1080×1920, software scope 확인. 이미지 생성/옛 영상 캡처 아님.'},
        {'id': 5, 'criterion': '전역 시간축 보존', 'status': 'PASS' if global_clock_ok else 'FAIL', 'evidence': 'proof/FRAME_RENDER_REPORT.json;CAMERA_AND_FRONT_TRACE.csv', 'detail': '하나의 runtime에 원본 0..2399 global clock으로 랜덤 접근; 각 프레임 Scene 초기화 없음.'},
        {'id': 6, 'criterion': '카메라 이동/줌 실제 픽셀 증거', 'status': 'PASS' if camera_proven else 'FAIL', 'evidence': 'CAMERA_AND_FRONT_TRACE.csv;reports/ACTUAL_FRAME_REVIEW.json#cameraMeasurements', 'detail': '실제 native factory의 고정 지명 투영 위치와 카메라 bounds/scale 변화 측정. 연출 만족도/회전 구현 PASS는 아님.'},
        {'id': 7, 'criterion': '전선/영토 자료 일치', 'status': 'PASS' if all_source_ok else 'FAIL', 'evidence': 'FRAME_REVIEW_16.csv;reports/HISTORY_AND_SCENE.json', 'detail': '기존 clock/Area/front evaluator와 실제 25개 draw의 지리 geometry·alpha·선택 상태를 SHA로 비교. 전환 시작의 이전 상태도 그대로 검증; 정확한 일별 역사 전선이나 전체 양측 점령은 주장하지 않음.'},
        {'id': 8, 'criterion': '국가색·모바일 가독성', 'status': 'UNKNOWN', 'evidence': 'FRAME_REVIEW_16.csv;public-review/CONTACT_SHEET_4X4.png', 'detail': '완전한 양측 영토·역사 군대 좌표 없음. 실제 PNG 모바일 가독성은 사용자 검수 대기; native 레이아웃 체크만으로 품질 PASS 선언 금지.'},
        {'id': 9, 'criterion': '품질 PASS 남용 금지', 'status': 'PASS' if report.get('visualQualityApproved') is False else 'FAIL', 'evidence': 'proof/FRAME_RENDER_REPORT.json;FRAME_REVIEW_16.csv', 'detail': '기술/software 소비자 관측과 시각 품질 승인 분리. 최종 품질 USER_REVIEW_REQUIRED.'},
        {'id': 10, 'criterion': '사용자 승인 전 유료/80초/FINAL 금지', 'status': 'PASS' if no_paid_or_video else 'UNKNOWN', 'evidence': 'BASELINE.json;proof/FRAME_RENDER_REPORT.json', 'detail': '무료 소프트웨어 정지 프레임만 출력. MP4/유료GPU/FINAL 승격 없음.'},
    ]
    summary = {'schema': 'WORLD_ENGINE_ACTUAL_STILL_FRAME_REVIEW_V1', 'renderEvidence': proof,
               'scope': 'ACTUAL_SOFTWARE_DRAW_READBACK_PNG_AND_NATIVE_PIXEL_PROJECTION_REVIEW',
               'verifiedFrameCount': len(frames), 'uniqueRawPixelFrameCount': len(unique_raw),
               'exactRepeatedSampleCount': 16-len(unique_raw), 'distinctActualCameraAndSuppliedMapStates': len(unique_map_states),
               'repeatedCameraAndSuppliedMapStateCount': 16-len(unique_map_states), 'allSampleChapterIdsMatchSource': all_chapter_ok,
               'allSampleGeometrySelectionsMatchSource': all_source_ok,
               'sourceConsumerOracle': {'path': 'proof/SOURCE_CONSUMER_ORACLE.json', 'sha256': hashlib.sha256(oracle_file.read_bytes()).hexdigest(), 'actualFramesMatched': len(oracle_rows)},
               'nativeLayoutValidAtAllSamples': layout_ok, 'sourceClockReset': report.get('sceneReinitializedPerFrame') is True,
               'cameraMeasurements': {'actualNativeBoundsCount': len(actual_bounds),
                   'distinctActualNativeBounds': len({compact(b) for b in actual_bounds}),
                   'distinctCameraViewsAt1e9DegreeReviewPrecision': len({compact([round(v,9) for v in b]) for b in actual_bounds}),
                   'cameraReviewHashRoundingDoesNotModifyInputsOrRawTrace': True,
                   'fixedContextAnchorMaximumDisplacementPixels': projection_motion,
                   'maximumRelativeNativeZoomRatio': zoom, 'cameraCallIsNotSufficientWithoutPixels': True,
                   'matrixProofPolicy': 'Only compare declared matrix against actual native.project targets; do not call a CPU matrix GPU pose.'},
               'adjacentActualSampleCount': len(adjacent_verified), 'adjacentEvidence': adjacent_proof,
               'officialSourceMapDatesObserved': sorted(official_dates), 'officialSourceMapDatesObservedCount': len(official_dates),
               'adjacentContinuityScope': 'SOURCE_SNAPSHOT_ENDPOINTS_AND_CAMERA;NO_UNOBSERVED_HISTORICAL_FRONT_INTERPOLATION',
               'protection': protection_result, 'pixelStatistics': stats,
               'nvidiaHardwareVerified': False, 'visualQualityApproved': False,
               'overallCompletePass': False, 'manualInspection': {'path': 'reports/MANUAL_VISUAL_INSPECTION.json', 'sha256': hashlib.sha256(manual_file.read_bytes()).hexdigest()} if manual else None,
               'topThreeActualVisualDefects': manual.get('topThreeDefects', []) if manual else [],
               'decision': manual.get('decision', 'VISUAL_REVIEW_REQUIRED_WITH_HISTORICAL_DATA_GAPS') if manual else 'VISUAL_REVIEW_REQUIRED_WITH_HISTORICAL_DATA_GAPS'}
    (ROOT / 'reports/ACTUAL_FRAME_REVIEW.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    criteria = {'schema': 'WORLD_ENGINE_STORY_DIRECTOR_10_CRITERIA_V1', 'criteria': criterion,
                'counts': {state: sum(c['status']==state for c in criterion) for state in ('PASS','FAIL','UNKNOWN')},
                'overallCompletePass': False, 'visualQualityApproved': False, 'userReviewRequired': True,
                'unknownBlocksOverallCompletionPass': True}
    (ROOT / 'reports/10_CRITERIA_REVIEW.json').write_text(json.dumps(criteria, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 실제 16장 검수', '', '정지 프레임은 실제 WORLD ENGINE 소프트웨어 WebGL2 출력입니다. NVIDIA 품질 검증과 사용자 화면 승인은 아직 수행하지 않았습니다.', '', '| # | 검수 항목 | 상태 | 근거 |', '|---|---|---|---|']
    lines.extend(f"| {c['id']} | {c['criterion']} | {c['status']} | {c['evidence']} |" for c in criterion)
    lines.extend(['', '역사 자료·모바일 가독성 UNKNOWN이 남아 있어 전체 완성 PASS를 선언하지 않습니다.', '',
                  '16장만으로 연속 영토 확장을 증명하지 않습니다. 원본 자료의 held-core, snapshot crossfade, 부분 전선 endpoint를 구분합니다.', '',
                  '국가별 군대 표식, 전체 상대 점령 영역, 원본 65422 회전·scalar는 검증된 역사 입력/소비자가 없어 활성화하지 않았습니다.', ''])
    (ROOT / 'FRAME_REVIEW_README.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'frames': len(frames), 'uniqueRawFrames': len(unique_raw), 'cameraProjectionMotionPixels': projection_motion,
            'zoomRatio': zoom, 'criteria': criteria['counts'], 'visualQualityApproved': False}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--report', type=pathlib.Path, default=ROOT / 'proof/FRAME_RENDER_REPORT.json')
    a = p.parse_args(); print(json.dumps(build(a.report), ensure_ascii=False))
