"""Read the new MP4 and its saved full-frame ledger. Never invokes a renderer."""
import gzip, hashlib, json, math, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

base=Path(__file__).parent
cap=base/'final-a1'
out=base/'final-a1-review'
out.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
video=cap/'VIDEO.mp4'
receipt=json.loads((cap/'CAPTURE_RECEIPT.json').read_text())
video_hash=sha(video.read_bytes())
assert video_hash==receipt['video']['sha256']
assert receipt['status']=='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'
assert receipt['softwareOnly'] and not receipt['paidExecuted']
assert 'SwiftShader' in receipt['runtime']['backend']
assert receipt['browserErrors']==[]
wire=gzip.decompress((cap/'FRAME_EVIDENCE.json.gz').read_bytes())
assert sha(wire)==receipt['frameEvidence']['sha256']
rows=json.loads(wire)['frames']
assert [r['frame'] for r in rows]==list(range(180))
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-show_frames','-show_entries','frame=best_effort_timestamp_time,width,height:stream:format','-of','json',str(video)]))
stream=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (stream['width'],stream['height'],stream['r_frame_rate'])==(1080,1920,'30/1')
assert stream['codec_name']=='h264' and abs(float(probe['format']['duration'])-6)<1e-6
assert len(probe['frames'])==180
assert all(abs(float(f['best_effort_timestamp_time'])-i/30)<1e-5 for i,f in enumerate(probe['frames']))
w,h=270,480
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-vf',f'scale={w}:{h}:flags=area','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
assert len(raw)==180*w*h*3
pixels=np.frombuffer(raw,np.uint8).reshape(180,h,w,3)
for start in range(0,180,15):
    sheet=Image.new('RGB',(w*5,(h+28)*3),'#101722');draw=ImageDraw.Draw(sheet)
    for j,frame in enumerate(range(start,start+15)):
        x=j%5*w;y=j//5*(h+28)
        sheet.paste(Image.fromarray(pixels[frame]),(x,y+28))
        draw.text((x+8,y+8),f'{frame:03d} | {frame/30:.3f}s',fill='white')
    sheet.save(out/f'ALL_FRAMES_{start:03d}_{start+14:03d}.jpg',quality=89)
merc=lambda lat:180/math.pi*math.log(math.tan(math.pi/4+math.radians(lat)/2))
project=lambda pose,pt:[540+(pt[0]-pose['center'][0])*pose['scale'],960-(merc(pt[1])-merc(pose['center'][1]))*pose['scale']]
anchors=[[90,43],[118,57],[104,50],[105,35],[120,20]]
summary=[];prevpose=None
for i,row in enumerate(rows):
    d=row['diagnostic'];assert d['glError']==0 and d['material']['fullViewportCovered']
    feature=next(f for f in d['features'] if f.get('continuousEvidence'))
    areas=feature['sourceAreas'];assert len(areas)==1 and areas[0]['alpha']==1
    assert all(a['drawn'] for dr in feature['draws'] for a in dr['draw']['areas'])
    assert d['featureChangedPixels']>0
    pose=d['camera']['actualFactory']['pose']
    assert pose==d['camera']['state']['pose']
    labels=d['presentationLabels']['drawn']
    assert all(48<=l['box'][0]<l['box'][2]<=1032 and 72<=l['box'][1]<l['box'][3]<=1848 for l in labels)
    assert len({l['id'] for l in labels})==len(labels)
    year=next(l['text'] for l in labels if l['role']=='TIMELINE')
    effects=[dr for f in d['features'] if f['id']=='TERRITORY_DIFFERENCES_V2' for dr in f['draws']]
    effect_areas=[a for e in effects for a in e['draw']['areas']]
    camera_delta=max(math.dist(project(prevpose,a),project(pose,a)) for a in anchors) if prevpose else 0
    logarithmic_speed=abs(math.log(pose['scale']/prevpose['scale']))*30 if prevpose else 0
    p=pixels[i].astype(np.int16)
    pixel_delta=float(np.abs(p[90:330]-pixels[i-1,90:330].astype(np.int16)).mean()) if i else 0
    summary.append({'frame':i,'timeSeconds':i/30,'year':year,'geometrySHA256':sha(json.dumps(areas[0]['geometry'],sort_keys=True,separators=(',',':')).encode()),
        'rawSHA256':row['rawSHA256'],'decodedThumbnailSHA256':sha(pixels[i].tobytes()),
        'alpha':areas[0]['alpha'],'sourceArea':feature['continuousEvidence']['areaDisplayUnits'],
        'continuousIndex':feature['continuousEvidence']['index'],'active':feature['continuousEvidence']['active'],
        'boundaryDrawn':any(a['drawn'] for a in effect_areas),'boundaryAlpha':effects[0]['alpha'] if effects else 0,
        'boundaryGlowGain':effects[0]['draw']['style']['AREA']['glowGain'] if effects else 0,
        'featureChangedPixels':d['featureChangedPixels'],'cameraPose':pose,'cameraAnchorMaxStepPixels':camera_delta,
        'cameraLogScalePerSecond':logarithmic_speed,'mapMeanAbsDeltaRGB':pixel_delta,
        'decodedMeanRGB':float(p.mean()),'safeLabelCount':len(labels)})
    prevpose=pose
changes=[r['frame'] for a,r in zip(summary,summary[1:]) if a['geometrySHA256']!=r['geometrySHA256']]
posechanges=[r['frame'] for a,r in zip(summary,summary[1:]) if a['cameraPose']!=r['cameraPose']]
hold=next(i for i in range(180) if len({r['rawSHA256'] for r in summary[i:]})==1)
camera_steps=[r['cameraAnchorMaxStepPixels'] for r in summary if r['cameraAnchorMaxStepPixels']>1e-8]
geometry_area_steps=[r['sourceArea']-a['sourceArea'] for a,r in zip(summary,summary[1:])]
result={'status':'FULL_MP4_TECHNICAL_CHECKS_PASS_VISUAL_REVIEW_PENDING','runtimeSHA256':sha((base/'RUNTIME_REQUEST.json').read_bytes()),
    'videoSHA256':video_hash,'video':receipt['video'],'backend':receipt['runtime']['backend'],
    'decodedAllFrames':180,'ledgerAllFrames':180,'framePTSValid':True,'safeLabelFrames':180,
    'geometryUniqueStates':len({r['geometrySHA256'] for r in summary}),'geometryChangeFrames':changes,
    'cameraChangeFrames':posechanges,'geometryAndCameraChangingTogetherFrames':len(set(changes)&set(posechanges)),
    'rawStableFinalHoldStart':hold,'rawStableFinalHoldFrames':180-hold,'rawStableFinalHoldSeconds':(180-hold)/30,
    'cameraScaleRatio':summary[-1]['cameraPose']['scale']/summary[0]['cameraPose']['scale'],
    'cameraMaxAnchorStepPixels':max(camera_steps),'cameraMedianNonzeroAnchorStepPixels':float(np.median(camera_steps)),
    'cameraLargestSteps':sorted([{'frame':r['frame'],'pixelsPerFrame':r['cameraAnchorMaxStepPixels']} for r in summary],key=lambda r:-r['pixelsPerFrame'])[:8],
    'cameraPeakLogScalePerSecond':max(r['cameraLogScalePerSecond'] for r in summary),
    'sourceAreaMinDelta':min(geometry_area_steps),'sourceAreaMaxDelta':max(geometry_area_steps),
    'boundaryDrawFrames':[r['frame'] for r in summary if r['boundaryDrawn']],
    'boundaryBandGlowGainValues':sorted({r['boundaryGlowGain'] for r in summary}),
    'encodedMapLargestDeltas':sorted([{'frame':r['frame'],'meanAbsRGB':r['mapMeanAbsDeltaRGB']} for r in summary],key=lambda r:-r['meanAbsRGB'])[:10],
    'fullVisualQualityPass':False,'userVisualApproval':'PENDING','oldPassReruns':0,'gpuStarts':0,
    'captureEncodingPassPreservedNotRerun':True,'rendererRunsByReview':0,'summary':summary}
(out/'FULL_FRAME_TECHNICAL_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'FFPROBE.json').write_text(json.dumps(probe,indent=2)+'\n')
(out/'VIDEO_SHA256.txt').write_text(video_hash+'  ../final-a1/VIDEO.mp4\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['summary','geometryChangeFrames','cameraChangeFrames','boundaryDrawFrames']},indent=2))
