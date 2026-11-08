"""Inspect two actual minimum-height native neighborhoods; never rewrite DSM."""
import pathlib,json,numpy as np,rasterio,hashlib
from rasterio.windows import Window
from bounded_cog import RangeFile
P=pathlib.Path(__file__).parent;O=P/'dsm_extrema';O.mkdir(exist_ok=True);out=[]
for tile in ['N41E123','N38E125']:
 m=json.loads((P/'dsm_overviews'/(tile+'.json')).read_text());h=np.load(P/'dsm_overviews'/(tile+'.npz'))['height'];y,x=np.unravel_index(np.nanargmin(h),h.shape);n=h.shape[0];lon=int(tile[4:])+(x+.5)/n;lat=int(tile[1:3])+1-(y+.5)/n;target=tile+'_extrema.tif';url=m['url']
 def opener(path,mode='rb'):
  if path!=target:raise FileNotFoundError(path)
  return RangeFile(url)
 with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_PAM_ENABLED='NO'):
  with rasterio.open(target,opener=opener) as ds:
   row,col=ds.index(lon,lat);w=Window(max(0,col-20),max(0,row-20),41,41);a=ds.read(1,window=w,masked=True);data=a.filled(np.nan);invalid=np.ma.getmaskarray(a);np.savez_compressed(O/(tile+'.npz'),height=data,invalid=invalid)
   r={'tile':tile,'url':url,'overviewPixel':[int(x),int(y)],'overviewMinimumMetres':float(h[y,x]),'centerLonLat':[float(lon),float(lat)],'nativeWindow':[int(w.col_off),int(w.row_off),int(w.width),int(w.height)],'nativeMinimumMetres':float(a.min()),'nativeMaximumMetres':float(a.max()),'nativeInvalidSamples':int(invalid.sum()),'nativeArraySha256':hashlib.sha256(data.tobytes()).hexdigest(),'sourceBounds':list(ds.bounds),'sourceTransform':list(ds.transform),'productionAdmitted':False,'interpretation':'Actual native negative elevations confirmed if present; not evidence of physical correctness or historical terrain. No zero clamping.'};out.append(r);print(json.dumps(r),flush=True)
(P/'DSM_NATIVE_EXTREMA_INSPECTION.json').write_text(json.dumps(out,indent=2)+'\n')
