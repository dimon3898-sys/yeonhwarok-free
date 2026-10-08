"""Full singleton admission and shared camera projection, no GPU draw."""
import json,subprocess
from pathlib import Path
from engine.qa_planner import generate_deployment_plan
from deployment.gcube.framegrid_preflight import check
from engine.single_event_camera import ROOT,PRESET

def run(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    plan=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True))
    p=folder/'plan.json';p.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    result=subprocess.run(['node','tools/test_single_event_camera.mjs',str(p)],cwd=ROOT,capture_output=True,text=True,check=True)
    geometry=json.loads(result.stdout);(folder/'camera.json').write_text(result.stdout)
    preflight=check(plan,folder/'collect-all');assert preflight['passed'],preflight
    native=preflight['scenes'][0]['checks'][1]['report']['pose_records']
    for record,expected in zip(native,geometry['frames']):
        assert record['frame_index']==expected['frame']
        assert record['cameraPosition']==expected['position']
        assert record['cameraFov']==expected['fov']
    assert len(native)==360
    summary=dict(passed=True,timeline=plan['scenes'][0]['single_event_camera']['timeline'],wide=geometry['wide'],event=geometry['event'],frames=360,gap=0,overlap=0,Orbit=False,GPU='NOT_RUN',collect_all=preflight['passed'])
    (folder/'REPORT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print('::notice title=Single-event camera::'+json.dumps(summary,ensure_ascii=False));return summary
if __name__=='__main__':
    import sys
    run(sys.argv[1])
