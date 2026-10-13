#!/usr/bin/env python3
"""Data-only visual reference fixture; original countries and historical facts stay intact."""
from pathlib import Path
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parents[1]
OLD = ENGINE / 'recovery/planner-scene-json-v1'


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def coordinates(value):
    if isinstance(value, list) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from coordinates(child)


def build():
    tracking = load(ROOT / 'evidence/reference_tracking/TRACKING_REPORT.json')
    original = load(OLD / 'fixtures/RUNTIME_FIXTURE.json')
    peninsula = load(OLD / 'data/NATIVE_PENINSULA.json')
    facts = load(OLD / 'data/FACT_DATA.json')
    domain = [{'id': key, 'geometry': copy.deepcopy(peninsula['countries'][key])}
              for key in ['COUNTRY_KOR', 'COUNTRY_PRK']]
    boundary = next(g['geometry']['coordinates'] for g in facts['geometries'] if g['id'] == 'FRONT_ARMISTICE')
    points = sorted(boundary)
    source_lons = [p[0] for item in domain for p in coordinates(item['geometry']['coordinates'])]
    left, right = min(source_lons) - .1, max(source_lons) + .1
    # A uniformly sampled visual envelope avoids near-vertical steps caused by
    # tiny longitude gaps in the existing boundary; source GIS stays untouched.
    knots = [left + (right - left) * i / 47 for i in range(48)]

    def base_at(x):
        if x <= points[0][0]:
            return points[0][1]
        for a, b in zip(points, points[1:]):
            if x <= b[0] and b[0] > a[0]:
                return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
        return points[-1][1]

    base = [base_at(x) for x in knots]
    # Approximate visual control envelope over real supplied land, not a surveyed battle front.
    def advance(x, progress):
        west_to_east = min(1, max(0, (x - 125.8) / 3.3))
        return .055 + progress * (1.60 - .48 * west_to_east)

    intent = {'version': 'TERRITORY_CONTROL_INTENT_V1', 'semantic_mode': 'REFERENCE_VISUAL_STUDY',
              'source': {'source_type': 'USER_AUTHORIZED_COUNTERFACTUAL_REFERENCE_VISUAL',
                         'source_reference': 'REFERENCE_65379_SELECTED_SEGMENT; NATIVE_COUNTRY_GEOMETRY',
                         'verification_status': 'REFERENCE_CONTENT_VERIFIED_NOT_REAL_EVENT'},
              'domain': domain, 'factions': {'winner': {'id': 'PURPLE'}, 'loser': {'id': 'ORANGE'}},
              'longitudinal_knots': knots, 'base_boundary_latitudes': base,
              'boundary_keyframes': [{'frame': 0, 'latitudes': [y + advance(x, 0) for x, y in zip(knots, base)]},
                                     {'frame': 149, 'latitudes': [y + advance(x, 1) for x, y in zip(knots, base)]}],
              'advance_direction': 'POSITIVE_LATITUDE', 'start_frame': 0, 'total_frames': 150,
              'fps': 30, 'interpolation': 'LINEAR'}
    # Geographic registration is an explicit visual approximation. Relative pan/zoom follows
    # measured unchanged reference terrain. Rotation is preserved as a documented unsupported gap.
    initial = [123.90, 33.30, 130.70, 42.95]
    width, height = initial[2] - initial[0], initial[3] - initial[1]
    cx, cy = (initial[0] + initial[2]) / 2, (initial[1] + initial[3]) / 2
    camera = []
    for frame, measurement in zip([0, 38, 75, 112, 149], tracking['records'][:5]):
        motion = measurement['camera_screen_tracking']
        factor = motion['scale']
        dx, dy = motion['map_crop_center_displacement_pixels']
        x, y = cx - dx / 1080 * width / factor, cy + dy / 1920 * height / factor
        w, h = width / factor, height / factor
        camera.append({'frame': frame, 'bounds': [x - w / 2, y - h / 2, x + w / 2, y + h / 2]})
    style = {'profileName': 'MEASURED_ORANGE_PURPLE_REFERENCE_MATERIAL_V1',
             'losingColor': [145 / 255, 24 / 255, 12 / 255, .50],
             'existingWinningColor': [94 / 255, 43 / 255, 137 / 255, .80],
             'gainedWinningColor': [91 / 255, 0, 253 / 255, .88],
             'interfaceColor': [1, 1, 1, .85], 'interfaceWidthPixels': 1,
             'sharedDomainBoundary': 'CONTROL_MATERIAL_REPLACES_INTERNAL_SEPARATOR'}
    scene = {'version': 'REFERENCE_VISUAL_SCENE_V1',
             'metadata': {'output': {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False},
                          'referenceSHA256': tracking['input_sha256'],
                          'referenceSegmentSeconds': [5.181813, 10.181813],
                          'semanticMode': 'COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY',
                          'factualBasis': 'Existing real country GIS; authored approximate control envelope.',
                          'cameraRegistration': 'APPROXIMATE_ABSOLUTE_GEOGRAPHY_MEASURED_RELATIVE_SCREEN_PAN_ZOOM',
                          'rotationReproduced': False, 'historicalOriginalFixtureChanged': False,
                          'arrowsRoutesStandaloneFrontLines': False},
             'controlIntent': intent, 'cameraKeyframes': camera, 'style': style}
    regional = load(ENGINE / original['nativeFiles']['regionalPlan'])
    native_scene = load(ENGINE / original['nativeFiles']['scene'])
    regional['text']['eventTitle'] = '한반도'
    # New fixture color inputs through the unchanged public Region Material
    # contract. Original plans, material code and Boundary style are preserved.
    regional['theme'].update(primary=[.04, 0, .70],
                             secondary=[172 / 255, 32 / 255, 0],
                             primaryStrength=.93, secondaryStrength=.94,
                             primaryLuminance=.22, secondaryLuminance=.36,
                             visualColorProfile='REFERENCE_ORANGE_PURPLE_DATA_PROFILE_V1')
    native_scene['event_title'] = '한반도'
    native_files = copy.deepcopy(original['nativeFiles'])
    native_files.update(regionalPlan='recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json',
                        scene='recovery/reference-reproduction-v1/fixtures/scene-native.json')
    runtime = {'version': 'REFERENCE_REPRODUCTION_RUNTIME_V1', 'nativeFiles': native_files,
               'currentNativeFrame': original['presentation']['cameraStartFrame'] + original['presentation']['eventStartFrame'],
               'totalFrames': 150, 'fps': 30, 'videoFilename': 'WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4',
               'checkpoints': [{'frame': f, 'name': name} for f, name in
                               [(0, '01_START.png'), (38, '02_ADVANCE.png'), (75, '03_TRACKING.png'),
                                (112, '04_CONTINUOUS_CONTROL.png'), (149, '05_END.png')]]}
    for name, value in [('SCENE_PLAN.json', scene), ('REGIONAL-plan.json', regional),
                        ('scene-native.json', native_scene), ('RUNTIME_FIXTURE.json', runtime)]:
        write(ROOT / 'fixtures' / name, value)
    receipt = {'status': 'FIXTURE_READY_FOR_NATIVE_PROBE', 'sourceCountryGeometriesUnchanged': True,
               'historicalOriginalSourceChanged': False, 'actualRelativeCameraMeasurementUsed': True,
               'absoluteFramingAndControlEnvelope': 'VISUAL_APPROXIMATION_NOT_SURVEYED_EVENT',
               'protectedCameraPlanChanged': False, 'originalNativeThemeOrStyleChanged': False,
               'newFixtureRegionColorInputs': 'PURPLE_ORANGE_PUBLIC_THEME_CONTRACT',
               'boundaryStyleChanged': False,
               'newFixtureTitle': '한반도', 'requiredTempOnlyFiles': 0,
               'sceneSHA256': hashlib.sha256((ROOT / 'fixtures/SCENE_PLAN.json').read_bytes()).hexdigest()}
    write(ROOT / 'evidence/FIXTURE_BUILD.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    build()
