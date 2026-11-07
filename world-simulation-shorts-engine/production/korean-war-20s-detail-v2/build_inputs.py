"""Author two inputs for existing ten-second presentation path; not a renderer."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib

HERE=Path(__file__).resolve().parent
def write(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
countries=json.loads((HERE/'sources/COUNTRIES_CONTEXT.json').read_text())['features']
cities=json.loads((HERE/'sources/CITY_CONTEXT.json').read_text())['features']
city={x['properties']['name']:x['geometry']['coordinates'] for x in cities}

# Dissolve only identical shared edges. Every surviving point/edge comes from
# the pinned modern geographic source. No observed control area is inferred.
edges=Counter(); original=0
for f in countries:
    for polygon in f['geometry']['coordinates']:
        assert len(polygon)==1,'Unexpected hole: do not infer a topology'
        ring=polygon[0];assert ring[0]==ring[-1]
        for a,b in zip(ring,ring[1:]):
            a,b=tuple(a),tuple(b)
            if a==b:continue
            edges[tuple(sorted((a,b)))]+=1;original+=1
assert all(n in (1,2) for n in edges.values())
remaining={e for e,n in edges.items() if n==1};shared=sum(n==2 for n in edges.values())
assert shared>0,'No source-qualified shared edge found'
graph=defaultdict(set)
for a,b in remaining:graph[a].add(b);graph[b].add(a)
assert all(len(v)==2 for v in graph.values()),'Cannot dissolve without guessing'
rings=[];unused=set(remaining)
while unused:
    a,b=min(unused);ring=[a,b];unused.remove(tuple(sorted((a,b))))
    while ring[-1]!=ring[0]:
        options=[x for x in graph[ring[-1]] if tuple(sorted((ring[-1],x))) in unused]
        assert len(options)==1,'Ambiguous source topology'
        nxt=options[0];unused.remove(tuple(sorted((ring[-1],nxt))));ring.append(nxt)
    rings.append([list(x) for x in ring])
area=lambda ring:abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:])))/2
rings.sort(key=area,reverse=True)
land={'type':'MultiPolygon','coordinates':[[ring] for ring in rings]}
# Existing per-geometry capacity stays 4096: separate complete source polygons,
# never split, smooth, simplify, or invent an edge.
land_groups=[[],[]]
for ring in rings:
    group=0 if sum(len(p[0]) for p in land_groups[0])+len(ring)<=4096 else 1
    land_groups[group].append([ring])
assert all(sum(len(p[0]) for p in group)<=4096 for group in land_groups)
lands=[{'id':'KOREAN_LAND_CONTEXT_'+str(i+1),'source_id':'PINNED_GEOGRAPHIC_CONTEXT','geometry':{'type':'MultiPolygon','coordinates':group}} for i,group in enumerate(land_groups) if group]
land_ids=[g['id'] for g in lands]
# The preserved Area line pass accepts 128 segments. This is an explicitly
# generalized modern context outline, not a historical frontline. Keep original
# vertices; terrain and land polygons retain their original full detail.
main=rings[0]
stride=max(1,(len(main)-2+127)//128)
outline=main[:-1:stride]
outline.append(outline[0])
assert len(outline)<=129
coast={'type':'LineString','coordinates':outline}
direction={'type':'LineString','coordinates':[city['Incheon'],city['Seoul']]}
write('sources/GEOGRAPHIC_DERIVATION.json',{'schema':'WORLD_ENGINE_GEOGRAPHIC_CONTEXT_DERIVATION_V1','method':'Exact shared-edge cancellation and source-edge cycle traversal for area; deterministic original-vertex decimation for optional context line only','sourceEdges':original,'sharedEdgesRemovedTwice':shared*2,'retainedAreaEdges':len(remaining),'contextLineVertices':len(outline),'contextLineStride':stride,'outputRings':len(rings),'inventedVertices':0,'historicalControlPolygon':False,'sourceGitBlob':'5ebc66e25fc1af01edaebe9375c546655e04cf1e','directionMeaning':'Straight diagram of verified Incheon-to-Seoul campaign direction; not a unit track or road.','directionSource':'https://unarchives.mpva.go.kr/contents/map'})
write('sources/LAND_CONTEXT.geojson',{'type':'Feature','properties':{'meaning':'Modern generalized land context, not 1950 control or shoreline reconstruction'},'geometry':land})

GEO='PINNED_GEOGRAPHIC_CONTEXT'
DIR='OFFICIAL_CAMPAIGN_DIRECTION'
source=[{'id':GEO,'source_type':'GEOGRAPHIC_CONTEXT','verification_status':'VERIFIED',
 'source_reference':'Natural Earth official nvkelso/natural-earth-vector commit ca96624a56bd078437bca8184e78163e5039ad19 geojson/ne_10m_admin_0_countries.geojson blob5ebc66e25fc1af01edaebe9375c546655e04cf1e; unchanged city coordinates from repository bbd2ff9b783d00da208a6296e91183b32905373c populated_places_source.geojson blob4da9c6b27b5cd41d7c930ea9cd0c1f84548b65fb.',
 'note':'Only modern generalized land context and named city coordinates are qualified. Exact shared-edge cancellation removes the modern internal Korea border; coordinates are unchanged. WAR/stages/front_refs are legacy generic display channels. The supplied line is land context, NOT a historic military front. Stage dates define authored emphasis intervals, not occupied-area observations. No faction ownership, historical troop coordinate or land gain is asserted.','license':'Natural Earth Public Domain; existing source receipts reused','crs':'EPSG:4326','resolution':'Natural Earth 1:10 million modern geometry and NASA BMNG September2004 nominal500m shaded-topography raster; REGIONAL context only, not a1950 shoreline reconstruction.'},
 {'id':DIR,'source_type':'OFFICIAL_HISTORY_AND_DERIVED_DIRECTION_DIAGRAM','verification_status':'VERIFIED','source_reference':'https://unarchives.mpva.go.kr/contents/map ; https://theme.archives.go.kr/next/chronology/yearRecord.do?archiveEvntId=0049286404&year=1950',
 'note':'Official narrative states Incheon landing on1950-09-15, advance toward Seoul and Seoul recapture on1950-09-28. The straight segment joins existing named city-context points and shows that direction only. It is labeled 진격 방향(개략), is not an actual troop route, and is never extended to sea or a landing beach. No exact sea approach is fabricated.','license':'Facts paraphrased; no website image or copied map incorporated','crs':'EPSG:4326','resolution':'City-level diagram only; no route accuracy claim.'}]
locations=[{'id':name.upper(),'label':{'Daegu':'대구','Incheon':'인천','Busan':'부산','Seoul':'서울'}[name],'anchor':xy,'country_id':'COUNTRY_KOR'} for name,xy in city.items()]
mid=[(city['Incheon'][i]+city['Seoul'][i])/2 for i in range(2)]
locations += [{'id':'DIRECTION_LABEL','label':'진격 방향 설명 위치','anchor':mid,'country_id':'COUNTRY_KOR'}]

def facts(sid,dates,line='LAND_OUTLINE',reveal=18):
    return {'version':'PLANNER_FACTS_V1','data_mode':'PRODUCTION','semantic_mode':'ILLUSTRATIVE_FACT_BASED_VISUAL',
      'subject':{'id':'KOREA_GEOGRAPHIC_EVENT_CONTEXT','label':'한국전쟁 사건 지도','aliases':['한국전쟁 사건 지도'],'event_family':'WAR'},
      'locations':locations,'time_range':{'start':dates[0],'end':dates[1]},'source_notes':source,
      'geometries':lands+[{'id':'LAND_OUTLINE','source_id':GEO,'geometry':coast},{'id':'INCHEON_SEOUL_DIRECTION','source_id':DIR,'geometry':direction}],
      'stages':[{'id':sid+'_CONTEXT','date':dates[0],'label':'Geographic background emphasis, not military control','area_refs':land_ids,'front_refs':[line]},{'id':sid+'_HOLD','date':dates[1],'label':'Same land context; no occupation change','area_refs':land_ids,'front_refs':[line]}],
      'routes':[],'markers':[],'text':[],
      'camera':{'anchor':[127.6,37.0],'target_geometry_refs':land_ids,'minimum_context_geometry_refs':land_ids,'detail_policy':'FACT_BASED_VISUAL_GRADE'},
      'native_context':{'country_ids':['COUNTRY_KOR'],'primary_country_id':'COUNTRY_KOR','secondary_country_ids':[],'context_location_ids':['SEOUL']},'scale':{'preferred':'REGIONAL'},
      'scene_timing':{'fps':30,'total_frames':150,'duration_seconds':5,'camera_lock_frame':0,'event_start_frame':0,'initial_reveal_frames':reveal,'state_transition_frames':90-reveal,'final_hold_frames':60,'action_frames':90,'frame_policy':'INTEGER_DETERMINISTIC','blank_interstage_frames':0}}

def camera(rows):return {'mode':'KEYFRAMES','keyframes':[{'frame':f,'center':c,'zoom':z} for f,c,z in rows]}
def event(eid,loc,start=0,end=150):return {'id':eid,'locationId':loc,'startFrame':start,'endFrame':end}
def label(i,text,loc,eid,start=0,end=150,role='EVENT',pin='NONE',pop=False):
    out={'id':i,'role':role,'text':text,'locationId':loc,'startFrame':start,'endFrame':end,'revealFrames':1,'exitFrames':1,'priority':100 if role=='EVENT' else 80,'style':'REFERENCE_V1','pin':pin}
    if eid:out['eventId']=eid
    if pop:out.update(reveal='GRAPHEME_POP',revealFrames=16)
    return out
def presentation(sid,cam,highlights,labels,accent=None):
    style={'preset':'REFERENCE_FOCUS_V2','revealFrames':1,'countryFill':False,'nativeBoundaries':False}
    if accent:style['lineAccentFrames']=accent
    return {'camera':cam,'mapStyle':style,'initialStateVisibility':'PRESERVE_PROVIDED',
      'territoryColors':{sid+'_CONTEXT':[1,.80,.10,.18],sid+'_HOLD':[1,.80,.10,.18]},'highlights':highlights,'labels':{'enabled':True,'items':labels}}

# Every scene uses the same base source extent; camera states cross all cuts.
region={'sourceId':'NASA_BMNG_KOREA_500M_NE10M_V2','crs':'EPSG:4326','center':[127.6,37.0],'bbox':[126.6,35.5,128.6,38.5],'countryId':'COUNTRY_KOR'}
overview=[127.5,38.2];south=city['Daegu'];inch=city['Incheon'];seoul=city['Seoul']
cams=[camera([(0,overview,.25),(15,overview,.25),(105,south,1),(149,south,1)]),
      camera([(0,south,1),(10,south,1),(80,inch,1),(149,inch,1)]),
      camera([(0,inch,1),(20,inch,1),(110,seoul,1),(149,seoul,1)]),
      camera([(0,seoul,1),(149,seoul,1)])]
specs=[('NAKTONG',('1950-09-01','1950-09-14'),'LAND_OUTLINE'),('INCHEON',('1950-09-15','1950-09-16'),'LAND_OUTLINE'),('ADVANCE',('1950-09-16','1950-09-27'),'INCHEON_SEOUL_DIRECTION'),('SEOUL',('1950-09-28','1950-09-29'),'INCHEON_SEOUL_DIRECTION')]
pres=[presentation('NAKTONG',cams[0],[event('south','DAEGU',70)],
 [label('intro','한국전쟁','SEOUL',None,0,55,'COUNTRY'),label('defense','낙동강 방어','DAEGU','south',70,150,pin='CONTEXT',pop=True),label('september','1950.09 초','DAEGU','south',95,150,'NUMERIC')]),
 presentation('INCHEON',cams[1],[event('landing','INCHEON',85)],
 [label('incheon','인천상륙작전','INCHEON','landing',85,150,pin='CONTEXT',pop=True),label('landing-date','1950.09.15','INCHEON','landing',110,150,'NUMERIC')]),
 presentation('ADVANCE',cams[2],[event('landing','INCHEON',0,20),event('advance','DIRECTION_LABEL',30,110),event('capital','SEOUL',100)],
 [label('incheon','인천상륙작전','INCHEON','landing',0,20,pin='CONTEXT'),label('landing-date','1950.09.15','INCHEON','landing',0,20,'NUMERIC'),label('advance-direction','진격 방향(개략)','DIRECTION_LABEL','advance',30,110,pop=True),label('seoul','서울','SEOUL','capital',100,150,pin='CONTEXT',pop=True)],[25,150]),
 presentation('SEOUL',cams[3],[event('capital','SEOUL')],
 [label('seoul','서울','SEOUL','capital',0,18,pin='CONTEXT'),label('recapture','서울 수복','SEOUL','capital',18,150,pin='CONTEXT',pop=True),label('recapture-date','1950.09.28','SEOUL','capital',50,150,'NUMERIC')],[0,150])]

for clip in range(2):
    rows=[]
    for index in range(2):
        n=clip*2+index;sid,dates,line=specs[n]
        rows.append({'sceneId':sid.lower(),'startFrame':index*150,'endFrame':(index+1)*150,'facts':facts(sid,dates,line,75 if n==2 else 18)})
    p=pres[clip*2].copy();p['transitions']=[{'type':'CUT','frame':150}];p['sceneOverrides']={specs[clip*2+1][0].lower():pres[clip*2+1]}
    p['initialStateVisibility']='PRESERVE_AREA_REVEAL_LINE'
    data={'schema':'WORLD_ENGINE_PRESENTATION_PROMPT_V2','prompt':'한국전쟁 사건 지도. 제공한 지리 자료와 사건 라벨을 사용하는 10초 30fps 영상이다. 카메라 위치와 이름표는 첨부한 장면 설정을 사용한다. 두 장면을 전환한다.',
      'data':{'schema':'WORLD_ENGINE_DATA_PROMPT_V1','topic':'한국전쟁 사건 지도','simulationType':'GENERAL','durationSeconds':10,'fps':30,'resolution':{'width':1080,'height':1920},'scenes':rows},'region':region,'presentation':p}
    write(f'KOREAN_WAR_20S_PART_{clip+1:02d}.json',data)

write('STORYBOARD.json',{'schema':'WORLD_ENGINE_TWO_CLIP_STORYBOARD_V1','durationSeconds':20,'fps':30,'totalFrames':600,'resolution':{'width':1080,'height':1920},'segments':[{'id':sid,'startFrame':i*150,'endFrame':(i+1)*150,'clip':i//2+1,'dateStart':dates[0],'dateEnd':dates[1],'geographicLineMeaning':'Land context outline' if line=='LAND_OUTLINE' else 'Abstract city-to-city campaign direction, not a troop route'} for i,(sid,dates,line) in enumerate(specs)],'authorizedFallbacks':['No precise September front or occupation fill','No unverified sea approach or landing-beach point','Named city/event pins and captioned approximate campaign direction'],'modernNativeBordersSuppressed':True,'historicalOwnershipClaimed':False,'audioIncluded':False,'gpuApproved':False,'qualityApproved':False})
print(json.dumps({'inputs':2,'frames':600,'sourceSharedEdgesRemoved':shared,'landRings':len(rings),'historicalControlCreated':False}))
