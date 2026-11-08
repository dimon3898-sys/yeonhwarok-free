"""Bind bounded alternate inspection reuse to parents, coordinates, code and actual bytes."""
import pathlib,json,hashlib,numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest()
def binding(root,tile,url,n,coords,algorithm):
 p=pathlib.Path(root)
 parents={f:sha((p/f).read_bytes()) for f in ['WORLDCOVER_GRID_SELECTION.json','TRISTATE_SOURCE_MASK_AUDIT.json',f'land_overviews/{tile}.npz',f'land_overviews/{tile}_classification_masks.npz']}
 return {'schema':'ALTERNATE_SOURCE_BINDING_V1','tile':tile,'url':url,'samplesPerDegree':n,'coordinates':coords,'parentFileSha256':parents,'algorithmSha256':sha(pathlib.Path(algorithm).read_bytes()),'cacheVerifierSha256':sha(pathlib.Path(__file__).read_bytes())}
def reusable(path,expected):
 try:
  p=pathlib.Path(path);d=json.loads(p.read_text())
  if d.get('status')!='ACTUAL_ALTERNATE_INSPECTED' or d.get('sourceBinding')!=expected or d.get('url')!=expected['url']:return False
  entries=d['entries']
  if [e['overviewPixel'] for e in entries]!=expected['coordinates']:return False
  for e in entries:
   x,y=e['overviewPixel'];name=f"{expected['tile']}_{x}_{y}.npz"
   if e['file']!=name:return False
   f=p.parent/name
   if f.is_symlink() or sha(f.read_bytes())!=e.get('npzSha256'):return False
   with np.load(f,allow_pickle=False) as a:
    if sha(a['data'].tobytes())!=e['arraySha256'] or sha(a['invalid'].tobytes())!=e['maskSha256']:return False
    n=expected['samplesPerDegree'];xa=x*12000/n;xb=(x+1)*12000/n;ya=y*12000/n;yb=(y+1)*12000/n
    x0=int(np.floor(xa));x1=int(np.ceil(xb));y0=int(np.floor(ya));y1=int(np.ceil(yb))
    if e['nativeWindow']!=[x0,y0,x1-x0,y1-y0] or list(a['data'].shape)!=[4,y1-y0,x1-x0] or list(a['invalid'].shape)!=[y1-y0,x1-x0]:return False
    wx=np.minimum(np.arange(x0,x1)+1,xb)-np.maximum(np.arange(x0,x1),xa);wy=np.minimum(np.arange(y0,y1)+1,yb)-np.maximum(np.arange(y0,y1),ya);w=wy[:,None]*wx[None,:]
    full=not bool((a['invalid']&(w>0)).any());value=np.rint((a['data']*w[None,:,:]).sum(axis=(1,2))/w.sum()).astype('uint16').tolist() if full else None
    if e['completeValidTargetCell']!=full or e['areaWeightedFourBandValue']!=value:return False
  return d['completeValidCells']==sum(e['completeValidTargetCell'] for e in entries) and d['totalCells']==len(entries)
 except (OSError,ValueError,KeyError,TypeError):return False
