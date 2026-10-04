"""Set complete BT.709 limited-range VUI without re-encoding picture slices."""
import argparse, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args()
source=Path(a.source);destination=Path(a.destination)
if destination.exists():raise FileExistsError(destination)
credits=(Path(__file__).resolve().parents[1]/'assets/v3/CREDITS_V3.txt').read_text()
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(source),'-map','0:v:0','-c:v','copy','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-metadata','title=CINEMATIC WORLD MAP — MASTER V3','-metadata','comment='+credits,'-an','-movflags','+faststart',str(destination)],check=True)
print('Saved picture-preserving BT.709 VUI:',destination)
