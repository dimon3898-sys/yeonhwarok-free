"""Frame timing is measured; affine image motion is an estimate, never camera telemetry."""
import cv2, numpy as np, json, hashlib, subprocess, sys
from pathlib import Path
from PIL import Image,ImageDraw
video=Path(sys.argv[1]); out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','frame=best_effort_timestamp_time,pkt_duration_time:stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(video)]))
cap=cv2.VideoCapture(str(video)); records=[]; thumbs=[];prev=None
while True:
    ok,frame=cap.read()
    if not ok:break
    i=len(records); small=cv2.resize(frame,(411,960));gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    # fixed crop excludes top phone UI, right social buttons and lower captions.
    roi=gray[85:550,10:365]
    r={'frame':i,'ptsSeconds':float(meta['frames'][i]['best_effort_timestamp_time'])}
    if prev is not None:
        r['meanPixelDifference']=float(np.abs(roi.astype(float)-prev.astype(float)).mean())
        points=cv2.goodFeaturesToTrack(prev,600,.015,8)
        if points is not None:
            q,status,err=cv2.calcOpticalFlowPyrLK(prev,roi,points,None,winSize=(25,25),maxLevel=4)
            mask=status.ravel()==1;p=points[mask];q=q[mask]
            if len(p)>=12:
                affine,inliers=cv2.estimateAffinePartial2D(p,q,method=cv2.RANSAC,ransacReprojThreshold=2)
                if affine is not None:
                    a,b,tx=affine[0];c,d,ty=affine[1];scale=float(np.hypot(a,c));center=np.array([roi.shape[1]/2,roi.shape[0]/2]);move=affine[:,:2]@center+affine[:,2]-center
                    r.update(affineScale=scale,rotationDegrees=float(np.degrees(np.arctan2(c,a))),centerDxPixels=float(move[0]*2),centerDyPixels=float(move[1]*2),inliers=int(inliers.sum()),tracked=len(p),inlierRatio=float(inliers.mean()))
                    r['estimatedMotionValid']=bool(inliers.sum()>=18 and inliers.mean()>=.65 and .8<scale<1.2)
    records.append(r);prev=roi
    thumb=Image.fromarray(cv2.cvtColor(small,cv2.COLOR_BGR2RGB)).resize((103,240));thumbs.append(thumb)
cap.release()
for start in range(0,len(thumbs),80):
    sheet=Image.new('RGB',(8*113,10*262),'#171b23');draw=ImageDraw.Draw(sheet)
    for k,img in enumerate(thumbs[start:start+80]):
        x=(k%8)*113;y=(k//8)*262;sheet.paste(img,(x,y));draw.text((x+2,y+241),f'{start+k} | {(start+k)/30:.2f}s',fill='white')
    sheet.save(out/f'ALL_FRAMES_{start:03d}.jpg',quality=90)
for i,r in enumerate(records):
    if i and r.get('estimatedMotionValid'):
        dt=r['ptsSeconds']-records[i-1]['ptsSeconds'];r['estimatedScaleLogPerSecond']=float(np.log(r['affineScale'])/dt);r['estimatedCenterSpeedPixelsPerSecond']=float(np.hypot(r['centerDxPixels'],r['centerDyPixels'])/dt)
        if records[i-1].get('estimatedCenterSpeedPixelsPerSecond') is not None:r['estimatedSpeedChangePixelsPerSecondSquared']=(r['estimatedCenterSpeedPixelsPerSecond']-records[i-1]['estimatedCenterSpeedPixelsPerSecond'])/dt
result={'source':video.name,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'stream':meta['streams'][0],'decodedFrames':len(records),'measurements':'PTS, frame count and pixel differences are measured. LK/RANSAC affine motion is estimated from the static-map ROI, may be affected by effects and cannot recover physical 3D camera distances.','trackingROIOriginalPixels':[20,170,730,1100],'records':records}
(out/'FRAME_MEASUREMENTS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'frames':len(records),'sha256':result['sha256'],'validAffinePairs':sum(r.get('estimatedMotionValid',False) for r in records),'cutsToReview':[r['frame'] for r in records if r.get('meanPixelDifference',0)>30]}))
