"""Actual v022 map-state audit, scoped to explicitly sourced infographic plans.

The original decoded-video, GPU, clipping, assets, audio and camera checks run
first. Legacy narrative-retention scoring is replaced only for this new family
by its authored geometry/state/speech evidence; legacy plans retain exact QC.
"""
from pathlib import Path
from fractions import Fraction
from . import qc
from .storage import atomic_json


def audit_map_state(plan, audits):
    from .infographic_contract import validate_infographic
    admission = validate_infographic(plan)
    rows = qc._audit_frames(audits)
    errors, events = [], []
    if not admission['passed']:
        return dict(passed=False, errors=admission['errors'], events=[], pixel_quality='NOT_DETERMINED')
    for scene in plan['scenes']:
        selection = scene['infographic']
        own = [r for r in rows if r.get('scene_id') == scene['scene_id']]
        if len(own) != scene['frame_count']:
            errors.append(dict(code='INFOGRAPHIC_AUDIT_FRAME_COUNT_INVALID', scene_id=scene['scene_id']))
        for index, row in enumerate(own):
            receipt = row.get('infographic')
            if (not isinstance(receipt, dict) or receipt.get('version') != 'v022'
                    or receipt.get('frame') != index
                    or receipt.get('registry_sha256') != selection['registry_sha256']
                    or receipt.get('profile_sha256') != selection['profile_sha256']):
                errors.append(dict(code='INFOGRAPHIC_AUDIT_SOURCE_INVALID', scene_id=scene['scene_id'], frame=index))
                continue
            if receipt.get('primary_motion_effect_count', 2) > 1:
                errors.append(dict(code='INFOGRAPHIC_EFFECT_OVERDENSITY', scene_id=scene['scene_id'], frame=index))
            if not receipt.get('layout', {}).get('passed'):
                errors.append(dict(code='INFOGRAPHIC_LAYOUT_INVALID', scene_id=scene['scene_id'], frame=index))
        for event in selection['events']:
            steady = own[event['transition_end_frame']:event['end_frame']]
            geometry_frames = text_frames = marked_frames = 0
            primary_text = (event['text']['event_title'] if event['primary_role'] == 'EVENT_TITLE'
                            else event['text']['location_label'])
            for row in steady:
                receipt = row.get('infographic', {})
                geometries = receipt.get('geometry', [])
                if any(g.get('geometry_id') in event['target_geometry_refs']
                       and g.get('event_id') == event['id'] and g.get('visible') is True
                       and g.get('state') == event['state_after'] for g in geometries):
                    geometry_frames += 1
                labels = receipt.get('labels', [])
                if any(l.get('event_id') == event['id'] and l.get('role') == event['primary_role']
                       and l.get('displayed_text') == primary_text and l.get('opacity', 0) > .1 for l in labels):
                    text_frames += 1
                if any(l.get('displayed_text') == event['watermark'] and l.get('opacity', 0) > .1 for l in labels):
                    marked_frames += 1
            # Some source geometry is horizon/frustum occluded during travel.
            # Require sustained real projected state, not a label-only assertion.
            required = min(len(steady), max(1, round(float(Fraction(selection['fps'])) / 3)))
            if event['target_geometry_refs'] and geometry_frames < required:
                errors.append(dict(code='INFOGRAPHIC_GEOMETRY_STATE_NOT_VISIBLE', event_id=event['id']))
            if primary_text and text_frames < required:
                errors.append(dict(code='INFOGRAPHIC_PRIMARY_TEXT_NOT_READABLE', event_id=event['id']))
            if event['evidence_type'] == 'hypothetical_scenario' and marked_frames < len(steady):
                errors.append(dict(code='INFOGRAPHIC_HYPOTHESIS_NOT_VISIBLE', event_id=event['id']))
            events.append(dict(event_id=event['id'], steady_frames=len(steady),
                               geometry_visible_frames=geometry_frames, text_visible_frames=text_frames,
                               hypothesis_visible_frames=marked_frames))
    return dict(passed=not errors, errors=errors, events=events,
                pixel_quality='Requires decoded output and human comparison; audit alone is insufficient')


def run_qc(video, plan, audits, outdir, **kwargs):
    if not any(s.get('infographic') for s in plan.get('scenes', [])):
        return qc.run_qc(video, plan, audits, outdir, **kwargs)
    folder = Path(outdir)
    technical = qc.run_qc(video, plan, audits, folder / 'technical', **kwargs)
    state = audit_map_state(plan, audits)
    report = dict(technical)
    # These exact legacy pacing heuristics do not model the explicit measured
    # Production contract or approved camera-only QA. All other failures remain.
    scoped = {'FROZEN_INTERVAL', 'FIRST_HALF_SECOND_STATIONARY',
              'FINAL_RETENTION_GATE_FAILED', 'ACTUAL_RENDER_RETENTION_GATE_FAILED'}
    report['legacy_pacing_not_applicable'] = [f for f in technical['failures'] if f in scoped]
    report['failures'] = [f for f in technical['failures'] if f not in scoped]
    if plan.get('metadata', {}).get('camera_test_preset') == 'SECOND_EVENT_ADAPTIVE_WIDE_TEST':
        from .second_event_qc import camera_qc
        camera = camera_qc(plan, audits)
        report['camera_qa'] = camera
        report['failures'].extend(camera['failures'])
        report['publication_quality'] = False
    else:
        from .semantic_timeline import validate_production_plan
        measured = validate_production_plan(plan)
        report['measured_semantic_policy'] = measured
        if not measured['passed']:
            report['failures'].append('MEASURED_SEMANTIC_QC_FAILED')
    report['map_state'] = state
    report['failures'].extend(e['code'] for e in state['errors'])
    report['failures'] = sorted(set(report['failures']))
    report['passed'] = not report['failures']
    report['human_visual_approval'] = 'REQUIRED'
    atomic_json(folder / 'qc_report.json', report)
    (folder / 'qc_report.md').write_text('Map infographic v022 QC\n\n' +
                                      ('PASS' if report['passed'] else 'FAIL') + '\n')
    return report
