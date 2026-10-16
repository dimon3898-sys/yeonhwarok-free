#!/usr/bin/env python3
"""Free, additive V4 archival-front checks, connected software draw, and GHCR build."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery'
WORKFLOW = '.github/workflows/verified-front-v4-recovery.yml'
BRANCH = 'development/korean-war-front-data-v4-recovery-20261016'
BASELINE = '4c4f39a35f4618021bdf1541764fb5dc6eb334b6'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb'
BASE = IMAGE + '@' + PARENT_DIGEST
DEST = '/opt/rtx-package/repo/' + NAMESPACE
TAG_PATTERN = re.compile(r'front-v4-4c4f39a-[1-9][0-9]*-[1-9][0-9]*', re.ASCII)

specification = importlib.util.spec_from_file_location('_front_isolated_v3_ci', HERE.parent / 'universal-production-v3/ci.py')
parent = importlib.util.module_from_spec(specification)
specification.loader.exec_module(parent)
controls = parent.controls
run, save, state_path, sha, safe_log = parent.run, parent.save, parent.state_path, parent.sha, parent.safe_log
specification = importlib.util.spec_from_file_location('_front_source_contract', HERE / 'source_manifest_recovery.py')
files = importlib.util.module_from_spec(specification)
specification.loader.exec_module(files)
CHAIN = (parent, *parent.CHAIN)
for module in CHAIN:
    for name, value in {'HERE': HERE, 'REPO': REPO, 'NAMESPACE': NAMESPACE, 'WORKFLOW': WORKFLOW,
            'BRANCH': BRANCH, 'BASELINE': BASELINE, 'PARENT_DIGEST': PARENT_DIGEST, 'BASE': BASE,
            'DEST': DEST, 'PATCHES': {}}.items():
        setattr(module, name, value)


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_VERIFIED_FRONT_RECOVERY_IMAGE_V4', 'status': 'IN_PROGRESS',
        'ciCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE,
        'gpuExecuted': False, 'gCubeDeployed': False, 'paidWorkExecuted': False,
        'finalModified': False, 'rendererModified': False, 'oldImagesDeleted': False,
        'imageBuilt': False, 'imagePushed': False, 'pullVerified': False,
        'videoQualityApproved': False, 'actual80SecondNvidiaVideoGenerated': False,
        'externalDropboxDeliveryVerified': False,
        'prior74CpuChecksReused': True, 'priorV3SoftwareAndImageEvidenceReused': True}


for module in CHAIN:
    module.state, module.save = state, save


def helpers():
    native = parent.parent.reference.parent.prior._parent_helpers()
    return SimpleNamespace(require_space=native.require_space, login=native.login, check_image=composed_image_check)


controls.helpers = helpers


def configure_registry():
    module = parent.configure_registry()
    module.TAG_PATTERN = TAG_PATTERN
    return module


def preflight():
    controls.preflight()
    value = state()
    value['tag'] = 'front-v4-4c4f39a-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    value['image'] = IMAGE + ':' + value['tag']
    save(value)


def guard():
    configure_registry()
    controls.guard()


def source_commit():
    value = os.environ.get('GITHUB_SHA') or run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip()
    if not files.COMMIT.fullmatch(value):
        raise RuntimeError('FRONT_SOURCE_COMMIT_REQUIRED')
    return value


def generate_manifest():
    _, inherited = files.parent_closure(REPO)
    declared = files.inventory(HERE)
    return {'schema': files.SCHEMA, 'profileId': files.PROFILE_ID, 'family': files.PROFILE_ID,
        'sourceCommit': source_commit(), 'baselineCommit': BASELINE, 'parentImage': BASE,
        'parentSourceCommit': files.PARENT_SOURCE_COMMIT, 'parentManifestSha256': files.PARENT_MANIFEST_SHA,
        'parentInventoryFiles': files.PARENT_INVENTORY_FILES,
        'files': {name: sha(HERE / name) for name in declared['files']},
        'testFiles': {name: sha(HERE / name) for name in declared['testFiles']},
        'repoDependencies': inherited}


def extensions():
    manifest = generate_manifest()
    expected = {'repo/' + name: digest for name, digest in manifest['repoDependencies'].items()}
    for group in ('files', 'testFiles'):
        expected.update({'repo/' + NAMESPACE + '/' + name: digest for name, digest in manifest[group].items()})
    expected['repo/' + NAMESPACE + '/' + files.MANIFEST_NAME] = hashlib.sha256((json.dumps(manifest, indent=2) + '\n').encode()).hexdigest()
    return expected


parent.parent.reference.parent.extensions = extensions
composed_image_check = parent.composed_image_check


def test_context():
    folder = Path(tempfile.mkdtemp(prefix='front-v4-test-', dir=os.environ['RUNNER_TEMP']))
    shutil.copytree(HERE, folder / 'front', ignore=shutil.ignore_patterns('runs', 'public-review', '__pycache__'))
    (folder / 'front' / files.MANIFEST_NAME).write_text(json.dumps(generate_manifest(), indent=2) + '\n')
    return folder


def container(*, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=8g', '--cpus=2',
        '--pids-limit=512', '--restart=no', '--shm-size=2g', '--tmpfs', '/workspace:rw,mode=1777', '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / 'front') + ',target=' + DEST + ',readonly']
    return command


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/var/lib/world-engine-private/engine/verified-front-v4');"
        "p.mkdir(mode=0o700,exist_ok=True);os.chown(p,1000,1000);os.setgroups([]);os.setgid(1000);os.setuid(1000);" + body)


def validate_software_report(report):
    """Require real source-active pixels and truthful hardware/length boundaries."""
    required = ('actualDrawReadPixels', 'actualShaderCompile', 'softwareWebGLDrawExecuted',
        'sourceActiveFrame', 'actualHistoricalSourceSelected', 'originalSourcesUnchanged',
        'actualAstraUpload', 'sourceOrderVerified', 'fullPlan2400Frames', 'twelveChapterPlanSelected')
    if (not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'WORLD_ENGINE_ARCHIVAL_FRONT_V4_SOFTWARE_PROBE_V1'
            or report.get('testOnly') is not True or report.get('nvidiaHardwareVerified') is not False
            or report.get('full80SecondVideoRendered') is not False
            or any(report.get(name) is not False for name in ('physicalNvidiaExecuted', 'gpuRenderingVerified', 'gpuVideoQualityApproved'))
            or any(report.get(name) is not True for name in required)):
        raise RuntimeError('FRONT_ACTUAL_CONNECTED_SOURCE_PIXELS_REQUIRED')
    rows = report.get('rows')
    if not isinstance(rows, list) or len(rows) < 3 or len(rows) > 12:
        raise RuntimeError('FRONT_TEMPORAL_SOURCE_BOUND_ROWS_REQUIRED')
    observed = set()
    active = 0
    for row in rows:
        frame = row.get('frame')
        if type(frame) is not int or not 0 <= frame < 2400 or frame in observed:
            raise RuntimeError('FRONT_UNIQUE_GLOBAL_FRAMES_REQUIRED')
        observed.add(frame)
        if not files.HASH.fullmatch(str(row.get('rawRgbaSha256'))) or not files.HASH.fullmatch(str(row.get('pngSha256'))):
            raise RuntimeError('FRONT_ACTUAL_PIXEL_HASHES_REQUIRED')
        if row.get('sourceActiveFrame') is True:
            active += 1
            if (not files.HASH.fullmatch(str(row.get('sourceGeoJsonSha256')))
                    or not isinstance(row.get('sourceMapDate'), str)
                    or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['sourceMapDate'])
                    or type(row.get('sourceCoordinateCount')) is not int or row['sourceCoordinateCount'] < 2):
                raise RuntimeError('FRONT_ACTUAL_SOURCE_GEOMETRY_BINDING_REQUIRED')
            bounds = row.get('geometryBounds', {})
            if (bounds.get('active') is not True or bounds.get('wholeEventGeometryInViewport') is not True
                    or bounds.get('wholeEventGeometryInSafeArea') is not True):
                raise RuntimeError('FRONT_ACTUAL_SOURCE_MUST_FIT_VIEWPORT_AND_SAFE_AREA')
    if active == 0:
        raise RuntimeError('FRONT_DATA_MUST_BE_SELECTED_BY_RENDERER')
    ab = report.get('abComparison', {})
    if (ab.get('status') != 'PASS' or ab.get('sameCamera') is not True or ab.get('sameFrame') is not True
            or type(ab.get('changedPixelCount')) is not int or not 0 < ab['changedPixelCount'] <= 1080 * 1920
            or ab.get('protectedGraphicChangedPixelCount') != 0 or ab.get('outsideSafeAreaChangedPixelCount') != 0):
        raise RuntimeError('FRONT_ACTUAL_AB_AND_PROTECTED_PIXELS_REQUIRED')
    old = report.get('preservedFallback', {})
    first = next((row for row in rows if row['frame'] == 0), None)
    if (first is None or old.get('status') != 'PASS' or old.get('frame') != 0
            or old.get('bitExact') is not True or old.get('originalV3CompositorUsed') is not True
            or old.get('rawRgbaSha256') != first['rawRgbaSha256']):
        raise RuntimeError('FRONT_ACTUAL_PARENT_FALLBACK_PIXEL_EQUALITY_REQUIRED')
    native = report.get('nativeBoundaryProtection', {})
    if native.get('status') != 'PASS' or native.get('actualReadPixelsCompared') is not True:
        raise RuntimeError('FRONT_ACTUAL_NATIVE_BOUNDARY_PROTECTION_REQUIRED')
    cut = report.get('actualBoundaryPair')
    if cut is not None:
        continuity = report.get('continuity')
        if type(cut) is not int or not isinstance(continuity, list) or [row.get('frame') for row in continuity] != [cut - 1, cut]:
            raise RuntimeError('FRONT_ACTUAL_WORK_SCENE_BOUNDARY_ROWS_REQUIRED')
        for row in continuity:
            captured = next((item for item in rows if item['frame'] == row['frame']), None)
            if (captured is None or row.get('bitExact') is not True
                    or row.get('segmentedRawRgbaSha256') != captured['rawRgbaSha256']
                    or row.get('fullTimelineRawRgbaSha256') != captured['rawRgbaSha256']):
                raise RuntimeError('FRONT_ACTUAL_SEGMENTED_PIXEL_EQUALITY_REQUIRED')
    return {'status': 'PASS', 'actualSourceActiveFrames': active, 'actualTemporalFrames': len(rows),
        'softwareOnlyNotNvidia': True, 'reportBooleanAloneAccepted': False}


def validate_source_bindings(report, root=None):
    """Recompute source/profile provenance, not just accept reported SHA strings."""
    root = HERE if root is None else Path(root)
    raw = files.read_source(root, 'FRONT_PROFILE.json')
    if report.get('frontProfileSha256') != hashlib.sha256(raw).hexdigest():
        raise RuntimeError('FRONT_ACTUAL_PROFILE_FILE_SHA_REQUIRED')
    profile = json.loads(raw)
    if profile.get('schema') != 'WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4' or profile.get('runtimeProfile') != files.PROFILE_ID:
        raise RuntimeError('FRONT_ACTUAL_PROFILE_REQUIRED')
    fronts = profile.get('fronts')
    if not isinstance(fronts, list) or len({row.get('frontId') for row in fronts}) != len(fronts):
        raise RuntimeError('FRONT_UNIQUE_SOURCE_RECORDS_REQUIRED')
    matched = []
    for row in report['rows']:
        if row.get('sourceActiveFrame') is not True:
            continue
        source = next((front for front in fronts if front.get('frontId') == row.get('frontId')), None)
        if (source is None or source.get('sourceFile') != row.get('sourceFile')
                or source.get('mapDate') != row.get('sourceMapDate')
                or source.get('geoJsonSha256') != row.get('sourceGeoJsonSha256')):
            raise RuntimeError('FRONT_RENDERED_SOURCE_PROFILE_MISMATCH')
        raw_geo = files.read_source(root, source['sourceFile'])
        if hashlib.sha256(raw_geo).hexdigest() != source['geoJsonSha256']:
            raise RuntimeError('FRONT_ORIGINAL_GEOJSON_FILE_SHA_MISMATCH')
        document = json.loads(raw_geo)
        candidates = ([feature.get('geometry') for feature in document.get('features', [])]
            if document.get('type') == 'FeatureCollection' else
            [document.get('geometry')] if document.get('type') == 'Feature' else [document])
        if source.get('geometry') not in candidates:
            raise RuntimeError('FRONT_PROFILE_MUST_SELECT_ORIGINAL_SOURCE_GEOMETRY')
        selected = [item for item in profile.get('schedule', [])
            if item.get('startFrame', 2400) <= row['frame'] < item.get('endFrame', -1)]
        if len(selected) != 1 or selected[0].get('frontId') != source['frontId']:
            raise RuntimeError('FRONT_RENDERED_SOURCE_SCHEDULE_MISMATCH')
        matched.append({'frame': row['frame'], 'frontId': source['frontId'], 'sourceFile': source['sourceFile'],
            'sourceMapDate': source['mapDate'], 'sourceGeoJsonSha256': source['geoJsonSha256']})
    if not matched:
        raise RuntimeError('FRONT_DATA_MUST_BE_SELECTED_BY_RENDERER')
    return {'status': 'PASS', 'frontProfileSha256': hashlib.sha256(raw).hexdigest(), 'rows': matched}


def collect_png_evidence(folder, report):
    """Validate bounded actual PNG bytes and their separately generated sums."""
    records = report.get('files')
    if not isinstance(records, list) or not 3 <= len(records) <= 14:
        raise RuntimeError('FRONT_ACTUAL_PNG_FILES_REQUIRED')
    expected = {}
    total = 0
    for row in records:
        name = row.get('file')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}\.png', name)
                or name in expected or not files.HASH.fullmatch(str(row.get('sha256')))):
            raise RuntimeError('FRONT_CANONICAL_PNG_RECORD_REQUIRED')
        raw = files.read_source(folder, name)
        total += len(raw)
        if (len(raw) > 12 * 1024**2 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR'
                or struct.unpack('>II', raw[16:24]) != (1080, 1920)
                or row.get('bytes') != len(raw) or row['sha256'] != hashlib.sha256(raw).hexdigest()):
            raise RuntimeError('FRONT_ACTUAL_PNG_SHA_OR_DIMENSION_MISMATCH')
        expected[name] = row['sha256']
    if total > 120 * 1024**2 or {path.name for path in folder.iterdir()} != {*expected, 'SHA256SUMS'}:
        raise RuntimeError('FRONT_EXACT_BOUNDED_PNG_SET_REQUIRED')
    raw_sums = files.read_source(folder, 'SHA256SUMS')
    if len(raw_sums) > 64 * 1024:
        raise RuntimeError('FRONT_BOUNDED_SHA_SUMS_REQUIRED')
    observed = {}
    for line in raw_sums.decode('ascii').splitlines():
        digest, separator, name = line.partition('  ')
        if not separator or not files.HASH.fullmatch(digest) or name not in expected or name in observed:
            raise RuntimeError('FRONT_PNG_SHA_SUMS_MISMATCH')
        observed[name] = digest
    if observed != expected:
        raise RuntimeError('FRONT_PNG_SHA_SUMS_MISMATCH')
    for row in report.get('rows', []):
        if expected.get('FRAME_' + str(row['frame']).zfill(6) + '.png') != row.get('pngSha256'):
            raise RuntimeError('FRONT_TEMPORAL_PNG_BYTES_NOT_BOUND_TO_PIXELS')
    ab = report.get('abComparison', {})
    if ab:
        for side in ('before', 'after'):
            record = ab.get(side, {})
            for key in ('rawRgbaSha256', 'pngSha256', 'cameraSha256', 'geometrySha256', 'dateSha256'):
                if not files.HASH.fullmatch(str(record.get(key))):
                    raise RuntimeError('FRONT_ACTUAL_AB_HASH_WITNESS_REQUIRED')
            if expected.get('AB_' + side.upper() + '.png') != record['pngSha256']:
                raise RuntimeError('FRONT_AB_PNG_BYTES_MISMATCH')
        if (any(ab['before'][key] != ab['after'][key] for key in ('cameraSha256', 'geometrySha256', 'dateSha256'))
                or ab['before']['rawRgbaSha256'] == ab['after']['rawRgbaSha256']):
            raise RuntimeError('FRONT_AB_SOURCE_OR_PIXEL_HASH_MISMATCH')
    return records


def software_probe(image, *, context=None, phase):
    evidence = Path(tempfile.mkdtemp(prefix='front-v4-software-evidence-', dir=os.environ['RUNNER_TEMP']))
    evidence.chmod(0o777)
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/software_probe_front.mjs']).returncode)"
    command = container(context=context) + ['--mount', 'type=bind,source=' + str(evidence) + ',target=/workspace/front-evidence',
        '--env', 'WORLD_ENGINE_FRONT_EVIDENCE_DIR=/workspace/front-evidence']
    result = subprocess.run(command + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=1200)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state()
    value[phase] = {'exitCode': result.returncode, 'report': report, 'stdout': safe_log(result.stdout),
        'stderr': safe_log(result.stderr), 'scope': 'ACTUAL_ARCHIVAL_FRONT_SWIFTSHADER_NOT_NVIDIA', 'gpuExecuted': False}
    save(value)
    if result.returncode:
        raise RuntimeError('FRONT_ACTUAL_SOFTWARE_PROBE_FAILED')
    audit = validate_software_report(report)
    expected_manifest = hashlib.sha256((json.dumps(generate_manifest(), indent=2) + '\n').encode()).hexdigest()
    if report.get('frontManifestSha256') != expected_manifest:
        raise RuntimeError('FRONT_ACTUAL_RUNTIME_MANIFEST_SHA_REQUIRED')
    bindings = validate_source_bindings(report)
    records = collect_png_evidence(evidence, report)
    value = state(); value[phase].update(softwareAudit=audit, sourceBindings=bindings, actualPngEvidence=records, evidenceFolder=str(evidence)); save(value)
    return report


def verify_reproduction(image, *, context):
    """Recompute calibration, reviewed source edges and generated front artifacts."""
    code = ("import subprocess;raise SystemExit(subprocess.run(['/usr/bin/python3','-B','" + DEST
        + "/build_front_profile.py','--root','" + DEST + "','--recipe','RECIPE.json','--output-root','"
        + DEST + "','--verify-numerical']).returncode)")
    result = subprocess.run(container(context=context) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=240)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state(); value['sourceReproduction'] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr),
        'scope': 'REAL_SOURCE_MAP_PIXELS_AND_REVIEWED_EDGES_CPU_RECOMPUTATION_NOT_SURVEY_CERTIFICATION'}; save(value)
    if (result.returncode or not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'WORLD_ENGINE_FRONT_NUMERICAL_REPRODUCTION_V1'
            or report.get('mode') != 'READ_ONLY_NUMERICAL_REPRODUCTION'
            or report.get('sourcePixelsAndEdgesExact') is not True or report.get('frozenGeneratedHashesVerified') is not True
            or report.get('gpuExecuted') is not False or report.get('historicalAccuracyCertified') is not False
            or type(report.get('files')) is not int or report['files'] < 1
            or not isinstance(report.get('coordinateToleranceDegrees'), (int, float))
            or not 0 <= report['coordinateToleranceDegrees'] <= 1e-10
            or not isinstance(report.get('registrationResidualToleranceMeters'), (int, float))
            or not 0 <= report['registrationResidualToleranceMeters'] <= 1e-3):
        raise RuntimeError('FRONT_ACTUAL_SOURCE_BUILD_REPRODUCTION_REQUIRED')
    return report


def test():
    helpers().require_space()
    recorder = parent.parent.reference.parent.prior._record_case
    recorder('front-v4-ci-safety', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'),
        '-p', 'test_ci_recovery.py', '-v'], scope='NEW_V4_CI_ONLY')
    run(['docker', 'pull', BASE], timeout=900)
    context = test_context(); common = container(context=context)
    verify_reproduction(BASE, context=context)
    for path in sorted((HERE / 'tests').glob('test_*.py')):
        if path.name == 'test_ci_recovery.py':
            continue
        code = ("import unittest;s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + path.name + "');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_V4_CPU_ONLY')
    for path in sorted((HERE / 'tests').glob('test_*.mjs')):
        code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/tests/" + path.name + "']).returncode)"
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_V4_JS_CPU_ONLY')
    software_probe(BASE, context=context, phase='softwareProbeBeforeBuild')
    value = state(); value['focusedTests']['status'] = 'PASS'; save(value)


def stage():
    value = state()
    if (value.get('focusedTests', {}).get('status') != 'PASS'
            or value.get('softwareProbeBeforeBuild', {}).get('exitCode') != 0
            or value.get('sourceReproduction', {}).get('report', {}).get('status') != 'PASS'):
        raise RuntimeError('FRONT_FOCUSED_AND_CONNECTED_SOFTWARE_PROOF_REQUIRED')
    validate_software_report(value['softwareProbeBeforeBuild'].get('report'))
    validate_source_bindings(value['softwareProbeBeforeBuild']['report'])
    context = Path(os.environ['RUNNER_TEMP']) / ('front-v4-image-' + value['tag'])
    context.mkdir(mode=0o700); payload = context / 'front'; payload.mkdir()
    manifest = generate_manifest()
    for name in (*manifest['files'], *manifest['testFiles']):
        destination = payload / name; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(HERE / name, destination)
    (payload / files.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    value.update(context=str(context), frontManifest=manifest,
        frontManifestSha256=sha(payload / files.MANIFEST_NAME), dockerfileSha256=sha(context / 'Dockerfile'))
    save(value)


def inspect_image(image):
    facts = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    config = facts.get('Config', {}); labels = config.get('Labels', {})
    expected = {'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.production-v3.source-revision': files.PARENT_SOURCE_COMMIT,
        'world-engine.front-v4.source-revision': os.environ['GITHUB_SHA'],
        'world-engine.front-v4.parent-digest': PARENT_DIGEST}
    if facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64' or any(labels.get(key) != value for key, value in expected.items()):
        raise RuntimeError('FRONT_IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('FRONT_PARENT_ENTRYPOINT_CHANGED')
    if {row.partition('=')[0] for row in config.get('Env', [])} & {'GH_TOKEN', 'GITHUB_TOKEN', 'DOCKER_AUTH_CONFIG', 'GITHUB_AUTHORIZATION', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN'}:
        raise RuntimeError('FRONT_CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value = state(); value['builderBeforeBuild'] = helpers().require_space(); save(value)
    if value.get('sourceReproduction', {}).get('report', {}).get('status') != 'PASS':
        raise RuntimeError('FRONT_ACTUAL_SOURCE_BUILD_REPRODUCTION_REQUIRED')
    validate_software_report(value.get('softwareProbeBeforeBuild', {}).get('report'))
    validate_source_bindings(value['softwareProbeBeforeBuild']['report'])
    folder = Path(value['context']); manifest = generate_manifest()
    expected = {*manifest['files'], *manifest['testFiles'], files.MANIFEST_NAME}
    observed = {str(path.relative_to(folder / 'front')) for path in (folder / 'front').rglob('*') if path.is_file()}
    if set(path.name for path in folder.iterdir()) != {'front', 'Dockerfile'} or observed != expected:
        raise RuntimeError('FRONT_EXPLICIT_NEW_NAMESPACE_CONTEXT_REQUIRED')
    subprocess.run(['docker', 'build', '--platform=linux/amd64', '--file', str(folder / 'Dockerfile'),
        '--label', 'world-engine.front-v4.source-revision=' + os.environ['GITHUB_SHA'], '--tag', value['image'], str(folder)], check=True, timeout=600)
    facts = inspect_image(value['image']); value.update(imageBuilt=True, configDigest=facts['Id'], imageSizeBytes=facts['Size']); save(value)


def image_hashes(image):
    code = "import sys,json;sys.path.insert(0,'" + DEST + "');import source_manifest_recovery;print(json.dumps(source_manifest_recovery.verify_sources()))"
    report = json.loads(run(['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--entrypoint=/usr/bin/python3', image, '-B', '-c', code]))
    expected = hashlib.sha256((json.dumps(generate_manifest(), indent=2) + '\n').encode()).hexdigest()
    if report.get('status') != 'PASS' or report.get('manifestSha256') != expected or report.get('parentInventoryFiles') != 272:
        raise RuntimeError('FRONT_EXTENSION_HASH_MISMATCH')
    return report


def verify():
    value = state(); value.update(originalSources=composed_image_check(value['image'], hashes_only=True), imageHashes=image_hashes(value['image'])); save(value)
    software_probe(value['image'], phase='actualImageSoftwareProbe')
    parent.parent.reference.parent.prior.secret_scan(value['image'])
    value = state(); value['verification'] = 'PASS'; save(value)


controls.inspect_image, controls.image_hashes = inspect_image, image_hashes


def publish():
    configure_registry(); controls.publish()


def pull():
    configure_registry(); controls.pull()
    value = state(); value['status'] = 'VERIFIED_FRONT_V4_CPU_SOFTWARE_IMAGE_READY_HARDWARE_PENDING'; save(value)


def persist():
    value = state(); value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if value['status'] == 'IN_PROGRESS' or any(row == 'failure' for row in value['stepOutcomes'].values()):
        value['status'] = 'VERIFIED_FRONT_V4_IMAGE_BLOCKED'
    relative = NAMESPACE + '/runs/' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '/' + os.environ['RESULT_PHASE'] + '.json'
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 16 * 1024**2:
        raise RuntimeError('FRONT_BOUNDED_EVIDENCE_REQUIRED')
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO, timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    artifacts = {}
    if os.environ['RESULT_PHASE'] == 'build':
        for key in ('softwareProbeBeforeBuild', 'actualImageSoftwareProbe'):
            probe = value.get(key, {})
            if probe.get('exitCode') == 0 and probe.get('evidenceFolder'):
                folder = Path(probe['evidenceFolder'])
                collect_png_evidence(folder, probe['report'])
                for source in folder.iterdir():
                    artifacts[str(Path(relative).parent / key / source.name)] = source.read_bytes()
    target = REPO / relative
    if target.exists():
        raise RuntimeError('FRONT_EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    for name, body in artifacts.items():
        destination = REPO / name
        if destination.exists():
            raise RuntimeError('FRONT_EVIDENCE_OVERWRITE_FORBIDDEN')
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(body)
    run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    expected = sorted([relative, *artifacts])
    run(['git', 'add', '--', *expected], cwd=REPO)
    if sorted(run(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines()) != expected:
        raise RuntimeError('FRONT_BOUNDED_EVIDENCE_ONLY_REQUIRED')
    run(['git', 'commit', '-m', 'docs: persist archival front V4 ' + os.environ['RESULT_PHASE'] + ' evidence [skip ci]'], cwd=REPO)
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
            code = 'FRONT_CI_FAILED'
        value = state(); value.update(status='VERIFIED_FRONT_V4_IMAGE_BLOCKED', failedPhase=arguments.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            value['failedCommandExitCode'] = error.returncode
        save(value); print(json.dumps({'status': value['status'], 'phase': arguments.phase, 'reasonCode': code})); raise SystemExit(1)
