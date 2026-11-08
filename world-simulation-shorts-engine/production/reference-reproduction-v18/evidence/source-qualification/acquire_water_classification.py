import pathlib,json,hashlib,concurrent.futures,math
import numpy as np,rasterio
from rasterio.enums import Resampling
from shapely.geometry import shape,box
from bounded_cog import RangeFile
from cache_integrity import reusable_receipt
P=pathlib.Path(__file__).parent;O=P/'water_classification';O.mkdir(exist_ok=True)
plan=json.loads((P/('FINER_SOURCE_LOD_ACQUISITION_PLAN.json' if (P/'FINER_SOURCE_LOD_ACQUISITION_PLAN.json').exists() else 'SOURCE_LOD_ACQUISITION_PLAN.json')).read_text());catalog=json.loads((P/'worldcover_classification_grid.geojson').read_text());groups={}
for row in plan['cells']:
 if not (row['mappedLandPresent'] or row.get('finerClassifiedLandPresent')):continue
 lat=int(row['tile'][1:3]);lon=int(row['tile'][4:7]);tile=f'N{lat//3*3:02d}E{lon//3*3:03d}';groups[tile]=max(groups.get(tile,0),row['powerOfTwoSamplesPerDegree'])
registered={f['properties']['ll_tile'] for f in catalog['features']}
assert all(k in registered for k in groups),'CLASSIFICATION_TILE_NOT_IN_OFFICIAL_GRID'
def acquire(item):
 tile,n=item;path=O/(tile+'.json')
 url=f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif';lat=int(tile[1:3]);lon=int(tile[4:7])
 if reusable_receipt(path,status='DECODED_CLASSIFICATION_NOT_SHORELINE_ADMISSION',url=url,shape=[3*n,3*n],keys=[('classes','arraySha256',[3*n,3*n])],bounds=[lon,lat,lon+3,lat+3]):return {'tile':tile,'status':'REUSED_SUCCESS'}
 try:
  url=f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif';target=tile+'_classification.tif'
  def opener(path,mode='rb'):
   if path!=target:raise FileNotFoundError(path)
   return RangeFile(url)
  with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
   with rasterio.open(target,opener=opener) as ds:
    assert str(ds.crs)=='EPSG:4326' and ds.count==1 and ds.width==36000 and ds.height==36000,'CLASSIFICATION_GRID_MISMATCH'
    assert abs(ds.transform.a-1/12000)<1e-12 and abs(ds.transform.e+1/12000)<1e-12,'NATIVE_PIXEL_ALIGNMENT_MISMATCH'
    a=ds.read(1,out_shape=(3*n,3*n),masked=True,resampling=Resampling.nearest);data=a.filled(0).astype('uint8');invalid=np.ma.getmaskarray(a)| (data==0)
    classes,counts=np.unique(data,return_counts=True);assert set(classes).issubset({0,10,20,30,40,50,60,70,80,90,95,100}),'UNEXPECTED_CLASS'
    np.savez_compressed(O/(tile+'.npz'),classes=data,invalid=invalid)
    cache=RangeFile(url).root
    r={'tile':tile,'status':'DECODED_CLASSIFICATION_NOT_SHORELINE_ADMISSION','url':url,'sourceCRS':str(ds.crs),'sourceShape':[ds.height,ds.width],'sourceBounds':list(ds.bounds),'sourceTransform':list(ds.transform),'sourceNoData':ds.nodata,'decodedShape':list(data.shape),'decodedTransform':list(ds.transform*ds.transform.scale(ds.width/(3*n),ds.height/(3*n))),'resampling':'nearest-neighbor on available COG overviews','classCounts':{str(int(k)):int(v) for k,v in zip(classes,counts)},'classSemantics':{'0':'Unknown/no data, never ocean','80':'Classified permanent water (>9 months/year), not a tidal shoreline','90':'Herbaceous wetland, retained separately as uncertain for land/water compositing','otherDocumentedClasses':'Classified land-cover types; source may misclassify shadows and small features'},'sourceTags':ds.tags(),'arraySha256':hashlib.sha256(data.tobytes()).hexdigest(),'npzSha256':hashlib.sha256((O/(tile+'.npz')).read_bytes()).hexdigest(),'rangeCacheBytes':sum(p.stat().st_size for p in cache.glob('*.bin')),'license':'CC-BY 4.0','attribution':'ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium','productionAdmitted':False,'caveat':'Overview resampling/classification is not a native10m all-subpixel water proof or historical/tidal shoreline reconstruction.'}
    path.write_text(json.dumps(r,indent=2)+'\n');return {'tile':tile,'status':r['status'],'shape':r['decodedShape'],'classCounts':r['classCounts'],'rangeCacheBytes':r['rangeCacheBytes']}
 except Exception as e:
  r={'tile':tile,'status':'BLOCKED','error':str(e),'productionAdmitted':False};path.write_text(json.dumps(r,indent=2)+'\n');return r
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for r in pool.map(acquire,sorted(groups.items(),key=lambda x:-x[1])):print(json.dumps(r),flush=True)
