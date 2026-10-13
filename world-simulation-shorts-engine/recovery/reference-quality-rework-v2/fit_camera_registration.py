#!/usr/bin/env python3
"""Register unchanged country GIS to the actual first reference map colour silhouette."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, optimize

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parents[1]
SOURCE = ENGINE / 'recovery/reference-reproduction-v1/evidence/reference_tracking/REFERENCE_REL_00.000_FRAME_160_MAP.png'
GIS = ENGINE / 'recovery/planner-scene-json-v1/data/NATIVE_PENINSULA.json'
OUT = ROOT / 'evidence/camera_registration'
OUT.mkdir(parents=True, exist_ok=True)
W, H, DOWNSAMPLE = 1080, 1920, 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_sha, gis_sha = sha(SOURCE), sha(GIS)
    image = Image.open(SOURCE).convert('RGB')
    small = image.resize((W // DOWNSAMPLE, H // DOWNSAMPLE), Image.Resampling.BOX)
    hsv = np.asarray(small.convert('HSV'))
    hue, sat, val = (hsv[..., i].astype(float) for i in range(3))
    raw = (((hue < 27) & (sat > 145) & (val > 65)) |
           ((hue > 170) & (hue < 220) & (sat > 100) & (val > 60)))
    closed = ndimage.binary_closing(raw, iterations=2)
    labels, count = ndimage.label(closed)
    areas = np.bincount(labels.ravel()); areas[0] = 0
    mainland = labels == int(np.argmax(areas))
    observed = ndimage.binary_fill_holes(mainland)
    valid = np.ones_like(observed, dtype=bool)
    # Phone UI, subtitles and badges cannot establish geographic registration.
    valid[:, 920 // DOWNSAMPLE:] = False
    valid[1640 // DOWNSAMPLE:, :] = False
    valid[1260 // DOWNSAMPLE:1350 // DOWNSAMPLE, :] = False
    badges = [(350, 810, 77), (518, 763, 77), (640, 691, 77),
              (492, 965, 77), (635, 912, 77), (744, 998, 77),
              (588, 1054, 77), (411, 1092, 77)]
    yy, xx = np.mgrid[:H // DOWNSAMPLE, :W // DOWNSAMPLE]
    for x, y, radius in badges:
        valid[((xx * DOWNSAMPLE - x) ** 2 + (yy * DOWNSAMPLE - y) ** 2) < radius ** 2] = False
    records = json.loads(GIS.read_text())['countries']
    polygons = [poly for country in records.values() for poly in country['coordinates']]
    observed_distance = ndimage.distance_transform_edt(~observed)
    observed_inside_distance = ndimage.distance_transform_edt(observed)
    weights = 1 + 2 * np.exp(-(observed_distance + observed_inside_distance) / 3)
    weights *= valid

    def raster(parameters):
        sx, sy, ox, oy = parameters[:4]
        angle = np.deg2rad(parameters[4]) if len(parameters) == 5 else 0
        cosine, sine = np.cos(angle), np.sin(angle)
        def project(lon, lat):
            x, y = sx * (lon - 127.5), -sy * (lat - 38)
            return ((ox + cosine * x - sine * y) / DOWNSAMPLE,
                    (oy + sine * x + cosine * y) / DOWNSAMPLE)
        canvas = Image.new('1', observed.shape[::-1]); draw = ImageDraw.Draw(canvas)
        for polygon in polygons:
            ring = [project(lon, lat) for lon, lat in polygon[0]]
            draw.polygon(ring, fill=1)
            for hole in polygon[1:]:
                draw.polygon([project(lon, lat) for lon, lat in hole], fill=0)
        return np.asarray(canvas, dtype=bool)

    def score(parameters):
        predicted = raster(parameters)
        error = np.sum(weights * (predicted != observed)) / np.sum(weights)
        return float(error)

    result = optimize.differential_evolution(score, [(150, 225), (175, 265), (440, 660), (800, 1140)],
                                             seed=65379, maxiter=90, popsize=10, polish=False, tol=0.0001)
    sx, sy, ox, oy = map(float, result.x)
    west, east = 127.5 - ox / sx, 127.5 + (W - ox) / sx
    north, south = 38 + oy / sy, 38 - (H - oy) / sy
    bounds = [west, south, east, north]
    predicted = raster(result.x)
    intersection = np.count_nonzero(predicted & observed & valid)
    union = np.count_nonzero((predicted | observed) & valid)
    error = np.count_nonzero((predicted != observed) & valid)
    valid_pixels = np.count_nonzero(valid)
    # Compare the former approximate extent through the same finite ROI.
    old = [W / 6.8, H / 9.65, (127.5 - 123.9) * W / 6.8, (42.95 - 38) * H / 9.65]
    old_mask = raster(old)
    old_iou = np.count_nonzero(old_mask & observed & valid) / np.count_nonzero((old_mask | observed) & valid)
    overlay = np.asarray(small).copy()
    pred_edge = predicted ^ ndimage.binary_erosion(predicted)
    obs_edge = observed ^ ndimage.binary_erosion(observed)
    overlay[pred_edge & valid] = [0, 255, 255]
    overlay[obs_edge & valid] = [255, 255, 255]
    Image.fromarray(overlay).resize((W, H), Image.Resampling.NEAREST).save(OUT / 'REGISTRATION_OVERLAY.png')
    Image.fromarray((observed * 255).astype('uint8')).save(OUT / 'OBSERVED_MASK.png')
    report = {
        'status': 'MEASURED_APPROXIMATE_COUNTRY_SILHOUETTE_REGISTRATION',
        'referenceMap': str(SOURCE.relative_to(ENGINE)), 'referenceMapSha256': source_sha,
        'sourceGIS': str(GIS.relative_to(ENGINE)), 'sourceGISSha256': gis_sha,
        'inputGeometryUnchanged': True, 'initialRollDegrees': 0,
        'referenceFrame': 160, 'referencePtsSeconds': 5.181813,
        'mapCropSourcePixels': [0, 211, 1080, 2131],
        'startBounds': bounds, 'degreesExtent': [east - west, north - south],
        'affinePixels': {'longitudeScale': sx, 'latitudeScale': -sy,
                         'longitudeOrigin': 127.5, 'latitudeOrigin': 38,
                         'offset': [ox, oy]},
        'metrics': {'maskedCountryIoU': intersection / union,
                    'formerApproximateBoundsIoU': float(old_iou),
                    'validROIMismatchFraction': error / valid_pixels,
                    'weightedObjective': float(result.fun), 'evaluations': int(result.nfev)},
        'method': 'Fixed original country polygons, HSV ownership mask, silhouette hole fill; deterministic affine scale/translation optimization with phone/badge/subtitle exclusions.',
        'limits': ['Not geodetic certification', 'Simplified existing GIS differs from reference coastline',
                   'Reference country masks are partially occluded', 'No initial absolute roll inferred',
                   'Raster fitting resolution is 4px; relative measured motion is applied separately'],
        'qualityParityClaimed': False, 'requiredTempOnlyFiles': 0,
    }
    assert source_sha == sha(SOURCE) and gis_sha == sha(GIS)
    (OUT / 'REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'startBounds': bounds, 'metrics': report['metrics']}, ensure_ascii=False))
    rotated = optimize.differential_evolution(score, [(150, 225), (175, 265), (440, 660), (800, 1140), (-25, 25)],
                                              seed=65379, maxiter=120, popsize=12, polish=False, tol=0.0001)
    rsx, rsy, rox, roy, initial_roll = map(float, rotated.x)
    angle = np.deg2rad(initial_roll); cosine, sine = np.cos(angle), np.sin(angle)
    delta = np.array([rox-W/2, roy-H/2]); inverse = np.array([[cosine,sine],[-sine,cosine]]) @ delta
    native_center = [127.5-inverse[0]/rsx, 38+inverse[1]/rsy]
    rotated_bounds = [native_center[0]-W/rsx/2,native_center[1]-H/rsy/2,
                      native_center[0]+W/rsx/2,native_center[1]+H/rsy/2]
    rot_mask = raster(rotated.x)
    rot_iou = np.count_nonzero(rot_mask & observed & valid) / np.count_nonzero((rot_mask | observed) & valid)
    rot_overlay = np.asarray(small).copy()
    rot_overlay[(rot_mask ^ ndimage.binary_erosion(rot_mask)) & valid] = [0,255,255]
    rot_overlay[obs_edge & valid] = [255,255,255]
    Image.fromarray(rot_overlay).resize((W,H), Image.Resampling.NEAREST).save(OUT/'ROTATED_REGISTRATION_OVERLAY.png')
    rotated_report = {**report, 'startBounds': rotated_bounds, 'initialRollDegrees': initial_roll,
                      'degreesExtent': [W/rsx, H/rsy],
                      'affinePixels': {'longitudeScale':rsx,'latitudeScale':-rsy,'longitudeOrigin':127.5,
                                       'latitudeOrigin':38,'offset':[rox,roy],'rollDegrees':initial_roll},
                      'metrics':{'maskedCountryIoU':float(rot_iou),'axisAlignedFitIoU':report['metrics']['maskedCountryIoU'],
                                 'weightedObjective':float(rotated.fun),'evaluations':int(rotated.nfev)},
                      'method':'Diagnostic silhouette affine scale/translation/rotation fit; unchanged existing GIS.',
                      'initialAbsoluteRollInferred':True}
    rotated_report['limits'] = [item for item in report['limits'] if item != 'No initial absolute roll inferred']
    (OUT/'ROTATION_DIAGNOSTIC.json').write_text(json.dumps(rotated_report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'diagnosticRotatedStartBounds':rotated_bounds,'initialRollDegrees':initial_roll,
                      'metrics':rotated_report['metrics']},ensure_ascii=False))


if __name__ == '__main__':
    main()
