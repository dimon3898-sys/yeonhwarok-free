"""Decode every frame and measure the delivered stream, not just its metadata."""
import subprocess,json,sys
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
p=Path(sys.argv[1]).resolve();r=p.parent
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
v=next(x for x in meta['streams'] if x['codec_type']=='video');fps=float(Fraction(v['avg_frame_rate']))
dec=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p),'-map','0:v:0','-vf','scale=270:480','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
frames=[];diffs=[];map_diffs=[];previous=None;count=0;size=270*480*3
while True:
    b=dec.stdout.read(size)
    if not b:break
    if len(b)!=size:raise RuntimeError('Short decoded frame')
    arr=np.frombuffer(b,np.uint8).reshape((480,270,3))
    if previous is not None:
        diffs.append(float(np.mean(np.abs(arr.astype(float)-previous.astype(float)))))
        map_diffs.append(float(np.mean(np.abs(arr[90:360].astype(float)-previous[90:360].astype(float)))))
    if count%15==0:frames.append((count/fps,Image.fromarray(arr)))
    previous=arr.copy();count+=1
if dec.wait()!=0:raise RuntimeError('Video decode failed')
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
for k in range(0,len(frames),10):
    sheet=Image.new('RGB',(1350,1020),'#0a1019');d=ImageDraw.Draw(sheet)
    for i,(time,im) in enumerate(frames[k:k+10]):
        x=i%5*270;y=i//5*510;sheet.paste(im,(x,y+28));d.text((x+8,y+5),f'{time:.2f}s',font=font,fill='white')
    sheet.save(r/f'{p.stem}_contact_{k//10:02d}.jpg',quality=95)
run=0;maxrun=0
for x in diffs:
    run=run+1 if x<.015 else 0;maxrun=max(maxrun,run)
maprun=0;maxmaprun=0
for x in map_diffs:
    maprun=maprun+1 if x<.015 else 0;maxmaprun=max(maxmaprun,maprun)
report=dict(minimum_map_region_difference=min(map_diffs),median_map_region_difference=float(np.median(map_diffs)),maximum_near_duplicate_map_run_seconds=maxmaprun/fps,file=p.name,dimensions=[v['width'],v['height']],fps=fps,codec=v['codec_name'],pixel_format=v['pix_fmt'],duration=float(meta['format']['duration']),decoded_frames=count,minimum_adjacent_frame_mean_difference=min(diffs),median_adjacent_frame_mean_difference=float(np.median(diffs)),maximum_near_duplicate_run_seconds=maxrun/fps,audio=[dict(codec=x['codec_name'],sample_rate=x.get('sample_rate'),channels=x.get('channels')) for x in meta['streams'] if x['codec_type']=='audio'])
report['join_map_differences']={str(n/fps):map_diffs[n-1] for n in [150,300] if n<len(map_diffs)}
(r/f'{p.stem}_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
