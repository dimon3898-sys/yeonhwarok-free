from pathlib import Path
from PIL import Image,ImageDraw
import json,gzip,hashlib,subprocess
p=Path(__file__).resolve().parent.parent
r=p/'repair-a2';out=r/'probe';frames=json.loads(gzip.decompress((out/'FRAME_EVIDENCE.json.gz').read_bytes()))['frames'];old={x['frame']:x for x in json.loads(gzip.decompress((p/'cpu-a1/FRAME_EVIDENCE.json.gz').read_bytes()))['frames']}
receipt=json.loads((out/'CAPTURE_RECEIPT.json').read_text());assert receipt['status']=='ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO';assert len(frames)==11
rows=[]
for f in frames:
 d=f['diagnostic'];assert d['glError']==0;assert d['material']['fullViewportCovered'];assert f['baseRawSHA256']==old[f['frame']]['baseRawSHA256'];assert d['camera']['bounds']==old[f['frame']]['diagnostic']['camera']['bounds'];
 assert d['presentationLabels']==old[f['frame']]['diagnostic']['presentationLabels'];
 rows.append({'frame':f['frame'],'baseMapPixelsIdentical':True,'cameraBoundsIdentical':True,'labelsIdentical':True,'rawSHA256':f['rawSHA256'],'rings':d.get('locationRings'),'feature':next((x for x in d['features'] if x['id']=='ILLUSTRATIVE_ROUTE'),None)})
last=[x for x in frames if x['frame']>=149];assert len(set(x['rawSHA256'] for x in last))==1
(r/'PROBE_TECHNICAL_REVIEW.json').write_text(json.dumps({'status':'PASS','scope':'11 new effect probe frames; preserved A1 base pixel hashes used as evidence, no old capture','exactFinalHoldSamples':[149,150,179],'rows':rows},indent=2)+'\n')
selection=[9,15,60,90,96,120,143,149]
canvas=Image.new('RGB',(270*4,510*2),'#171b26');draw=ImageDraw.Draw(canvas)
for i,f in enumerate(selection):
 im=Image.open(out/f'FRAME_{f:03d}.png').resize((270,480),Image.Resampling.LANCZOS);x=i%4*270;y=i//4*510;canvas.paste(im,(x,y+30));draw.text((x+8,y+8),f'V3 revised | f{f:03d}',fill='white')
canvas.save(r/'PROBE_MOBILE_CONTACT.jpg',quality=94)
canvas=Image.new('RGB',(540*3,510),'#171b26');draw=ImageDraw.Draw(canvas)
for i,f in enumerate([9,90,149]):
 oldpng=r/f'BEFORE_{f:03d}.png';
 if not oldpng.exists():subprocess.run(['ffmpeg','-v','error','-i',str(p/'cpu-a1/VIDEO.mp4'),'-vf',f'select=eq(n\\,{f}),scale=270:480','-frames:v','1',str(oldpng)],check=True)
 a=Image.open(oldpng);b=Image.open(out/f'FRAME_{f:03d}.png').resize((270,480),Image.Resampling.LANCZOS);x=i*540;canvas.paste(a,(x,30));canvas.paste(b,(x+270,30));draw.text((x+8,8),f'BEFORE f{f:03d}',fill='white');draw.text((x+278,8),f'AFTER f{f:03d}',fill='white')
canvas.save(r/'PROBE_BEFORE_AFTER.jpg',quality=95)
print('11 probe frames: base map, camera, labels and sampled hold verified')
