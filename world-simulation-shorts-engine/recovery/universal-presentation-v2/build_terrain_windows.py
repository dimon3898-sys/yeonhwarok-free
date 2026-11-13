"""Reproducible crops/downsampling of a pinned geographic raster; never upscale."""
import hashlib,json,math,pathlib,sys
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
spec_path=pathlib.Path(sys.argv[1]);spec=json.loads(spec_path.read_text());repo=pathlib.Path(sys.argv[2]);original=pathlib.Path(sys.argv[3])
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=original.read_bytes();assert sha(raw)==spec['sourceOriginal']['sha256']
im=Image.open(original).convert('RGB');assert list(im.size)==spec['sourceOriginal']['dimensions']
parent=spec['sourceOriginal'];w,s,e,n=parent['bounds'];dx=(e-w)/im.width;dy=(n-s)/im.height
levels=[]
for window in spec['windows']:
    west,south,east,north=window['bounds']
    pixels=[round((west-w)/dx),round((n-north)/dy),round((east-w)/dx),round((n-south)/dy)]
    crop=im.crop(pixels);size=window['dimensions'];assert size[0]<=crop.width and size[1]<=crop.height
    if list(crop.size)!=size:crop=crop.resize(size,Image.Resampling.LANCZOS)
    out=repo/window['file'];out.parent.mkdir(parents=True,exist_ok=True);crop.save(out,compress_level=6)
    data=out.read_bytes()
    levels.append({'id':window['id'],'file':window['file'],'sha256':sha(data),'bytes':len(data),'dimensions':size,
        'bounds':window['bounds'],'pixelSpacing':[(east-west)/size[0],(north-south)/size[1]],'CRS':'EPSG:4326','NoData':None,
        'classification':'BAKED HILLSHADE','license':spec['license'],'sourceOriginalSHA256':parent['sha256'],
        'parentSHA256':[parent['sha256']],'method':'EXACT_NATIVE_PIXEL_WINDOW' if list(crop.size)==[pixels[2]-pixels[0],pixels[3]-pixels[1]] else 'SOURCE_WINDOW_DOWNSAMPLE_NO_UPSCALE',
        'sourcePixelBox':pixels,'decodedRGBSHA256':sha(crop.tobytes())})
manifest={'schema':'WORLD_ENGINE_GEOGRAPHIC_TERRAIN_PYRAMID_V1','epoch':parent['epoch'],'attribution':spec['attribution'],
    'sourcePage':spec['sourcePage'],'parents':[parent],'levels':levels,'upscaling':False,'newElevation':False}
out=repo/spec['manifestFile'];out.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'manifest':spec['manifestFile'],'manifestSHA256':sha(out.read_bytes()),'levels':[{k:v for k,v in l.items() if k in ['id','bytes','sha256','dimensions']} for l in levels]}))
