"""Production collect-all parity, preserving the recorded v013 fixture."""
from pathlib import Path
import json
from copy import deepcopy
from engine.frame_grid import canonicalize_plan
from engine.gpu_preflight import collect_all
from engine.qa_planner import configure_qa_schema

class Bundle:
    job_id='framegrid-parity'
    def __init__(self,folder):self.folder=folder
    def write(self,name,value):
        (self.folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))

def check(plan,folder):
    folder.mkdir(parents=True,exist_ok=True);(folder/'scene_json').mkdir(exist_ok=True)
    (folder/'scene_plan.json').write_text(json.dumps(plan,ensure_ascii=False))
    for scene in plan['scenes']:(folder/'scene_json'/(scene['scene_id']+'.json')).write_text(json.dumps(scene,ensure_ascii=False))
    try:collect_all(folder,plan,Bundle(folder))
    except RuntimeError as error:
        if str(error)!='COLLECT_ALL_PREFLIGHT_FAILED':raise
    return json.loads((folder/'preflight.json').read_text())

def run(folder):
    configure_qa_schema();folder=Path(folder)
    old=json.loads(Path(__file__).with_name('framegrid_v013_fixture.json').read_text())
    before=check(old,folder/'before')
    fixed=canonicalize_plan(deepcopy(old));after=check(fixed,folder/'after')
    print('::notice title=Production parity checks::'+json.dumps(dict(before_checks=before['checks'],after_checks=after['checks'],after_scenes=[dict(scene_id=s['scene_id'],passed=s['passed']) for s in after['scenes']]),ensure_ascii=False))
    assert [s['passed'] for s in before['scenes']]==[False,False,True,False],before
    assert after['passed'],after
    assert [s['frame_count'] for s in fixed['metadata']['frame_grid']['scenes']]==[64,88,93,115]
    from engine.qa_planner import generate_deployment_plan
    from deployment.gcube.reference_preflight import REQUESTS
    fresh=generate_deployment_plan(dict(REQUESTS['shipping'],direction_profile='REFERENCE_MASTER',quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True))
    generated=check(fresh,folder/'generated')
    assert generated['passed'],generated
    assert fresh['metadata']['frame_grid']['total_frames']==360
    report=dict(generated=generated,before=before,after=after,frame_grid=fixed['metadata']['frame_grid'],GPU='NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('::notice title=Frame-grid production parity::'+json.dumps(dict(before=[s['passed'] for s in before['scenes']],after=[s['passed'] for s in after['scenes']],frames=fixed['metadata']['frame_grid'])))
    return report
if __name__=='__main__':
    import sys
    run(sys.argv[1])
