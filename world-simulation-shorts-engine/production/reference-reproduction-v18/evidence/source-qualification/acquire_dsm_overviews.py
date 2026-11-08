import pathlib,json,hashlib,concurrent.futures,sys
import numpy as np,rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from affine import Affine
from bounded_cog import RangeFile
from cache_integrity import reusable_receipt
P=pathlib.Path(__file__).parent;O=P/'dsm_overviews';O.mkdir(exist_ok=True)
plan=json.loads((P/('FINER_SOURCE_LOD_ACQUISITION_PLAN.json' if (P/'FINER_SOURCE_LOD_ACQUISITION_PLAN.json').exists() else 'SOURCE_LOD_ACQUISITION_PLAN.json')).read_text());inventory=json.loads((P/'DSM_COVERAGE_INVENTORY.json').read_text());urls={f"N{r['latitude']:02d}E{r['longitude']:03d}":r['url'] for r in inventory['cells'] if r['inventoryStatus']=='PUBLISHED'}
rows=[r for r in plan['cells'] if r['mappedLandPresent'] or r.get('finerClassifiedLandPresent')];rows.sort(key=lambda r:(-r['powerOfTwoSamplesPerDegree'],r['tile']))
if len(sys.argv)>1:rows=rows[:int(sys.argv[1])]
def acquire(row):
 tile=row['tile'];path=O/(tile+'.json')
 n=row['powerOfTwoSamplesPerDegree'];url=urls.get(tile);lon=int(tile[4:7]);lat=int(tile[1:3])
 if url and reusable_receipt(path,status='DSM_DECODED_NOT_ADMITTED',url=url,shape=[n,n],keys=[('height','heightArraySha256',[n,n]),('valid','validMaskSha256',[n,n])],bounds=[lon,lat,lon+1,lat+1]):return {'tile':tile,'status':'REUSED_SUCCESS'}
 try:
  url=urls[tile];target=tile+'_dsm.tif';n=row['powerOfTwoSamplesPerDegree'];lon=int(tile[4:7]);lat=int(tile[1:3])
  def opener(path,mode='rb'):
   if path!=target:raise FileNotFoundError(path)
   return RangeFile(url)
  with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
   with rasterio.open(target,opener=opener) as ds:
    assert str(ds.crs)=='EPSG:4326' and ds.count==1 and ds.dtypes[0]=='float32','DSM_METADATA_MISMATCH'
    assert ds.tags().get('AREA_OR_POINT')=='Point','DSM_POINT_REGISTRATION_REQUIRED'
    a=ds.read(1,out_shape=(n+2,n+2),masked=True,resampling=Resampling.bilinear);v=a.filled(np.nan).astype('float32');valid=~np.ma.getmaskarray(a)&np.isfinite(v);v[~valid]=np.nan
    src_transform=ds.transform*ds.transform.scale(ds.width/(n+2),ds.height/(n+2));dst_transform=Affine(1/n,0,lon,0,-1/n,lat+1)
    out=np.full((n,n),np.nan,dtype='float32');coverage=np.zeros((n,n),dtype='float32')
    reproject(v,out,src_transform=src_transform,src_crs=ds.crs,dst_transform=dst_transform,dst_crs=ds.crs,src_nodata=np.nan,dst_nodata=np.nan,resampling=Resampling.bilinear)
    reproject(valid.astype('float32'),coverage,src_transform=src_transform,src_crs=ds.crs,dst_transform=dst_transform,dst_crs=ds.crs,dst_nodata=0,resampling=Resampling.bilinear)
    output_valid=np.isfinite(out)&(coverage>=1-1e-6);out[~output_valid]=np.nan
    np.savez_compressed(O/(tile+'.npz'),height=out,valid=output_valid)
    cache=RangeFile(url).root
    result={'tile':tile,'status':'DSM_DECODED_NOT_ADMITTED','url':url,'sourceCRS':str(ds.crs),'sourceDimensions':[ds.width,ds.height],'sourceBounds':list(ds.bounds),'sourceTransform':list(ds.transform),'sourceNoData':ds.nodata,'sourceUnits':ds.units,'sourceTags':ds.tags(),'overviewFactors':ds.overviews(1),'decodedShape':[n,n],'decodedTransform':list(dst_transform),'outputPixelInterpretation':'AREA-grid target sample centres, explicitly reprojected from source Point registration','processing':'Bounded COG bilinear overview read, followed by registered target-grid bilinear reprojection; invalid coverage remains NaN','units':'metres per Copernicus DEM provider documentation','invalidPixelCount':int((~output_valid).sum()),'sourceValidZeroPixels':int((output_valid&(out==0)).sum()),'minimumMetres':float(np.nanmin(out)) if output_valid.any() else None,'maximumMetres':float(np.nanmax(out)) if output_valid.any() else None,'heightArraySha256':hashlib.sha256(out.tobytes()).hexdigest(),'validMaskSha256':hashlib.sha256(output_valid.tobytes()).hexdigest(),'npzSha256':hashlib.sha256((O/(tile+'.npz')).read_bytes()).hexdigest(),'rangeCacheBytes':sum(p.stat().st_size for p in cache.glob('*.bin')),'sourceETag':json.loads((cache/'header.json').read_text()).get('etag'),'sourceWholeFileSha256':None,'priorIncheonFullSourceHash':'f530dd28308ecd6c5ceb0405dc1ffb7113bcafdec30d023de50f16dc433a274f' if tile=='N37E126' else None,'historicalTerrainClaim':False,'gutterPrepared':False,'neighborhoodMaskPrepared':False,'validityScope':'DECODED_SAMPLE_VALIDITY_ONLY','nativeContributorCompletenessVerified':False,'productionAdmitted':False,'caveat':'Valid source-provided0 is not an invented fill. Modern DSM includes buildings/vegetation and provider editing; overview-scale validity is not a native30m exhaustive survey.'}
    path.write_text(json.dumps(result,indent=2)+'\n');return {k:result[k] for k in ['tile','status','decodedShape','invalidPixelCount','minimumMetres','maximumMetres','rangeCacheBytes']}
 except Exception as e:
  result={'tile':tile,'status':'BLOCKED','error':str(e),'productionAdmitted':False};path.write_text(json.dumps(result,indent=2)+'\n');return result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(acquire,rows):print(json.dumps(result),flush=True)
