"""Pure, reviewable structural edits. These proposals never approve or start rendering.

Deletion repairs the actual neighboring state and surviving ancestor references.
Deferring a conclusion moves its events, narration and expanded network display;
it does not leave the result on screen behind an empty text overlay. No replacement
facts or coordinates are invented. Invalid proposals remain blocked by normal gates.
"""
from __future__ import annotations
from copy import deepcopy
import re
from .storage import EngineError
from .gis import LOCATIONS
from .retention import MEANINGFUL

_DELETE = re.compile(r'(?:장면|scene|씬)\s*0*\d*\s*(?:은|는|을|를|만|이|도)?\s*(?:삭제|제거|delete|remove)|(?:삭제|delete|remove)\s*(?:장면|scene|씬)\s*\d*|\bS\d+\b\s*(?:삭제|제거|delete|remove)|(?:여기|이것)\s*(?:삭제|제거)|\d+(?:\.\d+)?\s*초\s*(?:구간|장면)?\s*(?:삭제|제거)',re.I)
_DELAY = re.compile(r'(?:결론|결과|최종|conclusion|result|payoff).*(?:공개하지|보여주지|말하지|숨겨|늦|나중|뒤로|delay|later|not reveal)|(?:delay|defer|hide|do not reveal|don.t reveal).*(?:conclusion|result|payoff)',re.I)
_RESULT_KINDS={'final_reveal','peak_reveal','consequence_reveal','comparison_reveal','network_expand'}

def _revision(plan,kind,**fields):
    previous=deepcopy(plan.get('revision',{}))
    # A previously approved deletion stays the provenance for a <20 second duration.
    if previous.get('type')=='scene_delete' and kind!='scene_delete':
        previous['last_edit']=kind;previous.update(fields)
    else:
        previous.update(type=kind,**fields)
    plan['revision']=previous
    return previous

def _repair_causality(original,edited):
    """Resolve only missing/future references through the original ancestor chain."""
    old={e['id']:e for s in original['scenes'] for e in s['visual_events']}
    new=sorted([(s['start_time']+e['time'],s,e) for s in edited['scenes'] for e in s['visual_events']],key=lambda item:(item[0],item[2]['id']))
    seen=set();changed=set()
    for _,scene,event in new:
        dependency=event.get('caused_by');candidate=dependency;visited=set()
        while candidate and candidate not in seen:
            if candidate in visited:candidate=None;break
            visited.add(candidate);ancestor=old.get(candidate)
            candidate=ancestor.get('caused_by') if ancestor else None
        if dependency!=candidate:event['caused_by']=candidate;changed.add(scene['scene_id'])
        if event.get('kind') in MEANINGFUL and event.get('meaningful',True):seen.add(event['id'])
    return changed

def _repair_beats(original,edited):
    remaining={s['scene_id'] for s in edited['scenes']};old={b.get('scene_id'):b for b in original['story'].get('beats',[])}
    beats=[]
    for beat in deepcopy(original['story'].get('beats',[])):
        if beat.get('scene_id') not in remaining:continue
        cause=beat.get('cause');visited=set()
        while cause and cause not in remaining:
            if cause in visited:cause=None;break
            visited.add(cause);cause=old.get(cause,{}).get('cause')
        beat['cause']=cause;beats.append(beat)
    edited['story']['beats']=beats

def _connect(scene,previous):
    if previous is None:return
    scene['entry_state']=deepcopy(previous['exit_state'])
    scene['camera_start']=deepcopy(previous['exit_state']['camera'])
    old_routes={r['route_id']:r for r in previous['routes']}
    for route in scene['routes']:
        before=old_routes.get(route['route_id'])
        progress=before['progress_end'] if before else 0.
        if route['progress_start']!=progress:
            route['progress_start']=progress
            route['start_time']=0.
            if route['progress_end']<progress:route['progress_end']=progress
            for entity in scene['entities']:
                if entity.get('route_id')==route['route_id']:entity['start_time']=0.
    # Exit camera remains unchanged, so only this neighbor needs a new camera path.
    for entity in scene['exit_state'].get('entities',[]):
        match=next((r for r in scene['routes'] if r['route_id']==entity.get('route_id')),None)
        if match:entity['progress']=match['progress_end']

def _delete_scenes(original,selected):
    plan=deepcopy(original);ids=set(selected)
    if not ids:raise EngineError('EDIT_TARGET_NOT_FOUND','삭제할 장면이 없습니다.')
    actual={s['scene_id'] for s in plan['scenes']}
    if not ids<=actual:raise EngineError('EDIT_TARGET_NOT_FOUND','삭제할 장면 ID를 찾을 수 없습니다.')
    old_scenes=plan['scenes'];remaining=[s for s in old_scenes if s['scene_id'] not in ids]
    plan['scenes']=remaining
    cursor=0.;metadata=set();affected=set(ids);previous=None;old_indexes={s['scene_id']:i for i,s in enumerate(old_scenes)}
    for scene in remaining:
        original_start=scene['start_time']
        if abs(original_start-cursor)>1e-8:
            scene.setdefault('render_time_offset',original_start)
            scene['start_time']=round(cursor,6);metadata.add(scene['scene_id'])
        index=old_indexes[scene['scene_id']]
        deleted_before=index>0 and old_scenes[index-1]['scene_id'] in ids
        if deleted_before and previous is not None:
            _connect(scene,previous);affected.add(scene['scene_id'])
        # Removing the opening does not silently attach the old hook to another scene.
        if previous is None and old_scenes and old_scenes[0]['scene_id'] in ids:
            scene['entry_state']=deepcopy(scene['entry_state']);scene['camera_start']=deepcopy(scene['entry_state']['camera'])
            plan['story']['hook']=scene.get('hook','')
            affected.add(scene['scene_id'])
        cursor+=scene['duration'];previous=scene
    plan['duration']=round(cursor,6);plan['request']['duration']=plan['duration']
    _repair_beats(original,plan);metadata.update(_repair_causality(original,plan))
    prior_deleted=original.get('revision',{}).get('deleted_scene_ids',[])
    revision=_revision(plan,'scene_delete',original_duration=original.get('revision',{}).get('original_duration',original['duration']),deleted_scene_ids=sorted(set(prior_deleted)|ids),blocking_issues=[])
    if not remaining:revision['blocking_issues'].append(dict(code='NO_SCENES',message='모든 장면을 삭제했습니다. 새 기획이 필요합니다.'))
    elif plan['duration']<5:revision['blocking_issues'].append(dict(code='EDITED_DURATION_TOO_SHORT',message='삭제 후 영상이 5초보다 짧습니다.'))
    return dict(plan=plan,affected_scenes=sorted(affected),metadata_changed_scenes=sorted(metadata-affected),blocking_issues=revision['blocking_issues'],warnings=['삭제로 훅·중간 변수·Peak·마지막 보상이 사라지면 검수에서 차단됩니다. 삭제한 장면을 자동으로 복원하지 않습니다.'])

def _safe_geography_replacement(plan,scene,event):
    """A sourced, new geographic fact replaces a moved reveal at the same time."""
    source_location=LOCATIONS.get(scene['coordinates'].get('location_id'))
    country_name=source_location.get('country') if source_location else None
    candidates=[l for l in LOCATIONS.values() if l['kind']=='country' and (l['name']==country_name or l.get('country')==country_name)]
    before_text={e.get('text','').casefold() for s in plan['scenes'] for e in s['visual_events'] if s['start_time']+e['time']<scene['start_time']+event['time']}
    already_added={c['text'].split('의 위치')[0].casefold() for c in plan['story']['claims'] if c.get('id','').startswith('F_EDIT_')}
    location=next((l for l in candidates if l['name'].casefold() not in before_text and l['name'].casefold() not in already_added),None)
    if not location:return None
    coord=deepcopy(location['coordinates']);claim_id=f"F_EDIT_{scene['scene_id']}_{event['id']}"
    if not any(c['id']==claim_id for c in plan['story']['claims']):
        plan['story']['claims'].append(dict(id=claim_id,text=f"{location['name']}의 위치는 Natural Earth 원본 라벨 좌표로 확인됩니다.",status='FACT',source_ids=[coord['source_id']],scope='verified geographic orientation; no scenario outcome'))
    if claim_id not in scene['claim_ids']:scene['claim_ids'].append(claim_id)
    return dict(id=event['id']+'_context',kind='country_reveal',time=event['time'],duration=event['duration'],target_id=location['id'],role='orientation',caused_by=event.get('caused_by'),meaningful=True,text=location['name'].upper(),description=f"결론 대신 {location['name']}의 실제 위치 확인",coordinates=coord,claim_id=claim_id)

def _delay_conclusion(original,selected):
    plan=deepcopy(original);ids=set(selected);scenes=plan['scenes'];indexes=[i for i,s in enumerate(scenes) if s['scene_id'] in ids]
    if not indexes:raise EngineError('EDIT_TARGET_NOT_FOUND','수정할 장면을 찾을 수 없습니다.')
    later=[s for i,s in enumerate(scenes) if i>max(indexes) and s['scene_id'] not in ids]
    revision=_revision(plan,'conclusion_delay',selected_scene_ids=sorted(ids),blocking_issues=[])
    if not later:
        issue=dict(code='CONCLUSION_DELAY_REQUIRES_LATER_SCENE',message='선택한 장면 뒤에 결론을 옮길 장면이 없습니다. 이후 장면을 추가하거나 수정 범위를 바꿔 주세요.')
        revision['blocking_issues'].append(issue)
        return dict(plan=plan,affected_scenes=sorted(ids),metadata_changed_scenes=[],blocking_issues=[issue],warnings=[])
    destination=later[-1];affected=set();metadata=set();moved=[];narrations=[];warnings=[]
    for scene in scenes:
        if scene['scene_id'] not in ids:continue
        result_events=[e for e in scene['visual_events'] if e.get('kind') in _RESULT_KINDS or e.get('role') in {'peak','payoff'}]
        narrative_result=scene.get('role') in {'peak','payoff'} or bool(re.search(r'결론|결과|전체.{0,6}(드러|공개)|최종|result|revealed|whole',scene.get('narration',''),re.I))
        if not result_events and not narrative_result:continue
        affected.add(scene['scene_id'])
        result_ids={e['id'] for e in result_events};replacements=[]
        for event in result_events:
            # A geography replacement is optional; a pacing hole is truthfully blocked.
            replacement=_safe_geography_replacement(plan,scene,event)
            if replacement:replacements.append(replacement)
            sounds=[deepcopy(a) for a in scene['sound_events'] if a.get('visual_event_id')==event['id']]
            moved.append((deepcopy(event),sounds))
        scene['visual_events']=[e for e in scene['visual_events'] if e['id'] not in result_ids]+replacements
        scene['sound_events']=[a for a in scene['sound_events'] if a.get('visual_event_id') not in result_ids]
        for e in replacements:
            scene['sound_events'].append(dict(id='A_'+e['id'],kind='soft_impact',time=e['time'],duration=min(.7,scene['duration']-e['time']),visual_event_id=e['id'],gain_db=-15))
        if narrative_result and scene.get('narration'):narrations.append(scene['narration']);scene['narration']=''
        # A final network expansion must not remain visible under a hidden label.
        scene['routes']=[r for r in scene['routes'] if not (r.get('faint') or r['route_id'].startswith('N_'))]
        visible={r['route_id'] for r in scene['routes']};scene['entities']=[e for e in scene['entities'] if not e.get('route_id') or e['route_id'] in visible]
        scene['entity_actions']=[a for a in scene['entity_actions'] if a.get('entity_id') in {e['id'] for e in scene['entities']}]
        for route in scene['routes']:
            if route['progress_start']<1 and route['progress_end']>=1:route['progress_end']=max(route['progress_start'],.95)
        scene['exit_state']['active_routes']=[r['route_id'] for r in scene['routes']]
        for entity in scene['exit_state'].get('entities',[]):
            route=next((r for r in scene['routes'] if r['route_id']==entity.get('route_id')),None)
            if route:entity['progress']=route['progress_end']
        # Track the continuing main route; preserve exact neighboring camera endpoints.
        if scene.get('role')!='hook':
            scene['camera_preset']='ROUTE_CHASE';scene['lighting_preset']='GEOGRAPHY_READABILITY';scene['directing_presets']=['ROUTE_CHASE'];scene['role']='progression';scene['music_energy']=min(scene['music_energy'],.55)
        index=scenes.index(scene)
        if index+1<len(scenes):
            successor=scenes[index+1];_connect(successor,scene);affected.add(successor['scene_id'])
    if not affected:raise EngineError('NO_CONCLUSION_TO_DELAY','선택한 장면에는 결론 공개가 없습니다. 결론/Peak가 있는 시간 구간을 지정하세요.')
    # Reuse existing final-event times where possible; avoid inventing extra rapid hits.
    destination_events=destination['visual_events'];available=[e for e in destination_events if e['kind'] in {'final_reveal','peak_reveal'} or e.get('role') in {'peak','payoff'}]
    used=set()
    for index,(event,sounds) in enumerate(moved):
        slot=next((e for e in available if e['id'] not in used and ((event['kind']=='final_reveal' and e['kind']=='final_reveal') or (event['kind']!='final_reveal' and e['kind']!='final_reveal' and e.get('role')!='payoff'))),None)
        if slot:
            time=slot['time'];used.add(slot['id']);destination_events.remove(slot)
            destination['sound_events']=[s for s in destination['sound_events'] if s.get('visual_event_id')!=slot['id']]
        else:time=max(.3,destination['duration']-1.65-.65*(len(moved)-index-1))
        event['time']=round(time,6);event['duration']=min(event['duration'],destination['duration']-time)
        if event['kind']=='final_reveal':event['role']='payoff'
        destination_events.append(event)
        for sound in sounds:sound['time']=event['time'];sound['duration']=min(sound['duration'],destination['duration']-time);destination['sound_events'].append(sound)
    destination_events.sort(key=lambda e:(e['time'],e['id']));destination['sound_events'].sort(key=lambda e:(e['time'],e['id']))
    if narrations:
        # The diff explicitly shows this necessary final-scene narration replacement.
        destination['narration']=' '.join(dict.fromkeys(narrations))
    destination['narration_event_ids']=[e['id'] for e in destination_events]
    for scene in scenes:
        if scene['scene_id'] in affected:scene['narration_event_ids']=[e['id'] for e in scene['visual_events']]
    affected.add(destination['scene_id']);metadata.update(_repair_causality(original,plan))
    if not any(e['kind']=='final_reveal' or e.get('role')=='payoff' for e in destination_events):
        revision['blocking_issues'].append(dict(code='MISSING_FINAL_PAYOFF_AFTER_DELAY',message='결론 이동 후 최종 보상이 없습니다. 마지막 장면 기획을 보완해야 합니다.'))
    revision['destination_scene_id']=destination['scene_id'];revision['moved_event_ids']=[e['id'] for e,_ in moved]
    # These results now refer to the destination Scene's clock and connected route
    # state. A distance from the earlier hero shot cannot remain on the new shot.
    from .planner import refresh_clock_dependent_route_information
    metric_repairs=[]
    for event in destination_events:
        if event['id'] not in revision['moved_event_ids']:continue
        metric=refresh_clock_dependent_route_information(destination,event)
        if metric:metric_repairs.append(metric)
    if metric_repairs:revision['refreshed_route_metrics']=metric_repairs
    # A moved result must have a real readable slot in the unchanged information
    # layer. Keep final-QC onset limits; paired SFX follows any measured adjustment.
    from .planner import _certify_planned_events
    _certify_planned_events(plan)
    warnings.append('결론과 연결망 공개를 후반 장면으로 옮겼습니다. 변경된 다음 장면과 마지막 장면도 Diff에서 확인하세요.')
    return dict(plan=plan,affected_scenes=sorted(affected),metadata_changed_scenes=sorted(metadata-affected),blocking_issues=revision['blocking_issues'],warnings=warnings)

def apply_advanced_edit(plan,selected_scene_ids,text):
    """Return a pure structural proposal, or None for unrelated supported simple edits.

    Root previews all changes, revalidates and requires approval. ``blocking_issues``
    must be retained in plan.revision and treated as gate failures, including at the
    later approval endpoint. ``metadata_changed_scenes`` identifies retiming-only or
    causal-reference repairs separately from scenes with different visible content.
    """
    if _DELETE.search(text):return _delete_scenes(plan,selected_scene_ids)
    if _DELAY.search(text):return _delay_conclusion(plan,selected_scene_ids)
    return None
