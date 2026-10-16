#!/usr/bin/env python3
"""Opt-in free additive production V3 build; never starts a paid GPU workload."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-production-v3'
WORKFLOW = '.github/workflows/universal-production-v3.yml'
BRANCH = 'development/universal-production-v3-20261016'
BASELINE = 'e09be5d368eefa9548d63901dfe13a217a7ca02d'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014'
BASE = IMAGE + '@' + PARENT_DIGEST
DEST = '/opt/rtx-package/repo/' + NAMESPACE
TAG_PATTERN = re.compile(r'production-v3-e09be5d-[1-9][0-9]*-[1-9][0-9]*', re.ASCII)
# Explicit new-file inventory is frozen with the connected runtime checkpoint.
RUNTIME_FILES = ('source_manifest.py', 'PARENT_CLOSURE.json', 'BASELINE_LOCK.json',
    'scene_planner.py', 'operations.py', 'OPERATIONS_CAPABILITIES.json',
    'orchestrator.py', 'render_adapter.py', 'long_runtime.mjs', 'long_capture.mjs',
    'production_adapter.mjs', 'production_visual_profile.mjs', 'production_camera.mjs',
    'production_native_camera.mjs', 'production_area_pass.mjs',
    'history/CHRONOLOGY_12.json', 'history/AREA_OWNERSHIP.json',
    'history/EXISTING_GEOMETRY_MANIFEST.json', 'history/OFFICIAL_RETRIEVAL_ATTEMPTS.json', 'history/VALIDATION.json')
TEST_FILES = ('software_probe_production.mjs',)

specification = importlib.util.spec_from_file_location('_production_isolated_v2_ci', HERE.parent / 'universal-auto-video-v2/ci.py')
parent = importlib.util.module_from_spec(specification)
specification.loader.exec_module(parent)
controls = parent.controls
run, save, state_path, sha, safe_log = parent.run, parent.save, parent.state_path, parent.sha, parent.safe_log
specification = importlib.util.spec_from_file_location('_production_source_contract', HERE / 'source_manifest.py')
files = importlib.util.module_from_spec(specification)
specification.loader.exec_module(files)
CHAIN = (parent, parent.reference, parent.reference.parent, parent.reference.parent.prior, controls)
for module in CHAIN:
    for name, value in {'HERE': HERE, 'REPO': REPO, 'NAMESPACE': NAMESPACE, 'WORKFLOW': WORKFLOW,
            'BRANCH': BRANCH, 'BASELINE': BASELINE, 'PARENT_DIGEST': PARENT_DIGEST, 'BASE': BASE,
            'DEST': DEST, 'PATCHES': {}}.items():
        setattr(module, name, value)


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_UNIVERSAL_PRODUCTION_IMAGE_V3', 'status': 'IN_PROGRESS',
        'ciCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE,
        'gpuExecuted': False, 'gCubeDeployed': False, 'paidWorkExecuted': False,
        'finalModified': False, 'rendererModified': False, 'oldImagesDeleted': False,
        'imageBuilt': False, 'imagePushed': False, 'pullVerified': False,
        'videoQualityApproved': False, 'actual80SecondNvidiaVideoGenerated': False,
        'externalDropboxDeliveryVerified': False, 'existingV2TestsReused': 168}


for module in CHAIN:
    module.state, module.save = state, save


def helpers():
    native = parent.reference.parent.prior._parent_helpers()
    return SimpleNamespace(require_space=native.require_space, login=native.login, check_image=composed_image_check)


controls.helpers = helpers


def configure_registry():
    module = parent.configure_registry()
    module.TAG_PATTERN = TAG_PATTERN
    return module


def preflight():
    controls.preflight()
    value = state()
    value['tag'] = 'production-v3-e09be5d-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    value['image'] = IMAGE + ':' + value['tag']
    save(value)


def guard():
    configure_registry()
    controls.guard()


def source_commit():
    value = os.environ.get('GITHUB_SHA') or run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip()
    if not re.fullmatch('[a-f0-9]{40}', value):
        raise RuntimeError('PRODUCTION_SOURCE_COMMIT_REQUIRED')
    return value


def runtime_files():
    fixtures = tuple(sorted(str(path.relative_to(HERE)) for path in (HERE / 'fixtures').glob('*.json')))
    if not fixtures:
        raise RuntimeError('PRODUCTION_FIXTURE_REQUIRED')
    return (*RUNTIME_FILES, *fixtures)


def generate_manifest():
    _, inherited = files.parent_closure(REPO)
    declared = (*runtime_files(), *TEST_FILES)
    if len(set(declared)) != len(declared):
        raise RuntimeError('PRODUCTION_DISJOINT_FILE_GROUPS_REQUIRED')
    for name in declared:
        files.read_source(HERE, name)
    return {'schema': files.SCHEMA, 'profileId': files.PROFILE_ID, 'family': files.PROFILE_ID,
        'sourceCommit': source_commit(), 'baselineCommit': BASELINE, 'parentImage': BASE,
        'parentSourceCommit': files.PARENT_SOURCE_COMMIT, 'parentManifestSha256': files.PARENT_MANIFEST_SHA,
        'parentInventoryFiles': files.PARENT_INVENTORY_FILES,
        'files': {name: sha(HERE / name) for name in runtime_files()},
        'testFiles': {name: sha(HERE / name) for name in TEST_FILES}, 'repoDependencies': inherited}


def extensions():
    manifest = generate_manifest()
    expected = {'repo/' + name: digest for name, digest in manifest['repoDependencies'].items()}
    for group in ('files', 'testFiles'):
        expected.update({'repo/' + NAMESPACE + '/' + name: digest for name, digest in manifest[group].items()})
    expected['repo/' + NAMESPACE + '/' + files.MANIFEST_NAME] = hashlib.sha256((json.dumps(manifest, indent=2) + '\n').encode()).hexdigest()
    return expected


parent.reference.parent.extensions = extensions
composed_image_check = parent.reference.parent.composed_image_check


def test_context():
    folder = Path(tempfile.mkdtemp(prefix='production-v3-test-', dir=os.environ['RUNNER_TEMP']))
    shutil.copytree(HERE, folder / 'production', ignore=shutil.ignore_patterns('runs', 'public-review', '__pycache__'))
    (folder / 'production' / files.MANIFEST_NAME).write_text(json.dumps(generate_manifest(), indent=2) + '\n')
    return folder


def container(*, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=8g', '--cpus=2',
        '--pids-limit=512', '--restart=no', '--shm-size=2g', '--tmpfs', '/workspace:rw,mode=1777', '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / 'production') + ',target=' + DEST + ',readonly']
    return command


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/var/lib/world-engine-private/engine/universal-production-v3');"
        "p.mkdir(mode=0o700,exist_ok=True);os.chown(p,1000,1000);os.setgroups([]);os.setgid(1000);os.setuid(1000);" + body)


def parent_layout_probe(image, *, context=None):
    """Prove the real image uses shipped aliases, not checkout-only source paths."""
    code = ("import sys,json,pathlib;sys.path.insert(0," + repr(DEST) + ");import source_manifest as m;"
        "result={'schema':'WORLD_ENGINE_PRODUCTION_IMAGE_LAYOUT_PROOF_V1','testOnly':True,'gpuExecuted':False};\n"
        "try:\n result['checkoutOnly']={'status':'UNEXPECTED_PASS','report':m.verify_sources(require_staged=False)}\n"
        "except FileNotFoundError as error:\n"
        " missing=pathlib.Path(error.filename);relative=missing.relative_to(m.REPO).as_posix() if missing.is_relative_to(m.REPO) else None\n"
        " parent=json.loads((m.REPO/m.PARENT_NAMESPACE/'UNIVERSAL_FILES.json').read_text());known={row['repoPath'] for row in parent['inheritedFiles']}\n"
        " result['checkoutOnly']={'status':'EXPECTED_MISSING_CHECKOUT_ALIAS' if relative in known else 'FAIL',"
        "'errorType':'FileNotFoundError','missingRepoPath':relative if relative in known else None}\n"
        "except Exception as error:\n result['checkoutOnly']={'status':'FAIL','errorType':type(error).__name__}\n"
        "try:\n result['staged']={'status':'PASS','report':m.verify_sources(require_staged=True)}\n"
        "except Exception as error:\n result['staged']={'status':'FAIL','errorType':type(error).__name__}\n"
        "result['status']='PASS' if result['checkoutOnly'].get('status')=='EXPECTED_MISSING_CHECKOUT_ALIAS' and result['staged'].get('status')=='PASS' else 'FAIL'\n"
        "print(json.dumps(result));raise SystemExit(0 if result['status']=='PASS' else 2)\n")
    result = subprocess.run(container(context=context) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=180)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state(); value['parentLayoutVerification'] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr), 'scope': 'ACTUAL_PARENT_IMAGE_LAYOUT_CPU_NOT_GPU'}; save(value)
    if (result.returncode or not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('testOnly') is not True or report.get('gpuExecuted') is not False
            or report.get('checkoutOnly', {}).get('status') != 'EXPECTED_MISSING_CHECKOUT_ALIAS'
            or report.get('staged', {}).get('status') != 'PASS'
            or report.get('staged', {}).get('report', {}).get('status') != 'PASS'
            or report['staged']['report'].get('testOnly') is not False):
        raise RuntimeError('PRODUCTION_ACTUAL_IMAGE_STAGED_LAYOUT_REQUIRED')
    return report


def _one_at(records, frame, code):
    matches = [row for row in records if row['startFrame'] <= frame < row['endFrame']]
    if len(matches) != 1:
        raise RuntimeError(code)
    return matches[0]


def _geometry_frame(schedule, frame):
    if schedule.get('mode') == 'ARRIVAL_NO_EVENT':
        return None
    length = schedule['endFrame'] - schedule['startFrame']
    fraction = 1.0 if length == 1 else (frame - schedule['startFrame']) / (length - 1)
    return math.floor(schedule['sourceStartFrame'] + (schedule['sourceEndFrame'] - schedule['sourceStartFrame']) * fraction + .5)


def validate_actual_production_boundary(report, fixture_path=None):
    """Bind actual pixels to real V3 job ranges and its separate geometry clock."""
    fixture_path = HERE / 'fixtures/PLAN_80S.json' if fixture_path is None else Path(fixture_path)
    raw = fixture_path.read_bytes(); document = json.loads(raw)
    if report.get('planSha256') != hashlib.sha256(raw).hexdigest():
        raise RuntimeError('PRODUCTION_ACTUAL_SOURCE_PLAN_SHA_REQUIRED')
    metadata = document.get('productionV3', {})
    chapters = metadata.get('eventChapters', [])
    if len(chapters) != 12 or metadata.get('chapterCount') != 12:
        raise RuntimeError('PRODUCTION_ACTUAL_TWELVE_CHAPTER_PLAN_REQUIRED')
    pair = report.get('actualBoundaryPair')
    if not isinstance(pair, dict):
        raise RuntimeError('PRODUCTION_ACTUAL_BOUNDARY_WITNESS_REQUIRED')
    cut, before, after = (pair.get(name) for name in ('cutFrame', 'beforeFrame', 'afterFrame'))
    if (any(type(value) is not int for value in (cut, before, after)) or before != cut - 1 or after != cut):
        raise RuntimeError('PRODUCTION_ADJACENT_BOUNDARY_FRAMES_REQUIRED')
    scenes = document['scenes']
    adjacent = [(left, right) for left, right in zip(scenes, scenes[1:]) if left['endFrame'] == cut == right['startFrame']]
    if len(adjacent) != 1:
        raise RuntimeError('PRODUCTION_REAL_SOURCE_SCENE_CUT_REQUIRED')
    left, right = adjacent[0]
    left_range, right_range = [left['startFrame'], left['endFrame']], [right['startFrame'], right['endFrame']]
    if (left['sceneId'] == right['sceneId'] or pair.get('leftSceneId') != left['sceneId']
            or pair.get('rightSceneId') != right['sceneId'] or pair.get('leftRange') != left_range or pair.get('rightRange') != right_range):
        raise RuntimeError('PRODUCTION_DISTINCT_ACTUAL_SCENES_REQUIRED')
    schedule = metadata.get('geometrySchedule', [])
    before_schedule = _one_at(schedule, before, 'PRODUCTION_GEOMETRY_SCHEDULE_COVERAGE_REQUIRED')
    after_schedule = _one_at(schedule, after, 'PRODUCTION_GEOMETRY_SCHEDULE_COVERAGE_REQUIRED')
    if (before_schedule != after_schedule or before_schedule.get('mode') != 'TRANSITION_SUPPLIED_SNAPSHOTS'
            or not before_schedule['startFrame'] < before < after < before_schedule['endFrame'] - 1
            or _geometry_frame(before_schedule, before) == _geometry_frame(after_schedule, after)):
        raise RuntimeError('PRODUCTION_ACTUAL_ACTIVE_GEOMETRY_CLOCK_CUT_REQUIRED')
    ab = report.get('abComparison', {})
    ab_frame = ab.get('frame')
    expected_frames = [0, before, after, ab_frame, document['totalFrames'] - 1]
    if (type(ab_frame) is not int or not after < ab_frame < document['totalFrames'] - 1
            or len(set(expected_frames)) != 5 or report.get('frames') != expected_frames):
        raise RuntimeError('PRODUCTION_FIVE_SOURCE_BOUND_TEMPORAL_FRAMES_REQUIRED')
    rows = report.get('rows')
    if not isinstance(rows, list) or len(rows) != 5 or [row.get('frame') for row in rows] != expected_frames:
        raise RuntimeError('PRODUCTION_ACTUAL_SOURCE_BOUND_RENDER_ROWS_REQUIRED')
    digest = re.compile(r'[a-f0-9]{64}\Z')
    for row in rows:
        frame = row['frame']; scene = _one_at(scenes, frame, 'PRODUCTION_WORK_SCENE_COVERAGE_REQUIRED')
        chapter = _one_at(chapters, frame, 'PRODUCTION_CHAPTER_COVERAGE_REQUIRED')
        clock = _one_at(schedule, frame, 'PRODUCTION_GEOMETRY_SCHEDULE_COVERAGE_REQUIRED')
        if (row.get('globalFrame') != frame or row.get('sceneId') != scene['sceneId']
                or row.get('sceneRange') != [scene['startFrame'], scene['endFrame']]
                or row.get('chapterId') != chapter['chapterId'] or row.get('geometryScheduleId') != clock['scheduleId']
                or row.get('sourceGeometryFrame') != _geometry_frame(clock, frame)
                or not digest.fullmatch(str(row.get('sceneRangeSha256')))
                or not digest.fullmatch(str(row.get('rawRgbaSha256')))):
            raise RuntimeError('PRODUCTION_RENDERED_FRAME_CLOCK_AND_SCENE_BINDING_REQUIRED')
    continuity = report.get('continuity')
    if (not isinstance(continuity, list) or len(continuity) != 2
            or [row.get('globalFrame') for row in continuity] != [before, after]):
        raise RuntimeError('PRODUCTION_ACTUAL_CUT_COMPARISON_ROWS_REQUIRED')
    for row, scene, bounds in zip(continuity, (left, right), (left_range, right_range)):
        captured = next(item for item in rows if item['frame'] == row['globalFrame'])
        if (row.get('sceneId') != scene['sceneId'] or row.get('productionSceneRange') != bounds
                or row.get('productionSceneRangeSha256') != captured['sceneRangeSha256']
                or row.get('bitExact') is not True or row.get('segmentedRawRgbaSha256') != captured['rawRgbaSha256']
                or row.get('fullTimelineRawRgbaSha256') != captured['rawRgbaSha256']):
            raise RuntimeError('PRODUCTION_ACTUAL_CUT_SOURCE_AND_PIXEL_EQUALITY_REQUIRED')
    return {'status': 'PASS', 'sourcePlanSha256': hashlib.sha256(raw).hexdigest(),
        'cutFrame': cut, 'beforeFrame': before, 'afterFrame': after,
        'leftSceneId': left['sceneId'], 'rightSceneId': right['sceneId'], 'leftRange': left_range, 'rightRange': right_range,
        'geometryScheduleId': before_schedule['scheduleId'], 'sourceGeometryFrames': [_geometry_frame(before_schedule, before), _geometry_frame(after_schedule, after)],
        'differentActualProductionScenes': True, 'activeEventTransition': True,
        'actualCutPixelsBitExact': True, 'reportBooleanAloneAccepted': False}


def validate_ab_witness(report):
    ab = report.get('abComparison', {})
    rows = report.get('rows', [])
    matches = [row for row in rows if row.get('frame') == ab.get('frame')]
    if (len(matches) != 1 or ab.get('status') != 'PASS'
            or ab.get('comparisonScope') != 'SAME_FRAME_CAMERA_GEOMETRY_DATE'
            or any(ab.get(name) is not True for name in ('sameFrame', 'sameGeometryClock', 'sameCamera', 'sameChapterDate'))
            or type(ab.get('changedPixelCount')) is not int or not 0 < ab['changedPixelCount'] <= 1080 * 1920
            or ab.get('protectedGraphicChangedPixelCount') != 0 or ab.get('outsideSafeAreaChangedPixelCount') != 0):
        raise RuntimeError('PRODUCTION_ACTUAL_AB_COMPARISON_REQUIRED')
    captured = matches[0]
    if ab.get('sceneId') != captured['sceneId'] or ab.get('sceneRangeSha256') != captured['sceneRangeSha256']:
        raise RuntimeError('PRODUCTION_AB_SCENE_BINDING_REQUIRED')
    before, after = ab.get('before', {}), ab.get('after', {})
    for name in ('cameraSha256', 'geometrySha256', 'dateSha256', 'rawRgbaSha256', 'pngSha256'):
        if not files.HASH.fullmatch(str(before.get(name))) or not files.HASH.fullmatch(str(after.get(name))):
            raise RuntimeError('PRODUCTION_AB_ACTUAL_HASH_WITNESS_REQUIRED')
    if any(before[name] != after[name] for name in ('cameraSha256', 'geometrySha256', 'dateSha256')):
        raise RuntimeError('PRODUCTION_AB_CAMERA_GEOMETRY_DATE_CHANGED')
    if before['rawRgbaSha256'] == after['rawRgbaSha256'] or after['rawRgbaSha256'] != captured['rawRgbaSha256']:
        raise RuntimeError('PRODUCTION_AB_PIXELS_NOT_ACTUALLY_DIFFERENT')
    return {'status': 'PASS', 'frame': ab['frame'], 'cameraGeometryDateHashEquality': True,
        'changedPixelCount': ab['changedPixelCount'], 'reportBooleanAloneAccepted': False}


def collect_png_evidence(folder, report):
    expected = {'AB_BEFORE.png', 'AB_AFTER.png', *('FRAME_' + str(frame).zfill(6) + '.png' for frame in report['frames'])}
    observed = {path.name for path in folder.iterdir()}
    if observed != expected | {'SHA256SUMS'}:
        raise RuntimeError('PRODUCTION_EXACT_SOFTWARE_PNG_SET_REQUIRED')
    records = []; total = 0
    for name in sorted(expected):
        path = folder / name
        if path.is_symlink() or not path.is_file() or not 33 <= path.stat().st_size <= 12 * 1024**2:
            raise RuntimeError('PRODUCTION_BOUNDED_REGULAR_PNG_REQUIRED')
        raw = path.read_bytes(); total += len(raw)
        if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR' or struct.unpack('>II', raw[16:24]) != (1080, 1920):
            raise RuntimeError('PRODUCTION_SOFTWARE_PNG_OUTPUT_INVALID')
        records.append({'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'width': 1080, 'height': 1920, 'scope': 'CPU_SW_NOT_NVIDIA'})
    reported = report.get('files')
    if (total > 84 * 1024**2 or not isinstance(reported, list)
            or not all(isinstance(row, dict) and isinstance(row.get('file'), str) for row in reported)
            or sorted(reported, key=lambda row: row['file']) != records):
        raise RuntimeError('PRODUCTION_ACTUAL_PNG_REPORT_SHA_MISMATCH')
    sums = folder / 'SHA256SUMS'
    if sums.is_symlink() or not sums.is_file() or not 0 < sums.stat().st_size <= 64 * 1024:
        raise RuntimeError('PRODUCTION_SOFTWARE_SHA256SUMS_REQUIRED')
    try:
        lines = sums.read_text(encoding='ascii').splitlines()
    except UnicodeError:
        raise RuntimeError('PRODUCTION_SOFTWARE_SHA256SUMS_MISMATCH') from None
    expected_sums = {row['file']: row['sha256'] for row in records}; observed_sums = {}
    for line in lines:
        digest, separator, name = line.partition('  ')
        if not separator or not files.HASH.fullmatch(digest) or name not in expected_sums or name in observed_sums:
            raise RuntimeError('PRODUCTION_SOFTWARE_SHA256SUMS_MISMATCH')
        observed_sums[name] = digest
    if observed_sums != expected_sums:
        raise RuntimeError('PRODUCTION_SOFTWARE_SHA256SUMS_MISMATCH')
    mapped = {row['file']: row for row in records}
    ab = report['abComparison']
    if mapped['AB_BEFORE.png']['sha256'] != ab['before']['pngSha256'] or mapped['AB_AFTER.png']['sha256'] != ab['after']['pngSha256']:
        raise RuntimeError('PRODUCTION_AB_PNG_BYTES_MISMATCH')
    for row in report['rows']:
        if mapped['FRAME_' + str(row['frame']).zfill(6) + '.png']['sha256'] != row.get('pngSha256'):
            raise RuntimeError('PRODUCTION_TEMPORAL_PNG_BYTES_MISMATCH')
    return records


def validate_software_report(report):
    required = ('actualDrawReadPixels', 'actualShaderCompile', 'softwareWebGLDrawExecuted',
        'all5TemporalFrames', 'boundaryContinuityBitExact', 'rangeBoundaryContinuityVerified',
        'actualHistoricalSceneSelected', 'originalSourcesUnchanged', 'productionCpuPreparationSelected', 'inputCacheReuseVerified',
        'actualAstraUpload', 'sourceGradeSelected', 'sourceOrderVerified', 'ABComparisonVerified', 'twelveChapterPlanSelected',
        'projectedEventGeometryMeasured', 'wholeEventGeometryInViewport', 'wholeEventGeometryInSafeArea')
    if (not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'WORLD_ENGINE_PRODUCTION_V3_ACTUAL_SOFTWARE_PROBE_V1'
            or report.get('testOnly') is not True or report.get('nvidiaHardwareVerified') is not False
            or report.get('full80SecondVideoRendered') is not False
            or any(report.get(name) is not False for name in ('physicalNvidiaExecuted', 'gpuRenderingVerified',
                'sampleMp4Generated', 'gpuVideoQualityApproved'))
            or any(report.get(key) is not True for key in required)
            or report.get('nativeBoundaryProtection', {}).get('status') != 'PASS'
            or report.get('nativeBoundaryProtection', {}).get('actualReadPixelsCompared') is not True):
        raise RuntimeError('ACTUAL_PRODUCTION_V3_CONNECTED_SOFTWARE_PROOF_REQUIRED')
    boundary = validate_actual_production_boundary(report)
    validate_ab_witness(report)
    return boundary


def software_probe(image, *, context=None, phase):
    evidence = Path(tempfile.mkdtemp(prefix='production-v3-software-evidence-', dir=os.environ['RUNNER_TEMP']))
    evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/software_probe_production.mjs']).returncode)"
    command = container(context=context) + ['--mount', 'type=bind,source=' + str(evidence) + ',target=/workspace/production-evidence',
        '--env', 'WORLD_ENGINE_PRODUCTION_EVIDENCE_DIR=/workspace/production-evidence']
    result = subprocess.run(command + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=1200)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state()
    value[phase] = {'exitCode': result.returncode, 'report': report, 'stdout': safe_log(result.stdout),
        'stderr': safe_log(result.stderr), 'scope': 'ACTUAL_CONNECTED_PRODUCTION_V3_SWIFTSHADER_NOT_NVIDIA', 'gpuExecuted': False}
    save(value)
    if result.returncode:
        raise RuntimeError('ACTUAL_PRODUCTION_V3_CONNECTED_SOFTWARE_PROOF_REQUIRED')
    try:
        audit = validate_software_report(report)
    except RuntimeError as error:
        value = state(); value[phase]['actualBoundaryAudit'] = {'status': 'FAIL', 'reason': str(error)}; save(value)
        raise
    records = collect_png_evidence(evidence, report)
    value = state(); value[phase].update(actualBoundaryAudit=audit, actualABAudit=validate_ab_witness(report),
        actualPngEvidence=records, evidenceFolder=str(evidence)); save(value)
    return report


def test():
    helpers().require_space()
    recorder = parent.reference.parent.prior._record_case
    recorder('production-v3-ci-safety', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'),
        '-p', 'test_ci.py', '-v'], scope='NEW_PRODUCTION_V3_CI_ONLY')
    run(['docker', 'pull', BASE], timeout=900)
    context = test_context(); common = container(context=context)
    for path in sorted((HERE / 'tests').glob('test_*.py')):
        if path.name == 'test_ci.py':
            continue
        code = ("import unittest;s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + path.name + "');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_PRODUCTION_V3_CPU_ONLY')
    for path in sorted((HERE / 'tests').glob('test_*.mjs')):
        code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','--test','--test-isolation=none','" + DEST + "/tests/" + path.name + "']).returncode)"
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_PRODUCTION_V3_JS_CPU_ONLY')
    parent_layout_probe(BASE, context=context)
    software_probe(BASE, context=context, phase='softwareProbeBeforeBuild')
    value = state(); value['focusedTests']['status'] = 'PASS'; save(value)


def stage():
    value = state()
    if value.get('focusedTests', {}).get('status') != 'PASS' or value.get('softwareProbeBeforeBuild', {}).get('exitCode') != 0:
        raise RuntimeError('PRODUCTION_FOCUSED_AND_CONNECTED_SOFTWARE_PROOF_REQUIRED')
    context = Path(os.environ['RUNNER_TEMP']) / ('production-v3-image-' + value['tag'])
    context.mkdir(mode=0o700); payload = context / 'production'; payload.mkdir()
    manifest = generate_manifest()
    for name in (*runtime_files(), *TEST_FILES):
        destination = payload / name; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(HERE / name, destination)
    (payload / files.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    value.update(context=str(context), productionManifest=manifest,
        productionManifestSha256=sha(payload / files.MANIFEST_NAME), dockerfileSha256=sha(context / 'Dockerfile'))
    save(value)


def inspect_image(image):
    facts = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    config = facts.get('Config', {}); labels = config.get('Labels', {})
    expected = {'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.universal-v2.source-revision': files.PARENT_SOURCE_COMMIT,
        'world-engine.production-v3.source-revision': os.environ['GITHUB_SHA'],
        'world-engine.production-v3.parent-digest': PARENT_DIGEST}
    if facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64' or any(labels.get(key) != value for key, value in expected.items()):
        raise RuntimeError('PRODUCTION_IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('PRODUCTION_PARENT_ENTRYPOINT_CHANGED')
    if {row.partition('=')[0] for row in config.get('Env', [])} & {'GH_TOKEN', 'GITHUB_TOKEN', 'DOCKER_AUTH_CONFIG', 'GITHUB_AUTHORIZATION', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN'}:
        raise RuntimeError('PRODUCTION_CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value = state(); value['builderBeforeBuild'] = helpers().require_space(); save(value)
    folder = Path(value['context']); expected = {*runtime_files(), *TEST_FILES, files.MANIFEST_NAME}
    observed = {str(path.relative_to(folder / 'production')) for path in (folder / 'production').rglob('*') if path.is_file()}
    if set(path.name for path in folder.iterdir()) != {'production', 'Dockerfile'} or observed != expected:
        raise RuntimeError('PRODUCTION_EXPLICIT_NEW_NAMESPACE_CONTEXT_REQUIRED')
    subprocess.run(['docker', 'build', '--platform=linux/amd64', '--file', str(folder / 'Dockerfile'),
        '--label', 'world-engine.production-v3.source-revision=' + os.environ['GITHUB_SHA'], '--tag', value['image'], str(folder)], check=True, timeout=600)
    facts = inspect_image(value['image']); value.update(imageBuilt=True, configDigest=facts['Id'], imageSizeBytes=facts['Size']); save(value)


def image_hashes(image):
    code = "import sys,json;sys.path.insert(0,'" + DEST + "');import source_manifest;print(json.dumps(source_manifest.verify_sources()))"
    report = json.loads(run(['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--entrypoint=/usr/bin/python3', image, '-B', '-c', code]))
    expected = hashlib.sha256((json.dumps(generate_manifest(), indent=2) + '\n').encode()).hexdigest()
    if report.get('status') != 'PASS' or report.get('manifestSha256') != expected:
        raise RuntimeError('PRODUCTION_EXTENSION_HASH_MISMATCH')
    return report


def verify():
    value = state(); value.update(originalSources=composed_image_check(value['image'], hashes_only=True), imageHashes=image_hashes(value['image'])); save(value)
    software_probe(value['image'], phase='actualImageSoftwareProbe')
    parent.reference.parent.prior.secret_scan(value['image'])
    value = state(); value['verification'] = 'PASS'; save(value)


controls.inspect_image, controls.image_hashes = inspect_image, image_hashes


def publish():
    configure_registry(); controls.publish()


def pull():
    configure_registry(); controls.pull()
    value = state(); value['status'] = 'PRODUCTION_V3_CPU_SOFTWARE_VERIFIED_HARDWARE_AND_ACCOUNT_PENDING'; save(value)


def persist():
    value = state(); value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if value['status'] == 'IN_PROGRESS' or any(row == 'failure' for row in value['stepOutcomes'].values()):
        value['status'] = 'PRODUCTION_V3_IMAGE_BLOCKED'
    relative = NAMESPACE + '/runs/' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '/' + os.environ['RESULT_PHASE'] + '.json'
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 16 * 1024**2:
        raise RuntimeError('PRODUCTION_BOUNDED_EVIDENCE_REQUIRED')
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO, timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    target = REPO / relative
    if target.exists():
        raise RuntimeError('PRODUCTION_EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    run(['git', 'add', '--', relative], cwd=REPO)
    if run(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines() != [relative]:
        raise RuntimeError('PRODUCTION_BOUNDED_EVIDENCE_ONLY_REQUIRED')
    run(['git', 'commit', '-m', 'docs: persist production V3 ' + os.environ['RESULT_PHASE'] + ' evidence [skip ci]'], cwd=REPO)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=REPO, timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'])
    arguments = parser.parse_args()
    try:
        globals()[arguments.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'PRODUCTION_CI_FAILED'
        value = state(); value.update(status='PRODUCTION_V3_IMAGE_BLOCKED', failedPhase=arguments.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            value['failedCommandExitCode'] = error.returncode
        save(value); print(json.dumps({'status': value['status'], 'phase': arguments.phase, 'reasonCode': code})); raise SystemExit(1)
