"""Compare post-draw semantic receipts with rendered, isolated SFX cue timing.

Receipts are renderer visibility thresholds, not optical recognition. PCM onset
metadata describes the isolated rendered layer, not listening to the final mix.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .retention import MEANINGFUL

_EPSILON=1e-6
_MAX_ATTACK_ALLOWANCE=.001
_PRIMITIVES={'information','world_label','geographic_pulse','route_head','3D_entity',
             'route_barrier','network','clip_information','country_highlight','map_vfx'}
_PHYSICAL={'route_start':{'route_head'},'entity_departure':{'3D_entity'},
           'route_blocked':{'route_barrier'},'network_expand':{'network'},
           'arrival':{'geographic_pulse','world_label'}}
_SCOPE='First observed post-draw semantic visibility receipts versus isolated rendered core SFX insertion and measured 10%-peak PCM onset; not optical computer vision or direct listening.'


def _number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _read(value):
    return json.loads(Path(value).read_text()) if isinstance(value,(str,Path)) else value


def _frames(value):
    """Accept the same frame containers as qc._audit_frames, including one path."""
    value=_read(value)
    if isinstance(value,dict):
        if 't' in value and 'scene_id' in value:return [value]
        return _frames(value.get('frames',value.get('audits',[])))
    if isinstance(value,list):return [frame for item in value for frame in _frames(item)]
    return []


def _timing(cue,report):
    sources=report.get('sources',[])+report.get('catalog',{}).get('variants',[])
    source=next((item for item in sources if isinstance(item,dict) and
                 (item.get('id')==cue.get('sfx_variant') or
                  (cue.get('file') and item.get('file')==cue['file']))),{})
    rate=cue.get('sample_rate',source.get('sample_rate',report.get('sample_rate')))
    rate=rate if _number(rate) and rate>0 else None
    insertion=cue.get('onset_sample')
    insertion=float(insertion)/rate if rate and _number(insertion) else cue.get('absolute_time')
    insertion=float(insertion) if _number(insertion) and insertion>=0 else None
    peak=cue.get('first_10percent_peak_sample')
    measured=float(peak)/rate if rate and _number(peak) else None
    attack=measured-insertion if measured is not None and insertion is not None else cue.get('attack_10percent_peak_seconds')
    attack=float(attack) if _number(attack) and attack>=-_EPSILON else None
    if attack is not None:attack=max(0.,attack)
    if measured is None and insertion is not None and attack is not None:measured=insertion+attack
    return insertion,measured,attack,rate


def analyze_frame_sound_sync(plan,audits,cues,fps=30):
    """Require bound canonical sounds to match actual receipts within one frame.

    Explicit pre/post layers and the authored A_OPEN cue are reported separately.
    Unsounded meaningful events retain receipt coverage but do not require SFX.
    """
    base={'passed':True,'enabled':False,'skipped':True,'errors':[],'warnings':[],
          'events':[],'unbound_opening_cues':[],'excluded_layers':[],'scope':_SCOPE}
    if plan.get('rhythm_policy',{}).get('version')!='v1':
        return {**base,'skip_reason':'LEGACY_PLAN_WITHOUT_RHYTHM_V1'}
    if not plan.get('options',{}).get('sfx',True):return {**base,'skip_reason':'SFX_DISABLED'}
    errors=[];warnings=[]
    def error(code,**values):errors.append({'code':code,**values})
    if not _number(fps) or fps<=0:
        return {**base,'passed':False,'errors':[{'code':'RHYTHM_SYNC_INVALID_FPS'}]}
    try:
        report=_read(cues)
        if isinstance(report,list):report={'events':report}
        frames=_frames(audits)
        if not isinstance(report,dict):raise ValueError('Cue report must be an object or event list')
    except (OSError,ValueError,TypeError) as exc:
        return {**base,'passed':False,'errors':[{'code':'RHYTHM_SYNC_EVIDENCE_UNREADABLE','message':str(exc)}]}
    if report.get('enabled') is False:
        return {**base,'passed':False,'errors':[{'code':'RHYTHM_SYNC_SFX_REPORT_DISABLED'}]}
    frame_seconds=1/float(fps)
    scenes={scene['scene_id']:scene for scene in plan.get('scenes',[])}
    meaningful={(scene['scene_id'],event['id']):event for scene in scenes.values()
                for event in scene.get('visual_events',[]) if event.get('kind') in MEANINGFUL
                and event.get('meaningful',True)}
    required=set();canonical_openings=set()
    for scene in scenes.values():
        for sound in scene.get('sound_events',[]):
            target=sound.get('visual_event_id')
            if target and (scene['scene_id'],target) in meaningful:required.add((scene['scene_id'],target))
            elif target and not any(event.get('id')==target for event in scene.get('visual_events',[])):
                error('RHYTHM_SYNC_UNKNOWN_CANONICAL_SOUND_EVENT',scene_id=scene['scene_id'],event_id=target)
            elif sound.get('id')=='A_OPEN' and not target and sound.get('time')==0:
                canonical_openings.add((scene['scene_id'],'A_OPEN'))
    observed={}
    for index,frame in enumerate(frames):
        sid=frame.get('scene_id');scene=scenes.get(sid);local=frame.get('t')
        if scene is None or not _number(local) or not 0<=local<float(scene['duration'])+frame_seconds:
            error('RHYTHM_SYNC_INVALID_AUDIT_FRAME',scene_id=sid,frame=index);continue
        for receipt in frame.get('meaningfulEventsRendered',[]):
            key=(sid,receipt.get('event_id'))
            event=meaningful.get(key)
            if not event:continue
            primitive=receipt.get('rendered_primitive');actual=receipt.get('actual_time')
            physical=_PHYSICAL.get(event['kind'])
            if scene.get('render_mode')=='FLAT_MAP_PREMIUM':
                if event['kind']=='country_reveal':physical={'country_highlight','world_label','geographic_pulse'}
                if event['kind']=='route_reroute':physical={'route_head'}
            if (receipt.get('kind')!=event['kind'] or receipt.get('visible') is not True
                    or primitive not in _PRIMITIVES or not _number(actual)
                    or abs(actual-local)>frame_seconds+_EPSILON
                    or (physical and primitive not in physical)
                    or (primitive in {'country_highlight','map_vfx'} and scene.get('render_mode')!='FLAT_MAP_PREMIUM')
                    or (primitive in {'information','clip_information'} and not str(receipt.get('text','')).strip())):
                error('RHYTHM_SYNC_INVALID_SEMANTIC_RECEIPT',scene_id=sid,event_id=key[1],frame=index);continue
            absolute=float(scene['start_time'])+float(local)
            if key not in observed or absolute<observed[key]['visual_onset_seconds']:
                observed[key]={'scene_id':sid,'event_id':key[1],'kind':event['kind'],
                               'visual_onset_seconds':absolute,'visual_onset_frame':absolute*fps,
                               'first_local_time':float(local),'primitive':primitive}
    grouped={};excluded=[];opening=[];ignored_core=[]
    first_scene=next(iter(scenes),None)
    for cue in report.get('events',[]):
        if cue.get('pre_hit') or cue.get('post_hit') or cue.get('layer') in {'pre','post'}:
            excluded.append({'cue_id':cue.get('id'),'event_id':cue.get('visual_event_id'),
                             'layer':cue.get('layer'),'absolute_time':cue.get('absolute_time')});continue
        if cue.get('enabled') is False:continue
        if cue.get('layer')!='core' or cue.get('primary_sync') is not True:
            error('RHYTHM_SYNC_INVALID_CORE_LAYER',cue_id=cue.get('id'));continue
        sid=cue.get('scene_id');eid=cue.get('visual_event_id');key=(sid,eid)
        if not eid:
            insertion,peak,attack,rate=_timing(cue,report)
            if ((sid,cue.get('id')) not in canonical_openings or sid!=first_scene
                    or insertion is None or insertion>frame_seconds+_EPSILON):
                error('RHYTHM_SYNC_UNBOUND_CORE',cue_id=cue.get('id'),scene_id=sid)
            opening.append({'cue_id':cue.get('id'),'scene_id':sid,'core_insertion_seconds':insertion,
                            'pcm_10percent_onset_seconds':peak,'attack_10percent_peak_seconds':attack})
            continue
        if key not in meaningful:
            ignored_core.append({'cue_id':cue.get('id'),'scene_id':sid,'event_id':eid})
            if sid not in scenes or not any(event.get('id')==eid for event in scenes[sid].get('visual_events',[])):
                error('RHYTHM_SYNC_UNKNOWN_CORE_EVENT',scene_id=sid,event_id=eid)
            continue
        grouped.setdefault(key,[]).append(cue)
        if cue.get('visual_kind')!=meaningful[key]['kind']:
            error('RHYTHM_SYNC_CORE_KIND_MISMATCH',scene_id=sid,event_id=eid,cue_id=cue.get('id'))
    if len(opening)>1:error('RHYTHM_SYNC_EXTRA_UNBOUND_CORE',count=len(opening))
    rows=[]
    for key in sorted(required|set(grouped)):
        sid,eid=key;receipt=observed.get(key);core=grouped.get(key,[])
        if not receipt:error('RHYTHM_SYNC_MISSING_RENDERED_EVENT',scene_id=sid,event_id=eid)
        if not core:error('RHYTHM_SYNC_MISSING_CORE_CUE',scene_id=sid,event_id=eid)
        if len(core)>1:error('RHYTHM_SYNC_DUPLICATE_CORE_CUE',scene_id=sid,event_id=eid,count=len(core))
        if not receipt or not core:continue
        cue=core[0];insertion,peak,attack,rate=_timing(cue,report)
        if insertion is None:
            error('RHYTHM_SYNC_MISSING_CORE_INSERTION',scene_id=sid,event_id=eid);continue
        difference=insertion-receipt['visual_onset_seconds']
        allowance=min(attack,_MAX_ATTACK_ALLOWANCE) if attack is not None else 0.
        pcm_difference=peak-receipt['visual_onset_seconds'] if peak is not None else None
        row={**receipt,'cue_id':cue.get('id'),'authored_visual_time':float(scenes[sid]['start_time'])+float(meaningful[key]['time']),
             'core_insertion_seconds':insertion,'core_insertion_frame':insertion*fps,
             'core_insertion_difference_frames':difference*fps,'pcm_10percent_onset_seconds':peak,
             'pcm_onset_difference_frames':None if pcm_difference is None else pcm_difference*fps,
             'onset_difference_frames':(pcm_difference if pcm_difference is not None else difference)*fps,
             'attack_10percent_peak_seconds':attack,'source_attack_allowance_seconds':allowance,
             'sample_rate':rate,'onset_basis':'measured_10percent_pcm' if peak is not None else 'core_insertion'}
        row['passed']=abs(difference)<=frame_seconds+_EPSILON and (pcm_difference is None or abs(pcm_difference)<=frame_seconds+allowance+_EPSILON)
        rows.append(row)
        if abs(difference)>frame_seconds+_EPSILON:
            error('RHYTHM_SYNC_CORE_OUTSIDE_ONE_FRAME',scene_id=sid,event_id=eid,
                  onset_difference_frames=difference*fps,primitive=receipt['primitive'])
        if pcm_difference is not None and abs(pcm_difference)>frame_seconds+allowance+_EPSILON:
            error('RHYTHM_SYNC_PCM_OUTSIDE_ONE_FRAME',scene_id=sid,event_id=eid,
                  onset_difference_frames=pcm_difference*fps,source_attack_allowance_seconds=allowance)
        if peak is None:warnings.append({'code':'RHYTHM_SYNC_PCM_ATTACK_UNAVAILABLE','scene_id':sid,'event_id':eid})
    measured=sum(row['pcm_10percent_onset_seconds'] is not None for row in rows)
    return {'passed':not errors,'enabled':True,'skipped':False,'errors':errors,'warnings':warnings,
            'events':rows,'unbound_opening_cues':opening,'excluded_layers':excluded,
            'excluded_nonmeaningful_core_cues':ignored_core,
            'metrics':{'meaningful_events':len(meaningful),'meaningful_events_observed':len(observed),
                       'required_bound_events':len(required),'required_bound_events_observed':len(required&set(observed)),
                       'matched_bound_core_events':len(rows),'pcm_onsets_measured':measured,
                       'pcm_onset_measurement_complete':measured==len(rows) and len(rows)==len(required),
                       'maximum_abs_core_insertion_difference_frames':max((abs(row['core_insertion_difference_frames']) for row in rows),default=None),
                       'maximum_abs_pcm_onset_difference_frames':max((abs(row['pcm_onset_difference_frames']) for row in rows if row['pcm_onset_difference_frames'] is not None),default=None),
                       'maximum_measured_attack_seconds':max((row['attack_10percent_peak_seconds'] for row in rows if row['attack_10percent_peak_seconds'] is not None),default=None),
                       'unbound_opening_cues':len(opening),'excluded_pre_post_layers':len(excluded)},
            'policy':{'fps':fps,'core_insertion_tolerance_frames':1,'floating_point_epsilon_seconds':_EPSILON,
                      'maximum_measured_source_attack_allowance_seconds':_MAX_ATTACK_ALLOWANCE},'scope':_SCOPE}
