"""Decode actual completed Studio movies; never render or approve visual quality."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def exclusive(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def audit(name, path, output, expected_frames):
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-show_streams',
        '-show_format', '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    info = json.loads(probe.stdout)
    streams = [s for s in info['streams'] if s['codec_type'] == 'video']
    if len(streams) != 1:
        raise ValueError('ONE_VIDEO_STREAM_REQUIRED')
    stream = streams[0]
    count = int(stream['nb_read_frames'])
    fps = stream['avg_frame_rate']
    checks = {
        'h264': stream['codec_name'] == 'h264',
        'resolution': (stream['width'], stream['height']) == (1080, 1920),
        'fps30': fps == '30/1',
        'boundedShortDemo': 2 <= count <= 240,
        'matchesRequestedFrameBudget': count == expected_frames,
        'declaredFrameCount': int(stream.get('nb_frames', count)) == count,
        'durationFrameAgreement': abs(float(stream['duration']) - count / 30) < 0.001,
    }
    times = json.loads(subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'frame=best_effort_timestamp_time', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True).stdout)['frames']
    timestamps = [float(frame['best_effort_timestamp_time']) for frame in times]
    checks['presentationTimestamps'] = len(timestamps) == count and all(
        abs(value - i / 30) < 0.000002 for i, value in enumerate(timestamps))

    # Every encoded frame is decoded. Store thumbnails and measurements only,
    # rather than retaining full-resolution video frames in memory.
    process = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-i', str(path), '-an', '-vf', 'scale=180:320',
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    size = 180 * 320 * 3
    rows, thumbnails, previous = [], [], None
    while True:
        data = bytearray()
        while len(data) < size:
            chunk = process.stdout.read(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if not data:
            break
        if len(data) != size:
            raise ValueError('TRUNCATED_DECODE_FRAME')
        pixels = np.frombuffer(data, np.uint8).reshape(320, 180, 3)
        black = float((pixels.max(axis=2) < 4).mean())
        deviation = float(pixels.std())
        delta = None if previous is None else float(np.abs(
            pixels.astype(np.int16) - previous.astype(np.int16)).mean())
        rows.append({'frame': len(rows), 'timeSeconds': len(rows) / 30,
                     'blackPixelFraction': black, 'rgbStandardDeviation': deviation,
                     'meanAbsolutePreviousDifference': delta,
                     'thumbnailSHA256': hashlib.sha256(data).hexdigest()})
        thumbnails.append(Image.fromarray(pixels.copy()))
        previous = pixels.copy()
    error = process.stderr.read().decode('utf-8', 'replace')
    exit_code = process.wait()
    checks['fullDecode'] = exit_code == 0 and not error.strip() and len(rows) == count
    checks['noBlackFrames'] = all(row['blackPixelFraction'] < 0.98 for row in rows)
    checks['nonemptyFrames'] = all(row['rgbStandardDeviation'] > 2 for row in rows)
    # Identical held frames can be intentional; report them without calling
    # them encoder duplication or deleting any frames.
    identical = [row['frame'] for row in rows if row['meanAbsolutePreviousDifference'] == 0]
    columns, cell_width, cell_height = 10, 180, 342
    sheet = Image.new('RGB', (columns * cell_width,
                             ((count + columns - 1) // columns) * cell_height), '#111827')
    draw = ImageDraw.Draw(sheet)
    for i, thumbnail in enumerate(thumbnails):
        x, y = i % columns * cell_width, i // columns * cell_height
        sheet.paste(thumbnail, (x, y))
        draw.text((x + 3, y + 323), f'{name} f{i} {i/30:.2f}s', fill='white')
    sheet_path = output / f'{name}_ALL_FRAMES.png'
    if sheet_path.exists():
        raise ValueError('REFUSE_EXISTING_AUDIT_ARTIFACT')
    sheet.save(sheet_path)
    with (output / f'{name}_FRAMES.csv').open('x', newline='') as stream_out:
        writer = csv.DictWriter(stream_out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for index in sorted({0, count // 2, count - 1}):
        destination = output / f'{name}_F{index:03d}.png'
        subprocess.run([
            'ffmpeg', '-v', 'error', '-n', '-i', str(path), '-vf', f'select=eq(n\\,{index})',
            '-frames:v', '1', str(destination)], check=True, capture_output=True)
    return {
        'name': name, 'videoSHA256': digest(path), 'frames': count,
        'seconds': count / 30, 'codec': stream['codec_name'],
        'resolution': [stream['width'], stream['height']], 'fps': fps,
        'technicalChecks': checks,
        'technicalStatus': 'PASS' if all(checks.values()) else 'FAIL',
        'decodedIdenticalConsecutiveFrameIndices': identical,
        'identicalFramesInterpretation': 'MEASUREMENT_ONLY_INTENTIONAL_HOLDS_POSSIBLE',
        'automaticAuditDoesNotProve': ['geographicTruth', 'absenceOfAllVisibleSeams',
                                      'featureDataPixelAgreement', 'visualQualityApproval'],
        'visualQuality': 'QUALITY_REVIEW_REQUIRED',
        'softwareRenderingOnly': True, 'nvidiaVerified': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', action='append', required=True, help='NAME=MP4_PATH')
    parser.add_argument('--expected-frames', action='append', required=True, help='NAME=INPUT_FRAME_COUNT')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    expected = dict(value.split('=', 1) for value in args.expected_frames)
    results = []
    for value in args.video:
        name, filename = value.split('=', 1)
        if not name or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in name):
            raise ValueError('SAFE_ARTIFACT_NAME_REQUIRED')
        if name not in expected:
            raise ValueError('EXPLICIT_REQUESTED_FRAME_BUDGET_REQUIRED')
        results.append(audit(name, Path(filename), args.output, int(expected[name])))
    result = {'schema': 'WORLD_ENGINE_DATA_VIDEO_AUDIT_V1', 'movies': results,
              'technicalStatus': 'PASS' if all(r['technicalStatus'] == 'PASS' for r in results) else 'FAIL',
              'visualQuality': 'QUALITY_REVIEW_REQUIRED', 'userApproved': False}
    exclusive(args.output / 'VIDEO_AUDIT.json', (json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['technicalStatus'] == 'PASS' else 1)
