"""Versioned, geography-independent presentation decisions for newly authored plans.

The physical route/entity clocks, factual provenance and certified GPU admission
are never resampled. Saved plans are selected by their own version and hashes.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import math

VERSION = 'direction_v012'
ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('web/direction_visual_adapter.js', 'web/render_direction_earth.html',
           'web/render_direction_flat.html', 'tools/direction_semantic_preflight.mjs')
SUPPORT = {'milestone_reveal', 'distance_reveal', 'milestone'}
IMPORTANT = {'arrival', 'route_blocked', 'route_reroute', 'alternate_route_reveal',
             'new_variable', 'final_reveal', 'peak_reveal'}


def reading_time(text, *, result=False, important=False, density=1, motion=0, zoom='REGIONAL'):
    """Seconds, not multiplied by the QA/production duration ratio."""
    han = sum('\u3000' <= c <= '\u9fff' or '\uac00' <= c <= '\ud7af' for c in text)
    latin = len(text) - han
    floor, ceiling = (1.05, 1.5) if result else ((.82, 1.2) if important else (.62, .9))
    language = han / 8 + latin / 22
    return round(min(ceiling, max(floor, .35 + language + .06 * max(0, density-1)
                                + min(.12, motion/500) + (.05 if zoom == 'WORLD' else 0))), 3)


def angle(a, b):
    def v(p):
        lat, lon = math.radians(p['lat']), math.radians(p['lon'])
        return math.cos(lat)*math.cos(lon), math.sin(lat), math.cos(lat)*math.sin(lon)
    return math.degrees(math.acos(max(-1, min(1, sum(x*y for x,y in zip(v(a),v(b)))))))


def camera_up(a,b,up=None):
    def vector(p):
        la,lo=math.radians(p['lat']),math.radians(p['lon'])
        return [math.cos(la)*math.cos(lo),math.sin(la),-math.cos(la)*math.sin(lo)]
    def cross(u,v):return [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    av,bv=vector(a),vector(b)
    if up is None:
        la,lo=math.radians(a['lat']),math.radians(a['lon'])
        up=[-math.sin(la)*math.cos(lo),math.cos(la),math.sin(la)*math.sin(lo)]
    axis=cross(av,bv);sn=math.sqrt(sum(x*x for x in axis));co=sum(x*y for x,y in zip(av,bv))
    if sn<1e-9:return list(up),list(up)
    k=[x/sn for x in axis];kx=cross(k,up);dot=sum(x*y for x,y in zip(k,up))
    return list(up),[up[i]*co+kx[i]*sn+k[i]*dot*(1-co) for i in range(3)]


def apply_direction(plan):
    if plan.get('options', {}).get('pace') != 'FAST_PLUS':
        return plan
    if any(s.get('direction') for s in plan['scenes']):
        return plan  # Never silently upgrade a persisted direction version.
    result = deepcopy(plan)
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    previous = None
    for index, scene in enumerate(result['scenes']):
        scene.pop('visual_readability', None)
        d = scene['duration']
        final = index == len(result['scenes'])-1
        earth = scene.get('render_mode') != 'FLAT_MAP_PREMIUM'
        events = scene['visual_events']
        texts = scene.get('text_events', [])
        # Optional decorative questions do not earn event receipts or facts.
        decorations = {e['id'] for e in events if e.get('meaningful') is False
                       and e.get('kind') == 'hook_reveal'}
        scene['text_events'] = texts = [t for t in texts if t.get('event_id') not in decorations]
        scene['sound_events']=[s for s in scene.get('sound_events',[])
                               if not (s.get('id')=='A_OPEN' and s.get('visual_event_id') is None
                                       and s.get('kind')=='cinematic_hit')]
        if index == 0:
            # The verified geographical opening itself is the primary hook.
            # Do not add an ambiguous question above it.
            for label in scene.get('labels', []):
                if label.get('coordinates',{}).get('location_id') == scene['coordinates'].get('location_id'):
                    label['kind']='hook_reveal'
        # Short QA carries fewer support figures. Required causal facts stay.
        omitted = []
        if d <= 3 and not any(e.get('caused_by') for e in events):
            for event in events:
                if event.get('kind') in SUPPORT and event.get('role') == 'progression':
                    omitted.append(deepcopy(event))
                    # Only genuinely independent support may be dropped. A
                    # causal/retention receipt cannot be replaced by a caption.
                    event['meaningful'] = False
            omitted_ids = {e['id'] for e in omitted}
            texts[:] = [t for t in texts if t.get('event_id') not in omitted_ids]
            scene['sound_events'] = [s for s in scene.get('sound_events', [])
                                     if s.get('visual_event_id') not in omitted_ids | decorations]
        primary_event = next((e for e in events if e.get('kind') in IMPORTANT), None)
        if final:
            primary_event=next((e for e in reversed(events) if e['kind']=='final_reveal'),primary_event)
        primary_event = primary_event or next((e for e in events if e.get('role')=='hint'
                                              and e.get('kind') in {'destination_preview','route_choice'}),None)
        primary = next((t['text'] for t in texts if primary_event
                        and t.get('event_id') == primary_event['id']), None)
        primary = primary or next((l['text'] for l in scene.get('labels', [])
                                   if l.get('coordinates', {}).get('location_id') == scene['coordinates'].get('location_id')), '')
        zoom = 'WORLD' if final else ('REGIONAL' if scene.get('routes') else 'LOCAL')
        motion = angle(scene['camera_start'], scene['camera_end'])
        settle = reading_time(primary, result=final, important=bool(primary_event),
                              density=min(3, len(texts)+1), motion=motion, zoom=zoom)
        # A pre-existing physical early event receives an entry read window.
        # The final window is protected separately; no endless camera easing.
        early = primary_event is not None and primary_event['time'] < .4 and not final
        lead = primary_event['time']+settle if early else (.35 if index == 0 else 0)
        tail = .25 if early else settle
        travel = max(.35, d-lead-tail)
        if travel+lead+tail > d:
            lead = max(0, d-travel-tail)
        # A new information/SFX beat must land on the actual 30fps frame grid.
        # Round travel down so the protected reading minimum is never reduced.
        end_move = round(math.floor((d-tail)*30+1e-9)/30, 6)
        if not early:
            settle = round(d-end_move, 6)
        # One dominant axis. Strong geographical moves keep FOV and attitude
        # constant; height changes use a separate latter part of the same move.
        if earth:
            if scene['camera_preset'] == 'HORIZON_REVEAL':
                scene['camera_preset'] = 'COUNTRY_APPROACH'
            focus=deepcopy(scene['coordinates'])
            if early:
                # Once the arrival is read, the next moving path becomes focus.
                focus.update(lon=scene['camera_end']['lon'],lat=scene['camera_end']['lat'])
                if index+1<len(result['scenes']):
                    next_point=result['scenes'][index+1]['coordinates']
                    focus['lon']+=(((next_point['lon']-focus['lon']+180)%360)-180)*.25
                    focus['lat']+=(next_point['lat']-focus['lat'])*.25
            # A repeated location followed by a new location is a geographic
            # handoff, not an invitation to chase an unrelated route midpoint.
            if (not final and index+1<len(result['scenes']) and index
                    and scene['coordinates'].get('location_id') == result['scenes'][index-1]['coordinates'].get('location_id')):
                focus=deepcopy(result['scenes'][index+1]['coordinates'])
            if final:
                prior=next((s['coordinates'] for s in reversed(result['scenes'][:index])
                            if s['coordinates'].get('location_id') != focus.get('location_id')),None)
                if prior:
                    focus['lon']=focus['lon']+(((prior['lon']-focus['lon']+180)%360)-180)/3
                    focus['lat']=(focus['lat']*2+prior['lat'])/3
                network=[e['coordinates'] for e in events if e.get('coordinates')
                         and e['kind'] in {'network_expand','network_expansion','final_reveal'}]
                if len(network)>1:
                    origin=network[0]['lon']
                    focus['lon']=sum(origin+((c['lon']-origin+180)%360)-180 for c in network)/len(network)
                    focus['lat']=sum(c['lat'] for c in network)/len(network)
            if result['duration'] >= 40:
                # Production legs contain several truthful distance updates.
                # Their certified geographic endpoint frames those moving
                # paths; do not substitute the QA's compressed location handoff.
                focus.update(lon=scene['camera_end']['lon'],lat=scene['camera_end']['lat'])
                late=next((e for e in reversed(events) if e.get('coordinates')
                           and e['kind'] in {'new_variable','destination_preview','arrival','country_reveal'}
                           and e['time']>=d-1.3),None)
                if late:
                    point=late['coordinates']
                    focus['lon']+=(((point['lon']-focus['lon']+180)%360)-180)*.5
                    focus['lat']+=(point['lat']-focus['lat'])*.5
            scene['camera_end'].update(lon=focus['lon'],lat=focus['lat'])
            for name in ('camera_start', 'camera_end'):
                scene[name].update(fov=62, yaw=-.18, bank=0, tilt=.30)
                # Geographical aim and rig share the same phase, avoiding an
                # independent target swing while the zoom axis decelerates.
                scene[name]['target_lon'] = scene[name]['lon']
                scene[name]['target_lat'] = scene[name]['lat']
                scene[name]['height'] = 2.25
            if final:
                key_points=[e['coordinates'] for e in events if e.get('coordinates')
                            and e['kind'] in {'final_reveal','network_expand','network_expansion'}]
                spread=max((angle(focus,c) for c in key_points),default=0)
                scene['camera_end']['height'] = 2.0 if spread<45 else 2.30
                scene['camera_end']['tilt'] = .12
            if index == 0:
                scene['camera_start']['height'] = 2.35
            if previous and previous.get('render_mode') == scene.get('render_mode'):
                scene['camera_start'] = deepcopy(previous['camera_end'])
        scene['entry_state']['camera'] = deepcopy(scene['camera_start'])
        scene['exit_state']['camera'] = deepcopy(scene['camera_end'])
        if previous and previous.get('render_mode') != scene.get('render_mode'):
            # The existing registered geographic morph converts projection.
            # Its declared handoff pose must still match the next entry exactly.
            previous['camera_end'] = deepcopy(scene['camera_start'])
            previous['exit_state']['camera'] = deepcopy(scene['camera_start'])
        if not earth:
            # Fit verified geographic event locations, not only the original
            # focus center. Longitude extents are unwrapped around that center.
            config=scene['flat_map']
            coords=[scene['coordinates']]+[e['coordinates'] for e in events if e.get('coordinates')]
            origin=config['camera_start']['lon']
            lons=[origin+((c['lon']-origin+180)%360)-180 for c in coords]
            needed=max(8, (max(lons)-min(lons))/.70)
            center=(max(lons)+min(lons))/2
            for name in ('camera_start','camera_end'):
                config[name]['span_degrees']=max(needed,config[name].get('span_degrees',24))
                config[name]['lon']=((center+180)%360)-180
            # An abstract relationship needs a visible, source-bound label if
            # fewer than two physical routes are active. No fake network proof.
            from .gis import resolve_location
            for event in events:
                if event['kind']=='connection_reveal' and not event.get('text') and event.get('coordinates'):
                    location=resolve_location(event['coordinates']['location_id'])
                    event['text']=location['name'].upper()
                    texts.append(dict(id='D_'+event['id'],event_id=event['id'],text=event['text'],
                        coordinates=deepcopy(event['coordinates']),start_time=event['time'],
                        end_time=min(d,event['time']+max(.7,event['duration'])),role='status',
                        priority=8,large_title_approved=False))
        # A fresh, independently drawn connection in the middle is a real
        # variable. Relabel its narrative role, never fabricate a primitive.
        for event in events:
            absolute = scene['start_time'] + event['time']
            route = next((r for r in scene['routes'] if r['route_id'] == event.get('target_id')), None)
            if (event['kind'] == 'route_start' and route and route.get('progress_start', 0) == 0
                    and abs(route['start_time']-event['time']) < 1/30
                    and .35*result['duration'] <= absolute <= .70*result['duration']):
                event['role'] = 'variable'
        # Delay optional, non-physical result text together with its event/SFX.
        for event in events:
            if (index and not early and event['kind'] in {'destination_preview','route_choice','city_reveal'}
                    and event.get('role') == 'hint' and event['time'] < end_move
                    and result['duration']<=15 and scene['start_time']>3):
                shift=end_move-event['time']
                event['time']=end_move
                event['duration']=min(event['duration'],d-end_move)
                for text in texts:
                    if text.get('event_id')==event['id']:
                        text['start_time']+=shift
                        text['end_time']=min(d,text['end_time']+shift)
                preview=scene.get('flat_map',{}).get('next_event')
                if preview and preview.get('event_id')==event['id']:
                    preview['event_time']=event['time']
                for sound in scene.get('sound_events',[]):
                    if sound.get('visual_event_id')==event['id']:sound['time']=event['time']
            if final and event['kind']=='final_reveal' and abs(event['time']-end_move)>1e-6:
                shift = end_move-event['time']
                event['time'] = end_move
                event['duration'] = min(event['duration'], d-end_move)
                for text in texts:
                    if text.get('event_id') == event['id']:
                        text['start_time'] += shift
                        text['end_time'] = d
                for sound in scene.get('sound_events', []):
                    if sound.get('visual_event_id') == event['id']:
                        sound['time'] = event['time']
        up_start,up_end=camera_up(scene['camera_start'],scene['camera_end'],
            previous.get('direction',{}).get('camera_up_end') if previous and earth and previous.get('render_mode')==scene.get('render_mode') else None)
        roll=0.
        if earth and d>=4:
            desired,_=camera_up(scene['camera_end'],scene['camera_end'])
            la,lo=math.radians(scene['camera_end']['lat']),math.radians(scene['camera_end']['lon'])
            n=[math.cos(la)*math.cos(lo),math.sin(la),-math.cos(la)*math.sin(lo)]
            cross=[up_end[1]*desired[2]-up_end[2]*desired[1],up_end[2]*desired[0]-up_end[0]*desired[2],up_end[0]*desired[1]-up_end[1]*desired[0]]
            roll=math.atan2(sum(x*y for x,y in zip(n,cross)),sum(x*y for x,y in zip(up_end,desired)))
            up_end=desired
        scene['direction'] = dict(version=VERSION, preset='FAST_PLUS_DIRECTOR',
            camera_up_start=up_start,camera_up_end=up_end,camera_roll_correction=roll,
            mode='QA' if result['duration'] <= 15 else 'PRODUCTION',
            intent='RESULT_HERO' if final else ('LOCATION_ANCHOR' if not scene['routes'] else 'ROUTE_TRACK'),
            initial_hold=lead, move_end=end_move, settle=settle, acceleration_fraction=.20,
            settle_position='ENTRY' if early else 'EXIT',
            angular_budget_deg_s=55, primary=primary, zoom_level=zoom,
            primary_event_id=primary_event['id'] if primary_event else None,
            text_layers=['LOCATION','EVENT','SUPPORT'], safe_area=[.055,.075,.945,.86],
            route_width_1080=3.5 if zoom=='WORLD' else 3.0,
            entity_min_pixels_1080=18, entity_scale_cap=.015,
            geography_floor=.17, total_duration=result['duration'], source_hashes=hashes,
            omitted_support=omitted,
            beats=[dict(kind='MOVE',start=lead,end=end_move),
                   dict(kind='DECELERATION',start=lead+(end_move-lead)*.8,end=end_move),
                   dict(kind='SETTLE',start=primary_event['time'] if early else end_move,end=lead if early else d),
                   dict(kind='INFORMATION',start=end_move,end=d,primary=primary)])
        for text in texts:
            text['end_time']=min(d,max(text['end_time'],text['start_time']+reading_time(text['text'],
                result=final and any(e['id']==text.get('event_id') and e['kind']=='final_reveal' for e in events))))
        previous = scene
    result.setdefault('metadata', {})['direction_version'] = VERSION
    # Rebuild the preserved rhythm micro-beats from the retimed informational
    # events; keep BGM law/layers/history/ducking and physical route time intact.
    from .rhythm import _micro_beats, frame_time
    pauses=result.get('rhythm_policy',{}).get('micro_pauses',[])
    for pause in pauses:
        scene=next(s for s in result['scenes'] if s['scene_id']==pause['scene_id'])
        event=next(e for e in scene['visual_events'] if e['id']==pause['event_id'])
        local=frame_time(max(0,event['time']-1/6))
        pause['time']=round(scene['start_time']+local,6)
        pause['duration']=round(event['time']-local,6)
    for scene in result['scenes']:
        scene['rhythm_micro_beats']=_micro_beats(scene,[p for p in pauses if p['scene_id']==scene['scene_id']])
    result['metadata']['direction_qc'] = direction_qc(result)
    return result


def direction_qc(plan):
    """Planning warnings versus structural blockers; pixel tests remain NOT_RUN."""
    rows=[]
    for scene in plan['scenes']:
        p=scene.get('direction')
        if not p: continue
        sid=scene['scene_id']; move=p['move_end']-p['initial_hold']
        def add(code,severity='WARNING',**details):
            rows.append(dict(code=code,severity=severity,scene_id=sid,**details))
        if not 0 <= p['initial_hold'] < p['move_end'] < scene['duration']:
            add('INVALID_CAMERA_WINDOW','CRITICAL')
        if not all(math.isfinite(v) for pose in (scene['camera_start'],scene['camera_end']) for v in pose.values() if isinstance(v,(int,float))):
            add('INVALID_CAMERA','CRITICAL')
        if move > 0 and angle(scene['camera_start'],scene['camera_end'])*1.25/move > p['angular_budget_deg_s']:
            add('CAMERA_MOTION_OVERLOAD')
        if p['settle'] < (.99 if p['intent']=='RESULT_HERO' else .6): add('INSUFFICIENT_SETTLE')
        windows=[t for t in scene.get('text_events',[]) if len(t.get('text',''))>14
                 and t['start_time']<p['move_end'] and t['end_time']>p['initial_hold']]
        if windows: add('TEXT_DURING_HIGH_MOTION',text_event_ids=[t['id'] for t in windows])
        for sound in scene.get('sound_events',[]):
            event=next((e for e in scene['visual_events'] if e['id']==sound.get('visual_event_id')),None)
            if event and abs(sound['time']-event['time'])>1/30+.001:add('SFX_EVENT_MISALIGNMENT')
    return dict(passed=not any(r['severity']=='CRITICAL' for r in rows), findings=rows,
                rendered_pixel_checks='NOT_RUN',
                pixel_rules=['LABEL_COLLISION','ENTITY_TOO_SMALL','ROUTE_LOW_CONTRAST',
                             'GEOGRAPHY_TOO_DARK','RESULT_HERO_TOO_SMALL','INFORMATION_DENSITY_HIGH'])
