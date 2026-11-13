"""Acquire pinned NASA sources and prepare bounded geographic LOD windows. Not a renderer."""
from pathlib import Path
from PIL import Image
import hashlib,json,sys,urllib.request
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
CACHE=Path(sys.argv[1]);CACHE.mkdir(parents=True,exist_ok=True)
OUT=HERE/'sources';OUT.mkdir(exist_ok=True)
Image.MAX_IMAGE_PIXELS=500000000
BASE='https://assets.science.nasa.gov/content/dam/science/esd/eo/images/bmng/bmng-topography/september/'
PARENTS=[('world.topo.200409.3x21600x10800.jpg',22910406,'d38f6099976e9ce91d45cfc3a48a24a78ef2a8deb4c0242b75a0b884b76d45fa'),('world.topo.200409.3x21600x21600.B1.jpg',44642882,'54a26d629807658931ca087457ac7cb86bc8c9052f3540ccea20d0a2aab2b75d'),('world.topo.200409.3x21600x21600.C1.jpg',87922071,'6ceaebad2002f41eaee31c1894caf177141a8c4a27c535f78bed19273f0eb87f')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,size,digest in PARENTS:
 p=CACHE/name
 if not p.exists():
  with urllib.request.urlopen(BASE+name,timeout=90) as response,p.with_suffix('.download').open('xb') as out:
   total=0
   while chunk:=response.read(1024*1024):
    total+=len(chunk);assert total<=size,'SOURCE_SIZE_EXCEEDED';out.write(chunk)
  p.with_suffix('.download').rename(p)
 assert p.stat().st_size==size and sha(p)==digest,'NASA_SOURCE_HASH_MISMATCH'
# Coordinates are based on the companion actual GeoTIFF tags, archived separately.
registration=json.loads((OUT/'GEOTIFF_REGISTRATION.json').read_text())
for row in registration:assert 4326 in row['tags']['34735'] and row['tags']['34735'][11]==1
levels=[('overview',[-50,-55,70,75],60,1),('regional',[-27,0,30,63],120,2),('detail',[-15,18,9,48],240,1)]
receipts=[]
for name,bounds,ppd,down in levels:
 p=OUT/(name+'.png');west,south,east,north=bounds
 if name=='overview':
  with Image.open(CACHE/PARENTS[0][0]) as im:
   assert im.size==(21600,10800) and im.mode=='RGB'
   crop=im.crop(tuple(round(v) for v in [(west+180)*60,(90-north)*60,(east+180)*60,(90-south)*60]))
  parent=[PARENTS[0][2]];method='EXACT_NATIVE_PIXEL_WINDOW'
 else:
  canvas=Image.new('RGB',(round((east-west)*240),round((north-south)*240)))
  for tile,tw,te in [(PARENTS[1],-90,0),(PARENTS[2],0,90)]:
   left=max(west,tw);right=min(east,te)
   if right<=left:continue
   with Image.open(CACHE/tile[0]) as im:
    assert im.size==(21600,21600) and im.mode=='RGB'
    piece=im.crop(tuple(round(v) for v in [(left-tw)*240,(90-north)*240,(right-tw)*240,(90-south)*240]))
   canvas.paste(piece,(round((left-west)*240),0));piece.close()
  crop=canvas if down==1 else canvas.resize((canvas.width//down,canvas.height//down),Image.Resampling.BOX)
  if down!=1:canvas.close()
  parent=[PARENTS[1][2],PARENTS[2][2]];method='SOURCE_GRID_JOIN_AT_ZERO_LONGITUDE'+('_BOX_2X_NATIVE_DOWNSAMPLE' if down==2 else '_NO_RESAMPLE')
 assert max(crop.size)<=8192
 decoded=hashlib.sha256(crop.tobytes()).hexdigest()
 if not p.exists():crop.save(p,format='PNG',compress_level=6)
 with Image.open(p) as saved:assert saved.mode=='RGB' and saved.size==crop.size and hashlib.sha256(saved.tobytes()).hexdigest()==decoded,'LOD_OUTPUT_CHANGED'
 receipts.append({'id':name,'file':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size,'dimensions':list(crop.size),'bounds':bounds,'pixelSpacing':[1/ppd,1/ppd],'CRS':'EPSG:4326','NoData':None,'classification':'BAKED HILLSHADE','license':'NASA Earth Observatory image-use policy','sourceOriginalSHA256':parent[0],'parentSHA256':parent,'method':method,'decodedRGBSHA256':decoded})
 print(json.dumps({'level':name,'dimensions':crop.size,'sha256':receipts[-1]['sha256'],'bytes':p.stat().st_size}),flush=True);crop.close()
result={'schema':'WORLD_ENGINE_GEOGRAPHIC_TERRAIN_PYRAMID_V1','epoch':'2004-09','attribution':'NASA Earth Observatory, Blue Marble Next Generation (September 2004); country vectors: Natural Earth contributors.','sourcePage':'https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-topography/','usageURL':'https://www.nasa.gov/nasa-brand-center/images-and-media/','parents':[{'name':n,'url':BASE+n,'bytes':z,'sha256':h}for n,z,h in PARENTS],'levels':receipts,'historicalOwnershipClaimed':False,'upscaling':False,'newElevation':False}
p=OUT/'TERRAIN_PYRAMID.json'
if p.exists():assert json.loads(p.read_text())==result,'PINNED_PYRAMID_CHANGED'
else:p.write_text(json.dumps(result,indent=2)+'\n')
