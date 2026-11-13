"""Observe an actual MP4 with feature tracks; never generate/interpolate video."""
import argparse, hashlib, json, math
from pathlib import Path
import cv2
import numpy as np

p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('output');p.add_argument('--camera-input');a=p.parse_args()
cv2.setNumThreads(2);cv2.setRNGSeed(173)
cap=cv2.VideoCapture(a.video);rows=[];hashes=[];previous=None;index=0;center=np.array([270.,480.])
while True:
    ok,frame=cap.read()
    if not ok:break
    hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    gray=cv2.cvtColor(cv2.resize(frame,(540,960),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY)
    if previous is not None:
        pts=cv2.goodFeaturesToTrack(previous,maxCorners=1200,qualityLevel=.012,minDistance=6,blockSize=7)
        nxt,status,_=cv2.calcOpticalFlowPyrLK(previous,gray,pts,None,winSize=(31,31),maxLevel=4,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.001))
        back,backstatus,_=cv2.calcOpticalFlowPyrLK(gray,previous,nxt,None,winSize=(31,31),maxLevel=4,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.001))
        valid=(status[:,0]>0)&(backstatus[:,0]>0)&(np.linalg.norm(back[:,0]-pts[:,0],axis=1)<.6)
        x,y=pts[valid,0],nxt[valid,0]
        assert len(x)>40,('INSUFFICIENT_FEATURE_TRACKS',index,len(x))
        M,inliers=cv2.estimateAffinePartial2D(x,y,method=cv2.RANSAC,ransacReprojThreshold=.6,maxIters=3000,confidence=.999,refineIters=30)
        assert M is not None
        keep=inliers[:,0]>0;errors=np.linalg.norm(x@M[:,:2].T+M[:,2]-y,axis=1)
        scale=math.hypot(M[0,0],M[1,0]);delta=2*(M[:,:2]@center+M[:,2]-center)
        rows.append({'from':index-1,'to':index,'matrixAtHalfResolution':M.tolist(),'scaleRatio':scale,'logScaleDelta':math.log(scale),'rotationDegreesDelta':math.degrees(math.atan2(M[1,0],M[0,0])),'centerMotionPixels':delta.tolist(),'inliers':int(keep.sum()),'inlierFraction':float(keep.mean()),'inlierRmsPixels':float(2*np.sqrt(np.mean(errors[keep]**2)))})
    previous=gray;index+=1
cap.release();assert index==180,('EXPECTED_180',index)
result={'status':'MEASURED_ACTUAL_VIDEO','videoSHA256':hashlib.sha256(Path(a.video).read_bytes()).hexdigest(),'frames':index,'opencvVersion':cv2.__version__,'method':'Shi-Tomasi feature tracks, pyramidal Lucas-Kanade forward/backward consistency, RANSAC similarity; no generated frames','methodReference':'https://docs.opencv.org/5.0/javadoc/org/opencv/video/Video.html','duplicateMovingPairs':[i for i in range(1,150) if hashes[i]==hashes[i-1]],'decodedFrameSHA256':hashes,'pairs':rows,'GPUExecutions':0,'oldPassReruns':0}
if a.camera_input:
    poses=json.loads(Path(a.camera_input).read_text())['presentation']['camera']['frames']
    def Q(p):return np.array([p['center'][0],-math.degrees(math.log(math.tan(math.pi/4+math.radians(p['center'][1])/2)))])
    def R(p):
        t=math.radians(p['rollDegrees']);return np.array([[math.cos(t),-math.sin(t)],[math.sin(t),math.cos(t)]])
    grid=np.array([[80,80],[1000,80],[540,960],[80,1840],[1000,1840]],dtype=float)
    for row in rows:
        p0,p1=poses[row['from']],poses[row['to']];A=p1['scale']/p0['scale']*R(p1)@R(p0).T;t=2*center-A@(2*center)+p1['scale']*R(p1)@(Q(p0)-Q(p1));M=np.array(row['matrixAtHalfResolution']);obs=grid@M[:,:2].T+2*M[:,2];expected=grid@A.T+t
        row['expectedLogScaleDelta']=math.log(p1['scale']/p0['scale']);row['modelFitRmsPixels']=float(np.sqrt(np.mean((obs-expected)**2)));row['modelFitMaxPixels']=float(np.max(np.linalg.norm(obs-expected,axis=1)))
    moving=rows[:149];result['movingModelFitRmsPixelsMedian']=float(np.median([r['modelFitRmsPixels'] for r in moving]));result['movingModelFitRmsPixelsP95']=float(np.quantile([r['modelFitRmsPixels'] for r in moving],.95));result['observedVsAuthoredLogScaleCorrelation']=float(np.corrcoef([r['logScaleDelta'] for r in moving],[r['expectedLogScaleDelta'] for r in moving])[0,1])
Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['pairs','decodedFrameSHA256']},indent=2))
