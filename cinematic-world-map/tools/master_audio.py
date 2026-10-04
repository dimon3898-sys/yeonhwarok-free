"""Reproducible EBU R128 two-pass measurement and controlled mastering."""
import subprocess,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'assets/audio/score_raw.wav'
proc=subprocess.run(['ffmpeg','-hide_banner','-i',str(source),'-af','loudnorm=I=-20:TP=-2:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
data=json.loads(re.findall(r'\{[^{}]+\}',proc.stderr)[-1])
filter=f"loudnorm=I=-20:TP=-2:LRA=8:measured_I={data['input_i']}:measured_TP={data['input_tp']}:measured_LRA={data['input_lra']}:measured_thresh={data['input_thresh']}:offset={data['target_offset']}:linear=false:print_format=json"
proc=subprocess.run(['ffmpeg','-hide_banner','-y','-i',str(source),'-af',filter,'-ar','48000','-c:a','pcm_s24le',str(root/'assets/audio/score_master.wav')],capture_output=True,text=True,check=True)
result=json.loads(re.findall(r'\{[^{}]+\}',proc.stderr)[-1])
(root/'assets/audio/mastering.json').write_text(json.dumps(dict(measurement=data,result=result),indent=2))
print(json.dumps(result,indent=2))
