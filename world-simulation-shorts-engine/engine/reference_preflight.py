"""Collect-all perceptual geometry gate. Never claims shader/pixel/GPU success."""
from copy import deepcopy
from pathlib import Path
import json,subprocess,tempfile,math
from .reference_master import ROOT,VERSION


def collect(plan):
    with tempfile.TemporaryDirectory(prefix='reference-native-') as folder:
        file=Path(folder)/'plan.json';out=Path(folder)/'native.json'
        file.write_text(json.dumps(plan,ensure_ascii=False))
        result=subprocess.run(['node',str(ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(file),'--output',str(out)],cwd=ROOT,capture_output=True,text=True,timeout=240)
        if not out.is_file():raise RuntimeError('REFERENCE_NATIVE_REPORT_MISSING: '+result.stderr[-300:])
        return json.loads(out.read_text())


def native_perceptual_qc(plan,native):
    findings=[];metrics=[]
    def add(code,sid,frame=None,**values):findings.append(dict(code=code,severity='CRITICAL',scene_id=sid,frame_index=frame,**values))
    for scene in plan['scenes']:
        p=scene['direction'];sid=scene['scene_id'];records=[r for r in native['pose_records'] if r['scene_id']==sid]
        locked=[r for r in records if r['t']>=p['move_end']]
        if len(records)!=round(scene['duration']*30):add('FRAME_PLAN_INCOMPLETE',sid)
        if locked:
            a=locked[0]
            for r in locked[1:]:
                if any(abs(x-y)>1e-6 for x,y in zip(a['cameraPosition'],r['cameraPosition'])) or abs(abs(sum(x*y for x,y in zip(a['cameraQuaternion'],r['cameraQuaternion'])))-1)>1e-6 or abs(a['cameraFov']-r['cameraFov'])>1e-6:add('CAMERA_MOVING_DURING_REVEAL',sid,r['frame_index']);break
        entity_sizes=[];label_max=0
        for r in records:
            labels=[l for l in r.get('labels',[]) if l.get('opacity',0)>.1];label_max=max(label_max,len(labels))
            if len(labels)>2:add('INFORMATION_OVERLOAD',sid,r['frame_index'])
            for i,a in enumerate(labels):
                if a['x']<0 or a['y']<0 or a['x']+a['width']>2160 or a['y']+a['height']>3840:add('TEXT_OUTSIDE_SAFE_AREA',sid,r['frame_index'])
                for b in labels[i+1:]:
                    if a['x']<b['x']+b['width'] and a['x']+a['width']>b['x'] and a['y']<b['y']+b['height'] and a['y']+a['height']>b['y']:add('LABEL_COLLISION',sid,r['frame_index'])
            for e in r['entities']:
                if e.get('visibility_role')!='primary' or not e.get('visible') or not e.get('screenVisible') or e.get('occluded'):continue
                if e.get('screenRadius') is None:continue
                pixels=2*e['screenRadius']*1080/2160;entity_sizes.append(pixels)
                if pixels<18-1e-4:add('ENTITY_NOT_TRACKABLE',sid,r['frame_index'],pixels=pixels)
        for t in scene.get('text_events',[]):
            frames=[r for r in records if any(l.get('event_id')==t['event_id'] and l.get('opacity',0)>.1 for l in r.get('labels',[]))]
            from .reference_master import text_read_time
            if len(frames)/30+1e-6<text_read_time(t['text']):add('TEXT_NOT_READABLE_LONG_ENOUGH',sid,event_id=t['event_id'],visible_seconds=len(frames)/30)
        occupancy=[r['geometric_earth_occupancy'] for r in locked if 'geometric_earth_occupancy' in r]
        if p['intent']=='RESULT_HERO' and occupancy and min(occupancy)<p['result_min_occupancy']:add('RESULT_HERO_TOO_SMALL',sid,geometric_occupancy=min(occupancy))
        metrics.append(dict(geometric_earth_occupancy=min(occupancy) if occupancy else None,scene_id=sid,move_seconds=p['move_end'],settle_seconds=scene['duration']-p['move_end'],reveal_to_next_major_move=p['perception_hold'],max_visible_labels=label_max,
            entity_min_pixels_1080=min(entity_sizes) if entity_sizes else None,camera_lock='VERIFIED_GEOMETRY_ONLY',
            route_contrast='NOT_RUN',luminance='NOT_RUN',Earth_pixel_occupancy='NOT_RUN',GPU_draw='NOT_RUN'))
    findings.extend(native['failures'])
    return dict(passed=not findings,findings=findings,warnings=[],metrics=metrics,pixels='NOT_RUN')


def fit_native_composition(plan):
    """Bounded pullback for detected clipping, not a hidden audit exemption.

    Replays every original camera/entity/primitive predicate after correction.
    Only the new candidate is adjusted; saved files are never loaded/upgraded.
    """
    corrections=[]
    for attempt in range(5):
        native=collect(plan)
        clipped={f['scene_id'] for f in native['failures'] if f['code']=='POSE_CLIPPING'}
        if not clipped or attempt==4:break
        for i,s in enumerate(plan['scenes']):
            if s['scene_id'] not in clipped or s['render_mode']=='FLAT_MAP_PREMIUM':continue
            old=s['camera_end']['height'];s['camera_end']['height']=round(old*1.035,6)
            s['exit_state']['camera']=deepcopy(s['camera_end'])
            if i+1<len(plan['scenes']) and plan['scenes'][i+1]['render_mode']==s['render_mode']:
                nxt=plan['scenes'][i+1];nxt['camera_start']=deepcopy(s['camera_end']);nxt['entry_state']=deepcopy(s['exit_state'])
            corrections.append(dict(scene_id=s['scene_id'],code='CLIPPING_CAMERA_FIT',from_height=old,to_height=s['camera_end']['height'],tested_frames=round(s['duration']*30)))
    report=native_perceptual_qc(plan,native)
    plan['metadata']['reference_native_qc']=report
    plan['metadata']['reference_auto_corrections']=corrections
    return report
