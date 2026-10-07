"""Direction planning/native pose verification only; never launch a GPU renderer."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
from engine.qa_planner import generate_deployment_plan
from engine.direction import ROOT


def run(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    requests={
        'shipping':dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True),
        'aviation':dict(topic='서울 도쿄 타이베이 항공 네트워크가 연결된다면?',duration=12,qa_mode=True),
        'country':dict(topic='중국 한국 일본 국가별 위치와 반응',duration=12,qa_mode=True),
        'network':dict(topic='뉴욕 런던 서울 도쿄 세계 항공 네트워크가 확장된다면?',duration=20,qa_mode=False),
    }
    reports=[]
    for name,raw in requests.items():
        plan=generate_deployment_plan(dict(raw,quality='HIGH',pace='FAST_PLUS',tts=False,subtitle=False,bgm=True,sfx=True))
        path=folder/(name+'.json');path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
        output=folder/(name+'-native.json')
        result=subprocess.run(['node',str(ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(path),'--output',str(output)],cwd=ROOT,text=True,capture_output=True,timeout=180)
        native=json.loads(output.read_text()) if output.is_file() else {'passed':False,'failures':[{'code':'NATIVE_REPORT_MISSING'}]}
        reports.append(dict(fixture=name,duration=plan['duration'],scenes=len(plan['scenes']),
            plan_passed=plan['gate']['passed'],plan_errors=plan['gate']['errors'],
            native_passed=native['passed'],native_failures=native['failures'],
            angles=[s['numeric']['maxCameraAngleDegreesPerFrame'] for s in native.get('scene_checks',[])],
            hardware='NOT_RUN',direction_qc=plan['metadata']['direction_qc']))
    summary=dict(passed=all(r['plan_passed'] and r['native_passed'] for r in reports),fixtures=reports,gpu_render='NOT_RUN')
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary


if __name__=='__main__':
    if os.environ.get('WORLD_ENGINE_DIRECTION_VERSION')!='v012':raise SystemExit('DIRECTION_VERSION_NOT_SELECTED')
    with tempfile.TemporaryDirectory() as folder:
        result=run(folder)
        print('::notice title=Four direction fixtures::'+json.dumps(result,ensure_ascii=False))
        raise SystemExit(not result['passed'])
