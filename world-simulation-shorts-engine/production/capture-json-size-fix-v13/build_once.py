"""Free CPU-only additive image, retained once before unique-tag publication."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare as package
REPO = 'dimon3898-sys/yeonhwarok-free'
BRANCH = 'fix/capture-json-size-20261108'
WORKFLOW = '.github/workflows/world-engine-capture-json-size-image-once.yml'
OLD_TAG = 'kw20-native-v11-42345505600'

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

def main():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_RUN_ATTEMPT')=='1', 'RUN_GUARD')
    need(os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH, 'BRANCH_GUARD')
    repo, temp = Path(os.environ['GITHUB_WORKSPACE']), Path(os.environ['RUNNER_TEMP'])
    out = temp/'json-size-evidence'; out.mkdir()
    def write(name, obj): package.write(out/name, package.encoded(obj))
    keep = None
    try:
        need(run(['git','rev-parse','HEAD'])==os.environ['GITHUB_SHA'], 'CHECKOUT_CHANGED')
        need(run(['git','rev-parse','HEAD^'])==os.environ['JSON_SIZE_EXPECTED_PARENT'], 'PARENT_GUARD')
        need(run(['git','diff','--name-only','HEAD^','HEAD']).splitlines()==[WORKFLOW], 'WORKFLOW_ONLY_ACTIVATION')
        context = temp/'json-size-context'
        plan = package.prepare(context); write('CONTEXT.json', plan)
        need(plan['cpuResultSHA256']=='fdd9fb38ea6f938cfcf1d1b05b8d4a0a95cc7a51b413b781c1e19919002e81ab', 'CPU_RESULT_PIN')
        write('REUSED_CPU_RESULT.json', json.loads((HERE/'evidence/CPU_RESULT.json').read_bytes()))
        write('PREBUILD_GATE.json', {'status':'PASS','scope':'New post-capture JSON boundary; source unchanged since10 focused passes','oldPASSReruns':0,'focusedTestsRerun':0})
        need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST, 'PRESERVED_IMAGE_CHANGED')
        tag_name = 'capture-json-v13-'+os.environ['GITHUB_RUN_ID']
        target = package.IMAGE+':'+tag_name; common.absent(tag_name)
        need(['driver-type','io.containerd.snapshotter.v1'] in json.loads(docker('info','--format','{{json .DriverStatus}}')), 'CONTAINERD_REQUIRED')
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>12*1024**3, 'CAPACITY_REQUIRED')
        auth = temp/'json-size-docker-auth'; auth.mkdir(mode=0o700); os.environ['DOCKER_CONFIG']=str(auth)
        run(['docker','--host=unix:///var/run/docker.sock','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GH_TOKEN'])
        write('PULL_ATTEMPT.json', {'attempt':1,'image':package.PARENT}); docker_once(['pull',package.PARENT])
        parent=json.loads(docker('image','inspect',package.PARENT))[0]
        need(package.PARENT in parent.get('RepoDigests',[]), 'PARENT_DIGEST_CHANGED')
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>parent['Size']*3+2*1024**3, 'BACKUP_CAPACITY_REQUIRED')
        keep=module('_json_size_retention',repo/'world-simulation-shorts-engine/recovery/reference-label-quality-v1/retain_quality_image.py')
        keep.ROOT=temp/'json-size-backup'; keep.ROOT.mkdir(); keep.SOURCE=os.environ['GITHUB_SHA']; keep.PARENT=package.PARENT_DIGEST
        keep.RELEASE_TAG='capture-json-image-backup-'+os.environ['GITHUB_RUN_ID']
        keep.reserve()
        release=keep.read('RELEASE.json')
        for filename in ('CPU_RESULT.json','INCIDENT.json','CAPTURE_DIAGNOSTIC.json','CAPTURE_CHECKPOINT.json'):
            keep.upload(release,HERE/'evidence'/filename)
        local='world-engine-json-size:unpublished-'+os.environ['GITHUB_RUN_ID']; os.environ['TAG']=local
        write('BUILD_ATTEMPT.json', {'attempt':1,'image':local})
        docker_once(['build','--platform','linux/amd64','--provenance=false','--sbom=false','--network','none','--pull=false','-t',local,str(context)])
        candidate=json.loads(docker('image','inspect',local))[0]
        expected=dict(parent['Config']); expected['Entrypoint']=plan['entrypoint']
        need(candidate['Config']==expected, 'ONLY_STARTUP_HASH_CONFIG_CHANGE')
        need(candidate['RootFS']['Layers'][:-1]==parent['RootFS']['Layers'], 'ONE_ADDITIVE_LAYER_REQUIRED')
        # Archive even if the new installed import boundary is blocked.
        probe_error = None
        try: write('INSTALLED_SOURCE.json', probe(local,plan))
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
        write('RESULT.json', {'status':'PASS','tag':target,'digest':digest,'sourceCommit':os.environ['GITHUB_SHA'],
            'backup':release['html_url'],'parentImage':package.PARENT,'oldTagPreserved':True,
            'builds':1,'publications':1,'gpuStarts':0,'renders':0,'oldPASSReruns':0,'focusedTestsRerun':0,
            'runtimeManifestSHA256':plan['runtimeManifestSHA256'],'startupManifestSHA256':plan['startupManifestSHA256'],
            'actualGpuRetry':'NOT_RUN_USER_ONLY','actualPriorFailureFileSize':'UNKNOWN'})
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
