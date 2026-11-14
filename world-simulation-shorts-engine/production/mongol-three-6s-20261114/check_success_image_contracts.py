"""New HISTORICAL/180 compatibility check against pinned successful-image source.

No old success test, image execution, compilation of a video or GPU operation.
Only exact existing pure admission functions are extracted from immutable git blobs.
"""
from pathlib import Path
import ast, hashlib, json, subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
COMMON='world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/common.py'
MANIFEST='world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
CANDIDATES=[
 ('27f9fa5c133a65ed08824cf047116128bd9dfe5e','g2-diagnostics-v1-27f9fa5c133a-40767632198','sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'),
 ('f0f44d269b9ab5189019c696e9e5024e0e719215','required-fixes-f0f44d269b9a-43362382877','sha256:8f7a91201840b84769523ec4cd2430df54470403883d57c40e26d3d1e36ce329'),
 ('044bde9e8bc342b09d91ea71d62325f9f6f28226','quality-boundary-camera-044bde9e8bc3-43368976255','sha256:cf52ba25cb46b16b6bee0ba3149d1e8048a3d6a5abf05f1cfda932f7094665a8'),
 ('2c26a3bfa6e3d5669c5e251dd78677a4c697c2ff','quality-v2-2c26a3bfa6e3-43376804907','sha256:ed2ff287e7617b201876059210603e4f507632ca7143ae1768414364faf848ce')]

def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)

def main():
 rows=[]
 for commit,tag,digest in CANDIDATES:
  raw=blob(commit,COMMON);tree=ast.parse(raw);manifest=json.loads(blob(commit,MANIFEST));entry=next(x for x in manifest['files'] if x['path']==COMMON)
  assert hashlib.sha256(raw).hexdigest()==entry['sha256'] and len(raw)==entry['bytes']
  plan_schema=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PLAN' for t in n.targets))
  funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'validate_plan','duration_contract'}]
  ns={'PLAN':plan_schema};exec(compile(ast.Module(body=funcs,type_ignores=[]),COMMON,'exec'),ns)
  fixture={'schema':plan_schema,'totalFrames':180,'durationSeconds':6,'fps':30,'resolution':{'width':1080,'height':1920},'aspectRatio':'9:16','audioSettings':{'enabled':False,'mode':'SILENT'},'simulationType':'HISTORICAL'}
  try:ns['validate_plan'](fixture,image_digest=digest,source_sha=hashlib.sha256(blob(commit,MANIFEST)).hexdigest())
  except RuntimeError as error:code=str(error)
  else:raise AssertionError('Unexpected acceptance: inspect compatibility before continuing')
  assert code=='HANDOFF_EXACT_NONHISTORICAL_SIX_SECOND_PLAN_REQUIRED'
  absent=[]
  for path in ['world-simulation-shorts-engine/recovery/universal-presentation-v2/history_authored_v1.mjs','world-simulation-shorts-engine/production/continuous-territory-20261114/RUNTIME_REQUEST.json']:
   proc=subprocess.run(['git','cat-file','-e',commit+':'+path],cwd=ROOT,capture_output=True)
   absent.append({'path':path,'existsAtBuildCommit':proc.returncode==0})
  row={'sourceCommit':commit,'image':'ghcr.io/dimon3898-sys/world-simulation-shorts-engine:'+tag,'digest':digest,'sourceFile':COMMON,'sourceSHA256':entry['sha256'],'sourceMatchesBuildCommitManifest':True,'buildCommitRuntimeManifestSHA256':hashlib.sha256(blob(commit,MANIFEST)).hexdigest(),'testedScope':'NEW_HISTORICAL_6S_180_ADMISSION_ONLY_NO_OLD_PASS_TEST','fixtureIsProductionInput':False,'fixture':'All initial duration/resolution/audio/schema fields satisfy existing gate; simulationType HISTORICAL is rejected before runtime payload','result':'REJECTED','errorCode':code,'newHistoryArtifacts':absent}
  if tag.startswith('g2-'):
   published=ROOT/'world-simulation-shorts-engine/recovery/capture-diagnostics-g2-v1/evidence/ci-40767632198/RUNTIME_SOURCE_MANIFEST.json'
   published_entry=next(x for x in json.loads(published.read_bytes())['files'] if x['path']==COMMON)
   assert published_entry==entry
   row['publishedImageEvidence']={'manifestPath':str(published.relative_to(ROOT)),'runtimeManifestSHA256':hashlib.sha256(published.read_bytes()).hexdigest(),'sameAdmissionSourceHash':True}
  else:
   row['publishedImageEvidence']={'scope':'Build commit and its manifest; no new container inspection in this task'}
  rows.append(row)
 output={'schema':'WORLD_ENGINE_SIX_SECOND_SUCCESS_IMAGE_COMPATIBILITY_V1','status':'BLOCKED_HISTORICAL_180_NOT_SUPPORTED_BY_SUCCESS_IMAGES','candidates':rows,'oldPassReruns':0,'productionCodeChanges':0,'imageRuns':0,'GPUStarts':0,'rendererExecutions':0,'meaning':'Prior actual GPU success preserved; incompatibility applies only to newly requested Mongol HISTORICAL 180 input. Candidate success lineage strengths are detailed separately in SIX_SECOND_GPU_SUCCESS_BASELINE.md.'}
 (HERE/'SUCCESS_IMAGE_COMPATIBILITY.json').write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps({'status':output['status'],'newCompatibilityProbes':len(rows),'codes':[x['errorCode'] for x in rows],'GPUStarts':0}))

if __name__=='__main__':main()
