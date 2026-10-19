#!/usr/bin/env python3
"""Free CPU-only additive image build/push; no workload or render operation.

Registry verification, public/free runner admission, Secret Scan and token-on-
stdin publishing reuse the hash-pinned existing HTTPS CI helper. Only new,
manifested integration directories are copied to the immutable base image.
"""
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

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'universal-integration-v1'
FROZEN=HERE.parent/'studio-https-bootstrap-v1/ci_package.py'
if hashlib.sha256(FROZEN.read_bytes()).hexdigest()!='93f588a9f1df0763814d42c8842495fd7733dcd3bbb97304c16a264d4cc6b393':
 raise RuntimeError('COMPLETION_FROZEN_CI_CHANGED')
spec=importlib.util.spec_from_file_location('_completion_frozen_ci',FROZEN)
ci=importlib.util.module_from_spec(spec);spec.loader.exec_module(ci)
ci.HERE=HERE
ci.NAMESPACE='world-simulation-shorts-engine/recovery/universal-integration-completion-v2'
ci.WORKFLOW='.github/workflows/world-engine-universal-completion-v2.yml'
ci.BRANCH='development/universal-integration-completion-20261019'
ci.BASE_DIGEST='sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
ci.BASE=ci.IMAGE+'@'+ci.BASE_DIGEST
ENGINE_RECOVERY='/opt/rtx-package/repo/world-simulation-shorts-engine/recovery'
ci.DEST=ENGINE_RECOVERY+'/universal-integration-completion-v2'
PRIOR_DEST=ENGINE_RECOVERY+'/universal-integration-v1'
ci.TAG=re.compile(r'completion-v2-[a-f0-9]{7,12}-[1-9][0-9]*-[1-9][0-9]*\Z')
FIXTURE_COMMIT='61c7fc3a36cc987c3f88844aba98c57bb62fe22e'
FIXTURE_DEST='/opt/completion-fixture-payload'
FIXTURE_PREFIX='world-simulation-shorts-engine/recovery/'


def build_fixture_manifest():
 """Bind original fixture bytes to their saved Git commit, never regenerate data."""
 namespace=FIXTURE_PREFIX+'verified-front-data-v4-recovery/'
 profile=json.loads((ci.REPO/namespace/'FRONT_PROFILE.json').read_bytes())
 paths={namespace+name for name in ('VIDEO_PLAN_80S.json','FRONT_PROFILE.json','FRONT_FILES.json','PARENT_PLAN_80S.json')}
 paths.add(FIXTURE_PREFIX+'universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json')
 for front in profile['fronts']:
  name=front['sourceFile']
  if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts or not name.endswith('.geojson'):
   raise RuntimeError('COMPLETION_FIXTURE_SOURCE_REFERENCE_INVALID')
  paths.add(namespace+name)
 if len(paths)!=13:raise RuntimeError('COMPLETION_EXACT_FIXTURE_CLOSURE_REQUIRED')
 rows=[]
 for relative in sorted(paths):
  file=ci.REPO/relative
  if any(p.is_symlink() for p in (file,*file.parents)):
   raise RuntimeError('COMPLETION_ORIGINAL_FIXTURE_REQUIRED')
  result=subprocess.run(['git','cat-file','blob',FIXTURE_COMMIT+':'+relative],cwd=ci.REPO,capture_output=True,check=False)
  if result.returncode or not 0<len(result.stdout)<=4*1024**2:raise RuntimeError('COMPLETION_SAVED_FIXTURE_BYTES_REQUIRED')
  raw=result.stdout
  if file.exists() and (not file.is_file() or file.read_bytes()!=raw):
   raise RuntimeError('COMPLETION_SAVED_FIXTURE_BYTES_CHANGED')
  rows.append({'repoPath':relative,'target':'/opt/rtx-package/repo/'+relative,
   'sha256':hashlib.sha256(raw).hexdigest(),'sourceCommit':FIXTURE_COMMIT,'bytes':len(raw)})
 value={'schema':'WORLD_ENGINE_PACKAGED_FIXTURES_V1','sourceCommit':FIXTURE_COMMIT,'files':rows}
 (HERE/'PACKAGED_FIXTURES.json').write_text(json.dumps(value,indent=2)+'\n')
 return value


def location():
 root=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'world-engine-completion-v2-package'
 root.mkdir(mode=0o700,parents=True,exist_ok=True);return root
ci.location=location
_original_state=ci.state
def state():
 value=_original_state()
 value['schema']='WORLD_ENGINE_COMPLETION_IMAGE_CPU_V2'
 value['status']=value['status'].replace('STUDIO_HTTPS_CANDIDATE','COMPLETION_CANDIDATE')
 value.update(gpuExecuted=False,nvidiaHardwareVerified=False,paidWorkExecuted=False,gCubeDeployed=False)
 return value
ci.state=state


def _entries(root,name):
 path=root/name
 if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or not 0<path.stat().st_size<=4*1024**2:
  raise RuntimeError('COMPLETION_BOUNDED_MANIFEST_REQUIRED')
 value=json.loads(path.read_bytes());entries=value.get('files')
 if not isinstance(entries,dict) or not entries:raise RuntimeError('COMPLETION_EXPLICIT_FILES_REQUIRED')
 for relative,digest in entries.items():
  if (not isinstance(relative,str) or Path(relative).name!=relative or '\\' in relative or relative in {'.','..'}
      or not ci.HASH.fullmatch(str(digest))):raise RuntimeError('COMPLETION_PACKAGE_PATH_INVALID')
 return value,entries


def _copy_manifested(root,name,destination,extras=()):
 manifest,entries=_entries(root,name)
 # Only public immutable source enters this directory. Runtime UID1000 must
 # traverse the same payload during pre-build bind-mount verification.
 destination.mkdir(mode=0o755)
 for relative in sorted({*entries,name,*extras}):
  file=root/relative
  if (any(p.is_symlink() for p in (file,*file.parents)) or not file.is_file()
      or not 0<file.stat().st_size<=16*1024**2):raise RuntimeError('COMPLETION_REGULAR_SOURCE_REQUIRED')
  if relative in entries and ci.sha(file)!=entries[relative]:raise RuntimeError('COMPLETION_SOURCE_SHA_MISMATCH')
  shutil.copyfile(file,destination/relative)
 return manifest


def payload_context(*,root=HERE,prior=PRIOR,repo_root=None):
 context=Path(tempfile.mkdtemp(prefix='payload-',dir=location()))
 previous=_copy_manifested(prior,'INTEGRATION_FILES.json',context/'integration',('RUNTIME_SOURCE_MANIFEST.json',))
 completion=_copy_manifested(root,'COMPLETION_FILES.json',context/'completion')
 if completion.get('previousManifestSHA256')!=ci.sha(prior/'INTEGRATION_FILES.json'):
  raise RuntimeError('COMPLETION_PRIOR_MANIFEST_BINDING_CHANGED')
 if completion.get('baseOperatingImageDigest')!=ci.BASE_DIGEST or previous.get('baseOperatingImageDigest')!=ci.BASE_DIGEST:
  raise RuntimeError('COMPLETION_IMMUTABLE_BASE_CHANGED')
 required={'bootstrap.py','studio_entry.py','studio_controller.py','runtime_bridge.py','capture_runtime.mjs','package_manifest.py',
  'install_fixtures.py','PACKAGED_FIXTURES.json'}
 if not required<=set(completion['files']):raise RuntimeError('COMPLETION_CONNECTED_RUNTIME_REQUIRED')
 fixture_raw=(root/'PACKAGED_FIXTURES.json').read_bytes();fixture_manifest=json.loads(fixture_raw)
 if fixture_manifest.get('schema')!='WORLD_ENGINE_PACKAGED_FIXTURES_V1' or fixture_manifest.get('sourceCommit')!=FIXTURE_COMMIT:
  raise RuntimeError('COMPLETION_FIXTURE_MANIFEST_REQUIRED')
 fixture_root=context/'fixtures';fixture_root.mkdir(mode=0o755)
 (fixture_root/'PACKAGED_FIXTURES.json').write_bytes(fixture_raw)
 for row in fixture_manifest['files']:
  relative=row['repoPath'];path=Path(relative)
  if (not isinstance(relative,str) or path.is_absolute() or '..' in path.parts or '\\' in relative
      or not relative.startswith(FIXTURE_PREFIX) or not relative.endswith(('.json','.geojson'))
      or row['sourceCommit']!=FIXTURE_COMMIT or row['target']!='/opt/rtx-package/repo/'+relative):
   raise RuntimeError('COMPLETION_FIXTURE_PACKAGE_PATH_INVALID')
  source=Path(repo_root or ci.REPO)/path
  if any(p.is_symlink() for p in (source,*source.parents)):
   raise RuntimeError('COMPLETION_FIXTURE_PACKAGE_REGULAR_REQUIRED')
  if source.exists():
   if not source.is_file():raise RuntimeError('COMPLETION_FIXTURE_PACKAGE_REGULAR_REQUIRED')
   raw=source.read_bytes()
  else:
   saved=subprocess.run(['git','cat-file','blob',FIXTURE_COMMIT+':'+relative],cwd=Path(repo_root or ci.REPO),capture_output=True,check=False)
   if saved.returncode:raise RuntimeError('COMPLETION_FIXTURE_SAVED_BLOB_REQUIRED')
   raw=saved.stdout
  if hashlib.sha256(raw).hexdigest()!=row['sha256'] or len(raw)!=row['bytes']:
   raise RuntimeError('COMPLETION_FIXTURE_PACKAGE_SHA_MISMATCH')
  target=fixture_root/'repo'/path;target.parent.mkdir(mode=0o755,parents=True,exist_ok=True);target.write_bytes(raw)
 shutil.copyfile(root/'Dockerfile',context/'Dockerfile')
 return context


def preflight():
 value=ci.state();value['builder']=ci.require_free_runner()
 commit=os.environ.get('GITHUB_SHA','')
 if not ci.COMMIT.fullmatch(commit):raise RuntimeError('COMPLETION_SOURCE_COMMIT_REQUIRED')
 tag='completion-v2-'+commit[:10]+'-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
 if not ci.TAG.fullmatch(tag):raise RuntimeError('COMPLETION_UNIQUE_TAG_REQUIRED')
 value.update(tag=tag,image=ci.IMAGE+':'+tag);ci.save(value)


def container(image,*,context=None):
 args=['docker','run','--rm','--network=none','--user=0:0','--memory=6g','--cpus=2','--pids-limit=256',
  '--restart=no','--shm-size=2g','--tmpfs','/tmp:rw,mode=1777']
 if context:
  args+=['--mount','type=bind,source='+str(context/'integration')+',target='+PRIOR_DEST+',readonly',
   '--mount','type=bind,source='+str(context/'completion')+',target='+ci.DEST+',readonly',
   '--mount','type=bind,source='+str(context/'fixtures')+',target='+FIXTURE_DEST+',readonly']
 return args+['--entrypoint=/usr/bin/python3',image,'-B']


def fixture_install_code():
 return ("import importlib.util;"
  "s=importlib.util.spec_from_file_location('_completion_ci_fixture_install','"+ci.DEST+"/install_fixtures.py');"
  "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
  "m.install('"+FIXTURE_DEST+"');")


def source_code():
 return (fixture_install_code()+"import importlib.util,json,sys,os;os.setgroups([]);os.setgid(1000);os.setuid(1000);"
  "sys.path.insert(0,'/opt/world-engine-studio-https-proxy-fix');"
  "from manifest import verify_sources as frozen_verify;frozen=frozen_verify();"
  "p='"+ci.DEST+"/package_manifest.py';s=importlib.util.spec_from_file_location('_completion_ci_sources',p);"
  "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);new=m.verify_sources();"
  "print(json.dumps({'status':'PASS','completion':new,'frozen':frozen,'gpuExecuted':False}))")


def image_hashes(image,context=None):
 result=ci.run(container(image,context=context)+['-c',source_code()],timeout=180,check=False)
 if result.returncode:
  value=ci.state();value['sourceContainerFailure']={'exitCode':result.returncode,
   'stdout':ci.bounded(result.stdout),'stderr':ci.bounded(result.stderr),'gpuExecuted':False};ci.save(value)
  raise RuntimeError('COMPLETION_CONTAINER_SOURCE_VERIFICATION_FAILED')
 try:report=json.loads(result.stdout.strip().splitlines()[-1])
 except (ValueError,IndexError):raise RuntimeError('COMPLETION_CONTAINER_SOURCE_REPORT_REQUIRED') from None
 expected=ci.sha((context/'completion' if context else HERE)/'COMPLETION_FILES.json')
 if (report.get('status')!='PASS' or report.get('gpuExecuted') is not False
     or report.get('completion',{}).get('manifestSHA256')!=expected
     or report.get('frozen',{}).get('status')!='PASS'):
  raise RuntimeError('COMPLETION_CONTAINER_SOURCE_HASH_MISMATCH')
 return report
ci.image_hashes=image_hashes


def inspect_image(image):
 row=json.loads(ci.run(['docker','image','inspect',image]).stdout)[0];config=row.get('Config',{});labels=config.get('Labels',{})
 expected=['/usr/bin/tini','-g','--','/usr/bin/python3','-B',ci.DEST+'/bootstrap.py']
 if (row.get('Os')!='linux' or row.get('Architecture')!='amd64' or config.get('Entrypoint')!=expected
     or labels.get('world-engine.completion.parent-digest')!=ci.BASE_DIGEST
     or labels.get('world-engine.completion.source-revision')!=os.environ['GITHUB_SHA']):
  raise RuntimeError('COMPLETION_IMAGE_PROVENANCE_REQUIRED')
 if set(item.partition('=')[0] for item in config.get('Env',[]))&{
  'GH_TOKEN','GITHUB_TOKEN','GCUBE_ACCESS_TOKEN','GCUBE_API_TOKEN','WORLD_ENGINE_STUDIO_OWNER_CODE',
  'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON','DROPBOX_REFRESH_TOKEN','WORLD_ENGINE_BACKUP_KEY'}:
  raise RuntimeError('COMPLETION_IMAGE_SECRET_ENV_FORBIDDEN')
 if '8080/healthz' not in ' '.join(config.get('Healthcheck',{}).get('Test',[])):
  raise RuntimeError('COMPLETION_EXISTING_HEALTHCHECK_REQUIRED')
 return {'status':'PASS','configDigest':row['Id'],'sizeBytes':row['Size'],'entrypoint':expected,
  'platform':'linux/amd64','secretEnvironmentPresent':False,'gpuExecuted':False}
ci.inspect_image=inspect_image


def test():
 ci.require_free_runner()
 pulled=ci.run(['docker','pull',ci.BASE],timeout=900,check=False)
 if pulled.returncode:
  value=ci.state();value['baseImagePullFailure']={'exitCode':pulled.returncode,
   'stdout':ci.bounded(pulled.stdout),'stderr':ci.bounded(pulled.stderr),'gpuExecuted':False};ci.save(value)
  raise RuntimeError('COMPLETION_BASE_IMAGE_PULL_FAILED')
 context=payload_context();value=ci.state();value['testContext']=str(context);ci.save(value)
 report=image_hashes(ci.BASE,context)
 # Exercise the actual inherited startup boundary. No owner code is created,
 # no secret is injected, and process spawning is explicitly denied by fixture.
 code=(fixture_install_code()+"import importlib.util,os,json;from unittest.mock import patch;"
  "os.environ['WORLD_ENGINE_STUDIO_STATE_ROOT']='/tmp/completion-owner-negative';"
  "os.environ.pop('WORLD_ENGINE_STUDIO_OWNER_CODE',None);"
  "s=importlib.util.spec_from_file_location('_completion_negative_boot','"+ci.DEST+"/bootstrap.py');"
  "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
  "\ntry:\n with patch('subprocess.Popen',side_effect=AssertionError('NO_PROCESS_ALLOWED')): m.main([])"
  "\nexcept Exception as e:\n code=getattr(e,'code',None) or str(e);"
  "\n if code != 'STUDIO_OWNER_CONFIGURATION_REQUIRED': raise"
  "\n print(json.dumps({'status':'PASS','errorCode':code,'renderStarted':False,'gpuExecuted':False}))"
  "\nelse: raise RuntimeError('COMPLETION_MISSING_OWNER_DID_NOT_FAIL')")
 result=ci.record('actual-container-owner-fail-closed',container(ci.BASE,context=context)+['-c',code],timeout=180)
 proof=json.loads(result.stdout.strip().splitlines()[-1]);value=ci.state()
 value.update(testsStatus='PASS',testSourceHashes=report,ownerNegativeProof=proof);ci.save(value)


def stage():
 value=ci.state()
 if value.get('testsStatus')!='PASS':raise RuntimeError('COMPLETION_CPU_CONTAINER_TESTS_REQUIRED')
 context=payload_context();old=Path(value['testContext'])
 for directory,manifest in [('completion','COMPLETION_FILES.json'),('integration','INTEGRATION_FILES.json')]:
  if (context/directory/manifest).read_bytes()!=(old/directory/manifest).read_bytes():
   raise RuntimeError('COMPLETION_TESTED_CONTEXT_CHANGED')
 value.update(context=str(context),extensionManifestSha256=ci.sha(context/'completion/COMPLETION_FILES.json'),
  priorManifestSha256=ci.sha(context/'integration/INTEGRATION_FILES.json'),dockerfileSha256=ci.sha(context/'Dockerfile'));ci.save(value)


def build():
 value=ci.state();ci.require_free_runner()
 if value.get('testsStatus')!='PASS' or not value.get('context'):raise RuntimeError('COMPLETION_TESTED_PAYLOAD_REQUIRED')
 context=Path(value['context'])
 if ci.sha(context/'completion/COMPLETION_FILES.json')!=value['extensionManifestSha256'] or ci.sha(context/'Dockerfile')!=value['dockerfileSha256']:
  raise RuntimeError('COMPLETION_FROZEN_CONTEXT_CHANGED')
 result=ci.run(['docker','build','--platform=linux/amd64','--network=none','--file',str(context/'Dockerfile'),
  '--label','world-engine.completion.source-revision='+os.environ['GITHUB_SHA'],'--tag',value['image'],str(context)],timeout=900,check=False)
 value['dockerBuild']={'exitCode':result.returncode,'stdout':ci.bounded(result.stdout),'stderr':ci.bounded(result.stderr)};ci.save(value)
 if result.returncode:raise RuntimeError('COMPLETION_IMAGE_BUILD_FAILED')
 value=ci.state();value.update(imageBuilt=True,imageConfiguration=inspect_image(value['image']));ci.save(value)


def verify():
 value=ci.state()
 if not value.get('imageBuilt'):raise RuntimeError('COMPLETION_BUILT_IMAGE_REQUIRED')
 hashes=image_hashes(value['image']);scan=ci.secret_scan()
 value=ci.state();value.update(imageHashes=hashes,secretScan=scan,verification='PASS');ci.save(value)


def pull():
 ci.pull()
 value=ci.state()
 if (value.get('pullVerified') is not True or value.get('imageHashes',{}).get('status')!='PASS'
     or value.get('imageConfiguration',{}).get('status')!='PASS'):
  raise RuntimeError('COMPLETION_INDEPENDENT_PULL_PROOF_REQUIRED')
 value['imageProof']={'schema':'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1',
  'imageDigest':value['imageDigest'],'sourceManifestSHA256':ci.sha(HERE/'COMPLETION_FILES.json'),
  'sourceCommit':os.environ['GITHUB_SHA'],'independentPullVerified':True,'sourceHashesVerified':True,
  'baseDigest':ci.BASE_DIGEST,'result':'PASS'}
 ci.save(value)


def persist():
 value=ci.state();value['stepOutcomes']=json.loads(os.environ.get('RESULT_STEP_OUTCOMES','{}'))
 if 'failure' in value['stepOutcomes'].values():value['status']='COMPLETION_CANDIDATE_BLOCKED'
 for name in ('context','testContext'):value.pop(name,None)
 phase=os.environ.get('RESULT_PHASE');run_id=os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
 if phase not in {'build','pull'} or not re.fullmatch('[1-9][0-9]*-[1-9][0-9]*',run_id):
  raise RuntimeError('COMPLETION_BOUNDED_RESULT_REQUIRED')
 relative=Path(ci.NAMESPACE)/'runs'/run_id;raw=(json.dumps(value,indent=2)+'\n').encode()
 if len(raw)>4*1024**2 or ci.SENSITIVE.search(raw.decode()):raise RuntimeError('COMPLETION_SAFE_EVIDENCE_REQUIRED')
 artifacts={str(relative/(phase+'.json')):raw,
  str(relative/(phase+'.SHA256SUMS')):(hashlib.sha256(raw).hexdigest()+'  '+phase+'.json\n').encode()}
 if phase=='pull' and value.get('pullVerified') is True and value.get('imageProof',{}).get('result')=='PASS':
  proof_raw=(json.dumps(value['imageProof'],indent=2)+'\n').encode()
  artifacts[str(relative/'IMAGE_PROOF.json')]=proof_raw
  artifacts[str(relative/'IMAGE_PROOF.SHA256SUMS')]=(hashlib.sha256(proof_raw).hexdigest()+'  IMAGE_PROOF.json\n').encode()
 ci.run(['git','fetch','--filter=blob:none','origin',ci.BRANCH],timeout=180);ci.run(['git','switch','--detach','FETCH_HEAD'])
 for name,data in artifacts.items():
  destination=ci.REPO/name
  if destination.exists():raise RuntimeError('COMPLETION_EXISTING_EVIDENCE_PRESERVED')
  destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
 ci.run(['git','config','user.name','github-actions[bot]']);ci.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'])
 ci.run(['git','add','--',*sorted(artifacts)])
 if sorted(ci.run(['git','diff','--cached','--name-only']).stdout.splitlines())!=sorted(artifacts):raise RuntimeError('COMPLETION_BOUNDED_EVIDENCE_COMMIT_REQUIRED')
 ci.run(['git','diff','--cached','--check']);ci.run(['git','commit','-m','docs(completion): persist '+phase+' CPU image evidence [skip ci]'])
 ci.run(['git','push','origin','HEAD:refs/heads/'+ci.BRANCH],timeout=180)


def main(argv=None):
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('preflight','guard','test','stage','build','verify','publish','pull','persist'))
 phase=parser.parse_args(argv).phase
 try:
  operation=globals().get(phase) or getattr(ci,phase);operation();return 0
 except Exception as error:
  code=str(error)
  if not re.fullmatch('[A-Z][A-Z0-9_]{0,95}',code):code='COMPLETION_CI_FAILED'
  value=ci.state();value.update(status='COMPLETION_CANDIDATE_BLOCKED',failedPhase=phase,reasonCode=code,errorType=type(error).__name__);ci.save(value)
  print(json.dumps({'status':value['status'],'phase':phase,'reasonCode':code}));return 1
if __name__=='__main__':raise SystemExit(main())
