"""New geometric source-gap audit over preserved bounds, not a renderer/test rerun."""
import json, pathlib, hashlib, math
from shapely.geometry import shape,box,mapping
from shapely.ops import unary_union
from shapely.validation import make_valid
P=pathlib.Path(__file__).parent
frames=json.loads((P/'PRESERVED_FRAME_BOUNDS.json').read_text())
footprint=unary_union([box(*f['bounds']) for f in frames['frames']])
envelope=box(*footprint.bounds)
land_bytes=(P/'ne_10m_admin_0_countries.geojson').read_bytes()
assert hashlib.sha256(land_bytes).hexdigest()=='239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255', 'LAND_SOURCE_HASH_MISMATCH'
assert frames['artifactSha256']=='2b4f8d2419e5998d72b922b05a4e617cd30788b00af0f85e981507cf043836c9', 'FRAME_ARTIFACT_HASH_MISMATCH'
world=json.loads(land_bytes)
lands=[];sources=[];repairs=[]
for f in world['features']:
 g=shape(f['geometry'])
 if not box(*g.bounds).intersects(envelope):continue
 if not g.is_valid:g=make_valid(g);repairs.append(f['properties'].get('ADMIN'))
 clipped=g.intersection(footprint)
 if not clipped.is_empty and clipped.area>0:lands.append(clipped);sources.append(f['properties'].get('ADMIN'))
land=unary_union(lands)
wc=json.loads((P/'WORLDCOVER_GRID_INVENTORY.json').read_text());dsm=json.loads((P/'DSM_COVERAGE_INVENTORY.json').read_text())
wc_present=set(wc['sourceUrls']);dsm_present={f"N{x['latitude']:02d}E{x['longitude']:03d}" for x in dsm['cells'] if x['inventoryStatus']=='PUBLISHED'}
cells=[]
for lat in range(math.floor(footprint.bounds[1]),math.ceil(footprint.bounds[3])):
 for lon in range(math.floor(footprint.bounds[0]),math.ceil(footprint.bounds[2])):
  tile=f'N{lat:02d}E{lon:03d}';visible=box(lon,lat,lon+1,lat+1).intersection(footprint)
  if visible.area==0:continue
  overlap=visible.intersection(land)
  visible_frames=[f for f in frames['frames'] if box(*f['bounds']).intersection(visible).area>0]
  cells.append({'tile':tile,'bounds':[lon,lat,lon+1,lat+1],'visibleAreaSquareDegrees':visible.area,'mappedLandAreaSquareDegrees':overlap.area,'classification':'MAPPED_LAND_PRESENT' if overlap.area>0 else 'NO_MAPPED_LAND_AT_NE10M_SCALE','opticalCatalogPresent':tile in wc_present,'dsmCatalogPresent':tile in dsm_present,'visibleFrameCount':len(visible_frames),'firstVisibleFrame':{'part':visible_frames[0]['part'],'frame':visible_frames[0]['frame']},'missingSourceLandGeometry':mapping(overlap) if overlap.area>0 and (tile not in wc_present or tile not in dsm_present) else None})
def summary(k):
 missing=[c for c in cells if not c[k]]
 return {'missingCells':len(missing),'missingWithMappedLand':[c['tile'] for c in missing if c['mappedLandAreaSquareDegrees']>0],'missingWithoutMappedLand':[c['tile'] for c in missing if c['mappedLandAreaSquareDegrees']==0]}
result={'schema':'WORLD_ENGINE_SOURCE_GAP_GEOMETRY_AUDIT_V1','status':'CPU_GEOMETRIC_CLASSIFICATION_NOT_SOURCE_ADMISSION','baseCommit':'5d36583e493e8b6ca9ba3a121cbeb16cc3460d83','boundsEvidence':{k:v for k,v in frames.items() if k!='frames'},'landSourceUrl':'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson','landSourceSha256':hashlib.sha256((P/'ne_10m_admin_0_countries.geojson').read_bytes()).hexdigest(),'landSourceCountries':sources,'geometryRepairs':repairs,'preservedFrameCount':len(frames['frames']),'uniqueBoundsCount':len({tuple(x['bounds']) for x in frames['frames']}),'actualFootprintBounds':list(footprint.bounds),'actualFootprintAreaSquareDegrees':footprint.area,'envelopeUnusedAreaSquareDegrees':envelope.difference(footprint).area,'initialFrameCoversFootprint':box(*frames['frames'][0]['bounds']).covers(footprint),'optical':summary('opticalCatalogPresent'),'dsm':summary('dsmCatalogPresent'),'cells':cells,'limitations':['Natural Earth 1:10m is generalized cartography, not a 10-metre mask. Absence of mapped land is not proof of no small island or valid water data.','Country polygons are modern land context, not historical coastline reconstruction.','All preserved frame rectangles are visible geographic footprints; this does not model label occlusion as grounds for discarding data.','No missing cell is filled with zero height or fabricated imagery. Source/renderer admission remains false.'],'oldPASSReruns':0,'gpuStarts':0,'renders':0,'productionAdmitted':False}
(P/'SOURCE_GAP_GEOMETRY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['cells','limitations']},indent=2))
