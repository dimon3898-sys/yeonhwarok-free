from pathlib import Path
import json,gzip,hashlib,subprocess,math
from PIL import Image,ImageDraw
import numpy as np
p=Path(__file__).resolve().parents[2];r=p/'repair-a2';out=r/'final';qa=r/'final-review';qa.mkdir(exist_ok=True)
read=lambda file:json.loads(gzip.decompress(file.read_bytes())) if file.suffix=='.gz' else json.loads(file.read_text())
receipt=read(out/'CAPTURE_RECEIPT.json');assert receipt['status']=='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED';video=receipt['video'];assert (video['width'],video['height'],video['fps'],video['frames'],video['durationSeconds'])==(1080,1920,30,180,6);assert video['fullDecode']=='PASS';assert hashlib.sha256((out/'VIDEO.mp4').read_bytes()).hexdigest()==video['sha256'];
rows=read(out/'FRAME_EVIDENCE.json.gz')['frames'];old=read(p/'cpu-a1/FRAME_EVIDENCE.json.gz')['frames'];probe=read(r/'probe/FRAME_EVIDENCE.json.gz')['frames'];assert len(rows)==180
safe=[48,72,1032,1848];roiOk=lambda b:b[0]>=safe[0] and b[1]>=safe[1] and b[2]<=safe[2] and b[3]<=safe[3]
summary=[]
for f,row in enumerate(rows):
 assert row['frame']==f;d=row['diagnostic'];od=old[f]['diagnostic'];assert d['glError']==0 and d['material']['fullViewportCovered'];assert row['baseRawSHA256']==old[f]['baseRawSHA256'];assert d['camera']['bounds']==od['camera']['bounds'];assert d['presentationLabels']==od['presentationLabels'];
 for label in d['presentationLabels']['drawn']:assert roiOk(label['box'])
 feature=next((x for x in d['features'] if x['id']=='ILLUSTRATIVE_ROUTE'),None)
 if feature:
  assert feature['routeFraction']>=feature['objectFraction'];assert feature['objectPosition']==old[f]['diagnostic']['features'][0]['objectPosition'];assert feature['admission'];
  for box in feature['draw']['rois']:assert roiOk(box)
 for ring in d['locationRings']:assert roiOk(ring['draw']['roi'])
 summary.append({'frame':f,'labelIds':[x['id'] for x in d['presentationLabels']['drawn']],'objectFraction':feature['objectFraction'] if feature else None,'rings':[{'id':x['id'],'radius':x['draw']['radius'],'alpha':x['draw']['alpha']} for x in d['locationRings']]})
assert len(set(x['rawSHA256'] for x in rows[149:]))==1
for row in probe:assert rows[row['frame']]['rawSHA256']==row['rawSHA256']
result={'status':'PASS','video':video,'baseMapPixelsIdenticalToPreservedA1Frames':180,'cameraAndLabelRecordsIdenticalToA1Frames':180,'routeObjectPositionsIdenticalToA1':True,'allEffectAndLabelBoundsInsideSafeArea':True,'probePixelsReproducedExactly':len(probe),'finalHoldRawFramesIdentical':31,'softwareBackend':receipt['runtime']['backend'],'renderSeconds':receipt['elapsedSeconds'],'gpuExecutions':0,'paidKRW':0,'oldPASSExecutions':0,'visualReview':'PENDING_ACTUAL_MP4_FRAME_CONTACT_REVIEW','summary':summary}
(qa/'TECHNICAL_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
# Read the encoded MP4 once for visual inspection; no re-render of any source.
import tempfile
dec=Path(tempfile.mkdtemp(prefix='world-engine-v3-review-'))
subprocess.run(['ffmpeg','-v','error','-i',str(out/'VIDEO.mp4'),'-vsync','0',str(dec/'f_%03d.png')],check=True)
files=sorted(dec.glob('f_*.png'));assert len(files)==180
for batch in range(6):
 canvas=Image.new('RGB',(1080,1720),'#171b26');draw=ImageDraw.Draw(canvas)
 for i,f in enumerate(range(batch*30,(batch+1)*30)):
  im=Image.open(files[f]).resize((180,320),Image.Resampling.LANCZOS);x=i%6*180;y=i//6*344;canvas.paste(im,(x,y+24));draw.text((x+6,y+5),f'f{f:03d}',fill='white')
 canvas.save(qa/f'ALL_FRAMES_{batch*30:03d}_{batch*30+29:03d}.jpg',quality=91)
selection=[0,15,45,75,94,120,143,179]
canvas=Image.new('RGB',(1080,1020),'#171b26');draw=ImageDraw.Draw(canvas)
for i,f in enumerate(selection):
 x=i%4*270;y=i//4*510;canvas.paste(Image.open(files[f]).resize((270,480),Image.Resampling.LANCZOS),(x,y+30));draw.text((x+10,y+8),f'{f/30:.2f}s | f{f:03d}',fill='white')
canvas.save(qa/'JAPAN_V3_REPRESENTATIVE_FRAMES.jpg',quality=95)
# Existing V2 video is only decoded for comparison; no V2 generator execution.
v2=p.parent/'japan-6s-v2-20261113/cpu-a3/VIDEO.mp4'
canvas=Image.new('RGB',(1620,510),'#171b26');draw=ImageDraw.Draw(canvas)
for i,f in enumerate([15,90,149]):
 before=qa/f'V2_FRAME_{f:03d}.png'
 if not before.exists():subprocess.run(['ffmpeg','-v','error','-i',str(v2),'-vf',f'select=eq(n\\,{f}),scale=270:480','-frames:v','1',str(before)],check=True)
 canvas.paste(Image.open(before),(i*540,30));canvas.paste(Image.open(files[f]).resize((270,480),Image.Resampling.LANCZOS),(i*540+270,30));draw.text((i*540+10,8),f'V2 | f{f:03d}',fill='white');draw.text((i*540+280,8),f'V3 FINAL | f{f:03d}',fill='white')
canvas.save(qa/'V2_V3_COMPARISON.jpg',quality=95)
print(json.dumps({k:v for k,v in result.items() if k!='summary'},indent=2))
