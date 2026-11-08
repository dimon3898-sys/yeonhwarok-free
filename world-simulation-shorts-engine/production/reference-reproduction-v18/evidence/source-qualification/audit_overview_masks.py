import json,pathlib,numpy as np,hashlib
import rasterio
from rasterio.features import rasterize
from affine import Affine
from shapely.geometry import shape,box
from shapely.ops import unary_union
P=pathlib.Path(__file__).parent;O=P/'land_overviews'
world=json.loads((P/'ne_10m_admin_0_countries.geojson').read_text());extent=box(123.27404215372272,32.2,131.72595784627728,44.2)
geoms=[shape(f['geometry']) for f in world['features'] if box(*shape(f['geometry']).bounds).intersects(extent)]
land=unary_union([g.intersection(extent) for g in geoms]);inner=land.buffer(-.02)
reports=[]
for file in sorted(O.glob('*.json')):
 r=json.loads(file.read_text())
 if r.get('status')!='DECODED_NOT_ADMITTED':continue
 z=np.load(file.with_suffix('.npz'));a=z['data'];invalid=z['invalid'];n=a.shape[1];t=Affine(*r['decodedTransform'][:6]);b=box(*r['sourceBounds'])
 masks=[]
 for geom in [land,inner]:
  g=geom.intersection(b);m=rasterize([(g,1)],out_shape=(n,n),transform=t,fill=0,dtype='uint8').astype(bool) if not g.is_empty else np.zeros((n,n),bool);masks.append(m)
 mapped,interior=masks;holes=invalid&interior;bright=(a[:3]>=3500).all(axis=0)&~invalid
 y,x=np.where(holes);hole_bounds=None
 if len(x):
  lo=t*(int(x.min()),int(y.max())+1);hi=t*(int(x.max())+1,int(y.min()));hole_bounds=[lo[0],lo[1],hi[0],hi[1]]
 result={'tile':r['tile'],'decodedSize':n,'invalidPixels':int(invalid.sum()),'invalidOnMappedLandPixels':int((invalid&mapped).sum()),'invalidBeyond002DegreeCoastBufferPixels':int(holes.sum()),'interiorInvalidBounds':hole_bounds,'brightAllRGBAtLeast3500Pixels':int(bright.sum()),'brightFraction':float(bright.mean()),'warning':'Brightness is only a review flag, not cloud classification. Buffered NE land is generalized; lakes/islands/shoreline mismatch remain possible.','productionAdmitted':False}
 reports.append(result)
result={'schema':'WORLD_ENGINE_OVERVIEW_MASK_AUDIT_V1','decodedTileCount':len(reports),'sourceMaskScope':'Requested decoded overview scale only, not native10m exhaustive mask','landClassification':'Pinned Natural Earth generalized1:10-million; interior buffer0.02degrees, not a scientific water mask','tilesWithInvalidMappedInterior':[r['tile'] for r in reports if r['invalidBeyond002DegreeCoastBufferPixels']>0],'tiles':reports,'productionAdmitted':False,'gpuStarts':0,'renders':0}
(P/'OVERVIEW_MASK_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'decoded':len(reports),'interiorGapTiles':result['tilesWithInvalidMappedInterior'],'totalInvalid':sum(x['invalidPixels'] for x in reports)}))
