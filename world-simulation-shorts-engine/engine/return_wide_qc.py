"""Preset-scoped camera QA policy; ordinary production QC is never replaced."""
from pathlib import Path
import json,math
from .return_wide_camera import PRESET,TIMELINE,validate_camera
from . import qc
RULES=('WIDE_PRESENT','EVENT_LOCATION_PRESENT','ZOOM_IN_PRESENT','EVENT_VIEW_PRESENT','EVENT_HOLD_PRESENT','EVENT_RESOLVED_PRESENT','ZOOM_OUT_PRESENT','FINAL_WIDE_PRESENT','NO_UNEXPECTED_ORBIT','NO_UNEXPECTED_ROTATION','NO_NEXT_EVENT','FRAME_GRID_VALID')
# Intentional QA stillness and one event are incompatible with these narrative
# production policies. Every other technical/post-draw failure remains blocking.
PRODUCTION_ONLY={'FROZEN_INTERVAL','FIRST_HALF_SECOND_STATIONARY','FINAL_RETENTION_GATE_FAILED','ACTUAL_RENDER_RETENTION_GATE_FAILED'}
def state_at(frame):return next((n for n,a,b in TIMELINE if a<=frame<b),'END')
def camera_qc(plan,audits):
    rows=qc._audit_frames(audits);checks={name:True for name in RULES}
    checks['FRAME_GRID_VALID']=validate_camera(plan)['passed'] and len(rows)==450
    checks['NO_NEXT_EVENT']=len(plan.get('scenes',[]))==1 and len(plan['scenes'][0]['visual_events'])==3
    failures=[];positions=[];fovs=[];quats=[]
    for i,row in enumerate(rows):
        t=row.get('timestamp',row.get('t'));frame=row.get('frame_index',i)
        if frame!=i or not isinstance(t,(int,float)) or abs(t-i/30)>1e-7 or row.get('cameraState')!=state_at(i):checks['FRAME_GRID_VALID']=False
        p=row.get('cameraPosition',[]);q=row.get('cameraQuaternion',[]);f=row.get('cameraFov')
        if len(p)!=3 or len(q)!=4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p+q+[f]):
            checks['NO_UNEXPECTED_ORBIT']=checks['NO_UNEXPECTED_ROTATION']=False;continue
        if sum(x*x for x in p)<1e-12 or not 0<f<180 or abs(sum(x*x for x in q)-1)>1e-5:
            checks['NO_UNEXPECTED_ORBIT']=checks['NO_UNEXPECTED_ROTATION']=False;continue
        positions.append(p);quats.append(q);fovs.append(f)
    if len(positions)!=450:checks['FRAME_GRID_VALID']=False
    if len(positions)==450:
        radii=[math.sqrt(sum(x*x for x in p)) for p in positions];lat=math.radians(plan['scenes'][0]['camera_start']['lat']);lon=math.radians(plan['scenes'][0]['camera_start']['lon']);normal=[math.cos(lat)*math.cos(lon),math.sin(lat),-math.cos(lat)*math.sin(lon)]
        checks['NO_UNEXPECTED_ORBIT']=all(max(abs(p[j]/r-normal[j]) for j in range(3))<1e-7 for p,r in zip(positions,radii))
        checks['NO_UNEXPECTED_ROTATION']=all(abs(sum(x*y for x,y in zip(quats[0],q)))>1-1e-8 for q in quats)
        stable=lambda a,b,r,f:all(abs(radii[i]-r)<1e-7 and abs(fovs[i]-f)<1e-7 for i in range(a,b))
        checks['WIDE_PRESENT']=stable(0,90,3.5,64)
        checks['EVENT_VIEW_PRESENT']=stable(150,180,1.2,48)
        checks['EVENT_HOLD_PRESENT']=stable(240,330,1.2,48)
        checks['FINAL_WIDE_PRESENT']=stable(420,450,3.5,64)
        checks['ZOOM_IN_PRESENT']=radii[149]<radii[90]-2 and all(radii[i]<=radii[i-1]+1e-9 for i in range(91,151))
        checks['ZOOM_OUT_PRESENT']=radii[419]>radii[360]+2 and all(radii[i]>=radii[i-1]-1e-9 for i in range(361,421))
        checks['EVENT_RESOLVED_PRESENT']=stable(330,360,1.2,48)
    def text_present(a,b,text):return any(any(x.get('text')==text and x.get('opacity',0)>.1 for x in row.get('labels',[])) for row in rows[a:b])
    checks['EVENT_LOCATION_PRESENT']=text_present(60,90,'SUEZ CANAL')
    checks['EVENT_HOLD_PRESENT'] &= text_present(240,330,'CANAL CLOSED')
    checks['EVENT_RESOLVED_PRESENT'] &= text_present(330,360,'CANAL OPEN')
    failures=[name for name,passed in checks.items() if not passed]
    return dict(passed=not failures,failures=failures,checks=checks,frames=len(rows),scope='post-draw camera-state and visible-label QA only; no production retention scoring')
def apply_policy(plan,technical,camera):
    if plan.get('metadata',{}).get('camera_test_preset')!=PRESET:return technical
    report=dict(technical);all_failures=technical.get('failures',[])
    report['production_policy_not_applicable']=[x for x in all_failures if x in PRODUCTION_ONLY]
    report['failures']=sorted(set([x for x in all_failures if x not in PRODUCTION_ONLY]+camera['failures']))
    report['camera_qa']=camera;report['passed']=not report['failures'];report['publication_quality']=False
    report['qa_preset']=PRESET
    return report
def run_qc(video,plan,audits,outdir,**kwargs):
    if plan.get('metadata',{}).get('camera_test_preset')!=PRESET:return qc.run_qc(video,plan,audits,outdir,**kwargs)
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    technical=qc.run_qc(video,plan,audits,outdir/'technical',**kwargs)
    report=apply_policy(plan,technical,camera_qc(plan,audits))
    from .storage import atomic_json
    atomic_json(outdir/'qc_report.json',report)
    (outdir/'qc_report.md').write_text('# Return-to-wide camera QA\n\n'+('PASS' if report['passed'] else 'FAIL')+'\n\n'+json.dumps(report['camera_qa'],indent=2)+'\n\nTechnical failures: '+', '.join(report['failures']))
    return report
