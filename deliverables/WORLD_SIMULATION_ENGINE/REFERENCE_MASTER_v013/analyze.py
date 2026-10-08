import sys,json,hashlib,math,subprocess
from pathlib import Path
sys.path.insert(0,'/tmp/world-direction-v012/python')
import cv2,numpy as np
from scipy.signal import find_peaks
from PIL import Image,ImageDraw
ROOT=Path('/tmp/world-reference-v013')
FILES=[Path('/workspace/attachments/6c912884-d41c-4e3f-a607-c54c82448229/final (3).mp4'),Path('/workspace/attachments/98beddfa-385e-4515-9599-1e8480b316f3/lv_0_20261008074313.mp4')]
def intervals(flags):
 out=[];start=None
 for i,f in enumerate(list(flags)+[False]):
  if f and start is None:start=i
  if not f and start is not None:
   if i-start>=9:out.append({'start':round(start/30,3),'end':round(i/30,3),'duration':round((i-start)/30,3)})
   start=None
 return out
for n,file in enumerate(FILES):
 cap=cv2.VideoCapture(str(file));frames=[];rows=[];last=None;previous=None
 while True:
  okay,frame=cap.read()
  if not okay:break
  frame=cv2.resize(frame,(270,round(frame.shape[0]*270/frame.shape[1])))
  frames.append(frame)
  h,w=frame.shape[:2];roi=frame[int(h*(.08 if n else .10)):int(h*(.64 if n else .85)),int(w*.05):int(w*.88)]
  gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY);row={'frame':len(frames)-1,'time':round((len(frames)-1)/30,6),'luma':float(gray.mean()),'dark_fraction':float((gray<18).mean()),'median_flow_px':None,'rotation_2d_deg_per_s':None,'scale_log_per_s':None,'affine_inliers':0}
  if last is not None:
   pts=cv2.goodFeaturesToTrack(last,600,.012,6)
   if pts is not None:
    moved,status,err=cv2.calcOpticalFlowPyrLK(last,gray,pts,None,winSize=(21,21),maxLevel=3)
    valid=status.ravel()==1;a=pts[valid].reshape(-1,2);b=moved[valid].reshape(-1,2)
    if len(a)>=20:
     distances=np.linalg.norm(b-a,axis=1);row['median_flow_px']=float(np.median(distances))
     transform,mask=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=1.8)
     if transform is not None and mask.sum()>=20 and mask.mean()>=.55:
      row['affine_inliers']=int(mask.sum());row['rotation_2d_deg_per_s']=math.atan2(transform[1,0],transform[0,0])*180/math.pi*30;row['scale_log_per_s']=math.log(max(1e-9,math.hypot(transform[0,0],transform[1,0])))*30
   row['frame_change']=float(np.abs(gray.astype(float)-last.astype(float)).mean())
  rows.append(row);last=gray
 cap.release()
 # Exclude the reference's appended CapCut slate; preserve full decoded records.
 end=12 if n==0 else 18.8
 selected=[r for r in rows if r['time']<end]
 smooth=[]
 for i,r in enumerate(selected):
  vals=[x['median_flow_px'] for x in selected[max(0,i-2):i+3] if x['median_flow_px'] is not None]
  smooth.append(float(np.median(vals)) if vals else None)
 settles=intervals([v is not None and v<.45 for v in smooth]);high=intervals([v is not None and v>2.2 for v in smooth])
 vel=[abs(r['rotation_2d_deg_per_s']) for r in selected if r['rotation_2d_deg_per_s'] is not None];zoom=[abs(r['scale_log_per_s']) for r in selected if r['scale_log_per_s'] is not None]
 audio=ROOT/f'audio{n}.f32';subprocess.run(['ffmpeg','-v','error','-i',str(file),'-vn','-ac','1','-ar','48000','-f','f32le',str(audio)],check=True)
 samples=np.fromfile(audio,dtype=np.float32);rms=np.sqrt(np.mean(samples[:len(samples)//1600*1600].reshape(-1,1600)**2,axis=1));db=20*np.log10(np.maximum(rms,1e-8));novelty=np.maximum(0,np.diff(db,prepend=db[0]));peaks,_=find_peaks(novelty,height=3.5,distance=6)
 report={'file':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'decoded_frames':len(frames),'content_end':end,'excluded_tail_reason':'CapCut export slate after actual reference map segment' if n else None,'measurement':'2D feature flow/affine proxies on geographic ROI; not physical 3D camera or isolated SFX','thresholds':{'settle_px_per_frame':.45,'high_motion_px_per_frame':2.2,'min_segment_seconds':.3},'settles':settles,'high_motion':high,'rotation_2d_abs_p95_deg_s':float(np.percentile(vel,95)) if vel else None,'log_scale_abs_p95_s':float(np.percentile(zoom,95)) if zoom else None,'median_luma':float(np.median([r['luma'] for r in selected])),'last_map_luma':selected[-1]['luma'],'audio_transient_candidates':[round(int(i)/30,3) for i in peaks if i/30<end],'audio_peak':float(abs(samples).max()),'frames':rows}
 (ROOT/f'metrics{n}.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='frames'}),flush=True)
 for page,start in enumerate(range(0,math.ceil(end*2),18)):
  selected_indices=[min(len(frames)-1,round(k*.5*30)) for k in range(start,min(start+18,math.ceil(end*2)))];tile_h=frames[0].shape[0]+24;sheet=Image.new('RGB',(270*6,tile_h*3),'#121d25');draw=ImageDraw.Draw(sheet)
  for j,i in enumerate(selected_indices):
   im=Image.fromarray(cv2.cvtColor(frames[i],cv2.COLOR_BGR2RGB));x=j%6*270;y=j//6*tile_h;sheet.paste(im,(x,y+24));draw.text((x+4,y+4),f'{i/30:.3f}s / frame {i}',fill='white')
  sheet.save(ROOT/f'contact_{n}_{page}.jpg',quality=91)
