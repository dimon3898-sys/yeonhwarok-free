"""Constrained natural-language edits, previewed as a diff before explicit approval."""
from __future__ import annotations
import copy,json,re,uuid,subprocess
from pathlib import Path
from .storage import EngineError,atomic_json,read_json,plan_hash,now

def _requested_window(text,scene):
    match=re.search(r'(\d+(?:\.\d+)?)\s*[~～–-]\s*(\d+(?:\.\d+)?)\s*(?:초|s|sec)',text,re.I)
    if not match:return (0.,scene['duration'])
    lo,hi=map(float,match.groups())
    return max(0.,lo-scene['start_time']),min(scene['duration'],hi-scene['start_time'])

def _network_visibility(scene,event_id):
    """Certify a proposed connection with the actual, canvas-free Three camera.

    Reuses the frozen adapter geometry; creates no renderer, context or image.
    An unavailable geometry verifier fails closed rather than approving a hidden
    connection. Camera-only approximation is insufficient for event auditing.
    """
    script=r'''
import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';
const app=process.cwd(),legacy=path.resolve(app,'../cinematic-world-map'),THREE=await import(pathToFileURL(path.join(legacy,'node_modules/three/build/three.module.js'))),{createAircraftV3}=await import(pathToFileURL(path.join(legacy,'src/aircraft_v3.js')));
const geo=(lon,lat,r=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(r),clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
const source=fs.readFileSync(path.join(app,'web/earth_adapter.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,''),{SceneRoutes,GenericCamera,SceneEarthRenderer}=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',source+';return {SceneRoutes,GenericCamera,SceneEarthRenderer};')(THREE,class {},{},createAircraftV3,geo,clamp,smooth);
const input=JSON.parse(fs.readFileSync(0,'utf8')),scene=input.scene,event=scene.visual_events.find(e=>e.id===input.event_id),camera=new THREE.PerspectiveCamera(44,9/16,.02,30),routes=new SceneRoutes(scene),cam=new GenericCamera(camera,scene,routes),context={camera,w:1080,h:1920};let qualified=0,checked=0,first=null;
const safe=point=>{const p=SceneEarthRenderer.prototype.project.call(context,point);return p.visible&&p.x>=1080*.06&&p.x<=1080*.91&&p.y>=1920*.08&&p.y<=1920*.85;};
for(let t=event.time+1/30;t<Math.min(scene.duration,event.time+1.25);t+=1/30){cam.update(t);checked++;const visible=routes.routes.filter(r=>{const p=routes.progress(t,r);if(p<=0||!(t>=r.start||r.progress_start>0))return false;for(let i=0;i<=24;i++)if(safe(r.curve.getPoint(p*i/24)))return true;return false;});if(visible.length>=2&&visible.some(r=>r.id===event.target_id&&t>=r.start&&t<r.end)){qualified++;first??=t;}}
console.log(JSON.stringify({passed:qualified>=Math.min(12,checked),qualified_frames:qualified,checked_frames:checked,first_visible_time:first,event_id:event.id,route_id:event.target_id,method:'Frozen Three.js projection and actual network-event geometry, no GL'}));
'''
    try:
        result=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps({'scene':scene,'event_id':event_id}),text=True,cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=12,check=True)
        return json.loads(result.stdout)
    except (OSError,subprocess.SubprocessError,ValueError) as error:
        raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT','현재 카메라에서 추가 항로의 실제 가시성을 확인할 수 없습니다.',{'required_plugins':['VISIBLE_NETWORK_COMPOSITION'],'reason':str(error)}) from error

def _add_visible_routes(plan,scene,text):
    candidates={route['route_id']:copy.deepcopy(route) for other in plan['scenes'] for route in other['routes'] if route['route_id'] not in {r['route_id'] for r in scene['routes']}}
    count=2 if re.search(r'두|2|two',text,re.I) else 1
    if len(candidates)<count:raise EngineError('SUPPORTED_ROUTE_REQUIRED','추가할 검증된 항로가 부족합니다. 출발지와 목적지를 지정한 새 기획을 사용해 주세요.')
    used=set();evidence=[];previous_time=-1.;sequence=1
    existing_routes={r['route_id'] for r in scene['routes']};existing_events={e['id'] for e in scene['visual_events']}
    while any(f"{scene['scene_id']}_added_route_{sequence+i}" in existing_routes or f"{scene['scene_id']}_route_add_{sequence+i-1}" in existing_events for i in range(count)):sequence+=1
    for index in range(count):
        accepted=False
        for fraction in (.45,.57,.68,.79):
            timestamp=round(scene['duration']*fraction,6)
            if timestamp<previous_time+.7 or timestamp>scene['duration']-.4:continue
            for original_id,candidate in candidates.items():
                if original_id in used:continue
                route=copy.deepcopy(candidate);route.update(route_id=f"{scene['scene_id']}_added_route_{sequence+index}",start_time=timestamp,end_time=scene['duration']-.1,progress_start=0,progress_end=1,faint=True)
                if route['route_id'] in {r['route_id'] for r in scene['routes']}:continue
                predecessors=[e for e in scene['visual_events'] if e['time']<=timestamp]
                cause=max(predecessors,key=lambda e:e['time'])['id'] if predecessors else scene['visual_events'][0]['caused_by']
                coordinates=copy.deepcopy(route['points'][-1]);description=route.get('description','검증된 위치의 새 연결').replace('Sampled geographic connection: ','')
                event={'id':f"{scene['scene_id']}_route_add_{sequence+index-1}",'kind':'network_expand','time':timestamp,'duration':.7,'target_id':route['route_id'],'role':'variable','caused_by':cause,'meaningful':True,'text':description,'description':'검증된 좌표의 추가 연결 공개','coordinates':coordinates,'claim_id':'M01'}
                scene['routes'].append(route);scene['visual_events'].append(event)
                check=_network_visibility(scene,event['id'])
                if check['passed']:
                    scene['sound_events'].append({'id':'A_'+event['id'],'kind':'wide_riser','time':timestamp,'duration':min(1.2,scene['duration']-timestamp),'visual_event_id':event['id'],'gain_db':-18})
                    scene['narration_event_ids'].append(event['id']);used.add(original_id);previous_time=timestamp;evidence.append(check);accepted=True;break
                scene['routes'].pop();scene['visual_events'].pop()
            if accepted:break
        if not accepted:raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT','요청한 추가 항로를 현재 장면에서 실제로 보여줄 수 없습니다. 카메라 범위를 바꾸거나 다른 장면을 선택해 주세요.',{'required_plugins':['VISIBLE_NETWORK_COMPOSITION'],'scene_id':scene['scene_id']})
    scene['visual_events'].sort(key=lambda event:event['time'])
    return evidence

def _selected(plan,text):
    m=re.search(r'(\d+(?:\.\d+)?)\s*[~～–-]\s*(\d+(?:\.\d+)?)\s*(?:초|s|sec)',text,re.I)
    if m:
        lo,hi=map(float,m.groups())
        if hi<=lo:raise EngineError('INVALID_RANGE','끝 시각이 시작 시각보다 커야 합니다.')
        return [s for s in plan['scenes'] if s['start_time']<hi and s['start_time']+s['duration']>lo]
    matches=list(re.finditer(r'(?:scene|장면|씬)\s*0*(\d+)|\bS0*(\d+)\b',text,re.I))
    if matches:
        numbers={int(match.group(1) or match.group(2)) for match in matches}
        available={int(scene['scene_id'][1:]) for scene in plan['scenes']}
        if not numbers<=available:raise EngineError('EDIT_TARGET_NOT_FOUND','명시한 장면 번호가 기획에 없습니다.')
        return [s for s in plan['scenes'] if int(s['scene_id'][1:]) in numbers]
    if re.search(r'첫|처음|초반|opening|first',text,re.I):return [plan['scenes'][0]]
    if re.search(r'마지막|결말|final|ending',text,re.I):return [plan['scenes'][-1]]
    m=re.search(r'(\d+(?:\.\d+)?)\s*초',text)
    if m:
        t=float(m.group(1));return [s for s in plan['scenes'] if s['start_time']<=t<s['start_time']+s['duration']]
    from .gis import LOCATIONS
    for loc in LOCATIONS.values() if isinstance(LOCATIONS,dict) else LOCATIONS:
        names=[loc.get('name',''),loc.get('id','')]+loc.get('aliases',[])
        if any(x and x.lower() in text.lower() for x in names):
            return [s for s in plan['scenes'] if loc.get('id') in s['geographic_targets']]
    raise EngineError('EDIT_TARGET_REQUIRED','수정할 시간 구간, 장면 번호 또는 장소를 입력해 주세요.')

def _place_label_edit_requested(text):
    """Require an explicit place-label target and readability/size request.

    A country being hard to see, subtitle sizing, or entity sizing is not a
    place-label edit. Dedicated label requests never alter scene lighting or
    camera simply because their explanation contains '안 보여' or '크기'.
    """
    if re.search(r'자막|subtitle|caption',text,re.I):return False
    return bool(re.search(r'지명|도시명|도시\s*이름|(?:world|place|city)\s*(?:name\s*)?labels?',text,re.I) and re.search(r'안\s*보|안\s*읽|대비|가독|읽기|선명|크기|크게|contrast|readab|legib|larger|size',text,re.I))

def _status_label_edit_requested(text):
    """Status contrast requests opt in without enlarging long status text."""
    if re.search(r'자막|subtitle|caption',text,re.I):return False
    return bool(re.search(r'상태\s*(?:라벨|레이블)|status\s*labels?',text,re.I) and re.search(r'안\s*보|안\s*읽|대비|가독|읽기|선명|contrast|readab|legib',text,re.I))

def preview_revision(store,pid,version,text):
    if not isinstance(text,str) or not text.strip():raise EngineError('EMPTY_EDIT','수정 내용을 입력해 주세요.')
    old=store.get(pid,version)['plan'];new=copy.deepcopy(old);targets=_selected(new,text);changes=[];geometry_checks=[];ship_ids={};ship_phases={};proposal_warnings=[]
    if not targets:raise EngineError('EDIT_TARGET_NOT_FOUND','해당 시간 또는 장소의 장면이 없습니다.')
    from .advanced_revisions import apply_advanced_edit
    structural=apply_advanced_edit(old,[s['scene_id'] for s in targets],text)
    if structural is not None:
        new=structural['plan'];before={s['scene_id']:s for s in old['scenes']};after={s['scene_id']:s for s in new['scenes']}
        for key in ('duration','request','story','revision','required_plugins'):
            if new.get(key)!=old.get(key):
                changes.append({'scene_id':'전체 기획','field':key,'before':old.get(key),'after':new.get(key)})
        for sid in before.keys()|after.keys():
            if sid not in after:changes.append({'scene_id':sid,'field':'scene','before':before[sid],'after':None});continue
            if sid not in before:changes.append({'scene_id':sid,'field':'scene','before':None,'after':after[sid]});continue
            for key in after[sid]:
                if after[sid][key]!=before[sid].get(key):changes.append({'scene_id':sid,'field':key,'before':before[sid].get(key),'after':after[sid][key]})
        from .schema import validate_plan
        new['gate']=validate_plan(new)
        rid='revision_'+uuid.uuid4().hex[:12]
        record={'revision_id':rid,'base_version':version,'base_plan_hash':old['plan_hash'],'request':text,'created_at':now(),'diff':changes,'affected_scenes':structural['affected_scenes'],'metadata_changed_scenes':structural.get('metadata_changed_scenes',[]),'warnings':structural.get('warnings',[]),'plan':new,'approved':False}
        atomic_json(store.path(pid)/'revisions'/(rid+'.json'),record,True);return record
    for s in targets:
        before=copy.deepcopy(s);matched=False
        place_label_edit=_place_label_edit_requested(text);status_label_edit=_status_label_edit_requested(text)
        if place_label_edit or status_label_edit:
            from .planner import apply_readable_place_labels
            labels=s['labels'] if place_label_edit else [label for label in s['labels'] if label.get('role')=='status']
            if not apply_readable_place_labels(labels,s['lighting_preset'],explicit_edit=True,include_status=status_label_edit):
                raise EngineError('UNSUPPORTED_LABEL_EDIT','선택한 장면에는 현재 조명에서 조정할 검증된 요청 라벨이 없습니다.',{'scene_id':s['scene_id']})
            for key in s:
                if s[key]!=before.get(key):changes.append({'scene_id':s['scene_id'],'field':key,'before':before.get(key),'after':s[key]})
            continue
        if re.search(r'국가|지역|도시|geographic|country|city|region',text,re.I) and re.search(r'대신|replace',text,re.I) and re.search(r'남은\s*거리|remaining\s*(?:route\s*)?distance',text,re.I):
            from .visibility import certify_semantic_visibility
            from .planner import replace_geographic_event_with_milestone,repeated_city_reveal_events,PlanningInputError,SOUND_MAP
            certificate=certify_semantic_visibility(new)
            hidden={failure.get('event_id') for failure in certificate.get('failures',[]) if failure.get('code')=='GEOGRAPHIC_EVENT_NOT_VISIBLE' and failure.get('scene_id')==s['scene_id']}
            repeated={event['id'] for event in repeated_city_reveal_events(s)} if re.search(r'중복|반복|duplicate|repeat',text,re.I) else set()
            replacement_events=[event for event in s['visual_events'] if event['id'] in (hidden|repeated) and event['kind'] in {'city_reveal','country_reveal','region_reveal','destination_preview'}]
            if not replacement_events:raise EngineError('NO_CHANGES','선택한 장면에 요청한 화면 밖 또는 중복 지리 강조 사건이 없습니다.')
            for event in replacement_events:
                try:
                    geometry_checks.append(replace_geographic_event_with_milestone(s,event))
                    for sound in s['sound_events']:
                        if sound.get('visual_event_id')==event['id']:sound['kind']=SOUND_MAP[event['kind']]
                except PlanningInputError as error:raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT',str(error),error.details) from error
            matched=True
        if re.search(r'낮|주간|day',text,re.I):s['lighting_preset']='DAY_DOCUMENTARY';matched=True
        elif re.search(r'밤|야간|night',text,re.I):s['lighting_preset']='CINEMATIC_NIGHT';matched=True
        elif re.search(r'잘 안 보|안보|가독|보이게|밝게|readab',text,re.I):s['lighting_preset']='GEOGRAPHY_READABILITY';matched=True
        if re.search(r'빠르|빠르게|빠른|속도.*높|faster|speed up',text,re.I):s['camera_speed']=min(3.0,float(s.get('camera_speed',1))*1.2);matched=True
        if re.search(r'느리|천천히|slower',text,re.I):s['camera_speed']=max(.6,float(s.get('camera_speed',1))*.8);matched=True
        if re.search(r'영화|시네마|cinematic',text,re.I):s['lighting_preset']='HERO';s['render_quality']='CINEMA';matched=True
        if re.search(r'줌아웃|zoom.?out|pull.?back',text,re.I):s['camera_preset']='GLOBAL_PULLBACK';s['camera_speed']=1.25;matched=True
        if re.search(r'비행기.*(?:빼|제거|없애)|remove.*aircraft',text,re.I):
            removed={x['id'] for x in s['entities'] if x['type']=='aircraft'}
            s['entities']=[x for x in s['entities'] if x['type']!='aircraft'];s['entity_actions']=[x for x in s['entity_actions'] if x.get('entity_id') in {e['id'] for e in s['entities']}]
            deleted={e['id'] for e in s['visual_events'] if e['kind']=='entity_departure' and e.get('target_id') in removed}
            predecessors={e['id']:e.get('caused_by') for e in s['visual_events'] if e['id'] in deleted}
            s['visual_events']=[e for e in s['visual_events'] if e['id'] not in deleted]
            s['sound_events']=[e for e in s['sound_events'] if e.get('visual_event_id') not in deleted]
            s['narration_event_ids']=[eid for eid in s.get('narration_event_ids',[]) if eid not in deleted]
            for other in new['scenes']:
                for event in other['visual_events']:
                    while event.get('caused_by') in deleted:event['caused_by']=predecessors[event['caused_by']]
            matched=True
        if re.search(r'(?:폭발|효과|glow|effect).*(?:줄|낮|reduce)',text,re.I):
            s['effect_strength']=max(.1,float(s.get('effect_strength',1))*.6);matched=True
        if re.search(r'(?:약해|훅.*강|hook)',text,re.I):
            s['camera_preset']='FAST_HOOK_DIVE';s['camera_speed']=min(3.,max(1.8,float(s.get('camera_speed',1)))*1.15)
            for e in s['visual_events']:
                if e['time']<3:e['strength']=min(1.4,float(e.get('strength',1))*1.15)
            matched=True
        if re.search(r'(?:배|선박|ship).*(?:추가|add)|add.*ship',text,re.I):
            if not any(e['type']=='cargo_ship' for e in s['entities']):raise EngineError('UNSUPPORTED_EDIT','선박 추가는 해상 Scene에서 지원합니다.')
            count=2 if re.search(r'두|2|two',text,re.I) else 1;lo,hi=_requested_window(text,s)
            routes={r['route_id']:r for r in s['routes']};eligible=[]
            for entity in s['entities']:
                route=routes.get(entity.get('route_id'))
                if entity['type']!='cargo_ship' or entity['action']=='stop' or not route or route['progress_end']<=route['progress_start']:continue
                overlap=max(0.,min(hi,entity['end_time'],route['end_time'])-max(lo,entity['start_time'],route['start_time']))
                if overlap>0:eligible.append((overlap,entity))
            if not eligible:raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT','요청 시간에 실제로 이동하는 검증된 해상 경로가 없습니다. 선박이 출발하는 구간을 선택해 주세요.',{'required_plugins':['ACTIVE_SEA_ROUTE'],'scene_id':s['scene_id']})
            template=max(eligible,key=lambda item:item[0])[1];route=routes[template['route_id']]
            prior_phase=max((float(e.get('phase_offset',0)) for e in s['entities'] if e.get('route_id')==template['route_id']),default=0.)
            available=max(0.,1.-route['progress_end']-prior_phase);spacing=min(.005,available/(count+1))
            if spacing<.0001:raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT','도착 직전이라 추가 선박을 서로 구분할 공간이 없습니다. 이전 구간을 선택해 주세요.',{'required_plugins':['VISIBLE_SHIP_COMPOSITION'],'scene_id':s['scene_id']})
            if template['route_id'] not in ship_ids:
                existing={e['id'] for other in new['scenes'] for e in other['entities']};prefix='added_ship_'+template['route_id']+'_';sequence=1
                while any(prefix+str(sequence+i) in existing for i in range(count)):sequence+=1
                ship_ids[template['route_id']]=[prefix+str(sequence+i) for i in range(count)]
                ship_phases[template['route_id']]=[prior_phase+spacing*(i+1) for i in range(count)]
            phases=ship_phases[template['route_id']]
            if phases[-1]>=1.-route['progress_end']:raise EngineError('UNSUPPORTED_VISUAL_REQUIREMENT','선택한 장면을 연결하며 추가 선박 간격을 유지할 수 없습니다. 도착 이전 구간을 선택해 주세요.',{'required_plugins':['VISIBLE_SHIP_COMPOSITION'],'scene_id':s['scene_id']})
            if template['start_time']>lo+.01:proposal_warnings.append(f"{s['scene_id']}: 추가 선박은 검증된 항로가 출발하는 {s['start_time']+template['start_time']:g}초부터 표시됩니다.")
            for i in range(count):
                e=copy.deepcopy(template);e['id']=ship_ids[template['route_id']][i];e['phase_offset']=phases[i];s['entities'].append(e)
                s['entity_actions'].append({'entity_id':e['id'],'action':e['action']})
            matched=True
        if re.search(r'항로.*(?:추가|add)|add.*route',text,re.I):
            geometry_checks.extend(_add_visible_routes(new,s,text))
            matched=True
        if not matched:raise EngineError('UNSUPPORTED_EDIT','이 수정 표현은 아직 지원하지 않습니다. 시간 구간과 낮/밤, 가독성, 속도, 항공기 제거, 검증된 항로 또는 선박 추가를 지정해 주세요.')
        if s['lighting_preset']!=before['lighting_preset']:
            from .planner import apply_readable_place_labels
            apply_readable_place_labels(s['labels'],s['lighting_preset'],explicit_edit=True,include_status=True)
        for key in s:
            if s[key]!=before.get(key):changes.append({'scene_id':s['scene_id'],'field':key,'before':before.get(key),'after':s[key]})
    if not changes:raise EngineError('NO_CHANGES','현재 설정과 동일하여 변경할 내용이 없습니다.')
    from .schema import validate_plan
    new['gate']=validate_plan(new)
    rid='revision_'+uuid.uuid4().hex[:12];record={'revision_id':rid,'base_version':version,'base_plan_hash':old['plan_hash'],'request':text,'created_at':now(),'diff':changes,'affected_scenes':[s['scene_id'] for s in targets],'plan':new,'approved':False,'geometry_checks':geometry_checks,'warnings':proposal_warnings}
    atomic_json(store.path(pid)/'revisions'/(rid+'.json'),record,True);return record

def approve_revision(store,pid,rid):
    if not re.fullmatch(r'revision_[a-z0-9]{12}',rid):raise EngineError('INVALID_REVISION','잘못된 수정 ID입니다.')
    path=store.path(pid)/'revisions'/(rid+'.json')
    if not path.exists():raise EngineError('NOT_FOUND','수정 요청을 찾을 수 없습니다.',status=404)
    with store.lock:
        record=read_json(path)
        if record.get('result_version'):return store.get(pid,record['result_version'])
        current=store.get(pid)
        if current['version']!=record['base_version'] or current['plan']['plan_hash']!=record['base_plan_hash']:raise EngineError('STALE_REVISION','다른 버전이 생성되었습니다. 최신 버전을 기준으로 수정해 주세요.',status=409)
        from .schema import validate_plan
        gate=validate_plan(record['plan'])
        if not gate['passed']:raise EngineError('PLAN_GATE_FAILED','수정 계획의 검수가 실패했습니다.',gate)
        result=store.add_version(pid,record['plan']);store.approve(pid,result['version'],result['plan']['plan_hash'])
        record['approved']=True;record['approved_at']=now();record['result_version']=result['version'];atomic_json(path,record)
        atomic_json(store.version_path(pid,result['version'])/'revision.json',{'base_version':record['base_version'],'affected_scenes':record['affected_scenes'],'revision_id':rid},True)
        return result

def preview_clip_revision(store,pid,version,scene_id,asset_id,uploads):
    if not re.fullmatch(r'asset_[a-z0-9]{12}',asset_id or ''):raise EngineError('INVALID_ASSET','업로드한 영상 파일을 선택해 주세요.')
    sourcefile=uploads/asset_id/'source.json'
    if not sourcefile.exists():raise EngineError('NOT_FOUND','업로드한 파일을 찾을 수 없습니다.',status=404)
    source=read_json(sourcefile)
    if source['kind']!='clip' or not source['rights_declared']:raise EngineError('CLIP_LICENSE_REQUIRED','사용 권한이 확인된 MP4가 필요합니다.')
    old=store.get(pid,version)['plan'];new=copy.deepcopy(old);s=next((s for s in new['scenes'] if s['scene_id']==scene_id),None)
    if not s:raise EngineError('EDIT_TARGET_NOT_FOUND','해당 장면이 없습니다.')
    if float(source['probe']['format']['duration'])+.01<s['duration']:raise EngineError('CLIP_TOO_SHORT','장면보다 긴 외부 영상을 선택해 주세요.')
    before=copy.deepcopy(s);s['scene_type']='CINEMATIC_CLIP';s['source_type']='EXTERNAL_CLIP';s['cinematic_clip']={'path':source['path'],'trim_start':0,'license':'USER_SUPPLIED_RIGHTS','user_owned':True,'source_id':asset_id};s['transition_in']='MATCH_CUT';s['transition_out']='MATCH_CUT'
    claims={c['id']:c for c in new['story']['claims']}
    from .assets import validate_clip_requirements,CLIP_INFORMATIONAL_EVENTS
    annotations=[]
    for event in s['visual_events']:
        if event.get('meaningful',True) and event['kind'] in CLIP_INFORMATIONAL_EVENTS:
            claim=claims.get(event.get('claim_id'))
            if not claim:continue
            annotations.append({'event_id':event['id'],'time':event['time'],'duration':min(max(1.35,event.get('duration',.7)),s['duration']-event['time']),'text':event.get('text') or claim['text'],'source_ids':claim['source_ids'],'fact_status':claim['status'],'claim_ids':[claim['id']]})
    s['cinematic_clip']['annotations']=annotations
    check=validate_clip_requirements(s,{item['id'] for item in new['sources']},{cid:claim['status'] for cid,claim in claims.items()})
    if not check['passed']:raise EngineError('UNSUPPORTED_CLIP_SEMANTIC_EVENT','이 장면에는 외부 영상에서 자동 확인할 수 없는 물리 이벤트가 있습니다. 정보 공개 장면을 선택해 주세요.',check)
    if 'CINEMATIC_CLIP' not in new['required_plugins']:new['required_plugins'].append('CINEMATIC_CLIP')
    from .schema import validate_plan
    new['gate']=validate_plan(new)
    rid='revision_'+uuid.uuid4().hex[:12];changes=[{'scene_id':scene_id,'field':k,'before':before.get(k),'after':val} for k,val in s.items() if val!=before.get(k)]
    record={'revision_id':rid,'base_version':version,'base_plan_hash':old['plan_hash'],'request':'사용 권한이 확인된 외부 영상 삽입','created_at':now(),'diff':changes,'affected_scenes':[scene_id],'plan':new,'approved':False,'warnings':['외부 영상의 내용·카메라·색감이 기존 장면과 맞는지 승인 전에 확인해 주세요.']}
    atomic_json(store.path(pid)/'revisions'/(rid+'.json'),record,True);return record
