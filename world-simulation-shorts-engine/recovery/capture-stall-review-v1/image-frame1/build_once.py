#!/usr/bin/env python3
"""Package the CPU-validated frame1 fix once. No functional test reruns or GPU."""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

REC = 'world-simulation-shorts-engine/recovery/'
HERE = REC + 'capture-stall-review-v1/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
REPO = 'dimon3898-sys/yeonhwarok-free'
BRANCH = 'recovery/capture-durable-20261105'
WORKFLOW = '.github/workflows/world-engine-frame1-fix-image-once.yml'
PARENT_DIGEST = 'sha256:534e5afd33e73b9d3f3e49db3f4a7dc63a1ee25a91457611f2d4b4fcb00e1e4c'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT = IMAGE + '@' + PARENT_DIGEST
OLD_TAG = 'capture-retention-v1-42002690934'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
VALIDATED = '754b09262140b0ad5a48238843e0f98aaa8c4735'

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

# Reuse established registry, one-attempt Docker, source and entrypoint helpers.
common = module('_retention_image_common', Path(__file__).resolve().parents[2] / 'reference-label-quality-v1/build_once.py')
need, sha, source = common.need, common.sha, common.source
encoded, docker, docker_once = common.encoded, common.docker, common.docker_once
registry, absent, run_command = common.registry, common.absent, common.run_command
entrypoint = common.entrypoint

def prepare(repo, context):
    repo, context = repo.resolve(), context.absolute()
    need(not context.exists() and not context.is_relative_to(repo), 'FRESH_SEPARATE_CONTEXT_REQUIRED')
    seal_raw = source(repo / (HERE + 'evidence/INCIDENT_SOURCE_SEAL.json'))
    seal = json.loads(seal_raw)
    evidence = HERE + 'executions/20261105-user-render-a1/'
    gate = json.loads(source(repo / (evidence + 'IMAGE_FIX_PLAN.json')))
    ci = json.loads(source(repo / (evidence + 'CPU_RESULT.json')))
    frames = json.loads(source(repo / (evidence + 'FRAME1_RESULT.json')))
    controls = json.loads(source(repo / (evidence + 'CONTROL_RESULT.json')))
    need(ci['sourceCommit'] == gate['sourceCommit'] == VALIDATED, 'VALIDATED_SOURCE_REQUIRED')
    need(ci['status'] == 'PASS' and ci['uid'] == 1000 and gate['validatedCpuRun'] == 42031019500, 'CPU_EVIDENCE_REQUIRED')
    need(frames['status'] == 'CPU_FRAME1_REGRESSION_PASS' and controls['status'] == 'PASS' and controls['uid'] == 1000, 'INCIDENT_PASS_REQUIRED')
    need(seal['files'] == gate['overlay'] and len(seal['files']) == 9, 'EXACT_NINE_SEALED_FILES')
    need(seal['sourceRows'] == 356, 'RUNTIME_ROW_COUNT')
    need(gate['baseImage'] == PARENT, 'EXACT_PARENT_REQUIRED')
    base = json.loads(source(repo / (HERE + 'image-frame1/BASE_PINS.json')))
    overlay = {}
    for row in seal['files']:
        name = row['path']
        need(name in base and name.startswith(REC) and '..' not in Path(name).parts, 'EXACT_OVERLAY_PATH')
        raw = source(repo / name)
        need(row == {'path': name, 'bytes': len(raw), 'sha256': sha(raw)}, 'VALIDATED_BYTES_CHANGED')
        overlay[name] = raw
    need(len(overlay) == len(base) == 9, 'OVERLAY_UNIQUE_SET')
    runtime = json.loads(overlay[RUNTIME])
    rows = {r['path']: r for r in runtime['files']}
    need(len(rows) == 356 and len(runtime['files']) == 356, 'UNIQUE_RUNTIME_ROWS')
    changed = [r for r in seal['files'] if r['path'] not in (RUNTIME, STARTUP, BOOTSTRAP)]
    need(len(changed) == 6 and all(rows[r['path']] == r for r in changed), 'MANIFEST_OVERLAY_LINK')
    runtime_sha = sha(overlay[RUNTIME]); startup_sha = sha(overlay[STARTUP])
    need(runtime_sha == seal['runtimeManifestSHA256'], 'RUNTIME_PIN')
    startup = json.loads(overlay[STARTUP])
    need(startup['runtimeManifestSHA256'] == runtime_sha, 'STARTUP_RUNTIME_PIN')
    need(startup['files']['bootstrap.py'] == {'bytes':len(overlay[BOOTSTRAP]), 'sha256':sha(overlay[BOOTSTRAP])}, 'STARTUP_BOOTSTRAP_PIN')
    need(("SOURCE_SHA = '" + runtime_sha + "'").encode() in overlay[BOOTSTRAP], 'BOOTSTRAP_RUNTIME_PIN')
    entry = entrypoint(runtime_sha, startup_sha)
    dockerfile = 'FROM ' + PARENT + '\nCOPY --chown=0:0 ' + json.dumps(['overlay/', IMAGE_ROOT + '/']) + '\nENTRYPOINT ' + json.dumps(entry) + '\n'
    need(sum(map(len,overlay.values())) < 1024**2, 'BOUNDED_OVERLAY')
    context.mkdir(parents=True, mode=0o755)
    for name, raw in {**{'overlay/'+p:b for p,b in overlay.items()}, 'Dockerfile':dockerfile.encode()}.items():
        path = context / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(0o644)
    for path in context.rglob('*'):
        if path.is_dir(): path.chmod(0o755)
    return {'schema':'WORLD_ENGINE_FRAME1_FIX_IMAGE_CONTEXT_V1','status':'PASS','sourceCommit':VALIDATED,
        'overlay':seal['files'],'basePins':base,'runtimeSourceRows':356,'entrypoint':entry,
        'parentDigest':PARENT_DIGEST,'dockerfileSHA256':sha(dockerfile.encode()),
        'runtimeManifestSHA256':runtime_sha,'startupManifestSHA256':startup_sha,
        'reusedCPURun':42031019500,'functionalTestsRerun':0,'oldPASSReruns':0,'gpuExecutions':0}

def old_tag():
    need(registry(OLD_TAG)[1] == PARENT_DIGEST, 'EXISTING_PARENT_TAG_CHANGED')

def retention(repo, temp):
    keep = module('_retention_image_backup', repo / (REC + 'reference-label-quality-v1/retain_quality_image.py'))
    keep.ROOT = temp / 'frame1-fix-backup'; keep.ROOT.mkdir()
    keep.SOURCE = os.environ['GITHUB_SHA']; keep.PARENT = PARENT_DIGEST
    keep.RELEASE_TAG = 'frame1-fix-image-backup-' + os.environ['GITHUB_RUN_ID']
    def reserve():
        release = keep.api(keep.API + '/releases', {'tag_name':keep.RELEASE_TAG, 'target_commitish':keep.SOURCE,
            'name':'Frame1 fix image backup ' + os.environ['GITHUB_RUN_ID'],
            'body':'CPU-validated frame1 fix overlay. GPU300-frame capture and actual mounted-storage validation remain pending. Existing images are preserved.',
            'draft':False, 'prerelease':True, 'make_latest':'false'})
        keep.write('RELEASE.json',release)
        keep.write('RESERVATION.json',{'sourceCommit':keep.SOURCE,'parentDigest':PARENT_DIGEST,'maxBuilds':1,'maxGHCRPublications':1,'retries':0})
        proof = keep.upload(release,keep.ROOT/'RESERVATION.json')
        keep.write('RESERVATION_RESULT.json',{'status':'PASS','releaseURL':release['html_url'],'asset':proof})
    keep.reserve = reserve
    return keep

def installed_probe(repo, tag, mode, plan):
    script = source(repo / (HERE + 'image/installed_probe.py')).decode()
    payload = {'mode':mode,'root':IMAGE_ROOT,'plan':plan,
        'runtime':json.loads(source(repo/RUNTIME)),
        'bootstrap':source(repo/BOOTSTRAP).decode(),'startup':json.loads(source(repo/STARTUP))}
    value = run_command(['docker','--host=unix:///var/run/docker.sock','run','--rm','-i','--network','none',
        '--read-only','--user','1000:1000','--cap-drop=ALL','--security-opt=no-new-privileges',
        '--entrypoint','/usr/bin/python3',tag,'-I','-B','-c',script], input=json.dumps(payload))
    result = json.loads(value)
    need(result['status'] == 'PASS' and result['mode'] == mode and result['uid'] == 1000,'INSTALLED_PROBE_REQUIRED')
    return result

def main_run():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_RUN_ATTEMPT') == '1','RUN_GUARD')
    need(os.environ.get('GITHUB_REF') == 'refs/heads/'+BRANCH,'BRANCH_GUARD')
    repo=Path(os.environ['GITHUB_WORKSPACE']).resolve(); temp=Path(os.environ['RUNNER_TEMP'])
    out=temp/'frame1-fix-image-evidence'; out.mkdir()
    def write(name,value):
        with (out/name).open('x') as f: f.write(encoded(value).decode())
    keep=None
    try:
        need(run_command(['git','rev-parse','HEAD']) == os.environ['GITHUB_SHA'],'CHECKOUT_CHANGED')
        need(run_command(['git','rev-parse','HEAD^']) == os.environ['FRAME1_EXPECTED_PARENT'],'EXPECTED_PARENT_REQUIRED')
        need(run_command(['git','diff','--name-only','HEAD^','HEAD']).splitlines() == [WORKFLOW],'ACTIVATION_WORKFLOW_ONLY')
        context=temp/'frame1-fix-image-context'; plan=prepare(repo,context); write('CONTEXT.json',plan)
        old_tag(); tag_name='frame1-fix-v1-'+os.environ['GITHUB_RUN_ID']; target=IMAGE+':'+tag_name; absent(tag_name)
        need(['driver-type','io.containerd.snapshotter.v1'] in json.loads(docker('info','--format','{{json .DriverStatus}}')),'CONTAINERD_IMAGE_STORE_REQUIRED')
        docker_root=docker('info','--format','{{.DockerRootDir}}')
        need(shutil.disk_usage(docker_root).free >= 12*1024**3,'PREPULL_CAPACITY')
        auth=temp/'frame1-fix-docker-auth'; auth.mkdir(mode=0o700); os.environ['DOCKER_CONFIG']=str(auth)
        run_command(['docker','--host=unix:///var/run/docker.sock','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GH_TOKEN'])
        keep=retention(repo,temp); keep.reserve()
        write('PULL_ATTEMPT.json',{'attempt':1,'parent':PARENT}); docker_once(['pull',PARENT])
        parent=json.loads(docker('image','inspect',PARENT))[0]
        need(PARENT in parent.get('RepoDigests',[]),'PARENT_DIGEST_NOT_PRESENT')
        need(parent['Config']['Entrypoint']==entrypoint(plan['basePins'][RUNTIME],plan['basePins'][STARTUP]),'PARENT_STARTUP_CHANGED')
        write('PARENT_OVERLAY_CONTRACT.json',installed_probe(repo,PARENT,'parent',plan))
        need(shutil.disk_usage(docker_root).free >= parent['Size']*3+2*1024**3,'PREBUILD_ARCHIVE_CAPACITY')
        local='world-engine-frame1-fix:unpublished-'+os.environ['GITHUB_RUN_ID']; os.environ['TAG']=local
        write('BUILD_ATTEMPT.json',{'attempt':1,'tag':local})
        docker_once(['build','--platform','linux/amd64','--provenance=false','--sbom=false','--network','none','--pull=false','-t',local,str(context)])
        keep.archive()
        candidate=json.loads(docker('image','inspect',local))[0]; retained=keep.read('RETENTION_RESULT.json')
        need(retained['status']=='PASS' and retained['identityMode']=='CONTAINERD_DESCRIPTOR_AND_CONFIG' and
            retained['imageID']==retained['archiveRootDigest']==candidate['Id'] and
            retained['rootFSDiffIDs']==candidate['RootFS']['Layers'],'ARCHIVE_IDENTITY_REQUIRED')
        expected=dict(parent['Config']); expected['Entrypoint']=plan['entrypoint']
        need(candidate['Config']==expected,'ONLY_STARTUP_HASH_CONFIG_CHANGE')
        need(candidate['RootFS']['Layers'][:-1]==parent['RootFS']['Layers'],'EXACT_ONE_ADDITIVE_LAYER')
        write('INSTALLED_SOURCE.json',installed_probe(repo,local,'candidate',plan))
        write('CANDIDATE.json',{'status':'PASS','imageID':candidate['Id'],'overlayFiles':9,'uid':1000,
            'parentLayersPreserved':len(parent['RootFS']['Layers']),'newLayers':1,'startupSourceContract':'PASS',
            'functionalTestsRerun':0,'oldPASSReruns':0,'gpuExecutions':0})
        old_tag(); absent(tag_name); docker('tag',local,target)
        need(docker('image','inspect','--format','{{.Id}}',target)==candidate['Id'],'TAG_IDENTITY')
        write('PUBLICATION_ATTEMPT.json',{'attempt':1,'tag':target,'imageID':candidate['Id']}); docker_once(['push',target])
        raw,digest=registry(tag_name); pinned,confirmed=registry(digest); manifest=json.loads(raw)
        need(raw==pinned and digest==confirmed==retained['archiveRootDigest']==candidate['Id'],'REMOTE_ROOT_DESCRIPTOR_IDENTITY')
        if 'manifests' in manifest:
            need(len(manifest['manifests'])==1 and manifest['manifests'][0]['digest']==retained['imageManifestDigest'],'REMOTE_SINGLE_PLATFORM_IDENTITY')
            image_raw,image_digest=registry(retained['imageManifestDigest']); manifest=json.loads(image_raw)
            need(image_digest==retained['imageManifestDigest'],'REMOTE_IMAGE_IDENTITY')
        need(manifest['config']['digest']==retained['configDigest'],'REMOTE_CONFIG_IDENTITY'); old_tag()
        write('RESULT.json',{'schema':'WORLD_ENGINE_FRAME1_FIX_IMAGE_RESULT_V1','status':'PASS',
            'tag':target,'digest':digest,'imageID':candidate['Id'],'configDigest':retained['configDigest'],
            'imageManifestDigest':retained['imageManifestDigest'],'sourceCommit':os.environ['GITHUB_SHA'],
            'validatedImplementationCommit':VALIDATED,'imageRelease':retained['releaseURL'],
            'builds':1,'publications':1,'retries':0,'oldPASSReruns':0,'gpuStarts':0,'renders':0,
            'oldTagUnchanged':True,'actualGcubeMountVerified':False,'actualStallFixed':False,'referenceQualityPass':False})
    except Exception as error:
        write('BLOCKED.json',{'status':'BLOCKED','errorType':type(error).__name__,
            'reason':str(error) if isinstance(error,RuntimeError) else 'COMMAND_OR_SERVICE_OPERATION_FAILED',
            'automaticRetries':0,'gpuExecutions':0})
        raise
    finally:
        for path in sorted(out.glob('*.json')):
            raw=path.read_bytes()
            print('FRAME1_IMAGE_EVIDENCE='+json.dumps({'name':path.name,'sha256':sha(raw),'base64':base64.b64encode(raw).decode()}),flush=True)
            if keep is not None and (keep.ROOT/'RELEASE.json').exists(): keep.upload(keep.read('RELEASE.json'),path)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('operation',choices=['prepare','run'])
    parser.add_argument('--repo',type=Path); parser.add_argument('--context',type=Path); args=parser.parse_args()
    if args.operation=='prepare': print(json.dumps(prepare(args.repo,args.context),indent=2,sort_keys=True))
    else: main_run()
