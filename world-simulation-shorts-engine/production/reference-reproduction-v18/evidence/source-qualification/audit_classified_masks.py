import json,pathlib,numpy as np
P=pathlib.Path(__file__).parent;reports=[];cache={}
for f in sorted((P/'land_overviews').glob('*.json')):
 r=json.loads(f.read_text())
 if r.get('status')!='DECODED_NOT_ADMITTED':continue
 tile=r['tile'];lat=int(tile[1:3]);lon=int(tile[4:7]);parent=f'N{lat//3*3:02d}E{lon//3*3:03d}';mf=P/'water_classification'/(parent+'.json')
 if not mf.exists():continue
 m=json.loads(mf.read_text())
 if m.get('status')!='DECODED_CLASSIFICATION_NOT_SHORELINE_ADMISSION':continue
 if parent not in cache:cache[parent]=np.load(mf.with_suffix('.npz'))['classes']
 classes=cache[parent];pn=classes.shape[0]//3;n=r['decodedShape'][1];ratio=pn//n;assert pn%n==0 and ratio>0
 off=ratio//2;y=(lat//3*3+3-lat-1)*pn;x=(lon-lon//3*3)*pn;c=classes[y+off:y+pn:ratio,x+off:x+pn:ratio];assert c.shape==(n,n)
 z=np.load(f.with_suffix('.npz'));invalid=z['invalid'];unknown=(c==0)|(c==90);water=c==80;land=~(unknown|water);assert np.all(unknown.astype(int)+water.astype(int)+land.astype(int)==1)
 gaps=invalid&land;ys,xs=np.where(gaps);bb=None
 if len(xs):bb=[lon+float(xs.min())/n,lat+1-float(ys.max()+1)/n,lon+float(xs.max()+1)/n,lat+1-float(ys.min())/n]
 np.savez_compressed(P/'land_overviews'/(tile+'_classification_masks.npz'),knownLand=land,classifiedPermanentWater=water,unknown=unknown,classes=c)
 reports.append({'tile':tile,'classificationTile':parent,'decodedSize':n,'classifiedLandPixels':int(land.sum()),'classifiedPermanentWaterPixels':int(water.sum()),'unknownOrWetlandPixels':int(unknown.sum()),'invalidOpticalClassifiedLandPixels':int(gaps.sum()),'invalidOpticalWaterPixels':int((invalid&water).sum()),'invalidOpticalUnknownPixels':int((invalid&unknown).sum()),'invalidClassifiedLandBounds':bb,'classSourceCaveat':'Annual categorical map may misclassify shadows; wetlands and0 kept unknown. Nearest overview labels are not all-native-pixel water proof.','productionAdmitted':False})
out={'schema':'WORLD_ENGINE_TRISTATE_SOURCE_MASK_AUDIT_V1','pairedTileCount':len(reports),'tilesWithInvalidClassifiedLand':[r['tile'] for r in reports if r['invalidOpticalClassifiedLandPixels']>0],'triStatePolicy':'Use optical only where valid and classified land. Preserve real baseline for water/unknown; unknown is never silently reclassified as ocean. Invalid classified land blocks detailed-source admission.','tiles':reports,'productionAdmitted':False,'gpuStarts':0,'renders':0}
(P/'TRISTATE_SOURCE_MASK_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='tiles'}));print(json.dumps(reports))
