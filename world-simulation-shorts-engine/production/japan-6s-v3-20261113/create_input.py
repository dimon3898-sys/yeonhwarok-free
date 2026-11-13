from pathlib import Path
import json,copy,hashlib
p=Path(__file__).resolve().parent
v2=json.loads((p.parent/'japan-6s-v2-20261113/JAPAN_V2_SCENE_INPUT.json').read_text());v3=copy.deepcopy(v2)
v3['prompt']='Japan cinematic city connection, 6 seconds. Supplied illustrative Tokyo, Nagoya, Kyoto connection. No actual transport service is claimed.'
v3['data']['topic']='Japan illustrative city connection transport route'
f=v3['data']['scenes'][0]['facts'];f['subject']['label']='Japan illustrative city connection';f['subject']['aliases']=['Japan illustrative city connection']
f['source_notes'][0]['note']='V3 author-defined illustrative geographic connection through exact previously supplied Tokyo, Nagoya and Kyoto anchors. Not a real airline, rail or road service; playback dates are synthetic. V2 geometry and original records remain unchanged.'
loc={x['id']:x['anchor'] for x in f['locations']}
next(g for g in f['geometries'] if g['id']=='DECLARED_CONNECTION')['geometry']['coordinates']=[loc[x] for x in ['TOKYO','NAGOYA','KYOTO']]
f['routes'][0]['object_graphic']['width_px']=80;f['routes'][0]['object_graphic']['height_px']=80
f['routes'][0]['object_graphic']['polygons'][0]['color']=[.04,.9,1,1]
f['scene_timing'].update(camera_lock_frame=24,event_start_frame=24,action_frames=126)
v3['region']['bbox']=[135.2,33,140.8,39]
v3['presentation']={
 'camera':{'mode':'KEYFRAMES','keyframes':[
 {'frame':0,'center':loc['TOKYO'],'zoom':1},
 {'frame':24,'center':[138.1,35.65],'zoom':.88},
 {'frame':76,'center':[137.9,35.55],'zoom':.91},
 {'frame':102,'center':[137.8,35.48],'zoom':.94},
 {'frame':137,'center':[137.72,35.4],'zoom':1},
 {'frame':149,'center':[137.72,35.4],'zoom':1},
 {'frame':179,'center':[137.72,35.4],'zoom':1}]},
 'mapStyle':{'preset':'REFERENCE_FOCUS_V2','revealFrames':16,'countryFill':False,'nativeBoundaries':True},
 'highlights':[
 {'id':'tokyo-location','locationId':'TOKYO','startFrame':0,'endFrame':180,'ring':{'frames':24,'radiusPx':62,'color':[.04,.9,1,1]}},
 {'id':'nagoya-location','locationId':'NAGOYA','startFrame':82,'endFrame':180,'ring':{'frames':20,'radiusPx':55,'color':[.04,.9,1,1]}},
 {'id':'kyoto-location','locationId':'KYOTO','startFrame':112,'endFrame':180,'ring':{'frames':26,'radiusPx':55,'color':[.04,.9,1,1]}}],
 'labels':{'enabled':True,'items':[]},
 'flow':[{'routeId':'ILLUSTRATIVE_ROUTE','timing':{'fps':30,'start_frame':0,'reveal_frames':36,'direction_start_frame':1,'object_start_frame':1,'travel_frames':113,'departure_pulse_frames':0,'arrival_pulse_frames':12,'hold_frames':30},
 'style':{'width':6,'coreColor':[.83,.98,1,1],'glowColor':[.02,.75,1,1],'glowRadius':10,'glowGain':.65},
 'previewStyle':{'width':2,'coreColor':[.4,.75,.85,.24],'glowColor':[.04,.7,1,.3],'glowRadius':1,'glowGain':.05},
 'trail':{'echoes':3,'spacingPixels':22,'alpha':.33},'reveal':{'mode':'FOLLOW_OBJECT','leadPixels':20}}]}
def label(id,city,text,start,end,priority=90,fade=6):return {'id':id,'role':'EVENT','text':text,'locationId':city,'eventId':city.lower()+'-location','startFrame':start,'endFrame':end,'revealFrames':fade,'exitFrames':1 if end==180 else 6,'style':'REFERENCE_V1','pin':'NONE','priority':priority}
v3['presentation']['labels']['items']=[label('tokyo-intro','TOKYO','도쿄 TOKYO',0,70,100),label('tokyo-result','TOKYO','도쿄',70,180,70),label('nagoya-pass','NAGOYA','나고야 NAGOYA',82,114,100),label('nagoya-result','NAGOYA','나고야',114,180,70),label('kyoto-approach','KYOTO','교토 KYOTO',112,138,100),label('kyoto-arrival','KYOTO','교토 도착',138,180,100)]
# Keep the existing geometry/source values other than inserting the supplied waypoint.
(p/'JAPAN_V3_SCENE_INPUT.json').write_text(json.dumps(v3,ensure_ascii=False,indent=2)+'\n')
def delta(a,b,path='$'):
 if type(a)!=type(b):return [{'field':path,'before':a,'after':b}]
 if isinstance(a,dict):return [x for k in sorted(set(a)|set(b)) for x in (delta(a[k],b[k],path+'.'+k) if k in a and k in b else [{'field':path+'.'+k,'before':a.get(k),'after':b.get(k)}])]
 if isinstance(a,list):
  if len(a)!=len(b):return [{'field':path,'before':a,'after':b}]
  return [x for i in range(len(a)) for x in delta(a[i],b[i],path+f'[{i}]')]
 return [] if a==b else [{'field':path,'before':a,'after':b}]
(p/'INPUT_DELTA.json').write_text(json.dumps(delta(v2,v3),ensure_ascii=False,indent=2)+'\n')
