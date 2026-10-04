"""Mux original sound against exactly the same approved silent picture."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--seconds',type=float,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1]
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-i',str(r/'outputs'/f'{a.name}_muted.mp4'),'-i',str(r/'assets/audio/v2/score_master.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','volume=-0.6dB','-c:a','aac','-b:a','320k','-ar','48000','-t',str(a.seconds),'-movflags','+faststart',str(r/'outputs'/f'{a.name}.mp4')],check=True)
print('Muxed',a.name)
