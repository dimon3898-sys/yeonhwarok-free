#!/usr/bin/env python3
"""Free additive CPU image packaging; never deploys, renders, or resets jobs."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'studio-https-bootstrap-v1/ci_package.py'
if hashlib.sha256(FROZEN.read_bytes()).hexdigest() != '93f588a9f1df0763814d42c8842495fd7733dcd3bbb97304c16a264d4cc6b393':
    raise RuntimeError('OVERNIGHT_FROZEN_CI_CHANGED')
spec = importlib.util.spec_from_file_location('_overnight_frozen_ci', FROZEN)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
ci.HERE = HERE
ci.NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-overnight-v3'
ci.WORKFLOW = '.github/workflows/world-engine-overnight-v3.yml'
ci.BRANCH = 'development/universal-overnight-safe-20261019'
ci.BASE_DIGEST = 'sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886'
ci.BASE = ci.IMAGE + '@' + ci.BASE_DIGEST
ci.DEST = '/opt/rtx-package/repo/' + ci.NAMESPACE
ci.TAG = re.compile(r'overnight-v3-[a-f0-9]{7,12}-[1-9][0-9]*-[1-9][0-9]*\Z')
PARENT_MANIFEST_SHA = '99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9'
MANIFEST_NAME = 'OVERNIGHT_FILES.json'


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'world-engine-overnight-v3-package'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


ci.location = location
_original_state = ci.state


def state():
    value = _original_state()
    value['schema'] = 'WORLD_ENGINE_OVERNIGHT_IMAGE_CPU_V1'
    value['status'] = value['status'].replace('STUDIO_HTTPS_CANDIDATE', 'OVERNIGHT_CANDIDATE')
    value.update(gpuExecuted=False, nvidiaHardwareVerified=False, paidWorkExecuted=False, gCubeDeployed=False)
    return value


ci.state = state


def _manifest(root):
    path = Path(root) / MANIFEST_NAME
    if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
            or not 0 < path.stat().st_size <= 4 * 1024**2):
        raise RuntimeError('OVERNIGHT_BOUNDED_MANIFEST_REQUIRED')
    value = json.loads(path.read_bytes())
    if (value.get('schema') != 'WORLD_ENGINE_OVERNIGHT_FILES_V1'
            or value.get('baseOperatingImageDigest') != ci.BASE_DIGEST
            or value.get('previousManifestSHA256') != PARENT_MANIFEST_SHA
            or not isinstance(value.get('files'), dict) or not value['files']):
        raise RuntimeError('OVERNIGHT_EXPLICIT_PARENT_BOUND_FILES_REQUIRED')
    for name, digest in value['files'].items():
        if (not isinstance(name, str) or Path(name).name != name or '\\' in name or name in {'.', '..'}
                or not ci.HASH.fullmatch(str(digest))):
            raise RuntimeError('OVERNIGHT_PACKAGE_PATH_INVALID')
    return value


def payload_context(*, root=HERE):
    manifest = _manifest(root)
    required = {'bootstrap.py', 'studio_entry.py', 'studio_controller.py', 'runtime_bridge.py', 'package_manifest.py',
                'prepare_source_preview.py', 'capture_runtime.mjs'}
    if not required <= set(manifest['files']):
        raise RuntimeError('OVERNIGHT_CONNECTED_STUDIO_RUNTIME_REQUIRED')
    context = Path(tempfile.mkdtemp(prefix='payload-', dir=location()))
    payload = context / 'overnight'
    payload.mkdir(mode=0o755)
    for name in sorted({*manifest['files'], MANIFEST_NAME}):
        path = Path(root) / name
        if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
                or not 0 < path.stat().st_size <= 16 * 1024**2):
            raise RuntimeError('OVERNIGHT_REGULAR_SOURCE_REQUIRED')
        if name in manifest['files'] and ci.sha(path) != manifest['files'][name]:
            raise RuntimeError('OVERNIGHT_SOURCE_SHA_MISMATCH')
        shutil.copyfile(path, payload / name)
    dockerfile = Path(root) / 'Dockerfile'
    if dockerfile.is_symlink() or not dockerfile.is_file():
        raise RuntimeError('OVERNIGHT_REGULAR_DOCKERFILE_REQUIRED')
    shutil.copyfile(dockerfile, context / 'Dockerfile')
    return context


def preflight():
    value = ci.state()
    value['builder'] = ci.require_free_runner()
    commit = os.environ.get('GITHUB_SHA', '')
    if not ci.COMMIT.fullmatch(commit):
        raise RuntimeError('OVERNIGHT_SOURCE_COMMIT_REQUIRED')
    tag = 'overnight-v3-' + commit[:10] + '-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not ci.TAG.fullmatch(tag):
        raise RuntimeError('OVERNIGHT_UNIQUE_TAG_REQUIRED')
    value.update(tag=tag, image=ci.IMAGE + ':' + tag)
    ci.save(value)


def container(image, *, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--user=0:0', '--memory=6g', '--cpus=2',
               '--pids-limit=256', '--restart=no', '--shm-size=2g', '--tmpfs', '/tmp:rw,mode=1777']
    if context:
        command += ['--mount', 'type=bind,source=' + str(context / 'overnight') + ',target=' + ci.DEST + ',readonly']
    return command + ['--entrypoint=/usr/bin/python3', image, '-B']


def source_code():
    return ("import importlib.util,json,sys,os;os.setgroups([]);os.setgid(1000);os.setuid(1000);"
            "sys.path.insert(0,'/opt/world-engine-studio-https-proxy-fix');"
            "from manifest import verify_sources as frozen_verify;frozen=frozen_verify();"
            "s=importlib.util.spec_from_file_location('_overnight_ci_sources','" + ci.DEST + "/package_manifest.py');"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);new=m.verify_sources();"
            "print(json.dumps({'status':'PASS','overnight':new,'frozen':frozen,'gpuExecuted':False}))")


def image_hashes(image, context=None):
    result = ci.run(container(image, context=context) + ['-c', source_code()], timeout=180, check=False)
    if result.returncode:
        value = ci.state()
        value['sourceContainerFailure'] = {'exitCode': result.returncode, 'stdout': ci.bounded(result.stdout),
                                           'stderr': ci.bounded(result.stderr), 'gpuExecuted': False}
        ci.save(value)
        raise RuntimeError('OVERNIGHT_CONTAINER_SOURCE_VERIFICATION_FAILED')
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('OVERNIGHT_CONTAINER_SOURCE_REPORT_REQUIRED') from None
    expected = ci.sha((context / 'overnight' if context else HERE) / MANIFEST_NAME)
    if (report.get('status') != 'PASS' or report.get('gpuExecuted') is not False
            or report.get('overnight', {}).get('manifestSHA256') != expected
            or report['overnight'].get('previousManifestSHA256') != PARENT_MANIFEST_SHA
            or report.get('frozen', {}).get('status') != 'PASS'):
        raise RuntimeError('OVERNIGHT_CONTAINER_SOURCE_HASH_MISMATCH')
    return report


ci.image_hashes = image_hashes


def source_plan_probe_code():
    """Real source/Scene loader only: no browser, GL opener, or GPU admission."""
    node = ("import assert from 'node:assert/strict';"
            "import {loadLongRuntimePlan} from '" + ci.DEST + "/capture_runtime.mjs';"
            "const supplied=JSON.parse(process.argv[1]),options=supplied.options??supplied;"
            "const plan=await loadLongRuntimePlan(options),range=plan.overnightRequest?.preview?.range;"
            "assert.equal(plan.document.totalFrames,2400,'OVERNIGHT_SOURCE_2400_FRAMES_REQUIRED');"
            "assert.equal(range?.endFrame-range?.startFrame,150,'OVERNIGHT_SOURCE_150_FRAME_RANGE_REQUIRED');"
            "assert.equal(range?.totalFrames,plan.document.totalFrames,'OVERNIGHT_GLOBAL_CLOCK_REQUIRED');"
            "assert.ok(Array.isArray(plan.sourceBindings)&&plan.sourceBindings.length>0,'OVERNIGHT_ACTUAL_SOURCE_BINDINGS_REQUIRED');"
            "assert.ok(Array.isArray(plan.serverConfig?.bindings)&&plan.serverConfig.bindings.length>0,'OVERNIGHT_ACTUAL_SERVER_BINDINGS_REQUIRED');"
            "await plan.assertSourceUnchanged();"
            "console.log(JSON.stringify({status:'PASS',scope:'ACTUAL_SOURCE_PLAN_LOAD_NO_GL',"
            "range,originalTotalFrames:plan.document.totalFrames,sceneId:plan.scene.sceneId,"
            "sourceBindings:plan.sourceBindings.length,serverBindings:plan.serverConfig.bindings.length,"
            "gpuExecuted:false,browserOpened:false,renderStarted:false}));")
    return ("import importlib.util,os,json,subprocess,tempfile,hashlib,pathlib,sys;os.setgroups([]);os.setgid(1000);os.setuid(1000);"
            "s=importlib.util.spec_from_file_location('_overnight_ci_source_prepare','" + ci.DEST + "/prepare_source_preview.py');"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "prepared=m.prepare('/tmp/overnight-source-plan-probe',image_digest='" + ci.BASE_DIGEST + "');"
            "options=prepared.get('options',prepared);"
            "\nif not options.get('activationFile'):"
            "\n private=tempfile.mkdtemp(prefix='overnight-ci-activation-');"
            "\n activation=subprocess.run(['/usr/bin/python3','-B','" + ci.DEST +
            "/../reference-visual-master-v2/prepare_ref2.py','--prepare-activation','--private-root',private,'--variant','F'],"
            "text=True,capture_output=True,timeout=180);"
            "\n if activation.returncode:"
            "\n  print(activation.stdout,end='');print(activation.stderr,end='',file=sys.stderr);raise RuntimeError('OVERNIGHT_CPU_ACTIVATION_PREP_FAILED')"
            "\n data=json.loads(activation.stdout.strip().splitlines()[-1]);"
            "\n options.update(activationFile=data['activationFile'],expectedActivationSha256=data['activationSha256']);"
            "\n path=pathlib.Path(options['activationFile']);"
            "\n if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=options['expectedActivationSha256']:"
            "\n  raise RuntimeError('OVERNIGHT_ACTUAL_CPU_ACTIVATION_SHA_REQUIRED')"
            "\nresult=subprocess.run(['/usr/local/bin/node','--input-type=module','-e'," + repr(node) +
            ",json.dumps(options)],text=True,capture_output=True,timeout=240);"
            "print(result.stdout,end='');print(result.stderr,end='',file=__import__('sys').stderr);"
            "raise SystemExit(result.returncode)")


def source_plan_probe(image, *, context=None):
    result = ci.record('actual-source-plan-load-no-gl',
                       container(image, context=context) + ['-c', source_plan_probe_code()], timeout=480)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('OVERNIGHT_ACTUAL_SOURCE_PLAN_REPORT_REQUIRED') from None
    if (report.get('status') != 'PASS' or report.get('scope') != 'ACTUAL_SOURCE_PLAN_LOAD_NO_GL'
            or report.get('gpuExecuted') is not False or report.get('browserOpened') is not False
            or report.get('renderStarted') is not False or report.get('originalTotalFrames') != 2400
            or report.get('range', {}).get('endFrame', 0) - report.get('range', {}).get('startFrame', 0) != 150):
        raise RuntimeError('OVERNIGHT_ACTUAL_SOURCE_PLAN_LOAD_REQUIRED')
    return report


def inspect_image(image):
    row = json.loads(ci.run(['docker', 'image', 'inspect', image]).stdout)[0]
    config = row.get('Config', {})
    labels = config.get('Labels', {})
    expected = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', ci.DEST + '/bootstrap.py']
    if (row.get('Os') != 'linux' or row.get('Architecture') != 'amd64' or config.get('Entrypoint') != expected
            or labels.get('world-engine.overnight.parent-digest') != ci.BASE_DIGEST
            or labels.get('world-engine.overnight.source-revision') != os.environ['GITHUB_SHA']):
        raise RuntimeError('OVERNIGHT_IMAGE_PROVENANCE_REQUIRED')
    if set(item.partition('=')[0] for item in config.get('Env', [])) & {
            'GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN',
            'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON',
            'DROPBOX_REFRESH_TOKEN', 'WORLD_ENGINE_BACKUP_KEY'}:
        raise RuntimeError('OVERNIGHT_IMAGE_SECRET_ENV_FORBIDDEN')
    if '8080/healthz' not in ' '.join(config.get('Healthcheck', {}).get('Test', [])):
        raise RuntimeError('OVERNIGHT_EXISTING_HEALTHCHECK_REQUIRED')
    return {'status': 'PASS', 'configDigest': row['Id'], 'sizeBytes': row['Size'],
            'entrypoint': expected, 'platform': 'linux/amd64', 'secretEnvironmentPresent': False, 'gpuExecuted': False}


ci.inspect_image = inspect_image


def test():
    ci.require_free_runner()
    pulled = ci.run(['docker', 'pull', ci.BASE], timeout=900, check=False)
    if pulled.returncode:
        value = ci.state()
        value['baseImagePullFailure'] = {'exitCode': pulled.returncode, 'stdout': ci.bounded(pulled.stdout),
                                        'stderr': ci.bounded(pulled.stderr), 'gpuExecuted': False}
        ci.save(value)
        raise RuntimeError('OVERNIGHT_BASE_IMAGE_PULL_FAILED')
    context = payload_context()
    value = ci.state()
    value['testContext'] = str(context)
    ci.save(value)
    hashes = image_hashes(ci.BASE, context)
    source_plan = source_plan_probe(ci.BASE, context=context)
    code = ("import importlib.util,os,json;from unittest.mock import patch;"
            "os.environ['WORLD_ENGINE_STUDIO_STATE_ROOT']='/tmp/overnight-owner-negative';"
            "os.environ.pop('WORLD_ENGINE_STUDIO_OWNER_CODE',None);"
            "s=importlib.util.spec_from_file_location('_overnight_negative_boot','" + ci.DEST + "/bootstrap.py');"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "\ntry:\n with patch('subprocess.Popen',side_effect=AssertionError('NO_PROCESS_ALLOWED')): m.main([])"
            "\nexcept Exception as e:\n code=getattr(e,'code',None) or str(e);"
            "\n if code != 'STUDIO_OWNER_CONFIGURATION_REQUIRED': raise"
            "\n print(json.dumps({'status':'PASS','errorCode':code,'renderStarted':False,'gpuExecuted':False}))"
            "\nelse: raise RuntimeError('OVERNIGHT_MISSING_OWNER_DID_NOT_FAIL')")
    result = ci.record('actual-container-owner-fail-closed', container(ci.BASE, context=context) + ['-c', code], timeout=180)
    owner = json.loads(result.stdout.strip().splitlines()[-1])
    value = ci.state()
    value.update(testsStatus='PASS', testSourceHashes=hashes, actualSourcePlanLoad=source_plan, ownerNegativeProof=owner)
    ci.save(value)


def stage():
    value = ci.state()
    if value.get('testsStatus') != 'PASS':
        raise RuntimeError('OVERNIGHT_CPU_CONTAINER_TESTS_REQUIRED')
    context = payload_context()
    if ((context / 'overnight' / MANIFEST_NAME).read_bytes()
            != (Path(value['testContext']) / 'overnight' / MANIFEST_NAME).read_bytes()):
        raise RuntimeError('OVERNIGHT_TESTED_CONTEXT_CHANGED')
    value.update(context=str(context), extensionManifestSha256=ci.sha(context / 'overnight' / MANIFEST_NAME),
                 dockerfileSha256=ci.sha(context / 'Dockerfile'))
    ci.save(value)


def build():
    value = ci.state()
    ci.require_free_runner()
    if value.get('testsStatus') != 'PASS' or not value.get('context'):
        raise RuntimeError('OVERNIGHT_TESTED_PAYLOAD_REQUIRED')
    context = Path(value['context'])
    if (ci.sha(context / 'overnight' / MANIFEST_NAME) != value['extensionManifestSha256']
            or ci.sha(context / 'Dockerfile') != value['dockerfileSha256']):
        raise RuntimeError('OVERNIGHT_FROZEN_CONTEXT_CHANGED')
    result = ci.run(['docker', 'build', '--platform=linux/amd64', '--network=none', '--file', str(context / 'Dockerfile'),
                     '--label', 'world-engine.overnight.source-revision=' + os.environ['GITHUB_SHA'],
                     '--tag', value['image'], str(context)], timeout=900, check=False)
    value['dockerBuild'] = {'exitCode': result.returncode, 'stdout': ci.bounded(result.stdout), 'stderr': ci.bounded(result.stderr)}
    ci.save(value)
    if result.returncode:
        raise RuntimeError('OVERNIGHT_IMAGE_BUILD_FAILED')
    value = ci.state()
    value.update(imageBuilt=True, imageConfiguration=inspect_image(value['image']))
    ci.save(value)


def verify():
    value = ci.state()
    if not value.get('imageBuilt'):
        raise RuntimeError('OVERNIGHT_BUILT_IMAGE_REQUIRED')
    hashes = image_hashes(value['image'])
    scan = ci.secret_scan()
    value = ci.state()
    value.update(imageHashes=hashes, secretScan=scan, verification='PASS')
    ci.save(value)


def pull():
    ci.pull()
    value = ci.state()
    if (value.get('pullVerified') is not True or value.get('imageHashes', {}).get('status') != 'PASS'
            or value.get('imageConfiguration', {}).get('status') != 'PASS'):
        raise RuntimeError('OVERNIGHT_INDEPENDENT_PULL_PROOF_REQUIRED')
    value['imageProof'] = {'schema': 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_V1',
                          'imageDigest': value['imageDigest'], 'sourceManifestSHA256': ci.sha(HERE / MANIFEST_NAME),
                          'sourceCommit': os.environ['GITHUB_SHA'], 'independentPullVerified': True,
                          'sourceHashesVerified': True, 'baseDigest': ci.BASE_DIGEST, 'result': 'PASS'}
    ci.save(value)


def persist():
    value = ci.state()
    value['stepOutcomes'] = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    if 'failure' in value['stepOutcomes'].values():
        value['status'] = 'OVERNIGHT_CANDIDATE_BLOCKED'
    for name in ('context', 'testContext'):
        value.pop(name, None)
    phase = os.environ.get('RESULT_PHASE')
    run_id = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if phase not in {'build', 'pull'} or not re.fullmatch('[1-9][0-9]*-[1-9][0-9]*', run_id):
        raise RuntimeError('OVERNIGHT_BOUNDED_RESULT_REQUIRED')
    relative = Path(ci.NAMESPACE) / 'runs' / run_id
    raw = (json.dumps(value, indent=2) + '\n').encode()
    if len(raw) > 4 * 1024**2 or ci.SENSITIVE.search(raw.decode()):
        raise RuntimeError('OVERNIGHT_SAFE_EVIDENCE_REQUIRED')
    artifacts = {str(relative / (phase + '.json')): raw,
                 str(relative / (phase + '.SHA256SUMS')): (hashlib.sha256(raw).hexdigest() + '  ' + phase + '.json\n').encode()}
    if phase == 'pull' and value.get('pullVerified') is True and value.get('imageProof', {}).get('result') == 'PASS':
        proof = (json.dumps(value['imageProof'], indent=2) + '\n').encode()
        artifacts[str(relative / 'IMAGE_PROOF.json')] = proof
        artifacts[str(relative / 'IMAGE_PROOF.SHA256SUMS')] = (hashlib.sha256(proof).hexdigest() + '  IMAGE_PROOF.json\n').encode()
    ci.run(['git', 'fetch', '--filter=blob:none', 'origin', ci.BRANCH], timeout=180)
    ci.run(['git', 'switch', '--detach', 'FETCH_HEAD'])
    for name, data in artifacts.items():
        target = ci.REPO / name
        if target.exists():
            raise RuntimeError('OVERNIGHT_EXISTING_EVIDENCE_PRESERVED')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    ci.run(['git', 'config', 'user.name', 'github-actions[bot]'])
    ci.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    ci.run(['git', 'add', '--', *sorted(artifacts)])
    if sorted(ci.run(['git', 'diff', '--cached', '--name-only']).stdout.splitlines()) != sorted(artifacts):
        raise RuntimeError('OVERNIGHT_BOUNDED_EVIDENCE_COMMIT_REQUIRED')
    ci.run(['git', 'diff', '--cached', '--check'])
    ci.run(['git', 'commit', '-m', 'docs(overnight): persist ' + phase + ' CPU image evidence [skip ci]'])
    ci.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + ci.BRANCH], timeout=180)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('preflight', 'guard', 'test', 'stage', 'build', 'verify', 'publish', 'pull', 'persist'))
    phase = parser.parse_args(argv).phase
    try:
        (globals().get(phase) or getattr(ci, phase))()
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'OVERNIGHT_CI_FAILED'
        value = ci.state()
        value.update(status='OVERNIGHT_CANDIDATE_BLOCKED', failedPhase=phase, reasonCode=code, errorType=type(error).__name__)
        ci.save(value)
        print(json.dumps({'status': value['status'], 'phase': phase, 'reasonCode': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
