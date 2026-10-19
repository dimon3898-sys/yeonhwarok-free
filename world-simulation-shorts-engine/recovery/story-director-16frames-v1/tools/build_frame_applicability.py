#!/usr/bin/env python3
"""Account for the original 151 audit identities against 16 actual still frames.

This report is not an API exposure list or a visual quality score. A source-bound
supporting function is not promoted to an observed draw merely because its module
was imported. Every software-consumer observation requires a verified PNG hash,
matching global frame and a feature-specific diagnostic witness.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, pathlib, re, struct

HERE = pathlib.Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
CATALOG = REPO / 'world-simulation-shorts-engine/docs/audits/knowledge-handoff-v2-20261019/CAPABILITY_CATALOG.json'
PRIOR = REPO / 'world-simulation-shorts-engine/recovery/universal-integration-completion-v2/reports/FEATURE_LEDGER_151.json'
CATALOG_SHA = '85f14ba4f52931b0f6248c173104529bc5b837e83655007b5140a2e2fba86861'
FRAMES = list(range(0, 2400, 150))
PIXEL_STATES = {'SOFTWARE_CONSUMER_OBSERVED', 'SOFTWARE_ROLE_SELECTED_PARTIAL_SUPPORT'}

# The exact operation needs an authored input. The original counterfactual Scene
# is expressly prohibited as a source of historical territory, flags or routes.
MISSING_INPUT = {
    'AREA.CONTRACT': 'No source CONTRACT operation; supplied snapshots are not continuous contraction.',
    'AREA.GROW': 'No source GROW operation; snapshot crossfade is not continuous occupation expansion.',
    'AREA.MOVE': 'No source MOVE operation or verified moving historical region.',
    'AREA.TIME_STEP': 'No source TIME_STEP operation; narrative chapter dates are a different consumer.',
    'DETAIL.POST_ARRIVAL_APPROACH': 'Director view uses the existing V5 source bounds; independent admitted post-arrival detail input not selected.',
    'DETAIL.VISUAL_GRADE_ADMISSION': 'No new screen-specific detail admission is inferred from a rendered still.',
    'FRONTIER.MOVING_SCALAR_LIGHT': 'Historical input has supplied lines, not a complementary scalar ownership field.',
    'FRONTIER.OUTER_DOMAIN_GOLD': 'Original counterfactual scalar domain is not authorized historical occupation data.',
    'FRONTIER.TERRAIN_DESTINATION_LIGHT': 'Scalar territory/current-terrain texture contract is missing; supplied Area line is the actual owner.',
    'MAP.REFERENCE_PRESENTATION_ROLL': 'Original five-second counterfactual roll track is not used as a historical director track.',
    'TERRITORY.COMPLEMENTARY_SCALAR_CONTROL': 'Complete verified opposing ownership field is absent; partial front does not authorize complement fill.',
    'TERRITORY.GAIN_STYLE': 'Original gained-territory scalar input is absent; no inferred historical gains.',
    'UNITS.NATIONAL_TABLETS': 'Historical unit/date/location/role input is empty; original fictional units are not transplanted.',
    'UNITS.SAFE_STATIC_SCALE': 'No source-bound national unit tablets are present to scale.',
    'UNITS.HISTORICAL_PARTICIPATION_GATE': 'No supplied historical unit position records; participation policy alone does not supply positions.',
    'PLANNER.CAUSAL_TRACKS': 'No verified additional causal event/route geometry is supplied to this historical Scene.',
    'PLANNER.FAMILY_TRANSPORT': 'No verified historical transport route or moving object input.',
}
for _id in ('DIRECTIONAL_FLOW', 'ENDPOINT_PULSE', 'HEADING', 'MOVING_OBJECT', 'ROUTE_HOLD', 'ROUTE_REVEAL', 'VISUAL_POLISH_PROFILE'):
    MISSING_INPUT['FLOW.' + _id] = 'No verified historical route/object/start/end input; original counterfactual units/routes are not reused.'

UNRELATED = {
    'AREA.IMPACT_ZONE', 'AREA.PROPAGATION_RING', 'AREA.PROPAGATION_WAVE',
    'WAVE.IRREGULAR_OPEN_FRONTS', 'COMBAT.LEGACY_BADGE_OVERLAY',
    'PLANNER.FAMILY_DISASTER', 'PLANNER.FAMILY_LINE_METRIC',
    'PLANNER.NIGHT_RUN_SCHEMATIC_COMPOSITION', 'PLANNER.BOUNDED_TOPIC_PARSER',
    'PLANNER.CATALOG_TOPIC_SELECTION', 'PLANNER.ADVANCED_F_NOT_SELECTED',
}
# Observed categories use positive runtime witnesses below. Source support is
# retained separately for compile/parse/cache work not measured in this capture.
OBSERVABLE = {
    'AREA.FRONT_LINE', 'AREA.HOLD', 'AREA.LONG_FORM_SOURCE_CLOCK',
    'AREA.NATIVE_PROTECTION', 'AREA.PRODUCTION_WHITE_GOLD', 'AREA.REVEAL',
    'AREA.STATE_TRANSITION', 'ASTRA.BATHYMETRY_COLOR', 'ASTRA.GPU_UPLOAD_CONTRACT',
    'ASTRA.NODATA_FALLBACK', 'ASTRA.SUPPORT_DISTANCE_BLEND', 'ASTRA.SURFACE_TEXTURE',
    'ASTRA.TERRAIN_NORMAL_LIGHTING', 'CAMERA.CONSERVATIVE_CHAPTER_FOCUS',
    'CAMERA.GUIDED_LAYOUT_SCALE', 'CAMERA.MINIMUM_CONTEXT', 'CAMERA.NATURAL_TURNAROUND',
    'EVENT.GEOGRAPHIC_LINE_ARCLENGTH', 'EVENT.METRIC_GLYPH_PRIMITIVE',
    'EVENT.METRIC_LAYOUT', 'FRONTIER.PRODUCTION_FRONT_STYLE', 'LAYOUT.UNIVERSAL_MEASURED',
    'MAP.BAKED_RELIEF', 'MAP.GIS_LAND_COVERAGE', 'MAP.NATIVE_WEBGL_FACTORY',
    'MAP.PROJECTION', 'MAP.SOURCE_GRADE', 'MAP.SOURCE_OCEAN_TONE', 'MAP.TERRAIN_LOD',
    'MAP.WARM_TERRAIN_TREATMENT', 'TERRITORY.ARCHIVAL_FRONT_ONLY',
    'TERRITORY.SUPPLIED_AREA_COLOR', 'UNITS.NATIVE_MARKERS',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dig(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            return default
        obj = obj[key]
    return obj


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def read_inputs():
    raw = CATALOG.read_bytes()
    if sha(raw) != CATALOG_SHA:
        raise ValueError('FRAME_CATALOG_PIN_MISMATCH')
    catalog = json.loads(raw)
    ids = [row['id'] for row in catalog['features']]
    if len(ids) != 151 or len(set(ids)) != 151:
        raise ValueError('FRAME_151_DISTINCT_IDS_REQUIRED')
    prior = json.loads(PRIOR.read_bytes())
    old = {r['id']: r for r in prior['features']}
    if set(ids) != set(old) or sum(r['classification'] == 'NOT_WIRED' for r in catalog['features']) != 53:
        raise ValueError('FRAME_ORIGINAL_151_53_IDENTITY_REQUIRED')
    return catalog, old


def frame_number(row):
    for key in ('globalFrame', 'frameIndex', 'frame'):
        value = row.get(key)
        if isinstance(value, int):
            return value
    return dig(row, 'diagnostic', 'frame')


def verified_rows(report_file):
    if not report_file.is_file():
        return {}, {'state': 'NOT_RENDERED', 'path': str(report_file.relative_to(HERE)) if report_file.is_relative_to(HERE) else str(report_file)}, None
    raw = report_file.read_bytes()
    report = json.loads(raw)
    found = {}
    for row in report.get('frames', report.get('captures', [])):
        frame = frame_number(row)
        if frame not in FRAMES:
            continue
        if frame in found:
            raise ValueError('FRAME_DUPLICATE_GLOBAL_INDEX')
        diagnostic = row.get('diagnostic', {})
        if row.get('directRendererOutput') is not True:
            raise ValueError('FRAME_DIRECT_RENDERER_OUTPUT_REQUIRED')
        raw_hash = row.get('raw_rgba_sha256') or row.get('rawRgbaSha256')
        if not isinstance(raw_hash, str) or not re.fullmatch('[a-f0-9]{64}', raw_hash):
            raise ValueError('FRAME_RAW_DRAW_READBACK_HASH_REQUIRED')
        if diagnostic.get('frame') != frame or diagnostic.get('glError') != 0:
            raise ValueError('FRAME_DIAGNOSTIC_GLOBAL_OR_GL_MISMATCH')
        name = row.get('file') or row.get('path') or row.get('pngFile') or dig(row, 'png', 'path')
        expected = row.get('pngSha256') or row.get('png_sha256') or row.get('sha256') or dig(row, 'png', 'sha256')
        if not name or not expected:
            raise ValueError('FRAME_PNG_BINDING_REQUIRED')
        file = pathlib.Path(name)
        candidates = [file] if file.is_absolute() else [HERE / file, report_file.parent / file]
        file = next((p for p in candidates if p.is_file()), None)
        if file is None:
            raise ValueError('FRAME_PNG_FILE_UNAVAILABLE')
        png = file.read_bytes()
        if sha(png) != expected or png[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', png[16:24]) != (1080, 1920):
            raise ValueError('FRAME_PNG_HASH_OR_SIZE_MISMATCH')
        if dig(diagnostic, 'universalVideo', 'testOnly') is not True:
            raise ValueError('FRAME_EXPLICIT_SOFTWARE_SCOPE_REQUIRED')
        found[frame] = {**row, '_png': str(file.relative_to(HERE)) if file.is_relative_to(HERE) else str(file), '_sha': expected}
    return found, {'state': 'ACTUAL_SOFTWARE_DRAW_READBACK_AND_PNG_VERIFIED',
                   'path': str(report_file.relative_to(HERE)) if report_file.is_relative_to(HERE) else str(report_file),
                   'sha256': sha(raw), 'verifiedFrameCount': len(found)}, report


def observed(feature_id, d):
    """Return evidence pointer/reason only when the exact consumer is witnessed."""
    area = d.get('area', {})
    controls = area.get('controls') or {}
    graphics = area.get('graphics') or {}
    fronts = controls.get('fronts') or []
    areas = controls.get('areas') or []
    astra = dig(d, 'terrain', 'astra', default={}) or {}
    camera = d.get('camera') or {}
    gpu = camera.get('gpu') or {}
    clock = dig(d, 'productionV3', 'geometryClock', default={}) or {}
    native = gpu.get('nativeRedrawn') is True and gpu.get('glError') == 0
    area_owner = area.get('geometryUnchanged') is True
    src = d.get('sourceIntegrity') or {}
    director = camera.get('storyDirector') or dig(camera, 'productionCamera', 'storyDirector') or d.get('storyDirector') or {}
    if feature_id == 'MAP.NATIVE_WEBGL_FACTORY' and native:
        return 'camera.gpu', 'Original native factory draw consumed current camera state before actual software readback.'
    if feature_id == 'MAP.PROJECTION' and (camera.get('projection') or dig(gpu, 'actualCamera', 'projection')):
        return 'camera.gpu.actualCamera', 'Original native projection is present in this exact captured global frame.'
    if feature_id == 'MAP.GIS_LAND_COVERAGE' and astra.get('actualNativeCoverage') is True:
        return 'terrain.astra.actualNativeCoverage', 'ASTRA composition reused native geographic coverage; no invented coast mask.'
    if feature_id == 'MAP.TERRAIN_LOD' and gpu.get('terrainLod'):
        return 'camera.gpu.terrainLod', 'Native terrain source texel-density LOD was evaluated for this camera.'
    if feature_id in {'MAP.BAKED_RELIEF', 'MAP.WARM_TERRAIN_TREATMENT', 'MAP.SOURCE_OCEAN_TONE'} and dig(d, 'terrain', 'actualMaterialSnapshot') is True:
        return 'terrain', 'Preserved source material factory was drawn; this witness is not a separate relief/ocean quality assessment.'
    if feature_id == 'MAP.SOURCE_GRADE' and dig(d, 'terrain', 'sourceGrade', 'supportDraws', default=0) > 0:
        return 'terrain.sourceGrade', 'Actual support-limited source grade draws occurred before supplied territory/front.'
    if feature_id.startswith('ASTRA.') and astra.get('actualMaterialFactorySelected') and astra.get('gpuUploadExecuted'):
        if feature_id in {'ASTRA.BATHYMETRY_COLOR', 'ASTRA.SURFACE_TEXTURE', 'ASTRA.TERRAIN_NORMAL_LIGHTING'}:
            role = {'ASTRA.BATHYMETRY_COLOR': 'bathymetry', 'ASTRA.SURFACE_TEXTURE': 'surfaceTexture', 'ASTRA.TERRAIN_NORMAL_LIGHTING': 'terrain'}[feature_id]
            if role in astra.get('selectedSourceRoles', []):
                return 'terrain.astra.selectedSourceRoles', 'Source role ' + role + ' was selected/uploaded; effect is limited to its true support mask, not the whole map.'
        if feature_id == 'ASTRA.GPU_UPLOAD_CONTRACT':
            return 'terrain.astra', 'Real WebGL2 texture upload in SwiftShader; not NVIDIA hardware validation.'
        if feature_id in {'ASTRA.NODATA_FALLBACK', 'ASTRA.SUPPORT_DISTANCE_BLEND'} and dig(astra, 'boundary', 'sourceMasks'):
            return 'terrain.astra.boundary', 'Validity/support masks and distance feathering were consumed by the actual source material.'
    if feature_id == 'AREA.LONG_FORM_SOURCE_CLOCK' and clock.get('globalFrame') == d['frame']:
        return 'productionV3.geometryClock', 'Original global frame was mapped by the preserved supplied-snapshot clock.'
    if feature_id == 'AREA.FRONT_LINE' and area_owner and fronts and graphics:
        return 'area.controls.fronts;area.graphics', 'Supplied LineString/front consumer drew this exact global frame.'
    if feature_id == 'EVENT.GEOGRAPHIC_LINE_ARCLENGTH' and any(f.get('linePrimitive') and f.get('lineReveal') for f in fronts) and graphics:
        return 'area.controls.fronts[].linePrimitive;lineReveal', 'Actual Area front reused the Event arc-length primitive; this does not prove historical travel motion.'
    if feature_id in {'AREA.PRODUCTION_WHITE_GOLD', 'FRONTIER.PRODUCTION_FRONT_STYLE'} and fronts and graphics.get('productionVisual'):
        return 'area.graphics.productionVisual', 'Original supplied-front white/gold Area style was selected; original scalar frontier remains unavailable.'
    if feature_id == 'TERRITORY.SUPPLIED_AREA_COLOR' and areas and dig(graphics, 'productionVisual', 'actualSuppliedOwnership') is True:
        return 'area.graphics.productionVisual.areaBindings', 'Only explicit supplied schematic area ownership receives color; no enemy complement fill.'
    if feature_id == 'TERRITORY.ARCHIVAL_FRONT_ONLY' and fronts and not areas and (d.get('frontV4') or d.get('archivalFrontV4') or any(str(f.get('id', '')).startswith(('CMH', 'ARCHIVAL', 'cmh')) for f in fronts)):
        return 'area.controls.fronts;area.controls.areas', 'Source has archival partial line(s) only; no complete occupation polygon is claimed.'
    if feature_id == 'AREA.HOLD' and controls.get('hold') is True and area_owner:
        return 'area.controls.hold', 'Exact supplied geometry hold evaluated, with no inferred intermediate boundary.'
    if feature_id == 'AREA.STATE_TRANSITION' and 'STATE_TRANSITION' in controls.get('activeFeatures', []):
        return 'area.controls.activeFeatures', 'Supplied snapshot state-transition consumer selected; crossfade is not coordinate-interpolated territorial expansion.'
    if feature_id == 'AREA.REVEAL' and any(0 < float(a.get('coverage', 1)) < 1 for a in areas):
        return 'area.controls.areas[].coverage', 'Actual partial reveal coverage consumed inside supplied source polygon.'
    if feature_id == 'AREA.NATIVE_PROTECTION' and graphics and dig(graphics, 'productionVisual', 'nativeBoundaryAndReservationsMasked') is True:
        return 'area.graphics.productionVisual.nativeBoundaryAndReservationsMasked', 'Original native boundary/reservation masks were forwarded to the supplied-geometry draw.'
    if feature_id in {'EVENT.METRIC_GLYPH_PRIMITIVE', 'EVENT.METRIC_LAYOUT'} and area.get('date'):
        return 'area.date', 'Measured existing date/event glyph owners placed and drew this frame; no new arbitrary metric input.'
    if feature_id in {'CAMERA.MINIMUM_CONTEXT', 'CAMERA.GUIDED_LAYOUT_SCALE', 'CAMERA.CONSERVATIVE_CHAPTER_FOCUS'} and native:
        if director or camera.get('directorVersion') == 'CAMERA_DIRECTOR_V5' or dig(camera, 'productionCamera', 'completionV2', 'directorVersion') == 'CAMERA_DIRECTOR_V5':
            return 'camera;camera.gpu.actualCamera', 'Original V5 native draw consumed director bounds/layout; amount of visible movement is assessed separately from this call.'
    if feature_id == 'CAMERA.NATURAL_TURNAROUND' and (director.get('actualV5Turn') is True or dig(camera, 'productionCamera', 'completionV2', 'actualV5Turn') is True):
        return 'camera.productionCamera', 'This frame explicitly witnesses a V5 turnaround selection, not merely a V5 module import.'
    if feature_id == 'LAYOUT.UNIVERSAL_MEASURED' and gpu.get('layoutEligibilityValidation'):
        return 'camera.gpu.layoutEligibilityValidation', 'Original measured layout validation was evaluated for the native draw.'
    if feature_id == 'UNITS.NATIVE_MARKERS' and dig(d, 'foreground', 'items'):
        return 'foreground.items', 'Original location/region graphics are rendered; these are not national military tablets.'
    return None


def classify(feature, prior, frame_row):
    fid = feature['id']
    if feature['classification'] == 'NOT_IMPLEMENTED':
        return 'NOT_IMPLEMENTED', '', 'Catalog records no implementation; this still task does not introduce it.'
    if fid in MISSING_INPUT:
        return 'BLOCKED_MISSING_VERIFIED_INPUT', '', MISSING_INPUT[fid]
    if fid in UNRELATED or feature['domain'] in {'Audio', 'Backup', 'Studio'} or fid.startswith(('AUDIO.', 'BACKUP.', 'STUDIO.')):
        return 'NOT_APPLICABLE_STILL_CAPTURE', '', 'Outside this read-only actual-still capture; existing implementation remains preserved, not exercised.'
    if fid not in OBSERVABLE:
        return 'SUPPORTING_SOURCE_NOT_PIXEL_PROOF', '', 'Pinned source/config/parse/validation capability retained; no feature-specific consumer measurement in this still capture.'
    if frame_row is None:
        return 'NOT_RENDERED', '', 'No verified actual PNG/diagnostic for this required global frame.'
    witness = observed(fid, frame_row['diagnostic'])
    if witness:
        pointer, reason = witness
        state = 'SOFTWARE_ROLE_SELECTED_PARTIAL_SUPPORT' if fid in {'ASTRA.BATHYMETRY_COLOR', 'ASTRA.SURFACE_TEXTURE', 'ASTRA.TERRAIN_NORMAL_LIGHTING'} else 'SOFTWARE_CONSUMER_OBSERVED'
        return state, pointer, reason
    return 'NOT_ACTIVE_OR_NOT_WITNESSED_THIS_FRAME', '', 'This frame contains no positive feature-specific witness; a source import/earlier proof is insufficient.'


def build(report_file=HERE / 'proof/FRAME_RENDER_REPORT.json', output=HERE):
    catalog, prior = read_inputs()
    frames, proof, report = verified_rows(report_file)
    long_rows, wide_rows = [], []
    for feature in catalog['features']:
        fid = feature['id']
        evidence = ';'.join(f"{e['path']}:{e['startLine']}:{e['symbol']}" for e in feature['evidence'])
        old = prior[fid]
        wide = {'id': fid, 'domain': feature['domain'], 'name': feature['name'],
                'originalClassification': feature['classification'], 'originallyUnwired': str(feature['classification'] == 'NOT_WIRED').lower(),
                'priorCompletionStatus': old['status'], 'currentScope': '16_ACTUAL_HISTORICAL_GLOBAL_STILLS_SOFTWARE_PREVIEW',
                'historicalAPIEntryPoint': feature['input'].get('entrypoint', ''),
                'sourceEvidence': evidence, 'actualConsumerEvidence': '', 'blockerOrScope': '',
                'actualSoftwareFrameCount': 0, 'nvidiaHardwareVerified': 'false', 'visualQualityApproved': 'false'}
        consumers, reasons = set(), set()
        for index, frame in enumerate(FRAMES):
            row = frames.get(frame)
            state, pointer, reason = classify(feature, old, row)
            wide[f'T{frame//30:03d}_F{frame:04d}'] = state
            if state in PIXEL_STATES:
                wide['actualSoftwareFrameCount'] += 1
                consumers.add(f'proof/FRAME_RENDER_REPORT.json:frames[globalFrame={frame}].diagnostic.{pointer}')
            reasons.add(reason)
            long_rows.append({'id': fid, 'globalFrame': frame, 'timeSeconds': frame//30,
                'file': row['_png'] if row else '', 'pngSha256': row['_sha'] if row else '',
                'state': state, 'consumerPointer': pointer, 'reason': reason,
                'originalClassification': feature['classification'], 'sourceEvidence': evidence,
                'nvidiaHardwareVerified': 'false', 'visualQualityApproved': 'false'})
        wide['actualConsumerEvidence'] = ';'.join(sorted(consumers))
        wide['blockerOrScope'] = ' | '.join(sorted(reasons))
        wide_rows.append(wide)
    output.mkdir(parents=True, exist_ok=True)
    def write(name, rows):
        with (output / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
    write('FRAME_APPLICABILITY_151.csv', wide_rows)
    write('FRAME_APPLICABILITY_151_BY_FRAME.csv', long_rows)
    summary = {'schema': 'WORLD_ENGINE_FRAME_APPLICABILITY_151_V1',
        'catalog': {'path': str(CATALOG.relative_to(REPO)), 'sha256': CATALOG_SHA},
        'priorCompletion': {'path': str(PRIOR.relative_to(REPO)), 'sha256': sha(PRIOR.read_bytes())},
        'featureCount': len(wide_rows), 'originallyUnwiredCount': sum(r['originallyUnwired'] == 'true' for r in wide_rows),
        'frameCountExpected': 16, 'actualFrameCountVerified': len(frames), 'all151ReviewedForAll16Frames': True,
        'featureFrameRows': len(long_rows), 'stateCountsAcross2416FeatureFrames': dict(sorted(collections.Counter(r['state'] for r in long_rows).items())),
        'featuresWithAtLeastOneSoftwareConsumerObservation': sum(r['actualSoftwareFrameCount'] > 0 for r in wide_rows),
        'featuresBlockedByVerifiedInput': sorted(MISSING_INPUT), 'renderEvidence': proof,
        'softwareConsumerIsNotPerPixelIsolatedAB': True,
        'noClaimAll151MustAppearOnScreen': True, 'noClaimAll151ArePromptCallable': True,
        'nvidiaHardwareVerified': False, 'visualQualityApproved': False, 'userReviewRequired': True}
    (output / 'reports/FRAME_APPLICABILITY_SUMMARY.json').parent.mkdir(parents=True, exist_ok=True)
    (output / 'reports/FRAME_APPLICABILITY_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=pathlib.Path, default=HERE / 'proof/FRAME_RENDER_REPORT.json')
    p.add_argument('--output', type=pathlib.Path, default=HERE)
    a = p.parse_args(); print(json.dumps(build(a.report, a.output), ensure_ascii=False))
