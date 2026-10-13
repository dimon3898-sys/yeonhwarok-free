#!/usr/bin/env python3
"""Author a new visual fixture from measured input; never modify the saved fixture."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parents[1]
PRIOR = ENGINE / 'recovery/reference-reproduction-v1'


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coords(item):
    if isinstance(item, list) and len(item) == 2 and all(isinstance(x, (int, float)) for x in item):
        yield item
    elif isinstance(item, list):
        for child in item:
            yield from coords(child)


def build():
    scene = copy.deepcopy(read(PRIOR / 'fixtures/SCENE_PLAN.json'))
    front_path = ROOT / 'evidence/front_reference/REPORT.json'
    front = read(front_path)
    registration_path = ROOT / 'evidence/camera_registration/ROTATION_DIAGNOSTIC.json'
    registration = read(registration_path)
    assert front['registered_start_bounds'] == registration['startBounds']
    assert front['registration_sha256'] == sha(registration_path)
    tracking_path = PRIOR / 'evidence/reference_tracking/TRACKING_REPORT.json'
    tracking = read(tracking_path)
    start = registration['startBounds']
    width, height = start[2] - start[0], start[3] - start[1]
    cx, cy = (start[0] + start[2]) / 2, (start[1] + start[3]) / 2
    keys = []
    for frame, record in zip([0, 38, 75, 112, 149], tracking['records'][:5]):
        pose = record['camera_screen_tracking']
        factor = pose['scale']
        dx, dy = pose['map_crop_center_displacement_pixels']
        x, y = cx - dx / 1080 * width / factor, cy + dy / 1920 * height / factor
        w, h = width / factor, height / factor
        keys.append({'frame': frame, 'bounds': [x-w/2, y-h/2, x+w/2, y+h/2],
                     'rotationDegrees': registration['initialRollDegrees'] + pose['screen_rotation_degrees']})
    intent = scene['controlIntent']
    domain_lons = [p[0] for part in intent['domain'] for p in coords(part['geometry']['coordinates'])]
    measured = []
    for sample in front['samples']:
        points = sorted(p['geographic_approximation'] for p in sample['points']
                        if p['color_adjacency_score'] >= .25)
        assert len(points) >= 2
        measured.append(points)
    left = min(p[0] for points in measured for p in points) - .08
    right = max(p[0] for points in measured for p in points) + .08
    knots = np.r_[min(domain_lons)-.02, np.linspace(left, right, 62), max(domain_lons)+.02]
    assert np.all(np.diff(knots) > 0)
    base = np.interp(knots, intent['longitudinal_knots'], intent['base_boundary_latitudes'])
    rows, corrections, spans = [], [], []
    previous = base.copy()
    for sample, points in zip(front['samples'], measured):
        observed = np.asarray(points)
        # Explicit local authoring across measured gaps: no claim of observing
        # a hidden frontier. End support is clamped outside the visible samples.
        raw = np.interp(knots, observed[:, 0], observed[:, 1])
        authored = np.maximum(raw, previous)
        correction = authored - raw
        corrections.append({'frame': sample['candidate_frame'],
                            'correctedKnots': int(np.count_nonzero(correction > 1e-9)),
                            'maximumLatitudeCorrectionDegrees': float(correction.max()),
                            'correctionScope': 'MEASURED_NOISE_AND_OCCLUDED_SUPPORT_MONOTONE_ENVELOPE'})
        spans.append({'frame': sample['candidate_frame'], 'observedLongitudeRange':
                      [float(observed[:, 0].min()), float(observed[:, 0].max())],
                      'sourcePointsUsed': len(points), 'actualHiddenBoundaryObserved': False})
        rows.append({'frame': sample['candidate_frame'], 'latitudes': authored.tolist()})
        previous = authored
    intent.update(longitudinal_knots=knots.tolist(), base_boundary_latitudes=base.tolist(),
                  boundary_keyframes=rows, interpolation='LINEAR')
    scene.update(version='REFERENCE_VISUAL_SCENE_V2', cameraKeyframes=keys)
    scene['metadata'].update(cameraRegistration='MEASURED_APPROXIMATE_COUNTRY_SILHOUETTE_WITH_ABSOLUTE_ROLL',
                             rotationReproduced=True,
                             factualBasis='Original country GIS; observed counterfactual reference frontier with disclosed occlusion authoring.',
                             sourcePhoneUIAndCaptionsExcluded=True,
                             optionalNativeShotGraphics=False,
                             qualityParityClaimed=False)
    scene['style'] = {'profileName': 'REFERENCE_OLIVE_BASE_ORANGE_PURPLE_V2',
                      'losingColor': [186/255, 30/255, 11/255, .70],
                      'existingWinningColor': [104/255, 23/255, 229/255, .65],
                      'gainedWinningColor': [91/255, 0, 251/255, .98],
                      'interfaceColor': [1, 1, 1, 0], 'interfaceWidthPixels': 0,
                      'sharedDomainBoundary': 'CONTROL_MATERIAL_REPLACES_INTERNAL_SEPARATOR'}
    scene['terrainProfile'] = {'profileName': 'NE1_REFERENCE_OLIVE_TEAL_VISUAL_V2',
                              'landTint': [64/255, 72/255, 25/255], 'seaTint': [31/255, 78/255, 87/255],
                              'landSourceAnchor': .85, 'seaSourceAnchor': .70,
                              'landContrast': 1.65, 'seaContrast': 1.15, 'sourceChromaRetention': .08}
    scene['presentationProfile'] = {'overscan': 1.36, 'nativeForeground': 'EXPLICIT_NEW_SHOT_OPTIONAL_GRAPHICS_FALSE'}
    combat_path = ROOT / 'fixtures/COMBAT_PROFILE.json'
    scene['combatProfile'] = read(combat_path) if combat_path.exists() else {'units': [], 'profiles': {}}
    save(ROOT / 'fixtures/SCENE_PLAN.json', scene)
    runtime = copy.deepcopy(read(PRIOR / 'fixtures/RUNTIME_FIXTURE.json'))
    modules = read(PRIOR / 'manifests/IMPORT_MANIFEST.json')['browser_runtime_modules']
    module_paths = [p.removeprefix('world-simulation-shorts-engine/') for p in modules]
    new_modules = ['reference_quality_gpu_adapter_v2.mjs', 'reference_presentation_adapter_v2.mjs',
                   'reference_terrain_material_v2.mjs', 'reference_combat_overlay_v2.mjs']
    module_paths += ['web/map_infographic_v1/' + p for p in new_modules]
    runtime.update(version='REFERENCE_QUALITY_REWORK_RUNTIME_V2',
                   videoFilename='WORLD_ENGINE_REFERENCE_65379_QUALITY_REWORK_5S.mp4',
                   runtimeModuleFiles=sorted(set(module_paths)),
                   runtimeAssetFiles=['web/flat_assets/natural_earth_1_east_asia.png',
                                      'web/fonts/NotoSansCJKkr-Bold.otf'],
                   inheritedAdmissionFiles={'scenePlan': 'recovery/reference-reproduction-v1/fixtures/SCENE_PLAN.json',
                                             'visualAdmission': 'recovery/reference-reproduction-v1/evidence/VISUAL_ADMISSION.json'})
    save(ROOT / 'fixtures/RUNTIME_FIXTURE.json', runtime)
    save(ROOT / 'evidence/FIXTURE_BUILD.json', {
        'status': 'SOURCE_READY_FOR_ACTUAL_NATIVE_PROBE', 'originalGeometryUnchanged': True,
        'oldSceneAndFinalFilesUnchanged': True, 'sourceFrontMeasurementSHA256': sha(front_path),
        'registrationSHA256': sha(registration_path), 'trackingSHA256': sha(tracking_path),
        'fieldKnots': len(knots), 'observedFrontKeyframes': len(rows),
        'actualObservedSupport': spans, 'monotonicAuthoringCorrections': corrections,
        'hiddenBoundaryAuthoring': 'LINEAR_BETWEEN_OBSERVED_POINTS; CONSTANT_AT_UNOBSERVED_OUTER_LONGITUDES',
        'initialSourceWesternOcclusion': 'PARTIAL_COLOR_SUPPORT; NOT_SURVEYED_OR_EXACTLY_OBSERVED',
        'qualityParityClaimed': False, 'requiredTempOnlyFiles': 0,
        'sceneSHA256': sha(ROOT / 'fixtures/SCENE_PLAN.json')})
    print(json.dumps({'status': 'FIXTURE_BUILT', 'knots': len(knots), 'keyframes': len(rows),
                      'maximumCorrectionDegrees': max(v['maximumLatitudeCorrectionDegrees'] for v in corrections),
                      'combatUnits': len(scene['combatProfile']['units'])}))


if __name__ == '__main__':
    build()
