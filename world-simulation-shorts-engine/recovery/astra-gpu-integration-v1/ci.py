#!/usr/bin/env python3
"""Free CPU validation of an INACTIVE upload extension; no image build or GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/astra-gpu-integration-v1'
WORKFLOW = '.github/workflows/astra-gpu-integration.yml'
BRANCH = 'development/astra-gpu-minimal-integration-20261016'
BASELINE = '5269521131059cacdd18de5110ee3aaae302b8b5'
PARENT = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5dc61e9ce0edfc175c4a38fa0a3f559e660761e604b65bb5edfb6704312610b7'
SCANNER_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
DEST = '/opt/rtx-package/repo/' + NAMESPACE


def command(args, *, timeout=180, **kwargs):
    return subprocess.run(args, check=False, text=True, capture_output=True, timeout=timeout, **kwargs)


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise RuntimeError('SUBCOMMAND_FAILED_' + str(result.returncode))
    return result.stdout


def state_path():
    return Path(os.environ['RUNNER_TEMP']) / ('astra-upload-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'] + '.json')


def state():
    return json.loads(state_path().read_text()) if state_path().exists() else {
        'schema': 'ASTRA_INACTIVE_UPLOAD_CI_V1', 'sourceCommit': os.environ['GITHUB_SHA'],
        'activeIntegration': 'BLOCKED_MISSING_PROTECTED_RUNTIME_HOOK',
        'parentImage': PARENT, 'newImageBuilt': False, 'newImagePushed': False,
        'gpuExecuted': False, 'gCubeDeployed': False, 'paidGPUExecuted': False,
        'oldImagesOrCacheDeleted': False, 'status': 'IN_PROGRESS'}


def save(value):
    path = state_path(); pending = path.with_suffix('.writing')
    pending.write_text(json.dumps(value, indent=2) + '\n'); pending.replace(path)


def preflight():
    if (os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
        or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
        or os.environ.get('ASTRA_REPOSITORY_PRIVATE') != 'false'
        or os.environ.get('ASTRA_RUNNER_LABEL') != 'ubuntu-24.04'
        or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH):
        raise RuntimeError('FREE_PUBLIC_STANDARD_RUNNER_REQUIRED')
    for name in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'):
        if re.fullmatch(r'[1-9][0-9]*', os.environ.get(name,'')) is None:
            raise RuntimeError('VALID_RUN_ID_REQUIRED')
    root = Path(json.loads(checked(['docker','info','--format','{{json .DockerRootDir}}'])))
    free = shutil.disk_usage(root).free
    if free < 20 * 1024**3:
        raise RuntimeError('TWENTY_GIB_FREE_REQUIRED_NO_CACHE_DELETION')
    changed = checked(['git','diff','--name-only',BASELINE,'HEAD'],cwd=REPO).splitlines()
    if any(not (name.startswith(NAMESPACE+'/') or name==WORKFLOW) for name in changed):
        raise RuntimeError('PROTECTED_SOURCE_CHANGE')
    if checked(['git','status','--porcelain'],cwd=REPO).strip():
        raise RuntimeError('CLEAN_CHECKOUT_REQUIRED')
    value=state(); value['preflight']={'freeStandardRunner':True,'freeBytes':free,'protectedChanges':0}; save(value)


def audit():
    result=command(['python3','-B',str(HERE/'check_integration.py'),'--repo-root',str(REPO)])
    report=json.loads(result.stdout)
    value=state(); value['connectionAudit']=report; value['connectionAuditExitCode']=result.returncode; save(value)
    if result.returncode: raise RuntimeError('INTEGRATION_AUDIT_FAILED')
    tests=command(['python3','-B','-m','unittest','discover','-s',str(HERE/'tests'),'-p','test_integration.py','-v'])
    value=state(); value['auditTests']={'exitCode':tests.returncode,'stdout':tests.stdout[-65536:],'stderr':tests.stderr[-65536:]}; save(value)
    if tests.returncode: raise RuntimeError('INTEGRATION_AUDIT_TESTS_FAILED')


def test():
    checked(['docker','pull',PARENT],timeout=900)
    common=['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--user=1000:1000','--memory=3g','--cpus=2',
        '--pids-limit=128','--restart=no','--tmpfs','/workspace:rw,mode=1777',
        '--tmpfs','/tmp:rw,mode=1777','--mount','type=bind,source='+str(HERE)+',target='+DEST+',readonly']
    verify="import json,subprocess,unittest; s=unittest.defaultTestLoader.discover('PLACEHOLDER/tests',pattern='test_upload_bundle.py'); r=unittest.TextTestRunner(verbosity=2).run(s); assert r.testsRun>0 and r.wasSuccessful() and not r.skipped"
    verify=verify.replace('PLACEHOLDER',DEST)
    python=command(common+['--entrypoint=/usr/bin/python3',PARENT,'-B','-c',verify],timeout=240)
    value=state(); value['pythonUploadTests']={'exitCode':python.returncode,'stdout':python.stdout[-65536:],'stderr':python.stderr[-65536:],'scope':'ONLY_NEW_UPLOAD_TESTS_CPU'}; save(value)
    if python.returncode: raise RuntimeError('UPLOAD_TESTS_FAILED')
    node=command(common+['--entrypoint=/usr/local/bin/node',PARENT,'--test','--test-isolation=none',DEST+'/tests/test_gpu_upload.mjs'],timeout=120)
    value=state(); value['nodeUploadTests']={'exitCode':node.returncode,'stdout':node.stdout[-65536:],'stderr':node.stderr[-65536:],'scope':'CPU_FAKE_WEBGL2_NOT_GPU'}; save(value)
    if node.returncode: raise RuntimeError('NODE_UPLOAD_CONTRACT_TESTS_FAILED')
    smoke=command(common+['--entrypoint=/usr/bin/python3',PARENT,'-B',DEST+'/verify_bridge.py'],timeout=240)
    value=state(); value['realSourceBridge']={'exitCode':smoke.returncode,'report':json.loads(smoke.stdout),'scope':'EXISTING_THREE_SOURCE_SMALL_WINDOW_CPU_PACKING_AND_JS_CROSSCHECK'}; save(value)
    if smoke.returncode: raise RuntimeError('REAL_SOURCE_BRIDGE_FAILED')
    value=state(); value['status']='INACTIVE_UPLOAD_CPU_VERIFIED_ACTIVE_PATH_BLOCKED'; save(value)


def scan():
    temp=Path(tempfile.mkdtemp(prefix='astra-new-code-scan-',dir=os.environ['RUNNER_TEMP']))
    snapshot=temp/'snapshot'; snapshot.mkdir()
    shutil.copytree(HERE,snapshot/'namespace',ignore=shutil.ignore_patterns('__pycache__','runs'))
    shutil.copyfile(REPO/WORKFLOW,snapshot/'workflow.yml')
    with urllib.request.urlopen('https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz',timeout=30) as response:
        body=response.read(32*1024**2+1)
    if len(body)>32*1024**2: raise RuntimeError('SCANNER_SIZE_LIMIT')
    archive=temp/'scanner.tar.gz'; archive.write_bytes(body)
    with tarfile.open(archive,'r:gz') as source:
        entry=source.getmember('gitleaks')
        if not entry.isfile() or entry.size>64*1024**2: raise RuntimeError('SCANNER_MEMBER_INVALID')
        data=source.extractfile(entry).read()
    if hashlib.sha256(data).hexdigest()!=SCANNER_SHA: raise RuntimeError('SCANNER_SHA_MISMATCH')
    binary=temp/'gitleaks'; binary.write_bytes(data); binary.chmod(0o700)
    config=temp/'config.toml'; config.write_text('[extend]\nuseDefault = true\n')
    ignore=temp/'ignore'; ignore.write_text(''); report=temp/'findings.json'
    result=command([str(binary),'dir',str(snapshot),'--config',str(config),'--gitleaks-ignore-path',str(ignore),'--ignore-gitleaks-allow','--redact=100','--report-format=json','--report-path',str(report),'--no-banner'])
    findings=json.loads(report.read_text()) if report.exists() else None
    value=state(); value['secretScan']={'status':'PASS' if result.returncode==0 and findings==[] else 'FAIL','findings':len(findings) if isinstance(findings,list) else None,'exitCode':result.returncode,'scannerSHA256':SCANNER_SHA}; save(value)
    if value['secretScan']['status']!='PASS': raise RuntimeError('SECRET_SCAN_FAILED')


def persist():
    value=state(); value['stepOutcomes']=json.loads(os.environ.get('ASTRA_STEP_OUTCOMES','{}'))
    if any(x=='failure' for x in value['stepOutcomes'].values()): value['status']='CPU_VALIDATION_FAILED_ACTIVE_PATH_BLOCKED'
    relative=NAMESPACE+'/runs/'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']+'/cpu.json'
    checked(['git','fetch','--filter=blob:none','origin',BRANCH],cwd=REPO)
    checked(['git','switch','--detach','FETCH_HEAD'],cwd=REPO)
    target=REPO/relative
    if target.exists(): raise RuntimeError('EVIDENCE_OVERWRITE_FORBIDDEN')
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(value,indent=2)+'\n')
    checked(['git','config','user.name','github-actions[bot]'],cwd=REPO)
    checked(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=REPO)
    checked(['git','add','--',relative],cwd=REPO)
    if checked(['git','diff','--cached','--name-only'],cwd=REPO).splitlines()!=[relative]: raise RuntimeError('REPORT_ONLY_COMMIT_REQUIRED')
    checked(['git','commit','-m','docs: save inactive ASTRA upload CPU evidence [skip ci]'],cwd=REPO)
    checked(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=REPO)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('phase',choices=['preflight','audit','test','scan','persist']); args=parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        value=state(); value.update(status='CPU_VALIDATION_FAILED_ACTIVE_PATH_BLOCKED',failedPhase=args.phase,errorType=type(error).__name__)
        reason=str(error)
        value['reasonCode']=reason if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}',reason) else 'CPU_VALIDATION_ERROR'
        save(value); print(json.dumps({'status':value['status'],'reasonCode':value['reasonCode']})); raise SystemExit(1)
