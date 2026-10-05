"""Create a new appearance-only sample version; do not start any render job."""
import argparse
import copy
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from engine.assets import renderer_version, sha256_file
from engine.schema import validate_plan
from engine.storage import ProjectStore, atomic_json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', default=str(APP/'projects-flat-validation'))
    parser.add_argument('--project', default='project_c047b389d1f8')
    parser.add_argument('--separate-aircraft', action='store_true',
                        help='Correct only S004 display separation after the v004 draft is complete')
    args = parser.parse_args()
    store = ProjectStore(args.projects)
    source_version = 'v004' if args.separate_aircraft else 'v003'
    original = store.get(args.project, source_version)
    if original['project']['current_version'] != source_version:
        raise RuntimeError('Refusing to modify a different current immutable version')
    if args.separate_aircraft and store.status(args.project, source_version)['status'] not in {'complete','completed','qc_failed'}:
        raise RuntimeError('Finish and preserve the v004 draft before a targeted correction')
    plan = copy.deepcopy(original['plan'])
    if not (plan['duration'] == 15 and len(plan['scenes']) == 5):
        raise RuntimeError('Only the existing five-Scene 15-second sample can be polished')
    changes = []
    for scene in plan['scenes']:
        if args.separate_aircraft and scene['scene_id'] != 'S004':
            continue
        previous = copy.deepcopy(scene)
        if args.separate_aircraft:
            if scene.get('visual_polish') != {'version':'v004'} or scene.get('render_mode') != 'FLAT_MAP_PREMIUM':
                raise RuntimeError('The targeted correction requires the preserved v004 Flat S004')
            scene['visual_polish']['entity_separation'] = 'v1'
        else:
            scene['visual_polish'] = {'version':'v004'}
        renderer_version(scene)  # Fail before creating a version if an adapter is missing.
        restored = copy.deepcopy(scene)
        if args.separate_aircraft:
            restored['visual_polish'].pop('entity_separation')
        else:
            restored.pop('visual_polish')
        if restored != previous:
            raise RuntimeError('Appearance update unexpectedly changed Scene semantics')
        changes.append({'scene_id':scene['scene_id'], 'changed_fields':['visual_polish.entity_separation' if args.separate_aircraft else 'visual_polish'],
                        'events_routes_gis_camera_audio_timing_unchanged':True})
    gate = validate_plan(plan)
    if not gate['passed']:
        raise RuntimeError(json.dumps(gate['errors'], ensure_ascii=False))
    result = store.add_version(args.project, plan)
    version = store.version_path(args.project, result['version'])
    atomic_json(version/'VISUAL_POLISH_DIFF.json', {
        'source_version':source_version, 'source_plan_sha256':sha256_file(store.version_path(args.project,source_version)/'scene_plan.json'),
        'target_version':result['version'], 'duration':15, 'changes':changes,
        'public_visual_release':'PREMIUM_FLAT_MAP_15S_v004',
        'render_started':False, 'sample_render_authorized_by_current_task':True,
        '75_second_render_authorized':False, 'default_renderer_changed':False,
    }, exclusive=True)
    print(json.dumps({'project':args.project, 'version':result['version'],
                      'plan':str(version/'scene_plan.json'), 'gate_passed':result['plan']['gate']['passed'],
                      'render_started':False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
