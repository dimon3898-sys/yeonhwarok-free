"""Reference-informed, component-local timing over approved production graphics.

Metadata beats are not new story events. Ramp integration matches the native JS
adapter exactly; global time, asset geometry, voice speed and endpoints stay put.
"""
from copy import deepcopy
import math
from .pace import PACE_PROFILES, frame_time

KINDS={'country_reveal':'REVEAL','city_reveal':'REVEAL','destination_preview':'NEXT_CUE',
       'route_start':'MOVE','entity_departure':'MOVE','milestone_reveal':'REVEAL',
       'arrival':'RESPONSE','new_variable':'BUILD','route_blocked':'IMPACT',
       'route_reroute':'RESPONSE','network_expand':'BUILD','peak_reveal':'PEAK',
       'final_reveal':'PEAK','response':'RESPONSE'}
ENERGY={'REVEAL':.56,'FOCUS':.46,'MOVE':.58,'RESPONSE':.62,'IMPACT':.76,
        'NEXT_CUE':.64,'BUILD':.72,'PEAK':.96,'RELEASE':.34,'MICRO_PAUSE':.22}
BANNED={'NEXT?','ONE NETWORK','THE WORLD CHANGES','THREE CITIES · ONE NETWORK'}
DEFAULT_KNOTS=[{'phase':0.,'speed':.65},{'phase':.22,'speed':1.30},
               {'phase':.56,'speed':1.50},{'phase':.82,'speed':.80},{'phase':1.,'speed':.50}]


def ramp_phase(phase, knots):
    """Integral of piecewise smoothstep speeds, normalized to exact endpoints."""
    phase=max(0.,min(1.,float(phase)));area=0.;partial=0.
    for a,b in zip(knots,knots[1:]):
        h=float(b['phase'])-float(a['phase']);v=float(a['speed']);delta=float(b['speed'])-v
        if h<=0:raise ValueError('RHYTHM_KNOT_ORDER')
        area+=h*(v+float(b['speed']))/2
        u=max(0.,min(1.,(phase-float(a['phase']))/h))
        partial+=h*(v*u+delta*(u**3-.5*u**4))
    if area<=1e-9:raise ValueError('RHYTHM_ZERO_SPEED_AREA')
    return max(0.,min(1.,partial/area))


def route_rhythm_progress(scene, route, time):
    phase=max(0.,min(1.,(float(time)-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
    spec=next((r for r in scene.get('rhythm_visual',{}).get('routes',[]) if r['route_id']==route['route_id']),None)
    if spec:phase=ramp_phase(phase,spec['knots'])
    easing=route.get('speed_easing','ease_in_out')
    if easing=='linear':eased=phase
    elif easing=='ease_in':eased=phase*phase
    elif easing=='ease_out':eased=1-(1-phase)*(1-phase)
    else:eased=phase*phase*(3-2*phase)
    return route['progress_start']+(route['progress_end']-route['progress_start'])*eased


def _pause_knots(start, end, total):
    a=start/total;b=end/total
    if not 0<a<b<1:raise ValueError('RHYTHM_PAUSE_OUTSIDE_CAMERA_TRAVEL')
    return [{'phase':0.,'speed':.70},{'phase':a*.52,'speed':1.35},
            {'phase':max(a*.53,a-.08),'speed':1.20},{'phase':a,'speed':0.},
            {'phase':b,'speed':0.},{'phase':min(1.,b+.09),'speed':1.35},
            {'phase':1.,'speed':.55}]


def _short_map_text(scene):
    """Keep a real sourced departure name where the old generated question was."""
    from .gis import resolve_location
    for event in scene.get('visual_events',[]):
        generated_place_hook=(event.get('kind')=='hook_reveal' and
            event.get('description')=='Source-backed map place; no generated decorative slogan')
        if event.get('text','').upper().strip() not in BANNED and not generated_place_hook:continue
        coord=event.get('coordinates') or scene['coordinates']
        name=resolve_location(coord['location_id'])['name'].upper()
        event.update(text=name,description='Source-backed map place; no generated decorative slogan')
        if event.get('kind')=='hook_reveal':
            # Reuse the already approved city label at its geographic anchor.
            # Adding a second question-role label would push the duplicate
            # into a different collision-avoidance row. Keep one place label.
            city=next((label for label in scene.get('labels',[]) if
                label.get('text','').upper()==name and
                label.get('coordinates',{}).get('location_id')==coord['location_id']),None)
            if city:
                city.update(kind='hook_reveal',event_id=event['id'])
                scene['text_events']=[text for text in scene.get('text_events',[]) if text.get('event_id')!=event['id']]
                continue
        for text in scene.get('text_events',[]):
            if text.get('event_id')==event['id']:
                # The preserved renderer uses its historical "question" role
                # for the opening hook receipt. It remains a map-attached,
                # sourced place name; this adds no slogan or story event.
                text.update(text=name,role='question' if event.get('kind')=='hook_reveal' else 'city',priority=6)
    for text in scene.get('text_events',[]):
        if text.get('text','').upper().strip() in BANNED:
            raise ValueError('RHYTHM_DECORATIVE_TEXT_FORBIDDEN')


def _micro_beats(scene, pauses):
    points={0.:('FOCUS',None)};duration=scene['duration']
    for event in scene['visual_events']:
        if event.get('meaningful',True):points[float(event['time'])]=(KINDS.get(event['kind'],'REVEAL'),event['id'])
    preview=scene.get('flat_map',{}).get('next_event')
    if preview:
        points[frame_time(max(0.,preview['event_time']-preview['lead_time']))]=('NEXT_CUE',preview['event_id'])
    for pause in pauses:
        points[round(pause['time']-scene['start_time'],6)]=('MICRO_PAUSE',pause['event_id'])
    peak=next((e for e in scene['visual_events'] if e['kind'] in {'peak_reveal','final_reveal'}),None)
    if peak and peak['time']+.4<duration:
        points[frame_time(peak['time']+.4)]=('RELEASE',peak['id'])
    times=sorted(t for t in points if 0<=t<duration);beats=[]
    for i,time in enumerate(times):
        kind,event_id=points[time];end=times[i+1] if i+1<len(times) else duration
        if end-time<=1e-6:continue
        beat=dict(id=f"{scene['scene_id']}_B{i+1:02}",time=time,duration=round(end-time,6),kind=kind,music_energy=ENERGY[kind])
        if event_id:beat['visual_event_id']=event_id
        beats.append(beat)
    return beats


def apply_rhythm_policy(plan, *, preserve_earth_pixels=False):
    """Copy a new plan/version; do not implicitly upgrade any saved project.

    Explicit cache preservation is used by this bounded polish sample: the
    Earth scene's pixel input stays byte-identical and only audio metadata is
    added. General FAST_PLUS plans author their pace before this function.
    """
    plan=deepcopy(plan);plan['options']['pace']=plan['request']['pace']='FAST_PLUS'
    plan['production_defaults']['pace']='FAST_PLUS';pauses=[];changes=[]
    for scene in plan['scenes']:
        is_flat=scene.get('render_mode')=='FLAT_MAP_PREMIUM'
        before=deepcopy(scene.get('motion_timing',{}))
        if is_flat:
            _short_map_text(scene)
            if scene.get('pace')!='FAST_PLUS':
                d=scene['duration'];profile=PACE_PROFILES['FAST_PLUS'];peak=scene.get('role') in {'peak','payoff'} or any(e.get('role') in {'peak','payoff'} for e in scene['visual_events'])
                new_factor=1.+(profile['route_speed_factor']-1.)*(.35 if peak else 1.)
                old_factor=max(.1,float(before.get('route_speed_factor',1.)))
                for route in scene['routes']:
                    if route['progress_end']<=route['progress_start']:continue
                    interval=(route['end_time']-route['start_time'])*old_factor/new_factor
                    route['end_time']=frame_time(min(d,route['start_time']+max(min(.5,route['end_time']-route['start_time']),interval)),latest=d)
                motion={**before,'camera_travel_duration':frame_time(d*(.80 if peak else profile['camera_fraction']),latest=d),
                        'zoom_duration':frame_time(d*(.80 if peak else profile['zoom_fraction']),latest=d),
                        'focus_transition_duration':profile['focus_transition_duration'],
                        'route_speed_factor':round(new_factor,6),'entity_speed_factor':round(new_factor,6),
                        'next_event_lead_time':profile['next_event_lead_time'],'tts_playback_rate':1.0}
                # Preserve the approved geographic handoff window when its Earth
                # neighbor is deliberately reused. No different-screen blur.
                if not scene.get('map_transition'):
                    motion['transition_duration']=profile['transition_duration']
                scene['motion_timing']=motion;scene['pace']='FAST_PLUS'
                preview=scene.get('flat_map',{}).get('next_event')
                if preview:preview['lead_time']=min(profile['next_event_lead_time'],preview['event_time'])
            scene['rhythm_visual']=dict(version='v1',camera=dict(knots=deepcopy(DEFAULT_KNOTS)),zoom=dict(knots=deepcopy(DEFAULT_KNOTS)),
                routes=[dict(route_id=r['route_id'],knots=deepcopy(DEFAULT_KNOTS)) for r in scene['routes'] if r['progress_end']>r['progress_start']])
            major=next((e for e in scene['visual_events'] if e['kind']=='route_blocked' and e['time']>.4),None)
            if major:
                pause_start=frame_time(major['time']-1/6)
                # Slow the important response, then accelerate after the hit.
                travel=frame_time(min(scene['duration'],max(scene['motion_timing']['camera_travel_duration'],major['time']+.7)))
                scene['motion_timing']['camera_travel_duration']=travel
                scene['rhythm_visual']['camera']['knots']=_pause_knots(pause_start,major['time'],travel)
                pauses.append(dict(id='PAUSE_'+major['id'],time=round(scene['start_time']+pause_start,6),
                    duration=round(major['time']-pause_start,6),scene_id=scene['scene_id'],event_id=major['id']))
            changes.append(dict(scene_id=scene['scene_id'],before_motion=before,after_motion=scene['motion_timing'],native_component_ramps=True))
        elif not preserve_earth_pixels:
            _short_map_text(scene)
        peak=next((e for e in scene['visual_events'] if e['kind'] in {'peak_reveal','final_reveal'} and e['time']>.4),None)
        if peak:
            start=frame_time(peak['time']-1/6)
            pauses.append(dict(id='PAUSE_'+peak['id'],time=round(scene['start_time']+start,6),duration=round(peak['time']-start,6),scene_id=scene['scene_id'],event_id=peak['id']))
        local=[p for p in pauses if p['scene_id']==scene['scene_id']]
        scene['rhythm_micro_beats']=_micro_beats(scene,local)
    # Route-distance information is calculated from the actual new native clock.
    from .planner import refresh_clock_dependent_route_information
    from .production import _map_text
    for scene in plan['scenes']:
        if scene.get('rhythm_visual'):
            for event in scene['visual_events']:refresh_clock_dependent_route_information(scene,event)
            _map_text(scene,scene.get('production_defaults',{}).get('large_titles',False))
            _short_map_text(scene)
    plan['rhythm_policy']=dict(version='v1',sfx_core_onset_offset_frames=1,micro_pauses=pauses,
        bgm_sidechain=True,reference_pattern='two_uploaded_excerpt_common_patterns_20261006')
    plan.setdefault('metadata',{})['rhythm_timing_changes']=changes
    plan['metadata']['rhythm_policy_notes']=dict(global_time_warp=False,narration_rate=1.,
        semantic_events_not_added_by_micro_beats=True,earth_pixels_deliberately_preserved=preserve_earth_pixels,
        pause_duration_from_reference_bounded_short_energy_dips=True)
    for key in ['gate','approval','plan_hash']:plan.pop(key,None)
    return plan


def validate_rhythm_plan(plan):
    if plan.get('rhythm_policy',{}).get('version')!='v1':return dict(passed=True,errors=[],warnings=[],metrics={},legacy=True)
    from .retention import MEANINGFUL
    errors=[];ramps=0;beat_count=0;meaningful=[];scene_ids={s['scene_id']:s for s in plan['scenes']}
    def error(code,scene_id=None,**values):errors.append(dict(code=code,**({'scene_id':scene_id} if scene_id else {}),**values))
    for scene in plan['scenes']:
        sid=scene['scene_id'];events={e['id']:e for e in scene['visual_events']};seen=set()
        meaningful.extend(scene['start_time']+e['time'] for e in scene['visual_events'] if e.get('meaningful',True) and e['kind'] in MEANINGFUL)
        beats=scene.get('rhythm_micro_beats',[]);beat_count+=len(beats)
        for beat in beats:
            if beat['id'] in seen:error('RHYTHM_DUPLICATE_BEAT',sid)
            seen.add(beat['id'])
            if not 0<=beat['time']<beat['time']+beat['duration']<=scene['duration']+1e-5:error('RHYTHM_BEAT_OUT_OF_SCENE',sid)
            if beat.get('visual_event_id') and beat['visual_event_id'] not in events:error('RHYTHM_UNKNOWN_BEAT_EVENT',sid)
        if any(text.get('text','').upper().strip() in BANNED for text in scene.get('text_events',[])):error('RHYTHM_DECORATIVE_TEXT_FORBIDDEN',sid)
        spec=scene.get('rhythm_visual')
        if not spec:continue
        if scene.get('render_mode')!='FLAT_MAP_PREMIUM':error('RHYTHM_NATIVE_MODE_UNSUPPORTED',sid)
        components=[spec.get('camera',{}),spec.get('zoom',{})]+spec.get('routes',[])
        route_ids={r['route_id']:r for r in scene['routes']};seen_routes=set()
        for component in components:
            knots=component.get('knots',[]);ramps+=1
            if not 2<=len(knots)<=16 or knots[0]['phase']!=0 or knots[-1]['phase']!=1:error('RHYTHM_KNOT_ENDPOINTS',sid);continue
            if any(not math.isfinite(k['phase']) or not 0<=k['phase']<=1 or not math.isfinite(k['speed']) or not 0<=k['speed']<=4 for k in knots):error('RHYTHM_INVALID_SPEED',sid);continue
            try:ramp_phase(.5,knots)
            except ValueError as exc:error(str(exc),sid)
            rid=component.get('route_id')
            if rid:
                if rid in seen_routes or rid not in route_ids:error('RHYTHM_UNKNOWN_OR_DUPLICATE_ROUTE',sid,route_id=rid)
                seen_routes.add(rid);route=route_ids.get(rid)
                if route and route['progress_end']<=route['progress_start']:error('RHYTHM_HELD_ROUTE_RAMP',sid,route_id=rid)
    pauses=plan['rhythm_policy'].get('micro_pauses',[])
    for pause in pauses:
        scene=scene_ids.get(pause['scene_id'])
        if not scene:error('RHYTHM_UNKNOWN_PAUSE_SCENE');continue
        event=next((e for e in scene['visual_events'] if e['id']==pause['event_id']),None)
        if not event or abs(pause['time']+pause['duration']-scene['start_time']-event['time'])>1/30+1e-5:error('RHYTHM_PAUSE_NOT_BEFORE_HIT',scene['scene_id'])
        if not 0<pause['duration']<=.3 or pause['time']<scene['start_time']:error('RHYTHM_PAUSE_WINDOW_INVALID',scene['scene_id'])
    times=sorted(meaningful);gaps=[b-a for a,b in zip(times,times[1:])]
    return dict(passed=not errors,errors=errors,warnings=[],metrics=dict(micro_beats=beat_count,
        speed_ramps=ramps,micro_pauses=len(pauses),visual_events=len(times),
        average_visual_event_interval=sum(gaps)/len(gaps) if gaps else None,
        maximum_visual_event_gap=max(gaps) if gaps else None,
        peaks=sum(e.get('role')=='peak' or e['kind'] in {'peak_reveal','final_reveal'} for s in plan['scenes'] for e in s['visual_events']),
        micro_beats_counted_as_new_story_events=False,full_video_speedup=False))
