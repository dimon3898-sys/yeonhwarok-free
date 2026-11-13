"""Inspect actual encoded frames and saved formal-runtime evidence; never render."""
import sys,json,gzip,hashlib,subprocess,io
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
base=Path(__file__).parent;cap=base/sys.argv[1];out=base/'final-review';out.mkdir(exist_ok=False)
video=cap/'VIDEO.mp4';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)]));stream=next(s for s in info['streams'] if s['codec_type']=='video')
assert (stream['width'],stream['height'],stream['r_frame_rate'],stream['nb_read_frames'])==(1080,1920,'30/1','180');assert abs(float(info['format']['duration'])-6)<.00001
subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True,capture_output=True)
credit=info['format']['tags']['copyright'];assert 'Cliopatria' in credit and 'CC BY 4.0' in credit and 'v0.2.1' in credit and 'NASA' in credit
ledger=json.loads(gzip.decompress((cap/'FRAME_EVIDENCE.json.gz').read_bytes()));frames=ledger['frames'];assert [f['frame'] for f in frames]==list(range(180))
r=json.loads((base/'RUNTIME_REQUEST.json').read_text());scene=r['segments'][0]['scene'];geometries={a['id']:next(g['geometry'] for g in scene['geometries'] if g['id']==a['geometry_ref']) for a in scene['areas']}
summary=[]
for f in frames:
 d=f['diagnostic'];assert d['glError']==0 and 'SwiftShader' in d['backend'];assert d['material']['fullViewportCovered'] and d['featureChangedPixels']>0
 labels=d['presentationLabels']['drawn'];assert len(labels)==3;year=next(l for l in labels if l['role']=='TIMELINE');assert all(l['box'][0]>=32 and l['box'][1]>=32 and l['box'][2]<=1048 and l['box'][3]<=1888 for l in labels)
 features=d['features'];assert all(x['engine']=='EXISTING_AREA_V3' for x in features)
 areas=[a for x in features for a in x['sourceAreas']];assert 1<=len(areas)<=2
 for a in areas:assert a['geometry']==geometries[a['id']]
 assert all(not x['sourceFronts'] for x in features)
 style=features[0]['draws'][0]['draw']['style']['AREA'];assert style['coreColor'][3]>0 and style['glowGain']>0
 summary.append({'frame':f['frame'],'year':year['text'],'states':[a['stateId'] for a in areas],'alpha':[a['alpha'] for a in areas],'featureChangedPixels':d['featureChangedPixels'],'visibleLabels':len(labels),'sourceLevel':d['material']['terrainSHA256'],'camera':d['camera']['center']})
assert len({f['rawSHA256'] for f in frames[135:]})==1
# Every encoded frame is decoded for differences and contact inspection.
w,h=270,480;raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-vf',f'scale={w}:{h}:flags=area','-f','rawvideo','-pix_fmt','rgb24','-']);arr=np.frombuffer(raw,np.uint8).reshape((-1,h,w,3));assert len(arr)==180
diff=np.abs(arr[1:].astype(np.int16)-arr[:-1].astype(np.int16)).mean(axis=(1,2,3));pixel={ 'meanConsecutiveRGBDelta':float(diff.mean()),'maxConsecutiveRGBDelta':float(diff.max()),'maxDeltaFrame':int(diff.argmax()+1),'finalHoldMeanDelta':float(diff[135:].mean())}
for start in range(0,180,30):
 canvas=Image.new('RGB',(w*6,(h+28)*5),'#101722');draw=ImageDraw.Draw(canvas)
 for k in range(30):
  n=start+k;x=k%6*w;y=k//6*(h+28);canvas.paste(Image.fromarray(arr[n]),(x,y));draw.text((x+8,y+h+5),f'{n:03d} / {n/30:.2f}s',fill='white')
 canvas.save(out/f'ALL_FRAMES_{start:03d}_{start+29:03d}.jpg',quality=86)
indices=[0,30,54,70,86,102,134,179];canvas=Image.new('RGB',(w*4,(h+28)*2),'#101722');draw=ImageDraw.Draw(canvas)
for k,n in enumerate(indices):
 x=k%4*w;y=k//4*(h+28);canvas.paste(Image.fromarray(arr[n]),(x,y));draw.text((x+8,y+h+5),f'{n:03d} / {summary[n]["year"]}',fill='white')
canvas.save(out/'MONGOL_EMPIRE_REPRESENTATIVE_FRAMES.jpg',quality=94)
for n in [0,54,102,179]:
 subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf',f'select=eq(n\\,{n})','-frames:v','1',str(out/f'ENCODED_FRAME_{n:03d}.png')],check=True)
receipt=json.loads((cap/'CAPTURE_RECEIPT.json').read_text());report={'status':'PASS_TECHNICAL_NOT_USER_VISUAL_APPROVAL','video':{'sha256':sha(video),'bytes':video.stat().st_size,'frames':180,'width':1080,'height':1920,'fps':30,'seconds':6,'fullDecode':'PASS'},'sourceGeometryPreservedFrames':180,'frameLabelAndCoordinateRuntimeChecks':180,'stableFinalHoldFrames':45,'paidGPUExecutions':0,'oldPASSReruns':0,'actualPixelStatistics':pixel,'runtimeReceipt':receipt['status'],'visualReview':'PENDING_ENCODED_CONTACT_AND_FULL_FRAME_REVIEW','summary':summary}
(out/'TECHNICAL_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(out/'FFPROBE.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='summary'},ensure_ascii=False))
