"""Audit saved V2 pixels and receipts. Does not invoke any renderer."""
import sys,json,gzip,hashlib,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
base=Path(__file__).parent;cap=base/sys.argv[1];out=base/(sys.argv[1]+'-review');out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((cap/'CAPTURE_RECEIPT.json').read_text());raw=gzip.decompress((cap/'FRAME_EVIDENCE.json.gz').read_bytes());assert hashlib.sha256(raw).hexdigest()==receipt['frameEvidence']['sha256']
frames=json.loads(raw)['frames'];r=json.loads((base/'RUNTIME_REQUEST.json').read_text());scene=r['segments'][0]['scene'];p=r['segments'][0]['presentation'];hold=scene['timing']['total_frames']-scene['timing']['final_hold_frames'];summary=[]
geometries={a['id']:next(g['geometry'] for g in scene['geometries'] if g['id']==a['geometry_ref']) for a in scene['areas']}
for f in frames:
 d=f['diagnostic'];assert d['glError']==0 and 'SwiftShader' in d['backend'];assert d['material']['fullViewportCovered'] and d['featureChangedPixels']>0
 labels=d['presentationLabels']['drawn'];assert len(labels)==3;year=next(l for l in labels if l['role']=='TIMELINE');assert all(l['box'][0]>=32 and l['box'][1]>=32 and l['box'][2]<=1048 and l['box'][3]<=1888 for l in labels)
 base_features=[x for x in d['features'] if x['engine']=='EXISTING_AREA_V3'];effects=[x for x in d['features'] if x['engine']=='EXISTING_AREA_V3_DIFFERENCE_OVERLAY'];assert len(base_features)+len(effects)==len(d['features'])
 areas=[a for x in base_features for a in x['sourceAreas']];assert areas
 for a in areas:assert a['geometry']==geometries[a['id']]
 assert all(not x['sourceFronts'] for x in base_features)
 if f['frame']>=hold:assert not effects
 summary.append({'frame':f['frame'],'year':year['text'],'states':[a['stateId'] for a in areas],'effectDraws':sum(len(x['draws']) for x in effects),'featureChangedPixels':d['featureChangedPixels'],'camera':d['camera']['center'],'rawSHA256':f['rawSHA256']})
video=cap/'VIDEO.mp4';w,h=270,480
if video.exists():
 assert sha(video)==receipt['video']['sha256'] and receipt['video']['frames']==180 and receipt['video']['fullDecode']=='PASS'
 assert [f['frame'] for f in frames]==list(range(180));assert len({f['rawSHA256'] for f in frames[hold-1:]})==1
 # Capture already certified encoding. Decode once here for the new pixel review.
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-vf',f'scale={w}:{h}:flags=area','-f','rawvideo','-pix_fmt','rgb24','-'])
 arr=np.frombuffer(raw,np.uint8).reshape((-1,h,w,3));assert len(arr)==180
 pages=[list(range(start,start+30)) for start in range(0,180,30)]
 for indices in pages:
  canvas=Image.new('RGB',(w*6,(h+28)*5),'#101722');draw=ImageDraw.Draw(canvas)
  for k,n in enumerate(indices):
   x=k%6*w;y=k//6*(h+28);canvas.paste(Image.fromarray(arr[n]),(x,y));draw.text((x+8,y+h+5),f'{n:03d} / {n/30:.2f}s',fill='white')
  canvas.save(out/f'ALL_FRAMES_{indices[0]:03d}_{indices[-1]:03d}.jpg',quality=87)
 indices=[0,32,49,67,87,106,124,179]
 for n in [0,32,67,87,124,179]:subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf',f'select=eq(n\\,{n})','-frames:v','1',str(out/f'ENCODED_FRAME_{n:03d}.png')],check=True)
else:
 indices=[f['frame'] for f in frames];arr={n:np.asarray(Image.open(cap/f'FRAME_{n:03d}.png').convert('RGB').resize((w,h))) for n in indices}
cols=4;canvas=Image.new('RGB',(w*cols,(h+28)*((len(indices)+cols-1)//cols)),'#101722');draw=ImageDraw.Draw(canvas)
for k,n in enumerate(indices):
 x=k%cols*w;y=k//cols*(h+28);canvas.paste(Image.fromarray(arr[n]),(x,y));draw.text((x+8,y+h+5),f'{n:03d} / {n/30:.2f}s',fill='white')
canvas.save(out/'REPRESENTATIVE_FRAMES.jpg',quality=94)
report={'status':'PASS_TECHNICAL_VISUAL_REVIEW_PENDING','actualFrames':len(frames),'runtimeSHA256':sha(base/'RUNTIME_REQUEST.json'),'captureSHA256':sha(cap/'CAPTURE_RECEIPT.json'),'sourceGeometryPreservedFrames':len(frames),'safeLabelFrames':len(frames),'effectFrames':sum(x['effectDraws']>0 for x in summary),'stableFinalHoldFrames':scene['timing']['final_hold_frames'] if video.exists() else None,'video':receipt.get('video'),'captureEncodingPassPreservedNotRerun':video.exists(),'summary':summary}
(out/'TECHNICAL_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='summary'}))
