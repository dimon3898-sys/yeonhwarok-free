"""Verify a prior successful new normalization's private cache/submission roundtrip.
No browser, GPU preflight, submit endpoint, start method or real authorization.
"""
from pathlib import Path
import argparse,hashlib,json,sys
P=Path(__file__).resolve().parent;E=P.parents[1];R=E.parent;H=E/'recovery/codex-to-gcube-handoff-v1'
sys.path.insert(0,str(H/'controller'))
from nvidia_controller import NvidiaPresentationController
from common import validate_plan,canonical
parser=argparse.ArgumentParser();parser.add_argument('--private',required=True);parser.add_argument('--exports',required=True);parser.add_argument('--normalized',required=True);args=parser.parse_args()
manifest=H/'RUNTIME_SOURCE_MANIFEST.json';sha=lambda b:hashlib.sha256(b).hexdigest();pin=sha(manifest.read_bytes());digest='sha256:'+'a'*64
private,exports=Path(args.private),Path(args.exports);prior=json.loads(Path(args.normalized).read_text())
c=NvidiaPresentationController(control_root=private,export_root=exports,image_digest=digest,source_manifest=manifest,expected_manifest_sha256=pin)
# Existing source-cache identity must be reused. A fresh crop would fail EEXIST.
cache_before=sorted(str(x) for x in private.rglob('*-crop'))
out=c._normal(json.loads((P/'FINAL_20S_INPUT.json').read_text()));assert out==prior
assert sorted(str(x) for x in private.rglob('*-crop'))==cache_before
plan=out['videoPlan'];validate_plan(plan,image_digest=digest,source_sha=pin)
with c._cache.PrivateTree(c.control_root) as tree:
 with tree.lock(wait_seconds=8):
  identifier=c._save_submission(tree,out)
  saved=c._read_submission(tree,identifier)
  assert saved['submission']==out
assert not list(private.rglob('authorization.json'))
cachefiles=list(private.rglob('presentation-sources/*.json'));assert len(cachefiles)==1
cached=json.loads(cachefiles[0].read_text());assert cached['cacheFormat']=='HISTORY_PREPARED_WIRE_ONLY_V1' and 'prepared' not in cached
prepared=json.loads(cached['preparedWireJSON']);assert prepared['totalFrames']==600 and len(prepared['segments'][0]['presentation']['camera']['frames'])==600
source=prepared['segments'][0]['regionEvidence'];assert source['actualSourceBytesVerified'] is True and source['maximumOutputPixelsPerNativeTexel']<=1
report={'schema':'WORLD_ENGINE_600_CONTROLLER_TRANSPORT_V1','status':'PASS_NEW_CONTROLLER_AND_PRIVATE_CACHE_ONLY','checks':['REAL_CONTROLLER_HISTORICAL_NORMALIZATION','SOURCE_CACHE_ROUNDTRIP_WITHOUT_DUPLICATE_GEOMETRY','PRESERVED_STUDIO_SUBMISSION_SAVE_READ','ACTUAL_600_CAMERA_SOURCE_PREPARATION'],'profile':out['profile'],'simulationType':plan['simulationType'],'totalFrames':600,'durationSeconds':20,'inputJSONSHA256':sha((P/'FINAL_20S_INPUT.json').read_bytes()),'runtimeWireSHA256':plan['runtimeWireSHA256'],'runtimeWireBytes':len(plan['runtimeWireJSON'].encode()),'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'sourceClosureSHA256':pin,'sourceCacheBytes':cachefiles[0].stat().st_size,'genericJSONLimitBytes':c._cache.MAX_JSON,'maximumOutputPixelsPerNativeTexel':source['maximumOutputPixelsPerNativeTexel'],'terrainSource':source['sourceId'],'cameraFrames':600,'historicalAdmission':plan['historicalAdmission'],'testImageDigest':'SYNTHETIC_BINDING_ONLY_NOT_IMAGE_PROOF','GPUExecutions':0,'actualRendererExecutions':0,'authorizationCreated':False,'actualGPU':'PENDING_GPU'}
(P/'CONTROLLER_TRANSPORT_TESTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','totalFrames','sourceCacheBytes','runtimeWireBytes','maximumOutputPixelsPerNativeTexel']}))
