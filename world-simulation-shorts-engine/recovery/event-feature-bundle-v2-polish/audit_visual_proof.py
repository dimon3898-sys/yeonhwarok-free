#!/usr/bin/env python3
"""Read-only MP4 inspection preparation; visual PASS requires a separate human/agent image review.

Extracts private decoded contact PNGs from the existing Candidate MP4. It never
renders geographic frames, encodes/replaces video, or writes Public Review files.
"""
import hashlib
import json
import math
import struct
import subprocess
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
FRAMES = [0, 26, 60, 72, 80, 88, 100, 120, 145, 157, 170, 187, 192, 199, 206, 239]
VIDEO_NAME = 'SUEZ_EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH.mp4'


def digest(file):
    body = file.read_bytes()
    return {'path': file.relative_to(REPO).as_posix(), 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}


def read_json(file):
    return json.loads(file.read_text())


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True).stdout


def contiguous(values):
    return not values or values == list(range(values[0], values[-1] + 1))


def main():
    public = ROOT / 'public-review'
    video = public / VIDEO_NAME
    report_file = ROOT / 'evidence/proof/REPORT.json'
    report = read_json(report_file)
    assert report['status'] == 'PASS'
    assert digest(video)['sha256'] == report['video']['sha256']
    assert len(report['frames']) == 240
    probe_args = ['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)]
    probe = json.loads(run(probe_args))
    stream = probe['streams'][0]
    assert len(probe['streams']) == 1 and stream['codec_type'] == 'video'
    assert (stream['width'], stream['height'], stream['avg_frame_rate'], int(stream['nb_read_frames'])) == (1080, 1920, '30/1', 240)
    assert float(stream['duration']) == 8

    checks = []
    for checkpoint in report['checkpoints']:
        file = public / checkpoint['file']
        data = file.read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', data[16:24]) == (1080, 1920)
        assert hashlib.sha256(data).hexdigest() == checkpoint['sha256']
        assert checkpoint['sha256'] == report['frames'][checkpoint['frame']]['png_sha256']
        checks.append({'frame': checkpoint['frame'], 'state': checkpoint['state'], **digest(file), 'exactNativeInputCheckpoint': True})
    assert len(checks) == 6
    assert sorted(p.name for p in public.iterdir()) == sorted([VIDEO_NAME, 'SHA256SUMS', *[c['file'] for c in report['checkpoints']]])

    accepted = read_json(ROOT.parent / 'event-feature-bundle-v2/evidence/proof/REPORT.json')
    integration_file = ROOT.parent / 'event-feature-bundle-v2/evidence/integration/REPORT.json'
    integration = read_json(integration_file)
    disclosures = [item for item in integration['frames'][0]['diagnostic']['native']['gpu']['layout']
                   if item['role'] == 'SCENARIO_DISCLOSURE']
    assert len(disclosures) == 1 and disclosures[0]['kind'] == 'TEXT'
    disclosure = disclosures[0]
    x, y, width, height = disclosure['box']
    pad = disclosure.get('outlineRadius', disclosure.get('metrics', {}).get('outlineRadius', 0)) + 2
    removed_disclosure_box = [x - pad, y - pad, x + width + pad, y + height + pad]
    old_source = ROOT.parent / 'event-feature-bundle-v2/fixtures'
    for name in ['FLOW_PLAN.json', 'DETAIL_ADAPTER_PLAN.json']:
        assert (ROOT / 'fixtures' / name).read_bytes() == (old_source / name).read_bytes()
    active = []
    for row in report['frames']:
        number = row['frame']
        assert row['cameraBounds'] == accepted['frames'][number]['cameraBounds']
        assert row['glError'] == 0
        assert row['layoutValidation']['valid']
        assert not any(item['role'] == 'SCENARIO_DISCLOSURE' for item in row['layoutItems'])
        protection = row['flow']['protection']
        assert all(protection[key] == 0 for key in ['protectedChangedPixels', 'markerChangedPixels', 'outsideRoiChangedPixels'])
        if not row['flow']['enabled']:
            assert number < 60
            continue
        assert row['cameraLocked']
        expected_controls = copy.deepcopy(accepted['frames'][number]['flow']['controls'])
        prior_boxes = expected_controls['eventControls']['readiness']['protectedBoxes']
        filtered = [box for box in prior_boxes if box != removed_disclosure_box]
        assert len(prior_boxes) - len(filtered) == 1, 'Only the measured optional footer reservation may differ'
        expected_controls['eventControls']['readiness']['protectedBoxes'] = filtered
        assert row['flow']['controls'] == expected_controls
        assert row['protectedGraphics'] == [graphic for graphic in accepted['frames'][number]['protectedGraphics']
                                            if graphic['box'] != removed_disclosure_box]
        visual, core = row['flow']['visualControls'], row['flow']['controls']
        for field in ['objectFraction', 'objectPosition', 'objectHeading', 'headingLookAheadPixels', 'state', 'localFrame']:
            assert visual[field] == core[field]
        assert visual['routeFraction'] >= core['objectFraction'] - 1e-12
        assert row['flow']['visualProfile']['afterSize'] == [62.4, 36]
        active.append(row)
    assert len(active) == 180
    visual_routes = [row['flow']['visualControls']['routeFraction'] for row in active]
    assert all(a <= b + 1e-12 for a, b in zip(visual_routes, visual_routes[1:]))
    completion = next(row['frame'] for row in active if row['flow']['visualControls']['routeFraction'] == 1)
    old_completion = next(row['frame'] for row in accepted['frames'] if row['flow']['enabled'] and row['flow']['controls']['routeFraction'] == 1)
    moving = [row for row in active if row['flow']['controls']['objectVisible']]
    step = lambda a, b: math.dist(a['flow']['controls']['objectPosition'], b['flow']['controls']['objectPosition'])
    maximum_step = max(step(a, b) for a, b in zip(moving, moving[1:]))
    maximum_heading = max(abs(a['flow']['controls']['objectHeading'] - b['flow']['controls']['objectHeading']) for a, b in zip(moving, moving[1:]))
    arrival = [row for row in active if row['flow']['visualControls']['arrivalPulse']['active']]
    departure = [row for row in active if row['flow']['visualControls']['departurePulse']['active']]
    arrival_frames = [row['frame'] for row in arrival]
    departure_frames = [row['frame'] for row in departure]
    assert contiguous(arrival_frames) and contiguous(departure_frames)
    assert len(arrival_frames) == 18 and len(departure_frames) == 18
    peak = max(arrival, key=lambda row: row['flow']['visualControls']['arrivalPulse']['alpha'])
    hold = [row for row in active if row['flow']['controls']['hold']]
    assert len(hold) == 34 and len(set(row['raw_rgba_sha256'] for row in hold)) == 1
    occluded = [row['frame'] for row in active if row['flow']['graphics'].get('object') and row['flow']['graphics']['object']['occluded']]

    private = ROOT / 'evidence/visual'
    private.mkdir(exist_ok=True)
    select = "select='" + '+'.join(f'eq(n,{frame})' for frame in FRAMES) + "'"
    commands = []
    contacts = []
    for name, filters in [
        ('DECODED_FULL_CONTACT.png', 'scale=270:480,tile=4x4:padding=4:margin=4:color=black'),
        ('DECODED_ROUTE_CONTACT.png', 'crop=400:500:330:745,tile=4x4:padding=4:margin=4:color=black'),
    ]:
        output = private / name
        assert not output.exists(), 'Private extraction output already exists; inspect the existing evidence instead of overwriting it'
        arguments = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '2', '-i', str(video), '-vf', select + ',' + filters,
                     '-frames:v', '1', '-update', '1', str(output)]
        run(arguments)
        commands.append(arguments)
        contacts.append(digest(output))
    measurements = {'schema': 1, 'status': 'MEASURED_REQUIRES_ACTUAL_VISUAL_REVIEW',
        'scope': 'FOCUSED_EXISTING_MP4_DECODE_AND_FROZEN_FRAME_RECORD_INSPECTION',
        'noRenderingOrVideoReencoding': True, 'publicMediaUnchanged': True,
        'inputs': {'video': digest(video), 'proofReport': digest(report_file),
                   'visualProfile': digest(ROOT / 'fixtures/VISUAL_PROFILE.json'),
                   'acceptedDisclosureLayoutEvidence': digest(integration_file)},
        'video': {'width': 1080, 'height': 1920, 'fps': 30, 'durationSeconds': 8, 'frames': 240, 'audioStreams': 0},
        'decodeFramesInContactOrder': FRAMES, 'decodedContacts': contacts, 'extractionCommands': commands,
        'nativeCheckpoints': checks,
        'focusedMeasurements': {'cameraFrameRecordsEqualAccepted': 240, 'objectCoreFrameRecordsEqualAccepted': 180,
            'objectBeforeSize': [52, 30], 'objectAfterSize': [62.4, 36], 'sizeIncreasePercent': 20,
            'normalizedControlRecordsEqualAccepted': 180,
            'onlyAllowedReadinessContextDifference': {'removedRole': 'SCENARIO_DISCLOSURE', 'measuredBox': removed_disclosure_box},
            'visualRouteMonotonic': True, 'oldRouteCompletionFrame': old_completion, 'polishedRouteCompletionFrame': completion,
            'maximumObjectStepPixels': maximum_step, 'maximumHeadingStepDegrees': maximum_heading * 180 / math.pi,
            'singleArrivalPulseFrames': arrival_frames, 'arrivalPeakFrame': peak['frame'],
            'singleDeparturePulseFrames': departure_frames, 'holdFrames': len(hold), 'holdNativeRawPixelStable': True,
            'objectReservationOverlapFrames': occluded, 'objectReservationOverlapDurationSeconds': len(occluded) / 30,
            'publicTestDisclosureInstances': 0, 'protectedChangedPixels': 0, 'markerChangedPixels': 0, 'outsideRoiChangedPixels': 0},
        'reviewLimitation': 'These measurements do not claim visual approval. Inspect decoded contact sheets and all six exact native checkpoints before writing VISUAL_AUDIT.json.'}
    file = ROOT / 'evidence/VISUAL_MEASUREMENTS.json'
    with file.open('x') as handle:
        json.dump(measurements, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'status': measurements['status'], 'contacts': len(contacts), 'nativeCheckpoints': len(checks),
                      'videoSha256': measurements['inputs']['video']['sha256'], 'routeCompletionFrame': completion}))


if __name__ == '__main__':
    main()
