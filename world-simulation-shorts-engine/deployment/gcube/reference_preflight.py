"""Four-domain REFERENCE_MASTER geometry/planning admission, no GPU launch."""
from pathlib import Path
import json,tempfile
from engine.qa_planner import generate_deployment_plan

REQUESTS={
 'shipping':dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True),
 'aviation':dict(topic='서울 도쿄 타이베이 항공 네트워크가 연결된다면?',duration=12,qa_mode=True),
 'country':dict(topic='중국 한국 일본 국가별 위치와 반응',duration=12,qa_mode=True),
 'network':dict(topic='뉴욕 런던 서울 도쿄 세계 항공 네트워크가 확장된다면?',duration=12,qa_mode=True),
}

def run(folder):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);reports=[]
 for name,raw in REQUESTS.items():
  try:
   p=generate_deployment_plan(dict(raw,direction_profile='REFERENCE_MASTER',quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True))
   (folder/(name+'.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2))
   qc=p['metadata']['reference_native_qc'];planning=p['metadata']['direction_qc']
   reports.append(dict(fixture=name,passed=p['gate']['passed'] and qc['passed'] and planning['passed'],errors=p['gate']['errors'],perceptual=qc,planning=planning,beats=[dict(scene_id=s['scene_id'],start=s['start_time'],end=s['start_time']+s['duration'],**s['direction']) for s in p['scenes']]))
  except Exception as error:
   reports.append(dict(fixture=name,passed=False,error_type=type(error).__name__,error=str(error),details=getattr(error,'details',None)))
 summary=dict(passed=all(r['passed'] for r in reports),fixtures=reports,GPU='NOT_RUN')
 (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary

if __name__=='__main__':
 import sys
 with tempfile.TemporaryDirectory() as folder:
  result=run(sys.argv[1] if len(sys.argv)>1 else folder)
  print('::notice title=Reference Master fixtures::'+json.dumps(dict(passed=result['passed'],GPU=result['GPU'],fixtures=[dict(fixture=f['fixture'],passed=f['passed'],errors=f.get('errors',f.get('details')),perceptual=f.get('perceptual',{}).get('findings'),warnings=f.get('planning',{}).get('warning_count')) for f in result['fixtures']]),ensure_ascii=False))
  raise SystemExit(not result['passed'])
