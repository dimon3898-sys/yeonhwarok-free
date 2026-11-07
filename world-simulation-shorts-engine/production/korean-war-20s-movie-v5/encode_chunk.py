"""Encode the actual ordered PNGs; reuse three immutable successful color stills."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
here=Path(__file__).resolve().parent
clip=int(os.environ['KW20_CLIP']);start=int(os.environ['KW20_START']);end=start+150
out=Path('/out');chunk=out/'chunk'
pins=json.loads((here/'CACHED_FRAMES.json').read_bytes())
capture=json.loads((chunk/'CPU_PREVIEW_RESULT.json').read_bytes())
assert capture['status']=='PASS_SELECTED_FRAMES_ONLY'
evidence=json.loads((chunk/'FRAME_EVIDENCE.json').read_bytes())['frames']
new={r['frame'] for r in evidence}
reuse=[r for r in pins if r['clip']==clip and start<=r['frame']<end]
assert new==set(range(start,end))-{r['frame'] for r in reuse},'FRAME_COVERAGE_GAP_OR_DUPLICATE'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def label_state(frame):
    d=json.loads((chunk/f'FRAME_{frame:03d}.json').read_bytes())['diagnostic']
    return {'camera':d['camera']['bounds'],'labels':[{k:x.get(k) for k in ['id','text','box','pinBox','alpha','projected']} for x in d['presentationLabels']['drawn']]}
for row in reuse:
    for ext in ('png','json'):
        source=Path(row['root'])/f'clip-{clip:02d}'/f'FRAME_{row["frame"]:03d}.{ext}'
        assert sha(source)==row[ext],'CACHED_FRAME_CHANGED'
        target=chunk/source.name
        with source.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
    neighbor=1 if row['frame']==0 else 298
    assert label_state(row['frame'])==label_state(neighbor),'CACHED_HOLD_BOUNDARY_STATE_DIFFERENT'
for f in range(start,end):assert (chunk/f'FRAME_{f:03d}.png').is_file()
movie=out/f'CLIP_{clip:02d}_FRAMES_{start:03d}_{end-1:03d}.mp4'
subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-framerate','30','-start_number',str(start),'-i',str(chunk/'FRAME_%03d.png'),'-frames:v','150','-an','-c:v','libx264','-preset','veryfast','-crf','18','-profile:v','high','-level:v','4.2','-g','150','-keyint_min','150','-sc_threshold','0','-bf','0','-pix_fmt','yuv420p','-metadata','comment=CPU SwiftShader sample. Modern NASA BMNG and Natural Earth geography; no reconstructed military ownership.','-movflags','+faststart',str(movie)],check=True,timeout=180)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]))
v=probe['streams'][0]
assert len(probe['streams'])==1 and v['width']==1080 and v['height']==1920 and v['nb_frames']=='150' and v['avg_frame_rate']=='30/1' and float(v['duration'])==5
seal=json.loads((here.parent/'korean-war-20s-visual-v4/SOURCE_SEAL.json').read_bytes())
receipt={'schema':'WORLD_ENGINE_KW20_SCENE_MOVIE_RECEIPT_V1','status':'PASS_ACTUAL_150_ORDERED_FRAMES_ENCODED','clip':clip,'startFrame':start,'endFrame':end,'globalStartFrame':(clip-1)*300+start,'globalEndFrame':(clip-1)*300+end,'newFrames':len(new),'reusedFrames':[r['frame'] for r in reuse],'file':movie.name,'sha256':sha(movie),'bytes':movie.stat().st_size,'inputSHA256':seal['inputs'][clip-1]['sha256'],'runtimeManifestSHA256':seal['runtimeManifestSHA256'],'width':1080,'height':1920,'fps':30,'frames':150,'durationSeconds':5,'softwareOnly':True,'gpuExecutions':0,'oldPassSuitesRerun':0,'finalVideoQualityPass':False,'finalFullDecode':'DEFERRED_TO_EXISTING_COMPOSER'}
(out/'CHUNK_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
(out/'PNG_SEQUENCE.json').write_text(json.dumps({'frames':[{'frame':f,'pngSHA256':sha(chunk/f'FRAME_{f:03d}.png'),'reused':f not in new} for f in range(start,end)]},indent=2)+'\n')
print(json.dumps(receipt))
