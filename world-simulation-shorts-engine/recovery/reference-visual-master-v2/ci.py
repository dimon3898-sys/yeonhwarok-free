#!/usr/bin/env python3
"""Thin free CI for explicit reference V2 lane; frozen parent manifests are inputs."""
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

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
NAMESPACE='world-simulation-shorts-engine/recovery/reference-visual-master-v2'
WORKFLOW='.github/workflows/reference-visual-master-v2.yml'
BRANCH='development/reference-visual-master-v2-20261016'
BASELINE='233bca75f38005c314da8f8af3b33c240f7fb89f'
IMAGE='ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST='sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae'
BASE=IMAGE+'@'+PARENT_DIGEST
DEST='/opt/rtx-package/repo/'+NAMESPACE
PARENT_NAMESPACE='world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1'
PARENT_MANIFEST_SHA='cd025141c88f1d5fa196fc58c3026565ceb386b09926f7036638d78ecb3385ff'
BASELINE_META_SHA='71ef50f4a2a4532c7209e17e1484aa30a42143bcb6e02012f74c604dd2441d5a'
TAG_PATTERN=re.compile(r'reference-v2-233bca7-[1-9][0-9]*-[1-9][0-9]*',re.ASCII)
RUNTIME_FILES=('camera-profile.mjs','unit-size-profile.mjs','native_domain_coverage.mjs','coverage_outer_glow.mjs',
    'frontier_profile_core.mjs','frontier_ref2.mjs','gain_style_core.mjs','gain_territory.mjs',
    'reference_source_material.mjs','source_grade_core.mjs','source_grade_pass.mjs','ref2_profiles.mjs',
    'ref2_runtime.mjs','ref2_adapter.mjs','serve_ref2.py','job_ref2.py','prepare_ref2.py','launch_ref2.py',
    'capture_ref2.mjs','PROTECTED_BASELINE.json')
TEST_FILES=('software_probe_ref2.mjs','gain_ab_probe.mjs','source_grade_ab_probe.mjs','build_source_probe.py','outer_glow_ab_probe.mjs')
PNG_NAMES=frozenset({'A_075.png','B_075.png','C_075.png','D_075.png','E_075.png',
    'F_000.png','F_038.png','F_075.png','F_112.png','F_149.png'})
# Only an isolated imported CI object is configured. No protected on-disk helper,
# source receipt, renderer API, old claim or parent manifest is rewritten.
spec=importlib.util.spec_from_file_location('_ref2_quality_ci',HERE.parent/'visual-quality-upgrade-v1/ci.py')
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
controls=parent.controls
for name,value in {'HERE':HERE,'REPO':REPO,'NAMESPACE':NAMESPACE,'WORKFLOW':WORKFLOW,'BRANCH':BRANCH,
    'BASELINE':BASELINE,'PARENT_DIGEST':PARENT_DIGEST,'BASE':BASE,'PATCHES':{}}.items():setattr(controls,name,value)
run=controls.run
save=controls.save
state_path=controls.state_path
sha=controls.sha
safe_log=controls.safe_log


def state():
    if state_path().exists():return json.loads(state_path().read_text())
    return {'schema':'WORLD_ENGINE_REFERENCE_VISUAL_IMAGE_V2','status':'IN_PROGRESS','ciCommit':os.environ.get('GITHUB_SHA'),
        'parentImage':BASE,'gpuExecuted':False,'gCubeDeployed':False,'paidWorkExecuted':False,
        'oldRendererModified':False,'finalModified':False,'oldImagesDeleted':False,
        'imageBuilt':False,'imagePushed':False,'pullVerified':False,'videoQualityApproved':False,
        'rawReferencePublished':False}


def helpers():
    native=parent.prior._parent_helpers()
    return SimpleNamespace(require_space=native.require_space,login=native.login,check_image=composed_image_check)


controls.state=state
controls.helpers=helpers
# The proven inventory walker and scanner are reused; only additive expected
# hashes and namespace change. The parent's generate_manifest is never called.
for module in (parent,parent.prior):
    for name,value in {'HERE':HERE,'REPO':REPO,'NAMESPACE':NAMESPACE,'WORKFLOW':WORKFLOW,'DEST':DEST,
                       'state':state,'save':save}.items():setattr(module,name,value)
parent.PNG_NAMES=PNG_NAMES
parent.MAX_PNG_TOTAL=60*1024**2


def configure_registry():
    module=parent.configure_registry();module.TAG_PATTERN=TAG_PATTERN;return module


def preflight():
    controls.preflight();value=state()
    value['tag']='reference-v2-233bca7-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    value['image']=IMAGE+':'+value['tag'];save(value)


def guard():configure_registry();controls.guard()


def source_commit():
    value=os.environ.get('GITHUB_SHA') or run(['git','rev-parse','HEAD'],cwd=REPO).strip()
    if not re.fullmatch('[0-9a-f]{40}',value):raise RuntimeError('SOURCE_COMMIT_REQUIRED')
    return value


def parent_closure():
    target=REPO/PARENT_NAMESPACE/'QUALITY_FILES.json'
    if sha(target)!=PARENT_MANIFEST_SHA:raise RuntimeError('FROZEN_QUALITY_PARENT_MANIFEST_REQUIRED')
    manifest=json.loads(target.read_text())
    sources={PARENT_NAMESPACE+'/'+name:digest for name,digest in manifest['files'].items()}
    sources.update(manifest['repoDependencies'])
    sources[PARENT_NAMESPACE+'/QUALITY_FILES.json']=PARENT_MANIFEST_SHA
    sources.update({PARENT_NAMESPACE+'/'+name:digest for name,digest in manifest['testFiles'].items()})
    if len(sources)!=31:raise RuntimeError('EXACT_THIRTY_ONE_PARENT_ADDITIONS_REQUIRED')
    for relative,digest in sources.items():
        if sha(REPO/relative)!=digest:raise RuntimeError('FROZEN_PARENT_SOURCE_CHANGED')
    return manifest,sources


def generate_manifest():
    manifest,dependencies=parent_closure()
    if sha(HERE/'PROTECTED_BASELINE.json')!=BASELINE_META_SHA:raise RuntimeError('PROTECTED_BASELINE_METADATA_CHANGED')
    for name in (*RUNTIME_FILES,*TEST_FILES):
        file=HERE/name
        if file.is_symlink() or not file.is_file():raise RuntimeError('EXPLICIT_REFERENCE_SOURCE_REQUIRED')
    return {'schema':'WORLD_ENGINE_REFERENCE_VISUAL_FILES_V2','profileId':'REFERENCE_VISUAL_MASTER_V2',
        'family':'REFERENCE_VISUAL_MASTER_V2',
        'sourceCommit':source_commit(),'baselineCommit':BASELINE,'parentImage':BASE,
        'parentQualityManifestSha256':PARENT_MANIFEST_SHA,
        'files':{name:sha(HERE/name) for name in RUNTIME_FILES},'repoDependencies':dependencies,
        'testFiles':{name:sha(HERE/name) for name in TEST_FILES},
        'inheritedFiles':manifest.get('inheritedFiles',[])}


def extensions():
    manifest=generate_manifest()
    output={'repo/'+relative:digest for relative,digest in manifest['repoDependencies'].items()}
    output.update({'repo/'+NAMESPACE+'/'+name:digest for name,digest in manifest['files'].items()})
    output.update({'repo/'+NAMESPACE+'/'+name:digest for name,digest in manifest['testFiles'].items()})
    output['repo/'+NAMESPACE+'/REFERENCE_FILES.json']=hashlib.sha256((json.dumps(manifest,indent=2)+'\n').encode()).hexdigest()
    return output


parent.extensions=extensions
composed_image_check=parent.composed_image_check


def test_context():
    folder=Path(tempfile.mkdtemp(prefix='ref2-source-context-',dir=os.environ['RUNNER_TEMP']))
    shutil.copytree(HERE,folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('runs','public-review','__pycache__'))
    (folder/'REFERENCE_FILES.json').write_text(json.dumps(generate_manifest(),indent=2)+'\n')
    return folder


def container(*,context=None,evidence=None):
    args=['docker','run','--rm','--network=none','--user=0:0','--memory=8g','--cpus=2','--pids-limit=512',
        '--restart=no','--shm-size=2g','--tmpfs','/workspace:rw,mode=1777','--tmpfs','/tmp:rw,mode=1777']
    if context is not None:args+=['--mount','type=bind,source='+str(context)+',target='+DEST+',readonly']
    if evidence is not None:args+=['--mount','type=bind,source='+str(evidence)+',target=/workspace/reference-evidence',
        '--env','WORLD_ENGINE_REFERENCE_EVIDENCE_DIR=/workspace/reference-evidence']
    return args


def uid_code(body):
    return ("import os,pathlib;p=pathlib.Path('/var/lib/world-engine-private/engine/job-reference-v2-v1');"
        "p.mkdir(mode=0o700,exist_ok=True);os.chown(p,1000,1000);os.setgroups([]);os.setgid(1000);os.setuid(1000);"+body)


def collect_pngs(folder):
    try:return parent.collect_pngs(folder)
    except RuntimeError as error:
        if str(error)=='EXACT_EIGHT_QUALITY_PNGS_REQUIRED':raise RuntimeError('EXACT_TEN_REFERENCE_PNGS_REQUIRED') from None
        raise


def validate_png_report(report,records):
    rows=report.get('files');keys=('file','bytes','sha256','width','height')
    if (not isinstance(rows,list) or len(rows)!=10 or len(records)!=10
        or any(not isinstance(row,dict) or row.get('scope')!='CPU_SW_NOT_NVIDIA' for row in rows)):
        raise RuntimeError('ACTUAL_REFERENCE_PNG_BINDING_REQUIRED')
    projected=sorted(({key:row.get(key) for key in keys} for row in rows),key=lambda row:str(row['file']))
    if projected!=records:raise RuntimeError('ACTUAL_REFERENCE_PNG_SHA_MISMATCH')


def software_probe(image,*,context=None,phase):
    output=Path(tempfile.mkdtemp(prefix='ref2-software-png-',dir=os.environ['RUNNER_TEMP']));output.chmod(0o777)
    code="import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','"+DEST+"/software_probe_ref2.mjs']).returncode)"
    result=subprocess.run(container(context=context,evidence=output)+['--entrypoint=/usr/bin/python3',image,'-B','-c',uid_code(code)],
        text=True,capture_output=True,check=False,timeout=1200)
    try:report=json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):report=None
    value=state();value[phase]={'exitCode':result.returncode,'report':report,'stdout':safe_log(result.stdout),
        'stderr':safe_log(result.stderr),'scope':'ACTUAL_CPU_SWIFTSHADER_REF2_AB_NOT_NVIDIA','gpuExecuted':False};save(value)
    if (result.returncode or not isinstance(report,dict) or report.get('status')!='PASS'
        or report.get('schema')!='REFERENCE_V2_ACTUAL_SOFTWARE_PROBE_V1'
        or report.get('testOnly') is not True or report.get('physicalNvidiaExecuted') is not False
        or report.get('gpuRenderingVerified') is not False
        or any(report.get(key) is not True for key in ('actualShaderCompile','softwareWebGLDrawExecuted',
            'actualReferenceABPixelsDiffer','parentSoftwareBaselineBitExact','originalSourcesUnchanged'))):
        raise RuntimeError('ACTUAL_REFERENCE_SOFTWARE_AB_REQUIRED')
    records=collect_pngs(output);validate_png_report(report,records)
    value=state();value[phase].update(pngs=records,pngRoot=str(output));save(value);return report


def test():
    helpers().require_space()
    parent.prior._record_case('ref2-ci-safety',[sys.executable,'-B','-m','unittest','discover','-s',str(HERE/'tests'),'-p','test_ci.py','-v'],scope='NEW_REF2_CI_ONLY')
    run(['docker','pull',BASE],timeout=900);source=test_context();common=container(context=source)
    for pattern in sorted(path.name for path in (HERE/'tests').glob('test_*.py') if path.name!='test_ci.py'):
        code=("import unittest;s=unittest.defaultTestLoader.discover('"+DEST+"/tests',pattern='"+pattern+"');"
            "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(0 if r.testsRun>0 and r.wasSuccessful() and not r.skipped else 1)")
        parent.prior._record_case(pattern,common+['--entrypoint=/usr/bin/python3',BASE,'-B','-c',uid_code(code)],scope='NEW_REF2_CPU_ONLY')
    for pattern in sorted(path.name for path in (HERE/'tests').glob('test_*.mjs')):
        code="import subprocess;raise SystemExit(subprocess.run(['/usr/local/bin/node','--test','--test-isolation=none','"+DEST+"/tests/"+pattern+"']).returncode)"
        parent.prior._record_case(pattern,common+['--entrypoint=/usr/bin/python3',BASE,'-B','-c',uid_code(code)],scope='NEW_REF2_JS_CPU_ONLY')
    software_probe(BASE,context=source,phase='softwareProbeBeforeBuild')
    value=state();value['focusedTests']['status']='PASS';save(value)


def stage():
    value=state()
    if value.get('focusedTests',{}).get('status')!='PASS' or value.get('softwareProbeBeforeBuild',{}).get('exitCode')!=0:
        raise RuntimeError('FOCUSED_AND_ACTUAL_REF2_AB_PASS_REQUIRED')
    folder=Path(os.environ['RUNNER_TEMP'])/('reference-image-'+value['tag']);folder.mkdir(mode=0o700)
    payload=folder/'reference';payload.mkdir()
    for name in (*RUNTIME_FILES,*TEST_FILES):shutil.copyfile(HERE/name,payload/name)
    manifest=generate_manifest();(payload/'REFERENCE_FILES.json').write_text(json.dumps(manifest,indent=2)+'\n')
    shutil.copyfile(HERE/'Dockerfile',folder/'Dockerfile')
    value.update(context=str(folder),referenceManifest=manifest,referenceManifestSha256=sha(payload/'REFERENCE_FILES.json'),
        dockerfileSha256=sha(folder/'Dockerfile'));save(value)


def inspect_image(image):
    facts=json.loads(run(['docker','image','inspect',image]))[0];config=facts.get('Config',{});labels=config.get('Labels',{})
    wanted={'org.opencontainers.image.revision':'2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
        'world-engine.visual-quality.source-revision':'17393dd6a017a06de542a1484686cd8f8f598e60',
        'world-engine.reference-v2.source-revision':os.environ['GITHUB_SHA'],'world-engine.reference-v2.parent-digest':PARENT_DIGEST}
    if facts.get('Os')!='linux' or facts.get('Architecture')!='amd64' or any(labels.get(key)!=value for key,value in wanted.items()):
        raise RuntimeError('REFERENCE_IMAGE_PROVENANCE_MISMATCH')
    if config.get('Entrypoint')!=['/usr/bin/tini','-g','--','/usr/bin/python3','/opt/world-engine-storage-fix/launch.py']:
        raise RuntimeError('PARENT_ENTRYPOINT_CHANGED')
    if {row.partition('=')[0] for row in config.get('Env',[])}&{'GH_TOKEN','GITHUB_TOKEN','DOCKER_AUTH_CONFIG','GITHUB_AUTHORIZATION'}:
        raise RuntimeError('CREDENTIAL_ENV_IN_IMAGE')
    return facts


def build():
    value=state();value['builderBeforeBuild']=helpers().require_space();save(value);folder=Path(value['context'])
    if set(row.name for row in folder.iterdir())!={'reference','Dockerfile'} or set(row.name for row in (folder/'reference').iterdir())!={*RUNTIME_FILES,*TEST_FILES,'REFERENCE_FILES.json'}:
        raise RuntimeError('EXPLICIT_REFERENCE_BUILD_CONTEXT_REQUIRED')
    subprocess.run(['docker','build','--platform=linux/amd64','--file',str(folder/'Dockerfile'),
        '--label','world-engine.reference-v2.source-revision='+os.environ['GITHUB_SHA'],'--tag',value['image'],str(folder)],check=True,timeout=600)
    facts=inspect_image(value['image']);value.update(imageBuilt=True,configDigest=facts['Id'],imageSizeBytes=facts['Size']);save(value)


def image_hashes(image):
    code="import sys,json;sys.path.insert(0,'"+DEST+"');import prepare_ref2;print(json.dumps(prepare_ref2.verify_extension(package_root='/opt/rtx-package',require_staged=True)))"
    report=json.loads(run(['docker','run','--rm','--network=none','--user=1000:1000','--entrypoint=/usr/bin/python3',image,'-B','-c',code]))
    expected=hashlib.sha256((json.dumps(generate_manifest(),indent=2)+'\n').encode()).hexdigest()
    if report.get('status')!='PASS' or report.get('manifestSha256')!=expected:raise RuntimeError('REFERENCE_EXTENSION_HASH_MISMATCH')
    return report


def verify():
    value=state();value.update(originalSources=composed_image_check(value['image'],hashes_only=True),imageHashes=image_hashes(value['image']));save(value)
    software_probe(value['image'],phase='actualImageSoftwareProbe');results=[]
    for action in ('inspect','status'):
        result=subprocess.run(['docker','run','--rm','--network=none','--user=1000:1000','--memory=2g','--pids-limit=128',
            '--tmpfs','/world-storage:rw,mode=1777','--entrypoint=/usr/bin/python3',value['image'],'-B',DEST+'/job_ref2.py',action],
            text=True,capture_output=True,check=False,timeout=30)
        attempt=state();attempt.setdefault('readOnlyCliAttempts',[]).append({'action':action,
            'exitCode':result.returncode,'stdout':safe_log(result.stdout),'stderr':safe_log(result.stderr)});save(attempt)
        try:body=json.loads(result.stdout)
        except ValueError:raise RuntimeError('REF2_CLI_JSON_REQUIRED') from None
        if result.returncode or body.get('renderAllowed') is not False or (action=='inspect' and body.get('status')!='CLEAR') or (action=='status' and body.get('state')!='NOT_STARTED'):
            raise RuntimeError('REF2_READ_ONLY_CLI_MUST_NOT_START_RENDER')
        results.append({'action':action,'exitCode':result.returncode,'report':body,'gpuExecuted':False})
    value=state();value['actualImageReadOnlyCLI']=results;save(value)
    parent.prior.secret_scan(value['image']);value=state();value['verification']='PASS';save(value)


def publish():configure_registry();controls.publish()


controls.inspect_image=inspect_image
controls.image_hashes=image_hashes


def pull():
    configure_registry();controls.pull();value=state();value['status']='REFERENCE_V2_IMAGE_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING';save(value)


def persist():
    value=state();value['stepOutcomes']=json.loads(os.environ.get('RESULT_STEP_OUTCOMES','{}'))
    if value['status']=='IN_PROGRESS' or any(row=='failure' for row in value['stepOutcomes'].values()):value['status']='REFERENCE_V2_IMAGE_BLOCKED'
    folder=NAMESPACE+'/runs/'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    paths={folder+'/'+os.environ['RESULT_PHASE']+'.json':(json.dumps(value,indent=2)+'\n').encode()}
    if os.environ['RESULT_PHASE']=='build' and value.get('actualImageSoftwareProbe',{}).get('exitCode')==0:
        proof=value['actualImageSoftwareProbe'];records=collect_pngs(proof['pngRoot'])
        if records!=proof.get('pngs'):raise RuntimeError('REFERENCE_SOFTWARE_EVIDENCE_CHANGED')
        for row in records:paths[folder+'/public-review/'+row['file']]=(Path(proof['pngRoot'])/row['file']).read_bytes()
        paths[folder+'/public-review/SHA256SUMS']=''.join(row['sha256']+'  '+row['file']+'\n' for row in records).encode()
    run(['git','fetch','--filter=blob:none','origin',BRANCH],cwd=REPO,timeout=180);run(['git','switch','--detach','FETCH_HEAD'],cwd=REPO)
    for relative,body in paths.items():
        target=REPO/relative
        if target.exists():raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    run(['git','config','user.name','github-actions[bot]'],cwd=REPO);run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=REPO)
    run(['git','add','--',*sorted(paths)],cwd=REPO)
    if run(['git','diff','--cached','--name-only'],cwd=REPO).splitlines()!=sorted(paths):raise RuntimeError('BOUNDED_REFERENCE_EVIDENCE_ONLY_REQUIRED')
    run(['git','commit','-m','docs: persist reference V2 '+os.environ['RESULT_PHASE']+' software evidence [skip ci]'],cwd=REPO)
    run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=REPO,timeout=180)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['preflight','guard','test','stage','build','verify','publish','pull','persist']);args=parser.parse_args()
    try:globals()[args.phase]()
    except Exception as error:
        code=str(error)
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}',code):code='REFERENCE_CI_FAILED'
        value=state();value.update(status='REFERENCE_V2_IMAGE_BLOCKED',failedPhase=args.phase,reasonCode=code,errorType=type(error).__name__)
        if isinstance(error,subprocess.CalledProcessError):value['failedCommandExitCode']=error.returncode
        save(value);print(json.dumps({'status':value['status'],'phase':args.phase,'reasonCode':code}));raise SystemExit(1)
