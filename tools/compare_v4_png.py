#!/usr/bin/env python3
"""Compare freshly rendered V4 PNGs with immutable approved RGBA pixels."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def compare(expected, actual):
    reference = np.asarray(Image.open(expected).convert('RGBA'))
    candidate = np.asarray(Image.open(actual).convert('RGBA'))
    result = {
        'expected_sha256': hashlib.sha256(Path(expected).read_bytes()).hexdigest(),
        'actual_sha256': hashlib.sha256(Path(actual).read_bytes()).hexdigest(),
        'expected_rgba_sha256': hashlib.sha256(reference.tobytes()).hexdigest(),
        'actual_rgba_sha256': hashlib.sha256(candidate.tobytes()).hexdigest(),
        'expected_dimensions': list(reference.shape[:2][::-1]),
        'actual_dimensions': list(candidate.shape[:2][::-1]),
    }
    if reference.shape != candidate.shape:
        result.update(classification='MISMATCH', reason='DIMENSIONS_DIFFER')
        return result
    delta = np.abs(reference.astype(np.int16) - candidate.astype(np.int16))
    changed = np.any(delta != 0, axis=2)
    count = int(changed.sum())
    ys, xs = np.nonzero(changed)
    result.update(
        changed_pixels=count,
        total_pixels=int(changed.size),
        changed_fraction=float(changed.mean()),
        max_channel_difference=int(delta.max()),
        mean_channel_difference=float(delta.mean()),
        changed_bounds=None if not count else [int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)],
        classification='BIT_EXACT' if result['expected_sha256'] == result['actual_sha256'] else 'PIXEL_EXACT' if count == 0 else 'MISMATCH',
    )
    # Spatial bins locate differences without changing the accepted reference.
    result['spatial_diff'] = []
    height, width = changed.shape
    for row in range(4):
        for col in range(3):
            x0, x1 = width*col//3, width*(col+1)//3
            y0, y1 = height*row//4, height*(row+1)//4
            mask = changed[y0:y1, x0:x1]
            result['spatial_diff'].append({'bounds': [x0,y0,x1,y1], 'changed_pixels': int(mask.sum()), 'mean_channel_difference': float(delta[y0:y1,x0:x1].mean())})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('expected', type=Path)
    parser.add_argument('actual', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = compare(args.expected, args.actual)
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print(output)
    raise SystemExit(0 if report['classification'] in ('BIT_EXACT', 'PIXEL_EXACT') else 1)
