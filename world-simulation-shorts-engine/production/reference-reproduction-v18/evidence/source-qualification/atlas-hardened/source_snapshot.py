"""Immutable byte capture, affine checks and reproducible classification pairing."""
import hashlib,json,io,pathlib
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest()
class Snapshot:
 def __init__(self):self.files={};self.inventories={}
 def read(self,path):
  p=pathlib.Path(path).resolve();b=p.read_bytes();h=sha(b)
  if str(p) in self.files and self.files[str(p)]['sha256']!=h:raise ValueError('INPUT_CHANGED_DURING_CAPTURE')
  self.files[str(p)]={'sha256':h,'bytes':len(b)}
  return b
 def json(self,p):return json.loads(self.read(p))
 def arrays(self,p):
  with np.load(io.BytesIO(self.read(p)),allow_pickle=False) as z:return {k:z[k] for k in z.files}
 def inventory(self,p,pattern):
  paths=sorted(pathlib.Path(p).glob(pattern));self.inventories[(str(p),pattern)]=[str(x) for x in paths];return paths
 def verify(self):
  for (p,pat),paths in self.inventories.items():
   if paths!=[str(x) for x in sorted(pathlib.Path(p).glob(pat))]:raise ValueError('INPUT_INVENTORY_CHANGED')
  for p,r in self.files.items():
   b=pathlib.Path(p).read_bytes()
   if len(b)!=r['bytes'] or sha(b)!=r['sha256']:raise ValueError('INPUT_CHANGED_BEFORE_PUBLICATION')
def check_grid(m,shape):
 if m.get('sourceCRS')!='EPSG:4326':raise ValueError('GRID_CRS')
 h,w=shape;W,S,E,N=m['sourceBounds'];t=m['decodedTransform'];expected=[(E-W)/w,0,W,0,-(N-S)/h,N,0,0,1]
 if len(t)!=9 or not np.isfinite(t).all() or not np.allclose(t,expected,rtol=0,atol=1e-10):raise ValueError('GRID_AFFINE_MISMATCH')
 tile=m['tile'];lat=int(tile[1:3]);lon=int(tile[4:7]);span=3 if 'sourceShape' in m else 1
 if not np.allclose([W,S,E,N],[lon,lat,lon+span,lat+span],rtol=0,atol=1e-10):raise ValueError('GRID_TILE_EDGE_MISMATCH')
 if list(m['decodedShape'][-2:])!=[h,w]:raise ValueError('GRID_SHAPE')
def paired_masks(optical,classification,classes):
 n=optical['decodedShape'][-1];check_grid(optical,(n,n));check_grid(classification,classes.shape)
 W,S,E,N=optical['sourceBounds'];cw,cs,ce,cn=classification['sourceBounds'];h,w=classes.shape
 x=W+(np.arange(n)+.5)*(E-W)/n;y=N-(np.arange(n)+.5)*(N-S)/n
 # Exact integer ratio follows the existing documented nearest-center tie rule.
 sx=np.floor((x-cw)/(ce-cw)*w+1e-10).astype(int);sy=np.floor((cn-y)/(cn-cs)*h+1e-10).astype(int)
 if np.any(sx<0) or np.any(sx>=w) or np.any(sy<0) or np.any(sy>=h):raise ValueError('CLASSIFICATION_COVERAGE')
 c=classes[np.ix_(sy,sx)];unknown=(c==0)|(c==90);water=c==80;land=np.isin(c,[10,20,30,40,50,60,70,95,100])
 if not np.all(unknown.astype(int)+water.astype(int)+land.astype(int)==1):raise ValueError('UNKNOWN_CLASS_VALUE')
 return dict(classes=c,knownLand=land,classifiedPermanentWater=water,unknown=unknown)
def verify_pair(stored,expected):
 if set(stored)!=set(expected) or any(not np.array_equal(stored[k],a) for k,a in expected.items()):raise ValueError('PAIRED_MASK_PARENT_MISMATCH')
