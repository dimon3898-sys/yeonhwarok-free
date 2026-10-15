#!/usr/bin/env python3
"""Free CPU/SwiftShader validation and opt-in ASTRA image layer, never NVIDIA proof."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/astra-gpu-activation-v1'
WORKFLOW = '.github/workflows/astra-gpu-activation.yml'
BRANCH = 'development/astra-gpu-activation-20261016'
BASELINE = '711b232265aefb1f0f4e368673f7943d86cf03b0'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:5dc61e9ce0edfc175c4a38fa0a3f559e660761e604b65bb5edfb6704312610b7'
BASE = IMAGE + '@' + PARENT_DIGEST
DEST = '/opt/rtx-package/repo/' + NAMESPACE
UPLOAD_NAMESPACE = 'world-simulation-shorts-engine/recovery/astra-gpu-integration-v1'
UPLOAD_DEST = '/opt/rtx-package/repo/' + UPLOAD_NAMESPACE
TAG_PATTERN = re.compile(r'astra-v1-711b232-[1-9][0-9]*-[1-9][0-9]*', re.ASCII)
RUNTIME_FILES = ('astra_adapter.mjs', 'astra_material.mjs', 'astra_material_core.mjs', 'astra_runtime.mjs',
                 'capture_astra.mjs', 'job_astra.py', 'launch_astra.py', 'serve_astra.py', 'prepare_activation.py',
                 'SCENE_MAP_DATA.json')
UPLOAD_FILES = {'upload_bundle.py': 'b462b294ff2c7d3301e592dfb075d636763bbaa98935d9ed7ca24ccd42d88e1a',
                'gpu_upload.mjs': '35fd7eb5ea9456e694a39a022a8f2452a09568cdd373b9d0b5ee4c4d3adad4f1'}
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
# Isolated import configures only a CI helper instance. Approved source bytes are
# reused without editing the existing helper or any production runtime module.
spec = importlib.util.spec_from_file_location('_astra_free_image_controls', HERE.parent / 'gcube-diagnostic-result-v1/ci.py')
controls = importlib.util.module_from_spec(spec); spec.loader.exec_module(controls)
for name, value in {'HERE': HERE, 'REPO': REPO, 'NAMESPACE': NAMESPACE, 'WORKFLOW': WORKFLOW,
                    'BRANCH': BRANCH, 'BASELINE': BASELINE, 'PARENT_DIGEST': PARENT_DIGEST, 'BASE': BASE,
                    'PATCHES': {}}.items():
    setattr(controls, name, value)
run = controls.run
save = controls.save
state_path = controls.state_path
sha = controls.sha
safe_log = controls.safe_log
_parent_helpers = controls.helpers


def helpers():
    base = _parent_helpers()
    return SimpleNamespace(require_space=base.require_space, login=base.login, check_image=composed_image_check)


controls.helpers = helpers


def state():
    if state_path().exists():
        return json.loads(state_path().read_text())
    return {'schema': 'WORLD_ENGINE_ASTRA_ACTIVATION_IMAGE_V1', 'status': 'IN_PROGRESS',
            'ciCommit': os.environ.get('GITHUB_SHA'), 'parentImage': BASE, 'gpuExecuted': False,
            'gCubeDeployed': False, 'paidWorkExecuted': False, 'rendererModified': False,
            'finalModified': False, 'oldImagesDeleted': False, 'imageBuilt': False,
            'imagePushed': False, 'pullVerified': False, 'videoQualityApproved': False}


controls.state = state


def configure_registry():
    import registry_guard
    # Its new isolated CI process accepts only this task's unique tag grammar.
    # No file or existing image/reference is modified.
    registry_guard.TAG_PATTERN = TAG_PATTERN
    return registry_guard


def preflight():
    controls.preflight()
    identifier, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    value = state(); value['tag'] = 'astra-v1-711b232-' + identifier + '-' + attempt
    value['image'] = IMAGE + ':' + value['tag']; save(value)


def guard():
    configure_registry(); controls.guard()


def _source_commit():
    value = os.environ.get('GITHUB_SHA') or run(['git', 'rev-parse', 'HEAD'], cwd=REPO).strip()
    if re.fullmatch(r'[0-9a-f]{40}', value) is None:
        raise RuntimeError('SOURCE_COMMIT_REQUIRED')
    return value


def _parent_manifest():
    path = HERE.parent / 'gcube-detached-render-v1/JOB_FILES.json'
    if sha(path) != '8df0a2248872ed4f568ce9cf9af9fd8994a217a9348127f0e2ed04b48a4c0208':
        raise RuntimeError('PINNED_DETACHED_MANIFEST_REQUIRED')
    return json.loads(path.read_text())


def generate_manifest():
    parent = _parent_manifest()
    inherited = []
    for name, expected in parent['files'].items():
        namespace = 'gcube-detached-render-v1' if name != 'verify_artifacts.py' else 'gcube-65422-render-v1'
        inherited.append({'imagePath': '/opt/world-engine-detached-render/' + name,
                          'repoPath': 'world-simulation-shorts-engine/recovery/' + namespace + '/' + name,
                          'sha256': expected})
    for image_path, expected in parent['inheritedSources'].items():
        if image_path.startswith('/opt/world-engine-startup-diagnostics/'):
            namespace = 'gcube-diagnostic-image-v1'
        elif image_path.startswith('/opt/world-engine-storage-fix/'):
            namespace = 'gcube-storage-fix-v1'
        else:
            namespace = 'gcube-diagnostic-result-v1'
        inherited.append({'imagePath': image_path,
                          'repoPath': 'world-simulation-shorts-engine/recovery/' + namespace + '/' + Path(image_path).name,
                          'sha256': expected})
    for name in RUNTIME_FILES:
        source = HERE / name
        if source.is_symlink() or not source.is_file():
            raise RuntimeError('EXPLICIT_RUNTIME_FILE_REQUIRED')
    for name, expected in UPLOAD_FILES.items():
        if sha(REPO / UPLOAD_NAMESPACE / name) != expected:
            raise RuntimeError('PINNED_UPLOAD_SOURCE_REQUIRED')
    for entry in inherited:
        if sha(REPO / entry['repoPath']) != entry['sha256']:
            raise RuntimeError('PINNED_PARENT_RUNTIME_REQUIRED')
    return {'schema': 'ASTRA_ACTIVATION_FILES_V1', 'profileId': 'ASTRA_SOURCE_MATERIAL_V1',
            'sourceCommit': _source_commit(), 'baselineCommit': BASELINE, 'parentImage': BASE,
            'files': {name: sha(HERE / name) for name in RUNTIME_FILES},
            'repoDependencies': {UPLOAD_NAMESPACE + '/' + name: expected for name, expected in UPLOAD_FILES.items()},
            'inheritedFiles': inherited}


def _test_context():
    root = Path(tempfile.mkdtemp(prefix='astra-activation-context-', dir=os.environ['RUNNER_TEMP']))
    selected = root / NAMESPACE
    shutil.copytree(HERE, selected, ignore=shutil.ignore_patterns('runs', '__pycache__'))
    upload = root / UPLOAD_NAMESPACE; upload.mkdir(parents=True)
    for name, expected in UPLOAD_FILES.items():
        source = REPO / UPLOAD_NAMESPACE / name
        if sha(source) != expected: raise RuntimeError('PINNED_UPLOAD_SOURCE_REQUIRED')
        shutil.copyfile(source, upload / name)
    (selected / 'ACTIVATION_FILES.json').write_text(json.dumps(generate_manifest(), indent=2) + '\n')
    return root


def _container_common(image, *, context=None):
    command = ['docker', 'run', '--rm', '--network=none', '--memory=6g', '--cpus=2',
               '--pids-limit=512', '--restart=no', '--shm-size=2g', '--user=0:0',
               '--tmpfs', '/workspace:rw,mode=1777', '--tmpfs', '/tmp:rw,mode=1777']
    if context is not None:
        command += ['--mount', 'type=bind,source=' + str(context / NAMESPACE) + ',target=' + DEST + ',readonly',
                    '--mount', 'type=bind,source=' + str(context / UPLOAD_NAMESPACE) + ',target=' + UPLOAD_DEST + ',readonly']
    return command


def _record_case(name, command, *, timeout=240, scope):
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    report = {'name': name, 'exitCode': result.returncode, 'stdout': safe_log(result.stdout),
              'stderr': safe_log(result.stderr), 'scope': scope, 'gpuExecuted': False}
    value = state(); value.setdefault('focusedTests', {}).setdefault('results', []).append(report)
    value['focusedTests']['exitCode'] = max(item['exitCode'] for item in value['focusedTests']['results']); save(value)
    if result.returncode:
        raise RuntimeError('FOCUSED_ACTIVATION_TEST_FAILED')
    return result


def _drop_uid_code(body):
    return ("import os,pathlib; p=pathlib.Path('/var/lib/world-engine-private/engine/job-astra-v1'); "
            "p.mkdir(mode=0o700,exist_ok=True); os.chown(p,1000,1000); "
            "os.setgroups([]); os.setgid(1000); os.setuid(1000); " + body)


def software_probe(image, *, context=None, phase):
    common = _container_common(image, context=context)
    # This is an actual Chromium GLSL compile/draw/readback under SwiftShader,
    # explicitly test-only. It cannot satisfy production NVIDIA admission.
    command = common + ['--entrypoint=/usr/bin/python3', image, '-B', '-c',
        _drop_uid_code("import subprocess; raise SystemExit(subprocess.run(['/usr/local/bin/node','" + DEST + "/software_probe.mjs']).returncode)")]
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=480)
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = None
    value = state(); value[phase] = {'exitCode': result.returncode, 'report': report,
        'stdout': safe_log(result.stdout), 'stderr': safe_log(result.stderr),
        'scope': 'ACTUAL_CHROMIUM_SWIFTSHADER_COMPILE_DRAW_CPU_NOT_NVIDIA', 'gpuExecuted': False}; save(value)
    if (result.returncode != 0 or not isinstance(report, dict) or report.get('status') != 'PASS'
            or report.get('schema') != 'ASTRA_ACTUAL_SOFTWARE_RENDER_PROBE_V1'
            or report.get('testOnly') is not True or report.get('gpuRenderingVerified') is not False
            or report.get('physicalNvidiaExecuted') is not False
            or any(report.get(key) is not True for key in ('actualShaderCompile','softwareWebGLDrawExecuted',
                    'actualSoftwareABPixelsDiffer','cameraAndGeometryEqual','originalSourcesUnchanged'))):
        raise RuntimeError('ACTUAL_SOFTWARE_ACTIVATION_PROBE_REQUIRED')
    return report


def test():
    helpers().require_space()
    _record_case('ci-safety', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE / 'tests'),
                 '-p', 'test_ci.py', '-v'], scope='NEW_CI_MOCKS_ONLY')
    run(['docker', 'pull', BASE], timeout=900)
    context = _test_context(); common = _container_common(BASE, context=context)
    python_tests = sorted(path.name for path in (HERE / 'tests').glob('test_*.py') if path.name != 'test_ci.py')
    node_tests = sorted(path.name for path in (HERE / 'tests').glob('test_*.mjs'))
    if not python_tests or not node_tests: raise RuntimeError('FOCUSED_ACTIVATION_TESTS_REQUIRED')
    for pattern in python_tests:
        body = ("import unittest; s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + pattern + "'); "
                "r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>0 and not r.skipped else 1)")
        _record_case(pattern, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c', _drop_uid_code(body)],
                     scope='NEW_PROFILE_COORDINATE_SOURCE_AND_JOB_TESTS_CPU_NO_GPU')
    for pattern in node_tests:
        _record_case(pattern, common + ['--entrypoint=/usr/bin/python3', BASE, '-B', '-c',
                     _drop_uid_code("import subprocess; raise SystemExit(subprocess.run(['/usr/local/bin/node','--test','--test-isolation=none','" + DEST + "/tests/" + pattern + "']).returncode)")],
                     scope='NEW_CPU_JS_CONTRACTS_NO_NVIDIA')
    software_probe(BASE, context=context, phase='softwareProbeBeforeBuild')
    value = state(); value['focusedTests']['status'] = 'PASS'; save(value)


def stage():
    value = state()
    if (value.get('focusedTests', {}).get('status') != 'PASS'
            or value.get('softwareProbeBeforeBuild', {}).get('exitCode') != 0):
        raise RuntimeError('ACTIVATION_TEST_AND_SOFTWARE_PROBE_REQUIRED')
    context = Path(os.environ['RUNNER_TEMP']) / ('astra-image-' + value['tag']); context.mkdir(mode=0o700)
    runtime = context / 'activation'; runtime.mkdir()
    manifest = generate_manifest()
    for name in RUNTIME_FILES:
        shutil.copyfile(HERE / name, runtime / name)
    shutil.copyfile(HERE / 'software_probe.mjs', runtime / 'software_probe.mjs')
    (runtime / 'ACTIVATION_FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
    upload = context / 'upload'; upload.mkdir()
    for name in UPLOAD_FILES: shutil.copyfile(REPO / UPLOAD_NAMESPACE / name, upload / name)
    shutil.copyfile(HERE / 'Dockerfile', context / 'Dockerfile')
    value.update(context=str(context), activationManifest=manifest,
                 activationManifestSha256=sha(runtime / 'ACTIVATION_FILES.json'),
                 softwareProbeSha256=sha(runtime / 'software_probe.mjs'), dockerfileSha256=sha(context / 'Dockerfile'))
    save(value)


def inspect_image(image):
    facts = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    config = facts.get('Config', {}); labels = config.get('Labels', {})
    expected = {'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.astra-activation.source-revision': os.environ['GITHUB_SHA'],
        'world-engine.astra-activation.parent-digest': PARENT_DIGEST,
        'world-engine.detached-render.source-revision': 'aaa9347bcb50eaa480dc83e135bc2ebca6f1f5f2'}
    if (facts.get('Os') != 'linux' or facts.get('Architecture') != 'amd64'
            or any(labels.get(key) != value for key, value in expected.items())):
        raise RuntimeError('IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint') != ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('PARENT_ENTRYPOINT_CHANGED')
    if {entry.partition('=')[0] for entry in config.get('Env', [])} & {'GH_TOKEN','GITHUB_TOKEN','DOCKER_AUTH_CONFIG','GITHUB_AUTHORIZATION'}:
        raise RuntimeError('CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value = state(); value['builderBeforeBuild'] = helpers().require_space(); save(value)
    context = Path(value['context'])
    if (set(path.name for path in context.iterdir()) != {'activation','upload','Dockerfile'}
            or set(path.name for path in (context/'activation').iterdir()) != {*RUNTIME_FILES, 'ACTIVATION_FILES.json', 'software_probe.mjs'}
            or set(path.name for path in (context/'upload').iterdir()) != set(UPLOAD_FILES)):
        raise RuntimeError('EXPLICIT_BUILD_CONTEXT_REQUIRED')
    subprocess.run(['docker','build','--platform=linux/amd64','--file',str(context/'Dockerfile'),
                    '--label','world-engine.astra-activation.source-revision='+os.environ['GITHUB_SHA'],
                    '--tag',value['image'],str(context)],check=True,timeout=600)
    facts = inspect_image(value['image']); value.update(imageBuilt=True,configDigest=facts['Id'],imageSizeBytes=facts['Size']); save(value)


def image_hashes(image):
    code = ("import json,sys; sys.path.insert(0,'" + DEST + "'); import prepare_activation; "
            "print(json.dumps(prepare_activation.verify_extension(package_root='/opt/rtx-package',require_staged=True)))")
    actual = json.loads(run(['docker','run','--rm','--network=none','--user=1000:1000','--entrypoint=/usr/bin/python3',image,'-B','-c',code]))
    if actual.get('status') != 'PASS': raise RuntimeError('ACTIVATION_IMAGE_HASH_MISMATCH')
    expected = hashlib.sha256((json.dumps(generate_manifest(),indent=2)+'\n').encode()).hexdigest()
    if actual.get('manifestSha256') != expected: raise RuntimeError('ACTIVATION_MANIFEST_SOURCE_MISMATCH')
    return actual


def composed_source_tree(root, legacy, extensions):
    """Strict union of original immutable receipt and independently hashed extras.

    The installed npm subtree has the identical exclusion used by the original
    image auditor. Every other regular file must be in exactly one manifest or
    be a validated original-source Python bytecode derivative. No directory or
    source is hidden from the inventory walk.
    """
    root = Path(root)
    for ancestor in [*reversed(root.parents), root]:
        legacy._root_owned_readonly(ancestor, directory=True)
    contract, contract_hash = legacy._read_json(root / 'source_contract.json')
    receipt, receipt_hash = legacy._read_json(root / 'STAGING_RECEIPT.json')
    if contract_hash != legacy.SOURCE_CONTRACT_SHA256 or not isinstance(contract.get('files'), list) or len(contract['files']) != 140:
        raise legacy.ImageCheckError('PINNED_SOURCE_CONTRACT_MISMATCH')
    copied = receipt.get('files')
    if not isinstance(copied, list) or len(copied) != 160:
        raise legacy.ImageCheckError('STAGED_INVENTORY_INVALID')
    expected = {'source_contract.json': contract_hash, 'STAGING_RECEIPT.json': receipt_hash}
    bytecode_sources = {}
    for record in copied:
        if not isinstance(record, dict): raise legacy.ImageCheckError('STAGED_INVENTORY_INVALID')
        relative = 'repo/' + legacy._canonical(record.get('repoPath'))
        digest = record.get('sha256')
        if relative in expected or legacy._credential_path(relative) or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
            raise legacy.ImageCheckError('STAGED_CREDENTIAL_OR_DUPLICATE_FILE')
        expected[relative] = digest
        if relative.endswith('.py'):
            source = root / relative
            cached = Path(importlib.util.cache_from_source(str(source), optimization=''))
            bytecode_sources[cached.relative_to(root).as_posix()] = (source,digest)
    if not isinstance(extensions,dict) or not extensions:
        raise legacy.ImageCheckError('STAGED_INVENTORY_INVALID')
    for relative, digest in extensions.items():
        relative = legacy._canonical(relative)
        if (relative in expected or legacy._credential_path(relative) or not isinstance(digest,str)
            or not re.fullmatch('[0-9a-f]{64}',digest)):
            raise legacy.ImageCheckError('STAGED_CREDENTIAL_OR_DUPLICATE_FILE')
        expected[relative] = digest
    installed = root / 'repo/cinematic-world-map/node_modules'
    observed = set(); bytecode_proofs = []
    def walk_error(_error):
        raise legacy.ImageCheckError('STAGED_TREE_UNREADABLE')
    for parent, directories, filenames in os.walk(root,followlinks=False,onerror=walk_error):
        parent = Path(parent); legacy._root_owned_readonly(parent,directory=True)
        for name in list(directories):
            candidate = parent / name; legacy._root_owned_readonly(candidate,directory=True)
            if candidate == installed:
                directories.remove(name)
            elif legacy._credential_path(candidate.relative_to(root)):
                raise legacy.ImageCheckError('STAGED_CREDENTIAL_PATH_PRESENT')
        for name in filenames:
            candidate=parent/name; relative=candidate.relative_to(root).as_posix()
            if relative not in expected:
                if relative in bytecode_sources and not legacy._credential_path(relative):
                    source,digest=bytecode_sources[relative]
                    proof=legacy._validate_bytecode(candidate,source,expected_source_sha256=digest)
                    bytecode_proofs.append({'path':relative,**proof}); continue
                raise legacy.ImageCheckError('UNEXPECTED_STAGED_FILE',relative_path=relative)
            if legacy._credential_path(relative): raise legacy.ImageCheckError('UNEXPECTED_STAGED_FILE',relative_path=relative)
            legacy._root_owned_readonly(candidate)
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected[relative]:
                raise legacy.ImageCheckError('PACKAGED_SOURCE_VERIFICATION_FAILED',relative_path=relative)
            observed.add(relative)
    if observed != set(expected): raise legacy.ImageCheckError('STAGED_FILE_MISSING')
    proof_body=json.dumps(sorted(bytecode_proofs,key=lambda item:item['path']),sort_keys=True,separators=(',',':')).encode()
    return {'files':len(copied),'sourceContractSha256':contract_hash,'stagingReceiptSha256':receipt_hash,
            'derivedBytecodeCount':len(bytecode_proofs),'derivedBytecodeProofSha256':hashlib.sha256(proof_body).hexdigest(),
            'additiveFiles':len(extensions),'composedInventoryFiles':len(observed),
            'unexpectedFiles':0,'audit':'STRICT_ORIGINAL_RECEIPT_PLUS_HASHED_ASTRA_EXTENSION_NO_MASKING'}


def composed_image_check(image, *, hashes_only=False):
    if hashes_only is not True: raise RuntimeError('COMPOSED_HASHES_ONLY_AUDIT_REQUIRED')
    original = HERE.parent / 'rtx-image-build-v1/image_checks.py'
    if sha(original) != 'c1ca60b64fe752cdc3b95c892718f4f18f25cb1bcc044f8f6269c017f976f51f': raise RuntimeError('PINNED_ORIGINAL_IMAGE_AUDITOR_REQUIRED')
    manifest = generate_manifest()
    manifest_hash = hashlib.sha256((json.dumps(manifest,indent=2)+'\n').encode()).hexdigest()
    extensions = {'repo/'+NAMESPACE+'/'+name:digest for name,digest in manifest['files'].items()}
    extensions.update({'repo/'+name:digest for name,digest in manifest['repoDependencies'].items()})
    extensions['repo/'+NAMESPACE+'/ACTIVATION_FILES.json']=manifest_hash
    extensions['repo/'+NAMESPACE+'/software_probe.mjs']=sha(HERE/'software_probe.mjs')
    code = ("import hashlib,importlib.util,json,os,pathlib,re; from pathlib import Path; "
            "s=importlib.util.spec_from_file_location('_immutable_image_audit','/__ci/image_checks.py'); "
            "legacy=importlib.util.module_from_spec(s); s.loader.exec_module(legacy);\n"
            + inspect.getsource(composed_source_tree)
            + "\nlegacy._check_source_tree=lambda root:composed_source_tree(root,legacy,"+repr(extensions)+");\n"
            + "try:\n result=legacy.run_checks(hashes_only=True)\n"
            + "except legacy.ImageCheckError as error:\n result={'status':'FAIL','errorCode':str(error),"
            + "'unexpectedRelativePath':error.relative_path,'gpuExecuted':False}\n"
            + "print(json.dumps(result)); raise SystemExit(0 if result.get('status')=='PASS' else 1)\n")
    result = subprocess.run(['docker','run','--rm','--network=none','--user=1000:1000',
        '--entrypoint=/usr/bin/python3','--mount','type=bind,source='+str(original)+',target=/__ci/image_checks.py,readonly',
        image,'-B','-c',code],text=True,capture_output=True,check=False,timeout=180)
    audit_state=state(); audit_state['composedImageAudit']={'exitCode':result.returncode,
        'stdout':safe_log(result.stdout),'stderr':safe_log(result.stderr),
        'scope':'IMMUTABLE_ORIGINAL_AUDITOR_WITH_STRICT_ADDITIVE_EXPECTED_INVENTORY_NO_MASKING'}; save(audit_state)
    try: report=json.loads(result.stdout)
    except ValueError: raise RuntimeError('COMPOSED_IMAGE_AUDIT_JSON_REQUIRED') from None
    source=report.get('source',{}) if isinstance(report,dict) else {}
    if (result.returncode!=0 or report.get('schema')!='RTX_BUILT_IMAGE_CPU_CHECK_V1' or report.get('status')!='PASS'
        or report.get('uid')!=1000 or report.get('gpuExecuted') is not False or report.get('browserPageOpened') is not False
        or report.get('networkIsolation')!='LOOPBACK_ONLY' or report.get('mode')!='hashes-only'
        or source.get('files')!=160 or source.get('originalFiles')!=140
        or source.get('additiveFiles')!=len(extensions) or source.get('unexpectedFiles')!=0
        or source.get('sourceContractSha256')!='5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180'
        or source.get('sourceCommits')!={'cpu':'a002d89492734bfa9d17b98145ee6cb9a3b366a2','glow':'45af879d7417abba58e9ebd59d8e6630a785ac28'}):
        value=state();value['imageChecks']=report;save(value)
        raise RuntimeError('COMPOSED_IMAGE_AUDIT_FAILED')
    return report


def secret_scan(image):
    value = state(); root = Path(tempfile.mkdtemp(prefix='astra-scan-',dir=os.environ['RUNNER_TEMP']))
    container = run(['docker','create','--entrypoint=/bin/true',image]).strip()
    try:
        run(['docker','cp',container+':'+DEST,str(root/'actual-activation')])
        run(['docker','cp',container+':'+UPLOAD_DEST,str(root/'actual-upload')])
    finally:
        run(['docker','rm',container])
    shutil.copytree(HERE,root/'namespace',ignore=shutil.ignore_patterns('runs','__pycache__'))
    shutil.copyfile(REPO/WORKFLOW,root/'workflow.yml')
    scanner_dir=Path(tempfile.mkdtemp(prefix='astra-scanner-',dir=os.environ['RUNNER_TEMP']))
    with urllib.request.urlopen('https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz',timeout=30) as response:
        body=response.read(32*1024**2+1)
    if len(body)>32*1024**2: raise RuntimeError('SCANNER_ARCHIVE_SIZE_LIMIT')
    archive=scanner_dir/'scanner.tar.gz'; archive.write_bytes(body)
    with tarfile.open(archive,'r:gz') as source:
        member=source.getmember('gitleaks')
        if not member.isfile() or member.size>64*1024**2: raise RuntimeError('SCANNER_MEMBER_INVALID')
        binary=source.extractfile(member).read()
    if hashlib.sha256(binary).hexdigest()!=SCANNER_SHA: raise RuntimeError('SCANNER_SHA_MISMATCH')
    executable=scanner_dir/'gitleaks'; executable.write_bytes(binary); executable.chmod(0o700)
    config=scanner_dir/'config.toml'; config.write_text('[extend]\nuseDefault = true\n')
    ignore=scanner_dir/'ignore'; ignore.write_text(''); report=scanner_dir/'findings.json'
    outcome=subprocess.run([str(executable),'dir',str(root),'--config',str(config),'--gitleaks-ignore-path',str(ignore),
        '--ignore-gitleaks-allow','--redact=100','--report-format=json','--report-path',str(report),'--no-banner'],
        text=True,capture_output=True,check=False,timeout=180)
    findings=json.loads(report.read_text()) if report.exists() and report.stat().st_size<16*1024**2 else None
    value['secretScan']={'status':'PASS' if outcome.returncode==0 and findings==[] else 'FAIL',
        'findings':len(findings) if isinstance(findings,list) else None,'scannerSHA256':SCANNER_SHA,
        'scope':'ACTUAL_NEW_IMAGE_RUNTIME_PLUS_NEW_NAMESPACE_AND_WORKFLOW_PARENT_AUDIT_REUSED'}; save(value)
    if value['secretScan']['status']!='PASS': raise RuntimeError('ASTRA_SECRET_SCAN_FAILED')


def verify():
    value = state(); os.environ['RTX_CI_STATE'] = str(state_path())
    value.update(originalSources=helpers().check_image(value['image'],hashes_only=True),imageHashes=image_hashes(value['image'])); save(value)
    software_probe(value['image'],phase='actualImageSoftwareProbe')
    outcomes=[]
    for action in ('inspect','status'):
        result=subprocess.run(['docker','run','--rm','--network=none','--user=1000:1000','--memory=2g',
            '--pids-limit=128','--restart=no','--tmpfs','/world-storage:rw,mode=1777',
            '--entrypoint=/usr/bin/python3',value['image'],'-B',DEST+'/job_astra.py',action],
            text=True,capture_output=True,check=False,timeout=30)
        try: body=json.loads(result.stdout)
        except ValueError: raise RuntimeError('ASTRA_READ_ONLY_CLI_JSON_REQUIRED') from None
        if (result.returncode!=0 or not isinstance(body,dict) or body.get('renderAllowed') is not False
            or (action=='inspect' and body.get('status')!='CLEAR')
            or (action=='status' and body.get('state')!='NOT_STARTED')):
            raise RuntimeError('ASTRA_READ_ONLY_CLI_MUST_NOT_START_RENDER')
        outcomes.append({'action':action,'exitCode':result.returncode,'report':body,'gpuExecuted':False})
    value=state(); value['actualImageReadOnlyCLI']=outcomes; save(value)
    secret_scan(value['image']); value=state(); value['verification']='PASS'; save(value)


def publish():
    configure_registry(); controls.publish()


controls.inspect_image = inspect_image
controls.image_hashes = image_hashes


def pull():
    configure_registry(); controls.pull()
    value = state(); value['status'] = 'ASTRA_ACTIVATION_IMAGE_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING'; save(value)


def persist():
    value=state(); outcomes=json.loads(os.environ.get('RESULT_STEP_OUTCOMES','{}')); value['stepOutcomes']=outcomes
    if value['status']=='IN_PROGRESS' or any(item=='failure' for item in outcomes.values()): value['status']='ASTRA_ACTIVATION_IMAGE_BLOCKED'
    relative=NAMESPACE+'/runs/'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']+'/'+os.environ['RESULT_PHASE']+'.json'
    run(['git','fetch','--filter=blob:none','origin',BRANCH],cwd=REPO,timeout=180); run(['git','switch','--detach','FETCH_HEAD'],cwd=REPO)
    target=REPO/relative
    if target.exists(): raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(value,indent=2)+'\n')
    run(['git','config','user.name','github-actions[bot]'],cwd=REPO)
    run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=REPO)
    run(['git','add','--',relative],cwd=REPO)
    if run(['git','diff','--cached','--name-only'],cwd=REPO).splitlines()!=[relative]: raise RuntimeError('REPORT_ONLY_COMMIT_REQUIRED')
    run(['git','commit','-m','docs: persist ASTRA activation '+os.environ['RESULT_PHASE']+' evidence [skip ci]'],cwd=REPO)
    run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=REPO,timeout=180)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['preflight','guard','test','stage','build','verify','publish','pull','persist']); args=parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        code=str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}',code): code='ASTRA_CI_OPERATION_FAILED'
        value=state(); value.update(status='ASTRA_ACTIVATION_IMAGE_BLOCKED',failedPhase=args.phase,reasonCode=code,errorType=type(error).__name__)
        if isinstance(error,subprocess.CalledProcessError): value['failedCommandExitCode']=error.returncode
        save(value); print(json.dumps({'status':value['status'],'phase':args.phase,'reasonCode':code})); raise SystemExit(1)
