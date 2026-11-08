import pathlib,json,hashlib,concurrent.futures,sys,time
import numpy as np,rasterio
from rasterio.enums import Resampling
from PIL import Image
from bounded_cog import RangeFile
from cache_integrity import reusable_receipt
P=pathlib.Path(__file__).parent;OUT=P/'land_overviews';OUT.mkdir(exist_ok=True)
plan=json.loads((P/('FINER_SOURCE_LOD_ACQUISITION_PLAN.json' if (P/'FINER_SOURCE_LOD_ACQUISITION_PLAN.json').exists() else 'SOURCE_LOD_ACQUISITION_PLAN.json')).read_text());urls=json.loads((P/'WORLDCOVER_GRID_INVENTORY.json').read_text())['sourceUrls']
rows=[r for r in plan['cells'] if r['mappedLandPresent'] or r.get('finerClassifiedLandPresent')];rows.sort(key=lambda x:(-x['powerOfTwoSamplesPerDegree'],x['tile']))
limit=int(sys.argv[1]) if len(sys.argv)>1 else len(rows);rows=rows[:limit]
def acquire(r):
 tile=r['tile'];receipt=OUT/(tile+'.json')
 n=r['powerOfTwoSamplesPerDegree'];bucket,key=urls[tile][5:].split('/',1);url=f'https://{bucket}.s3.eu-central-1.amazonaws.com/{key}';lat=int(tile[1:3]);lon=int(tile[4:7])
 if reusable_receipt(receipt,status='DECODED_NOT_ADMITTED',url=url,shape=[4,n,n],keys=[('data','arraySha256',[4,n,n]),('invalid','maskSha256',[n,n])],bounds=[lon,lat,lon+1,lat+1]):return {'tile':tile,'status':'REUSED_SUCCESS'}
 try:
  n=r['powerOfTwoSamplesPerDegree'];bucket,key=urls[tile][5:].split('/',1);url=f'https://{bucket}.s3.eu-central-1.amazonaws.com/{key}';target=tile+'.tif'
  def opener(path,mode='rb'):
   if path!=target:raise FileNotFoundError(path)
   return RangeFile(url)
  with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
   with rasterio.open(target,opener=opener) as ds:
    assert str(ds.crs)=='EPSG:4326' and ds.count==4 and ds.dtypes==('uint16',)*4,'SOURCE_METADATA_MISMATCH'
    a=ds.read([1,2,3,4],out_shape=(4,n,n),masked=True,resampling=Resampling.average)
    data=a.filled(0);mask=np.ma.getmaskarray(a).any(axis=0);transform=ds.transform*ds.transform.scale(ds.width/n,ds.height/n)
    np.savez_compressed(OUT/(tile+'.npz'),data=data,invalid=mask)
    rgb=np.moveaxis(np.clip(data[:3]/3000.,0,1),0,2);rgb[mask]=[1,0,1];Image.fromarray((rgb*255).astype('uint8')).save(OUT/(tile+'.png'))
    cache=RangeFile(url).root
    result={'tile':tile,'status':'DECODED_NOT_ADMITTED','url':url,'sourceDimensions':[ds.width,ds.height],'sourceDtypes':ds.dtypes,'sourceCRS':str(ds.crs),'sourceBounds':list(ds.bounds),'sourceNoData':ds.nodata,'overviewFactors':ds.overviews(1),'decodedShape':list(data.shape),'decodedTransform':list(transform),'resampling':'GDAL average using available COG overview','invalidPixelCount':int(mask.sum()),'invalidFraction':float(mask.mean()),'maskScope':'Invalid at decoded overview scale, not an exhaustive native 10m mask audit','arraySha256':hashlib.sha256(data.tobytes()).hexdigest(),'maskSha256':hashlib.sha256(mask.tobytes()).hexdigest(),'npzSha256':hashlib.sha256((OUT/(tile+'.npz')).read_bytes()).hexdigest(),'sourceTags':ds.tags(),'rangeCacheBytes':sum(p.stat().st_size for p in cache.glob('*.bin')),'sourceETag':json.loads((cache/'header.json').read_text()).get('etag'),'sourceWholeFileSha256':None,'previewMapping':'Fixed raw/3000 clipped; invalid pixels magenta, no inpainting','gutterPrepared':False,'productionAdmitted':False}
    receipt.write_text(json.dumps(result,indent=2)+'\n');return {k:result[k] for k in ['tile','status','decodedShape','invalidFraction','rangeCacheBytes']}
 except Exception as e:
  result={'tile':tile,'status':'ACQUISITION_BLOCKED','error':str(e),'productionAdmitted':False};receipt.write_text(json.dumps(result,indent=2)+'\n');return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(acquire,rows):print(json.dumps(r),flush=True)
print(json.dumps({'processed':len(rows),'successful':sum(json.loads((OUT/(r['tile']+'.json')).read_text()).get('status')=='DECODED_NOT_ADMITTED' for r in rows)}),flush=True)
