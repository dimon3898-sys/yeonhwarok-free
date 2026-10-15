#!/usr/bin/env python3
"""Additive visual-quality image using the proven free ASTRA CI controls unchanged."""
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
import stat
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
NAMESPACE='world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1'
WORKFLOW='.github/workflows/visual-quality-upgrade-v1.yml'
BRANCH='development/visual-quality-upgrade-v1-20261016'
BASELINE='a7df81f6ad246333fe826270c14c242e477362d4'
IMAGE='ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST='sha256:8aba498e295b45a9cbfa29eeacd6f7779ff3d2ce4482c92215176be1540ff71a'
BASE=IMAGE+'@'+PARENT_DIGEST
DEST='/opt/rtx-package/repo/'+NAMESPACE
PRIOR_NAMESPACE='world-simulation-shorts-engine/recovery/astra-gpu-activation-v1'
PRIOR_MANIFEST_SHA='8264f51f52693a0ce80ed167d0d25fa56c6d5505b5cc01712c2d198c6448f330'
PRIOR_PROBE_SHA='54a5d833dd676b932d08772b1677693d799490ce89ecc7064df8b6187923efcb'
TAG_PATTERN=re.compile(r'visual-v1-a7df81f-[1-9][0-9]*-[1-9][0-9]*',re.ASCII)
RUNTIME_FILES=('quality_runtime.mjs','quality_adapter.mjs','quality_profiles.mjs','serve_quality.py',
    'quality_material.mjs','quality_material_core.mjs','support_gpu.mjs','distance_support.mjs',
    'quality_territory.mjs','territory_style_core.mjs','capture_quality.mjs','launch_quality.py',
    'job_quality.py','prepare_quality.py')
TEST_FILES=('software_probe.mjs','support_ab_probe.mjs')
PNG_NAMES=frozenset({'A_075.png','B_075.png','C_075.png','D_075.png','E_075.png','F_000.png','F_075.png','F_149.png'})
MAX_PNG_BYTES=12*1024**2
MAX_PNG_TOTAL=48*1024**2
# Reuse an isolated imported CI helper object. This changes no existing file,
# source contract, deployed runtime module, tag, image or renderer behavior.
spec=importlib.util.spec_from_file_location('_quality_parent_ci',HERE.parent/'astra-gpu-activation-v1/ci.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
controls=prior.controls
for name,value in {'HERE':HERE,'REPO':REPO,'NAMESPACE':NAMESPACE,'WORKFLOW':WORKFLOW,'BRANCH':BRANCH,
                    'BASELINE':BASELINE,'PARENT_DIGEST':PARENT_DIGEST,'BASE':BASE,'PATCHES':{}}.items():
    setattr(controls,name,value)
run=controls.run
save=controls.save
state_path=controls.state_path
sha=controls.sha
safe_log=controls.safe_log


def state():
    if state_path().exists():return json.loads(state_path().read_text())
    return {'schema':'WORLD_ENGINE_VISUAL_QUALITY_IMAGE_V1','status':'IN_PROGRESS','ciCommit':os.environ.get('GITHUB_SHA'),
        'parentImage':BASE,'gpuExecuted':False,'gCubeDeployed':False,'paidWorkExecuted':False,
        'rendererModified':False,'finalModified':False,'oldImagesDeleted':False,
        'imageBuilt':False,'imagePushed':False,'pullVerified':False,'videoQualityApproved':False}


def helpers():
    base=prior._parent_helpers()
    return SimpleNamespace(require_space=base.require_space,login=base.login,check_image=composed_image_check)


controls.state=state
controls.helpers=helpers
# Reuse only the parent's bounded recorder and source scanner with new namespace
# globals in this isolated module, never alter the original on-disk CI module.
for name,value in {'HERE':HERE,'REPO':REPO,'NAMESPACE':NAMESPACE,'WORKFLOW':WORKFLOW,'DEST':DEST,
                   'state':state,'save':save}.items():setattr(prior,name,value)


def configure_registry():
    module=prior.configure_registry();module.TAG_PATTERN=TAG_PATTERN;return module


def preflight():
    controls.preflight()
    value=state();value['tag']='visual-v1-a7df81f-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    value['image']=IMAGE+':'+value['tag'];save(value)


def guard():configure_registry();controls.guard()


def source_commit():
    value=os.environ.get('GITHUB_SHA') or run(['git','rev-parse','HEAD'],cwd=REPO).strip()
    if not re.fullmatch('[0-9a-f]{40}',value):raise RuntimeError('SOURCE_COMMIT_REQUIRED')
    return value


def parent_closure():
    directory=REPO/PRIOR_NAMESPACE
    if sha(directory/'ACTIVATION_FILES.json')!=PRIOR_MANIFEST_SHA or sha(directory/'software_probe.mjs')!=PRIOR_PROBE_SHA:
        raise RuntimeError('PINNED_ASTRA_PARENT_MANIFEST_REQUIRED')
    manifest=json.loads((directory/'ACTIVATION_FILES.json').read_text())
    files={PRIOR_NAMESPACE+'/'+name:digest for name,digest in manifest['files'].items()}
    files.update(manifest['repoDependencies'])
    files[PRIOR_NAMESPACE+'/ACTIVATION_FILES.json']=PRIOR_MANIFEST_SHA
    files[PRIOR_NAMESPACE+'/software_probe.mjs']=PRIOR_PROBE_SHA
    if len(files)!=14:raise RuntimeError('EXACT_FOURTEEN_PARENT_ADDITIONS_REQUIRED')
    for relative,digest in files.items():
        if sha(REPO/relative)!=digest:raise RuntimeError('PARENT_ASTRA_SOURCE_CHANGED')
    return manifest,files


def generate_manifest():
    parent,dependencies=parent_closure()
    if not RUNTIME_FILES:raise RuntimeError('EXPLICIT_RUNTIME_CLOSURE_REQUIRED')
    for name in (*RUNTIME_FILES,*TEST_FILES):
        target=HERE/name
        if target.is_symlink() or not target.is_file():raise RuntimeError('EXPLICIT_RUNTIME_SOURCE_REQUIRED')
    return {'schema':'WORLD_ENGINE_VISUAL_QUALITY_FILES_V1','profileId':'VISUAL_QUALITY_UPGRADE_V1',
        'sourceCommit':source_commit(),'baselineCommit':BASELINE,'parentImage':BASE,
        'files':{name:sha(HERE/name) for name in RUNTIME_FILES},'repoDependencies':dependencies,
        'inheritedFiles':parent['inheritedFiles'],'parentActivationManifestSha256':PRIOR_MANIFEST_SHA,
        'testFiles':{name:sha(HERE/name) for name in TEST_FILES}}


def extensions():
    manifest=generate_manifest()
    result={'repo/'+relative:digest for relative,digest in manifest['repoDependencies'].items()}
    result.update({'repo/'+NAMESPACE+'/'+name:digest for name,digest in manifest['files'].items()})
    result['repo/'+NAMESPACE+'/QUALITY_FILES.json']=hashlib.sha256((json.dumps(manifest,indent=2)+'\n').encode()).hexdigest()
    result.update({'repo/'+NAMESPACE+'/'+name:sha(HERE/name) for name in TEST_FILES})
    return result


def composed_image_check(image,*,hashes_only=False):
    if hashes_only is not True:raise RuntimeError('COMPOSED_HASHES_ONLY_REQUIRED')
    original=HERE.parent/'rtx-image-build-v1/image_checks.py'
    if sha(original)!='c1ca60b64fe752cdc3b95c892718f4f18f25cb1bcc044f8f6269c017f976f51f':
        raise RuntimeError('PINNED_ORIGINAL_AUDITOR_REQUIRED')
    extra=extensions()
    code=("import hashlib,importlib.util,json,os,re; from pathlib import Path; "
        "s=importlib.util.spec_from_file_location('_original_audit','/__ci/image_checks.py'); "
        "legacy=importlib.util.module_from_spec(s); s.loader.exec_module(legacy);\n"
        +inspect.getsource(prior.composed_source_tree)
        +"\nlegacy._check_source_tree=lambda root:composed_source_tree(root,legacy,"+repr(extra)+");\n"
        +"try:\n result=legacy.run_checks(hashes_only=True)\n"
        +"except legacy.ImageCheckError as error:\n result={'status':'FAIL','errorCode':str(error),'unexpectedRelativePath':error.relative_path}\n"
        +"print(json.dumps(result)); raise SystemExit(0 if result.get('status')=='PASS' else 1)\n")
    result=subprocess.run(['docker','run','--rm','--network=none','--user=1000:1000','--entrypoint=/usr/bin/python3',
        '--mount','type=bind,source='+str(original)+',target=/__ci/image_checks.py,readonly',image,'-B','-c',code],
        text=True,capture_output=True,check=False,timeout=180)
    value=state();value['composedImageAudit']={'exitCode':result.returncode,'stdout':safe_log(result.stdout),'stderr':safe_log(result.stderr)};save(value)
    try:report=json.loads(result.stdout)
    except ValueError:raise RuntimeError('COMPOSED_AUDIT_JSON_REQUIRED') from None
    source=report.get('source',{}) if isinstance(report,dict) else {}
    if (result.returncode or report.get('status')!='PASS' or report.get('uid')!=1000
        or report.get('gpuExecuted') is not False or report.get('mode')!='hashes-only'
        or report.get('networkIsolation')!='LOOPBACK_ONLY' or source.get('files')!=160 or source.get('originalFiles')!=140
        or source.get('additiveFiles')!=len(extra) or source.get('unexpectedFiles')!=0
        or source.get('sourceContractSha256')!='5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180'):
        value=state();value['imageChecks']=report;save(value);raise RuntimeError('STRICT_COMPOSED_IMAGE_AUDIT_FAILED')
    return report


def test_context():
    path=Path(tempfile.mkdtemp(prefix='quality-source-context-',dir=os.environ['RUNNER_TEMP']))
    shutil.copytree(HERE,path,dirs_exist_ok=True,ignore=shutil.ignore_patterns('runs','__pycache__'))
    (path/'QUALITY_FILES.json').write_text(json.dumps(generate_manifest(),indent=2)+'\n')
    return path


def container(*,context=None,evidence=None):
    args=['docker','run','--rm','--network=none','--user=0:0','--memory=8g','--cpus=2','--pids-limit=512',
          '--restart=no','--shm-size=2g','--tmpfs','/workspace:rw,mode=1777','--tmpfs','/tmp:rw,mode=1777']
    if context is not None:args+=['--mount','type=bind,source='+str(context)+',target='+DEST+',readonly']
    if evidence is not None:args+=['--mount','type=bind,source='+str(evidence)+',target=/workspace/quality-evidence',
        '--env','WORLD_ENGINE_QUALITY_EVIDENCE_DIR=/workspace/quality-evidence']
    return args


def uid_code(body):
    return ("import os,pathlib; p=pathlib.Path('/var/lib/world-engine-private/engine/job-quality-v1'); "
        "p.mkdir(mode=0o700,exist_ok=True); os.chown(p,1000,1000); os.setgroups([]);os.setgid(1000);os.setuid(1000); "+body)


def collect_pngs(root):
    root=Path(root)
    names={entry.name for entry in root.iterdir()}
    if names!=PNG_NAMES:raise RuntimeError('EXACT_EIGHT_QUALITY_PNGS_REQUIRED')
    records=[];total=0
    for name in sorted(names):
        path=root/name;before=path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or not 33<=before.st_size<=MAX_PNG_BYTES):
            raise RuntimeError('QUALITY_PNG_UNSAFE_OR_TOO_LARGE')
        raw=path.read_bytes();after=path.lstat()
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise RuntimeError('QUALITY_PNG_CHANGED_DURING_READ')
        if raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR' or struct.unpack('>II',raw[16:24])!=(1080,1920):
            raise RuntimeError('QUALITY_PNG_DIMENSIONS_REQUIRED')
        total+=len(raw);records.append({'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':1080,'height':1920})
    if total>MAX_PNG_TOTAL:raise RuntimeError('QUALITY_PNG_TOTAL_SIZE_LIMIT')
    return records



def validate_png_report(report,records):
    stated=report.get('files')
    if (not isinstance(stated,list) or len(stated)!=8 or len(records)!=8
        or any(not isinstance(item,dict) or item.get('scope')!='CPU_SW_NOT_NVIDIA' for item in stated)):
        raise RuntimeError('ACTUAL_SOFTWARE_PNG_BINDING_REQUIRED')
    keys=('file','bytes','sha256','width','height')
    summarized=sorted(({key:item.get(key) for key in keys} for item in stated),key=lambda item:str(item['file']))
    if summarized!=records:raise RuntimeError('ACTUAL_SOFTWARE_PNG_HASH_MISMATCH')


def software_probe(image,*,context=None,phase):
    output=Path(tempfile.mkdtemp(prefix='quality-software-png-',dir=os.environ['RUNNER_TEMP']));output.chmod(0o777)
    command=container(context=context,evidence=output)+['--entrypoint=/usr/bin/python3',image,'-B','-c',
        uid_code("import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','"+DEST+"/software_probe.mjs']).returncode)")]
    result=subprocess.run(command,text=True,capture_output=True,check=False,timeout=900)
    try:report=json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):report=None
    value=state();value[phase]={'exitCode':result.returncode,'report':report,'stdout':safe_log(result.stdout),
        'stderr':safe_log(result.stderr),'scope':'ACTUAL_CPU_SWIFTSHADER_QUALITY_AB_NOT_NVIDIA','gpuExecuted':False};save(value)
    if (result.returncode or not isinstance(report,dict) or report.get('status')!='PASS'
        or report.get('schema')!='QUALITY_ACTUAL_SOFTWARE_PROBE_V1'
        or report.get('softwareWebGLDrawExecuted') is not True
        or report.get('testOnly') is not True or report.get('physicalNvidiaExecuted') is not False
        or report.get('gpuRenderingVerified') is not False
        or any(report.get(key) is not True for key in ('actualShaderCompile','actualQualityABPixelsDiffer',
                'cameraAndGeometryEqual','originalSourcesUnchanged'))):
        raise RuntimeError('ACTUAL_QUALITY_SOFTWARE_AB_PROBE_REQUIRED')
    records=collect_pngs(output);validate_png_report(report,records)
    value=state();value[phase]['pngs']=records;value[phase]['pngRoot']=str(output);save(value)
    return report


def test():
    helpers().require_space()
    prior._record_case('new-ci-safety',[sys.executable,'-B','-m','unittest','discover','-s',str(HERE/'tests'),'-p','test_ci.py','-v'],scope='NEW_CI_ONLY')
    run(['docker','pull',BASE],timeout=900)
    source=test_context();common=container(context=source)
    python=sorted(path.name for path in (HERE/'tests').glob('test_*.py') if path.name!='test_ci.py')
    node=sorted(path.name for path in (HERE/'tests').glob('test_*.mjs'))
    if not python or not node:raise RuntimeError('NEW_FOCUSED_TESTS_REQUIRED')
    for name in python:
        code=("import unittest;s=unittest.defaultTestLoader.discover('"+DEST+"/tests',pattern='"+name+"');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        prior._record_case(name,common+['--entrypoint=/usr/bin/python3',BASE,'-B','-c',uid_code(code)],scope='NEW_QUALITY_CPU_TESTS_ONLY')
    for name in node:
        code="import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','--test','--test-isolation=none','"+DEST+"/tests/"+name+"']).returncode)"
        prior._record_case(name,common+['--entrypoint=/usr/bin/python3',BASE,'-B','-c',uid_code(code)],scope='NEW_QUALITY_JS_CPU_TESTS_ONLY')
    software_probe(BASE,context=source,phase='softwareProbeBeforeBuild')
    value=state();value['focusedTests']['status']='PASS';save(value)


def stage():
    value=state()
    if value.get('focusedTests',{}).get('status')!='PASS' or value.get('softwareProbeBeforeBuild',{}).get('exitCode')!=0:
        raise RuntimeError('FOCUSED_AND_ACTUAL_SOFTWARE_AB_PASS_REQUIRED')
    output=Path(os.environ['RUNNER_TEMP'])/('quality-image-'+value['tag']);output.mkdir(mode=0o700)
    payload=output/'quality';payload.mkdir()
    for name in (*RUNTIME_FILES,*TEST_FILES):shutil.copyfile(HERE/name,payload/name)
    manifest=generate_manifest();(payload/'QUALITY_FILES.json').write_text(json.dumps(manifest,indent=2)+'\n')
    shutil.copyfile(HERE/'Dockerfile',output/'Dockerfile')
    value.update(context=str(output),qualityManifest=manifest,qualityManifestSha256=sha(payload/'QUALITY_FILES.json'),
        softwareProbeSha256=sha(payload/'software_probe.mjs'),testToolSha256={name:sha(payload/name) for name in TEST_FILES},
        dockerfileSha256=sha(output/'Dockerfile'));save(value)


def inspect_image(image):
    facts=json.loads(run(['docker','image','inspect',image]))[0];config=facts.get('Config',{});labels=config.get('Labels',{})
    expected={'org.opencontainers.image.revision':'2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.astra-activation.source-revision':'7c4a0b6b4b0074bd06428dc11224a65f7f8fae58',
        'world-engine.visual-quality.source-revision':os.environ['GITHUB_SHA'],
        'world-engine.visual-quality.parent-digest':PARENT_DIGEST}
    if facts.get('Os')!='linux' or facts.get('Architecture')!='amd64' or any(labels.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint')!=['/usr/bin/tini','-g','--','/usr/bin/python3','/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('APPROVED_ENTRYPOINT_CHANGED')
    if {part.partition('=')[0] for part in config.get('Env',[])} & {'GH_TOKEN','GITHUB_TOKEN','DOCKER_AUTH_CONFIG','GITHUB_AUTHORIZATION'}:
        raise RuntimeError('CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value=state();value['builderBeforeBuild']=helpers().require_space();save(value);context=Path(value['context'])
    if set(path.name for path in context.iterdir())!={'quality','Dockerfile'} or set(path.name for path in (context/'quality').iterdir())!={*RUNTIME_FILES,'QUALITY_FILES.json',*TEST_FILES}:
        raise RuntimeError('EXPLICIT_BUILD_CONTEXT_REQUIRED')
    subprocess.run(['docker','build','--platform=linux/amd64','--file',str(context/'Dockerfile'),
        '--label','world-engine.visual-quality.source-revision='+os.environ['GITHUB_SHA'],'--tag',value['image'],str(context)],check=True,timeout=600)
    facts=inspect_image(value['image']);value.update(imageBuilt=True,configDigest=facts['Id'],imageSizeBytes=facts['Size']);save(value)


def image_hashes(image):
    code="import sys,json;sys.path.insert(0,'"+DEST+"');import prepare_quality;print(json.dumps(prepare_quality.verify_extension(package_root='/opt/rtx-package',require_staged=True)))"
    report=json.loads(run(['docker','run','--rm','--network=none','--user=1000:1000','--entrypoint=/usr/bin/python3',image,'-B','-c',code]))
    expected=hashlib.sha256((json.dumps(generate_manifest(),indent=2)+'\n').encode()).hexdigest()
    if report.get('status')!='PASS' or report.get('manifestSha256')!=expected:raise RuntimeError('QUALITY_EXTENSION_HASH_MISMATCH')
    return report


def verify():
    value=state();value.update(originalSources=composed_image_check(value['image'],hashes_only=True),imageHashes=image_hashes(value['image']));save(value)
    software_probe(value['image'],phase='actualImageSoftwareProbe')
    outcomes=[]
    for action in ('inspect','status'):
        result=subprocess.run(['docker','run','--rm','--network=none','--user=1000:1000','--memory=2g','--pids-limit=128',
            '--tmpfs','/world-storage:rw,mode=1777','--entrypoint=/usr/bin/python3',value['image'],'-B',DEST+'/job_quality.py',action],
            text=True,capture_output=True,check=False,timeout=30)
        try:report=json.loads(result.stdout)
        except ValueError:raise RuntimeError('QUALITY_CLI_JSON_REQUIRED') from None
        if result.returncode or report.get('renderAllowed') is not False or (action=='inspect' and report.get('status')!='CLEAR') or (action=='status' and report.get('state')!='NOT_STARTED'):
            raise RuntimeError('QUALITY_READ_ONLY_CLI_MUST_NOT_START_RENDER')
        outcomes.append({'action':action,'exitCode':result.returncode,'report':report,'gpuExecuted':False})
    value=state();value['actualImageReadOnlyCLI']=outcomes;save(value)
    prior.secret_scan(value['image']);value=state();value['verification']='PASS';save(value)


def publish():configure_registry();controls.publish()


controls.inspect_image=inspect_image
controls.image_hashes=image_hashes


def pull():
    configure_registry();controls.pull();value=state();value['status']='VISUAL_QUALITY_IMAGE_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING';save(value)


def persist():
    value=state();outcomes=json.loads(os.environ.get('RESULT_STEP_OUTCOMES','{}'));value['stepOutcomes']=outcomes
    if value['status']=='IN_PROGRESS' or any(item=='failure' for item in outcomes.values()):value['status']='VISUAL_QUALITY_IMAGE_BLOCKED'
    directory=NAMESPACE+'/runs/'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    paths={directory+'/'+os.environ['RESULT_PHASE']+'.json':(json.dumps(value,indent=2)+'\n').encode()}
    if os.environ['RESULT_PHASE']=='build' and value.get('actualImageSoftwareProbe',{}).get('exitCode')==0:
        evidence=value['actualImageSoftwareProbe'];current=collect_pngs(evidence['pngRoot'])
        if current!=evidence.get('pngs'):raise RuntimeError('SOFTWARE_EVIDENCE_HASH_CHANGED')
        for item in current:paths[directory+'/software-png/'+item['file']]=(Path(evidence['pngRoot'])/item['file']).read_bytes()
    run(['git','fetch','--filter=blob:none','origin',BRANCH],cwd=REPO,timeout=180);run(['git','switch','--detach','FETCH_HEAD'],cwd=REPO)
    for relative,body in paths.items():
        target=REPO/relative
        if target.exists():raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    run(['git','config','user.name','github-actions[bot]'],cwd=REPO);run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=REPO)
    run(['git','add','--',*sorted(paths)],cwd=REPO)
    if run(['git','diff','--cached','--name-only'],cwd=REPO).splitlines()!=sorted(paths):raise RuntimeError('BOUNDED_EVIDENCE_ONLY_COMMIT_REQUIRED')
    run(['git','commit','-m','docs: persist visual quality '+os.environ['RESULT_PHASE']+' software evidence [skip ci]'],cwd=REPO)
    run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=REPO,timeout=180)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['preflight','guard','test','stage','build','verify','publish','pull','persist']);args=parser.parse_args()
    try:globals()[args.phase]()
    except Exception as error:
        code=str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}',code):code='VISUAL_QUALITY_CI_FAILED'
        value=state();value.update(status='VISUAL_QUALITY_IMAGE_BLOCKED',failedPhase=args.phase,reasonCode=code,errorType=type(error).__name__)
        if isinstance(error,subprocess.CalledProcessError):value['failedCommandExitCode']=error.returncode
        save(value);print(json.dumps({'status':value['status'],'phase':args.phase,'reasonCode':code}));raise SystemExit(1)
