"""Prepare exact registry bytes, then one scoped publication; never build images.

Default policy is DRAFT and blocks before the reused build steps. This CLI must
not be executed by preparation tests; all process/network effects are injected.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_surface_publication_contract', HERE / 'publish_contract.py')
contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
PARENT_DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
SUCCESS_REPO = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
CANDIDATE_REPO = 'ghcr.io/dimon3898-sys/world-engine-vulkan-surface-candidates'
SUCCESS_TAG = SUCCESS_REPO + ':g2-diagnostics-v1-27f9fa5c133a-40767632198'
SAFE_FILES = {'PUBLICATION_PREFLIGHT.json', 'REGISTRY_READY.json', 'PUBLISH_INTENT.json', 'PUBLISH_RECEIPT.json', 'PUBLISH_FAILURE.json'}

def require(value, code):
    if not value: raise RuntimeError(code)

def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()

def load(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024**2, 'BOUNDED_JSON_REQUIRED')
    return json.loads(path.read_bytes())

def write(path, value):
    path = Path(path); raw = (json.dumps(value, sort_keys=True, indent=2)+'\n').encode()
    require(len(raw) <= 1024**2, 'PUBLICATION_EVIDENCE_TOO_LARGE')
    temporary = path.with_name('.'+path.name+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.chmod(temporary, 0o600); os.replace(temporary, path)

def clean_env():
    result = dict(os.environ)
    for name in ('SURFACE_CANDIDATE_GHCR_TOKEN', 'SURFACE_CANDIDATE_GHCR_USER',
                 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH',
                 'REGISTRY_AUTH_FILE'):
        result.pop(name, None)
    return result

def command(args, *, seconds=60, allow_failure=False):
    result = subprocess.run(args, env=clean_env(), stdin=subprocess.DEVNULL,
        capture_output=True, timeout=seconds)
    require(len(result.stdout) <= 2*1024**2, 'PUBLICATION_COMMAND_OUTPUT_TOO_LARGE')
    if not allow_failure: require(result.returncode == 0, 'PUBLICATION_COMMAND_FAILED')
    return result

def policy_gate(policy, env):
    require(policy.get('schema') == 'WORLD_ENGINE_SURFACE_PUBLISH_POLICY_V1'
        and policy.get('status') == 'APPROVED_FOR_SEPARATE_MANUAL_RUN'
        and policy.get('publicationApprovalRecorded') is True, 'PUBLICATION_POLICY_NOT_AUTHORIZED')
    require(policy.get('candidateRepository') == CANDIDATE_REPO
        and policy.get('successfulRepository') == SUCCESS_REPO
        and policy.get('parentDigest') == PARENT_DIGEST, 'PUBLICATION_NAMESPACE_OR_PARENT_INVALID')
    require(policy.get('publisherCanWriteSuccessfulPackage') is False
        and policy.get('publisherCanDeleteSuccessfulPackage') is False
        and policy.get('credentialHasDeleteScope') is False
        and policy.get('candidatePackageExclusiveWriterVerified') is True
        and re.fullmatch('[a-f0-9]{64}', policy.get('aclEvidenceSHA256') or '')
        and isinstance(policy.get('publisherIdentity'), str) and policy['publisherIdentity'],
        'PUBLISHER_ACL_PROOF_REQUIRED')
    require(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}', policy['publisherIdentity'])
        and policy['publisherIdentity'].lower() != 'dimon3898-sys',
        'CANDIDATE_ONLY_NON_OWNER_PUBLISHER_REQUIRED')
    require(isinstance(policy.get('approvedSkopeoVersion'),str) and policy['approvedSkopeoVersion'],
        'REVIEWED_SKOPEO_VERSION_REQUIRED')
    expected = {'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_RUN_ATTEMPT':'1','GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free',
        'GITHUB_REF':'refs/heads/recovery/g1-capture-diagnostic-contract-20261028',
        'RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64',
        'PUBLICATION_APPROVAL':'PUBLISH_VERIFIED_SURFACE_CANDIDATE_ONCE',
        'SIGNAL_APPROVAL':'BUILD_SURFACE_CANDIDATE_LOCAL_ONLY','ZERO_COST_CONFIRMED':'true'}
    require(all(env.get(k)==v for k,v in expected.items()), 'MANUAL_PUBLICATION_APPROVAL_REQUIRED')
    require(re.fullmatch('[a-f0-9]{40}', env.get('APPROVED_HEAD_SHA',''))
        and env['APPROVED_HEAD_SHA']==env.get('GITHUB_SHA'), 'PUBLICATION_REVIEWED_HEAD_REQUIRED')
    require(re.fullmatch('[0-9]+',env.get('GITHUB_RUN_ID','')), 'PUBLICATION_RUN_ID_REQUIRED')

def verify_tool(policy, work):
    tool=shutil.which('skopeo'); require(tool, 'SKOPEO_NOT_AVAILABLE_NO_INSTALL_OR_BUILD')
    version=command([tool,'--version']).stdout.decode().strip()
    require(version==policy['approvedSkopeoVersion'], 'SKOPEO_VERSION_CHANGED')
    help_text=command([tool,'copy','--help']).stdout.decode()
    require(all(flag in help_text for flag in ['--preserve-digests','--retry-times','--dest-compress','--format']), 'SKOPEO_REQUIRED_FLAGS_MISSING')
    inspect_help=command([tool,'inspect','--help']).stdout.decode()
    require('--retry-times' in inspect_help and '--raw' in inspect_help, 'SKOPEO_INSPECT_FLAGS_MISSING')
    data=Path(tool).read_bytes()
    return {'path':str(Path(tool).resolve()),'version':version,'binarySHA256':digest(data)}

def claim(work,name):
    require(not (work/'evidence/PUBLISH_FAILURE.json').exists(),'PUBLICATION_ALREADY_BLOCKED')
    with (work/'attempts'/name).open('x') as stream: stream.write('1\n')

def skopeo(work):
    info=load(work/'evidence/PUBLICATION_PREFLIGHT.json')['tool']
    tool=Path(info['path'])
    require(digest(tool.read_bytes())==info['binarySHA256'], 'SKOPEO_BINARY_CHANGED')
    return str(tool)

def receipts(build_work):
    return {name:load(build_work/'evidence'/(name+'.json')) for name in
        ['PREFLIGHT','BUILD','CONNECTION_VERIFY','IMAGE_SCOPE','STAGE_RECEIPT']}

def inspect_raw(tool, reference, authfile, *, absent_allowed=False):
    # All references are constructed from fixed repositories, never job input.
    require(reference.startswith(CANDIDATE_REPO+':') or reference.startswith(CANDIDATE_REPO+'@')
            or reference in (SUCCESS_TAG,SUCCESS_REPO+'@'+PARENT_DIGEST), 'REGISTRY_REFERENCE_FORBIDDEN')
    result=command([tool,'--command-timeout=45s','inspect','--retry-times=0',
        '--authfile',str(authfile),'--raw','docker://'+reference],seconds=50,allow_failure=absent_allowed)
    if result.returncode:
        # Any auth/network/ambiguous error is NOT evidence that a tag is absent.
        error=result.stderr.decode(errors='replace').lower()
        require(absent_allowed and 'manifest unknown' in error
            and not any(x in error for x in ['unauthorized','denied','forbidden','timeout']),
            'REGISTRY_ABSENCE_NOT_PROVEN')
        return None
    require(0<len(result.stdout)<=1024**2, 'REGISTRY_MANIFEST_SIZE_INVALID')
    return result.stdout

def preflight(work,build_work):
    work.mkdir(mode=0o700)
    for name in ('evidence','private','attempts'): (work/name).mkdir(mode=0o700)
    claim(work,'preflight')
    require('SURFACE_CANDIDATE_GHCR_TOKEN' not in os.environ
        and 'SURFACE_CANDIDATE_GHCR_USER' not in os.environ, 'WRITE_CREDENTIAL_TOO_EARLY')
    policy=load(HERE/'PUBLISH_POLICY.json'); policy_gate(policy,os.environ)
    tool=verify_tool(policy,work)
    write(work/'private/anonymous-auth.json',{'auths':{}})
    write(work/'evidence/PUBLICATION_PREFLIGHT.json',{'status':'PASS','tool':tool,
        'policySHA256':digest((HERE/'PUBLISH_POLICY.json').read_bytes()),
        'aclEvidenceSHA256':policy['aclEvidenceSHA256'],'candidateRepository':CANDIDATE_REPO,
        'successfulPackageWriteAllowed':False,'deleteScopeAllowed':False,
        'reviewedHead':os.environ['GITHUB_SHA'],'registryWrites':0,'gpuExecuted':False})

def prepare(work,build_work):
    claim(work,'prepare'); pre=load(work/'evidence/PUBLICATION_PREFLIGHT.json')
    require(pre.get('status')=='PASS','PUBLICATION_PREFLIGHT_NOT_PASS')
    require(not (build_work/'evidence/FAILURE.json').exists(),'BUILD_OR_VERIFICATION_FAILED')
    evidence=receipts(build_work); contract.validate_evidence(evidence,reviewed_head=os.environ['GITHUB_SHA'])
    image_id=evidence['BUILD']['candidateImageID']; tag=evidence['BUILD']['candidateTag']
    image=json.loads(command(['docker','--host=unix:///var/run/docker.sock','image','inspect',image_id]).stdout)[0]
    require(image['Id']==image_id,'VERIFIED_LOCAL_IMAGE_CHANGED')
    tagged=json.loads(command(['docker','--host=unix:///var/run/docker.sock','image','inspect',tag]).stdout)[0]
    require(tagged['Id']==image_id,'BUILD_PUBLISH_TAG_NOT_TESTED_IMAGE')
    need=2*image['Size']+2*1024**3
    require(shutil.disk_usage(work).free>=need,'INSUFFICIENT_REGISTRY_EXPORT_CAPACITY')
    tool=skopeo(work); anonymous=work/'private/anonymous-auth.json'
    parent_before=inspect_raw(tool,SUCCESS_TAG,anonymous)
    parent_addressed=inspect_raw(tool,SUCCESS_REPO+'@'+PARENT_DIGEST,anonymous)
    require(digest(parent_before)==digest(parent_addressed)==PARENT_DIGEST,'SUCCESSFUL_TAG_BASELINE_CHANGED')
    (work/'private/parent-before.json').write_bytes(parent_before)
    # Docker-daemon -> compressed dir transport. No second image build.
    layout=work/'registry-ready'
    command([tool,'--command-timeout=4m','copy','--retry-times=0','--format=oci','--dest-compress',
        '--src-daemon-host=unix:///var/run/docker.sock','docker-daemon:'+tag,'dir:'+str(layout)],seconds=250)
    verified=contract.validate_registry_ready(layout,image_id,expected_diff_ids=image['RootFS']['Layers'])
    destination=contract.candidate_destination(os.environ['GITHUB_RUN_ID'],1,os.environ['GITHUB_SHA'])
    write(work/'private/build-evidence.json',evidence)
    write(work/'private/expected-diffids.json',image['RootFS']['Layers'])
    write(work/'evidence/REGISTRY_READY.json',{'status':'PASS','destination':destination,
        'expectedRegistryDigest':verified['expectedRegistryDigest'],'candidateImageID':image_id,
        'sourceReviewedHead':os.environ['GITHUB_SHA'],'evidenceSHA256':digest(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()),
        'layerCount':verified['layerCount'],'exportCapacityEstimateBytes':need,
        'successfulTagBeforeDigest':PARENT_DIGEST,'registryWrites':0,'gpuExecuted':False})

def publish(work,build_work):
    claim(work,'publish')
    policy=load(HERE/'PUBLISH_POLICY.json');policy_gate(policy,os.environ)
    pre=load(work/'evidence/PUBLICATION_PREFLIGHT.json')
    require(pre['policySHA256']==digest((HERE/'PUBLISH_POLICY.json').read_bytes()),'PUBLISH_POLICY_CHANGED')
    ready=load(work/'evidence/REGISTRY_READY.json');require(ready.get('status')=='PASS','REGISTRY_READY_NOT_PASS')
    require(not (build_work/'evidence/FAILURE.json').exists(),'BUILD_OR_VERIFICATION_FAILED')
    evidence=receipts(build_work);contract.validate_evidence(evidence,reviewed_head=os.environ['GITHUB_SHA'])
    require(ready['candidateImageID']==evidence['BUILD']['candidateImageID'],
        'PUBLISH_READY_BUILD_CONNECTION_CHANGED')
    require(digest(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode())==ready['evidenceSHA256'],'VALIDATION_RECEIPTS_CHANGED')
    destination=contract.validate_destination(ready['destination'],os.environ['GITHUB_RUN_ID'],1,os.environ['GITHUB_SHA'])
    tool=skopeo(work);layout=work/'registry-ready'
    checked=contract.validate_registry_ready(layout,ready['candidateImageID'],expected_diff_ids=load(work/'private/expected-diffids.json'))
    require(checked['expectedRegistryDigest']==ready['expectedRegistryDigest'],'REGISTRY_READY_BYTES_CHANGED')
    user=os.environ.get('SURFACE_CANDIDATE_GHCR_USER','');token=os.environ.get('SURFACE_CANDIDATE_GHCR_TOKEN','')
    require(user==policy['publisherIdentity'] and token and not any(c in user+token for c in '\r\n\0'),'PUBLISHER_CREDENTIAL_REQUIRED')
    # Credentials exist only in this step and a fresh private authfile, excluded
    # from all build contexts, evidence bundles, argv values and image layers.
    with tempfile.TemporaryDirectory(prefix='publisher-auth-',dir=work/'private') as tmp:
        auth=Path(tmp)/'auth.json'
        write(auth,{'auths':{'ghcr.io':{'auth':base64.b64encode((user+':'+token).encode()).decode()}}})
        old=inspect_raw(tool,destination,auth,absent_allowed=True)
        parent_before=inspect_raw(tool,SUCCESS_TAG,work/'private/anonymous-auth.json')
        contract.validate_publish_preconditions(destination,os.environ['GITHUB_RUN_ID'],1,os.environ['GITHUB_SHA'],
            tag_exists=old is not None,parent_manifest_raw=parent_before)
        # Record mutation intent BEFORE the single transfer; never retry even
        # if timeout leaves remote state ambiguous. No remote delete/rollback.
        write(work/'private/mutation-intent.json',{'attempt':1,'destination':destination})
        intent={'status':'MUTATION_PENDING_UNCONFIRMED','destination':destination,
            'expectedRegistryDigest':ready['expectedRegistryDigest'],'candidateImageID':ready['candidateImageID'],
            'pushAttempts':1,'retryCount':0,'gpuExecuted':False}
        write(work/'evidence/PUBLISH_INTENT.json',intent)
        print('SURFACE_PUBLICATION_INTENT='+json.dumps(intent,sort_keys=True,separators=(',',':')),flush=True)
        digestfile=work/'private/pushed.digest'
        command([tool,'--command-timeout=8m','copy','--retry-times=0','--preserve-digests',
            '--dest-authfile',str(auth),'--digestfile',str(digestfile),'dir:'+str(layout),'docker://'+destination],seconds=490)
        require(digestfile.read_text().strip()==ready['expectedRegistryDigest'],'TRANSFER_DIGEST_MISMATCH')
        tag_raw=inspect_raw(tool,destination,auth)
        raw_addressed=inspect_raw(tool,CANDIDATE_REPO+'@'+ready['expectedRegistryDigest'],auth)
        parent_after=inspect_raw(tool,SUCCESS_TAG,work/'private/anonymous-auth.json')
        contract.validate_registry_readback(ready['expectedRegistryDigest'],ready['candidateImageID'],
            tag_raw,raw_addressed,parent_before,parent_after)
        write(work/'evidence/PUBLISH_RECEIPT.json',{'status':'PASS','scope':'REGISTRY_RETENTION_ONLY_NOT_GPU_INITIALIZATION',
            'destination':destination,'registryDigest':ready['expectedRegistryDigest'],
            'candidateImageID':ready['candidateImageID'],'tagAndDigestBodyMatched':True,
            'successfulTagBeforeDigest':PARENT_DIGEST,'successfulTagAfterDigest':PARENT_DIGEST,
            'pushAttempts':1,'retryCount':0,'oldPackageWriteRequests':0,'deleteRequests':0,'gpuExecuted':False})

def collect(work):
    entries=[]
    for name in sorted(SAFE_FILES):
        p=work/'evidence'/name
        if not p.exists():continue
        require(p.is_file() and not p.is_symlink() and p.stat().st_size<=65536,'PUBLICATION_SAFE_FILE_INVALID')
        raw=p.read_bytes();json.loads(raw)
        entries.append({'name':name,'sha256':digest(raw),'base64':base64.b64encode(raw).decode()})
    raw=json.dumps({'schema':'WORLD_ENGINE_SURFACE_PUBLISH_LOG_EVIDENCE_V1','files':entries},separators=(',',':'))
    require(len(raw)<=512*1024,'PUBLICATION_SAFE_BUNDLE_LIMIT')
    for i in range(0,len(raw),3000):print('SURFACE_PUBLICATION_EVIDENCE_CHUNK='+raw[i:i+3000])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['preflight','prepare','publish','collect']);parser.add_argument('--work',required=True)
    args=parser.parse_args();require(os.environ.get('GITHUB_ACTIONS')=='true','ACTIONS_ONLY_NO_LOCAL_PUBLICATION')
    workspace=Path(os.environ['GITHUB_WORKSPACE']).resolve()
    require(args.work=='surface-publish-work','FIXED_PUBLISH_WORKSPACE_REQUIRED')
    work=workspace/args.work;build_work=workspace/'surface-candidate-work'
    require(not work.is_symlink() and not build_work.is_symlink(),'PUBLISH_WORKSPACE_SYMLINK_FORBIDDEN')
    if args.stage=='collect':collect(work);return
    try:globals()[args.stage](work,build_work)
    except Exception as error:
        if (work/'evidence').is_dir():
            message=str(error);code=message if re.fullmatch('[A-Z][A-Z0-9_]{1,120}',message) else 'PUBLICATION_STAGE_FAILED'
            write(work/'evidence/PUBLISH_FAILURE.json',{'status':'BLOCKED','stage':args.stage,'code':code,
                'errorType':type(error).__name__,'retryCount':0,
                'mutationAttempted':(work/'private/mutation-intent.json').exists(),
                'remoteState':'UNKNOWN_IF_MUTATION_ATTEMPTED; NO_RETRY_OR_DELETE','gpuExecuted':False})
        raise SystemExit('PUBLICATION_BLOCKED_'+args.stage.upper()) from None

if __name__=='__main__':main()
