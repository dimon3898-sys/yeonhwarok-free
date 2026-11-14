"""Inspect an already-produced new MP4 and ledger; never invoke a renderer."""
import gzip,hashlib,json,math,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
base=Path(__file__).parent;cap=base/'final-a1';out=base/'final-a1-review';out.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
r=json.loads((cap/'CAPTURE_RECEIPT.json').read_text());v=cap/'VIDEO.mp4'
assert r['status']=='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED' and r['softwareOnly'] and not r['paidExecuted']
assert sha(v.read_bytes())==r['video']['sha256'] and r['browserErrors']==[]
wire=gzip.decompress((cap/'FRAME_EVIDENCE.json.gz').read_bytes());assert sha(wire)==r['frameEvidence']['sha256']
rows=json.loads(wire)['frames'];assert [x['frame'] for x in rows]==list(range(180))
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-show_frames','-show_entries','frame=best_effort_timestamp_time,width,height:stream:format','-of','json',str(v)]));s=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (s['width'],s['height'],s['r_frame_rate'],s['codec_name'])==(1080,1920,'30/1','h264');assert len(probe['frames'])==180 and abs(float(probe['format']['duration'])-6)<1e-6
assert all(abs(float(f['best_effort_timestamp_time'])-i/30)<1e-5 for i,f in enumerate(probe['frames']))
w,h=270,480;raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(v),'-vf',f'scale={w}:{h}:flags=area','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-']);assert len(raw)==180*w*h*3
pixels=np.frombuffer(raw,np.uint8).reshape(180,h,w,3)
def sheet(indices,name,columns=5):
 im=Image.new('RGB',(columns*w,math.ceil(len(indices)/columns)*(h+24)),'#101722');d=ImageDraw.Draw(im)
 for j,f in enumerate(indices):
  x=j%columns*w;y=j//columns*(h+24);im.paste(Image.fromarray(pixels[f]),(x,y+24));d.text((x+7,y+6),f'{f:03d} | {f/30:.3f}s',fill='white')
 im.save(out/name,quality=90)
for start in range(0,180,30):sheet(list(range(start,start+30)),f'ALL_{start:03d}_{start+29:03d}.jpg',6)
sheet([0,15,26,27,53,78,79,105,130,131,149,179],'KEY_FRAMES.jpg',4)
merc=lambda a:180/math.pi*math.log(math.tan(math.pi/4+math.radians(a)/2))
project=lambda p,q:[540+(q[0]-p['center'][0])*p['scale'],960-(merc(q[1])-merc(p['center'][1]))*p['scale']]
summary=[];prev=None
for row in rows:
 d=row['diagnostic'];f=row['frame'];assert d['glError']==0 and d['material']['fullViewportCovered'] and d['material']['sourceReliefDetail']=='SOURCE_RELIEF_V1'
 p=d['camera']['actualFactory']['pose'];assert p==d['camera']['state']['pose']
 labels=d['presentationLabels']['drawn'];assert all(48<=l['box'][0]<l['box'][2]<=1032 and 72<=l['box'][1]<l['box'][3]<=1848 for l in labels)
 for i,a in enumerate(labels):
  for b in labels[i+1:]:
   aa,bb=a['box'],b['box'];assert not (min(aa[2],bb[2])>max(aa[0],bb[0]) and min(aa[3],bb[3])>max(aa[1],bb[1]))
 effects=[e for x in d['features'] if x['id']=='TERRITORY_DIFFERENCES_V2' for e in x['draws']];moving=[e for e in effects if e['kind']=='moving_boundary']
 assert all(e['draw']['style']['AREA']['glowGain']>0 for e in moving)
 assert not d['physicalContext']['modernBordersAdded'] and not d['physicalContext']['historicalCitiesAdded']
 delta=max(math.dist(project(p,a),project(prev,a)) for a in [[90,43],[118,57],[104,50],[105,35],[120,20]]) if prev else 0
 summary.append({'frame':f,'rawSHA256':row['rawSHA256'],'pose':p,'cameraMaxAnchorStepPx':delta,'movingDrawCount':len(moving),'movingAlpha':max([e['alpha'] for e in moving],default=0),'terrainSHA256':d['material']['terrainSHA256'],'safeLabels':len(labels),'decodedMeanRGB':float(pixels[f].mean()),'mapMeanRGBDelta':float(np.abs(pixels[f].astype(np.int16)-pixels[f-1].astype(np.int16)).mean()) if f else 0});prev=p
hold=next(i for i in range(180) if len({x['rawSHA256'] for x in summary[i:]})==1)
result={'status':'NEW_MP4_TECHNICAL_PASS_VISUAL_REVIEW_REQUIRED','video':r['video'],'backend':r['runtime']['backend'],'ledgerFrames':180,'decodedFrames':180,'labelSafeAndNonOverlappingFrames':180,'sourceCoveredFrames':180,'cameraScaleRatio':summary[-1]['pose']['scale']/summary[0]['pose']['scale'],'cameraMaxAnchorStepPx':max(x['cameraMaxAnchorStepPx'] for x in summary),'frame27AnchorStepPx':summary[27]['cameraMaxAnchorStepPx'],'cameraHoldFrames':48,'rawStableHoldStart':hold,'rawStableHoldFrames':180-hold,'movingBoundaryFrames':[x['frame'] for x in summary if x['movingDrawCount']],'sourceLevelChangeFrames':[b['frame'] for a,b in zip(summary,summary[1:]) if a['terrainSHA256']!=b['terrainSHA256']],'oldPassReruns':0,'gpuStarts':0,'rendererRunsByReview':0,'referenceVisualQualityPass':False,'userVisualApproval':'PENDING','summary':summary}
(out/'FULL_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');(out/'FFPROBE.json').write_text(json.dumps(probe,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['summary','movingBoundaryFrames']},indent=2))
