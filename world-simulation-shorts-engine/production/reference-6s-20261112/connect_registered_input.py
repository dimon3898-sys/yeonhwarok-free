"""Reuse V10; register Mercator poses and official shoreline pin coordinates. No flow analysis."""
from pathlib import Path
import json,hashlib,math,subprocess,sys
P=Path(__file__).resolve().parent;E=P.parents[1];R=E.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def canonical(x):
 return subprocess.check_output(['node','-e',"const f=require('fs');const c=x=>Array.isArray(x)?'['+x.map(c).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+c(x[k])).join(',')+'}':JSON.stringify(x);process.stdout.write(c(JSON.parse(f.readFileSync(0,'utf8'))));"],input=json.dumps(x),text=True).encode()
raw=Path(sys.argv[1]).read_bytes();originalSHA=sha(raw);assert originalSHA=='239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255'
fit=json.loads((P/'calibration/mercator_registration.json').read_text());v10=json.loads((P/'inputs/REFERENCE_5S_CAMERA_BRIDGE_V10.json').read_text())
features={f['properties']['ADM0_A3']:(i,f) for i,f in enumerate(json.loads(raw)['features'])};codes=['ESP','MAR','PRT','DZA','FRA','TUN','MRT'];records=[]
for code in codes:
 i,f=features[code];records.append({'crs':'EPSG:4326','geometry_role':'country','geometry_type':f['geometry']['type'],'id':'COUNTRY_'+code,'name':f['properties']['NAME_EN'],'source_feature_id':code,'source_file_sha256':originalSHA,'source_id':'natural_earth_countries_10m','source_version':'ca96624a56bd078437bca8184e78163e5039ad19','scale':{'denominator':10000000,'precision':'Native source polygons retained'},'provenance':{'selector':{'field':'ADM0_A3','value':code},'source_feature_index':i,'transformations':['Native rings and vertices unchanged; runtime wrapper only']},'coordinates':f['geometry']['coordinates']})
write(P/'sources/NATIVE_COUNTRY_OVERRIDES.json',{'schema':'WORLD_ENGINE_NATIVE_GEOMETRY_OVERRIDE_V1','sourceOriginalSHA256':originalSHA,'historicalOwnershipClaimed':False,'records':records})
x=json.loads((P/'REFERENCE_6S_GEOGRAPHIC_INPUT.json').read_text());facts=x['data']['scenes'][0]['facts'];mapping={'NE_LOWRES_SPAIN':'ESP','NE_LOWRES_MOROCCO':'MAR','NE_LOWRES_PORTUGAL':'PRT','NE_LOWRES_ALGERIA':'DZA','NE_LOWRES_FRANCE':'FRA','NE_LOWRES_TUNISIA':'TUN','NE_LOWRES_MAURITANIA':'MRT'}
facts['geometries']=[g for g in facts['geometries'] if g['id'] in facts['camera']['target_geometry_refs']]
sourceId='NATURAL_EARTH_10M_NATIVE_REGISTERED';sourceURL='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson'
facts['source_notes']=[{**facts['source_notes'][0],'id':sourceId,'sha256':originalSHA,'source_reference':sourceURL,'verification_basis':'Exact native country geometries from pinned Natural Earth 10m source; official IGN coordinates; static modern geography only.'}]
for g in facts['geometries']:g['source_id']=sourceId;g['geometry']=features[mapping[g['id']]][1]['geometry']
pins=[[-5.30675127,35.88810209],[-2.93680807082062,35.2922515360894]]
for i,name in enumerate(['COAST_PIN_A','COAST_PIN_B']):
 l=next(l for l in facts['locations'] if l['id']==name);l.update(anchor=pins[i],country_id='COUNTRY_ESP',label='Coastal pin '+('A' if i==0 else 'B'))
x['region']={'sourceId':'NASA_BMNG_EU_AFRICA_PYRAMID_V1','crs':'EPSG:4326','center':[-3.7,38],'bbox':[-5.5,35.5,-1.9,40.5],'countryId':'COUNTRY_ESP'}
# Keep on-screen place labels neutral; the coordinate-source identity is explicit in evidence.
x['presentation']['labels']['items'][0]['text']='해안 A'
x['presentation']['labels']['items'][0]['pin']='CONTEXT'
x['presentation']['labels']['items'].append({**x['presentation']['labels']['items'][0],'id':'pin-b','text':'해안 B','locationId':'COAST_PIN_B','eventId':'coast-pin-b','priority':59})
merc=lambda t:math.degrees(math.log(math.tan(math.pi/4+math.radians(t)/2)))
inv=lambda y:math.degrees(2*math.atan(math.exp(math.radians(y)))-math.pi/2)
p=fit['parameters'];theta=math.radians(p['rollDegrees']);sc=p['pixelsPerProjectedDegree'];c=math.cos(theta);s=math.sin(theta);origin=p['originGeographic'];offset=p['originPixel']
# Complex numbers preserve V10's measured screen similarity without measuring it again.
base=complex(c,s)*sc;originQ=complex(origin[0],-merc(origin[1]));baseOffset=complex(*offset)-base*originQ
transforms=[]
for row in v10['frames']:
 m=row['screenTransformFromFrame0'];a=complex(m[0][0],m[1][0]);transforms.append((a*base,a*baseOffset+complex(m[0][2],m[1][2])))
qpin=[complex(lon,-merc(lat)) for lon,lat in pins];lastA,lastB=transforms[-1];pred=[lastA*q+lastB for q in qpin];observed=[complex(234,749),complex(556,740)]
correction=(observed[1]-observed[0])/(pred[1]-pred[0]);shift=observed[0]-correction*pred[0]
frames=[]
for f,(a,b) in enumerate(transforms):
 t=max(0,min(1,(f-90)/59));w=t*t*(3-2*t);z=complex(1,0)+(correction-1)*w;a=z*a;b=z*b+shift*w
 center=(complex(411,160+1920/2*822/1080)-b)/a
 frames.append({'center':[center.real,inv(-center.imag)],'scale':abs(a)*1080/822,'rollDegrees':math.degrees(math.atan2(a.imag,a.real))})
frames+=frames[-1:]*30;x['presentation']['camera']={'mode':'GEOGRAPHIC_TRACK','projection':'GEOGRAPHIC_MERCATOR_V1','frames':frames}
recordId='REF6_GEOGRAPHIC_REGISTERED_20261113';claim='STATIC_MODERN_GEOGRAPHY_ONLY'
x['data']['scenes'][0]['historicalEvidence']=[{'recordId':recordId,'sourceId':sourceId,'claimId':claim,'geometryIds':[g['id'] for g in facts['geometries']],'stageIds':[]}]
registry=E/'recovery/universal-data-pipeline-v1/evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json';data=json.loads(registry.read_text());data['records']=[r for r in data['records'] if r['id']!=recordId]
record={**data['records'][0],'id':recordId,'sourceId':sourceId,'sourceSHA256':originalSHA,'sourceReference':sourceURL,'canonicalFactsSHA256':sha(canonical(facts)),'geometrySHA256ById':{g['id']:sha(canonical(g['geometry'])) for g in facts['geometries']},'reviewEvidence':{'sourceURL':sourceURL,'sourceSHA256':originalSHA,'extraction':'EXACT_GEOJSON_GEOMETRY_NO_SIMPLIFICATION','cameraApproval':'PENDING_FULL_SOURCE_AND_PIXEL_VERIFICATION','pins':'Official IGN location table, ETRS89 geographic coordinates; modern static source context'}};data['records'].append(record);write(registry,data)
module=registry.parent.parent/'reviewed_geographic_registry.mjs';text=module.read_text();import re;text=re.sub(r"!=='[a-f0-9]{64}'", "!=='"+sha(registry.read_bytes())+"'",text);module.write_text(text)
write(P/'REFERENCE_6S_REGISTERED_INPUT.json',x)
write(P/'calibration/REGISTERED_CAMERA_BINDING.json',{'schema':'REFERENCE_6S_REGISTERED_CAMERA_BINDING_V1','V10SHA256':sha((P/'inputs/REFERENCE_5S_CAMERA_BRIDGE_V10.json').read_bytes()),'originalVideoSHA256':'853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc','originalFrameTime':8.966666666666667,'firstFrameRegistration':fit,'sourceCrop':[0,160,822,1621.3333333333333],'finalObservedPinTips':[[z.real,z.imag] for z in observed],'officialPinCoordinates':pins,'pinCoordinateSource':'https://www.ign.es/resources/ane/Informacion_Geografica_Destacada/IGN_INFOGEO_LOCALIZACION.html','pinIdentities':['Ceuta approximate center','Melilla approximate center'],'finalSimilarityCorrection':{'scale':abs(correction),'rollDegrees':math.degrees(math.atan2(correction.imag,correction.real)),'translation':[shift.real,shift.imag],'weight':'smoothstep((frame-90)/59), final30 hold'},'opticalFlowRerun':False,'independentMeasuredFramesClaimed':False,'visualApproval':'PENDING_ACTUAL_RENDERER_PNG','frames':180})
print(json.dumps({'inputSHA256':sha((P/'REFERENCE_6S_REGISTERED_INPUT.json').read_bytes()),'finalScale':frames[-1]['scale'],'pinCorrectionScale':abs(correction)}))
