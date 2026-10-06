"""Copy a verified short Scene Plan into an isolated deployment QA project.

This is explicitly a deployment regression fixture, not a new topic generator.
It changes only S001 camera travel timing and never approves or starts a render.
"""
import argparse, copy, json, sys
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from deployment.mobile_server import checked_state_root
from engine.storage import ProjectStore

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-plan',required=True,type=Path)
    parser.add_argument('--state-root',required=True,type=Path)
    args=parser.parse_args()
    source=json.loads(args.source_plan.read_text())
    if not 5 <= source['duration'] <= 20 or source['options']['quality']!='HIGH':
        raise SystemExit('Only a short existing HIGH QA plan is permitted.')
    plan=copy.deepcopy(source)
    for field in ['project_id','version','plan_hash','gate','validation','approval']:
        plan.pop(field,None)
    first=plan['scenes'][0]
    if first['scene_id']!='S001' or first.get('rhythm_visual',{}).get('version')!='v1':
        raise SystemExit('Expected the preserved native rhythm regression sample.')
    old=first['motion_timing']['camera_travel_duration']
    first['motion_timing']['camera_travel_duration']=round(old-2/30,6)
    for item in plan.get('metadata',{}).get('camera_provenance',[]):
        if item['scene_id']=='S001':item['motion_timing']=copy.deepcopy(first['motion_timing'])
    plan['metadata'].pop('estimates',None)
    plan['metadata']['deployment_validation']={'scope':'One changed short native Scene; other completed Scenes must use cache.',
        'changed_scene_ids':['S001'],'source_plan_sha256':__import__('hashlib').sha256(args.source_plan.read_bytes()).hexdigest(),
        'camera_travel_before':old,'camera_travel_after':first['motion_timing']['camera_travel_duration'],
        'long_render_performed':False}
    store=ProjectStore(checked_state_root(args.state_root)/'projects')
    result=store.create(plan['request'],plan)
    if not result['plan']['gate']['passed']:
        raise SystemExit(json.dumps(result['plan']['gate'],ensure_ascii=False))
    print(json.dumps({'project_id':result['project']['id'],'version':result['version'],
        'duration':result['plan']['duration'],'plan_hash':result['plan']['plan_hash'],
        'gate_passed':True,'approved':False,'render_started':False},ensure_ascii=False))

if __name__=='__main__':main()
