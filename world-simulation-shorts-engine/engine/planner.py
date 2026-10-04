"""Offline, inspectable causal planner for supported aviation/shipping/geographic scenarios.

This is deliberately a capability-bounded domain planner, not an unconstrained language
model that invents factual claims, geographic coordinates or nonexistent plugins.
An optional external planner can implement the same contract, but still passes gates.
"""
from copy import deepcopy
from datetime import datetime,date,timezone
import math,re
from .gis import LOCATIONS,resolve_location,mentioned_locations,RouteEngine,great_circle_distance,coordinate_source_report,UnknownLocation
from .presets import CAMERA_PRESETS,camera_state,choose_lighting
from .plugins import UnsupportedVisualRequirement,require_plugins

UNSUPPORTED_PATTERNS={
 'LAND_ROUTING':r'자동차|육로|차량|차로\s*이동|\bland\s+route\b|\broad\s+trip\b|\btruck\b|\bvehicle\b',
 'GEOGRAPHY_MORPH':r'판게아|pangaea|대륙.{0,8}(이동|분리)|continental drift|섬.{0,8}(사라|제거)|island.{0,12}(remov|disappear)|해안선.{0,8}(변화|바뀌)',
 'TIME_MORPH':r'판게아|pangaea|빙하기|ice age',
 'TERRITORY_TIMELINE':r'제국|empire|국경.{0,8}(변화|바뀌)|영토.{0,8}(확장|변화)|territory change',
 'WAR_VFX':r'미사일|missile|전투기|fighter|전쟁|war\b|폭발|explosion|함대|fleet|탱크|tank\b',
 'WEATHER':r'태풍|허리케인|hurricane|typhoon|storm',
 'DISASTER':r'쓰나미|tsunami|화산|volcano|지진|earthquake',
 'SPACE':r'위성.{0,6}(궤도|이동)|satellite|화성|mars\b',
 'ECONOMY':r'물가|인플레이션|주가|gdp|경제.{0,6}(예측|폭락)|가격.{0,6}(예측|상승)|predict.{0,8}prices'
}
SOUND_MAP={'city_reveal':'soft_pulse','country_reveal':'soft_impact','route_start':'digital_sweep','entity_departure':'pass_by','arrival':'soft_impact','new_variable':'subtle_impact','route_blocked':'low_impact','alternate_route_reveal':'transition_sweep','network_expand':'wide_riser','comparison_reveal':'digital_sweep','milestone_reveal':'soft_pulse','destination_preview':'soft_pulse','response':'transition_sweep','escalation':'wide_riser','peak_reveal':'cinematic_hit','final_reveal':'deep_final_hit','route_choice':'digital_sweep','distance_reveal':'soft_pulse','region_reveal':'soft_impact','connection_reveal':'digital_sweep','consequence_reveal':'soft_impact'}

class PlanningInputError(ValueError):
    code='UNSUPPORTED_INPUT'
    def __init__(self,message,details=None):self.details=details or {};super().__init__(message)
    def as_dict(self):return {'code':self.code,'message':str(self),**self.details}

def _style_profile(style):
    aliases={
        'tension':{'긴장감 있는 세계 시뮬레이션','시네마틱 세계 시뮬레이션','tension','cinematic world simulation'},
        'documentary':{'시네마틱 지리 다큐멘터리','documentary','cinematic geography documentary'},
        'travel':{'차분한 여행과 탐험','travel','calm travel and exploration'},
        'network':{'역동적인 국제 네트워크','network','dynamic international network'},
    }
    normalized=style.strip().casefold()
    for profile,names in aliases.items():
        if normalized in names:return profile
    raise PlanningInputError('현재는 긴장감 있는 시뮬레이션, 지리 다큐멘터리, 차분한 여행, 국제 네트워크 연출을 지원합니다.',{'code':'UNSUPPORTED_STYLE','supported_styles':[next(n for n in sorted(names) if any('\uac00'<=ch<='\ud7a3' for ch in n)) for names in aliases.values()]})

def _requires_historical_geography(text):
    # Modern dated flight topics remain modern GIS. An explicitly past map/state
    # needs a historical dataset; a contemporary globe cannot substitute for it.
    geographic_state=r'지도|국경|영토|지형|해안|국가.{0,5}(?:형태|경계)|\bmap\b|\bborders?\b|territor|geograph|coast'
    geography=geographic_state+r'|국가|세계|이동|경로'
    if re.search(r'기원전|\b(?:BCE|BC)\b',text,re.I):return True
    if re.search(r'(?:역사|고대|중세|과거|historical|ancient|medieval).{0,24}(?:'+geography+r')|(?:'+geography+r').{0,24}(?:역사|historical)',text,re.I):return True
    if not (re.search(geographic_state,text,re.I) or re.search(r'당시|시대|\bera\b|\bperiod\b',text,re.I)):return False
    today=datetime.now(timezone.utc).date()
    dates=[match.groups() for pattern in [r'(?<![A-Za-z0-9])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)',r'(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일'] for match in re.finditer(pattern,text)]
    month=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    for pattern,order in [(r'\b('+month+r')\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})\b',(2,0,1)),(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+('+month+r')[,]?\s+(\d{4})\b',(2,1,0))]:
        for match in re.finditer(pattern,text,re.I):
            values=match.groups();name=values[order[1]]
            dates.append((values[order[0]],datetime.strptime(name,'%b' if len(name)==3 else '%B').month,values[order[2]]))
    for parts in dates:
        try:
            if date(*map(int,parts))<today:return True
        except ValueError:pass
    quantity_unit=r'\s*(?:seconds?|minutes?|hours?|kilomet(?:er|re)s?|miles?|km\b|초|분|킬로미터)'
    patterns=[r'(?<!\d)(\d{1,4})\s*(?:년|AD\b|CE\b)',r'\b(?:year|dated)\s+(\d{1,4})\b',r'\b(?:in|during|as\s+of)\s+(\d{4})\b(?!'+quantity_unit+r')',r'(?<![A-Za-z0-9])(\d{4})\s*(?:world\s+map|map|border|territor|geograph|coast|지도|국경|영토|해안)']
    if any(int(match.group(1))<today.year for pattern in patterns for match in re.finditer(pattern,text,re.I)):return True
    for match in re.finditer(r'(?<![A-Za-z0-9])(\d{4})(?![A-Za-z0-9])',text):
        if re.search(r'(?:\bflight|편명|항공편)\s*(?:no\.?|number|#)?\s*$',text[max(0,match.start()-24):match.start()],re.I):continue
        if re.match(quantity_unit,text[match.end():],re.I):continue
        if int(match.group(1))<today.year:return True
    return False

def _request(raw):
    request=deepcopy(raw)
    topic=str(request.get('topic','')).strip()
    if not topic:raise PlanningInputError('주제를 입력하세요.')
    try:duration=float(request.get('duration',20))
    except (TypeError,ValueError):raise PlanningInputError('영상 길이는 초 단위 숫자여야 합니다.')
    if not math.isfinite(duration) or duration<20 or duration>3600:raise PlanningInputError('현재 길이 범위는 20~3600초입니다.')
    requested_duration=duration
    duration=round(duration*30)/30
    if abs(duration-requested_duration)>1e-9:request['original_duration']=requested_duration
    quality=str(request.get('quality','HIGH')).upper()
    if quality not in {'FAST','HIGH','CINEMA'}:raise PlanningInputError('품질은 FAST / HIGH / CINEMA 중 하나입니다.')
    request.update(topic=topic,duration=duration,quality=quality,style=str(request.get('style','시네마틱 세계 시뮬레이션')))
    request['style_profile']=_style_profile(request['style'])
    for key,default in [('tts',False),('subtitles',False),('bgm',True)]:
        value=request.get(key,default)
        if not isinstance(value,bool):raise PlanningInputError(f'{key} 값은 true/false여야 합니다.')
        request[key]=value
    return request

def _route(route_id,points,kind='great_circle',altitude=13.,**kwargs):
    return dict(route_id=route_id,kind=kind,points=deepcopy(points),altitude_km=altitude,source_ids=sorted({p['source_id'] for p in points}),color='#b9eeff',**kwargs)

def _validate_explicit_place_mentions(text):
    # Parse explicit Korean origin/stop/destination particles and English from/via/to.
    fragments=[]
    for m in re.finditer(r'([가-힣]{2,24})(?:에서|까지|으로|을\s*거치|를\s*거치|을\s*거쳐|를\s*거쳐|을\s*경유|를\s*경유)',text):fragments.append(m.group(1))
    for m in re.finditer(r'\b(?:from|via|to)\s+([A-Za-z][A-Za-z ]{1,35}?)(?=\s+(?:to|via|in|with|by|for)\b|[→,?.]|$)',text,re.I):fragments.append(m.group(1).strip())
    nonplaces={'비행기','항공기','선박','직항','경로','항로','네트워크','운하','희망봉','수에즈운하','가상','세계','해상','민간항공','시뮬레이션'}
    for fragment in fragments:
        if fragment in nonplaces:continue
        if not mentioned_locations(fragment):raise UnknownLocation(fragment)

def _scenario(request):
    text=request['topic'];missing=[name for name,pattern in UNSUPPORTED_PATTERNS.items() if re.search(pattern,text,re.I)]
    if _requires_historical_geography(text):missing.extend(['HISTORICAL_GIS','TIME_MORPH'])
    if missing:raise UnsupportedVisualRequirement(missing,'이 주제에 필요한 연출 모듈은 아직 설치되지 않았습니다.')
    if re.search(r'수에즈|suez|운하|canal|해상|물류|cargo ship|shipping|선박|배\s*항로',text,re.I):
        if not re.search(r'수에즈|suez',text,re.I):raise UnsupportedVisualRequirement(['SEA_ROUTING_CATALOG_EXTENSION'],'현재 검증된 해상 시나리오는 로테르담–싱가포르/수에즈·희망봉 경로입니다. 다른 해상경로는 GIS 자료를 추가해야 합니다.')
        destinations=mentioned_locations(text)
        allowed={'rotterdam','singapore','suez','cape_town'}
        if any(l['id'] not in allowed and l['kind']!='airport' for l in destinations):raise UnsupportedVisualRequirement(['SEA_ROUTING_CATALOG_EXTENSION'],'요청한 항구 연결은 검증된 해상 경로 목록에 없습니다.')
        locations=[resolve_location('ROTTERDAM_PORT'),resolve_location('SUEZ_CANAL'),resolve_location('SINGAPORE_PORT')]
        routes=[_route('R_SUEZ',RouteEngine.sea('ROTTERDAM_SINGAPORE_SUEZ'),'sea',.03,description='Verified maritime graph via Suez'),_route('R_CAPE',RouteEngine.sea('ROTTERDAM_SINGAPORE_CAPE'),'sea',.03,description='Hypothetical closure alternative via Cape')]
        for route in routes:
            route['points'][0]=deepcopy(locations[0]['coordinates']);route['points'][-1]=deepcopy(locations[-1]['coordinates'])
        return dict(domain='shipping',locations=locations,routes=routes,plugins=['SHIPPING','NETWORK','GEOGRAPHY'],conditional=True,bypass=False)
    _validate_explicit_place_mentions(text)
    locations=mentioned_locations(text)
    country_comparison=bool(re.search(r'비교|comparison|compare|국가.{0,6}위치|country.{0,6}locat',text,re.I)) and any(l['kind']=='country' for l in locations)
    if not country_comparison:locations=[l for l in locations if l['kind']!='country']
    # Explicit coordinate literals are never trusted as GIS records.
    if re.search(r'\b(?:lat|lon|latitude|longitude)\s*[:=]\s*[-\d]',text,re.I):raise PlanningInputError('좌표 직접 입력 대신 출처가 확인된 장소를 사용하세요.',{'code':'UNVERIFIED_GIS_COORDINATE'})
    if len(locations)<2:raise PlanningInputError('검증된 도시/공항 두 곳 이상을 입력하세요. 예: 런던 → 파리 → 로마.',{'code':'UNKNOWN_GIS_LOCATION','supported_examples':['런던 → 파리 → 로마','서울 → 도쿄 → 싱가포르','뉴욕 → 런던','수에즈 운하가 7일 막힌다면?']})
    if len(locations)>8:raise PlanningInputError('현재 한 기획의 명시적 핵심 장소는 8곳까지 지원합니다.')
    # Explicit arrow lists must not silently drop an unknown place in the middle.
    if '→' in text or '->' in text:
        segments=re.split(r'→|->',text)
        for segment in segments:
            if len(segment.strip()) and not mentioned_locations(segment):raise UnknownLocation(segment.strip())
    conditional=bool(re.search(r'만약|가상|hypothetical|what if|if\b|시뮬레이션|simulation',text,re.I))
    bypass=bool(re.search(r'거치지|경유하지|직항|direct|bypass',text,re.I)) and len(locations)>=3
    pairs=list(zip(locations,locations[1:]))
    if bypass:pairs.append((locations[0],locations[-1]))
    routes=[_route(f'R_{index+1:02}',[a['coordinates'],b['coordinates']],length_km=round(great_circle_distance(a,b),2),description=f"{a['name']} → {b['name']}") for index,(a,b) in enumerate(pairs)]
    return dict(domain='comparison' if country_comparison else 'geography' if bypass else 'aviation',locations=locations,routes=routes,plugins=['NETWORK','GEOGRAPHY'] if country_comparison else ['AVIATION','NETWORK','GEOGRAPHY'],conditional=conditional or bypass,bypass=bypass)

def _claims(scenario,request):
    locs=scenario['locations'];claims=[]
    for i,loc in enumerate(locs):
        claims.append(dict(id=f'F{i+1:02}',text=f"{loc['name']}의 위치는 공개 GIS 원본 좌표로 확인됩니다.",status='FACT',source_ids=[loc['coordinates']['source_id']],scope='coordinate provenance'))
    if scenario['domain']=='shipping':
        match=re.search(r'(\d+)\s*(?:일|days?)',request['topic'],re.I);days=int(match.group(1)) if match else 7
        assumption=f'수에즈 경로가 {days}일 동안 차단된다고 가정합니다. 실제 폐쇄나 미래 예측이 아닙니다.'
        result='폐쇄 가정 아래 검증된 해상 그래프에서 수에즈를 제외한 희망봉 우회 경로를 비교합니다. 실제 선박 선택·가격·지연을 예측하지 않습니다.'
    elif scenario['domain']=='comparison':
        assumption='입력한 국가 간 연결은 위치 비교를 위한 시각적 가정입니다. 실제 이동이나 물류 규모가 아닙니다.'
        result='공개 GIS의 국가 라벨 좌표와 실제 국가 형태를 비교하여 위치 관계를 시각화합니다.'
    else:
        assumption='입력한 도시 연결과 화면의 이동 시간은 시각화를 위한 가정입니다. 실제 항공편 일정이나 성능 예측이 아닙니다.'
        result='검증된 위치를 연결하는 구면 경로의 공간적 차이와 연결망을 시각화합니다.'
    for index,route in enumerate(scenario['routes']):
        distance=route.get('length_km',sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:])))
        claims.append(dict(id=f'FD{index+1:02}',text=f'공개 좌표로 계산한 경로의 구면 길이는 약 {distance:,.0f} km입니다. 실제 항공편/항해 시간은 계산하지 않습니다.',status='FACT',source_ids=route['source_ids'],scope='derived geometric length; spherical Earth radius 6371.0088 km'))
    claims.append(dict(id='A01',text=assumption,status='ASSUMPTION',source_ids=[],scope='scenario premise'))
    claims.append(dict(id='M01',text=result,status='SIMULATION',source_ids=sorted({p['source_id'] for r in scenario['routes'] for p in r['points']}),assumption_ids=['A01'],scope='visualization only'))
    return claims

def _event_schedule(duration,scenario):
    # 1.3 / 1.8 second opening changes, then 2.15 second new information.
    times=[.6,1.3,2.4];t=4.5
    while t<duration-1.25:times.append(round(t,6));t+=2.15
    times.append(round(duration-.65,6));times=sorted(set(times))
    kinds=['city_reveal','route_start','destination_preview','entity_departure','country_reveal','distance_reveal','arrival','new_variable','alternate_route_reveal','network_expand','connection_reveal','milestone_reveal','region_reveal','response','comparison_reveal','escalation','route_choice','consequence_reveal']
    result=[]
    for i,time in enumerate(times):
        q=time/duration;loc=scenario['locations'][min(len(scenario['locations'])-1,int(q*len(scenario['locations'])))];kind=kinds[i%len(kinds)]
        role='cause' if i<3 else 'progression'
        if i==2:role='hint';loc=scenario['locations'][min(1,len(scenario['locations'])-1)]
        if .38<=q<=.52 and not any(e['role']=='variable' for e in result):kind='new_variable';role='variable'
        if .56<=q<=.67 and not any(e['role']=='peak' for e in result):kind='peak_reveal';role='peak'
        if .85<=q<=.94 and duration>=70 and len([e for e in result if e['role']=='peak'])<2:kind='peak_reveal';role='peak'
        if i==len(times)-1:kind='final_reveal';role='payoff'
        if scenario['domain']=='shipping':
            if role=='variable':kind='route_blocked'
            elif kind=='arrival' and q<.72:kind='region_reveal'
            elif kind=='entity_departure' and q>.4:kind='response'
        # No city-arrival claim until the route's actual endpoint progress is reached.
        if kind=='arrival' and q<.78:kind='destination_preview'
        if scenario['domain']=='comparison' and kind in {'entity_departure','arrival'}:kind='connection_reveal'
        descriptions={
          'city_reveal':f"{loc['name']}의 확인된 위치 공개",'destination_preview':f"다음 연결점 {loc['name']} 공개",'route_start':'연결 경로 선택 공개',
          'entity_departure':'가상 이동체 출발', 'country_reveal':f"{loc.get('country',loc['name'])}의 위치 관계 공개",'distance_reveal':'검증 좌표에서 계산한 구면 거리 공개',
          'new_variable':'다음 연결/대안이라는 새 변수 공개','route_blocked':'수에즈 폐쇄 가정 적용','alternate_route_reveal':'검증된 대안 항로 공개',
          'network_expand':'연결망 범위 확대','connection_reveal':'새 연결 관계 공개','milestone_reveal':'경로 진행과 공간 범위 비교','region_reveal':'다음 지역의 위치 공개',
          'response':'가정에 대한 대안 선택','comparison_reveal':'원래 경로와 대안 비교','escalation':'전체 연결망의 범위 확대','route_choice':'다음 연결 방향 선택',
          'consequence_reveal':'가정에 따른 경로 차이 공개','peak_reveal':'주요 연결과 전체 공간 관계 동시 공개','arrival':f"{loc['name']} 도착",'final_reveal':'전체 연결 구조와 가정의 한계 공개'}
        display={'route_start':'THE JOURNEY BEGINS','entity_departure':'IN FLIGHT' if scenario['domain']!='shipping' else 'UNDER WAY','new_variable':'ANOTHER WAY FORWARD','alternate_route_reveal':'AN ALTERNATE ROUTE','network_expand':'A CONNECTED WORLD','connection_reveal':'NEW CONNECTIONS','response':'A DIFFERENT WAY','comparison_reveal':'TWO POSSIBLE ROUTES','escalation':'BEYOND THE FIRST ROUTE','route_choice':'WHERE NEXT?','consequence_reveal':'THE ROUTE CHANGES','peak_reveal':'ONE WORLD · MANY CONNECTIONS','final_reveal':'A MORE CONNECTED WORLD'}.get(kind,loc['name'].upper())
        value=None;unit=''
        if kind in {'distance_reveal','milestone_reveal','comparison_reveal','consequence_reveal'}:
            route=scenario['routes'][min(len(scenario['routes'])-1,int(q*len(scenario['routes'])))];value=round(route.get('length_km',sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))));unit='km';display=f'{value:,} km'
        elif kind in {'city_reveal','destination_preview','arrival','region_reveal'}:display=loc['name'].upper()
        elif kind=='country_reveal':display=loc.get('country',loc['name']).upper()
        elif kind=='new_variable':display='AN ALTERNATE CONNECTION'
        elif kind=='route_blocked':display='ASSUMPTION · SUEZ CLOSED'
        elif kind=='final_reveal':display='CONNECTIONS REVEALED'
        eid=f'E{i+1:03}';result.append(dict(id=eid,kind=kind,time=time,duration=.7,target_id=loc['id'],role=role,caused_by=result[-1]['id'] if result else None,meaningful=True,description=descriptions[kind],text=display,value=value,unit=unit,coordinates=deepcopy(loc['coordinates']),claim_id=('A01' if kind=='route_blocked' else f'FD{min(len(scenario["routes"])-1,int(q*len(scenario["routes"])))+1:02}' if kind in {'distance_reveal','milestone_reveal','comparison_reveal','consequence_reveal'} else f'F{scenario["locations"].index(loc)+1:02}' if kind in {'city_reveal','country_reveal','region_reveal','destination_preview'} and loc in scenario['locations'] else 'M01')))
    return result


def _bind_events_to_geometry(events,scenario,route_specs,duration,bounds):
    """Bind event meanings to the actual route clock; never recount an old departure.

    Coincident arrival/onward-start primitives form one semantic event. The arrival
    detail remains rendered and sounded, with meaningful=False to avoid double
    counting the same focal moment. Distance milestones depend on the real sampled
    curve progress, not an arbitrary claim that another aircraft just took off.
    """
    main=[item for item in route_specs if not item[0]['route_id'].startswith('N_')]
    networks=[item for item in route_specs if item[0]['route_id'].startswith('N_')]
    def progress(item,t):
        route,start,end=item
        index=next((i for i in range(len(bounds)-1) if bounds[i]<=t<bounds[i+1]),len(bounds)-2)
        scene_start,scene_end=bounds[index:index+2];d=scene_end-scene_start
        p0=max(0.,min(1.,(scene_start-start)/(end-start)));p1=max(0.,min(1.,(scene_end-start)/(end-start)))
        local_start=max(0.,start-scene_start);local_end=min(d,max(0.,end-scene_start))
        if local_end<=local_start:local_start,local_end=0.,d
        u=max(0.,min(1.,(t-scene_start-local_start)/max(.001,local_end-local_start)));u=u*u*(3-2*u)
        v=p0+(p1-p0)*u
        return v*.40194431692212046 if scenario['domain']=='shipping' and route['route_id']=='R_SUEZ' else v
    def active(t):
        live=[item for item in main if item[1]<=t<item[2]]
        return live[-1] if live else min(main,key=lambda item:min(abs(t-item[1]),abs(t-item[2])))
    def location(point):
        return resolve_location(point['location_id']) if point.get('location_id') else None
    def display_location(loc):
        return loc['id'][8:].upper() if loc and loc.get('kind')=='airport' else loc['name'] if loc else 'DESTINATION'
    def location_fact_id(loc):
        # A route endpoint may differ from the scheduler's next location. Keep
        # its provenance claim bound to the same verified place as its graphics.
        index=next((i for i,known in enumerate(scenario['locations']) if known['id']==loc['id']),None)
        if index is None:raise PlanningInputError('목적지의 위치 FACT가 기획에 없습니다.',{'code':'UNBOUND_GEOGRAPHIC_FACT','location_id':loc['id']})
        return f'F{index+1:02}'
    def distance(item):
        route=item[0]
        return route.get('length_km',sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:])))
    def milestone(event,item):
        route=item[0];t=event['time'];p=progress(item,t);length=distance(item);remaining=max(0,length*(1-p))
        event.update(kind='milestone_reveal',target_id=route['route_id'],coordinates=deepcopy(route['points'][-1]),text=f'{remaining:,.0f} km REMAINING',value=round(remaining),unit='km',claim_id='M01',description='실제 렌더 경로 진행률에서 계산한 남은 구면 거리; 압축된 이동 시간은 가정')
    bound=[]
    for original in events:
        event=deepcopy(original);t=event['time'];item=active(t);route,start,end=item;kind=event['kind']
        if kind=='route_start':
            exact=next((r for r in main if abs(r[1]-t)<=.04),None)
            if exact:
                r=exact[0];a=location(r['points'][0]);b=location(r['points'][-1]);event.update(target_id=r['route_id'],coordinates=deepcopy(r['points'][0]),text=f'{display_location(a)} → {display_location(b)}',claim_id='M01')
            else:milestone(event,item)
        elif kind=='entity_departure':
            milestone(event,item)
        elif kind=='arrival':
            if abs(t-end)>.04:event.update(kind='city_reveal',text=event.get('coordinates',{}).get('location_id',event['text']).replace('_',' ').upper())
        elif kind=='alternate_route_reveal':
            if scenario['domain']=='shipping' or scenario['bypass']:
                alternative=main[-1]
                if abs(event['time']-alternative[1])<=.7:event.update(time=round(alternative[1]+.08,6),target_id=alternative[0]['route_id'],coordinates=deepcopy(alternative[0]['points'][0]),text='AN ALTERNATE ROUTE',claim_id='M01')
                else:milestone(event,item)
            else:milestone(event,item)
        elif kind=='network_expand':
            if networks:
                fresh=min(networks,key=lambda r:abs(r[1]+.08-t))
                if abs(fresh[1]+.08-t)<=.7:event.update(time=round(fresh[1]+.08,6),target_id=fresh[0]['route_id'],coordinates=deepcopy(fresh[0]['points'][-1]),text='NEW CONNECTIONS',claim_id='M01')
                else:milestone(event,item)
            else:
                event.update(kind='comparison_reveal',target_id=main[-1][0]['route_id'],text=f'{distance(main[0]):,.0f} / {distance(main[-1]):,.0f} km',claim_id='M01')
        elif kind in {'response','route_choice','escalation'} and scenario['domain'] not in {'shipping','geography'}:
            milestone(event,item)
        elif kind=='destination_preview':
            destination=location(route['points'][-1])
            if destination:event.update(target_id=destination['id'],coordinates=deepcopy(destination['coordinates']),text=display_location(destination).upper(),claim_id=location_fact_id(destination),description=f"다음 연결점 {destination['name']} 공개")
        if event['role']=='variable' and scenario['domain']=='aviation':
            next_leg=next((r for r in main if r[1]>=t-.04 and r is not main[0]),main[-1]);destination=location(next_leg[0]['points'][-1])
            if destination:event.update(kind='new_variable',target_id=destination['id'],coordinates=deepcopy(destination['coordinates']),text='NEXT · '+display_location(destination).upper(),claim_id='M01')
        if event['role']=='peak' and scenario['domain']=='aviation':
            event.update(target_id=route['route_id'],coordinates=deepcopy(route['points'][-1]),text=f'{max(0,distance(item)*(1-progress(item,t))):,.0f} km TO THE NEXT CITY',claim_id='M01')
        bound.append(event)
    def append(kind,time,coord,target,text,meaningful=True):
        bound.append(dict(id='pending',kind=kind,time=round(time,6),duration=.7,target_id=target,role='progression',caused_by=None,meaningful=meaningful,description=text,text=text,coordinates=deepcopy(coord),claim_id='M01'))
    # First path starts before the aircraft appears; both are actual first-three-second changes.
    first=main[0];first_type='ship_reference' if scenario['domain']=='shipping' else 'aircraft_'+first[0]['route_id']
    if scenario['domain']!='comparison':append('entity_departure',first[1]+.2,first[0]['points'][0],first_type,'UNDER WAY' if scenario['domain']=='shipping' else 'DEPARTURE')
    for index,item in enumerate(main):
        route,start,end=item
        if index:
            if not any(e['kind']=='route_start' and e['target_id']==route['route_id'] and abs(e['time']-start)<.04 for e in bound):
                append('route_start',start,route['points'][0],route['route_id'],'THE NEXT CONNECTION' if scenario['domain']!='shipping' else 'THE CAPE ALTERNATIVE')
        # Actual endpoint / canal stop, not the generic scheduler's early arrival.
        arrival_coord=route['points'][-1]
        if scenario['domain']=='shipping' and route['route_id']=='R_SUEZ':arrival_coord=resolve_location('SUEZ_CANAL')['coordinates']
        arrival_location=location(arrival_coord)
        target=arrival_location['id'] if arrival_location else route['route_id'];text=display_location(arrival_location).upper()
        same_start=any(abs(end-other[1])<.04 for other in main if other is not item)
        append('connection_reveal' if scenario['domain']=='comparison' else 'arrival',end,arrival_coord,target,text,meaningful=not same_start)
    # Render one network activation at the final mid-story branch; it is a new sourced connection.
    if networks:
        middle=[r for r in networks if r[1]<duration*.75]
        if middle:
            item=middle[-1];t=item[1]+.08
            nearest=min((e for e in bound if e['kind']=='destination_preview' and e['time']>3),key=lambda e:abs(e['time']-t),default=None)
            if nearest and abs(nearest['time']-t)<=.7:
                nearest.update(kind='network_expand',time=round(t,6),target_id=item[0]['route_id'],coordinates=deepcopy(item[0]['points'][-1]),text='NEW CONNECTIONS',claim_id='M01')
    unique={}
    for event in bound:
        physical_key=(event['kind'],event['target_id'],round(event['time']*30))
        if event['kind'] in {'route_start','entity_departure','arrival','network_expand'} and physical_key in unique:continue
        unique[physical_key if event['kind'] in {'route_start','entity_departure','arrival','network_expand'} else (event['kind'],event['target_id'],event['time'],len(unique))]=event
    bound=list(unique.values())
    bound.sort(key=lambda event:(event['time'],event['kind']=='route_start'))
    for index,event in enumerate(bound):
        event['id']=f'E{index+1:03}';event['caused_by']=bound[index-1]['id'] if index else None
    # Decorative coincident-arrival ancestors must not be required by a semantic gate.
    previous=None
    for event in bound:
        event['caused_by']=previous
        if event.get('meaningful',True):previous=event['id']
    return bound

def _scene_role(q,last=False):
    if last:return ('FINAL_OVERVIEW','FINAL_REVEAL','FINAL_REVEAL','payoff')
    if q<.1:return ('EARTH_ESTABLISH','FAST_HOOK_DIVE','HOOK_REVEAL','hook')
    if q<.23:return ('CITY_FOCUS','CITY_APPROACH','CITY_REVEAL','orientation')
    if q<.4:return ('ROUTE_CHASE','ROUTE_CHASE','ROUTE_CHASE','progression')
    if q<.53:return ('COMPARISON','NETWORK_EXPANSION','NEW_VARIABLE','variable')
    if q<.7:return ('NETWORK','EARTH_ORBIT','PEAK_MOMENT','peak')
    if q<.85:return ('ROUTE_CHASE','HORIZON_REVEAL','ESCALATION','progression')
    return ('NETWORK','NETWORK_EXPANSION','NETWORK_EXPANSION','peak')


def _topic_hook(scenario,request):
    def short(location):
        if location['kind']=='airport':return location['id'][8:].upper()
        matched=[a for a in location.get('aliases',[]) if a in request['topic'] and any('\uac00'<=ch<='\ud7a3' for ch in a)]
        return min(matched,key=len) if matched else location['name']
    if scenario['domain']=='shipping':
        match=re.search(r'(\d+)\s*(?:일|days?)',request['topic'],re.I);days=int(match.group(1)) if match else 7
        return f'수에즈가 {days}일 막힌다면?'
    if scenario['domain']=='comparison':return f'{short(scenario["locations"][0])}와 {short(scenario["locations"][-1])}, 어디에 있을까요?'
    if scenario['bypass']:return f'{short(scenario["locations"][1])}를 거치지 않는다면?'
    names=[short(location) for location in scenario['locations']]
    return ' → '.join(names)+' · 하나의 여정?'

def _narration(role,location,domain,conditional,duration=None):
    if role=='hook':return '이 연결이 바뀌면, 어디로 향할까요?'
    # These concise defaults have actual offline ko155 measurements with room
    # for placement and punctuation. Never alter speech speed to force a fit.
    # Long-scene scripts retain their established wording; real synthesis still
    # has to pass the audio pipeline's independent duration guard.
    if duration is not None and duration<=4.2:
        compact={'variable':'다음 연결은 어떻게 달라질까요?','payoff':'새로운 연결이 보입니다.'}
        if duration<=3.6:compact.update(orientation='다음 위치를 확인합니다.',progression='다음 연결로 향합니다.',peak='전체 연결이 드러납니다.')
        if role in compact:return compact[role]
    return {'orientation':f"{location['name']}의 위치를 확인합니다.",'progression':'곡선을 따라 다음 연결점으로 향합니다.','variable':'다른 연결을 선택하면 어떻게 달라질까요?','peak':'연결망의 전체 구조가 드러납니다.','payoff':'같은 지구 위에서, 새로운 연결이 보입니다.'}.get(role,'다음 연결을 확인합니다.')

def _shipping_narration(start,end,duration,scene_events,route_specs,request,previous=''):
    """Causal route-phase narration; scene clocks and real events select the beat.

    No trade, speed or delivery forecast is inferred. Distance differences are
    derived solely from the sourced maritime graph used by the renderer.
    """
    reference=next(item for item in route_specs if item[0]['route_id']=='R_SUEZ')
    alternative=next(item for item in route_specs if item[0]['route_id']=='R_CAPE')
    match=re.search(r'(\d+)\s*(?:일|days?)',request['topic'],re.I);days=int(match.group(1)) if match else 7
    def length(route):return sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]))
    difference=round(length(alternative[0])-length(reference[0]));mid=(start+end)/2
    kinds={event['kind'] for event in scene_events};stage='start'
    if end>=duration-1e-6:stage='scope'
    elif 'route_blocked' in kinds:stage='closure'
    elif any(event['kind']=='arrival' and event['target_id']==alternative[0]['points'][-1].get('location_id') for event in scene_events) or mid>=alternative[1]+.82*(alternative[2]-alternative[1]):stage='destination'
    elif mid>=alternative[1]:
        progress=(mid-alternative[1])/(alternative[2]-alternative[1])
        stage='alternative' if progress<.32 or '가정합니다' in previous or '갈 길' in previous else 'comparison' if progress<.60 else 'same_earth'
    elif mid>=reference[2]:stage='route_choice'
    elif mid<reference[2]*.55:stage='start'
    elif mid<reference[2]*.78:stage='approach'
    else:stage='usual_connection'
    choices={
        'start':['로테르담을 떠나, 수에즈로 향합니다.','여정은 로테르담에서 시작됩니다.','먼저 수에즈로 가는 항로를 따라갑니다.'],
        'approach':['배는 운하를 향해 다가갑니다.','진행할수록 수에즈가 가까워집니다.','다음 통과 지점은 수에즈입니다.'],
        'usual_connection':['운하를 지나면 싱가포르로 연결됩니다.','수에즈는 이 여정의 통과 지점입니다.','기존 경로는 수에즈를 거쳐갑니다.'],
        'closure':[f'운하가 {days}일 막힌다고 가정합니다.',f'{days}일 동안의 폐쇄를 가정합니다.'],
        'route_choice':['운하를 피해 갈 길을 찾습니다.','다른 항로가 필요한 상황입니다.'],
        'alternative':['이제 희망봉 쪽으로 우회합니다.','운하를 피해, 다른 길을 선택합니다.','여정은 아프리카 남쪽을 돌아갑니다.'],
        'comparison':[f'우회 경로는 약 {difference:,}킬로미터 더 깁니다.','두 항로의 길이를 나란히 비교합니다.','원래 길과 우회 길의 차이가 드러납니다.'],
        'same_earth':['같은 두 도시지만, 이어지는 길은 다릅니다.','출발지와 도착지는 그대로입니다.','연결점은 같아도, 항로는 달라집니다.'],
        'destination':['우회한 배는 싱가포르로 다가갑니다.','여정은 다시 싱가포르를 향합니다.','긴 우회 끝에 도착지가 가까워집니다.'],
        'scope':['이것은 경로 비교이며, 실제 배송 지연 예측은 아닙니다.','비교한 것은 항로입니다. 실제 배송 일정은 예측하지 않습니다.'],
    }
    compact={
        'start':['수에즈로 향하는 여정입니다.','로테르담에서 출발합니다.'],
        'approach':['운하가 가까워집니다.','다음 지점은 수에즈입니다.'],
        'usual_connection':['싱가포르로 이어지는 길입니다.','수에즈를 거쳐가는 항로입니다.'],
        'closure':[f'{days}일 폐쇄를 가정합니다.',f'{days}일간 막힌다고 가정합니다.'],
        'route_choice':['다른 길을 선택해야 합니다.','우회할 항로를 찾습니다.'],
        'alternative':['희망봉으로 우회합니다.','다른 길을 선택합니다.'],
        'comparison':['두 항로의 길이를 비교합니다.','우회한 길이 더 깁니다.'],
        'same_earth':['같은 도시, 다른 항로입니다.','연결점은 그대로입니다.'],
        'destination':['싱가포르로 다가갑니다.','도착지가 가까워집니다.'],
        'scope':['배송 지연 예측은 아닙니다.','실제 배송 일정은 예측하지 않습니다.'],
    }
    budget=(end-start)*.9
    return next((line for line in choices[stage]+compact[stage] if line!=previous and len(line.replace(' ',''))/5.8<=budget),'폐쇄를 가정합니다.' if stage=='closure' else compact[stage][-1])

def replace_geographic_event_with_milestone(scene,event):
    """Replace an invisible place reveal with new, sourced current-route information.

    This changes neither the event clock/cause nor the camera, route or entity.
    Progress is the exact SceneRoutes smoothstep over its authored local window;
    the number describes geometric distance left in this compressed simulation,
    never a real aircraft/vessel arrival forecast.
    """
    t=float(event['time']);route_by_id={route['route_id']:route for route in scene['routes']}
    eligible=[]
    for entity in scene['entities']:
        route=route_by_id.get(entity.get('route_id'))
        if not route or entity.get('action')=='stop' or route.get('faint') or route['progress_end']<=route['progress_start']:continue
        if not (entity['start_time']<=t<entity['end_time'] and route['start_time']<=t<route['end_time']):continue
        eligible.append(route)
    if not eligible:
        raise PlanningInputError('이 시점에는 남은 거리를 표시할 실제 이동 경로가 없습니다.',{'code':'UNSUPPORTED_VISUAL_REQUIREMENT','required_plugins':['VISIBLE_GEOGRAPHY_COMPOSITION'],'scene_id':scene['scene_id'],'event_id':event['id']})
    route=eligible[-1];u=max(0.,min(1.,(t-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
    p=route['progress_start']+(route['progress_end']-route['progress_start'])*u*u*(3-2*u)
    length=sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]));remaining=max(0.,length*(1-p))
    before={key:deepcopy(event.get(key)) for key in ('kind','target_id','coordinates','claim_id','text','value','unit')}
    event.update(kind='milestone_reveal',target_id=route['route_id'],coordinates=deepcopy(route['points'][-1]),text=f'{remaining:,.0f} km REMAINING',value=round(remaining),unit='km',claim_id='M01',description='현재 실제 렌더 경로 진행률에서 계산한 남은 구면 거리; 압축된 이동 시간은 가정')
    return dict(scene_id=scene['scene_id'],event_id=event['id'],time=t,before=before,after={key:deepcopy(event.get(key)) for key in before},route_id=route['route_id'],progress=p,length_km=length,remaining_km=remaining,source_ids=route['source_ids'],method='SceneRoutes local smoothstep and sourced GIS angular-length geometry; no camera/route alteration')

def refresh_clock_dependent_route_information(scene,event):
    """Refresh only route metrics whose Scene clock/route state has been edited.

    A completed curve reports its sourced connection/total length. It does not
    retain a distance-to-arrival number from an earlier shot. Physical events and
    time-independent total-distance information are deliberately untouched.
    """
    kind=event.get('kind');text=str(event.get('text',''))
    if kind not in {'milestone_reveal','milestone'} and not (kind in {'peak_reveal','peak_moment'} and re.search(r'\bkm\s+(?:remaining|to\s+the\s+next\s+city)\b',text,re.I)):return None
    route=next((route for route in scene['routes'] if route['route_id']==event.get('target_id')),None)
    if not route:raise PlanningInputError('수정된 거리 정보의 출처 있는 경로를 찾을 수 없습니다.',{'code':'UNSUPPORTED_VISUAL_REQUIREMENT','required_plugins':['VERIFIED_ROUTE_METRIC'],'scene_id':scene['scene_id'],'event_id':event['id']})
    t=float(event['time']);u=max(0.,min(1.,(t-route['start_time'])/max(.001,route['end_time']-route['start_time'])))
    progress=route['progress_start']+(route['progress_end']-route['progress_start'])*u*u*(3-2*u)
    length=sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:]));remaining=max(0.,length*(1-progress))
    before={key:deepcopy(event.get(key)) for key in ('text','value','unit','description','claim_id','coordinates')}
    completed=progress>=1-1e-8
    if completed:
        endpoints=[]
        for point in (route['points'][0],route['points'][-1]):
            location=resolve_location(point['location_id']) if point.get('location_id') else None
            endpoints.append(location['name'].upper() if location else None)
        connection=' -> '.join(endpoints) if all(endpoints) else 'ROUTE COMPLETE'
        event.update(text=f'{connection} · {length:,.0f} km',value=round(length),unit='km',description='실제 렌더 경로가 완성된 시점의 연결과 출처 있는 전체 구면 거리; 운항 시간이나 배송 지연 예측이 아님')
    else:
        event.update(text=f'{remaining:,.0f} km REMAINING',value=round(remaining),unit='km',description='수정된 Scene 시각과 실제 렌더 경로 진행률에서 다시 계산한 남은 구면 거리; 압축된 이동 시간은 가정')
    event.update(claim_id='M01',coordinates=deepcopy(route['points'][-1]))
    return dict(scene_id=scene['scene_id'],event_id=event['id'],time=t,route_id=route['route_id'],progress=progress,completed=completed,length_km=length,remaining_km=remaining,source_ids=route['source_ids'],before=before,after={key:deepcopy(event.get(key)) for key in before},method='Exact edited SceneRoutes local smoothstep and sourced angular-length geometry')

def _replace_geographic_event_with_comparison(scene,event):
    # At a stopped reference / before the alternative departure, a distance
    # comparison is genuine new information; another departure is not occurring.
    routes=[route for route in scene['routes'] if not route.get('faint') and not route['route_id'].startswith('N_')]
    if len(routes)<2:raise PlanningInputError('비교할 출처 있는 두 경로가 없습니다.')
    lengths=[sum(great_circle_distance(a,b) for a,b in zip(route['points'],route['points'][1:])) for route in routes[:2]]
    before={key:deepcopy(event.get(key)) for key in ('kind','target_id','coordinates','claim_id','text','value','unit')}
    event.update(kind='comparison_reveal',target_id=routes[1]['route_id'],coordinates=deepcopy(routes[1]['points'][-1]),text=f'{lengths[0]:,.0f} / {lengths[1]:,.0f} km',value=None,unit='km',claim_id='M01',description='같은 출발지와 도착지를 잇는 검증된 두 경로의 구면 길이 비교; 운항 시간이나 배송 지연 예측이 아님')
    return dict(scene_id=scene['scene_id'],event_id=event['id'],time=event['time'],before=before,after={key:deepcopy(event.get(key)) for key in before},route_ids=[route['route_id'] for route in routes[:2]],lengths_km=lengths,source_ids=sorted({sid for route in routes[:2] for sid in route['source_ids']}),method='Actual sourced waypoint-length comparison before alternative departure; no invented motion')

def _fit_physical_event_cameras(plan,certificate):
    """Widen only real arrival/barrier framing, preserving shared geographic poses.

    Physical events cannot be replaced by text. A small bounded pull-back keeps
    the real point visible, also bracketing the supported20% speed edit at Suez.
    Projection/occlusion are measured by the unchanged Three renderer, not guessed.
    """
    from .visibility import certify_semantic_visibility
    scenes=plan['scenes'];indices={scene['scene_id']:i for i,scene in enumerate(scenes)}
    protected=[scene['scene_id'] for scene in scenes if any(event['kind'] in {'arrival','route_blocked'} and event.get('target_id')=='SUEZ_CANAL' for event in scene['visual_events'])]
    def problematic(report):
        result=set()
        for failure in report.get('failures',[]):
            if failure.get('code') not in {'GEOGRAPHIC_EVENT_NOT_VISIBLE','MEANINGFUL_EVENT_NOT_ELIGIBLE','MEANINGFUL_EVENT_ELIGIBLE_LATE','MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY'}:continue
            scene=next((scene for scene in scenes if scene['scene_id']==failure.get('scene_id')),None)
            event=next((event for event in scene['visual_events'] if event['id']==failure.get('event_id')),None) if scene else None
            if event and event['kind'] in {'arrival','route_blocked'}:result.add(scene['scene_id'])
        return result
    changes=[]
    for _ in range(4):
        failed=problematic(certificate)
        if protected:
            probe=deepcopy(plan)
            for scene in probe['scenes']:
                if scene['scene_id'] in protected:scene['camera_speed']=min(3.,scene['camera_speed']*1.2)
            failed|=problematic(certify_semantic_visibility(probe,scene_ids=protected))
        if not failed:break
        boundaries={boundary for sid in failed for boundary in (indices[sid],indices[sid]+1)}
        changed=False
        for boundary in sorted(boundaries):
            pose=scenes[boundary-1]['camera_end'] if boundary else scenes[0]['camera_start'];old=pose['height'];new=min(6.,old*1.25)
            if abs(new-old)<1e-8:continue
            updated={**deepcopy(pose),'height':new}
            if boundary:
                scenes[boundary-1]['camera_end']=deepcopy(updated);scenes[boundary-1]['exit_state']['camera']=deepcopy(updated)
            if boundary<len(scenes):
                scenes[boundary]['camera_start']=deepcopy(updated);scenes[boundary]['entry_state']['camera']=deepcopy(updated)
            changes.append(dict(boundary_index=boundary,before_height=old,after_height=new,required_by_scenes=sorted(failed),method='Bounded camera pull-back certified by actual30fps geographic primitive eligibility; Suez physical focus includes20% speed envelope'))
            changed=True
        if not changed:break
        certificate=certify_semantic_visibility(plan)
    if changes:plan['metadata']['physical_event_framing_repairs']=changes
    return certificate

def _certify_planned_events(plan,repair=True):
    """Certify real draw eligibility before approval; final pixel QC still applies."""
    from .visibility import certify_semantic_visibility
    certificate=certify_semantic_visibility(plan);repairs=[]
    scenes={scene['scene_id']:scene for scene in plan['scenes']}
    if repair:
        certificate=_fit_physical_event_cameras(plan,certificate)
        for failure in certificate.get('failures',[]):
            if failure.get('code') not in {'GEOGRAPHIC_EVENT_NOT_VISIBLE','MEANINGFUL_EVENT_ELIGIBLE_LATE','MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY'}:continue
            scene=scenes.get(failure.get('scene_id'));event=next((event for event in scene['visual_events'] if event['id']==failure.get('event_id')),None) if scene else None
            if not event or event['kind'] not in {'city_reveal','country_reveal','region_reveal','destination_preview'}:continue
            try:
                try:repair_record=replace_geographic_event_with_milestone(scene,event)
                except PlanningInputError:repair_record=_replace_geographic_event_with_comparison(scene,event)
                repairs.append(repair_record)
                for sound in scene['sound_events']:
                    if sound.get('visual_event_id')==event['id']:sound['kind']=SOUND_MAP[event['kind']]
            except PlanningInputError:continue
        if repairs:certificate=certify_semantic_visibility(plan)
        network_timing=[]
        observed={row['event_id']:row for row in certificate.get('events',[])}
        for failure in certificate.get('failures',[]):
            if failure.get('code')!='MEANINGFUL_EVENT_ELIGIBLE_LATE':continue
            scene=scenes.get(failure.get('scene_id'));event=next((event for event in scene['visual_events'] if event['id']==failure.get('event_id')),None) if scene else None
            row=observed.get(failure.get('event_id'),{})
            if not event or event['kind']!='network_expand' or 'network' not in row.get('eligible_primitives',[]):continue
            timestamp=row.get('first_eligible_local_time')
            if timestamp is None:continue
            network_timing.append(dict(scene_id=scene['scene_id'],event_id=event['id'],before_time=event['time'],after_time=timestamp,reason='New network becomes physically visible at this actual camera/route onset; unseen progress is not counted as a visible event'))
            event['time']=timestamp
            for sound in scene['sound_events']:
                if sound.get('visual_event_id')==event['id']:sound['time']=timestamp
        if network_timing:
            certificate=certify_semantic_visibility(plan)
            plan['metadata']['semantic_network_timing_repairs']=network_timing
        # The information layer has one focal caption at a time. A preceding
        # caption's minimum hold can hide a payoff even with valid geometry.
        # Move only that preceding informational onset and its SFX by the measured
        # conflict plus one frame; physical starts/arrivals keep their true clock.
        observed={row['event_id']:row for row in certificate.get('events',[])}
        informational={'distance_reveal','comparison_reveal','milestone_reveal','consequence_reveal','route_choice','new_variable','response','escalation','peak_reveal','final_reveal','destination_preview','alternate_route_reveal','connection_reveal'}
        timing_repairs=[]
        for failure in certificate.get('failures',[]):
            if failure.get('code')!='MEANINGFUL_EVENT_ELIGIBLE_LATE' or 'information' not in observed.get(failure.get('event_id'),{}).get('eligible_primitives',[]):continue
            scene=scenes.get(failure.get('scene_id'));event=next((item for item in scene['visual_events'] if item['id']==failure.get('event_id')),None) if scene else None
            if not event:continue
            previous=[item for item in scene['visual_events'] if item['kind'] in informational and item['time']<event['time'] and item['time']+max(1.35,item.get('duration',.7))>event['time']]
            if not previous:continue
            prior=max(previous,key=lambda item:item['time']);shift=max(0.,failure['latency_seconds']-failure['allowed_seconds'])+1/30
            new_time=round(prior['time']-shift,6)
            preceding=max((item['time'] for item in scene['visual_events'] if item['time']<prior['time']),default=-.1)
            if new_time<=max(0.,preceding+.1):continue
            timing_repairs.append(dict(scene_id=scene['scene_id'],event_id=prior['id'],before_time=prior['time'],after_time=new_time,reason='Measured preceding information hold obscures the next scheduled reveal; exact paired SFX follows the corrected onset'))
            prior['time']=new_time
            metric=refresh_clock_dependent_route_information(scene,prior)
            if metric:timing_repairs[-1]['refreshed_route_metric']=metric
            for sound in scene['sound_events']:
                if sound.get('visual_event_id')==prior['id']:sound['time']=new_time
        if timing_repairs:
            certificate=certify_semantic_visibility(plan)
            plan['metadata']['semantic_information_timing_repairs']=timing_repairs
    plan.setdefault('metadata',{})['semantic_visibility']=certificate
    if repairs:plan['metadata']['semantic_visibility_repairs']=repairs
    return certificate

def generate_plan(raw):
    request=_request(raw);duration=request['duration'];scenario=_scenario(request);require_plugins(scenario['plugins'])
    locations=scenario['locations'];n=max(5,math.ceil(duration/7.5));total_frames=round(duration*30);bounds=[round(total_frames*i/n)/30 for i in range(n+1)];events=_event_schedule(duration,scenario)
    event_window_repairs=[]
    for event in events:
        if event['kind'] in {'route_start','entity_departure','arrival','route_blocked'}:continue
        index=next((i for i in range(n) if bounds[i]<=event['time']<bounds[i+1]),n-1)
        if bounds[index+1]-event['time']<.6:
            previous=max((item['time'] for item in events if item['time']<event['time']),default=0.)
            timestamp=round(bounds[index+1]-.6,6)
            if timestamp>previous+.7:
                event_window_repairs.append(dict(event_id=event['id'],before_time=event['time'],after_time=timestamp,reason='Information needs a real30fps draw/read window inside its independent Scene'))
                event['time']=timestamp
    claims=_claims(scenario,request);sources=coordinate_source_report()
    route_specs=[]
    for i,r in enumerate(scenario['routes']):
        if scenario['domain']=='shipping':start,end=(1.3,duration*.42) if i==0 else (duration*.46,duration*.85)
        elif scenario['bypass'] and i==len(scenario['routes'])-1:start,end=duration*.45,duration*.85
        else:
            route_count=len(scenario['routes'])-int(scenario['bypass']);start=1.3 if i==0 else duration*(.075+.765*i/route_count);end=duration*(.075+.765*(i+1)/route_count)
        route_specs.append((r,start,end))
    # Three faint, sourced geographic connections add context without inventing actual traffic.
    if scenario['domain'] in {'aviation','geography'}:
        used={l['id'] for l in locations};candidates=[l for l in LOCATIONS.values() if l['kind']=='city' and l['id'] not in used]
        candidates.sort(key=lambda l:min(great_circle_distance(l,a) for a in locations))
        for j,city in enumerate(candidates[:5]):
            anchor=min(locations,key=lambda a:great_circle_distance(city,a))
            context=_route(f'N_{j+1:02}',[anchor['coordinates'],city['coordinates']],length_km=round(great_circle_distance(anchor,city),2),description=f'Sampled geographic connection: {anchor["name"]} → {city["name"]}')
            rs=duration*(.43+j*.05) if j<3 else duration*(.89+(j-3)*.04)
            re_=duration*(.48+j*.05) if j<3 else min(duration*.985,rs+duration*.045)
            route_specs.append((context,rs,re_))
    events=_bind_events_to_geometry(events,scenario,route_specs,duration,bounds)
    for window in event_window_repairs:
        window['planning_event_id']=window['event_id']
        window['event_id']=next((event['id'] for event in events if abs(event['time']-window['after_time'])<1e-6),window['event_id'])
    def boundary_anchor(time,pose):
        if time<=0:return pose,None
        primary=[r for r in route_specs if not r[0]['route_id'].startswith('N_')]
        active=[r for r in primary if r[1]<=time<r[2]]
        if scenario['bypass'] and time/duration>=.5:active=[r for r in active if r[0]['route_id']==scenario['routes'][-1]['route_id']] or active
        item=active[-1] if active else next((r for r in primary if time<r[1]),primary[-1])
        route,rs,re_=item;p=max(0.,min(1.,(time-rs)/(re_-rs)))
        if scenario['domain']=='shipping' and route['route_id']=='R_SUEZ':p*=.40194431692212046
        p=round(p,8)
        point=RouteEngine.spherical_point(route['points'],p)
        pose={**pose,**point,'target_lon':point['lon'],'target_lat':point['lat']}
        pose.pop('location_id',None)
        return pose,dict(time=time,route_id=route['route_id'],progress=p,method='GIS cumulative angular-length spherical interpolation; derived camera position, not a new place',source_ids=route['source_ids'])
    camera_provenance=[];overview_provenance=None
    first_start=camera_state(locations[0],'GLOBAL_ESTABLISH');first_start['yaw']=-.26
    states=[];scenes=[];previous_exit=None
    for i in range(n):
        start,end=bounds[i:i+2];d=end-start;q=(start+end)/2/duration
        scene_type,camera,directing,role=_scene_role(q,i==n-1)
        if i==0:scene_type,camera,directing,role='EARTH_ESTABLISH','FAST_HOOK_DIVE','HOOK_REVEAL','hook'
        if duration<40 and .64<=q<=.8:scene_type,camera,directing,role='ROUTE_CHASE','HORIZON_REVEAL','PEAK_MOMENT','peak'
        loc=locations[min(len(locations)-1,int(q*len(locations)))]
        if scenario['domain'] not in {'shipping','comparison'} and i not in {0,n-1}:
            main=[r for r,rs,re_ in route_specs if not r['route_id'].startswith('N_') and rs<=(start+end)/2<re_]
            if main and main[0]['points'][-1].get('location_id'):loc=resolve_location(main[0]['points'][-1]['location_id'])
        light=choose_lighting(scene_type,role)
        if scenario['domain']=='shipping' and .2<=q<=.7:light='GEOGRAPHY_READABILITY'
        if scenario['domain']=='comparison':
            light='GEOGRAPHY_READABILITY'
            if i not in (0,n-1):scene_type='COUNTRY_FOCUS';camera='COUNTRY_APPROACH';directing='COUNTRY_REVEAL'
        style=request['style_profile'];speed_factor=1.
        if style=='travel':
            speed_factor=.85
            if light!='HERO':light='GEOGRAPHY_READABILITY' if scene_type in {'COUNTRY_FOCUS','COMPARISON','TERRITORY','TIMELINE'} or scenario['domain']=='shipping' else 'DAY_DOCUMENTARY'
        elif style=='documentary' and (scene_type in {'EARTH_ESTABLISH','COUNTRY_FOCUS','CITY_FOCUS','COMPARISON','FINAL_OVERVIEW'} or role in {'orientation','geography','consequence'}):light='GEOGRAPHY_READABILITY'
        elif style=='network':
            speed_factor=1.1
            if scene_type in {'NETWORK','COMPARISON'} and camera!='HORIZON_REVEAL':camera='EARTH_ORBIT' if role=='peak' else 'NETWORK_EXPANSION'
        camera_begin=deepcopy(previous_exit['camera']) if previous_exit else deepcopy(first_start)
        camera_end=camera_state(loc,camera)
        # Continuous camera changes, including the wide final frame.
        camera_end['yaw']+=.025*(i%3-1)
        if i==n-1:
            camera_end,overview_provenance=RouteEngine.network_overview(scenario['routes'],camera_end)
            provenance=dict(time=end,method=overview_provenance['method'],source_ids=overview_provenance['source_ids'],network_overview=True)
        elif scenario['domain']=='comparison':
            coord=loc['coordinates'];camera_end.update(lon=coord['lon'],lat=coord['lat'],target_lon=coord['lon'],target_lat=coord['lat'])
            provenance=dict(time=end,method='Verified country focus coordinate; comparison has no moving entity',source_ids=[coord['source_id']],geography_focus=True,location_id=loc['id'])
        else:camera_end,provenance=boundary_anchor(end,camera_end)
        if provenance:camera_provenance.append(provenance)
        visible=[];entities=[]
        for r,rs,re_ in route_specs:
            if end<=rs:continue
            ps=max(0.,min(1.,(start-rs)/(re_-rs)));pe=max(0.,min(1.,(end-rs)/(re_-rs)))
            if scenario['domain']=='shipping' and r['route_id']=='R_SUEZ':
                ps*=.40194431692212046;pe*=.40194431692212046
            route={**deepcopy(r),'start_time':round(max(0.,rs-start),6),'end_time':round(min(d,max(0.,re_-start)),6),'progress_start':round(ps,8),'progress_end':round(pe,8),'faint':r['route_id'].startswith('N_') or (scenario['bypass'] and r['route_id']!=scenario['routes'][-1]['route_id'] and q>.5)}
            if route['end_time']<=route['start_time']:route.update(start_time=0.,end_time=d)
            visible.append(route)
            if pe>ps and scenario['domain']!='comparison' and not r['route_id'].startswith('N_'):
                entities.append(dict(id=('ship_reference' if r['route_id']=='R_SUEZ' else 'ship_alternative') if scenario['domain']=='shipping' else 'aircraft_'+r['route_id'],type='cargo_ship' if scenario['domain']=='shipping' else 'aircraft',route_id=r['route_id'],location_id=loc['id'],action='move',start_time=round(max(route['start_time'],rs+.2-start),6) if rs>=start else route['start_time'],end_time=route['end_time']))
        scene_events=[{**deepcopy(e),'time':round(e['time']-start,6)} for e in events if start<=e['time']<end]
        sound_events=[dict(id='A_'+e['id'],kind=SOUND_MAP[e['kind']],time=e['time'],duration=min(1.2,d-e['time']),visual_event_id=e['id'],gain_db=-15 if e['role']!='peak' else -10) for e in scene_events]
        if i==0:sound_events.insert(0,dict(id='A_OPEN',kind='cinematic_hit',time=0.,duration=1.,visual_event_id=None,gain_db=-12))
        labels=[dict(text=loc['id'][8:].upper() if loc['kind']=='airport' else loc['name'].upper(),coordinates=deepcopy(loc['coordinates']),start_time=.1,end_time=d,role='city',opacity=.9)]
        if i==n-1:
            labels=[dict(text=place['id'][8:].upper() if place['kind']=='airport' else place['name'].upper(),coordinates=deepcopy(place['coordinates']),start_time=.1,end_time=d,role='city',opacity=.9) for place in locations]
        if scenario['domain']=='shipping' and role=='variable':labels.append(dict(text='ASSUMPTION · CANAL CLOSED',coordinates=deepcopy(loc['coordinates']),start_time=.8,end_time=d,role='status',opacity=.8))
        timeline=dict(year=None,date=None,era='modern',timeline_position=round(start/duration,6))
        entry=deepcopy(previous_exit) if previous_exit else dict(camera=deepcopy(camera_begin),earth_rotation=0.,active_countries=[],active_routes=[],entities=[],lighting=light,timeline=timeline)
        exit_state=dict(camera=deepcopy(camera_end),earth_rotation=0.,active_countries=sorted({l.get('country','') for l in locations if l.get('country')}),active_routes=[r['route_id'] for r in visible],entities=[dict(id=e['id'],route_id=e['route_id'],progress=next(r['progress_end'] for r in visible if r['route_id']==e['route_id'])) for e in entities],lighting=light,timeline={**timeline,'timeline_position':round(end/duration,6)})
        narration=_topic_hook(scenario,request) if i==0 else _shipping_narration(start,end,duration,scene_events,route_specs,request,scenes[-1]['narration']) if scenario['domain']=='shipping' else _narration(role,loc,scenario['domain'],scenario['conditional'],d)
        # Keep short scenes comfortably under conservative Korean speech estimation.
        if len(narration.replace(' ',''))/5.8>d*.9:narration={'hook':'이 연결이 바뀐다면?','orientation':'검증된 출발점을 확인합니다.','progression':'다음 연결로 향합니다.','variable':'다른 경로가 필요합니다.','peak':'전체 연결이 드러납니다.','payoff':'새로운 연결이 보입니다.'}.get(role,'연결을 비교합니다.')
        scene=dict(hook=_topic_hook(scenario,request) if i==0 else '',scene_id=f'S{i+1:03}',start_time=start,duration=d,scene_type=scene_type,narration=narration,location=loc['name'],coordinates=deepcopy(loc['coordinates']),geographic_targets=[loc['id']],camera_preset=camera,camera_start=camera_begin,camera_end=camera_end,camera_speed=CAMERA_PRESETS[camera]['speed']*speed_factor,camera_easing=CAMERA_PRESETS[camera]['easing'],lighting_preset=light,entities=entities,entity_actions=[dict(entity_id=e['id'],action=e['action']) for e in entities],routes=visible,visual_events=scene_events,effects=[dict(kind='city_focus',target_id=loc['id'],strength=.35)],labels=labels,sound_events=sound_events,music_energy=.9 if role in {'hook','peak','payoff'} else .42 if role=='orientation' else .6,transition_in='camera_continuity',transition_out='camera_continuity',source_type='VERIFIED_GIS_WITH_EXPLICIT_SCENARIO',fact_status='SIMULATION',render_quality='CINEMA' if role=='peak' and request['quality']=='CINEMA' else request['quality'],entry_state=entry,exit_state=exit_state,directing_presets=[directing],claim_ids=['A01','M01']+[c['id'] for c in claims if c['status']=='FACT' and loc['coordinates']['source_id'] in c['source_ids']],year=None,date=None,era='modern',timeline_position=round(start/duration,6),motion_start=0.,description=f'{role}: {loc["name"]}',role=role,narration_event_ids=[e['id'] for e in scene_events])
        scenes.append(scene);previous_exit=exit_state
    plan=dict(schema_version='1.0',project_id=str(request.get('project_id','')),version=1,duration=duration,request=request,options={k:request[k] for k in ('tts','subtitles','bgm','quality')},story=dict(hook=scenes[0]['hook'],claims=claims,beats=[dict(scene_id=s['scene_id'],role=s['role'],cause=scenes[i-1]['scene_id'] if i else None,summary=s['description']) for i,s in enumerate(scenes)],domain=scenario['domain'],planner='offline-capability-bounded-v1',conclusion=claims[-1]['text'],limitations=['사실은 공개 GIS의 위치·형태·경로 자료에 한정합니다.','이동 속도·항로 선택·폐쇄의 결과는 가정 기반 시각화이며 예측이 아닙니다.']),scenes=scenes,required_plugins=scenario['plugins'],sources=sources,metadata=dict(camera_provenance=camera_provenance,style_profile=request['style_profile'],story_pattern={'shipping':'disruption-detour-network','comparison':'geography-comparison','geography':'route-choice-comparison','aviation':'journey-network-reveal'}[scenario['domain']]))
    # Explicit typed bindings distinguish places which share the same GIS file;
    # provenance cannot be established merely by matching a source ID.
    plan['metadata']['coordinate_claim_targets']={f'F{index+1:02}':loc['id'] for index,loc in enumerate(locations)}
    for optional in ('narration_file','narration_timing','tts_language'):
        if optional in request:plan['options'][optional]=request[optional]
    plan['metadata']['final_overview']=overview_provenance
    if event_window_repairs:plan['metadata']['scene_event_window_repairs']=event_window_repairs
    plan['story']['pattern']=plan['metadata']['story_pattern']
    certificate=_certify_planned_events(plan)
    from .schema import validate_plan
    plan['gate']=validate_plan(plan)
    return plan
