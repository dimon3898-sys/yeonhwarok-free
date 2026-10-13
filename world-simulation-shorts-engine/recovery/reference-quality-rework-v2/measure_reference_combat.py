#!/usr/bin/python3
"""Measure the eight unit badges actually visible in the selected reference.

Only selected decoded source pixels are read. Matching is local, masked and
normalized; no map coordinates, military simulation or extra cues are inferred.
Screen measurements must be converted with the shared camera registration
before a runtime geographic fixture is created.
"""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import correlate

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'evidence/input_audit/reference'
OUTPUT = ROOT / 'evidence/combat_reference'
INITIAL = [
    ('north_01', 'flag_profile_01', [359, 824], 112),
    ('north_02', 'flag_profile_02', [516, 764], 112),
    ('north_03', 'flag_profile_03', [640, 693], 112),
    ('south_01', 'flag_profile_04', [490, 966], 112),
    ('south_02', 'flag_profile_04', [632, 916], 112),
    ('south_03', 'flag_profile_05', [414, 1092], 112),
    ('south_04', 'flag_profile_05', [591, 1049], 112),
    ('south_05', 'flag_profile_05', [744, 999], 112),
]


def luminance(rgb):
    return np.dot(rgb.astype(np.float32), [0.2126, 0.7152, 0.0722])


def match(image, template, expected, radius=52):
    """Weighted NCC. Mask ignores the changing terrain around each badge."""
    target = luminance(np.asarray(image))
    x, y = expected
    results = []
    for scale in [1.0, 1.025, 1.05]:
        size = max(20, round(template.width * scale))
        resized = template.resize((size, size), Image.Resampling.LANCZOS)
        for rotation in [-3, 0, 3]:
            rotated = resized.rotate(rotation, Image.Resampling.BICUBIC)
            values = luminance(np.asarray(rotated))
            yy, xx = np.mgrid[:size, :size]
            mask = (((xx-(size-1)/2)**2+(yy-(size-1)/2)**2) < (.40*size)**2).astype(np.float32)
            count = float(mask.sum())
            mean = float((values*mask).sum()/count)
            centered = (values-mean)*mask
            norm = float(np.sqrt((centered**2).sum()))
            left = max(0, round(x-size/2-radius))
            top = max(0, round(y-size/2-radius))
            right = min(image.width, round(x+size/2+radius))
            bottom = min(image.height, round(y+size/2+radius))
            region = target[top:bottom, left:right]
            sums = correlate(region, mask, mode='valid', method='fft')
            squares = correlate(region**2, mask, mode='valid', method='fft')
            denominator = np.sqrt(np.maximum(0, squares-sums**2/count))*norm
            numerator = correlate(region, centered, mode='valid', method='fft')
            scores = np.divide(numerator, denominator, out=np.full_like(numerator, -1), where=denominator>1e-6)
            iy, ix = np.unravel_index(np.argmax(scores), scores.shape)
            results.append((float(scores[iy, ix]), [left+ix+size/2, top+iy+size/2], size, rotation))
    return max(results, key=lambda value: value[0])


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted(INPUT.glob('REFERENCE_REL_*.png'))
    if len(files) != 11:
        raise RuntimeError(f'EXPECTED_11_ACTUAL_DECODED_SOURCE_SAMPLES:{len(files)}')
    source_images = [Image.open(path).convert('RGB') for path in files]
    records = []
    templates = {}
    last = {}
    for unit, profile, center, size in INITIAL:
        templates[unit] = source_images[0].crop((center[0]-size//2, center[1]-size//2, center[0]+size//2, center[1]+size//2))
        last[unit] = center
    for index, (path, image) in enumerate(zip(files, source_images)):
        relative = float(re.search(r'REL_([0-9.]+)_', path.name)[1])
        frame = int(re.search(r'FRAME_(\d+)', path.name)[1])
        units = []
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for unit, profile, center, size in INITIAL:
            if index == 0:
                confidence, measured, actual_size, rotation = 1.0, center, size, 0
            else:
                confidence, measured, actual_size, rotation = match(image, templates[unit], last[unit])
                # Sequential local matching follows the visibly growing glyph.
                templates[unit] = image.crop((round(measured[0]-actual_size/2), round(measured[1]-actual_size/2),
                                             round(measured[0]+actual_size/2), round(measured[1]+actual_size/2)))
                last[unit] = measured
            units.append({'id': unit, 'profile_id': profile, 'center_px': measured,
                          'bbox_size_px': actual_size, 'adjacent_template_rotation_ccw_deg': rotation,
                          'masked_ncc': confidence})
            draw.ellipse((measured[0]-4, measured[1]-4, measured[0]+4, measured[1]+4), outline='#00ffff', width=2)
        records.append({'file': str(path.relative_to(ROOT)), 'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'source_frame': frame, 'selected_relative_seconds': relative, 'units': units})
        annotated.crop((180, 580, 880, 1300)).resize((350, 360)).save(OUTPUT/f'MEASURED_{index:02d}.png')
    contact = Image.new('RGB', (1400, 1080), '#161616')
    for index in range(len(records)):
        contact.paste(Image.open(OUTPUT/f'MEASURED_{index:02d}.png'), ((index%4)*350, (index//4)*360))
    contact.save(OUTPUT/'MEASURED_CONTACT.png')
    result = {'schema_version': 'REFERENCE_COMBAT_SCREEN_MEASUREMENTS_V2',
              'method': 'SOURCE_ACTUAL_PIXELS_MASKED_LOCAL_NORMALIZED_CROSS_CORRELATION',
              'coordinate_space': 'ACTUAL_1080x1920_MAP_CROP',
              'source_interval_seconds': [5.181813, 10.181813], 'source_samples': records,
              'source_semantics': 'MODERN_COUNTERFACTUAL_ATTACK_SCENARIO_NOT_KOREAN_WAR',
              'visible_unit_count': 8, 'upper_units': 3, 'lower_units': 5,
              'no_aircraft_or_explosions_in_selected_interval': True,
              'not_a_geographic_accuracy_certificate': True,
              'runtime_requirement': 'CONVERT_SCREEN_MEASUREMENTS_WITH_SHARED_CAMERA_REGISTRATION_TO_GEOGRAPHIC_ANCHORS',
              'quality_limit': 'Authored helmet and flag silhouettes approximate the visible source badges; exact source artwork is not copied.'}
    (OUTPUT/'COMBAT_SCREEN_MEASUREMENTS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'samples': len(records), 'units_per_sample': len(INITIAL),
                      'min_adjacent_ncc': min(unit['masked_ncc'] for row in records[1:] for unit in row['units'])}))


if __name__ == '__main__':
    main()
