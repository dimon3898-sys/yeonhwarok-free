#!/usr/bin/env python3
"""Decode ALL source frames once and measure conservative map-only proxies.

Analysis only: never imports or changes a renderer; never writes source video,
raw frame dumps or phone UI imagery. Metrics are not semantic GIS segmentation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image

EXPECTED_SHA='5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6'
SOURCE_SIZE=(1080,2520)
ANALYSIS_SIZE=(270,630)
MAP_RECT=(0,212,1080,2120)
EXCLUDED_RECTS=[
 {'role':'RIGHT_YOUTUBE_CONTROLS','box':[925,1050,1080,2120]},
 {'role':'VARIABLE_KOREAN_SUBTITLE_BAND','box':[140,1410,930,1635]},
 {'role':'IDENTITY_CAPTION_COMMENT_FOOTER','box':[0,1840,1080,2120]},
]
CAMERA_ROI=(12,235,445,905)


def sha_file(file):
 h=hashlib.sha256()
 with Path(file).open('rb') as source:
  for part in iter(lambda:source.read(1024*1024),b''):h.update(part)
 return h.hexdigest()


def box_mask(box):
 w,h=ANALYSIS_SIZE
 x=(np.arange(w)+.5)*SOURCE_SIZE[0]/w
 y=(np.arange(h)+.5)*SOURCE_SIZE[1]/h
 return ((y[:,None]>=box[1])&(y[:,None]<box[3])&(x[None,:]>=box[0])&(x[None,:]<box[2]))


def hsv(rgb):
 high=rgb.max(axis=2);low=rgb.min(axis=2);delta=high-low
 safe=np.maximum(delta,1e-6);hue=np.zeros_like(high)
 for channel,offset in [(0,0),(1,2),(2,4)]:
  use=(high==rgb[:,:,channel])&(delta>1e-6)
  values=((rgb[:,:,(channel+1)%3]-rgb[:,:,(channel+2)%3])/safe+offset)*60
  hue[use]=values[use]
 return hue%360,delta/np.maximum(high,1e-6),high


def dilate(mask,radius=2):
 result=mask.copy();padded=np.pad(mask,radius)
 for dy in range(radius*2+1):
  for dx in range(radius*2+1):result|=padded[dy:dy+mask.shape[0],dx:dx+mask.shape[1]]
 return result


def phase_shift(previous,current,mask):
 """Consecutive translation proxy; rotation/zoom/occlusion can lower confidence."""
 usable=mask&(previous>.02)&(current>.02)
 if usable.sum()<64:return {'status':'INSUFFICIENT_TEXTURE'}
 def highpass(value):
  lap=4*value-np.roll(value,1,0)-np.roll(value,-1,0)-np.roll(value,1,1)-np.roll(value,-1,1)
  result=(lap-lap[usable].mean())*usable
  return result*np.hanning(value.shape[0])[:,None]*np.hanning(value.shape[1])[None,:]
 a,b=highpass(previous),highpass(current)
 cross=np.fft.fft2(b)*np.conj(np.fft.fft2(a));cross/=np.maximum(np.abs(cross),1e-12)
 correlation=np.fft.ifft2(cross).real
 y,x=np.unravel_index(int(np.argmax(correlation)),correlation.shape)
 dx=x if x<=correlation.shape[1]//2 else x-correlation.shape[1]
 dy=y if y<=correlation.shape[0]//2 else y-correlation.shape[0]
 around=correlation.copy()
 for oy in range(-2,3):
  for ox in range(-2,3):around[(y+oy)%around.shape[0],(x+ox)%around.shape[1]]=0
 peak=float(correlation[y,x]);second=float(around.max())
 return {'status':'MEASURED_TRANSLATION_PROXY_ONLY','dxSourcePixels':int(dx*4),'dySourcePixels':int(dy*4),
  'phasePeak':round(peak,6),'peakToSecond':round(peak/max(second,1e-9),4),
  'usableFraction':round(float(usable.mean()),6),'exactCameraPoseClaimed':False}


def intervals(rows,predicate,minimum_seconds=.15):
 result=[];start=None
 for i,row in enumerate(rows):
  yes=bool(predicate(row))
  if yes and start is None:start=i
  if start is not None and (not yes or i==len(rows)-1):
   end=i if yes and i==len(rows)-1 else i-1
   duration=rows[end]['ptsSeconds']-rows[start]['ptsSeconds']
   if duration>=minimum_seconds:result.append({'startFrame':start,'endFrame':end,
    'startSeconds':rows[start]['ptsSeconds'],'endSeconds':rows[end]['ptsSeconds'],'sampleSpanSeconds':round(duration,6)})
   start=None
 return result


def analyze(source,*,expected_sha=EXPECTED_SHA,samples_directory=None):
 digest=sha_file(source)
 if digest!=expected_sha:raise ValueError('REFERENCE_SOURCE_SHA_MISMATCH')
 probe_command=['ffprobe','-v','error','-select_streams','v:0','-show_entries',
  'frame=best_effort_timestamp_time,pkt_duration_time','-show_entries',
  'stream=width,height,nb_frames,duration,r_frame_rate,avg_frame_rate','-show_entries','format=duration','-of','json',str(source)]
 probe=json.loads(subprocess.run(probe_command,check=True,capture_output=True,text=True).stdout)
 stream=probe['streams'][0]
 if (stream['width'],stream['height'])!=SOURCE_SIZE:raise ValueError('UNEXPECTED_REFERENCE_DIMENSIONS')
 pts=[float(row['best_effort_timestamp_time']) for row in probe['frames']]
 if any(b<=a for a,b in zip(pts,pts[1:])):raise ValueError('NONINCREASING_PTS')
 content=box_mask(MAP_RECT)
 for excluded in EXCLUDED_RECTS:content&=~box_mask(excluded['box'])
 roi=box_mask(CAMERA_ROI)&content
 roi_y,roi_x=np.where(roi);ry=slice(roi_y.min(),roi_y.max()+1);rx=slice(roi_x.min(),roi_x.max()+1)
 total=int(content.sum());rows=[];previous=None;previous_gray=None;previous_hue=None;previous_phase_mask=None;first=None;first_hash=None
 frame_bytes=SOURCE_SIZE[0]*SOURCE_SIZE[1]*3;full_sha=hashlib.sha256()
 command=['ffmpeg','-hide_banner','-loglevel','error','-xerror','-err_detect','explode','-threads','2',
  '-i',str(source),'-map','0:v:0','-an','-sn','-dn','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
 samples={int(np.argmin(np.abs(np.array(pts)-s))):s for s in range(0,32,3)}
 if samples_directory is not None:Path(samples_directory).mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryFile() as stderr:
  process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=stderr)
  try:
   index=0
   while True:
    raw=bytearray()
    while len(raw)<frame_bytes:
     part=process.stdout.read(frame_bytes-len(raw))
     if not part:break
     raw.extend(part)
    if not raw:break
    if len(raw)!=frame_bytes:raise ValueError('TRUNCATED_NATIVE_FRAME')
    if index>=len(pts):raise ValueError('DECODE_FRAME_COUNT_EXCEEDS_PTS')
    full_sha.update(raw)
    small=np.asarray(Image.frombytes('RGB',SOURCE_SIZE,bytes(raw)).resize(ANALYSIS_SIZE,Image.Resampling.BOX),dtype=np.float32)/255
    hue,saturation,value=hsv(small);r,g,b=small[:,:,0],small[:,:,1],small[:,:,2]
    orange=content&(((hue<38)|(hue>345))&(saturation>.5)&(value>.15))
    purple=content&((hue>=250)&(hue<=315)&(saturation>.42)&(value>.14))
    gold=content&(r>.60)&(g>.42)&(b<.60)&(r>b*1.2)&(g>b*1.2)&(value>.65)
    white=content&(small.min(axis=2)>.70)&(saturation<.18)
    sea=content&(hue>=165)&(hue<=235)&(saturation>.2)&(value>.10)
    gray=small@np.array([.2126,.7152,.0722],dtype=np.float32)
    edge_x=np.abs(np.diff(gray,axis=1));edge_y=np.abs(np.diff(gray,axis=0))
    eligible_x=content[:,1:]&content[:,:-1];eligible_y=content[1:,:]&content[:-1,:]
    phase_mask=roi&~orange&~purple&~gold&~white
    fractions={'orangeHue':orange,'purpleHue':purple,'goldBright':gold,'whiteBright':white,'blueCyanWaterLike':sea}
    row={'frame':index,'ptsSeconds':pts[index],'deltaPTSSeconds':None if index==0 else round(pts[index]-pts[index-1],6),
     'nativeRGBSHA256':hashlib.sha256(raw).hexdigest(),
     'mapLumaMean':round(float(gray[content].mean()*255),4),'mapLumaStd':round(float(gray[content].std()*255),4),
     'mapGradientMean':round(float((edge_x[eligible_x].mean()+edge_y[eligible_y].mean())*127.5),4),
     'fractions':{name:round(int(mask.sum())/total,7) for name,mask in fractions.items()},
     'goldAdjacentBothFactionHuesPixels':int((gold&dilate(orange)&dilate(purple)).sum()),
     'cameraTranslationProxy':None}
    row['hueCentroidsSourcePixels']={name:None if not mask.any() else [round(float(np.where(mask)[1].mean()*4+2),2),round(float(np.where(mask)[0].mean()*4+2),2)]
     for name,mask in [('orange',orange),('purple',purple)]}
    if previous is not None:
     difference=np.abs(small-previous)
     row.update(mapMeanAbsDelta=round(float(difference[content].mean()*255),5),
      mapChangedFractionOver5=round(float((difference.max(axis=2)[content]>5/255).mean()),7),
      hueClassFlipFraction=round(float(((orange!=previous_hue[0])|(purple!=previous_hue[1]))[content].mean()),7))
     row['cameraTranslationProxy']=phase_shift(previous_gray[ry,rx],gray[ry,rx],(phase_mask&previous_phase_mask)[ry,rx])
    else:
     row.update(mapMeanAbsDelta=None,mapChangedFractionOver5=None,hueClassFlipFraction=None)
     first=small.copy();first_hash=row['nativeRGBSHA256']
    row['mapMeanAbsDifferenceFromFirst']=round(float(np.abs(small-first)[content].mean()*255),5)
    if index in samples and samples_directory is not None:
     preview=np.clip(small*255,0,255).astype(np.uint8);preview[~content]=0
     Image.fromarray(preview).save(Path(samples_directory)/f'MAP_MASKED_{index:04d}.png')
    rows.append(row);previous=small;previous_gray=gray;previous_hue=(orange,purple);previous_phase_mask=phase_mask;index+=1
    if index%120==0:print(json.dumps({'phase':'FULL_NATIVE_DECODE_MAP_METRICS','decodedFrames':index}),flush=True)
   code=process.wait(timeout=30)
   stderr.seek(0);errors=stderr.read(65537)
   if code!=0 or errors:raise ValueError('FULL_REFERENCE_DECODE_FAILED')
  finally:
   if process.poll() is None:process.kill();process.wait(timeout=10)
   process.stdout.close()
 if len(rows)!=len(pts) or len(rows)!=int(stream['nb_frames']):raise ValueError('DECODE_FRAME_COUNT_MISMATCH')
 if sha_file(source)!=digest:raise ValueError('SOURCE_CHANGED_DURING_ANALYSIS')
 delta=np.array([r['mapMeanAbsDelta'] for r in rows[1:]])
 summary={'schema':'REFERENCE_FULL_MAP_TEMPORAL_ANALYSIS_V2','status':'FULL_DECODE_AND_METRICS_COMPLETE',
  'sourceName':Path(source).name,'sourceSHA256':digest,'sourceBytes':Path(source).stat().st_size,'sourceModified':False,
  'nativeDimensions':list(SOURCE_SIZE),'analysisDimensions':list(ANALYSIS_SIZE),'decodedFrames':len(rows),
  'containerDurationSeconds':float(probe['format']['duration']),'firstPTSSeconds':pts[0],'lastPTSSeconds':pts[-1],
  'strictIncreasingPTS':True,'ffmpegExitCode':code,'ffmpegErrorBytes':len(errors),'allDecodedRGBSHA256':full_sha.hexdigest(),
  'uiExclusion':{'sourceMapRectangle':list(MAP_RECT),'excludedRectangles':EXCLUDED_RECTS,
   'retainedAnalysisPixels':total,'retainedSourcePixelEquivalent':total*16,
   'maskPolicy':'CONSERVATIVE_FIXED_PHONE_UI_EXCLUSION_NOT_AN_INPAINTED_MAP','cameraROI':list(CAMERA_ROI)},
  'metricLimits':['Hue fractions are display proxies; badge colors, transient effects and camera changes remain possible contributors.',
   'Gold adjacent to both faction hues is a heuristic frontier-brightness proxy, not an exact boundary extractor.',
   'Translation estimates use consecutive texture phase correlation; zoom/roll/occlusion are not independently solved.',
   'No geographic position, exact territory area, physical lighting or exact camera pose is inferred.',
   'No reference pixels are available to any runtime, material, shader or public proof.'],
  'temporalSummary':{'meanFrameMapMAD':round(float(delta.mean()),5),'p50FrameMapMAD':round(float(np.median(delta)),5),
   'p95FrameMapMAD':round(float(np.percentile(delta,95)),5),'maxFrameMapMAD':round(float(delta.max()),5),
   'exactNativeConsecutiveDuplicateFrames':sum(a['nativeRGBSHA256']==b['nativeRGBSHA256'] for a,b in zip(rows,rows[1:])),
   'lowMotionRuns':intervals(rows,lambda r:r['mapMeanAbsDelta'] is not None and r['mapMeanAbsDelta']<.15 and r['mapChangedFractionOver5']<.002),
   'activeMotionRuns':intervals(rows,lambda r:r['mapMeanAbsDelta'] is not None and (r['mapMeanAbsDelta']>=.4 or r['mapChangedFractionOver5']>=.01)),
   'lastVersusFirstMapMAD':rows[-1]['mapMeanAbsDifferenceFromFirst'],
   'loopEqualityObserved':rows[-1]['nativeRGBSHA256']==first_hash},'frames':rows}
 return summary


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--expected-sha256',default=EXPECTED_SHA);parser.add_argument('--private-samples-directory',type=Path)
 args=parser.parse_args();report=analyze(args.input,expected_sha=args.expected_sha256,samples_directory=args.private_samples_directory)
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('x') as output:json.dump(report,output,indent=2);output.write('\n')
 print(json.dumps({'status':report['status'],'decodedFrames':report['decodedFrames'],'output':str(args.output)}))
