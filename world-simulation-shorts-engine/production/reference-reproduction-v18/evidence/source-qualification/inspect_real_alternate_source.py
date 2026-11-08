import pathlib,json,concurrent.futures,numpy as np,rasterio,hashlib
from rasterio.windows import Window
from bounded_cog import RangeFile
from alternate_cache_integrity import binding,reusable
P=pathlib.Path(__file__).parent;O=P/'alternate_2020';O.mkdir(exist_ok=True)
catalog=json.loads((P/'WORLDCOVER_GRID_SELECTION.json').read_text())['records'];urls={r['tile']:r['s2_rgbnir_2020'] for r in catalog};audit=json.loads((P/'TRISTATE_SOURCE_MASK_AUDIT.json').read_text());rows=[r for r in audit['tiles'] if r['invalidOpticalClassifiedLandPixels']]
def inspect(r):
 tile=r['tile'];path=O/(tile+'.json')
 try:
  s3=urls[tile];bucket,key=s3[5:].split('/',1);url=f'https://{bucket}.s3.eu-central-1.amazonaws.com/{key}';target=tile+'_alternate2020.tif';z=np.load(P/'land_overviews'/(tile+'.npz'));m=np.load(P/'land_overviews'/(tile+'_classification_masks.npz'));ys,xs=np.where(z['invalid']&m['knownLand']);n=r['decodedSize'];entries=[]
  source_binding=binding(P,tile,url,n,[[int(x),int(y)] for y,x in zip(ys,xs)],__file__)
  if reusable(path,source_binding):return {'tile':tile,'status':'REUSED_VERIFIED_SUCCESS'}
  def opener(path,mode='rb'):
   if path!=target:raise FileNotFoundError(path)
   return RangeFile(url)
  with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
   with rasterio.open(target,opener=opener) as ds:
    assert ds.width==12000 and ds.height==12000 and str(ds.crs)=='EPSG:4326' and ds.count==4
    for y,x in zip(ys,xs):
     xa=x*ds.width/n;xb=(x+1)*ds.width/n;ya=y*ds.height/n;yb=(y+1)*ds.height/n;x0=int(np.floor(xa));x1=int(np.ceil(xb));y0=int(np.floor(ya));y1=int(np.ceil(yb))
     a=ds.read([1,2,3,4],window=Window(x0,y0,x1-x0,y1-y0),masked=True);data=a.filled(0);invalid=np.ma.getmaskarray(a).any(axis=0)
     wx=np.minimum(np.arange(x0,x1)+1,xb)-np.maximum(np.arange(x0,x1),xa);wy=np.minimum(np.arange(y0,y1)+1,yb)-np.maximum(np.arange(y0,y1),ya);weights=wy[:,None]*wx[None,:];full=not bool((invalid&(weights>0)).any());value=np.rint((data*weights[None,:,:]).sum(axis=(1,2))/weights.sum()).astype('uint16').tolist() if full else None
     filename=f'{tile}_{x}_{y}.npz';np.savez_compressed(O/filename,data=data,invalid=invalid)
     entries.append({'overviewPixel':[int(x),int(y)],'nativeWindow':[x0,y0,x1-x0,y1-y0],'nativePixelCount':int(invalid.size),'invalidNativePixels':int(invalid.sum()),'completeValidTargetCell':full,'areaWeightedFourBandValue':value,'sourceYear':2020,'arraySha256':hashlib.sha256(data.tobytes()).hexdigest(),'maskSha256':hashlib.sha256(invalid.tobytes()).hexdigest(),'file':filename,'npzSha256':hashlib.sha256((O/filename).read_bytes()).hexdigest(),'productionAdmitted':False})
    result={'tile':tile,'status':'ACTUAL_ALTERNATE_INSPECTED','url':url,'sourceYear':2020,'sourceBinding':source_binding,'sourceBounds':list(ds.bounds),'sourceTransform':list(ds.transform),'sourceTags':ds.tags(),'resampling':'Explicit area-weighted mean over actual native source pixels only when every contributing sample is valid','entries':entries,'completeValidCells':sum(e['completeValidTargetCell'] for e in entries),'totalCells':len(entries),'productionAdmitted':False,'caveat':'Real2020 alternative is a different-date modern source, not inpainting and not1950 imagery. Pixel/seam acceptance remains pending.'}
    path.write_text(json.dumps(result,indent=2)+'\n');return {k:result[k] for k in ['tile','status','completeValidCells','totalCells']}
 except Exception as e:
  result={'tile':tile,'status':'BLOCKED','error':str(e),'productionAdmitted':False};path.write_text(json.dumps(result,indent=2)+'\n');return result
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
 for r in pool.map(inspect,rows):print(json.dumps(r),flush=True)
