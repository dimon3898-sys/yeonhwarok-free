"""Fail-closed reusable decoded receipt checks; never modifies source artifacts."""
import hashlib,json,pathlib

def reusable_receipt(path, *, status, url, shape, keys, bounds):
 try:
  import numpy as np
  p=pathlib.Path(path);m=json.loads(p.read_text());blob=p.with_suffix('.npz').read_bytes()
  if m.get('status')!=status or m.get('url')!=url or m.get('decodedShape')!=shape:return False
  if hashlib.sha256(blob).hexdigest()!=m.get('npzSha256'):return False
  if m.get('sourceCRS')!='EPSG:4326':return False
  n=shape[-1];w,s,e,north=bounds;t=m['decodedTransform']
  expected=[(e-w)/n,0,w,0,-(north-s)/n,north,0,0,1]
  if len(t)!=9 or any(abs(float(a)-b)>1e-10 for a,b in zip(t,expected)):return False
  with np.load(p.with_suffix('.npz'),allow_pickle=False) as z:
   for key,digest,expected_shape in keys:
    a=z[key]
    if list(a.shape)!=expected_shape or hashlib.sha256(a.tobytes()).hexdigest()!=m.get(digest):return False
  return True
 except (OSError,ValueError,KeyError,TypeError,ImportError):return False
