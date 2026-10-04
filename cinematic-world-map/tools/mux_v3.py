"""Add the original V3 score without re-encoding the approved picture."""
import argparse, subprocess
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--input',required=True)
p.add_argument('--output',required=True)
p.add_argument('--start',type=float,default=0)
p.add_argument('--seconds',type=float,default=20)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
picture=root/'outputs'/a.input
destination=root/'outputs'/a.output
if destination.exists():raise FileExistsError(destination)
credits=(root/'assets/v3/CREDITS_V3.txt').read_text()
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(picture),'-ss',str(a.start),'-i',str(root/'assets/audio/v3/score_master.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','volume=-0.3dB','-c:a','aac','-b:a','320k','-ar','48000','-t',str(a.seconds),'-metadata','title=CINEMATIC WORLD MAP — MASTER V3','-metadata','comment='+credits,'-movflags','+faststart',str(destination)],check=True)
print('Saved picture-preserving soundtrack mux:',destination)
