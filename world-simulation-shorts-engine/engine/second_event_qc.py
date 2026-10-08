"""Camera-only QA policy for the exact v017 preset; production gates unchanged."""
from pathlib import Path
import math,json
from . import qc
from .second_event_camera import PRESET,TIMELINE,validate_camera
from .return_wide_qc import PRODUCTION_ONLY
RULES=tuple(n+'_PRESENT' for n,_,_ in TIMELINE)+('NO_UNEXPECTED_ORBIT','NO_UNEXPECTED_ROTATION','NO_NEXT_EVENT','FRAME_GRID_VALID','BOTH_LOCATIONS_SAFE','RESOLVED_BEFORE_ZOOM_OUT','LOCATION_AFTER_WIDE_LOCK')
def state_at(frame):return next((n for n,a,b in TIMELINE if a<=frame<b),'END')
def _normal(v):
    a,b=math.radians(v['lat']),math.radians(v['lon']);return [math.cos(a)*math.cos(b),math.sin(a),-math.cos(a)*math.sin(b)]
def camera_values(frame,scene):
    c=scene['second_event_camera'];t=frame/30
    if t<3:return scene['camera_start']
    if t<5:a,b,u=scene['camera_start'],c['event1_camera'],(t-3)/2
    elif t<12:return c['event1_camera']
    elif t<14:a,b,u=c['event1_camera'],c['adaptive_camera'],(t-12)/2
    elif t<16.5:return c['adaptive_camera']
    elif t<19.5:a,b,u=c['adaptive_camera'],c['event2_camera'],(t-16.5)/3
    else:return c['event2_camera']
    p=u*u*u*(u*(u*6-15)+10);n,m=_normal(a),_normal(b);angle=math.acos(max(-1,min(1,sum(x*y for x,y in zip(n,m)))))
    if angle>1e-8:n=[(math.sin((1-p)*angle)*x+math.sin(p*angle)*y)/math.sin(angle) for x,y in zip(n,m)]
    return dict(lon=math.degrees(math.atan2(-n[2],n[0])),lat=math.degrees(math.asin(max(-1,min(1,n[1])))),height=a['height']+(b['height']-a['height'])*p,fov=a['fov']+(b['fov']-a['fov'])*p)
def _quaternion(v):
    a,b=math.radians(v['lat']),math.radians(v['lon']);z=_normal(v);up=[-math.sin(a)*math.cos(b),math.cos(a),math.sin(a)*math.sin(b)]
    cross=lambda x,y:[x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0]]
    x=cross(up,z);y=cross(z,x);m11,m12,m13=x[0],y[0],z[0];m21,m22,m23=x[1],y[1],z[1];m31,m32,m33=x[2],y[2],z[2];trace=m11+m22+m33
    if trace>0:s=.5/math.sqrt(trace+1);return [(m32-m23)*s,(m13-m31)*s,(m21-m12)*s,.25/s]
    if m11>m22 and m11>m33:s=2*math.sqrt(1+m11-m22-m33);return [.25*s,(m12+m21)/s,(m13+m31)/s,(m32-m23)/s]
    if m22>m33:s=2*math.sqrt(1+m22-m11-m33);return [(m12+m21)/s,.25*s,(m23+m32)/s,(m13-m31)/s]
    s=2*math.sqrt(1+m33-m11-m22);return [(m13+m31)/s,(m23+m32)/s,.25*s,(m21-m12)/s]
def camera_qc(plan,audits):
    rows=qc._audit_frames(audits);checks={n:True for n in RULES};checks['FRAME_GRID_VALID']=validate_camera(plan)['passed'] and len(rows)==720
    s=plan['scenes'][0];c=s['second_event_camera'];checks['NO_NEXT_EVENT']=len(plan['scenes'])==1 and len(s['visual_events'])==5
    for i,row in enumerate(rows):
        state=state_at(i);t=row.get('timestamp',row.get('t'))
        if row.get('frame_index',i)!=i or not isinstance(t,(int,float)) or abs(t-i/30)>1e-7 or row.get('cameraState')!=state:checks['FRAME_GRID_VALID']=False
        p,q,f=row.get('cameraPosition',[]),row.get('cameraQuaternion',[]),row.get('cameraFov');v=camera_values(i,s);n=_normal(v);expected=[x*(1+v['height']) for x in n]
        valid=isinstance(p,list) and isinstance(q,list) and len(p)==3 and len(q)==4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in p+q+[f])
        position=valid and max(abs(x-y) for x,y in zip(p,expected))<1e-7 and abs(f-v['fov'])<1e-7
        rotation=valid and abs(abs(sum(x*y for x,y in zip(q,_quaternion(v))))-1)<1e-7
        checks['NO_UNEXPECTED_ORBIT'] &= position;checks['NO_UNEXPECTED_ROTATION'] &= rotation
        if state!='END':checks[state+'_PRESENT'] &= position and rotation
    def text(a,b,value):return any(any(l.get('text')==value and l.get('opacity',0)>.1 for l in row.get('labels',[])) for row in rows[a:b])
    checks['EVENT1_LOCATION_PRESENT'] &= text(60,90,'SUEZ CANAL')
    checks['EVENT1_HOLD_PRESENT'] &= text(240,330,'CANAL CLOSED')
    checks['EVENT1_RESOLVED_PRESENT'] &= text(330,360,'CANAL OPEN');checks['RESOLVED_BEFORE_ZOOM_OUT']=checks['EVENT1_RESOLVED_PRESENT']
    checks['EVENT2_LOCATION_PRESENT'] &= text(450,495,'SINGAPORE')
    checks['EVENT2_HOLD_PRESENT'] &= text(615,720,'SINGAPORE')
    checks['LOCATION_AFTER_WIDE_LOCK']=not text(0,450,'SINGAPORE')
    from .adaptive_wide import project_location
    area=c['adaptive_wide']['safe_area'];checks['BOTH_LOCATIONS_SAFE']=all(project_location(c['adaptive_camera'],coord,safe_area=area)['in_safe_area'] for coord in (s['coordinates'],c['next_coordinates']))
    failures=[n for n,v in checks.items() if not v];return dict(passed=not failures,failures=failures,checks=checks,frames=len(rows),scope='actual camera-state/label QA; production technical failures remain blocking')
def apply_policy(plan,technical,camera):
    if plan.get('metadata',{}).get('camera_test_preset')!=PRESET:return technical
    report=dict(technical);failures=technical.get('failures',[]);report['production_policy_not_applicable']=[n for n in failures if n in PRODUCTION_ONLY]
    report['failures']=sorted(set([n for n in failures if n not in PRODUCTION_ONLY]+camera['failures']));report.update(camera_qa=camera,passed=not report['failures'],publication_quality=False,qa_preset=PRESET);return report
def run_qc(video,plan,audits,outdir,**kwargs):
    if plan.get('metadata',{}).get('camera_test_preset')!=PRESET:return qc.run_qc(video,plan,audits,outdir,**kwargs)
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True);technical=qc.run_qc(video,plan,audits,outdir/'technical',**kwargs);report=apply_policy(plan,technical,camera_qc(plan,audits))
    from .storage import atomic_json
    atomic_json(outdir/'qc_report.json',report);(outdir/'qc_report.md').write_text('# Second-event camera QA\n\n'+('PASS' if report['passed'] else 'FAIL')+'\n\n'+json.dumps(report['camera_qa'],indent=2));return report
