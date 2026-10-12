#!/usr/bin/python3
"""Encode actual V4 frames and compare them with immutable approved media.

This helper never renders, changes source, copies a golden frame, or resizes.
Its successful intermediate proof does not complete the permanent gate.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import PIL
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
BACKUP = REPO / 'world-simulation-shorts-engine/recovery/v4/approved-proof'
GOLDEN_MP4 = BACKUP / 'SUEZ_CAMERA_DIRECTOR_V4.mp4'
GOLDEN_MP4_SHA = 'c4021dcf4f809f076e4504955b3600a002e4c991fdd5a21a9971ea0d6ad1e239'
GOLDEN_DIAGNOSTICS_SHA = 'ec80904ea5c29c9dd0b5cb64924aa50fbc6cd8c920e12a0ffd5e7bdf02160ea2'
CHECKPOINT_SHAS = {
    '01_PRIMARY_START.png': 'bcda09ae05ad96cbe55de5ca73fbcce9382c4198ed987227064248baa659dbf0',
    '02_CONTEXT.png': 'f27363af7837552954a54fa07ac8b5c2048a26f04f3799b220ca2775b70b05c5',
    '03_EVENT_APPROACH.png': '6d1570e6c3f587761ccb55c7e9efb94ed82b649679a5970ae80d2e63c189ef32',
    '04_MARKER_GUIDE.png': 'd53fcb5b692d5bc520a666bd138ba9f0633d2b2bb43d083ae2db9573f8fb9b52',
    '05_REGIONAL_LOCK.png': '3a25e738d2741b0b0cd0d8b96831749a7c9c0e308235eae96544231439258b9a',
    '06_EVENT_TITLE.png': 'fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673',
    '07_FINAL_HOLD.png': 'fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673',
}
KNOWN_CHECKPOINTS = {'01_PRIMARY_START.png': 0, '02_CONTEXT.png': 93,
    '03_EVENT_APPROACH.png': 136, '05_REGIONAL_LOCK.png': 269,
    '06_EVENT_TITLE.png': 290, '07_FINAL_HOLD.png': 330}
REVEAL_KEYS = {'reveal', 'guidedReveal', 'revealReadiness'}
FRAME_BYTES = 1080 * 1920 * 4


def utc():
    return datetime.now(timezone.utc).isoformat()


def regular(path):
    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink() or path.resolve() != path:
        raise ValueError('REGULAR_NON_SYMLINK_FILE_REQUIRED')
    return path


def sha(path):
    digest = hashlib.sha256()
    with regular(path).open('rb') as source:
        while data := source.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def load_json(path):
    return json.loads(regular(path).read_text())


def command(argv, **kwargs):
    return subprocess.run([str(v) for v in argv], check=True, text=True, capture_output=True, **kwargs)


def write_json(path, value):
    with Path(path).open('x') as target:
        json.dump(value, target, indent=2, ensure_ascii=False)
        target.write('\n')


def rgba(path):
    with Image.open(regular(path)) as image:
        if image.size != (1080, 1920):
            raise ValueError('CANONICAL_PNG_DIMENSIONS_REQUIRED')
        return np.array(image.convert('RGBA'))


def inventory(args):
    directory = args.frames_dir.absolute()
    if not directory.is_dir() or directory.resolve() != directory:
        raise ValueError('REGULAR_FRAMES_DIRECTORY_REQUIRED')
    receipt = load_json(directory / 'runtime-diagnostic.json')
    if receipt.get('kind') != 'v4_runtime_diagnostic' or receipt.get('mode') != 'frames' or receipt.get('status') != 'RENDERED':
        raise ValueError('ACTUAL_375_RENDER_RECEIPT_REQUIRED')
    if receipt.get('errors') or receipt.get('command', {}).get('exit_code') != 0:
        raise ValueError('RENDER_RECEIPT_NOT_SUCCESSFUL')
    commit = command(['git', 'rev-parse', 'HEAD'], cwd=REPO).stdout.strip()
    if receipt.get('source_commit') != commit:
        raise ValueError('RENDER_SOURCE_COMMIT_MISMATCH')
    inputs = receipt.get('required_inputs')
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('RENDER_INPUT_INVENTORY_REQUIRED')
    for name, record in inputs.items():
        file = regular(REPO / name)
        if not file.is_relative_to(REPO) or sha(file) != record['sha256'] or file.stat().st_size != record['bytes']:
            raise ValueError('RENDER_INPUT_BYTES_CHANGED')
    outputs = receipt.get('outputs', [])
    by_frame = {item['frame']: item for item in outputs}
    expected = {f'frame-{i:03d}.png' for i in range(375)}
    actual = {file.name for file in directory.glob('frame-*.png')}
    if len(outputs) != 375 or set(by_frame) != set(range(375)) or actual != expected:
        raise ValueError('EXACT_375_FRAME_INVENTORY_REQUIRED')
    records = []
    for frame in range(375):
        file = regular(directory / f'frame-{frame:03d}.png')
        item = by_frame[frame]
        if Path(item['path']).absolute() != file or sha(file) != item['sha256'] or file.stat().st_size != item['bytes']:
            raise ValueError('ACTUAL_FRAME_RECEIPT_HASH_MISMATCH')
        with Image.open(file) as image:
            if image.format != 'PNG' or image.size != (1080, 1920):
                raise ValueError('CANONICAL_REAL_PNG_REQUIRED')
            image.verify()
        records.append({'frame': frame, 'sha256': item['sha256'], 'bytes': item['bytes']})
    if sha(args.golden_mp4) != GOLDEN_MP4_SHA or args.golden_mp4.stat().st_size != 14100953:
        raise ValueError('APPROVED_MP4_HASH_MISMATCH')
    if sha(args.golden_diagnostics) != GOLDEN_DIAGNOSTICS_SHA:
        raise ValueError('APPROVED_DIAGNOSTICS_HASH_MISMATCH')
    for filename, expected_sha in CHECKPOINT_SHAS.items():
        if sha(args.golden_checkpoints_dir / filename) != expected_sha:
            raise ValueError('APPROVED_CHECKPOINT_HASH_MISMATCH')
    return {'source_commit': commit, 'required_inputs': inputs, 'frames': records,
            'render_receipt_sha256': sha(directory / 'runtime-diagnostic.json'),
            'working_tree_clean': not command(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=REPO).stdout.strip()}


def probe(file, ffprobe):
    data = json.loads(command([ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_streams', '-show_packets', '-show_format', '-of', 'json', file], timeout=120).stdout)
    stream = data['streams'][0]
    packets = data['packets']
    time_base = Fraction(stream['time_base'])
    timestamps = sorted(Fraction(packet['pts']) * time_base for packet in packets)
    correct = (stream['codec_name'] == 'h264' and stream['width'] == 1080 and stream['height'] == 1920
        and stream['pix_fmt'] == 'yuv420p' and Fraction(stream['avg_frame_rate']) == 30
        and Fraction(stream['r_frame_rate']) == 30 and int(stream['nb_frames']) == 375
        and len(packets) == 375 and timestamps == [Fraction(i, 30) for i in range(375)]
        and all(Fraction(packet['duration']) * time_base == Fraction(1, 30) for packet in packets)
        and Fraction(stream['duration']) == Fraction(25, 2) and Fraction(data['format']['duration']) == Fraction(25, 2))
    return {'pass': correct, 'codec': stream['codec_name'], 'dimensions': [stream['width'], stream['height']],
        'pixel_format': stream['pix_fmt'], 'fps': stream['avg_frame_rate'], 'frames': len(packets),
        'time_base': stream['time_base'], 'duration': stream['duration'], 'packet_timing_exact': correct,
        'stream_encoder': stream.get('tags', {}).get('encoder'), 'container_encoder': data['format'].get('tags', {}).get('encoder')}


def sei(file):
    data = regular(file).read_bytes()
    start = data.find(b'x264 - core')
    if start < 0:
        raise ValueError('X264_SEI_REQUIRED')
    end = data.find(b'\0', start)
    text = data[start:end if end >= 0 else start + 4096].decode('ascii')
    prefix, options = text.split(' - options: ', 1)
    return {'core': prefix.split(' - H.264/', 1)[0], 'options': dict(re.findall(r'(\S+)=(\S+)', options))}


def checkpoints(args, directory):
    mapping = dict(KNOWN_CHECKPOINTS)
    if args.checkpoint_map:
        supplied = load_json(args.checkpoint_map)
        if set(supplied) != set(CHECKPOINT_SHAS) or any(type(v) is not int or not 0 <= v < 375 for v in supplied.values()):
            raise ValueError('EXPLICIT_SEVEN_CHECKPOINT_MAP_REQUIRED')
        if any(supplied[k] != v for k, v in KNOWN_CHECKPOINTS.items()):
            raise ValueError('SAVED_CAMERA_CHECKPOINT_BINDING_CHANGED')
        mapping = supplied
    rows = []
    for filename in CHECKPOINT_SHAS:
        expected = rgba(args.golden_checkpoints_dir / filename)
        candidates = [mapping[filename]] if filename in mapping else range(375)
        matches = []
        mapped_difference = None
        for frame in candidates:
            actual_file = directory / f'frame-{frame:03d}.png'
            candidate = rgba(actual_file)
            if filename in mapping:
                delta = np.abs(candidate.astype(np.int16) - expected.astype(np.int16))
                mapped_difference = {'frame': frame, 'actual_png_sha256': sha(actual_file),
                    'expected_png_sha256': CHECKPOINT_SHAS[filename],
                    'actual_rgba_sha256': hashlib.sha256(candidate.tobytes()).hexdigest(),
                    'expected_rgba_sha256': hashlib.sha256(expected.tobytes()).hexdigest(),
                    'changed_pixels': int(np.any(delta != 0, axis=2).sum()),
                    'max_channel_difference': int(delta.max())}
            if np.array_equal(candidate, expected):
                matches.append({'frame': frame, 'classification': 'BIT_EXACT' if sha(actual_file) == CHECKPOINT_SHAS[filename] else 'PIXEL_EXACT'})
        rows.append({'filename': filename, 'pass': bool(matches), 'matching_frames': matches,
                     'mapped_frame_difference': mapped_difference,
                     'frame_binding': 'SAVED_CAMERA_CHECKPOINT' if filename in KNOWN_CHECKPOINTS else
                         'EXPLICIT_MAP' if args.checkpoint_map else 'PIXEL_IDENTIFIED_CAPTURE_ORIGINAL_FRAME_UNKNOWN'})
    return {'pass': all(row['pass'] for row in rows), 'checked': len(rows), 'rows': rows}


def diagnostics(args, directory):
    old_rows = [json.loads(line) for line in regular(args.golden_diagnostics).read_text().splitlines() if line]
    if len(old_rows) != 375 or [row['frame'] for row in old_rows] != list(range(375)):
        raise ValueError('APPROVED_375_DIAGNOSTICS_REQUIRED')
    rows = []
    for frame, old in enumerate(old_rows):
        capture = load_json(directory / f'frame-{frame:03d}.diagnostic.json')
        current = capture['diagnostic']['frameDiagnostic']
        camera_keys = set(old) - REVEAL_KEYS - {'gpu', 'layoutChoice'}
        camera_diff = sorted(key for key in camera_keys if current.get(key) != old[key])
        reveal_diff = sorted(key for key in REVEAL_KEYS if current.get(key) != old[key])
        gpu = current.get('gpu', {})
        valid = (current['frame'] == frame and gpu.get('glError') == 0 and gpu.get('factoryCount') == 1
            and gpu.get('finishedFrameMix') is False and gpu.get('projectionChange') is False
            and gpu.get('actualPrimaryMaterial') == 1 and capture['backend']['preserveDrawingBuffer'] is True
            and capture['backend']['dimensions'] == [1080, 1920])
        rows.append({'frame': frame, 'camera_exact': not camera_diff, 'reveal_exact': not reveal_diff,
                     'gpu_validation_pass': valid, 'camera_differing_fields': camera_diff, 'reveal_differing_fields': reveal_diff})
    return {'pass': all(row['camera_exact'] and row['reveal_exact'] and row['gpu_validation_pass'] for row in rows),
            'checked': 375, 'camera_mismatched_frames': sum(not row['camera_exact'] for row in rows),
            'reveal_mismatched_frames': sum(not row['reveal_exact'] for row in rows), 'rows': rows}


def read_frame(pipe):
    parts = []
    remaining = FRAME_BYTES
    while remaining:
        data = pipe.read(remaining)
        if not data:
            raise ValueError('DECODED_FRAME_TRUNCATED')
        parts.append(data)
        remaining -= len(data)
    return b''.join(parts)


def decoded_video(args, encoded, out):
    processes = []
    logs = []
    rows = []
    total_changed = 0
    max_channel = 0
    try:
        for label, file in [('golden', args.golden_mp4), ('actual', encoded)]:
            log = (out / f'decode-{label}.log').open('xb')
            logs.append(log)
            argv = [args.ffmpeg, '-v', 'error', '-nostdin', '-threads', '2', '-i', str(file),
                    '-map', '0:v:0', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1']
            processes.append(subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=log))
        with (out / 'decoded-frame-comparison.jsonl').open('x') as catalog:
            for frame in range(375):
                expected, actual = [read_frame(process.stdout) for process in processes]
                a_sha, b_sha = hashlib.sha256(expected).hexdigest(), hashlib.sha256(actual).hexdigest()
                changed, maximum = 0, 0
                if expected != actual:
                    a = np.frombuffer(expected, dtype=np.uint8).reshape(1920, 1080, 4)
                    b = np.frombuffer(actual, dtype=np.uint8).reshape(1920, 1080, 4)
                    changed = int(np.any(a != b, axis=2).sum())
                    maximum = int(np.abs(a.astype(np.int16) - b.astype(np.int16)).max())
                total_changed += changed
                max_channel = max(max_channel, maximum)
                row = {'frame': frame, 'time_seconds_rational': str(Fraction(frame, 30)),
                    'expected_rgba_sha256': a_sha, 'actual_rgba_sha256': b_sha,
                    'changed_pixels': changed, 'max_channel_difference': maximum, 'pixel_exact': changed == 0}
                catalog.write(json.dumps(row) + '\n')
                rows.append(row)
                if frame % 30 == 0 or frame == 374:
                    print(json.dumps({'event': 'DECODE_COMPARE_PROGRESS', 'completed_frames': frame + 1, 'changed_pixels': total_changed}), flush=True)
        if any(process.stdout.read(1) for process in processes):
            raise ValueError('UNEXPECTED_EXTRA_DECODED_FRAMES')
        if any(process.wait(timeout=30) != 0 for process in processes):
            raise ValueError('FFMPEG_DECODE_FAILED')
        return {'pass': total_changed == 0, 'decoded_frames': len(rows), 'total_changed_pixels': total_changed,
                'max_channel_difference': max_channel, 'mismatched_frames': sum(not row['pixel_exact'] for row in rows),
                'comparison': 'DECODED_MP4_TO_DECODED_MP4_RGBA_EXACT', 'source_png_to_lossy_video': 'NOT_USED_AS_EQUALITY_CRITERION'}
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout:
                process.stdout.close()
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--golden-mp4', type=Path, default=GOLDEN_MP4)
    parser.add_argument('--golden-checkpoints-dir', type=Path, default=BACKUP)
    parser.add_argument('--golden-diagnostics', type=Path, default=BACKUP / 'frame-diagnostics.jsonl')
    parser.add_argument('--checkpoint-map', type=Path)
    parser.add_argument('--diagnostic-encode', action='store_true',
                        help='Allow checkpoint pixel differences for a review video; never bypass metadata or Camera/Reveal checks')
    parser.add_argument('--ffmpeg', default='/usr/bin/ffmpeg')
    parser.add_argument('--ffprobe', default='/usr/bin/ffprobe')
    args = parser.parse_args()
    for name in ('frames_dir', 'output_dir', 'golden_mp4', 'golden_checkpoints_dir', 'golden_diagnostics', 'checkpoint_map'):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).absolute())
    if sys.version_info[:3] != (3, 13, 5) or np.__version__ != '2.2.4' or PIL.__version__ != '11.1.0':
        raise ValueError('PINNED_SYSTEM_PYTHON_NUMPY_PILLOW_REQUIRED')
    version = command([args.ffmpeg, '-version']).stdout.splitlines()[0]
    if not version.startswith('ffmpeg version 7.1.5-'):
        raise ValueError('FFMPEG_7_1_5_REQUIRED')
    original = inventory(args)
    out = args.output_dir.absolute()
    if out.is_relative_to(REPO) or out.parent.resolve() != out.parent:
        raise ValueError('SEPARATE_REGULAR_OUTPUT_DIRECTORY_REQUIRED')
    out.mkdir()  # Never overwrite prior evidence or a golden file.
    report = {'schema': 1, 'kind': 'v4_video_reproduction', 'status': 'STARTED', 'started_at_utc': utc(),
        'source_commit': original['source_commit'], 'render_inventory': original, 'ffmpeg': version,
        'python': sys.version, 'numpy': np.__version__, 'Pillow': PIL.__version__,
        'permanent_gate_complete': False, 'diagnostic_encode': args.diagnostic_encode,
        'validation_failures': [], 'errors': []}
    try:
        report['golden_metadata'] = probe(args.golden_mp4, args.ffprobe)
        report['golden_x264_sei'] = sei(args.golden_mp4)
        report['checkpoint_comparison'] = checkpoints(args, args.frames_dir)
        report['camera_reveal_comparison'] = diagnostics(args, args.frames_dir)
        if not (report['golden_metadata']['pass'] and report['camera_reveal_comparison']['pass']):
            raise ValueError('FRAME_CHECKPOINT_OR_CAMERA_REVEAL_VALIDATION_FAILED')
        if not report['checkpoint_comparison']['pass']:
            report['validation_failures'].append('CHECKPOINT_PNG_PIXEL_MISMATCH')
            if not args.diagnostic_encode:
                raise ValueError('FRAME_CHECKPOINT_OR_CAMERA_REVEAL_VALIDATION_FAILED')
        encoded = out / 'v4-reproduction.mp4'
        argv = [args.ffmpeg, '-hide_banner', '-loglevel', 'warning', '-nostdin', '-n', '-framerate', '30',
                '-start_number', '0', '-i', str(args.frames_dir / 'frame-%03d.png'), '-frames:v', '375',
                '-c:v', 'libx264', '-preset', 'faster', '-crf', '16', '-threads', '2', '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', '-an', str(encoded)]
        report['encode_command'] = {'argv': argv, 'cwd': str(REPO),
            'parameter_provenance': 'SEI_EQUIVALENT_FASTER_CRF16_THREADS2; historical CLI tokens unknown',
            'visual_filters': [], 'resizing': False}
        with (out / 'encode.log').open('xb') as log:
            result = subprocess.run(argv, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=False)
        report['encode_command']['exit_code'] = result.returncode
        if result.returncode != 0:
            raise ValueError('FFMPEG_ENCODE_FAILED')
        report['actual_x264_sei'] = sei(encoded)
        report['encoding_settings_exact'] = report['actual_x264_sei'] == report['golden_x264_sei']
        report['actual_metadata'] = probe(encoded, args.ffprobe)
        report['decoded_comparison'] = decoded_video(args, encoded, out)
        current_inventory = inventory(args)
        if current_inventory != original:
            raise ValueError('SOURCE_OR_INPUT_CHANGED_DURING_VIDEO_REPRODUCTION')
        output_sha = sha(encoded)
        report['output'] = {'path': str(encoded), 'sha256': output_sha, 'bytes': encoded.stat().st_size}
        if not report['encoding_settings_exact']:
            report['validation_failures'].append('ENCODING_SETTINGS_MISMATCH')
        if not report['actual_metadata']['pass']:
            report['validation_failures'].append('ACTUAL_VIDEO_METADATA_MISMATCH')
        if not report['decoded_comparison']['pass']:
            report['validation_failures'].append('DECODED_VIDEO_RGBA_MISMATCH')
        technical_pass = report['encoding_settings_exact'] and report['actual_metadata']['pass']
        passed = technical_pass and report['decoded_comparison']['pass'] and report['checkpoint_comparison']['pass']
        report['status'] = 'PASS' if passed else 'USER_VISUAL_REVIEW_REQUIRED' if args.diagnostic_encode and technical_pass else 'FAIL'
        report['validation'] = 'PASS' if passed else 'FAIL'
        report['automatic_reproduction_pass'] = passed
        report['review_video_created'] = bool(args.diagnostic_encode and technical_pass)
        report['classification'] = 'BIT_EXACT' if passed and output_sha == GOLDEN_MP4_SHA else 'PIXEL_EXACT' if passed else 'MISMATCH'
    except Exception as error:
        report['status'] = 'FAIL' if str(error) == 'FRAME_CHECKPOINT_OR_CAMERA_REVEAL_VALIDATION_FAILED' else 'ERROR'
        report['errors'].append(type(error).__name__ + ': ' + str(error)[:1024])
    finally:
        report['completed_at_utc'] = utc()
        write_json(out / 'video-reproduction-summary.json', report)
    print(json.dumps({'status': report['status'], 'classification': report.get('classification'),
                      'report': str(out / 'video-reproduction-summary.json')}), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'ERROR', 'reason': type(error).__name__ + ': ' + str(error)[:1024]}), file=sys.stderr)
        raise SystemExit(1) from None
