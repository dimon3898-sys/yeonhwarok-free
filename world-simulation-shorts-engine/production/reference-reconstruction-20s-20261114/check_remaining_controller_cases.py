"""Previously uncovered malformed 600-frame inputs through the real controller.
No positive normalization rerun, no submit/start/backend/render operation.
"""
import copy, hashlib, json, sys, tempfile
from pathlib import Path
P=Path(__file__).resolve().parent; R=P.parents[2]; H=R/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1'
sys.path.insert(0,str(H/'controller'))
from nvidia_controller import NvidiaPresentationController
raw=(P/'FINAL_20S_INPUT.json').read_bytes(); source=json.loads(raw); checks=[]
manifest=H/'RUNTIME_SOURCE_MANIFEST.json'; pin=hashlib.sha256(manifest.read_bytes()).hexdigest()
cases=[
 ('DURATION_MISMATCH',lambda x:x['prompt']['output'].update(durationSeconds=10),'UP2_HISTORY_EXACT_600_OUTPUT_REQUIRED'),
 ('FPS_MISMATCH',lambda x:x['prompt']['output'].update(fps=24),'UP2_HISTORY_EXACT_600_OUTPUT_REQUIRED'),
 ('MISSING_HISTORY_SOURCE',lambda x:x['prompt'].pop('source'),'UP2_HISTORY_INPUT_FIELDS'),
 ('BAD_GEOMETRY_REFERENCE',lambda x:x['prompt']['source'].update(continuousSHA256='0'*64),'UP2_HISTORY_SOURCE_REFERENCE_CHANGED'),
 ('MISSING_CAMERA',lambda x:x['prompt']['presentation'].pop('camera'),'UP2_HISTORY_PRESENTATION_FIELDS'),
 ('MISSING_MAP_STYLE',lambda x:x['prompt']['presentation'].pop('mapStyle'),'UP2_HISTORY_PRESENTATION_FIELDS'),
 ('TERRITORY_OUT_OF_RANGE',lambda x:x['prompt']['timing'].update(territoryEndFrame=601),'UP2_HISTORY_TIMING_RANGE'),
 ('DOWNCAST_180',lambda x:x['prompt']['output'].update(durationSeconds=6,totalFrames=180),'UP2_HISTORY_EXACT_600_OUTPUT_REQUIRED'),
 ('DOWNCAST_300',lambda x:x['prompt']['output'].update(durationSeconds=10,totalFrames=300),'UP2_HISTORY_EXACT_600_OUTPUT_REQUIRED'),
 ('UNALLOWED_WRAPPER_PROFILE',lambda x:x.update(profile='UNKNOWN'),'HANDOFF_EXPLICIT_NVIDIA_PRESENTATION_REQUEST_REQUIRED'),
 ('CALLER_INPUT_HASH_FORBIDDEN',lambda x:x.update(inputSHA256='0'*64),'HANDOFF_EXPLICIT_NVIDIA_PRESENTATION_REQUEST_REQUIRED'),
]
with tempfile.TemporaryDirectory(prefix='history-controller-negative-') as tmp:
 root=Path(tmp); c=NvidiaPresentationController(control_root=root/'private',export_root=root/'exports',image_digest='sha256:'+'a'*64,source_manifest=manifest,expected_manifest_sha256=pin)
 for name,edit,expected in cases:
  x=copy.deepcopy(source);edit(x)
  try:c._normal(x)
  except Exception as e:
   actual=getattr(e,'code',str(e));assert actual==expected,(name,actual,expected)
   checks.append({'name':name,'status':'PASS','errorCode':actual,'reason':name.replace('_',' ').lower()})
  else:raise AssertionError('Malformed input accepted: '+name)
 assert not list(root.rglob('authorization.json')) and not list(root.rglob('*-crop'))
report={'schema':'WORLD_ENGINE_REMAINING_CONTROLLER_CASES_V1','status':'PASS','checks':checks,'inputSHA256':hashlib.sha256(raw).hexdigest(),'manifestSHA256':pin,'gpuStarts':0,'renderersExecuted':0,'positiveNormalizationReruns':0,'oldPassReruns':0}
(P/'REMAINING_CONTROLLER_CASES.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'PASS','newControllerRejections':len(checks)}))
