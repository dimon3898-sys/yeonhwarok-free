"""Inspect every delivered full-resolution frame and the actual scene audit.
Numerical tests complement visual review; they cannot certify aesthetic taste.
"""
import argparse,subprocess,json,hashlib
from pathlib import Path
from fractions import Fraction
import numpy as np
from PIL import Image,ImageDraw,ImageFont

p=argparse.ArgumentParser();p.add_argument('movie');p.add_argument('--scene',nargs='+',required=True);a=p.parse_args()
movie=Path(a.movie).resolve();out=movie.parent
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]))
video=next(x for x in meta['streams'] if x['codec_type']=='video');fps=float(Fraction(video['avg_frame_rate']));w,h=video['width'],video['height']
assert (w,h)==(1080,1920) and fps>=30 and video['codec_name']=='h264'
scene=[]
for path in a.scene:scene+=json.loads(Path(path).read_text())
scene.sort(key=lambda x:x['t'])
dec=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-i',str(movie),'-map','0:v:0','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
count=0;size=w*h*3;previous=None;previous_hash=None;picture_hash=hashlib.sha256();diffs=[];map_diffs=[];black=[];empty=[];duplicate=[];thumbs=[];brightness=[]
while True:
    data=dec.stdout.read(size)
    if not data:break
    if len(data)!=size:raise RuntimeError('Partial decoded frame')
    frame=np.frombuffer(data,np.uint8).reshape(h,w,3)
    digest=hashlib.sha256(data).digest()
    picture_hash.update(data)
    if digest==previous_hash:duplicate.append(count)
    sample=frame[::4,::4].astype(np.int16)
    roi=sample[75:335,25:235]
    brightness.append(float(roi.mean()))
    if float(frame.mean())<1:black.append(count)
    if float(roi.mean())<2 or float(roi.std())<.75:empty.append(count)
    if previous is not None:
        diffs.append(float(np.abs(sample-previous).mean()))
        map_diffs.append(float(np.abs(roi-previous[75:335,25:235]).mean()))
    if count%15==0:thumbs.append((count/fps,Image.fromarray(frame).resize((375,667),Image.Resampling.LANCZOS)))
    previous=sample;previous_hash=digest;count+=1
assert dec.wait()==0,'Decoder failure'
assert len(scene)==count,(len(scene),count)
assert all(abs(x['t']-i/fps)<1e-5 for i,x in enumerate(scene)),'Scene/video timing mismatch'
near_run=run=0
for d in map_diffs:
    run=run+1 if d<.025 else 0;near_run=max(near_run,run)
camera=np.array([s['camera'] for s in scene]);steps=np.linalg.norm(np.diff(camera,axis=0),axis=1)
quats=np.array([s['cameraQuaternion'] for s in scene]);dots=np.abs(np.sum(quats[1:]*quats[:-1],axis=1));angles=np.degrees(2*np.arccos(np.clip(dots,-1,1)))
routes=np.array([s['routeProgress'] for s in scene]);monotonic=bool(np.all(np.diff(routes,axis=0)>=-1e-8))
plane=np.array([s['planePosition'] for s in scene]);plane_steps=np.linalg.norm(np.diff(plane,axis=0),axis=1)
visible=[s for s in scene if s['planeVisible']]
plane_offscreen=[s['t'] for s in visible if not s['planeScreen']['visible'] or not (80<s['planeScreen']['x']<2080 and 250<s['planeScreen']['y']<2820)]
clipped=[{'time':s['t'],'texts':s['textClipped']} for s in scene if s['textClipped']]
label_overlaps=[{'time':s['t'],'texts':s['aircraftLabelOverlaps']} for s in scene if s.get('aircraftLabelOverlaps',[])]
gl_errors=[s['t'] for s in scene if s['webglError']]
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
for k in range(0,len(thumbs),6):
    sheet=Image.new('RGB',(1125,1430),'#090f18');d=ImageDraw.Draw(sheet)
    for j,(time,im) in enumerate(thumbs[k:k+6]):
        x=j%3*375;y=j//3*715;sheet.paste(im,(x,y+36));d.text((x+10,y+6),f'{time:.2f} s · 375px mobile',font=font,fill='white')
    sheet.save(out/f'{movie.stem}_mobile_contact_{k//6:02}.jpg',quality=96)
events=[0,.4,1.15,1.8,2.75,4.4,5.9,7.1,8.4,10.15,12.2,14.25,16.3,17.2,18.35,19.3]
intervals=np.diff(events)
report={'file':movie.name,'dimensions':[w,h],'fps':fps,'codec':video['codec_name'],'pixel_format':video['pix_fmt'],
 'duration':float(meta['format']['duration']),'decoded_full_resolution_frames':count,'all_decoded_rgb_sha256':picture_hash.hexdigest(),'black_frames':black,'empty_map_frames':empty,
 'exact_duplicate_frames':duplicate,'maximum_near_frozen_map_run_seconds':near_run/fps,'map_motion_min':min(map_diffs),'map_motion_median':float(np.median(map_diffs)),
 'first_half_second_map_motion_min':min(map_diffs[:15]),'map_motion_max':max(map_diffs),'text_clipping':clipped,'webgl_errors':gl_errors,
 'maximum_camera_step_globe_radii':float(steps.max()),'maximum_camera_angle_step_degrees':float(angles.max()),
 'minimum_camera_step_globe_radii':float(steps.min()),'maximum_entity_step_globe_radii':float(plane_steps.max()),
 'route_progress_monotonic':monotonic,'aircraft_outside_safe_scene':plane_offscreen,'aircraft_label_overlaps':label_overlaps,'encoded_frame_aircraft_label_audits':sum('aircraftLabelOverlaps' in s for s in scene),
 'authored_events':events,'authored_interval_mean':float(intervals.mean()),'authored_interval_max':float(intervals.max()),
 'first_three_seconds_authored_events':[t for t in events if t<3],
 'audio':[{'codec':s['codec_name'],'sample_rate':s.get('sample_rate'),'channels':s.get('channels')} for s in meta['streams'] if s['codec_type']=='audio'],
 'join_map_difference':{str(i/fps):map_diffs[i-1] for i in [150,300] if i<count},
 'scope':'All full-resolution decoded pixels hashed; per-frame image/motion checks plus geometry/text/asset audits. Visual review remains required.'}
(out/f'{movie.stem}_validation_v2.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert not black and not empty and not duplicate and near_run/fps<3
assert not clipped and not gl_errors and monotonic
assert not label_overlaps,'Focal city labels overlap the aircraft silhouette'
assert not plane_offscreen,'Aircraft left the safe map composition; inspect and correct camera'
assert float(angles.max())<8,'Unexpected camera orientation step'
