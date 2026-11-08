import pathlib,json,numpy as np,rasterio,hashlib
from rasterio.windows import Window
from bounded_cog import RangeFile
P=pathlib.Path(__file__).parent;O=P/'gap_native_inspection';O.mkdir(exist_ok=True);report=[]
audit=json.loads((P/'TRISTATE_SOURCE_MASK_AUDIT.json').read_text())
for entry in audit['tiles']:
 if not entry['invalidOpticalClassifiedLandPixels']:continue
 tile=entry['tile'];r=json.loads((P/'land_overviews'/(tile+'.json')).read_text());url=r['url'];z=np.load(P/'land_overviews'/(tile+'.npz'));m=np.load(P/'land_overviews'/(tile+'_classification_masks.npz'));ys,xs=np.where(z['invalid']&m['knownLand']);n=entry['decodedSize'];target=tile+'_native_gap.tif'
 def opener(path,mode='rb'):
  if path!=target:raise FileNotFoundError(path)
  return RangeFile(url)
 with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
  with rasterio.open(target,opener=opener) as ds:
   for y,x in zip(ys,xs):
    x0=int(np.floor(x*ds.width/n));x1=int(np.ceil((x+1)*ds.width/n));y0=int(np.floor(y*ds.height/n));y1=int(np.ceil((y+1)*ds.height/n));win=Window(x0,y0,x1-x0,y1-y0)
    a=ds.read([1,2,3,4],window=win,masked=True);data=a.filled(0);mask=np.ma.getmaskarray(a);name=f'{tile}_{x}_{y}.npz';np.savez_compressed(O/name,data=data,invalid=mask)
    e={'tile':tile,'overviewPixel':[int(x),int(y)],'nativeWindow':[x0,y0,x1-x0,y1-y0],'bounds':list(ds.window_bounds(win)),'nativeShape':list(data.shape),'nativeAnyBandInvalidCount':int(mask.any(axis=0).sum()),'nativePixelCount':int(data.shape[1]*data.shape[2]),'nativeBandInvalidCounts':mask.sum(axis=(1,2)).tolist(),'nativeAllBandsInvalidCount':int(mask.all(axis=0).sum()),'validValueMinPerBand':[int(a[i].min()) if a[i].count() else None for i in range(4)],'arraySha256':hashlib.sha256(data.tobytes()).hexdigest(),'maskSha256':hashlib.sha256(mask.tobytes()).hexdigest(),'file':name,'productionAdmitted':False}
    report.append(e);print(json.dumps(e),flush=True);(P/'NATIVE_MASK_DISAGREEMENT_INSPECTION.json').write_text(json.dumps({'status':'INSPECTION_ONLY_NOT_ADMITTED','entries':report},indent=2)+'\n')
