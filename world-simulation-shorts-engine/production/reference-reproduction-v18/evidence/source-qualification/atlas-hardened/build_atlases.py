import pathlib,json,hashlib,math,numpy as np
from PIL import Image
import io,os
from source_snapshot import Snapshot,check_grid,paired_masks,verify_pair
from cli_paths import parse_paths
args=parse_paths()
if args.check_paths:
 print(json.dumps(dict(sourceRoot=str(args.source_root),outputRoot=str(args.output_root),baselineReceipt=str(args.baseline_receipt))))
 raise SystemExit(0)
snapshot=Snapshot()
P=args.source_root; CODE=pathlib.Path(__file__).parent
FINAL=args.output_root;O=FINAL.with_name(FINAL.name+'.partial')
assert not FINAL.exists() and not O.exists(),'GENERATION_ALREADY_EXISTS'
O.mkdir(parents=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
def writej(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
frames=snapshot.json(P/'PRESERVED_FRAME_BOUNDS.json')['frames']
for r in frames:r['segment']=(r['part']-1)*2+r['frame']//150+1; r['segmentFrame']=r['frame']%150
baseline=next(s for s in snapshot.json(P/'REGION_SOURCE_CATALOG_PINNED.json')['sources'] if s['id']=='NASA_BMNG_KOREA_500M_NE10M_V2')
missing=['40 source-grid invalid optical known-land pixels across 7 tiles remain unresolved; atlas downsampling cannot waive this gate','Unknown classification, categorical overview shoreline suitability, source epoch and clouds require qualification','Acquisition authenticity and full upstream resampling reproduction not certified','LOD runtime binding, safe blending and source admission not implemented','DSM absent; no fabricated height, terrain mesh or lighting admission','No production admission, rendering or image build authorized']
plans=[]
def plan(part,role,ff,ppd=None):
 b=[min(r['bounds'][0] for r in ff),min(r['bounds'][1] for r in ff),max(r['bounds'][2] for r in ff),max(r['bounds'][3] for r in ff)]
 required=max(max(1080/(r['bounds'][2]-r['bounds'][0]),1920/(r['bounds'][3]-r['bounds'][1])) for r in ff)
 ppd=ppd or required
 # Preserve exact minimum density; ceil dimensions and enlarge eastern/southern edges only.
 w=math.ceil((b[2]-b[0])*ppd)+4;h=math.ceil((b[3]-b[1])*ppd)+4
 bounds=[b[0]-2/ppd,b[3]+2/ppd-h/ppd,b[0]-2/ppd+w/ppd,b[3]+2/ppd]
 assert max(w,h)<=4096
 return dict(part=part,role=role,dimensions=[w,h],bounds=bounds,pixelsPerDegree=ppd,required1xPixelsPerDegree=required,gutterPixels=2,firstFrame=min(r['frame'] for r in ff),lastFrame=max(r['frame'] for r in ff))
for part in range(1,5):
 ff=[r for r in frames if r['segment']==part]
 if part==1:
  plans+=[plan(part,'overview',ff,341),plan(part,'regional',[r for r in ff if r['segmentFrame']>=55])]
 else:plans.append(plan(part,'overview',ff))
writej(O/'GRID_PLAN.json',plans)
# Source inventory is snapshotted before sampling. No remote access.
opt=[];cls=[];evidence=[]
def collect(folder,target):
 for p in snapshot.inventory(P/folder,'*.json'):
  m=snapshot.json(p)
  if 'decodedShape' not in m:continue
  arrays=snapshot.arrays(p.with_suffix('.npz'));assert snapshot.files[str(p.with_suffix('.npz').resolve())]['sha256']==m['npzSha256'];check_grid(m,arrays['data' if 'data' in arrays else 'classes'].shape[-2:])
  key='data' if 'data' in arrays else 'classes';assert sha(arrays[key].tobytes())==m['arraySha256']
  cache=P/'range_cache'/sha(m['url'].encode());ranges=[]
  for rr in sorted(cache.glob('[0-9]*.json')):
   r=snapshot.json(rr);b=snapshot.read(rr.with_suffix('.bin'));assert sha(b)==r['sha256'] and len(b)==r['bytes'];ranges.append(dict(offset=r['start'],bytes=r['bytes'],sha256=r['sha256']))
  assert ranges
  source=dict(id=('opt_' if folder=='land_overviews' else 'class_')+m['tile'],sourceUrl=m['url'],license=m['sourceTags']['license'],attribution=m['sourceTags']['copyright'],sourceHashScope='BYTE_RANGES',sourceWholeFileSha256=None,rangeReceipts=ranges,grid=dict(kind='RASTER',crs=m['sourceCRS'],bounds=m['sourceBounds'],dimensions=m.get('sourceDimensions',list(reversed(m.get('sourceShape',[])))),pixelInterpretation='AREA'),processingMethod='COG_WINDOW_RESAMPLE')
  rec=dict(metadataFile=str(p),metadataSha256=snapshot.files[str(p.resolve())]['sha256'],npzFile=str(p.with_suffix('.npz')),npzSha256=m['npzSha256'],arrays={k:dict(shape=list(a.shape),dtype=str(a.dtype),sha256=sha(a.tobytes())) for k,a in arrays.items()},source=source,priorResampling=m['resampling'],decodedTransform=m['decodedTransform'])
  if folder=='land_overviews':
   mf=p.with_name(p.stem+'_classification_masks.npz');mm=snapshot.arrays(mf);rec['classificationMasksSha256']=snapshot.files[str(mf.resolve())]['sha256']
   lat=int(m['tile'][1:3]);lon=int(m['tile'][4:7]);ct=f'N{lat//3*3:02d}E{lon//3*3:03d}';cp=P/'water_classification'/(ct+'.json');cm=snapshot.json(cp);ca=snapshot.arrays(cp.with_suffix('.npz'))
   assert snapshot.files[str(cp.with_suffix('.npz').resolve())]['sha256']==cm['npzSha256'] and sha(ca['classes'].tobytes())==cm['arraySha256']
   expected=paired_masks(m,cm,ca['classes']);verify_pair(mm,expected)
   rec['pairedClassificationDerivation']=dict(parentMetadataSha256=snapshot.files[str(cp.resolve())]['sha256'],parentNpzSha256=cm['npzSha256'],parentArraySha256=cm['arraySha256'],parentDecodedTransform=cm['decodedTransform'],targetDecodedTransform=m['decodedTransform'],method='Nearest optical pixel center, floor index with 1e-10 numerical tie tolerance; exact array comparison',outputArrays={k:sha(v.tobytes()) for k,v in expected.items()})
   rec['invalidKnownLandSourcePixels']=int((arrays['invalid']&mm['knownLand']).sum());arrays['land']=mm['knownLand'];arrays['water']=mm['classifiedPermanentWater'];arrays['unknown']=mm['unknown']
  evidence.append(rec);target.append((m,arrays,source))
collect('land_overviews',opt);collect('water_classification',cls)

# Baseline input must arrive intact; this script may safely be rerun before any publication.
bp=P/'baseline_bmng.png';assert bp.exists(),'Baseline PNG pending';baseline_bytes=snapshot.read(bp);assert sha(baseline_bytes)==baseline['sha256']
base=np.asarray(Image.open(io.BytesIO(baseline_bytes)).convert('RGB'));assert list(reversed(base.shape[:2]))==baseline['dimensions']
base_source=dict(id='baseline_pinned_png',sourceUrl=baseline['sourceOriginal']['url'],license=baseline['license'],attribution=baseline['attribution'],sourceHashScope='WHOLE_FILE',sourceWholeFileSha256=baseline['sourceOriginal']['sha256'],grid=dict(kind='RASTER',crs='EPSG:4326',bounds=baseline['sourceOriginal']['bounds'],dimensions=baseline['sourceOriginal']['dimensions'],pixelInterpretation='AREA'),processingMethod='EXACT_SOURCE_DECODE')
baseline_receipt=snapshot.json(args.baseline_receipt)
assert baseline_receipt['derivedPngSha256']==baseline['sha256'] and baseline_receipt['sourceOriginalSha256']==baseline['sourceOriginal']['sha256']
evidence_doc=dict(schema='WORLD_ENGINE_SOURCE_EVIDENCE_INDEX_V1',sources=evidence,sourceInvalidKnownLand=sum(r.get('invalidKnownLandSourcePixels',0) for r in evidence),baselineCatalog=baseline,baselineMaterialization=baseline_receipt,inputFiles=snapshot.files.copy(),authenticity='PENDING',productionAdmitted=False)
assert evidence_doc['sourceInvalidKnownLand']==40,'SOURCE_GAP_CHECKPOINT_CHANGED_REQUIRES_REVIEW'
writej(O/'SOURCE_ARRAY_EVIDENCE.json',evidence_doc)
evidence_hash=sha((O/'SOURCE_ARRAY_EVIDENCE.json').read_bytes())
classes={'OPTICAL_RGB':'OPTICAL_RGB_NOT_BAKED','BAKED_BASEMAP_RGB':'BAKED_BASEMAP_NOT_OPTICAL','VALIDITY_MASK':'SOURCE_VALIDITY','KNOWN_LAND_MASK':'KNOWN_LAND','KNOWN_WATER_MASK':'KNOWN_WATER','UNKNOWN_MASK':'UNKNOWN_CLASSIFICATION','SELECTION_MASK':'SOURCE_SELECTION'}
reports=[]
for part in range(1,5):
 manifest=dict(schema='WORLD_ENGINE_DERIVED_SOURCE_CANDIDATE_V1',purpose='QUALIFICATION_ONLY',assets=[],receipts=[],products=[],layers=[],qualification=dict(state='PENDING',missingChecks=missing))
 manifest['receipts'].append(dict(file='SOURCE_ARRAY_EVIDENCE.json',sha256=evidence_hash,bytes=(O/'SOURCE_ARRAY_EVIDENCE.json').stat().st_size))
 def receipt(name,d):
  f=O/(name+'.json');writej(f,d);r=dict(file=f.name,sha256=sha(f.read_bytes()),bytes=f.stat().st_size)
  if not any(x['sha256']==r['sha256'] for x in manifest['receipts']):manifest['receipts'].append(r)
  return r['sha256']
 for p in [x for x in plans if x['part']==part]:
  stem=f"segment{part}_{p['role']}";w,h=p['dimensions'];west,south,east,north=p['bounds'];xs=west+(np.arange(w)+.5)*(east-west)/w;ys=north-(np.arange(h)+.5)*(north-south)/h
  def ij(bounds,shape):
   W,S,E,N=bounds;H,Wi=shape
   xi=np.flatnonzero((xs>=W)&(xs<E));yi=np.flatnonzero((ys>S)&(ys<=N));sx=np.floor((xs[xi]-W)/(E-W)*Wi).astype(int);sy=np.floor((N-ys[yi])/(N-S)*H).astype(int)
   assert np.all((sx>=0)&(sx<Wi)) and np.all((sy>=0)&(sy<H));return xi,yi,sx,sy
  ox=np.zeros((h,w,3),dtype=np.uint8);valid=np.zeros((h,w),dtype=bool);land=valid.copy();water=valid.copy();unknown=np.ones((h,w),dtype=bool);usedopt=[];usedclass=[]
  # Classification fills all covered geography, including cells without published optical.
  for m,a,s in cls:
   xi,yi,sx,sy=ij(m['sourceBounds'],a['classes'].shape)
   if len(xi)==0 or len(yi)==0:continue
   c=a['classes'][np.ix_(sy,sx)];idx=np.ix_(yi,xi);land[idx]=np.isin(c,[10,20,30,40,50,60,70,95,100]);water[idx]=c==80;unknown[idx]=~(land[idx]|water[idx]);usedclass.append(s)
  for m,a,s in opt:
   xi,yi,sx,sy=ij(m['sourceBounds'],a['invalid'].shape)
   if len(xi)==0 or len(yi)==0:continue
   idx=np.ix_(yi,xi);raw=a['data'][:3].transpose(1,2,0)[np.ix_(sy,sx)];ox[idx]=(np.clip(raw.astype(np.float32)/3000,0,1)*255).astype(np.uint8);valid[idx]=~a['invalid'][np.ix_(sy,sx)]
   # Keep class/validity pairing on the exact same optical decoded grid. Parent classification is nearest sampled at each optical pixel center.
   land[idx]=a['land'][np.ix_(sy,sx)];water[idx]=a['water'][np.ix_(sy,sx)];unknown[idx]=a['unknown'][np.ix_(sy,sx)];usedopt.append(s)
  xi,yi,sx,sy=ij(baseline['bounds'],base.shape[:2]);assert len(xi)==w and len(yi)==h
  bx=base[np.ix_(sy,sx)];bv=np.ones((h,w),dtype=np.uint8);sel=valid&land;out=np.where(sel[...,None],ox,bx)
  assert np.all(land.astype(int)+water.astype(int)+unknown.astype(int)==1)
  arrays={'rgb':out,'optical':ox,'baseline':bx,'baseline_valid':bv,'optical_valid':valid,'land':land,'water':water,'unknown':unknown,'selection':sel}
  for name,a in arrays.items():
   a=a.astype(np.uint8);f=O/(stem+'_'+name+'.raw');f.write_bytes(a.tobytes());manifest['assets'].append(dict(id=stem+'_'+name,file=f.name,sha256=sha(f.read_bytes()),bytes=f.stat().st_size,encoding='RGB8' if a.ndim==3 else 'MASK8',dimensions=[w,h],bounds=p['bounds'],crs='EPSG:4326'))
  kinds=dict(optical='OPTICAL_RGB',baseline='BAKED_BASEMAP_RGB',baseline_valid='VALIDITY_MASK',optical_valid='VALIDITY_MASK',land='KNOWN_LAND_MASK',water='KNOWN_WATER_MASK',unknown='UNKNOWN_MASK',selection='SELECTION_MASK')
  for name,kind in kinds.items():
   sources=[base_source] if name.startswith('baseline') else usedopt if name in ['optical','optical_valid'] else usedclass+usedopt
   upstream=receipt(stem+'_'+name+'_upstream',dict(schema='WORLD_ENGINE_DERIVED_SOURCE_INPUT_MANIFEST_V1',completeness='ALL_DECLARED_UPSTREAM_INPUTS',sources=sources))
   mapping='RGB8 = floor(255 * clip(uint16 RGB / 3000, 0, 1)); no adaptive mapping' if name=='optical' else 'Original baseline RGB8 unchanged; spatial nearest only' if name=='baseline' else 'Binary mask; tri-state pairing preserved from optical grid, class80 permanent water, class0/90 unknown; selection = valid AND knownLand'
   aid=stem+'_'+name;digest=next(a['sha256'] for a in manifest['assets'] if a['id']==aid)
   rh=receipt(aid+'_derivation',dict(schema='WORLD_ENGINE_LOCAL_DERIVATION_RECEIPT_V1',productKind=kind,sourceEvidenceSha256=evidence_hash,derivedArtifactSha256=digest,upstreamManifestSha256=upstream,resampling='NEAREST',colorMapping=mapping))
   manifest['products'].append(dict(id=aid+'_product',kind=kind,classification=classes[kind],assetId=aid,provenance=dict(acquisitionReceiptSha256=rh,upstreamManifestSha256=upstream,resampling='NEAREST',colorMapping=mapping)))
  layer=dict(role=p['role'],rgbAssetId=stem+'_rgb',composition='EXACT_MASK_SELECT_REAL_RGB',waterPolicy='PRESERVE_REAL_BASEMAP',invalidOpticalLandPolicy='PRESERVE_BASEMAP_AND_BLOCK_ADMISSION')
  for field,name in dict(opticalProductId='optical',baselineProductId='baseline',baselineValidityProductId='baseline_valid',opticalValidityProductId='optical_valid',knownLandMaskProductId='land',knownWaterMaskProductId='water',unknownMaskProductId='unknown',selectionProductId='selection').items():layer[field]=stem+'_'+name+'_product'
  manifest['layers'].append(layer)
  preview=Image.fromarray(out);preview.thumbnail((600,850));preview.save(O/(stem+'_source_preview.png'))
  yy,xx=np.where(~valid&land); gaps={}
  for y,x in zip(yy,xx):
   tile=f'N{int(ys[y]):02d}E{int(xs[x]):03d}';gaps[tile]=gaps.get(tile,0)+1
  reports.append(dict(**p,invalidKnownLandAtlasByTile=gaps,invalidKnownLandWithoutOpticalTile=sum(c for t,c in gaps.items() if not (P/'land_overviews'/(t+'.npz')).exists()),opticalPixels=int(sel.sum()),knownLandPixels=int(land.sum()),knownWaterPixels=int(water.sum()),unknownPixels=int(unknown.sum()),invalidOpticalKnownLandPixels=int((~valid&land).sum()),usedOpticalSources=len(usedopt),usedClassificationSources=len(usedclass)))
 writej(O/f'segment{part}_manifest.json',manifest)
 print('Completed',part,flush=True)
writej(O/'ATLAS_REPORT.json',dict(status='QUALIFICATION_REQUIRED',productionAdmitted=False,renderAllowed=False,imageBuildAllowed=False,sourceInvalidKnownLandPixels=sum(r.get('invalidKnownLandSourcePixels',0) for r in evidence),atlases=reports,missingChecks=missing))

# Publish only a complete generation; verify all captured inputs are unchanged.
snapshot.verify()
outputs={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(O.iterdir()) if p.is_file()}
writej(O/'GENERATION_INDEX.json',dict(schema='WORLD_ENGINE_IMMUTABLE_CANDIDATE_GENERATION_V1',files=outputs,sourceEvidenceSha256=evidence_hash,inputSnapshotStable=True,productionAdmitted=False,authenticity='PENDING'))
os.rename(O,FINAL)
print('Published isolated candidate generation:',FINAL,flush=True)
