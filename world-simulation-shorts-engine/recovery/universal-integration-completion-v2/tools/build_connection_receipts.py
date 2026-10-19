#!/usr/bin/env python3
"""Build source-hash/CPU-receipt feature connections; never render or authorize.

One receipt covers each original audit identity. New CPU instrumentation is
assigned only to consumers actually exercised by the named focused suites.
Unchanged source bindings remain SOURCE_STATIC, not a blanket 133-test claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
REL = ROOT.relative_to(REPO).as_posix()
SPEC = importlib.util.spec_from_file_location('completion_ledger_receipt_owner', ROOT / 'feature_ledger.py')
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


def source(path):
    relative = path if isinstance(path, str) else path.relative_to(REPO).as_posix()
    target = REPO / relative
    if not target.is_file() or any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError('CONNECTION_RECEIPT_SOURCE_UNAVAILABLE:' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def build(*, image_proof=None, source_commit=None):
    audit, prior = ledger.load_inputs()
    previous = {r['id']: r['integrationReview'] for r in prior['features']}
    cpu_path = ROOT / 'reports/CPU_TEST_RESULTS.json'
    cpu = json.loads(cpu_path.read_bytes())
    if (cpu.get('schema') != 'WORLD_ENGINE_COMPLETION_CPU_RECEIPT_V1' or cpu.get('status') != 'PASS'
            or cpu.get('gpuExecuted') is not False or cpu.get('swiftShaderDrawExecuted') is not False
            or cpu.get('videoRendered') is not False or cpu.get('paidWorkExecuted') is not False):
        raise ValueError('CONNECTION_CPU_RECEIPT_INVALID')
    suites = {row['test']: row for row in cpu['suites']}
    for name, row in suites.items():
        if (row.get('status') != 'PASS' or row.get('exitCode') != 0 or row.get('executed', 0) <= 0
                or row.get('testSourceSHA256') != source(ROOT / 'tests' / name)['sha256']):
            raise ValueError('CONNECTION_CPU_SUITE_STALE_OR_FAILED:' + name)
    if sum(row['executed'] for row in suites.values()) != cpu['executed']:
        raise ValueError('CONNECTION_CPU_COUNT_MISMATCH')
    rows = {}
    for f in audit['features']:
        r = previous[f['id']]
        # Source existence and old-image inclusion are retained separately.
        # These are source-level selected owners, not observed completion draws.
        visual = f['domain'] in {'Area', 'ASTRA', 'Camera', 'Detail', 'Event', 'Flow', 'Frontier', 'Layout', 'Map', 'Scale', 'Territory', 'Units'}
        selected = f['axes']['RENDERER_CALLED'] == 'YES'
        evidence_paths = list(dict.fromkeys(e['path'] for e in f['evidence']))
        available = [p for p in evidence_paths if (REPO / p).is_file()]
        records = [source(p) for p in available]
        records.append(source(ledger.AUDIT_PATH))
        rows[f['id']] = {
            'id': 'feature-' + f['id'].lower().replace('_', '-'), 'featureIds': [f['id']],
            'implementationExists': 'NO' if f['classification'] == 'NOT_IMPLEMENTED' else f['axes']['SOURCE_EXISTS'],
            'studioV2Exposed': 'INTERNAL_ONLY' if selected else 'NO',
            'sceneJSONAddressable': 'CONDITIONAL' if selected and visual else 'NO',
            'runtimeSelected': 'YES' if selected else 'NO',
            'actualRendererConsumer': 'SOURCE_BOUND' if selected and visual else 'NONE',
            'sourceFiles': records, 'inputFields': [],
            'factories': [f['input']['entrypoint']] if selected and visual and f['input'].get('entrypoint') else [],
            'consumers': [f['input']['entrypoint']] if selected and visual and f['input'].get('entrypoint') else [],
            'cpuTests': [], 'evidenceKind': 'SOURCE_STATIC', 'actualOutputProduced': False,
            'relevance': r['relevance'], 'status': r['status'],
            'reason': 'Preserved source/audit evidence only; no new feature-specific CPU consumer execution is claimed. ' + r['reason'],
            'outputTrace': {'state': 'NOT_PRODUCED'},
        }

    def bind(ids, *, files, fields=(), factories=(), consumers=(), tests=(), exposed='INTERNAL_ONLY',
             addressable='CONDITIONAL', selected='CONDITIONAL', renderer='CPU_INSTRUMENTED',
             status='SUPPORTING', reason, relevance=None, blockers=()):
        for feature_id in ids:
            r = rows[feature_id]
            merged = {item['path']: item for item in r['sourceFiles']}
            for file in files:
                item = source(ROOT / file)
                merged[item['path']] = item
            for name in tests:
                if name not in suites:
                    raise ValueError('CONNECTION_TEST_WAS_NOT_EXECUTED:' + name)
                item = source(ROOT / 'tests' / name)
                merged[item['path']] = item
            r.update({'sourceFiles': list(merged.values()), 'inputFields': list(fields),
                'factories': list(factories), 'consumers': list(consumers),
                'cpuTests': [{'name': name, 'result': suites[name]['status']} for name in tests],
                'studioV2Exposed': exposed, 'sceneJSONAddressable': addressable,
                'runtimeSelected': selected, 'actualRendererConsumer': renderer,
                'evidenceKind': 'CPU_INSTRUMENTATION' if tests else 'SOURCE_STATIC',
                'status': status, 'reason': reason})
            if tests:
                r['cpuReceipt'] = source(cpu_path)
            if relevance:
                r['relevance'] = relevance
            if blockers:
                r['blockingReasons'] = [{'code': code, 'reason': message} for code, message in blockers]
                r['status'] = 'BLOCKED'

    # Actual V5 math plus clearly labelled native/layout CPU instrumentation.
    bind(['CAMERA.CONSERVATIVE_CHAPTER_FOCUS', 'CAMERA.GUIDED_LAYOUT_SCALE',
          'CAMERA.MINIMUM_CONTEXT', 'CAMERA.NATURAL_TURNAROUND'],
         files=['camera_extension.mjs', 'production_camera_bridge.mjs', 'runtime_binding.mjs'],
         fields=['completion.camera.mode', 'completion.camera.settleFrames', 'completion.camera.holdFrames', 'visualProfile.cameraApproachFrames'],
         factories=['createCompletionNativeCamera', 'compileCompletionCameraTracking', 'compileMinimumContextPlan'],
         consumers=['evaluateMinimumContextCameraFrame', 'native.updateCamera/setScaleVisual/setTerrainLod/renderFrame'],
         tests=['test_camera_extension.mjs', 'test_runtime_binding.mjs'], exposed='YES', selected='YES',
         reason='Actual preserved V5 compilation/evaluation and all 2400 source-bound CPU camera states are verified; native redraw/layout calls are explicit CPU spies. Tracking preserves source geometry/minimum extent; no roll, arbitrary closer floor or GPU pixels are claimed.')

    # Five confirmed style parameters and actual supplied-front motion envelope.
    bind(['AREA.PRODUCTION_WHITE_GOLD', 'FRONTIER.PRODUCTION_FRONT_STYLE', 'PLANNER.V3_VISUAL_PROFILE'],
         files=['frontier_extension.mjs', 'production_area_bridge.mjs', 'source_observations.mjs', 'runtime_binding.mjs'],
         fields=['visualProfile.territoryOpacity', 'visualProfile.frontCoreWidthPixels', 'visualProfile.frontGlowRadiusPixels',
                 'visualProfile.frontGlowGain', 'completion.frontier'],
         factories=['bindFrontierProductionFactory', 'createProductionAreaPass'],
         consumers=['AreaOverlayPassV3.drawLine/contour', 'evaluateSuppliedFrontMotion'],
         tests=['test_frontier_extension.mjs', 'test_runtime_binding.mjs'], exposed='YES', selected='YES',
         reason='The exact original production Area factory consumes bounded white/gold style and supplied-front alpha response under CPU allocator instrumentation. Geometry/masks remain original; this is not the separate scalar terrain-light shader or rendered output.')

    # Trusted canonical Event/Flow/Area inputs are independently admitted.
    event_ids = ['EVENT.INTEGER_TIMELINE', 'EVENT.AUTOMATIC_LINE_CONTRAST', 'EVENT.GEOGRAPHIC_LINE_ARCLENGTH',
                 'EVENT.MARKER_OCCLUSION', 'EVENT.METRIC_GLYPH_PRIMITIVE', 'EVENT.METRIC_LAYOUT']
    bind(event_ids, files=['event_flow_binding.mjs', 'event_flow_contract.py', 'capture_runtime.mjs', 'SOURCE_DATA_CATALOG.json'],
         fields=['completion.eventFlow.events[].plan', 'completion.eventFlow.events[].sourceBindings'],
         factories=['compileCompletionEventFlow', 'createCompletionEventFlowPass', 'compileEventPlan'],
         consumers=['evaluateEventFrame', 'selectEventLineStyle', 'createEventLinePass.draw', 'createEventMetricPass.draw', 'chooseRelatedMetricPlacement'],
         tests=['test_event_flow_binding.mjs'], exposed='CONDITIONAL',
         reason='Canonical source-bound Event plans now reach the preserved compiler/evaluator and line/metric/occlusion consumer boundary. Explicit CPU factory/metric spies verify forwarding, not fonts/shaders/pixels. Current eighty-second added events[] is empty; no Suez metric or new historical event is inserted.')

    bind(['AREA.REVEAL', 'AREA.GROW', 'AREA.CONTRACT', 'AREA.MOVE', 'AREA.HOLD', 'AREA.FRONT_LINE', 'AREA.STATE_TRANSITION', 'AREA.TIME_STEP',
          'AREA.POLYGON_VALIDATION', 'AREA.NATIVE_PROTECTION'],
         files=['event_flow_binding.mjs', 'event_flow_contract.py', 'camera_extension.mjs', 'capture_runtime.mjs'],
         fields=['completion.eventFlow.areas[].plan', 'completion.eventFlow.areas[].sourceBindings'],
         factories=['compileAreaIntent', 'compileAreaPlan', 'createCompletionEventFlowPass', 'createAreaOverlayPass'],
         consumers=['evaluateAreaFrame', 'createAreaOverlayPass.draw', 'classifyEventLineProtection', 'nativeBoundarySupport'],
         tests=['test_event_flow_binding.mjs', 'test_camera_extension.mjs'], exposed='CONDITIONAL',
         reason='The original Area operations and geometry/occlusion owners are compiled/evaluated through the generic canonical input and CPU consumer instrumentation. An added production Area requires trusted source intent, actual same-frame native boundaries and Detail lock. Radial growth/translation is not claimed as observed historical military movement; current eighty-second added areas[] is empty.')

    flow_ids = ['FLOW.DIRECTIONAL_FLOW', 'FLOW.ENDPOINT_PULSE', 'FLOW.HEADING', 'FLOW.MOVING_OBJECT', 'FLOW.ROUTE_HOLD', 'FLOW.ROUTE_REVEAL']
    bind(flow_ids, files=['event_flow_binding.mjs', 'event_flow_contract.py', 'capture_runtime.mjs', 'SOURCE_DATA_CATALOG.json'],
         fields=['completion.eventFlow.flows[].plan', 'completion.eventFlow.flows[].sourceBindings', 'completion.eventFlow.flows[].routeVisibility', 'completion.eventFlow.flows[].arrivalAreaId'],
         factories=['compileFlowIntent', 'compileFlowPlan', 'compileFlowRoute', 'createFlowGraphicPass'],
         consumers=['evaluateFlowFrame', 'createFlowGraphicPass.draw', 'arrivalAreaId source-bound causal cue'],
         tests=['test_event_flow_binding.mjs'], exposed='CONDITIONAL', status='BLOCKED',
         reason='Generic Flow compiler/evaluator/consumer forwarding is CPU verified, including heading, pulse, hold and arrival-to-Area timing. Current historical flows[] is empty: no admitted historical routes/actors exist. Production route/highlight drawing is deliberately hidden; no movement is fabricated.',
         blockers=[('MISSING_VERIFIED_HISTORICAL_ACTOR_ROUTE', 'The historical fixture has no admitted actor identity/role/date/position/route plan; generic Flow CPU support cannot establish historical movement.')])
    for feature_id in ['FLOW.ROUTE_REVEAL', 'FLOW.DIRECTIONAL_FLOW']:
        rows[feature_id]['runtimeSelected'] = 'NO'
        rows[feature_id]['reason'] += ' In the production HIDDEN route mode, routeFraction=0 and directionalActive=false; visible route/highlight is not selected.'

    # Qualified source-only admission accepts known endpoints/held cores without
    # claiming complete opponent ownership or measured daily front observations.
    bind(['TERRITORY.SUPPLIED_AREA_COLOR', 'TERRITORY.ARCHIVAL_FRONT_ONLY', 'PLANNER.V4_PARTIAL_ARCHIVAL_PROFILE'],
         files=['history_admission.py', 'source_observations.mjs', 'production_area_bridge.mjs', 'SOURCE_DATA_CATALOG.json'],
         fields=['completion.dataPolicy=QUALIFIED_SOURCE_ONLY'],
         factories=['assess_history', 'suppliedFrontObservations', 'createProductionAreaPass'],
         consumers=['reviewed held-core/partial-front source selector', 'unchanged qualified Area/front consumer'],
         tests=['test_history_admission.py', 'test_runtime_binding.mjs', 'test_frontier_extension.mjs'], selected='YES',
         reason='The qualified source-only fixture admits preserved held-core schematic states and approximate partial official front holds with uncertainty intact. Actual selectors cover 2400 CPU frames; no opposite ownership complement, unobserved daily fronts or measured bilateral occupation is inferred.')

    # Strict frontend, source-bound metadata, and actual safe local HTTP tests.
    bind(['STUDIO.STRUCTURED_PRESET', 'PLANNER.V4_FROZEN_80S', 'STUDIO.TITLE_METADATA', 'STUDIO.ADVANCED_VISUAL_PROMPT'],
         files=['contract_v2.py', 'studio_controller.py', 'studio_entry.py', 'runtime_bridge.py', 'STUDIO_PROMPT_V2.schema.json'],
         fields=['prompt.schema=WORLD_ENGINE_STUDIO_PROMPT_V2', 'prompt.preset=VERIFIED_FRONT_V4_80S', 'prompt.completion', 'prompt.title'],
         factories=['normalize_submission', 'normalize_completion', 'StudioController._normal'],
         consumers=['preserved frozen V4 validator', 'prepare_runtime_request'],
         tests=['test_contract_completion.py', 'test_studio_completion_path.py'], exposed='YES', addressable='YES', selected='YES', renderer='NONE',
         reason='The new strict structured completion profile reaches the real frozen normalizer and authenticated private submission path. Only supported fields/preset are accepted; arbitrary natural-language visual requests remain unsupported. Actual GPU start remains gated.')
    # The original identity is broader than the new bounded structured subset.
    rows['STUDIO.ADVANCED_VISUAL_PROMPT']['implementationExists'] = 'NO'
    rows['STUDIO.ADVANCED_VISUAL_PROMPT']['reason'] += ' The original arbitrary-field/free-natural-language capability is still absent; this receipt documents the limited versioned replacement, not completion of that broader capability.'

    bind(['STUDIO.DURATION_SELECTION'], files=['contract_v2.py', 'STUDIO_PROMPT_V2.schema.json'],
         fields=['prompt.durationSeconds=80'], factories=['normalize_submission'], consumers=['preserved V2 preset validator'],
         tests=['test_contract_completion.py'], exposed='YES', addressable='YES', selected='YES', renderer='NONE',
         reason='The completion preset admits exactly eighty seconds/2400 frames. Older V1/V3 duration support through 120/180/300/600 remains preserved in its separate entry; it is not advertised as new completion preset support.')
    for feature_id in ['STUDIO.DIRECT_SCENE_INPUT', 'PLANNER.STUDIO_DIRECT_SCENE']:
        r = rows[feature_id]
        r.update({'studioV2Exposed': 'NO', 'sceneJSONAddressable': 'NO', 'runtimeSelected': 'NO', 'actualRendererConsumer': 'NONE',
                  'reason': 'Direct raw Scene input is preserved in the older V1 entry only. The new structured completion preset does not accept arbitrary sceneJson or relax the frozen eighty-second validator; its exact parent Scene is selected internally.'})

    # Auth/CSRF/private state and job metadata are real CPU/local HTTP checks,
    # but none is a renderer draw consumer.
    bind(['STUDIO.OWNER_AUTH', 'STUDIO.ORIGIN_CSRF', 'STUDIO.HTTPS_SETUP', 'STUDIO.MOBILE_UI',
          'STUDIO.PREFLIGHT', 'STUDIO.EXPLICIT_START', 'STUDIO.SOURCE_IMAGE_BINDING',
          'STUDIO.PRIVATE_STATE', 'STUDIO.JOB_LOOKUP'],
         files=['studio_entry.py', 'studio_controller.py', 'runtime_bridge.py', 'execution_manager.py'],
         fields=['authenticated inherited Studio endpoints', 'prompt.completion'],
         factories=['StudioController', 'Application.handler', 'prepare_runtime_request'],
         consumers=['existing owner authentication/Origin/CSRF/private submission/preflight handlers'],
         tests=['test_studio_completion_path.py', 'test_completion_package.py'], exposed='INTERNAL_ONLY', addressable='NO', selected='YES', renderer='NONE',
         reason='Actual local HTTP authentication/CSRF/Host-Origin and private submission tests preserve the existing security boundaries and completion metadata. This is CPU/service-contract evidence, not mobile NVIDIA rendering or a paid start; preflight correctly keeps rendering blocked without quality/image approval.')

    bind(['STUDIO.INTERVAL_SFX_REVISION', 'STUDIO.SFX_INTERVAL_REVISION'],
         files=['revision_bridge.py', 'studio_controller.py', 'execution_manager.py', 'runtime_bridge.py'],
         fields=['startSeconds', 'endSeconds', 'prompt', 'sfx'],
         factories=['revision_bridge.plan_revision', 'StudioController.revise', 'execution_manager.revise'],
         consumers=['original SFX-only revision planner', 'capture-scoped parent/silent-video reuse'],
         tests=['test_revision_bridge.py', 'test_studio_completion_path.py'], exposed='YES', addressable='YES', selected='CONDITIONAL', renderer='NONE',
         reason='The SFX revision bridge now preserves videoPlan, integration, completionV2 and the parent capture namespace while reusing all video scenes. Actual original revision checks and an explicitly fake completed parent are CPU tested; no real completed candidate or audio output is claimed.')

    bind(['STUDIO.SFX_CONTROLS', 'STUDIO.SFX_TOGGLE_GAIN', 'STUDIO.SFX_AUTHORED_CUES'],
         files=['contract_v2.py', 'revision_bridge.py', 'studio_controller.py'],
         fields=['prompt.sfx.enabled', 'prompt.sfx.gain', 'prompt.sfx.cues', 'prompt.sfx.exportWav'],
         factories=['normalize_submission', 'original normalize_sfx'], consumers=['preserved event-bound SFX normalizer'],
         tests=['test_contract_completion.py', 'test_revision_bridge.py'], exposed='YES', addressable='YES', selected='YES', renderer='NONE',
         reason='Structured completion input and SFX-only revisions retain exact normalized audio/cue metadata without dropping completion identity. Source-bound cue scheduling/mixing/mux implementations are preserved; no new WAV/AAC file or listening-quality proof is produced here.')

    # Native ASTRA/map/Planner owners remain selected by the preserved parent
    # source graph. New CPU tests prove configuration wiring, not these shaders.
    preserved_source_ids = [f['id'] for f in audit['features'] if (
        f['id'].startswith(('ASTRA.', 'MAP.')) and f['id'] != 'MAP.REFERENCE_PRESENTATION_ROLL')]
    for feature_id in preserved_source_ids:
        r = rows[feature_id]
        r['sourceFiles'] += [source(ROOT / 'capture_runtime.mjs'), source(ROOT / 'runtime_binding.mjs')]
        r['studioV2Exposed'] = 'INTERNAL_ONLY'
        r['sceneJSONAddressable'] = 'CONDITIONAL'
        r['runtimeSelected'] = 'YES'
        r['actualRendererConsumer'] = 'SOURCE_BOUND'
        r['reason'] = ('The unchanged native/ASTRA source owner remains in the inherited source-bound render graph. '
                       'New completion alias/config tests do not execute this feature shader or establish GPU output; authentic regional support/NoData fallback is retained. ' + previous[feature_id]['reason'])

    # Exact named advanced owners still absent from this compatible connection.
    missing_connections = {
        'TERRITORY.COMPLEMENTARY_SCALAR_CONTROL': ('INCOMPATIBLE_SCALAR_OWNERSHIP', 'The five-second complementary scalar owner requires a compatible complete ownership/domain contract. Partial historical fronts/held-core complements cannot safely supply that field.'),
        'FRONTIER.MOVING_SCALAR_LIGHT': ('INCOMPATIBLE_SCALAR_FRONTIER_OWNER', 'The exact high-grade scalar frontier owner is not selected. The new supplied-polyline alpha envelope is a distinct compatible consumer, not proof that this scalar feature is connected.'),
        'FRONTIER.TERRAIN_DESTINATION_LIGHT': ('MISSING_POLYLINE_TERRAIN_TEXTURE_CONTRACT', 'The preserved Area overlay has no source-terrain sampler input. The exact scalar destination-light shader remains unselected; a narrow compatible source-bound texture/light consumer is still required.'),
        'FRONTIER.OUTER_DOMAIN_GOLD': ('MISSING_REGISTERED_DOMAIN_LIGHT_SELECTION', 'The outer-domain gold owner requires same-frame registered domain coverage and is not selected by the current long Area adapter; a coastline/domain edge cannot be labelled a military front.'),
        'MAP.REFERENCE_PRESENTATION_ROLL': ('UNCONNECTED_COHERENT_ROLL_PROFILE', 'Actual V5 event tracking is connected, but the five-second coherent roll/overscan owner is not. No rotation input is exposed or silently ignored.'),
        'DETAIL.POST_ARRIVAL_APPROACH': ('UNCONNECTED_FULL_VISUAL_DETAIL_ADAPTER', 'The protected parent native Detail lock is preserved, but the separate full post-arrival visual Detail adapter and its native-render admission certificate are not selected.'),
        'TERRITORY.GAIN_STYLE': ('UNCONNECTED_ADVANCED_SCALAR_GAIN_STYLE', 'Bounded production Area opacity/white-gold controls are connected; the separate advanced scalar gain-brightness owner is not selected by that bridge.'),
        'FLOW.VISUAL_POLISH_PROFILE': ('MISSING_HISTORICAL_FLOW_AND_POLISH_SELECTION', 'The generic Flow core is source-bound, but this distinct approved mobile polish profile is not imported by the new binding and historical actor/route inputs are absent.'),
        'PLANNER.CAUSAL_TRACKS': ('MISSING_HISTORICAL_CAUSAL_TRACKS', 'The original optional schematic causal_tracks validator is not a factual historical unit source. The new source-bound arrivalAreaId cue is different; no historical route/contact track is fabricated.'),
        'PLANNER.FAMILY_TRANSPORT': ('MISSING_SOURCE_BACKED_HISTORICAL_TRANSPORT', 'The portable TRANSPORT family compiler remains separate from the strict frozen WAR preset. Generic canonical Flow inputs now have a consumer, but the current historical fixture supplies no admitted transport subevent.'),
        'UNITS.NATIONAL_TABLETS': ('MISSING_HISTORICAL_NATIONAL_UNIT_ANCHORS', 'Original national-tablet artwork exists but is not selected by the new current historical route, and no reviewed country/role/date/position anchors are supplied.'),
        'UNITS.SAFE_STATIC_SCALE': ('MISSING_NATIONAL_UNIT_LAYOUT_INPUTS', 'The old bounded national-tablet scale owner needs admitted per-frame historical anchors and is not selected in the current completion fixture.'),
    }
    for feature_id, (code, message) in missing_connections.items():
        rows[feature_id].update({'studioV2Exposed': 'NO', 'sceneJSONAddressable': 'NO', 'runtimeSelected': 'NO',
            'actualRendererConsumer': 'NONE', 'cpuTests': [], 'evidenceKind': 'SOURCE_STATIC',
            'status': 'BLOCKED', 'reason': message, 'blockingReasons': [{'code': code, 'reason': message}]})
        rows[feature_id]['sourceFiles'] += [source(ROOT / 'runtime_binding.mjs')]

    # No national actor API is exposed merely because a role/date validator is
    # preserved. Current native city/location markers are not military units.
    for feature_id in ['UNITS.HISTORICAL_PARTICIPATION_GATE', 'UNITS.NATIVE_MARKERS']:
        r = rows[feature_id]
        r['studioV2Exposed'] = 'INTERNAL_ONLY' if feature_id.endswith('NATIVE_MARKERS') else 'NO'
        r['sceneJSONAddressable'] = 'CONDITIONAL' if feature_id.endswith('NATIVE_MARKERS') else 'NO'
        r['runtimeSelected'] = 'YES' if feature_id.endswith('NATIVE_MARKERS') else 'NO'
        r['actualRendererConsumer'] = 'SOURCE_BOUND' if feature_id.endswith('NATIVE_MARKERS') else 'NONE'
        r['reason'] = 'Historical role/flag validation does not create actor positions; native geographic markers remain distinct and unchanged. ' + previous[feature_id]['reason']

    # Unknown actual old80s media remains unknown; nothing in a CPU suite may
    # upgrade this identity into actual-output evidence.
    rows['STUDIO.ACTUAL_80S_INPUT_OUTPUT'].update({'implementationExists': 'NOT_VERIFIED',
        'studioV2Exposed': 'NO', 'sceneJSONAddressable': 'NO', 'runtimeSelected': 'NO', 'actualRendererConsumer': 'NONE',
        'status': 'UNVERIFIED', 'reason': 'Actual 66430/eighty-second private input/output remains unavailable. Source selection/CPU tests cannot replace a real artifact comparison.'})

    # The ledger includes one unambiguous receipt per original identity. Files
    # may appear in many independent records; source existence is not GPU proof.
    proof = None
    if image_proof is not None:
        ref = source(image_proof)
        proof = json.loads((REPO / ref['path']).read_bytes())
    if source_commit is None:
        source_commit = proof.get('sourceCommit') if proof else subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=REPO, check=True,
            capture_output=True, text=True, timeout=10).stdout.strip()
    if not isinstance(source_commit, str) or not re.fullmatch('[a-f0-9]{40}', source_commit):
        raise ValueError('CONNECTION_SOURCE_COMMIT_INVALID')
    if proof and proof.get('sourceCommit') != source_commit:
        raise ValueError('CONNECTION_IMAGE_SOURCE_COMMIT_MISMATCH')
    result = {'schema': 'WORLD_ENGINE_COMPLETION_CONNECTION_RECEIPTS_V1', 'sourceCommit': source_commit,
              'candidateImage': {'state': 'NOT_BUILT', 'digest': None},
              'testResult': source(cpu_path), 'receipts': [rows[f['id']] for f in audit['features']]}
    if image_proof is not None:
        result['candidateImage'] = {'state': 'INDEPENDENT_PULL_VERIFIED', 'digest': proof.get('imageDigest'), 'proof': ref}
    ledger.validate_connections(result, audit, repo=REPO)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-proof', help='Repo-relative public IMAGE_PROOF.json after actual CI verification.')
    parser.add_argument('--source-commit', help='Explicit exact source commit; otherwise verified image proof or read-only git HEAD.')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/CONNECTION_RECEIPTS.json')
    args = parser.parse_args()
    value = build(image_proof=args.image_proof, source_commit=args.source_commit)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = ledger.write_reports(args.output)
    print(json.dumps({'receipts': len(value['receipts']), 'features': report['featureCount'],
        'unwired': report['previouslyUnwiredCount'], 'statusCounts': report['statusCounts'],
        'cpuFeatureProofs': report['axisCounts']['cpuProof'], 'gpuFeatureProofs': report['axisCounts']['gpuProof'],
        'actualOutputAppliedCount': report['actualOutputAppliedCount'], 'candidateImage': report['candidateImage']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
