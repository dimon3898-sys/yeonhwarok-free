"""Verify final silent-picture identity and the reviewed first-ten-second prefix."""
import hashlib
import json
import subprocess
from pathlib import Path

project = Path(__file__).resolve().parents[1]
outputs = project / 'outputs'
destination = outputs / 'v3_final_picture_identity.json'
if destination.exists():
    raise FileExistsError(destination)
movie = outputs / 'master_cinematic_20s_v3_muted.mp4'
probe = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(movie)]))
assert not any(s['codec_type'] == 'audio' for s in probe['streams'])
video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
assert (video['width'], video['height']) == (1080, 1920)
assert video['codec_name'] == 'h264' and video['r_frame_rate'] == '30/1'
assert float(probe['format']['duration']) == 20
assert video['color_range'] == 'tv'
assert all(video.get(key) == 'bt709' for key in ('color_space', 'color_transfer', 'color_primaries'))
decoder = subprocess.Popen([
    'ffmpeg', '-v', 'error', '-threads', '4', '-i', str(movie), '-map', '0:v:0',
    '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], stdout=subprocess.PIPE)
frame_bytes = 1080 * 1920 * 3
full, prefix = hashlib.sha256(), hashlib.sha256()
count = 0
while True:
    data = decoder.stdout.read(frame_bytes)
    if not data:
        break
    assert len(data) == frame_bytes, 'Incomplete decoded frame'
    full.update(data)
    if count < 300:
        prefix.update(data)
    count += 1
assert decoder.wait() == 0 and count == 600
final = json.loads((outputs / 'master_cinematic_20s_v3_validation_v3.json').read_text())
review = json.loads((outputs / 'v3_preview_10s_r15_validation_v3.json').read_text())
assert full.hexdigest() == final['all_decoded_rgb_sha256'], 'Sound and silent pictures differ'
assert prefix.hexdigest() == review['all_decoded_rgb_sha256'], 'Reviewed prefix changed'
result = {
    'silent_movie': movie.name, 'frames': count, 'duration': 20,
    'all_decoded_rgb_sha256': full.hexdigest(),
    'first_300_decoded_rgb_sha256': prefix.hexdigest(),
    'matches_sound_master_all_frames': True,
    'matches_reviewed_r15_first_ten_seconds': True,
    'scope': 'Actual full-resolution decoded RGB of the final silent MP4, compared '
             'with independently decoded final sound-master and reviewed r15 prefix.'}
with destination.open('x') as file:
    json.dump(result, file, indent=2)
print(json.dumps(result, indent=2))
