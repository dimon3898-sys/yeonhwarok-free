"""Reuse reviewed, identical-format picture segments without recompression."""
import argparse,subprocess,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('segments',nargs='+');a=p.parse_args()
r=Path(__file__).resolve().parents[1]/'outputs'
descriptions=[]
for name in a.segments:
    file=(r/name).resolve()
    if file.parent!=r:raise ValueError('Segments must be in outputs')
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(file)]))
    v=next(x for x in meta['streams'] if x['codec_type']=='video')
    signature=tuple(v.get(k) for k in ['codec_name','profile','width','height','pix_fmt','r_frame_rate','time_base','color_space','color_transfer','color_primaries'])
    descriptions.append(signature)
if any(x!=descriptions[0] for x in descriptions):raise ValueError('Incompatible picture segments')
listing=r/(a.output+'.concat.txt')
listing.write_text(''.join("file '"+str((r/name).resolve()).replace("'","'\\''")+"'\n" for name in a.segments))
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-c:v','copy','-an','-movflags','+faststart',str(r/a.output)],check=True)
print('Concatenated compatible bitstreams:',a.output)
