"""Explicit BT.709/full-range VUI tags without recompressing picture slices."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args()
source=Path(a.source);destination=Path(a.destination)
if destination.exists():raise FileExistsError(destination)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(source),'-map','0:v:0','-c:v','copy','-bsf:v','h264_metadata=video_full_range_flag=1:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1','-color_range','pc','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-an','-movflags','+faststart',str(destination)],check=True)
