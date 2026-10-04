"""Inspect every encoded V3 frame; keep image metrics separate from aesthetics."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from fractions import Fraction
import numpy as np
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser()
p.add_argument('movie')
p.add_argument('--scene',nargs='+',required=True)
p.add_argument('--start',type=float,default=0)
a=p.parse_args()
movie=Path(a.movie).resolve(); out=movie.parent
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
w,h=video['width'],video['height']; fps=float(Fraction(video['avg_frame_rate']))
assert (w,h)==(1080,1920) and fps>=30 and video['codec_name']=='h264'
assert video.get('color_range')=='tv' and all(video.get(k)=='bt709' for k in ['color_space','color_transfer','color_primaries']), 'Missing BT.709 limited-range tags'
scene=[]
for file in a.scene:scene+=json.loads(Path(file).read_text())
scene.sort(key=lambda s:s['t'])
dec=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(movie),'-map','0:v:0','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
count=0; frame_bytes=w*h*3; prev=None; prev_hash=None; prev_coarse=None
picture_hash=hashlib.sha256(); black=[]; duplicate=[]; empty=[]; diffs=[]; earth_diffs=[]; coarse_diffs=[]; motion=[]; thumbs=[]
while True:
    data=dec.stdout.read(frame_bytes)
    if not data:break
    if len(data)!=frame_bytes:raise RuntimeError('Partial decoded frame')
    frame=np.frombuffer(data,np.uint8).reshape(h,w,3)
    digest=hashlib.sha256(data).digest(); picture_hash.update(data)
    if digest==prev_hash:duplicate.append(count)
    sample=frame[::4,::4].astype(np.int16)
    # Image tests exclude the intentional black upper space field.
    roi=sample[120:420,15:255]
    # Average 40x32 final-pixel blocks: temporal dither must not disguise a freeze.
    coarse=roi.reshape(30,10,30,8,3).mean(axis=(1,3,4))
    if float(frame.mean())<1:black.append(count)
    if float(roi.std())<.75:empty.append(count)
    if prev is not None:
        delta=np.abs(sample-prev)
        diffs.append(float(delta.mean()))
        earth_diffs.append(float(delta[120:420,15:255].mean()))
        coarse_diffs.append(float(np.abs(coarse-prev_coarse).mean()))
        motion.append(float((delta[120:420,15:255]>3).mean()))
    if count%15==0:thumbs.append((a.start+count/fps,Image.fromarray(frame).resize((375,667),Image.Resampling.LANCZOS)))
    prev=sample;prev_coarse=coarse;prev_hash=digest;count+=1
assert dec.wait()==0,'Decoder failure'
assert len(scene)==count,(len(scene),count)
assert all(abs(s['t']-(a.start+i/fps))<1e-5 for i,s in enumerate(scene)),'Scene/video timing mismatch'
run=longest=0
for d in coarse_diffs:
    run=run+1 if d<.10 else 0
    longest=max(longest,run)
cameras=np.array([s['cameraPosition'] for s in scene]); steps=np.linalg.norm(np.diff(cameras,axis=0),axis=1)
qs=np.array([s['cameraQuaternion'] for s in scene]); angles=np.degrees(2*np.arccos(np.clip(np.abs(np.sum(qs[1:]*qs[:-1],axis=1)),-1,1)))
routes=np.array([s['routeProgress'] for s in scene]); monotonic=bool(np.all(np.diff(routes,axis=0)>=-1e-8))
clipped=[{'t':s['t'],'labels':s['textClipped']} for s in scene if s['textClipped']]
gl_errors=[s['t'] for s in scene if s['webglError']]
aircraft_offscreen=[]; label_plane=[]; label_label=[]
for s in scene:
    plane=s['aircraft']; labels=s['labels']
    if plane['visible']:
        # Audit coordinates use the 2160x3840 internal canvas.
        if not (172.8<plane['x']<1944 and 460.8<plane['y']<3033.6):aircraft_offscreen.append(s['t'])
        for label in labels:
            if label['x']-70<plane['x']<label['x']+label['width']+70 and label['y']-70<plane['y']<label['y']+label['height']+70:label_plane.append({'t':s['t'],'label':label['text']})
    for i,x in enumerate(labels):
        for y in labels[i+1:]:
            if x['x']<y['x']+y['width'] and y['x']<x['x']+x['width'] and x['y']<y['y']+y['height'] and y['y']<x['y']+x['height']:label_label.append({'t':s['t'],'labels':[x['text'],y['text']]})
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
for k in range(0,len(thumbs),6):
    dest=out/f'{movie.stem}_mobile_contact_{k//6:02}.jpg'
    if dest.exists():raise FileExistsError(dest)
    sheet=Image.new('RGB',(1125,1430),'#080e16');draw=ImageDraw.Draw(sheet)
    for j,(time,im) in enumerate(thumbs[k:k+6]):
        x=j%3*375;y=j//3*715;sheet.paste(im,(x,y+36));draw.text((x+10,y+6),f'{time:.2f} s / 375px mobile',font=font,fill='white')
    sheet.save(dest,quality=96)
events=[0,.3,.6,.9,1.2,1.5,2.2,3.8,5.6,7.1,8.3,9.65,10.2,12.1,14,15.5,16.5,17.25,18.1,19.2]
intervals=np.diff(events)
report={'file':movie.name,'dimensions':[w,h],'fps':fps,'codec':video['codec_name'],'pixel_format':video['pix_fmt'],'color_range':video.get('color_range'),'color_space':video.get('color_space'),'color_transfer':video.get('color_transfer'),'color_primaries':video.get('color_primaries'),'duration':float(meta['format']['duration']),'decoded_full_resolution_frames':count,'all_decoded_rgb_sha256':picture_hash.hexdigest(),'black_frames':black,'empty_earth_frames':empty,'exact_duplicate_frames':duplicate,'maximum_near_frozen_earth_run_seconds':longest/fps,'earth_motion_min':min(earth_diffs),'earth_motion_median':float(np.median(earth_diffs)),'earth_motion_max':max(earth_diffs),'first_half_second_earth_motion_min':min(earth_diffs[:15]),'mean_earth_changed_pixel_fraction':float(np.mean(motion)),'text_clipping':clipped,'webgl_errors':gl_errors,'maximum_camera_step_globe_radii':float(steps.max()),'maximum_camera_angle_step_degrees':float(angles.max()),'minimum_camera_step_globe_radii':float(steps.min()),'route_progress_monotonic':monotonic,'aircraft_outside_safe_scene':aircraft_offscreen,'label_plane_proximity':label_plane,'label_label_overlaps':label_label,'authored_events':events,'authored_interval_mean':float(intervals.mean()),'authored_interval_max':float(intervals.max()),'first_three_seconds_authored_events':[t for t in events if t<3],'audio':[{'codec':s['codec_name'],'sample_rate':s.get('sample_rate'),'channels':s.get('channels')} for s in meta['streams'] if s['codec_type']=='audio'],'scope':'Every encoded RGB frame decoded and hashed. Image/asset/pose/label checks complement required direct visual review. Authored event spacing is a timeline property, not measured audience retention.'}
report['freeze_detection']={'method':'40x32-pixel RGB block means in the Earth ROI; reduces temporal-dither noise','near_frozen_block_mad_threshold':.10,'coarse_motion_min':min(coarse_diffs),'coarse_motion_median':float(np.median(coarse_diffs)),'first_half_second_coarse_motion_min':min(coarse_diffs[:15])}
report['city_glyph_widths']={name:sorted({round(label['width'],7) for s in scene for label in s['labels'] if label['text']==name}) for name in ['SEOUL','TOKYO','SINGAPORE']}
dest=out/f'{movie.stem}_validation_v3.json'
with dest.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({k:v for k,v in report.items() if k not in ['authored_events','label_plane_proximity']},indent=2))
assert not black and not empty and not duplicate and longest/fps<3
assert not clipped and not gl_errors and monotonic and not label_label
assert not aircraft_offscreen,'Aircraft leaves safe scene; inspect composition'
assert float(angles.max())<3,'Unexpected camera orientation step'
assert not label_plane,'City label too close to aircraft; inspect and correct layout'
assert all(len(widths)<=1 for widths in report['city_glyph_widths'].values()),'City glyph width changes; inspect font loading'
