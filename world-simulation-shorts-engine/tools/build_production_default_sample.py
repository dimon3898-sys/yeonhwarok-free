"""Create one bounded production integration plan, without starting a render."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from engine.assets import sha256_file
from engine.pace import retime_scene_plan
from engine.production import apply_production_defaults
from engine.schema import validate_plan
from engine.storage import ProjectStore, atomic_json


def refresh_sample_metadata(plan, original_metadata, source, source_sha):
    """Keep inherited evidence as provenance, never report its old timing as current."""
    metadata = plan.setdefault('metadata', {})
    metadata['approved_source_metadata'] = deepcopy(original_metadata)
    metadata['approved_source'] = {'path': str(source), 'sha256': source_sha,
                                   'public_version': 'PREMIUM_FLAT_MAP_15S_v004'}
    metadata['sample_builder'] = 'tools/build_production_default_sample.py'
    metadata['sample_scope'] = (f"Bounded {plan['duration']:g}-second Production Default integration candidate; "
                               "native video, mobile playback and sound QC are required before promotion. "
                               "No 75-second or MASTER rerender.")
    metadata['sample_contract'] = {
        'assertion_scope': 'Validated authored IR only; actual media QC is still required.',
        'production_candidate_authored': True, 'existing_plans_modified': False,
        'global_production_default_promoted': False, 'render_duration_limit_seconds': 15,
        'final_scene_is_actual_master_v3_earth': True,
        'new_network_edge_is_hypothetical': True,
    }
    metadata['camera_provenance'] = [
        {'scene_id': scene['scene_id'], 'start_time': scene['start_time'],
         'end_time': scene['start_time'] + scene['duration'],
         'source_ids': sorted({target['source_id'] for target in scene.get('geographic_targets', [])
                               if isinstance(target, dict) and target.get('source_id')} |
                              {scene['coordinates']['source_id']}),
         'motion_timing': deepcopy(scene.get('motion_timing', {})),
         'method': 'Retimed approved GIS-sourced rig; camera target is not a new geographic place'}
        for scene in plan['scenes']
    ]
    # The source distance receipt describes its old clock. Current distance labels
    # are generated and validated from each Scene's actual route timing.
    metadata.pop('route_metric', None)
    metadata.pop('estimates', None)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(APP.parent/'deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v004/scene_plan.json'))
    parser.add_argument('--projects', default=str(APP/'projects-production-default-v1'))
    parser.add_argument('--evidence', required=True, help='New directory; existing evidence is never overwritten')
    args = parser.parse_args()
    evidence = Path(args.evidence).resolve()
    if evidence.exists():
        raise FileExistsError('Preserve the existing evidence and use a new directory')
    source = Path(args.source).resolve()
    original = json.loads(source.read_text())
    if original['duration'] != 15 or len(original['scenes']) != 5:
        raise ValueError('Only the approved five-scene, 15-second source is supported by this test tool')
    source_sha = sha256_file(source)
    working = deepcopy(original)
    phrases = ['목적지가 바뀐다면?', '도쿄로 향합니다.', '다음은 타이베이.', '새 항로가 열립니다.', '연결.']
    for scene, phrase in zip(working['scenes'], phrases):
        scene['narration'] = phrase
    working['options'].update(tts=True, subtitles=False, bgm=True, sfx=True)
    working['request'].update(tts=True, subtitles=False, bgm=True, sfx=True, pace='FAST')
    normal = apply_production_defaults(deepcopy(working), pace='NORMAL', final_context_node='Shanghai')
    fast = apply_production_defaults(retime_scene_plan(working, [2.5, 2.5, 2.5, 2.5, 2.0]), pace='FAST', final_context_node='Shanghai')
    # This fixed two-second incoming handoff was measured with the actual V3
    # rig: its earlier settle keeps angular velocity below the preserved
    # 2.5-degree/frame gate. This is a Scene-local sample edit, not a relaxed
    # renderer gate or a global camera/timewarp rule.
    fast['scenes'][-1]['motion_timing'].update(
        camera_travel_duration=1.4, zoom_duration=1.4, dead_time_removed=.6)
    refresh_sample_metadata(normal, original.get('metadata', {}), source, source_sha)
    refresh_sample_metadata(fast, original.get('metadata', {}), source, source_sha)
    evidence.mkdir(parents=True)
    atomic_json(evidence/'normal_plan.json', normal, True)
    atomic_json(evidence/'candidate_plan.json', fast, True)
    gate = validate_plan(fast)
    atomic_json(evidence/'candidate_gate.json', gate, True)
    if not gate['passed']:
        raise ValueError(json.dumps(gate['errors'], ensure_ascii=False))
    store = ProjectStore(args.projects)
    result = store.create(fast['request'], fast)
    version = store.version_path(result['project']['id'], result['version'])
    proof = {'project_id': result['project']['id'], 'version': result['version'],
             'plan': str(version/'scene_plan.json'), 'normal_plan': str(evidence/'normal_plan.json'),
             'duration': 12, 'source': str(source), 'source_sha256': source_sha,
             'source_bytes_unchanged': sha256_file(source) == source_sha,
             'scene_durations_before': [3]*5, 'scene_durations_after': [2.5]*4+[2],
             'whole_video_speedup': False, 'tts_speed_changed': False,
             'script_shortened_before_tts': True, 'render_started': False,
             'sample_render_authorized': True, '75_second_render_authorized': False}
    atomic_json(evidence/'PROJECT_CREATED.json', proof, True)
    atomic_json(version/'PRODUCTION_INTEGRATION_SOURCE.json', proof, True)
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == '__main__':
    main()
