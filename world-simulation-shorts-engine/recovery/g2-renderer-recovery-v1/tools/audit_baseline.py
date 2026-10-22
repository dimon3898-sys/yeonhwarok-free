from pathlib import Path
import subprocess,json,hashlib,csv,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path('/workspace/yeonhwarok-free-studio-startup/world-simulation-shorts-engine/recovery/universal-source-pipeline-v2')
OUT=Path('/workspace/g2-recovery-baseline-video');framesDir=OUT/'decoded-frames';framesDir.mkdir(exist_ok=False)
video=ROOT/'public-review/WORLD_ENGINE_UNIVERSAL_SOURCE_DEMO_6S.mp4';sha=hashlib.sha256(video.read_bytes()).hexdigest()
assert sha=='39c7fd94af3a228bb66b7543aadee843bdd1a4443ba436e858b21327b70abcca'
capture=json.loads((ROOT/'reports/ACTUAL_CAPTURE_REPORT.json').read_bytes())
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-show_frames','-of','json',str(video)]))
assert len(probe['streams'])==1
stream=probe['streams'][0];assert stream['codec_name']=='h264' and [stream['width'],stream['height']]==[1080,1920] and stream['avg_frame_rate']=='30/1' and stream['nb_frames']=='180'
pts=[float(f['best_effort_timestamp_time']) for f in probe['frames']];assert len(pts)==180 and all(abs(t-i/30)<1e-6 for i,t in enumerate(pts))
cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-xerror','-i',str(video),'-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def exact_read(n):
 parts=[];done=0
 while done<n:
  b=p.stdout.read(n-done)
  if not b:break
  parts.append(b);done+=len(b)
 return b''.join(parts)
def pix_x(lon,b):return (lon-b[0])/(b[2]-b[0])*1080

def pix_y(lat,b):return (b[3]-lat)/(b[3]-b[1])*1920

def vertical_score(a,x,y0,y1):
 x=int(round(x));lo=max(0,min(y0,y1));hi=min(1920,max(y0,y1));
 left=a[lo:hi,x-6:x-2].astype(np.float32).mean(axis=1);right=a[lo:hi,x+2:x+6].astype(np.float32).mean(axis=1)
 rowdiff=np.abs(right-left).mean(axis=1)
 return float(np.median(rowdiff)),float(rowdiff.mean())

def horizontal_score(a,y,x0,x1):
 y=int(round(y));lo=max(0,min(x0,x1));hi=min(1080,max(x0,x1));
 top=a[y-6:y-2,lo:hi].astype(np.float32).mean(axis=0);bottom=a[y+2:y+6,lo:hi].astype(np.float32).mean(axis=0)
 rowdiff=np.abs(bottom-top).mean(axis=1)
 return float(np.median(rowdiff)),float(rowdiff.mean())

rows=[];controlsV=[];controlsH=[];started=time.monotonic()
for i in range(180):
 raw=exact_read(1080*1920*3);assert len(raw)==1080*1920*3,(i,len(raw))
 a=np.frombuffer(raw,dtype=np.uint8).reshape(1920,1080,3)
 b=capture['frames'][i]['diagnostic']['actualCamera']['bounds'];x=pix_x(104,b);y=pix_y(7,b)
 y0,y1=[int(round(pix_y(lat,b))) for lat in [31,22]]
 x0,x1=[int(round(pix_x(lon,b))) for lon in [112,116]]
 vm,vmean=vertical_score(a,x,y0,y1);hm,hmean=horizontal_score(a,y,x0,x1)
 vc=[vertical_score(a,x+delta,y0,y1)[0] for delta in [-72,-36,-18,18,36,72]]
 hc=[horizontal_score(a,y+delta,x0,x1)[0] for delta in [-72,-36,-18,18,36,72]]
 controlsV.extend(vc);controlsH.extend(hc)
 name=f'{i:03d}.png';Image.fromarray(a).save(framesDir/name,optimize=False)
 rows.append({'frame':i,'pts':pts[i],'decodedRGBSHA256':hashlib.sha256(raw).hexdigest(),'decodedPNG':name,'decodedPNGSHA256':hashlib.sha256((framesDir/name).read_bytes()).hexdigest(),
 'seamXProjected':x,'seamYProjected':y,'verticalLatitudeBand':[22,31],'horizontalLongitudeBand':[112,116],
 'verticalMedianAbsRgbJump':vm,'verticalMeanAbsRgbJump':vmean,'horizontalMedianAbsRgbJump':hm,'horizontalMeanAbsRgbJump':hmean,
 'verticalControlScores':vc,'horizontalControlScores':hc,
 'blackPixelFraction':float(np.mean(np.all(a<=2,axis=2))),'meanLuminanceRgb8':float(a.mean()),'cameraBounds':b})
assert p.stdout.read(1)==b''
stderr=p.stderr.read().decode();code=p.wait();assert code==0,(code,stderr)
thresholdV=float(np.percentile(controlsV,99));thresholdH=float(np.percentile(controlsH,99))
for r in rows:
 r['verticalDetectedAboveControlP99']=r['verticalMedianAbsRgbJump']>thresholdV
 r['horizontalDetectedAboveControlP99']=r['horizontalMedianAbsRgbJump']>thresholdH

def summary(key,score,threshold):
 hits=[r['frame'] for r in rows if r[key]]
 intervals=[]
 for value in hits:
  if intervals and value==intervals[-1][1]:intervals[-1][1]=value+1
  else:intervals.append([value,value+1])
 return {'predictedSourceEdgeVisibleFrames':[0,180],'thresholdControlP99':threshold,'detectedFrames':len(hits),'firstDetectedFrame':min(hits) if hits else None,
 'detectionFrameIntervalsHalfOpen':intervals,'detectedDurationSeconds':len(hits)/30,
 'minimumMeasuredMedianAbsRgbJump':min(r[score] for r in rows),'maximumMeasuredMedianAbsRgbJump':max(r[score] for r in rows),
 'manualVisualFrames':[0,90,179],'classification':'KNOWN_SOURCE_SUPPORT_BOUNDARY_DIFFERENCE_NOT_GENERIC_EDGE_DETECTOR'}
result={'schema':'WORLD_ENGINE_G2_RECOVERY_BASELINE_VIDEO_AUDIT_V1','status':'DECODE_AND_MEASURE_COMPLETE','sourceMP4SHA256':sha,'sourceMP4Bytes':video.stat().st_size,
 'codec':stream['codec_name'],'width':1080,'height':1920,'fps':'30/1','frames':len(rows),'durationSeconds':float(probe['format']['duration']),'audioStreams':0,
 'fullDecodeExitCode':code,'fullDecodeStderr':stderr,'ptsExactlySequential30fps':True,'decodedUniqueRGBFrames':len({r['decodedRGBSHA256'] for r in rows}),
 'method':{'edgeCoordinates':'Actual per-frame equirectangular projection of pinned regional terrain source West104° and South7°',
 'verticalRegion':'Latitude22..31 along104°; excludes control-area overlay in southern region and top caption',
 'horizontalRegion':'Longitude112..116 along7°; ocean-only support edge, away from controls/marker/caption',
 'scores':'Median over row/column mean absolute RGB8 difference between 4px strips on either side, offsets [-6,-2) and [+2,+6)',
 'controls':'Same geographic scanband at displacement[-72,-36,-18,+18,+36,+72]px. P99 learned from180×6 control scores per edge; no threshold tuned to recovered video.',
 'interpretation':'Pixel differences on a predicted source footprint support mechanism diagnosis with source code; natural edges elsewhere are not labeled tile defects. A weak score does not prove no defect.',
 'fullFramesSaved':'All180 decoded PNGs saved onlyin new scratch; no WORLD ENGINE redraw'},
 'verticalSourceBoundary':summary('verticalDetectedAboveControlP99','verticalMedianAbsRgbJump',thresholdV),
 'horizontalSourceBoundary':summary('horizontalDetectedAboveControlP99','horizontalMedianAbsRgbJump',thresholdH),
 'blackPixelFractionRange':[min(r['blackPixelFraction'] for r in rows),max(r['blackPixelFraction'] for r in rows)],
 'causes':{'sourceMaterialRectangle':'Prior report mechanism is confirmed separately against actual source/consumer code by material audit; this report measures decoded video support-edge pixels.',
 'staircase':'Source-authored0.25°grid fixture, not independently proved renderer quantization; source/domain audit required. No smoothing applied.'},
 'noRendererRedraw':True,'oldFilesModified':False,'paidGpuExecuted':False,'visualQualityApproved':False,'elapsedSeconds':time.monotonic()-started,'framesData':rows}
(OUT/'BASELINE_VIDEO_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
columns=['frame','pts','seamXProjected','seamYProjected','verticalMedianAbsRgbJump','horizontalMedianAbsRgbJump','verticalDetectedAboveControlP99','horizontalDetectedAboveControlP99','blackPixelFraction','decodedRGBSHA256','decodedPNGSHA256']
with (OUT/'BASELINE_FRAME_AUDIT.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
contact=Image.new('RGB',(1080,688),'#101820');d=ImageDraw.Draw(contact)
for idx,i in enumerate([0,90,179]):
 x=idx*360;im=Image.open(framesDir/f'{i:03d}.png').convert('RGB');contact.paste(im.resize((360,640),Image.Resampling.LANCZOS),(x,48));d.text((x+8,13),f'BASELINE actual f{i} / {i/30:.2f}s',font=font,fill='white')
contact.save(OUT/'BASELINE_ACTUAL_CONTACT.png')
print(json.dumps({k:result[k] for k in ['status','frames','decodedUniqueRGBFrames','verticalSourceBoundary','horizontalSourceBoundary','elapsedSeconds']}))
