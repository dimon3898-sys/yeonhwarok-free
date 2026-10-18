#!/usr/bin/env python3
"""Existing-workload, GET-only evidence and existing-SSH read-only cache scan.

Never register SSH, start/stop/update a workload, submit rendering, repair modes,
or publish raw API/SSH output. The official gateway credential stays in memory.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import sys
import tempfile
import time

PRIOR = Path(__file__).resolve().parent.parent / 'studio-auth-recovery-v2'
sys.path.insert(0, str(PRIOR))
import collector
import rest_evidence

WORKLOAD = '5373'
JOB = 'studio-bcd340f797498d7c9fea8181921f91b9'
ROOT_PREFIX = '/var/lib/world-engine-private/engine/'
DEFAULT_ROOTS = (
    ROOT_PREFIX + 'production-studio-mvp-v1/production',
    ROOT_PREFIX + 'production-studio-v1',
    ROOT_PREFIX + 'studio-mvp/production',
)
MAX_OUTPUT = 512 * 1024

# This fixed program has no network, subprocess, environment, imports from the
# deployed application, file writes, locks, cache.begin/lookup, or status calls.
# Even SceneCache.lookup creates a missing directory, so it is not reused here.
SCANNER = r'''
import hashlib,json,math,os,pathlib,re,stat,time
START=time.monotonic();HASH_BYTES=0
SHA=re.compile(r'[a-f0-9]{64}\Z');NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z')
class ScanError(Exception):pass
def deadline():
 if time.monotonic()-START>85:raise ScanError('SCAN_TIME_LIMIT')
def open_directory(path):
 p=pathlib.Path(path)
 if not p.is_absolute() or '..' in p.parts:raise ScanError('UNSAFE_PATH')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in p.parts[1:]:
   nextfd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nextfd
  return fd
 except BaseException:os.close(fd);raise
def read_file(path,*,private=True,limit=8*1024**2,collect=True):
 global HASH_BYTES
 deadline();p=pathlib.Path(path);parent=open_directory(p.parent)
 try:fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
 finally:os.close(parent)
 try:
  a=os.fstat(fd)
  if not stat.S_ISREG(a.st_mode) or not 0<a.st_size<=limit or a.st_nlink!=1:raise ScanError('UNSAFE_FILE')
  if private and (a.st_uid!=PRIVATE_UID or stat.S_IMODE(a.st_mode)&0o077):raise ScanError('PRIVATE_RECORD_REQUIRED')
  h=hashlib.sha256();body=[];count=0
  while True:
   deadline();part=os.read(fd,1024*1024)
   if not part:break
   count+=len(part);HASH_BYTES+=len(part)
   if count>a.st_size or HASH_BYTES>8*1024**3:raise ScanError('SCAN_BYTE_LIMIT')
   h.update(part)
   if collect:body.append(part)
  b=os.fstat(fd)
  if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns):raise ScanError('FILE_CHANGED')
  return {'sha256':h.hexdigest(),'bytes':count},b''.join(body)
 finally:os.close(fd)
def read_json(path,limit=8*1024**2):
 facts,body=read_file(path,limit=limit)
 def pairs(items):
  out={}
  for key,val in items:
   if key in out:raise ScanError('DUPLICATE_JSON_KEY')
   out[key]=val
  return out
 value=json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ScanError('INVALID_JSON')))
 if not isinstance(value,dict):raise ScanError('INVALID_JSON')
 return facts,value
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def alive(value):
 try:
  if not isinstance(value,dict) or set(value)!={'pid','bootId','startTime'} or type(value['pid']) is not int or not 0<value['pid']<2**31:return False
  text=pathlib.Path('/proc',str(value['pid']),'stat').read_text();fields=text[text.rfind(')')+2:].split()
  return fields[0] not in ('Z','X') and fields[19]==value['startTime'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==value['bootId']
 except (OSError,ValueError,IndexError):return False
def code(error):
 if isinstance(error,FileNotFoundError):return 'NOT_FOUND'
 if isinstance(error,PermissionError):return 'PERMISSION_DENIED'
 if isinstance(error,ScanError):return str(error)
 return 'INVALID_RECORD'
def timed(value):
 allowed={'cpuInputPreparation','sceneRenderingAndVerification','composition','mountedExport','gpuPipeline','sfxComposeExportVerify'}
 return {k:round(v,6) for k,v in value.items() if k in allowed and type(v) in (int,float) and math.isfinite(v) and 0<=v<=10**8} if isinstance(value,dict) else {}
def segment(root,key,expected,scene):
 if not isinstance(key,str) or not SHA.fullmatch(key):raise ScanError('CACHE_BINDING_INVALID')
 directory=root/'cache'/key;_,index=read_json(directory/'SUCCESS.json',65536)
 if set(index)!={'key','attemptId','receiptSHA256'} or index['key']!=key or not isinstance(index['attemptId'],str) or not re.fullmatch(r'attempt-[a-f0-9]{24}',index['attemptId']):raise ScanError('CACHE_BINDING_INVALID')
 attempt=directory/index['attemptId'];facts,receipt=read_json(attempt/'COMPLETE.json')
 if facts['sha256']!=index['receiptSHA256'] or receipt.get('schema')!='WORLD_ENGINE_SCENE_CACHE_RECEIPT_V2' or receipt.get('status')!='COMPLETE' or receipt.get('key')!=key:raise ScanError('CACHE_RECEIPT_INVALID')
 files=receipt.get('files');seg=receipt.get('segment',{})
 if not isinstance(files,list) or not 1<=len(files)<=12 or not isinstance(seg,dict):raise ScanError('CACHE_RECEIPT_INVALID')
 if seg.get('sha256')!=expected or seg.get('testOnly') is not False or seg.get('hardwareVerified') is not True or seg.get('fullDecodeVerified') is not True or seg.get('frameCountVerified') is not True:raise ScanError('CACHE_PROVENANCE_INVALID')
 if any(seg.get(k)!=scene.get(k) for k in ('sceneId','startFrame','endFrame')):raise ScanError('CACHE_BINDING_INVALID')
 for row in files:
  if not isinstance(row,dict) or not isinstance(row.get('file'),str) or not NAME.fullmatch(row['file']):raise ScanError('UNSAFE_PATH')
  actual,_=read_file(attempt/row['file'],limit=4*1024**3,collect=False)
  if actual!={k:row[k] for k in ('sha256','bytes')}:raise ScanError('CACHE_HASH_MISMATCH')
 return {'status':'VERIFIED','sha256':expected,'startFrame':seg.get('startFrame'),'endFrame':seg.get('endFrame'),'bytes':next((f['bytes'] for f in files if f['file']==seg.get('file')),None)}
def checkpoint(item,coordinator,plan,scene,exports):
 if not isinstance(item,dict) or item.get('schema')!='WORLD_ENGINE_PRIVATE_SCENE_CHECKPOINT_ANCHOR_V2' or item.get('status')!='SCENE_CHECKPOINT_MOUNTED_VERIFIED':raise ScanError('ANCHOR_REQUIRED')
 anchor=pathlib.Path(item.get('privateAnchor',''))
 if anchor.name!='SCENE_CHECKPOINT_ANCHOR.json' or not anchor.is_relative_to(coordinator):raise ScanError('ANCHOR_PATH_INVALID')
 facts,saved=read_json(anchor,16384)
 if facts['sha256']!=item.get('privateAnchorSHA256'):raise ScanError('ANCHOR_HASH_MISMATCH')
 for k in ('sceneId','startFrame','endFrame','planSHA256','sceneSHA256','exportDirectory','files','testOnly','hardwareVerified'):
  if saved.get(k)!=item.get(k):raise ScanError('ANCHOR_BINDING_INVALID')
 if saved.get('planSHA256')!=canonical(plan) or saved.get('sceneSHA256')!=canonical(scene) or saved.get('testOnly') is not False or saved.get('hardwareVerified') is not True or saved.get('publicReview') is not False:raise ScanError('ANCHOR_BINDING_INVALID')
 location=saved.get('exportDirectory')
 if not isinstance(location,str) or not re.fullmatch(r'world-engine-export-[a-f0-9]{24}/scene-recovery-[a-f0-9]{24}',location):raise ScanError('UNSAFE_PATH')
 files=saved.get('files')
 if not isinstance(files,list) or len(files)!=2 or {f.get('file') for f in files if isinstance(f,dict)}!={'segment.mp4','SHA256SUMS'}:raise ScanError('ANCHOR_BINDING_INVALID')
 for row in files:
  actual,_=read_file(exports/location/row['file'],private=False,limit=4*1024**3,collect=False)
  if actual!={k:row[k] for k in ('sha256','bytes')}:raise ScanError('CHECKPOINT_HASH_MISMATCH')
 return {'status':'VERIFIED','sha256':next(f['sha256'] for f in files if f['file']=='segment.mp4')}
def scan(roots,exports,job_id):
 output={'schema':'WORLD_ENGINE_STUDIO_READONLY_CACHE_SCAN_V1','jobId':job_id,'status':'NOT_FOUND','rootsChecked':0,'rootResults':[],'writes':0,'gpuInvoked':False,'externalDownloadVerified':False}
 for root_text in roots:
  deadline();root=pathlib.Path(root_text);row={'status':'NOT_FOUND'};output['rootsChecked']+=1
  try:
   statefacts,state=read_json(root/job_id/'STATE.json');_,plan=read_json(root/job_id/'PLAN.json');audiofacts,_=read_json(root/job_id/'AUDIO.json')
   if state.get('jobId')!=job_id or state.get('schema')!='WORLD_ENGINE_STUDIO_JOB_V1':raise ScanError('JOB_BINDING_INVALID')
   scenes=plan.get('scenes',[])
   if not isinstance(scenes,list) or not 1<=len(scenes)<=120:raise ScanError('PLAN_INVALID')
   row={'status':'FOUND','stateSHA256':statefacts['sha256'],'planSHA256':canonical(plan),'audioSHA256':audiofacts['sha256'],'state':state.get('state'),'phase':state.get('phase'),'errorCode':state.get('errorCode'),'totalFrames':plan.get('totalFrames'),'totalScenes':len(scenes),'completedScenes':state.get('completedScenes'),'processedFrames':state.get('processedFrames'),'silentResultPresent':isinstance(state.get('silentResult'),dict),'resultPresent':isinstance(state.get('result'),dict),'supervisorAlive':alive(state.get('supervisorIdentity')),'timingsSeconds':timed(state.get('timingsSeconds'))};output['status']='FOUND'
   for k in ('createdUnix','finishedUnix'):
    value=state.get(k)
    if type(value) in (int,float) and math.isfinite(value):row[k]=round(value,6)
   try:
    _,approval=read_json(root/job_id/'APPROVAL.json');row['approvedMaxWallSeconds']=approval.get('maxWallSeconds')
   except Exception:row['approvalRecordPresent']=False
   namespace={'V4_ARCHIVAL_80S':'render-v4','UNIVERSAL_V3':'render-v3'}.get(state.get('profileId'))
   if namespace is None:raise ScanError('PROFILE_UNSUPPORTED')
   coordinator=root/namespace;lower=coordinator/('video-v2-'+canonical(plan)[:24]);lowerfacts,ledger=read_json(lower/'JOB.json')
   if ledger.get('planSHA256')!=canonical(plan):raise ScanError('COORDINATOR_BINDING_INVALID')
   row['coordinator']={'state':ledger.get('state'),'phase':ledger.get('phase'),'recordSHA256':lowerfacts['sha256'],'timingsSeconds':timed(ledger.get('timingsSeconds')),'resultPresent':isinstance(ledger.get('result'),dict),'supervisorAlive':alive(ledger.get('supervisorIdentity')),'rendererAlive':alive(ledger.get('rendererIdentity')),'deadlineUnix':ledger.get('deadlineUnix'),'retriesUsed':ledger.get('retriesUsed'),'completedScenes':len(ledger.get('completedScenes',{})),'checkpointReceipts':len(ledger.get('sceneCheckpoints',{}))}
   row['segments']=[];row['checkpoints']=[]
   for scene in scenes:
    sid=scene.get('sceneId');completed=ledger.get('completedScenes',{}).get(sid,{})
    for name,operation in [('segments',lambda:segment(coordinator,completed.get('cacheKey'),completed.get('sha256'),scene)),('checkpoints',lambda:checkpoint(ledger.get('sceneCheckpoints',{}).get(sid),lower,plan,scene,pathlib.Path(exports)))]:
     try:entry=operation()
     except Exception as e:entry={'status':'UNVERIFIED','errorCode':code(e)}
     entry['sceneIndex']=len(row[name]);row[name].append(entry)
   row['verifiedCachedScenes']=sum(s['status']=='VERIFIED' for s in row['segments']);row['verifiedCheckpointScenes']=sum(s['status']=='VERIFIED' for s in row['checkpoints']);output['status']='FOUND'
  except Exception as error:row['scanError']=code(error)
  output['rootResults'].append(row)
 output['scanSeconds']=round(time.monotonic()-START,6);output['hashedBytes']=HASH_BYTES
 return output
'''


def candidate_roots(container):
    """One deployed non-secret selector, plus known exact historical defaults."""
    roots = list(DEFAULT_ROOTS)
    rows = container.get('containerEnvs') if isinstance(container, dict) else None
    values = [r['WORLD_ENGINE_STUDIO_STATE_ROOT'] for r in rows or []
              if isinstance(r, dict) and set(r) == {'WORLD_ENGINE_STUDIO_STATE_ROOT'}]
    if len(values) == 1 and isinstance(values[0], str):
        value = values[0]
        if (value.startswith(ROOT_PREFIX) and len(value) <= 200
                and all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) and p not in {'.', '..'} for p in value.split('/')[1:])):
            roots.insert(0, value.rstrip('/') + '/production')
    return list(dict.fromkeys(roots))


def scanner_command(roots):
    if not roots or any(not isinstance(p, str) or p not in candidate_roots({'containerEnvs': [{'WORLD_ENGINE_STUDIO_STATE_ROOT': p.removesuffix('/production')} ]}) for p in roots):
        raise ValueError('FIXED_PRIVATE_ROOT_REQUIRED')
    suffix = '\nPRIVATE_UID=1000\nprint(json.dumps(scan(' + repr(roots) + ", '/world-storage', " + repr(JOB) + '),allow_nan=False))\n'
    return ' '.join(shlex.quote(v) for v in ('/usr/bin/python3', '-B', '-c', SCANNER + suffix))


ALLOWED_STRINGS = frozenset('''WORLD_ENGINE_STUDIO_READONLY_CACHE_SCAN_V1 FOUND NOT_FOUND VERIFIED UNVERIFIED
QUEUED RUNNING COMPLETED FAILED INTERRUPTED GPU_DELEGATION SFX_AND_FINAL_COMPOSITION
ADMISSION_PENDING CPU_INPUT_PREPARATION RENDER COMPOSE EXPORT SCENE_COMPLETE SCENE_CHECKPOINT_EXPORT
GPU_COMPOSE GPU_EXPORT GPU_RENDER GPU_SCENE_COMPLETE GPU_SCENE_CHECKPOINT_EXPORT GPU_FAILED
STUDIO_APPROVED_DEADLINE_EXCEEDED APPROVED_WALL_TIME_EXCEEDED GPU_APPROVAL_EXPIRED
PERMISSION_DENIED SCAN_TIME_LIMIT SCAN_BYTE_LIMIT UNSAFE_PATH UNSAFE_FILE PRIVATE_RECORD_REQUIRED
FILE_CHANGED DUPLICATE_JSON_KEY INVALID_JSON INVALID_RECORD CACHE_BINDING_INVALID CACHE_RECEIPT_INVALID
CACHE_PROVENANCE_INVALID CACHE_HASH_MISMATCH ANCHOR_REQUIRED ANCHOR_PATH_INVALID ANCHOR_HASH_MISMATCH
ANCHOR_BINDING_INVALID CHECKPOINT_HASH_MISMATCH JOB_BINDING_INVALID PLAN_INVALID PROFILE_UNSUPPORTED
COORDINATOR_BINDING_INVALID INPUT_VALIDATION WITHHELD_UNKNOWN'''.split()) | {JOB}
ALLOWED_KEYS = frozenset('''schema jobId status rootsChecked rootResults writes gpuInvoked externalDownloadVerified
stateSHA256 planSHA256 audioSHA256 state phase errorCode scanError totalFrames totalScenes completedScenes processedFrames
silentResultPresent resultPresent supervisorAlive rendererAlive timingsSeconds createdUnix finishedUnix
approvedMaxWallSeconds approvalRecordPresent coordinator recordSHA256 deadlineUnix retriesUsed checkpointReceipts
segments checkpoints verifiedCachedScenes verifiedCheckpointScenes sceneIndex sha256 startFrame endFrame bytes
scanSeconds hashedBytes cpuInputPreparation sceneRenderingAndVerification composition mountedExport gpuPipeline
sfxComposeExportVerify'''.split())


def sanitize_scan(value, depth=0):
    """Untrusted remote output never gains arbitrary text or object-key channels."""
    if depth > 9:
        return None
    if value is None or type(value) is bool:
        return value
    if type(value) in (int, float):
        return value if -1 <= value <= 10**15 and __import__('math').isfinite(value) else None
    if isinstance(value, str):
        return value if value in ALLOWED_STRINGS or re.fullmatch(r'[a-f0-9]{64}', value) else 'WITHHELD_UNKNOWN'
    if isinstance(value, list):
        return [sanitize_scan(item, depth + 1) for item in value[:120]]
    if isinstance(value, dict):
        return {k: sanitize_scan(v, depth + 1) for k, v in value.items() if k in ALLOWED_KEYS}
    return None


def official_bundle(token):
    from importlib.metadata import version
    if version('gcube-cli') != '0.4.2':
        raise RuntimeError('OFFICIAL_CLI_VERSION_REQUIRED')
    from gcube_cli.api.client import Client, decode_email_from_jwt
    from gcube_cli.api.workload import WorkloadAPI
    from gcube_cli.api.ssh import SshAPI
    from gcube_cli.commands.workload import _resolve_namespace
    client = Client('https://api.gcube.ai', token, debug=False)
    return WorkloadAPI(client), SshAPI(client), lambda wl: _resolve_namespace(wl, client, decode_email_from_jwt(token) or '')


def ssh_scan(info, roots):
    """Reuse authenticated official gateway, never register or reconfigure SSH.

    Official 0.4.2 uses AutoAddPolicy (TOFU); this is not pinned-host-key proof.
    No credential, gateway location, raw stderr, or arbitrary command leaves.
    """
    from gcube_cli.commands.workload import _ssh_connect
    client = _ssh_connect(info)
    try:
        _stdin, stdout, stderr = client.exec_command(scanner_command(roots), timeout=100)
        channel = stdout.channel
        channel.settimeout(0.1)
        deadline = time.monotonic() + 100
        data, err = bytearray(), bytearray()
        while not (channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready()):
            if time.monotonic() >= deadline:
                raise TimeoutError()
            for ready, recv, target in ((channel.recv_ready, channel.recv, data), (channel.recv_stderr_ready, channel.recv_stderr, err)):
                if ready():
                    target.extend(recv(4096))
                    if len(target) > MAX_OUTPUT:
                        raise RuntimeError('REMOTE_OUTPUT_LIMIT')
            time.sleep(0.02)
        code = channel.recv_exit_status()
        if code != 0:
            return {'status': 'BLOCKED', 'blocking_reason': 'READ_ONLY_SCANNER_FAILED', 'remote_exit_code': code}
        raw = json.loads(data)
        if not isinstance(raw, dict) or raw.get('schema') != 'WORLD_ENGINE_STUDIO_READONLY_CACHE_SCAN_V1' or raw.get('jobId') != JOB:
            raise ValueError('REMOTE_SCHEMA_INVALID')
        return {'status': 'READ_ONLY_SCAN_COLLECTED', 'remote_exit_code': code, 'scan': sanitize_scan(raw),
                'sshTrust': 'OFFICIAL_GATEWAY_EXISTING_REGISTRATION_TOFU_NOT_PINNED'}
    finally:
        client.close()


def collect(environ=None, *, factory=official_bundle, scanner=ssh_scan):
    environ = os.environ if environ is None else environ
    result = {'schema': 'WORLD_ENGINE_STUDIO_80S_REMOTE_EVIDENCE_V1', 'workload': 5373,
        'jobId': JOB, 'utc': datetime.now(timezone.utc).isoformat(), 'status': 'BLOCKED',
        'authenticated_workload_read_succeeded': False, 'state_changes': 0, 'paid_operations': 0,
        'raw_outputs_published': False, 'credential_values_published': False, 'operations': []}
    token = environ.get('GCUBE_ACCESS_TOKEN')
    if not isinstance(token, str) or not token:
        return {**result, 'blocking_reason': 'APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED'}
    operation = 'OFFICIAL_CLIENT_INITIALIZATION'
    with tempfile.TemporaryFile(mode='w+') as private:
        os.fchmod(private.fileno(), 0o600)
        with redirect_stdout(private), redirect_stderr(private):
            try:
                api, ssh, namespace_for = factory(token)
                operation = 'WORKLOAD_DESCRIBE'; workload = api.describe(WORKLOAD)
                raw = getattr(workload, 'raw', {})
                if not isinstance(raw, dict) or str(raw.get('ser')) != WORKLOAD:
                    return {**result, 'blocking_reason': 'WORKLOAD_ID_NOT_VERIFIED'}
                result['authenticated_workload_read_succeeded'] = True
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['workload_state'] = collector.closed_value(raw.get('state'), rest_evidence.RAW_STATES, 'WITHHELD_UNKNOWN')
                operation = 'WORKLOAD_PODS'; pods = api.pods(WORKLOAD)
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['pod_statuses'] = [collector.closed_value(p.get('status'), rest_evidence.POD_STATES, 'WITHHELD_UNKNOWN') for p in pods if isinstance(p, dict)] if isinstance(pods, list) else []
                containers = raw.get('containerArray')
                if not isinstance(pods, list) or len(pods) != 1 or not isinstance(pods[0], dict) or not isinstance(containers, list) or len(containers) != 1:
                    return {**result, 'blocking_reason': 'UNAMBIGUOUS_EXISTING_POD_AND_CONTAINER_REQUIRED'}
                pod = pods[0].get('name')
                if not isinstance(pod, str) or not rest_evidence.POD_NAME.fullmatch(pod) or '..' in pod:
                    return {**result, 'blocking_reason': 'AUTHORIZED_POD_NAME_NOT_VALIDATED'}
                operation = 'OFFICIAL_HTTP_POD_LOGS'
                try:
                    documents, oversized = rest_evidence.log_documents(api.logs(WORKLOAD, pod))
                    result['log_size_limit_exceeded'] = oversized
                    result['first_actual_error'] = collector.first_error(documents)
                    result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                except (Exception, SystemExit) as error:
                    result['operations'].append({'operation': operation, **rest_evidence.safe_exception(error)})
                if pods[0].get('status') != 'Running':
                    return {**result, 'blocking_reason': 'EXISTING_RUNNING_POD_REQUIRED_NO_REDEPLOY'}
                operation = 'EXISTING_SSH_REGISTRATION_GET'
                namespace = namespace_for(workload)
                if not isinstance(namespace, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', namespace):
                    return {**result, 'blocking_reason': 'OFFICIAL_NAMESPACE_NOT_VERIFIED'}
                info = ssh.get(namespace, pod, 0)
                result['existing_ssh_registration_present'] = info is not None
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                if info is None:
                    return {**result, 'blocking_reason': 'EXISTING_SSH_REGISTRATION_NOT_AVAILABLE_NO_REGISTRATION_ATTEMPTED'}
                operation = 'EXISTING_SSH_FIXED_READONLY_SCAN'
                evidence = scanner(info, candidate_roots(containers[0]))
                result['scan_evidence'] = evidence
                result['status'] = 'READ_ONLY_EVIDENCE_COLLECTED'
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
            except (Exception, SystemExit) as error:
                result['operations'].append({'operation': operation, **rest_evidence.safe_exception(error)})
                result['blocking_reason'] = 'READ_ONLY_REMOTE_ACCESS_FAILED'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cli', default='gcube')
    args = parser.parse_args()
    # Whole optional API/SSH collection is bounded. CLI helper independently
    # preserves authenticated describe/pods/log evidence even if SSH fails.
    cli = collector.collect(binary=args.cli,
        runner=lambda binary, argv, env, seconds: collector.capture_command(binary, argv, env, min(seconds, 25)))
    def expired(*_):
        raise TimeoutError()
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(180)
    try:
        remote = collect()
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, previous)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (('CLI_RESULT.json', cli), ('REMOTE_RESULT.json', remote)):
        data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        fd = os.open(args.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    print(json.dumps({'status': remote['status'], 'raw_outputs_published': False, 'state_changes': 0}))


if __name__ == '__main__':
    main()
