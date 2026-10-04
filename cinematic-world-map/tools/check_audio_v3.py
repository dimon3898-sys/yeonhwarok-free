"""Measure the actual encoded soundtrack; never claim direct listening."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import correlate, correlation_lags

project = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('movie')
p.add_argument('--output', default='outputs/v3_final_audio_validation.json')
a = p.parse_args()
movie = (project / a.movie).resolve()
destination = (project / a.output).resolve()
log = destination.with_suffix('.loudness.log')
for file in (destination, log):
    if file.exists():
        raise FileExistsError(file)

def run(arguments):
    return subprocess.run(arguments, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)

probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                       '-of', 'json', str(movie)]).stdout)
stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
assert stream['codec_name'] == 'aac' and int(stream['sample_rate']) == 48000
assert stream['channels'] == 2 and abs(float(stream['duration']) - 20) < .025
measurement = run(['ffmpeg', '-hide_banner', '-i', str(movie), '-map', '0:a:0',
                   '-af', 'loudnorm=I=-18.5:TP=-2.2:LRA=9:print_format=json',
                   '-f', 'null', '-'])
diagnostics = measurement.stderr.decode()
matches = re.findall(r'\{\s*"input_i"[\s\S]*?\}', diagnostics)
if not matches:
    raise ValueError('Actual AAC loudness measurements were not returned')
stats = json.loads(matches[-1])
with log.open('x') as f:
    f.write(diagnostics)

def pcm(file):
    raw = run(['ffmpeg', '-v', 'error', '-i', str(file), '-map', '0:a:0',
               '-ar', '48000', '-ac', '2', '-c:a', 'pcm_f32le', '-f', 'f32le',
               'pipe:1']).stdout
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2)

decoded = pcm(movie)
reference = pcm(project / 'assets/audio/v3/score_master.wav')
assert len(decoded) >= 20 * 48000 and len(reference) == 20 * 48000
# AAC packets can expose encoder padding when decoded to raw PCM. The MP4
# stream/edit duration is checked above; evaluate its audible 20-second range.
audible = decoded[:20 * 48000]
rate, step, span = 4000, 12, 6 * 48000
x = audible[:span:step].mean(axis=1).astype(np.float64)
y = reference[:span:step].mean(axis=1).astype(np.float64)
x -= x.mean()
y -= y.mean()
lags = correlation_lags(len(x), len(y), mode='full')
cross = correlate(x, y, mode='full', method='fft')
near = np.abs(lags) <= rate // 2
best = np.flatnonzero(near)[np.argmax(cross[near])]
lag = int(lags[best])
alignment = float(cross[best] / np.sqrt(np.dot(x, x) * np.dot(y, y)))

def db_rms(samples):
    return float(20 * np.log10(max(float(np.sqrt(np.mean(samples ** 2))), 1e-12)))

result = {
    'file': movie.name,
    'codec': 'aac', 'sample_rate': 48000, 'channels': 2,
    'stream_duration': float(stream['duration']),
    'actual_aac_integrated_lufs': float(stats['input_i']),
    'actual_aac_true_peak_dbtp': float(stats['input_tp']),
    'actual_aac_loudness_range_lu': float(stats['input_lra']),
    'actual_aac_sample_peak_dbfs': float(20 * np.log10(np.max(np.abs(audible)))),
    'pcm_decoded_samples_per_channel_including_packet_padding': len(decoded),
    'audible_samples_per_channel': len(audible),
    'decoded_pcm_sha256': hashlib.sha256(audible.tobytes()).hexdigest(),
    'soundtrack_alignment_lag_seconds': lag / rate,
    'alignment_measurement_resolution_seconds': 1 / rate,
    'alignment_correlation': alignment,
    'per_second_rms_dbfs': [db_rms(audible[i * 48000:(i + 1) * 48000]) for i in range(20)],
    'last_20ms_rms_dbfs': db_rms(audible[-960:]),
    'last_100ms_rms_dbfs': db_rms(audible[-4800:]),
    'direct_listening': False,
    'scope': 'Actual AAC decoding, measured loudness/true peak and 6-second '
             'cross-correlation against the original score. Uses loudnorm INPUT '
             'measurements, not its proposed OUTPUT. Does not certify listening quality.',
}
assert result['actual_aac_true_peak_dbtp'] < -1
assert abs(result['soundtrack_alignment_lag_seconds']) <= 1 / 30
assert alignment > .95
with destination.open('x') as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
