#!/usr/bin/env python3
"""Free, opt-in additive universal video image; no provider or NVIDIA execution."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-auto-video-v2'
WORKFLOW = '.github/workflows/universal-auto-video-v2.yml'
BRANCH = 'development/universal-auto-video-v2-20261016'
BASELINE = 'c1e9c099b22a8db1c5f21e7b029422e82f8efd33'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5'
BASE = IMAGE + '@' + PARENT_DIGEST
DEST = '/opt/rtx-package/repo/' + NAMESPACE
TAG_PATTERN = re.compile(r'universal-v2-c1e9c09-[1-9][0-9]*-[1-9][0-9]*', re.ASCII)
RUNTIME_FILES = ('contracts.py', 'planner.py', 'cache.py', 'compose.py', 'delivery.py',
    'orchestrator.py', 'render_adapter.py', 'prepare_video.py', 'universal_files.py',
    'long_runtime.mjs', 'long_capture.mjs', 'long_adapter.mjs', 'native_boundary_restore.mjs',
    'planner_geometry_serialization.mjs', 'long_area_timeline.mjs',
    'serve_long.py', 'HISTORY_CATALOG.json', 'SUPPLEMENTAL_SOURCES.json')
TEST_FILES = ('software_probe_long.mjs',)

# Reuse isolated helper objects for the proven scanner, registry guard and strict
# original160-file inventory. No helper or old manifest is rewritten on disk.
spec = importlib.util.spec_from_file_location('_universal_reference_ci', HERE.parent / 'reference-visual-master-v2/ci.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
controls = reference.controls
run, save, state_path, sha, safe_log = reference.run, reference.save, reference.state_path, reference.sha, reference.safe_log
for module in (reference, reference.parent, reference.parent.prior, controls):
    for name, value in {'HERE': HERE, 'REPO': REPO, 'NAMESPACE': NAMESPACE, 'WORKFLOW': WORKFLOW,
            'BRANCH': BRANCH, 'BASELINE': BASELINE, 'PARENT_DIGEST': PARENT_DIGEST, 'BASE': BASE, 'DEST': DEST,
            'PATCHES': {}}.items():
        setattr(module, name, value)
spec = importlib.util.spec_from_file_location('_universal_file_contract', HERE / 'universal_files.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_UNIVERSAL_AUTO_VIDEO_IMAGE_V2', 'status': 'IN_PROGRESS',
        'ciCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE, 'gpuExecuted': False,
        'gCubeDeployed': False, 'paidWorkExecuted': False, 'finalModified': False,
        'rendererModified': False, 'oldImagesDeleted': False, 'imageBuilt': False,
        'imagePushed': False, 'pullVerified': False, 'videoQualityApproved': False,
        'actual80SecondNvidiaVideoGenerated': False, 'externalDropboxDeliveryVerified': False}


for module in (reference, reference.parent, reference.parent.prior, controls):
    module.state = state
    module.save = save


def helpers():
    native = reference.parent.prior._parent_helpers()
    return SimpleNamespace(require_space=native.require_space, login=native.login, check_image=composed_image_check)


controls.helpers = helpers


def configure_registry():
    module = reference.configure_registry()
    module.TAG_PATTERN = TAG_PATTERN
    return module


def preflight():
    controls.preflight()
    value = state()
    value['tag'] = 'universal-v2-c1e9c09-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    value['image'] = IMAGE + ':' + value['tag']
    save(value)


def guard():
    configure_registry()
    controls.guard()


def source_commit():
    value = os.environ.get('GITHUB_SHA') or run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip()
    if not re.fullmatch('[0-9a-f]{40}', value):
        raise RuntimeError('UNIVERSAL_SOURCE_COMMIT_REQUIRED')
    return value


def runtime_files():
    fixtures = tuple(sorted(str(path.relative_to(HERE)) for path in (HERE / 'fixtures').glob('*.json')))
    if not fixtures:
        raise RuntimeError('UNIVERSAL_NATIVE_FIXTURES_REQUIRED')
    return (*RUNTIME_FILES, *fixtures)


def supplemental_files():
    document = json.loads((HERE / 'SUPPLEMENTAL_SOURCES.json').read_text())
    additional = document.get('files')
    if (document.get('schema') != 'WORLD_ENGINE_UNIVERSAL_SUPPLEMENTAL_FILES_V1'
            or document.get('sourceCommit') != BASELINE or not isinstance(additional, dict)):
        raise RuntimeError('UNIVERSAL_SUPPLEMENTAL_MANIFEST_REQUIRED')
    _, inherited = files.frozen_parent_files(REPO)
    source = json.loads((HERE.parent / 'rtx-gpu-package-v1/source_contract.json').read_text())
    original = {row['repoPath'] for row in source['files']}
    if (set(additional) & (original | set(inherited))
            or any(name.startswith(NAMESPACE + '/') for name in additional)):
        raise RuntimeError('SUPPLEMENTAL_PARENT_OVERWRITE_FORBIDDEN')
    for name, digest in additional.items():
        raw = files._bytes(REPO, name)
        if not files.HASH.fullmatch(str(digest)) or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('UNIVERSAL_SUPPLEMENTAL_SOURCE_CHANGED')
    return additional


def generate_manifest():
    parent, inherited = files.frozen_parent_files(REPO)
    declared = runtime_files()
    if len(set((*declared, *TEST_FILES))) != len(declared) + len(TEST_FILES):
        raise RuntimeError('DISJOINT_UNIVERSAL_FILE_GROUPS_REQUIRED')
    for name in (*declared, *TEST_FILES):
        files._bytes(HERE, name)
    return {'schema': files.SCHEMA, 'profileId': files.PROFILE_ID, 'family': files.PROFILE_ID,
        'sourceCommit': source_commit(), 'baselineCommit': BASELINE, 'parentImage': BASE,
        'parentReferenceManifestSha256': files.PARENT_MANIFEST_SHA,
        'files': {name: sha(HERE / name) for name in declared},
        'testFiles': {name: sha(HERE / name) for name in TEST_FILES}, 'repoDependencies': inherited,
        'additionalRepoFiles': supplemental_files(), 'inheritedFiles': parent.get('inheritedFiles', [])}


def extensions():
    manifest = generate_manifest()
    expected = {'repo/' + name: digest for name, digest in
        {**manifest['repoDependencies'], **manifest['additionalRepoFiles']}.items()}
    for group in ('files', 'testFiles'):
        expected.update({'repo/' + NAMESPACE + '/' + name: digest for name, digest in manifest[group].items()})
    expected['repo/' + NAMESPACE + '/UNIVERSAL_FILES.json'] = hashlib.sha256((json.dumps(manifest, indent=2) + '\n').encode()).hexdigest()
    return expected


reference.parent.extensions = extensions
composed_image_check = reference.parent.composed_image_check


def test_context():
    folder = Path(tempfile.mkdtemp(prefix='universal-source-context-', dir=os.environ['RUNNER_TEMP']))
    shutil.copytree(HERE, folder / 'universal', ignore=shutil.ignore_patterns('runs', 'public-review', '__pycache__'))
    (folder / 'universal/UNIVERSAL_FILES.json').write_text(json.dumps(generate_manifest(), indent=2) + '\n')
    for name in supplemental_files():
        target = folder / 'supplemental' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, target)
    return folder


def container(*, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=8g', '--cpus=2',
        '--pids-limit=512', '--restart=no', '--shm-size=2g', '--tmpfs', '/workspace:rw,mode=1777',
        '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / 'universal') + ',target=' + DEST + ',readonly']
        for name in supplemental_files():
            command += ['--mount', 'type=bind,source=' + str(context / 'supplemental' / name)
                + ',target=/opt/rtx-package/repo/' + name + ',readonly']
    return command


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/var/lib/world-engine-private/engine/universal-video-v2');"
        "p.mkdir(mode=0o700,exist_ok=True);os.chown(p,1000,1000);os.setgroups([]);os.setgid(1000);os.setuid(1000);" + body)


def validate_actual_boundary_report(report, fixture_path=None):
    """Independently bind pixel comparisons to a real production scene cut.

    Adjacent frame numbers alone are insufficient: 299/300 both belonged to
    scene-0003 in the first published fixture. Never trust the PASS boolean to
    establish that two different production ranges were actually exercised.
    """
    fixture_path = HERE / 'fixtures/PLAN_80S.json' if fixture_path is None else Path(fixture_path)
    raw = fixture_path.read_bytes()
    document = json.loads(raw)
    if report.get('planSha256') != hashlib.sha256(raw).hexdigest():
        raise RuntimeError('ACTUAL_BOUNDARY_SOURCE_PLAN_SHA_REQUIRED')
    pair = report.get('actualBoundaryPair')
    if not isinstance(pair, dict):
        raise RuntimeError('ACTUAL_SCENE_BOUNDARY_WITNESS_REQUIRED')
    cut, before, after = (pair.get(key) for key in ('cutFrame', 'beforeFrame', 'afterFrame'))
    if (any(isinstance(value, bool) or not isinstance(value, int) for value in (cut, before, after))
            or before != cut - 1 or after != cut):
        raise RuntimeError('ACTUAL_ADJACENT_BOUNDARY_FRAMES_REQUIRED')
    scenes = document['scenes']
    matches = [(left, right) for left, right in zip(scenes, scenes[1:])
        if left['endFrame'] == cut == right['startFrame']]
    if len(matches) != 1:
        raise RuntimeError('REAL_SOURCE_SCENE_CUT_REQUIRED')
    left, right = matches[0]
    left_range, right_range = [left['startFrame'], left['endFrame']], [right['startFrame'], right['endFrame']]
    if (left['sceneId'] == right['sceneId'] or pair.get('leftSceneId') != left['sceneId']
            or pair.get('rightSceneId') != right['sceneId']
            or pair.get('leftRange') != left_range or pair.get('rightRange') != right_range):
        raise RuntimeError('REAL_DISTINCT_SCENE_IDS_AND_RANGES_REQUIRED')
    timing = document['legacyScenePlan']['timing']
    after_reveal = timing['event_start_frame'] + timing['initial_reveal_frames']
    if (cut <= after_reveal or not any(cut > step['start_frame']
            and cut < step['start_frame'] + step['transition_frames'] - 1
            for step in document['legacyScenePlan']['time_steps'][1:])):
        raise RuntimeError('ACTUAL_ACTIVE_EVENT_SCENE_CUT_REQUIRED')
    expected_frames = [0, before, after, document['totalFrames'] // 2, document['totalFrames'] - 1]
    if len(set(expected_frames)) != 5 or report.get('frames') != expected_frames:
        raise RuntimeError('FIVE_SOURCE_BOUND_TEMPORAL_FRAMES_REQUIRED')
    rows = report.get('rows')
    if not isinstance(rows, list) or len(rows) != 5 or [row.get('frame') for row in rows] != expected_frames:
        raise RuntimeError('ACTUAL_SOURCE_BOUND_RENDER_ROWS_REQUIRED')
    digest = re.compile('[0-9a-f]{64}', re.ASCII)
    for row in rows:
        frame = row['frame']
        selected = [scene for scene in scenes if scene['startFrame'] <= frame < scene['endFrame']]
        if (len(selected) != 1 or row.get('sceneId') != selected[0]['sceneId']
                or row.get('globalFrame') != frame
                or row.get('sceneRange') != [selected[0]['startFrame'], selected[0]['endFrame']]
                or not isinstance(row.get('rawRgbaSha256'), str) or not digest.fullmatch(row['rawRgbaSha256'])
                or not isinstance(row.get('sceneRangeSha256'), str) or not digest.fullmatch(row['sceneRangeSha256'])):
            raise RuntimeError('ACTUAL_RENDERED_FRAME_SCENE_BINDING_REQUIRED')
    continuity = report.get('continuity')
    if (not isinstance(continuity, list) or len(continuity) != 2
            or [row.get('globalFrame') for row in continuity] != [before, after]):
        raise RuntimeError('ACTUAL_CUT_PIXEL_COMPARISON_ROWS_REQUIRED')
    for row, scene, bounds in zip(continuity, (left, right), (left_range, right_range)):
        captured = next(item for item in rows if item['frame'] == row['globalFrame'])
        if (row.get('sceneId') != scene['sceneId'] or row.get('productionSceneRange') != bounds
                or row.get('productionSceneRangeSha256') != captured['sceneRangeSha256']
                or row.get('bitExact') is not True
                or row.get('segmentedRawRgbaSha256') != captured['rawRgbaSha256']
                or row.get('fullTimelineRawRgbaSha256') != captured['rawRgbaSha256']):
            raise RuntimeError('ACTUAL_CUT_SOURCE_AND_PIXEL_EQUALITY_REQUIRED')
    return {'status': 'PASS', 'sourcePlanSha256': hashlib.sha256(raw).hexdigest(),
        'cutFrame': cut, 'beforeFrame': before, 'afterFrame': after,
        'leftSceneId': left['sceneId'], 'rightSceneId': right['sceneId'],
        'leftRange': left_range, 'rightRange': right_range,
        'differentActualProductionScenes': True, 'activeEventTransition': True,
        'actualCutPixelsBitExact': True, 'reportBooleanAloneAccepted': False}


def software_probe(image, *, context=None, phase):
    code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/software_probe_long.mjs']).returncode)"
    result = subprocess.run(container(context=context) + ['--entrypoint=/usr/bin/python3', image, '-B', '-c', uid_code(code)],
        text=True, capture_output=True, check=False, timeout=1200)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state()
    value[phase] = {'exitCode': result.returncode, 'report': report, 'stdout': safe_log(result.stdout),
        'stderr': safe_log(result.stderr), 'scope': 'ACTUAL_UNIVERSAL_SWIFTSHADER_RANGE_DRAW_NOT_NVIDIA', 'gpuExecuted': False}
    save(value)
    if (result.returncode or not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'WORLD_ENGINE_UNIVERSAL_ACTUAL_SOFTWARE_PROBE_V2'
            or report.get('testOnly') is not True or report.get('nvidiaHardwareVerified') is not False
            or report.get('full80SecondVideoRendered') is not False
            or any(report.get(key) is not True for key in ('actualDrawReadPixels', 'all5TemporalFrames',
                'actualHistoricalSceneSelected', 'boundaryContinuityBitExact', 'originalSourcesUnchanged',
                'productionCpuPreparationSelected', 'inputCacheReuseVerified'))
            or report.get('nativeBoundaryProtection', {}).get('status') != 'PASS'
            or report.get('nativeBoundaryProtection', {}).get('actualReadPixelsCompared') is not True):
        raise RuntimeError('ACTUAL_UNIVERSAL_SOFTWARE_RANGE_PROOF_REQUIRED')
    try:
        audit = validate_actual_boundary_report(report)
    except RuntimeError as error:
        value = state()
        value[phase]['actualBoundaryAudit'] = {'status': 'FAIL', 'reasonCode': str(error)}
        save(value)
        raise
    value = state()
    value[phase]['actualBoundaryAudit'] = audit
    save(value)
    return report


def test():
    helpers().require_space()
    recorder = reference.parent.prior._record_case
    recorder('universal-ci-safety', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'), '-p', 'test_ci.py', '-v'], scope='NEW_UNIVERSAL_CI_ONLY')
    run(['docker', 'pull', BASE], timeout=900)
    context = test_context()
    common = container(context=context)
    for path in sorted((HERE / 'tests').glob('test_*.py')):
        if path.name == 'test_ci.py':
            continue
        code = ("import unittest;s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + path.name + "');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_UNIVERSAL_CPU_ONLY')
    for path in sorted((HERE / 'tests').glob('test_*.mjs')):
        code = "import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','--test','--test-isolation=none','" + DEST + "/tests/" + path.name + "']).returncode)"
        recorder(path.name, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', uid_code(code)], scope='NEW_UNIVERSAL_JS_CPU_ONLY')
    software_probe(BASE, context=context, phase='softwareProbeBeforeBuild')
    value = state()
    value['focusedTests']['status'] = 'PASS'
    save(value)


def stage():
    value = state()
    if value.get('focusedTests', {}).get('status') != 'PASS' or value.get('softwareProbeBeforeBuild', {}).get('exitCode') != 0:
        raise RuntimeError('FOCUSED_AND_CONNECTED_SOFTWARE_PROOF_REQUIRED')
    context = Path(os.environ['RUNNER_TEMP']) / ('universal-image-' + value['tag'])
    context.mkdir(mode=0o700)
    payload = context / 'universal'
    payload.mkdir()
    manifest = generate_manifest()
    for name in (*runtime_files(), *TEST_FILES):
        destination = payload / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / name, destination)
    (payload / 'UNIVERSAL_FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (context / 'supplemental').mkdir()
    for name in manifest['additionalRepoFiles']:
        destination = context / 'supplemental' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, destination)
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    value.update(context=str(context), universalManifest=manifest,
        universalManifestSha256=sha(payload / 'UNIVERSAL_FILES.json'), dockerfileSha256=sha(context / 'Dockerfile'))
    save(value)


def inspect_image(image):
    facts = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    config = facts.get('Config', {})
    labels = config.get('Labels', {})
    expected = {'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.reference-v2.source-revision': 'e9feafc785fbd138cbac3ca4db090380968dc37e',
        'world-engine.universal-v2.source-revision': os.environ['GITHUB_SHA'],
        'world-engine.universal-v2.parent-digest': PARENT_DIGEST}
    if facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64' or any(labels.get(key) != value for key, value in expected.items()):
        raise RuntimeError('UNIVERSAL_IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('PARENT_ENTRYPOINT_CHANGED')
    if {row.partition('=')[0] for row in config.get('Env', [])} & {'GH_TOKEN', 'GITHUB_TOKEN', 'DOCKER_AUTH_CONFIG', 'GITHUB_AUTHORIZATION', 'GCUBE_ACCESS_TOKEN'}:
        raise RuntimeError('CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value = state()
    value['builderBeforeBuild'] = helpers().require_space()
    save(value)
    folder = Path(value['context'])
    expected = {*runtime_files(), *TEST_FILES, 'UNIVERSAL_FILES.json'}
    observed = {str(path.relative_to(folder / 'universal')) for path in (folder / 'universal').rglob('*') if path.is_file()}
    supplementary = {str(path.relative_to(folder / 'supplemental')) for path in (folder / 'supplemental').rglob('*') if path.is_file()}
    if (set(path.name for path in folder.iterdir()) != {'universal', 'supplemental', 'Dockerfile'}
            or observed != expected or supplementary != set(supplemental_files())):
        raise RuntimeError('EXPLICIT_UNIVERSAL_BUILD_CONTEXT_REQUIRED')
    subprocess.run(['docker', 'build', '--platform=linux/amd64', '--file', str(folder / 'Dockerfile'),
        '--label', 'world-engine.universal-v2.source-revision=' + os.environ['GITHUB_SHA'], '--tag', value['image'], str(folder)], check=True, timeout=600)
    facts = inspect_image(value['image'])
    value.update(imageBuilt=True, configDigest=facts['Id'], imageSizeBytes=facts['Size'])
    save(value)


def image_hashes(image):
    code = "import sys,json;sys.path.insert(0,'" + DEST + "');import universal_files;print(json.dumps(universal_files.verify_extension()))"
    report = json.loads(run(['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--entrypoint=/usr/bin/python3', image, '-B', '-c', code]))
    expected = hashlib.sha256((json.dumps(generate_manifest(), indent=2) + '\n').encode()).hexdigest()
    if report.get('status') != 'PASS' or report.get('manifestSha256') != expected:
        raise RuntimeError('UNIVERSAL_EXTENSION_HASH_MISMATCH')
    return report


def verify():
    value = state()
    value.update(originalSources=composed_image_check(value['image'], hashes_only=True), imageHashes=image_hashes(value['image']))
    save(value)
    software_probe(value['image'], phase='actualImageSoftwareProbe')
    reference.parent.prior.secret_scan(value['image'])
    value = state()
    value['verification'] = 'PASS'
    save(value)


def publish():
    configure_registry()
    controls.publish()


controls.inspect_image = inspect_image
controls.image_hashes = image_hashes


def pull():
    configure_registry()
    controls.pull()
    value = state()
    value['status'] = 'UNIVERSAL_V2_IMAGE_CPU_SOFTWARE_VERIFIED_HARDWARE_AND_ACCOUNT_PENDING'
    save(value)


def persist():
    value = state()
    value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if value['status'] == 'IN_PROGRESS' or any(row == 'failure' for row in value['stepOutcomes'].values()):
        value['status'] = 'UNIVERSAL_V2_IMAGE_BLOCKED'
    relative = NAMESPACE + '/runs/' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '/' + os.environ['RESULT_PHASE'] + '.json'
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 16 * 1024**2:
        raise RuntimeError('BOUNDED_UNIVERSAL_EVIDENCE_REQUIRED')
    run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], cwd=REPO, timeout=180)
    run(['git', 'switch', '--detach', 'FETCH_HEAD'], cwd=REPO)
    target = REPO / relative
    if target.exists():
        raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=REPO)
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=REPO)
    run(['git', 'add', '--', relative], cwd=REPO)
    if run(['git', 'diff', '--cached', '--name-only'], cwd=REPO).splitlines() != [relative]:
        raise RuntimeError('BOUNDED_UNIVERSAL_EVIDENCE_ONLY_REQUIRED')
    run(['git', 'commit', '-m', 'docs: persist universal video V2 ' + os.environ['RESULT_PHASE'] + ' evidence [skip ci]'], cwd=REPO)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], cwd=REPO, timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'])
    args = parser.parse_args()
    try:
        globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'UNIVERSAL_CI_FAILED'
        value = state()
        value.update(status='UNIVERSAL_V2_IMAGE_BLOCKED', failedPhase=args.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            value['failedCommandExitCode'] = error.returncode
        save(value)
        print(json.dumps({'status': value['status'], 'phase': args.phase, 'reasonCode': code}))
        raise SystemExit(1)
