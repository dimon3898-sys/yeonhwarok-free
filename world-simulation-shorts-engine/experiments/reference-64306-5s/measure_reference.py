#!/usr/bin/env python3
"""Reference-only 5-second color-timing evidence; never certifies render quality."""
import sys,json,cv2,numpy as np
from pathlib import Path
src=Path(sys.argv[1]); out=Path(sys.argv[2])
cap=cv2.VideoCapture(str(src))
assert cap.isOpened(), 'REFERENCE_VIDEO_UNREADABLE'
fps=cap.get(cv2.CAP_PROP_FPS); n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
assert fps>0 and n>=2, 'REFERENCE_FRAMES_INVALID'
samples=[]
for frame_id in sorted(set([0,n-1]+[min(n-1,round(t*fps)) for t in np.arange(0,n/fps,.5)])):
 cap.set(cv2.CAP_PROP_POS_FRAMES,frame_id); valid,frame=cap.read()
 assert valid, f'FRAME_DECODE_FAILED_{frame_id}'
 h,w=frame.shape[:2]; roi=frame[int(.16*h):int(.83*h),int(.12*w):int(.85*w)]
 hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
 colors={'yellow':([17,70,65],[39,255,255]),'cyan':([78,60,45],[104,255,255])}
 fractions={name:round(float(np.mean(cv2.inRange(hsv,np.array(lo),np.array(hi))>0)),5) for name,(lo,hi) in colors.items()}
 samples.append({'frame':frame_id,'relativeSeconds':round(frame_id/fps,3),'heuristicColorFractions':fractions})
cap.release()
out.write_text(json.dumps({'status':'REFERENCE_ONLY_NOT_RENDER_PASS','source':src.name,'fps':fps,'frames':n,'roi':[.12,.16,.85,.83],'limitations':['Heuristic color masks include terrain/UI','Not geographic source registration','No candidate video comparison'],'samples':samples},ensure_ascii=False,indent=2)+'\n')
print(out)
