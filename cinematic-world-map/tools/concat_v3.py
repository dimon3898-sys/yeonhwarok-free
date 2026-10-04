"""Join reviewed contiguous V3 segments, with source/format checks and no overwrite."""
import argparse, json, subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--compatibility');p.add_argument('segments',nargs='+');a=p.parse_args()
root=Path(__file__).resolve().parents[1]/'outputs'
destination=(root/a.output).resolve()
if destination.parent!=root or destination.exists():raise ValueError('Invalid or existing destination')
manifests=[];signatures=[];scene=[];expected=0
proof=json.loads(Path(a.compatibility).read_text()) if a.compatibility else None
if proof:
    assert proof['complete'] and proof['exactInputsEqual'] and not proof['mismatches']
    assert proof['sampling']['poseHz'] == 120 and proof['staticInputsEqual']
for name in a.segments:
    movie=(root/name).resolve()
    if movie.parent!=root:raise ValueError('Segments must be in outputs')
    manifest=json.loads(movie.with_name(movie.stem+'_source_manifest.json').read_text())
    if not manifest['complete'] or abs(manifest['start']-expected)>1e-6:raise ValueError('Incomplete or non-contiguous segment')
    if manifests and manifest['sourceHashes']!=manifests[0]['sourceHashes']:
        if not proof:raise ValueError('Segments use different scene sources')
        previous=manifests[0]
        if (previous['sourceHashes']!=proof['previousSourceHashes']
            or manifest['sourceHashes']!=proof['currentSourceHashes']
            or previous['start']<proof['sampling']['start']
            or previous['start']+previous['seconds']>proof['sampling']['end']):
            raise ValueError('Source differences are not covered by render-input equivalence proof')
    expected+=manifest['seconds'];manifests.append(manifest)
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(movie)]))
    video=next(s for s in meta['streams'] if s['codec_type']=='video')
    signatures.append(tuple(video.get(k) for k in ['codec_name','profile','width','height','pix_fmt','r_frame_rate','time_base','color_range','color_space','color_transfer','color_primaries']))
    if int(video['nb_frames'])!=manifest['frames']:raise ValueError('Frame count differs from manifest')
    scene+=json.loads(movie.with_name(movie.stem+'_scene_audit.json').read_text())
if any(s!=signatures[0] for s in signatures):raise ValueError('Incompatible picture profiles')
listing=destination.with_suffix('.concat.txt')
with listing.open('x') as file:file.write(''.join("file '"+str((root/name).resolve()).replace("'","'\\''")+"'\n" for name in a.segments))
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-c:v','copy','-an','-movflags','+faststart',str(destination)],check=True)
with destination.with_name(destination.stem+'_scene_audit.json').open('x') as file:json.dump(scene,file,indent=2)
with destination.with_name(destination.stem+'_source_manifest.json').open('x') as file:json.dump({**manifests[0],'seconds':expected,'frames':sum(m['frames'] for m in manifests),'segments':a.segments,'segmentSourceManifests':manifests,'renderInputEquivalenceProof':proof,'bitstreamCopy':True,'complete':True},file,indent=2)
print('Saved source-compatible continuous picture:',destination)
