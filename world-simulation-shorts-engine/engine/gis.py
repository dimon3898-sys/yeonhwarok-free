"""Read geographic coordinates from versioned public GIS sources, never language model guesses."""
from pathlib import Path
from copy import deepcopy
import json, math, re
DATA=Path(__file__).resolve().parents[1]/'data'
_CATALOG=json.loads((DATA/'locations.json').read_text())
LOCATIONS={loc['id']:loc for loc in _CATALOG['locations']}
SOURCES={s['id']:s for s in _CATALOG['sources']}

class UnknownLocation(ValueError):
    code='UNKNOWN_GIS_LOCATION'
    def __init__(self,name):self.name=name;super().__init__(f'검증된 GIS 목록에서 장소를 찾을 수 없습니다: {name}')

def _shipping():
    path=DATA/'shipping_routes.json'
    return json.loads(path.read_text()) if path.exists() else None

def resolve_location(name):
    if name in LOCATIONS:return deepcopy(LOCATIONS[name])
    for loc in LOCATIONS.values():
        if any(name.casefold()==a.casefold() for a in loc['aliases']):return deepcopy(loc)
    shipping=_shipping()
    if shipping:
        raw=shipping.get('locations',{})
        values=raw.values() if isinstance(raw,dict) else raw
        for loc in values:
            if name in (loc.get('id'),loc.get('name')) or name in loc.get('aliases',[]):return deepcopy(loc)
    raise UnknownLocation(name)

def mentioned_locations(text):
    """Only explicit, longest catalog aliases; ambiguous named places are disambiguated by catalog."""
    found=[]
    for loc in LOCATIONS.values():
        for alias in loc['aliases']:
            if len(alias)<3 and alias.isascii():continue
            pattern=re.escape(alias)
            if alias.isascii():pattern=r'(?<![A-Za-z])'+pattern+r'(?![A-Za-z])'
            match=re.search(pattern,text,re.I)
            if match:found.append((match.start(),match.end(),-len(alias),loc));break
    found.sort(key=lambda v:(v[0],v[2],v[3]['kind']=='country'));unique=[];occupied=[]
    for lo,hi,_,loc in found:
        if any(lo<b and hi>a for a,b in occupied):continue
        if loc['id'] not in [p['id'] for p in unique]:unique.append(deepcopy(loc));occupied.append((lo,hi))
    return unique

def verified_coordinate(coord,tolerance=1e-6):
    if not isinstance(coord,dict) or not all(k in coord for k in ('lon','lat','source_id')):return False
    if not (-180<=coord['lon']<=180 and -90<=coord['lat']<=90):return False
    loc_id=coord.get('location_id')
    if loc_id and loc_id in LOCATIONS:
        expected=LOCATIONS[loc_id]['coordinates']
        return coord['source_id']==expected['source_id'] and abs(coord['lon']-expected['lon'])<=tolerance and abs(coord['lat']-expected['lat'])<=tolerance
    shipping=_shipping()
    if shipping:
        raw_locations=shipping.get('locations',{})
        shipping_ids=set(raw_locations) if isinstance(raw_locations,dict) else {l['id'] for l in raw_locations}
        if loc_id and loc_id not in shipping_ids:return False
        for route in shipping.get('routes',{}).values() if isinstance(shipping.get('routes'),dict) else shipping.get('routes',[]):
            points=route.get('points',route.get('coordinates',[]))
            for p in points:
                lon,lat=(p['lon'],p['lat']) if isinstance(p,dict) else p[:2]
                if coord['source_id']==route.get('source_id') and abs(coord['lon']-lon)<=tolerance and abs(coord['lat']-lat)<=tolerance:return True
        raw=shipping.get('locations',{})
        for loc in raw.values() if isinstance(raw,dict) else raw:
            p=loc.get('coordinates',{})
            if isinstance(p,dict) and coord['source_id']==p.get('source_id') and abs(coord['lon']-p.get('lon',1000))<=tolerance and abs(coord['lat']-p.get('lat',1000))<=tolerance:return True
    return False

def great_circle_distance(a,b):
    a=a.get('coordinates',a);b=b.get('coordinates',b)
    lat1,lat2=map(math.radians,(a['lat'],b['lat']));dl=math.radians(b['lon']-a['lon'])
    v=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(v)))

def coordinate_source_report():
    result=list(deepcopy(SOURCES).values());shipping=_shipping()
    if shipping:result+=shipping.get('sources',[])
    return result

class RouteEngine:
    @staticmethod
    def network_overview(routes,pose):
        """Fit the sourced main network in portrait space without hiding its nodes.

        Finds a spherical enclosing focus from the convex hull of sourced route
        samples, then projects with the renderer's actual camera rig. Coordinates
        here are derived framing positions, never new GIS place records.
        """
        from .plugins import UnsupportedVisualRequirement
        def dot(a,b):return sum(x*y for x,y in zip(a,b))
        def normalize(v):
            length=math.sqrt(dot(v,v))
            return tuple(x/length for x in v) if length>1e-10 else None
        def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        def vector(p):
            lon,lat=math.radians(p['lon']),math.radians(p['lat'])
            return (math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat))
        def geographic(v):return dict(lon=math.degrees(math.atan2(v[1],v[0])),lat=math.degrees(math.asin(max(-1.,min(1.,v[2])))))
        samples={}
        for route in routes:
            points=route['points']+[RouteEngine.spherical_point(route['points'],i/32) for i in range(33)]
            for p in points:samples[(round(p['lon'],7),round(p['lat'],7))]=vector(p)
        points=list(samples.values())
        if not points:raise ValueError('No sourced main routes for overview')
        # Frank-Wolfe nearest convex-hull point gives the maximum-margin visible
        # hemisphere. It also detects globe-spanning topics a single shot cannot show.
        focus=tuple(sum(v[k] for v in points)/len(points) for k in range(3))
        for _ in range(512):
            v=min(points,key=lambda p:dot(focus,p));length=dot(focus,focus);gap=length-dot(focus,v)
            if gap<1e-12:break
            difference=tuple(y-x for x,y in zip(focus,v));denominator=dot(difference,difference)
            amount=max(0.,min(1.,gap/denominator)) if denominator>1e-15 else 0.
            focus=tuple(x+amount*d for x,d in zip(focus,difference))
        focus=normalize(focus)
        if focus is None or min(dot(focus,v) for v in points)<.01:
            raise UnsupportedVisualRequirement(['MULTI_HEMISPHERE_OVERVIEW'],'주 경로가 한 지구 반구에 들어가지 않습니다. 여러 지구 전경 장면이 필요하며, 뒤쪽 도시를 가짜로 앞에 표시하지 않습니다.')
        target=tuple(.99*x for x in focus);tan=math.tan(math.radians(44)/2);original=deepcopy(pose)
        for step in range(85):
            height=min(6.,max(original['height'],1.85)+step*.05);n=focus
            # Offset the rig's radial anchor to retain authored tilt/yaw while
            # keeping the actual viewing hemisphere centered on the real network.
            for _ in range(16):
                lon=math.atan2(n[1],n[0]);east=(-math.sin(lon),math.cos(lon),0.);north=cross(n,east)
                position=tuple((1+height)*x-original['tilt']*height*y+original['yaw']*height*z for x,y,z in zip(n,north,east))
                observed=normalize(position);n=normalize(tuple(x+(y-z) for x,y,z in zip(n,focus,observed)))
            lon=math.atan2(n[1],n[0]);east=(-math.sin(lon),math.cos(lon),0.);north=cross(n,east)
            position=tuple((1+height)*x-original['tilt']*height*y+original['yaw']*height*z for x,y,z in zip(n,north,east))
            direction=normalize(tuple(y-x for x,y in zip(position,target)))
            angle=original['bank'];rotation=cross(direction,n)
            up=tuple(x*math.cos(angle)+r*math.sin(angle)+d*dot(direction,n)*(1-math.cos(angle)) for x,r,d in zip(n,rotation,direction))
            if abs(dot(up,direction))>.995:up=north
            right=normalize(cross(direction,up));up=cross(right,direction);screen=[];visible=True
            for point in points:
                offset=tuple(x-y for x,y in zip(point,position));depth=dot(offset,direction)
                if depth<=0 or dot(point,position)<=1.00002:visible=False;break
                screen.append((.5+.5*dot(offset,right)/(depth*tan*9/16),.5-.5*dot(offset,up)/(depth*tan)))
            if visible and all(.145<=x<=.815 and .115<=y<=.765 for x,y in screen):
                focus_geo=geographic(focus);camera_geo=geographic(n)
                result={**original,**camera_geo,'target_lon':focus_geo['lon'],'target_lat':focus_geo['lat'],'height':height,'fov':44}
                result.pop('location_id',None)
                return result,dict(method='Sourced GIS spherical convex-hull focus and exact portrait camera-rig projection fit',focus=focus_geo,height=height,sample_count=len(points),screen_bounds=dict(x_min=min(x for x,y in screen),x_max=max(x for x,y in screen),y_min=min(y for x,y in screen),y_max=max(y for x,y in screen)),source_ids=sorted({sid for r in routes for sid in r['source_ids']}),route_ids=[r['route_id'] for r in routes])
            if height>=6:break
        raise UnsupportedVisualRequirement(['MULTI_HEMISPHERE_OVERVIEW'],'한 번의 9:16 지구 전경에 모든 주 경로를 안전하게 담을 수 없습니다. 전경을 두 장면으로 나누는 기획이 필요합니다.')

    @staticmethod
    def spherical_point(points,progress):
        """Derived camera position on a sourced route, not a new geographic place.

        Exactly the renderer's unit-sphere, cumulative angular-length interpolation.
        Sea routes retain every licensed graph waypoint. Radius/altitude has no
        effect on geographic longitude/latitude; no ports or cities are guessed.
        """
        if len(points)<2:raise ValueError('Route requires two sourced coordinates')
        progress=float(progress)
        if not math.isfinite(progress):raise ValueError('Non-finite route progress')
        progress=max(0.,min(1.,progress))
        def vector(point):
            lon,lat=math.radians(point['lon']),math.radians(point['lat'])
            return (math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat))
        def dot(a,b):return sum(x*y for x,y in zip(a,b))
        def normalize(v):
            length=math.sqrt(dot(v,v))
            return tuple(x/length for x in v)
        def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        vectors=[vector(p) for p in points];lengths=[0.]
        for a,b in zip(vectors,vectors[1:]):lengths.append(lengths[-1]+math.acos(max(-1.,min(1.,dot(a,b)))))
        if lengths[-1]<1e-7:raise ValueError('Route endpoints coincide')
        distance=progress*lengths[-1];index=1
        while index<len(lengths)-1 and lengths[index]<distance:index+=1
        delta=lengths[index]-lengths[index-1];u=(distance-lengths[index-1])/delta if delta>1e-8 else 0.
        a,b=vectors[index-1:index+1];angle=math.acos(max(-1.,min(1.,dot(a,b))))
        if angle<1e-7:v=normalize(tuple(x+(y-x)*u for x,y in zip(a,b)))
        elif math.pi-angle<1e-5:
            axis=cross((0.,0.,1.),a)
            if dot(axis,axis)<.001:axis=cross((1.,0.,0.),a)
            axis=normalize(axis);theta=math.pi*u;rotation=cross(axis,a)
            v=normalize(tuple(x*math.cos(theta)+r*math.sin(theta)+k*dot(axis,a)*(1-math.cos(theta)) for x,r,k in zip(a,rotation,axis)))
        else:
            wa=math.sin((1-u)*angle)/math.sin(angle);wb=math.sin(u*angle)/math.sin(angle)
            v=normalize(tuple(x*wa+y*wb for x,y in zip(a,b)))
        return dict(lon=math.degrees(math.atan2(v[1],v[0])),lat=math.degrees(math.asin(max(-1.,min(1.,v[2])))))
    @staticmethod
    def great_circle(start,end):
        return [resolve_location(start)['coordinates'],resolve_location(end)['coordinates']]
    @staticmethod
    def sea(route_id):
        source=_shipping()
        if not source:raise UnknownLocation('해상 경로 GIS 자료가 준비되지 않았습니다.')
        routes=source.get('routes',{})
        route=routes.get(route_id) if isinstance(routes,dict) else next((r for r in routes if r.get('id')==route_id),None)
        if not route:raise UnknownLocation(route_id)
        points=route.get('points',route.get('coordinates',[]));sid=route.get('source_id','searoute_marnet')
        return [dict(lon=p['lon'],lat=p['lat'],source_id=p.get('source_id',sid),**({'location_id':p['location_id']} if p.get('location_id') else {})) if isinstance(p,dict) else dict(lon=p[0],lat=p[1],source_id=sid) for p in points]
    @staticmethod
    def land(*_):
        from .plugins import UnsupportedVisualRequirement
        raise UnsupportedVisualRequirement(['LAND_ROUTING'],'검증된 육상 경로 그래프가 없어 임의 직선을 생성하지 않습니다.')
