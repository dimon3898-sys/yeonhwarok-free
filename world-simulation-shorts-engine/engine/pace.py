"""Scene-local pace authoring; never resample a video or change narration speed."""
from copy import deepcopy
import math

PACE_PROFILES = {
    'FAST': dict(camera_fraction=.72, zoom_fraction=.66, route_speed_factor=1.20,
                 focus_transition_duration=.18, transition_duration=.38,
                 next_event_lead_time=.35, peak_hold_duration=.8, travel_limit=4.2),
    'NORMAL': dict(camera_fraction=.90, zoom_fraction=.86, route_speed_factor=1.,
                   focus_transition_duration=.30, transition_duration=.65,
                   next_event_lead_time=.65, peak_hold_duration=1.0, travel_limit=6.),
    'CINEMATIC': dict(camera_fraction=1., zoom_fraction=1., route_speed_factor=.9,
                      focus_transition_duration=.42, transition_duration=.90,
                      next_event_lead_time=.85, peak_hold_duration=1.3, travel_limit=8.),
}


def normalize_pace(value='FAST'):
    value = str(value).upper().removeprefix('PACE_')
    if value not in PACE_PROFILES:
        raise ValueError('Pace must be FAST / NORMAL / CINEMATIC')
    return value


def frame_time(value, fps=30, *, latest=None):
    """First frame at or after an authored onset; optional inclusive last bound."""
    snapped = math.ceil(float(value)*fps-1e-4)/fps
    if latest is not None:
        snapped = min(snapped, math.floor(float(latest)*fps+1e-7)/fps)
    return round(max(0., snapped), 6)


def speech_estimate(scene):
    text=scene.get('narration','')
    return len(text.replace(' ',''))/5.8 if any('\uac00' <= c <= '\ud7a3' for c in text) else len(text.split())/2.6


def apply_scene_pace(scene, pace='FAST'):
    """Faster travel and focus within the same Scene; endpoint state stays exact.

    Changing route end windows gives actual authored movement a shorter interval.
    Progress start/end, GIS geometry, Scene duration and TTS samples are untouched.
    Peaking Scenes use a smaller acceleration and reserve recognition time.
    """
    scene=deepcopy(scene);pace=normalize_pace(pace);profile=PACE_PROFILES[pace]
    d=float(scene['duration']);peak=scene.get('role') in {'peak','payoff'} or any(
        e.get('role') in {'peak','payoff'} for e in scene.get('visual_events',[]))
    factor=1.+(profile['route_speed_factor']-1.)*(.35 if peak else 1.)
    before=[]
    for route in scene.get('routes',[]):
        start=float(route.get('start_time',0));end=float(route.get('end_time',d))
        if end<=start or route.get('progress_end',1)<=route.get('progress_start',0):continue
        revised=min(d,start+(end-start)/factor)
        # Route starts remain paired with physical events; modest end trim only.
        revised=max(start+min(.5,end-start),revised)
        revised=frame_time(revised,latest=d)
        if abs(revised-end)<1e-6:continue
        route['end_time']=revised
        # Entity visibility is a separate clock. A persistent/continuing plane
        # remains in frame while the earlier-completed route settles; trimming
        # its display lifetime would create a disappear/reappear boundary bug.
        before.append(dict(route_id=route['route_id'],before_end_time=end,after_end_time=revised))
    # Keep a visible camera path throughout. FAST approaches settle earlier but
    # renderer retains tracking, next-event preview and the true handoff clock.
    fraction=max(profile['camera_fraction'],.85 if peak else 0.)
    camera=frame_time(d*fraction,latest=d)
    zoom=frame_time(d*max(profile['zoom_fraction'],.85 if peak else 0.),latest=d)
    hold=profile['peak_hold_duration'] if peak else 0.
    scene['pace']=pace
    scene['motion_timing']=dict(camera_travel_duration=camera,zoom_duration=zoom,
        camera_speed_reference=float(scene.get('camera_speed',1.)),
        focus_transition_duration=profile['focus_transition_duration'],
        route_speed_factor=round(factor,6),entity_speed_factor=round(factor,6),
        transition_duration=profile['transition_duration'],peak_hold_duration=hold,
        next_event_lead_time=profile['next_event_lead_time'],
        dead_time_removed=round(max(0.,d-camera),6),tts_playback_rate=1.0)
    if scene.get('map_transition'):
        scene['map_transition']['duration']=profile['transition_duration']
    flat=scene.get('flat_map')
    if flat:
        if flat.get('transition_duration') is not None:flat['transition_duration']=profile['transition_duration']
        preview=flat.get('next_event')
        if preview:
            preview['lead_time']=min(profile['next_event_lead_time'],float(preview['event_time']))
    return scene,dict(scene_id=scene['scene_id'],pace=pace,duration_unchanged=d,
        route_timing_changes=before,camera_travel_duration=camera,zoom_duration=zoom,
        narration_speed_unchanged=True,entity_display_lifetime_preserved=True,ffmpeg_speed_filter=False)


def retime_scene_plan(plan, scene_durations):
    """Copy-only, frame-aligned partial plan retiming before approval.

    Used for a bounded integration sample. Normal natural-language requests keep
    their requested total length: production pace changes motion, not speech.
    Every local clock is scaled together; dependency snapshots are rebuilt from
    existing exit-state geometry. Source plans, caches and files are never edited.
    """
    if len(scene_durations)!=len(plan['scenes']):raise ValueError('One duration per Scene is required')
    updated=deepcopy(plan);changes=[];cursor=0.;previous=None
    for scene,new_duration in zip(updated['scenes'],scene_durations):
        new_duration=round(float(new_duration)*30)/30
        if new_duration<=0:raise ValueError('Scene duration must be positive')
        if speech_estimate(scene)>new_duration*1.08:
            raise ValueError('NARRATION_TOO_LONG: '+scene['scene_id']+'; shorten script or increase Scene duration')
        old_duration=float(scene['duration']);old_start=float(scene['start_time']);scale=new_duration/old_duration
        scene.update(start_time=round(cursor,6),duration=new_duration,render_time_offset=round(cursor,6))
        # Fields which are local seconds, never coordinates, progress, altitude,
        # phase offsets, sound gain, camera speed, text size or audio samples.
        for collection in ['routes','entities','entity_actions','visual_events','sound_events','labels','effects','text_events']:
            for item in scene.get(collection,[]):
                for key in ['time','start_time','end_time','duration']:
                    if isinstance(item.get(key),(float,int)):
                        item[key]=round(max(0.,float(item[key])*scale),6)
        for key in ['motion_start']:
            if key in scene:scene[key]=round(scene[key]*scale,6)
        for collection in ['country_highlights','focus']:
            for item in scene.get('flat_map',{}).get(collection,[]):
                for key in ['start_time','end_time']:item[key]=round(item[key]*scale,6)
        preview=scene.get('flat_map',{}).get('next_event')
        if preview:
            for key in ['event_time','lead_time']:preview[key]=round(preview[key]*scale,6)
        # Independent render snapshots retain actual geometry but share the
        # edited sequence's new continuous timeline/state boundary.
        if previous is not None:scene['entry_state']=deepcopy(previous)
        scene['entry_state']['camera']=deepcopy(scene['camera_start'])
        scene['exit_state']['camera']=deepcopy(scene['camera_end'])
        previous=scene['exit_state'];cursor+=new_duration
        changes.append(dict(scene_id=scene['scene_id'],before_duration=old_duration,
            after_duration=new_duration,before_start=old_start,after_start=scene['start_time'],local_clock_scale=scale))
    updated['duration']=round(cursor,6)
    updated['request']['duration']=updated['duration']
    for scene in updated['scenes']:
        scene['timeline_position']=round(scene['start_time']/cursor,6)
        scene['exit_state']['timeline']['timeline_position']=round((scene['start_time']+scene['duration'])/cursor,6)
    # previous exit is authoritative; this also propagates revised timelines.
    for index,scene in enumerate(updated['scenes'][1:],1):
        scene['entry_state']=deepcopy(updated['scenes'][index-1]['exit_state'])
    updated.setdefault('metadata',{})['production_scene_retiming']=changes
    for key in ['gate','approval','plan_hash']:updated.pop(key,None)
    return updated


def analyze_dead_time(plan):
    """Production-only gate; motion by itself never repairs a story gap."""
    from .retention import MEANINGFUL
    errors=[];warnings=[];scenes=[]
    absolute=[]
    for scene in plan.get('scenes',[]):
        pace=normalize_pace(scene.get('pace',plan.get('options',{}).get('pace','FAST')))
        profile=PACE_PROFILES[pace];d=float(scene['duration']);sid=scene['scene_id']
        events=[e for e in scene.get('visual_events',[]) if e.get('kind') in MEANINGFUL and e.get('meaningful',True)]
        absolute.extend((float(scene['start_time'])+float(e['time']),sid,e['id']) for e in events)
        transition=float(scene.get('map_transition',{}).get('duration',scene.get('flat_map',{}).get('transition_duration',0)))
        limit=.6 if pace=='FAST' else 1. if pace=='NORMAL' else 1.5
        if transition>limit+.001:errors.append(dict(code='DEAD_TIME_LONG_TRANSITION',scene_id=sid,duration=transition,max_seconds=limit))
        for route in scene.get('routes',[]):
            if route.get('faint') or route.get('progress_start',0)==route.get('progress_end',1):continue
            travel=float(route.get('end_time',d))-float(route.get('start_time',0))
            changes=[e for e in events if route.get('start_time',0)<e['time']<route.get('end_time',d) and e['kind'] not in {'entity_departure','milestone_reveal'}]
            if travel>profile['travel_limit'] and not changes:
                errors.append(dict(code='DEAD_TIME_LONG_ENTITY_TRAVEL',scene_id=sid,route_id=route['route_id'],duration=round(travel,4),suggestion='Shorten authored travel or add a real causal change'))
        for event in events:
            if event.get('role') in {'peak','payoff'} or event['kind'] in {'peak_reveal','final_reveal'}:
                available=min(d-event['time'],float(event.get('duration',d-event['time'])))
                if available<.8-1/30-1e-6:errors.append(dict(code='PEAK_READ_TIME_TOO_SHORT',scene_id=sid,event_id=event['id'],available_seconds=round(available,4),minimum_seconds=.8))
                if d-event['time']>3.01 and not any(e['time']>event['time'] for e in events):
                    errors.append(dict(code='DEAD_TIME_AFTER_PEAK',scene_id=sid,event_id=event['id'],seconds=round(d-event['time'],4)))
        motion=scene.get('motion_timing',{})
        if motion.get('tts_playback_rate',1)!=1:errors.append(dict(code='TTS_RATE_CHANGED_BY_PACE',scene_id=sid))
        scenes.append(dict(scene_id=sid,pace=pace,transition_seconds=transition,meaningful_events=len(events),narration_estimate_seconds=round(speech_estimate(scene),4)))
    absolute.sort();bounds=[0.]+[x[0] for x in absolute]+[float(plan.get('duration',0))]
    gaps=[(a,b) for a,b in zip(bounds,bounds[1:]) if b-a>3.01]
    for start,end in gaps:errors.append(dict(code='DEAD_TIME_CAMERA_ONLY_OR_UNCHANGED',start_time=round(start,4),end_time=round(end,4),seconds=round(end-start,4)))
    return dict(passed=not errors,errors=errors,warnings=warnings,scenes=scenes,
        camera_motion_counted_as_event=False,tts_playback_rate=1.0,
        automatic_remediation='Scene-local motion timing; story gaps remain blocking until approved plan correction')
