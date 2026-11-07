"""Resume retention/publication with preserved formal input connection PASS.
No capture command, GPU, Studio start, deployment API or movie production.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prepare as package
REPO='dimon3898-sys/yeonhwarok-free'
BRANCH='deployment/korean-war-20s-native-20261107'
WORKFLOW='.github/workflows/world-engine-kw20-native-deployment-once.yml'
OLD_TAG='variant-pin-fix-v1-42163156402'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value

common=module('_kw20_preserved_image_helpers',HERE.parents[1]/'recovery/reference-label-quality-v1/build_once.py')
need,sha,encoded=common.need,common.sha,common.encoded
docker,docker_once,run=common.docker,common.docker_once,common.run_command

def probe(tag,plan,mode,context=None):
    command=['docker','--host=unix:///var/run/docker.sock','run','--rm','-i','--network','none',
        '--read-only','--user','1000:1000','--cap-drop=ALL','--security-opt=no-new-privileges',
        '--tmpfs','/workspace:rw,nosuid,uid=1000,gid=1000,mode=0755,size=512m',
        '--tmpfs','/world-storage:rw,nosuid,uid=1000,gid=1000,mode=0755,size=64m',
        '--tmpfs','/tmp:rw,nosuid,size=128m','-e','NVIDIA_VISIBLE_DEVICES=void',
        '-e','PYTHONDONTWRITEBYTECODE=1','-e','WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map']
    if context is not None:
        for row in plan['overlay']:
            command+=['--mount',f'type=bind,src={context/"overlay"/row["path"]},dst={package.ROOT}/{row["path"]},readonly']
    command+=['--entrypoint','/usr/bin/python3',tag,'-I','-B','-c',(HERE/'probe.py').read_text()]
    result=json.loads(run(command,input=json.dumps({'plan':plan,'mode':mode,'root':package.ROOT})))
    need(result['status']=='PASS' and result['gpuStarts']==result['renderedFrames']==0,'PROBE_FAILED')
    return result

def main():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','RUN_GUARD')
    need(os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH,'BRANCH_GUARD')
    repo=Path(os.environ['GITHUB_WORKSPACE']);temp=Path(os.environ['RUNNER_TEMP'])
    out=temp/'kw20-native-evidence';out.mkdir()
    def write(name,value): package.write(out/name,encoded(value))
    keep=None
    try:
        need(run(['git','rev-parse','HEAD'])==os.environ['GITHUB_SHA'],'CHECKOUT_CHANGED')
        need(run(['git','rev-parse','HEAD^'])==os.environ['KW20_EXPECTED_PARENT'],'EXPECTED_PARENT_REQUIRED')
        need(run(['git','diff','--name-only','HEAD^','HEAD']).splitlines()==[WORKFLOW],'WORKFLOW_ONLY_ACTIVATION')
        plan=package.prepare(repo,temp/'kw20-validated-artifact',temp/'kw20-native-context')
        context=temp/'kw20-native-context';write('CONTEXT.json',{k:v for k,v in plan.items() if k!='expectedScenes'})
        approval=json.loads((HERE/'APPROVAL.json').read_bytes())
        need(approval['approved'] is True and approval['maxBuilds']==approval['maxPublications']==1 and approval['gpuStarts']==approval['renders']==0,'PREPARATION_ONLY_APPROVAL')
        need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST,'PRESERVED_TAG_CHANGED')
        tag_name='kw20-native-v11-'+os.environ['GITHUB_RUN_ID'];target=package.IMAGE+':'+tag_name;common.absent(tag_name)
        need(['driver-type','io.containerd.snapshotter.v1'] in json.loads(docker('info','--format','{{json .DriverStatus}}')),'CONTAINERD_REQUIRED')
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>12*1024**3,'CAPACITY_REQUIRED')
        auth=temp/'kw20-docker-auth';auth.mkdir(mode=0o700);os.environ['DOCKER_CONFIG']=str(auth)
        run(['docker','--host=unix:///var/run/docker.sock','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GH_TOKEN'])
        write('PULL_ATTEMPT.json',{'attempt':1,'image':package.PARENT});docker_once(['pull',package.PARENT])
        parent=json.loads(docker('image','inspect',package.PARENT))[0]
        need(package.PARENT in parent.get('RepoDigests',[]),'PARENT_DIGEST_CHANGED')
        # The A1 controller PASS remains valid. Compare source bytes, never rerun it.
        receipt=json.loads((HERE/'RESUME_FROM_A1.json').read_bytes())
        prior=temp/'kw20-a1-evidence'
        evidence={}
        for name,expected_hash in receipt['files'].items():
            raw=(prior/name).read_bytes();need(sha(raw)==expected_hash,'A1_EVIDENCE_CHANGED:'+name)
            evidence[name]=json.loads(raw)
        need(evidence['CONTEXT.json']=={k:v for k,v in plan.items() if k!='expectedScenes'},'A1_PACKAGE_IDENTITY_CHANGED')
        for name in ('FORMAL_INPUT_CONNECTION.json','PREBUILD_GATE.json'):
            need(evidence[name]['status']=='PASS','A1_PASS_REQUIRED:'+name)
            write(name,evidence[name])
        write('REUSED_PASS.json',{'status':'PASS','sourceRun':receipt['runId'],'checksReexecuted':0,
            'scope':'Byte-identical parent, package and original formal input PASS','gpuStarts':0,'renders':0})
        need(shutil.disk_usage(docker('info','--format','{{.DockerRootDir}}')).free>parent['Size']*3+2*1024**3,'BACKUP_CAPACITY_REQUIRED')
        keep=module('_kw20_preserved_retention',repo/'world-simulation-shorts-engine/recovery/reference-label-quality-v1/retain_quality_image.py')
        keep.ROOT=temp/'kw20-native-backup';keep.ROOT.mkdir();keep.SOURCE=os.environ['GITHUB_SHA'];keep.PARENT=package.PARENT_DIGEST
        keep.RELEASE_TAG='kw20-native-image-backup-'+os.environ['GITHUB_RUN_ID']
        release=keep.api(keep.API+'/releases',{'tag_name':keep.RELEASE_TAG,'target_commitish':keep.SOURCE,
            'name':'Korean War native generator image '+os.environ['GITHUB_RUN_ID'],
            'body':'Formal generator deployment preparation only. Existing source/input PASS preserved. No GPU or movie rendered. Includes complete image backup and exact two Studio inputs.',
            'draft':False,'prerelease':True,'make_latest':'false'})
        keep.write('RELEASE.json',release);keep.write('RESERVATION.json',approval)
        reservation=keep.upload(release,keep.ROOT/'RESERVATION.json')
        keep.write('RESERVATION_RESULT.json',{'status':'PASS','releaseURL':release['html_url'],'asset':reservation})
        keep.upload(release,keep.ROOT/'RESERVATION_RESULT.json')
        # Preserve the exact existing source artifact members before building.
        for name in ('VIEWPORT_OVERLAY.zip','VIEWPORT_SOURCE_SEAL.json','KW20_PINNED_SOURCE_CROP.zip','KOREAN_WAR_20S_PART_01.json','KOREAN_WAR_20S_PART_02.json'):
            keep.upload(release,temp/'kw20-validated-artifact'/name)
        local='world-engine-kw20-native:unpublished-'+os.environ['GITHUB_RUN_ID'];os.environ['TAG']=local
        write('BUILD_ATTEMPT.json',{'attempt':1,'tag':local})
        docker_once(['build','--platform','linux/amd64','--provenance=false','--sbom=false','--network','none','--pull=false','-t',local,str(context)])
        candidate=json.loads(docker('image','inspect',local))[0]
        expected=dict(parent['Config']);expected['Entrypoint']=plan['entrypoint']
        need(candidate['Config']==expected,'ONLY_STARTUP_HASH_CONFIG_CHANGE')
        need(candidate['RootFS']['Layers'][:-1]==parent['RootFS']['Layers'],'ONE_ADDITIVE_LAYER_REQUIRED')
        # Packaging check only, no second controller compilation.
        write('INSTALLED_SOURCE.json',probe(local,plan,'installed-package'))
        keep.archive();retained=keep.read('RETENTION_RESULT.json')
        need(retained['status']=='PASS' and retained['archiveRootDigest']==candidate['Id'] and retained['rootFSDiffIDs']==candidate['RootFS']['Layers'],'BACKUP_IDENTITY')
        common.absent(tag_name);need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST,'PRESERVED_TAG_CHANGED')
        docker('tag',local,target);write('PUBLICATION_ATTEMPT.json',{'attempt':1,'tag':target})
        docker_once(['push',target])
        raw,digest=common.registry(tag_name);pinned,confirmed=common.registry(digest);manifest=json.loads(raw)
        need(raw==pinned and digest==confirmed==candidate['Id']==retained['archiveRootDigest'],'REMOTE_DIGEST_IDENTITY')
        if 'manifests' in manifest:
            need(len(manifest['manifests'])==1 and manifest['manifests'][0]['digest']==retained['imageManifestDigest'],'SINGLE_PLATFORM_IDENTITY')
            manifest=json.loads(common.registry(retained['imageManifestDigest'])[0])
        need(manifest['config']['digest']==retained['configDigest'],'REMOTE_CONFIG_IDENTITY')
        need(common.registry(OLD_TAG)[1]==package.PARENT_DIGEST,'OLD_TAG_PRESERVED')
        write('RESULT.json',{'schema':'WORLD_ENGINE_KW20_NATIVE_DEPLOYMENT_IMAGE_V11','status':'PASS',
            'tag':target,'digest':digest,'sourceCommit':os.environ['GITHUB_SHA'],'imageBackup':release['html_url'],
            'parentImage':package.PARENT,'oldTagPreserved':True,'addedLayers':1,'runtimeManifestSHA256':plan['runtimeManifestSHA256'],
            'builds':1,'publications':1,'gpuStarts':0,'renders':0,'oldPASSReruns':0,'automaticRetries':0,
            'formalKoreanInputConnection':'PASS_REUSED_FROM_42344924914','reusedControllerPassRun':42344924914,'actualGcubeMountReadback':False,'generatorMP4Quality':'NOT_RUN_USER_EXECUTES'})
    except Exception as error:
        write('BLOCKED.json',{'status':'BLOCKED','errorType':type(error).__name__,
            'reason':str(error) if isinstance(error,RuntimeError) else 'COMMAND_OR_SERVICE_FAILURE','gpuStarts':0,'renders':0,'automaticRetries':0})
        raise
    finally:
        for path in sorted(out.glob('*.json')):
            if keep is not None:
                try: keep.upload(keep.read('RELEASE.json'),path)
                except Exception: print('EVIDENCE_RELEASE_UPLOAD_FAILED:'+path.name,flush=True)
        print('EVIDENCE_DIRECTORY='+str(out),flush=True)

if __name__=='__main__': main()
