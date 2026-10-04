"""Extract final encoded frames and a timestamp-matched V2/V3 comparison."""
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

project = Path(__file__).resolve().parents[1]
out = project / 'outputs'
v2 = out / 'master_cinematic_20s_v2.mp4'
v3 = out / 'master_cinematic_20s_v3.mp4'
times = [.5, 2, 6, 10, 15, 19]
destination = out / 'VISUAL_COMPARISON_V2_V3.png'
if destination.exists():
    raise FileExistsError(destination)
previews = [('preview_v3_01.png', .5), ('preview_v3_02.png', 6),
            ('preview_v3_03.png', 10), ('preview_v3_04.png', 19),
            ('preview_v3_hero.png', 15)]
for name, _ in previews:
    if (out / name).exists():
        raise FileExistsError(out / name)

def extract(movie, timestamp, target):
    if target.exists():
        raise FileExistsError(target)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                    '-ss', str(timestamp), '-i', str(movie), '-map', '0:v:0',
                    '-frames:v', '1', '-threads', '2', str(target)], check=True)

for name, timestamp in previews:
    extract(v3, timestamp, out / name)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 21)
sheet = Image.new('RGB', (1150, 6 * 1028 + 120), '#080e16')
draw = ImageDraw.Draw(sheet)
draw.text((30, 20), 'MASTER V2                         MASTER V3', font=font, fill='#edf3f8')
draw.text((30, 64), 'Same timestamps / actual decoded MP4 frames', font=small, fill='#9eb1c2')
records = []
for row, timestamp in enumerate(times):
    for column, (version, movie) in enumerate([('v2', v2), ('v3', v3)]):
        target = out / f'comparison_{version}_{timestamp:.2f}.png'
        extract(movie, timestamp, target)
        with Image.open(target) as original:
            frame = original.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS)
        x = 20 + column * 570
        y = 120 + row * 1028
        draw.text((x, y), f'{version.upper()}  {timestamp:.2f} s', font=font, fill='white')
        sheet.paste(frame, (x, y + 42))
        records.append({'version': version, 'time': timestamp, 'frame': target.name})
sheet.save(destination)
with (out / 'v3_frame_comparison_manifest.json').open('x') as file:
    json.dump({'frames': records, 'comparison': destination.name,
               'visual_target': 'Inspected in chat; no local target source was available. '
                                'Target was not recreated or substituted.'}, file, indent=2)
print('Saved exact-time final previews and V2/V3 comparison:', destination)
