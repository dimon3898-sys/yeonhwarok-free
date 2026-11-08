"""Free CPU-only additive image, retained once before unique-tag publication."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare as package
REPO = 'dimon3898-sys/yeonhwarok-free'
BRANCH = 'fix/cold-start-pins-20261108'
WORKFLOW = '.github/workflows/world-engine-cold-start-pin-image-once.yml'
OLD_TAG = 'capture-json-v13-42442147946'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value

common = module('_json_size_preserved_build_helpers', HERE.parents[1] / 'recovery/reference-label-quality-v1/build_once.py')
need, docker, docker_once, run = common.need, common.docker, common.docker_once, common.run_command

def probe(tag, plan):
    command = ['docker','--host=unix:///var/run/docker.sock','run','--rm','-i','--network','none',
        '--read-only','--user','1000:1000','--cap-drop=ALL','--security-opt=no-new-privileges',
        '--tmpfs','/tmp:rw,nosuid,size=64m','-e','NVIDIA_VISIBLE_DEVICES=void',
        '-e','PYTHONDONTWRITEBYTECODE=1','--entrypoint','/usr/bin/python3',tag,
        '-I','-B','-c',(HERE/'probe_installed.py').read_text()]
    result = json.loads(run(command, input=json.dumps({'root':package.ROOT,'plan':plan})))
    need(result['status']=='PASS' and result['gpuStarts']==result['renderedFrames']==0, 'INSTALLED_PROBE_FAILED')
    return result

def entrypoint_probe(tag):
    image_id=json.loads(docker('image','inspect',tag))[0]['Id']
    command=['docker','--host=unix:///var/run/docker.sock','run','--rm','--network','none',
        '--read-only','--cap-drop=ALL','--cap-add=CHOWN','--security-opt=no-new-privileges',
        '--tmpfs','/run:rw,nosuid,size=16m','--tmpfs','/world-storage:rw,nosuid,size=16m',
        '-e','NVIDIA_VISIBLE_DEVICES=void','-e','GPU_BACKEND=vulkan',
        '-e','WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST='+image_id,
        '-e','WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST='+image_id,
        '-e','WORLD_ENGINE_STUDIO_STATE_ROOT=/run/v14-cpu-only-private',
        '-e','WORLD_ENGINE_STUDIO_OWNER_CODE=','-e','WORLD_ENGINE_OWNER_CODE=',tag]
    # No --entrypoint override: test the actual packaged tini -> bootstrap.
    completed=subprocess.run(command,text=True,capture_output=True,timeout=60)
    rows=[json.loads(s) for s in completed.stdout.splitlines() if s.startswith('{')]
    need(completed.returncode==1 and len(rows)==1, 'ENTRYPOINT_EXPECTED_EARLY_AUTH_STOP')
    row=rows[0]
    need(row.get('stage')=='COLD_START_BLOCKED' and row.get('errorCode')=='STUDIO_OWNER_CONFIGURATION_REQUIRED'
         and row.get('listenerStarted') is False and row.get('renderAutomaticallyStarted') is False,
         'ENTRYPOINT_DID_NOT_REACH_AUTH_BOUNDARY:'+json.dumps(rows))
    need(not completed.stderr.strip(), 'ENTRYPOINT_STDERR_UNEXPECTED')
    return {'status':'PASS','actualImageEntrypointUsed':True,'exitCode':completed.returncode,
        'expectedStop':row,'scope':'Real tini/bootstrap startup passes manifest, process lineage, lock, ports, source handoff, frozen proxy verification; stops at intentionally absent owner before child/service/GPU admission',
        'gpuStarts':0,'renders':0,'network':'none','nvidiaDevices':'void','productionCredentialsUsed':False}

def main():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_RUN_ATTEMPT')=='1', 'RUN_GUARD')
    need(os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH, 'BRANCH_GUARD')
    repo, temp = Path(os.environ['GITHUB_WORKSPACE']), Path(os.environ['RUNNER_TEMP'])
    out = temp/'cold-start-pin-evidence'; out.mkdir()
    def write(name, obj): package.write(out/name, package.encoded(obj))
    keep = None
    try:
        need(run(['git','rev-parse','HEAD'])==os.environ['GITHUB_SHA'], 'CHECKOUT_CHANGED')
        need(run(['git','rev-parse','HEAD^'])==os.environ['COLD_START_EXPECTED_PARENT'], 'PARENT_GUARD')
        need(run(['git','diff','--name-only','HEAD^','HEAD']).splitlines()==[WORKFLOW], 'WORKFLOW_ONLY_ACTIVATION')
        context = temp/'cold-start-pin-context'
        plan = package.prepare(context); write('CONTEXT.json', plan)
        need(plan['cpuResultSHA256']=='f0010b2ddcf01e77608733d43d8ad970fc9909bde538115a637fbb6973bc8361', 'CPU_RESULT_PIN')
        write('REUSED_CPU_RESULT.json', json.loads((HERE/'evidence/CPU_RESULT.json').read_bytes()))
        write('PREBUILD_GATE.json', {'status':'PASS','scope':'New startup pin boundary; parent/child verification and source guards checked','oldPASSReruns':0,'focusedTestsRerun':0})
        need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST, 'PRESERVED_IMAGE_CHANGED')
        need(common.registry('kw20-native-v11-42345505600')[1]=='sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726','V11_PRESERVED')
        tag_name = 'cold-start-v14-'+os.environ['GITHUB_RUN_ID']
        target = package.IMAGE+':'+tag_name; common.absent(tag_name)
        need(['driver-type','io.containerd.snapshotter.v1'] in json.loads(docker('info','--format','{{json .DriverStatus}}')), 'CONTAINERD_REQUIRED')
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>12*1024**3, 'CAPACITY_REQUIRED')
        auth = temp/'cold-start-pin-docker-auth'; auth.mkdir(mode=0o700); os.environ['DOCKER_CONFIG']=str(auth)
        run(['docker','--host=unix:///var/run/docker.sock','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GH_TOKEN'])
        write('PULL_ATTEMPT.json', {'attempt':1,'image':package.PARENT}); docker_once(['pull',package.PARENT])
        parent=json.loads(docker('image','inspect',package.PARENT))[0]
        need(package.PARENT in parent.get('RepoDigests',[]), 'PARENT_DIGEST_CHANGED')
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>parent['Size']*3+2*1024**3, 'BACKUP_CAPACITY_REQUIRED')
        keep=module('_json_size_retention',repo/'world-simulation-shorts-engine/recovery/reference-label-quality-v1/retain_quality_image.py')
        keep.ROOT=temp/'cold-start-pin-backup'; keep.ROOT.mkdir(); keep.SOURCE=os.environ['GITHUB_SHA']; keep.PARENT=package.PARENT_DIGEST
        keep.RELEASE_TAG='cold-start-image-backup-'+os.environ['GITHUB_RUN_ID']
        keep.reserve()
        release=keep.read('RELEASE.json')
        for filename in ('CPU_RESULT.json','BASELINE_REPRODUCTION.json','INCIDENT.json'):
            keep.upload(release,HERE/'evidence'/filename)
        local='world-engine-cold-start-pin:unpublished-'+os.environ['GITHUB_RUN_ID']; os.environ['TAG']=local
        write('BUILD_ATTEMPT.json', {'attempt':1,'image':local})
        docker_once(['build','--platform','linux/amd64','--provenance=false','--sbom=false','--network','none','--pull=false','-t',local,str(context)])
        candidate=json.loads(docker('image','inspect',local))[0]
        expected=dict(parent['Config']); expected['Entrypoint']=plan['entrypoint']
        need(candidate['Config']==expected, 'ONLY_STARTUP_HASH_CONFIG_CHANGE')
        need(candidate['RootFS']['Layers'][:-1]==parent['RootFS']['Layers'], 'ONE_ADDITIVE_LAYER_REQUIRED')
        # Archive even if the new installed import boundary is blocked.
        probe_error = None
        try:
            write('INSTALLED_SOURCE.json', probe(local,plan))
            write('ENTRYPOINT_CPU.json', entrypoint_probe(local))
        except Exception as error: probe_error=error
        keep.archive(); retained=keep.read('RETENTION_RESULT.json')
        need(retained['status']=='PASS' and retained['archiveRootDigest']==candidate['Id'] and retained['rootFSDiffIDs']==candidate['RootFS']['Layers'], 'BACKUP_IDENTITY')
        if probe_error is not None: raise probe_error
        common.absent(tag_name); need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST, 'OLD_TAG_CHANGED')
        docker('tag',local,target); write('PUBLICATION_ATTEMPT.json',{'attempt':1,'tag':target}); docker_once(['push',target])
        raw,digest=common.registry(tag_name); pinned,confirmed=common.registry(digest); manifest=json.loads(raw)
        need(raw==pinned and digest==confirmed==candidate['Id']==retained['archiveRootDigest'], 'REMOTE_DIGEST_IDENTITY')
        if 'manifests' in manifest:
            need(len(manifest['manifests'])==1 and manifest['manifests'][0]['digest']==retained['imageManifestDigest'], 'SINGLE_PLATFORM_IDENTITY')
            manifest=json.loads(common.registry(retained['imageManifestDigest'])[0])
        need(manifest['config']['digest']==retained['configDigest'], 'REMOTE_CONFIG_IDENTITY')
        need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST, 'OLD_TAG_PRESERVED')
        need(common.registry('kw20-native-v11-42345505600')[1]=='sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726','V11_STILL_PRESERVED')
        write('RESULT.json', {'status':'PASS','tag':target,'digest':digest,'sourceCommit':os.environ['GITHUB_SHA'],
            'backup':release['html_url'],'parentImage':package.PARENT,'oldTagPreserved':True,
            'builds':1,'publications':1,'gpuStarts':0,'renders':0,'oldPASSReruns':0,'focusedTestsRerun':0,
            'runtimeManifestSHA256':plan['runtimeManifestSHA256'],'startupManifestSHA256':plan['startupManifestSHA256'],
            'actualGpuRetry':'NOT_RUN_USER_ONLY','actualGpuRuntime':'UNVERIFIED_USER_ONLY'})
    except Exception as error:
        write('BLOCKED.json', {'status':'BLOCKED','type':type(error).__name__,
            'reason':str(error) if isinstance(error,RuntimeError) else 'COMMAND_OR_SERVICE_FAILURE','gpuStarts':0,'renders':0,'automaticRetries':0})
        raise
    finally:
        for path in sorted(out.glob('*.json')):
            if keep is not None:
                try: keep.upload(keep.read('RELEASE.json'),path)
                except Exception: print('EVIDENCE_RELEASE_UPLOAD_FAILED:'+path.name,flush=True)

if __name__ == '__main__': main()
