"""Extract unchanged historical source rows. Does not invent dates/fronts/routes."""
import hashlib, json, pathlib, shutil, sys, zipfile
from shapely.geometry import shape
from shapely.validation import explain_validity

BASE = pathlib.Path(__file__).parent
SOURCE = pathlib.Path(sys.argv[1])
def write(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
archive = (SOURCE / 'cliopatria.geojson.zip').read_bytes()
with zipfile.ZipFile(SOURCE / 'cliopatria.geojson.zip') as z:
    member = z.namelist()[0]
    original = z.read(member)
    rows = [f for f in json.loads(original)['features'] if
            f['properties']['Name'] == 'Mongol Empire' and
            1206 <= f['properties']['FromYear'] <= 1250]
assert len(rows) == 8
rows.sort(key=lambda x: x['properties']['FromYear'])
write('source/CLIOPATRIA_MONGOL_1206_1259.geojson', {'type':'FeatureCollection','features':rows})
shutil.copy2(SOURCE / 'LICENSE.md', BASE / 'source/CLIOPATRIA_LICENSE.md')
audit=[]
for i,row in enumerate(rows):
    geom=shape(row['geometry'])
    audit.append({'fromYear':row['properties']['FromYear'],'toYear':row['properties']['ToYear'],
        'bounds':list(geom.bounds),'valid':geom.is_valid,'validity':explain_validity(geom),
        'sourceAreaKm2':row['properties']['Area'],
        'previousStateNotContained':bool(i and not shape(rows[i-1]['geometry']).difference(geom).is_empty),
        'previousMinusCurrentSquareDegrees':shape(rows[i-1]['geometry']).difference(geom).area if i else None,
        'geometrySHA256PythonCanonical':digest(json.dumps(row['geometry'],sort_keys=True,separators=(',',':')).encode())})
write('source/SOURCE_AUDIT.json', {'status':'SOURCE_BYTES_AND_GEOMETRY_VALIDATED_NOT_EXACT_HISTORY_CERTIFICATION',
    'repository':'https://github.com/Seshat-Global-History-Databank/cliopatria',
    'sourceCommit':'5f433377139a6eeaeacbdc894b70f8805b72c8b5','tag':'v0.2.1',
    'archiveSHA256':digest(archive),'archiveMember':member,'memberSHA256':digest(original),
    'selectedPeriod':[1206,1259], 'datePrecision':'YEAR', 'selectedRows':audit,
    'geometryChanged':False,'historicalInterpolationAllowed':False,
    'campaignRouteSourceAvailable':False,'battleFrontSourceAvailable':False,
    'interpretation':'Published reconstructed polity extents, not surveyed borders or exact conquest dates. Source year intervals inclusive. No January 1 conquest dates created.',
    'fallbackFinding':'Cumulative independent layers are not an exact snapshot sequence: earlier polygons are not fully contained in later polygons.'})
source_id='CLIOPATRIA_V021_MONGOL_RECONSTRUCTION'
geometries=[{'id':'MONGOL_EXTENT_'+str(r['properties']['FromYear']),'source_id':source_id,
    'geometry':r['geometry'],'note':f"Unchanged reconstructed extent applicable {r['properties']['FromYear']}–{r['properties']['ToYear']}; year precision only."} for r in rows]
b=shape(rows[0]['geometry']).bounds
anchor=[(b[0]+b[2])/2,(b[1]+b[3])/2]
facts={'version':'PLANNER_FACTS_V1','data_mode':'PRODUCTION','semantic_mode':'SUPPLIED_OBSERVED_STATES',
    'subject':{'id':'MONGOL_EMPIRE','label':'몽골제국','aliases':['몽골제국','Mongol Empire'],'event_family':'WAR'},
    'locations':[{'id':'SOURCE_EXTENT_CENTER','label':'초기 원자료 범위의 표시 중심','anchor':anchor}],
    'time_range':{'start':'1206','end':'1259'},
    'source_notes':[{'id':source_id,'source_type':'PUBLISHED_RECONSTRUCTED_POLITY_EXTENTS',
       'source_reference':'https://github.com/Seshat-Global-History-Databank/cliopatria/tree/v0.2.1',
       'verification_status':'VERIFIED','original_sha256':digest(archive),'version':'v0.2.1','crs':'EPSG:4326',
       'license':'CC BY 4.0; Bennett et al., Cliopatria/Seshat; https://creativecommons.org/licenses/by/4.0/',
       'note':'Source identity and faithful extraction verified. Historical reconstruction uncertainty retained. Not yet admitted to the engine historical evidence registry. Display center is a bounding-box calculation, not a named settlement.'}],
    'geometries':geometries,
    'stages':[{'id':'SNAPSHOT_'+str(r['properties']['FromYear']),'date':str(r['properties']['FromYear']),
       'label':str(r['properties']['FromYear'])+'-'+str(r['properties']['ToYear']),
       'area_refs':[g['id']],'front_refs':[]} for r,g in zip(rows,geometries)],
    'routes':[],'markers':[],'text':[],
    'camera':{'anchor':anchor,'target_geometry_refs':[g['id'] for g in geometries],
       'minimum_context_geometry_refs':[],'detail_policy':'FACT_BASED_VISUAL_GRADE'},
    'scale':{'preferred':'REGIONAL'}}
all_bounds=[min(shape(r['geometry']).bounds[j] for r in rows) if j<2 else max(shape(r['geometry']).bounds[j] for r in rows) for j in range(4)]
write('MONGOL_EMPIRE_INPUT_CANDIDATE.json', {'schema':'WORLD_ENGINE_PRESENTATION_PROMPT_V2',
    'prompt':'몽골제국의 영토 확장. 제공한 1206년부터 1259년까지의 역사 자료로 1080x1920, 30fps, 6초 영상을 만들어줘.',
    'data':{'schema':'WORLD_ENGINE_DATA_PROMPT_V1','topic':'몽골제국의 영토 확장 (Mongol Empire territorial expansion)',
      'simulationType':'HISTORICAL','durationSeconds':6,'fps':30,'resolution':{'width':1080,'height':1920},
      'scenes':[{'sceneId':'mongol-empire-source-snapshots','startFrame':0,'endFrame':180,'facts':facts,'historicalEvidence':[]}]},
    'region':{'sourceId':'AUTO','crs':'EPSG:4326','center':[(all_bounds[0]+all_bounds[2])/2,(all_bounds[1]+all_bounds[3])/2],'bbox':all_bounds}})
write('evidence/INPUT_ADAPTATION.json', {'renderInputStatus':'CANDIDATE_NOT_APPLIED',
    'manualDataMapping':['WAR family chosen as existing historical area-state consumer','source geometry IDs','bounding-box display anchors and region','English territory alias for existing bounded parser'],
    'manualPresentationEffects':[], 'sceneJSONEmitted':False,
    'forbiddenSubstitutionsNotPerformed':['invent exact month/day','turn reconstructed boundary into combat front','invent campaign route','make synthetic history','cumulative union presented as exact later territory']})
print(json.dumps({'extractedRows':len(rows),'period':[1206,1259],'allGeometryValid':all(a['valid'] for a in audit),'output':str(BASE)}))
