"""Invoke the existing verified composer on two new outputs; no new encoder."""
import importlib.util,json,hashlib,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('existing_compose',root/'recovery/universal-auto-video-v2/compose.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=Path(sys.argv[1]);plan=json.loads((out/'check/COMPOSE_PLAN.json').read_bytes())
segments=[]
for i in (1,2):
    p=out/f'clip-{i:02d}/CLIP_10S_CPU_PREVIEW.mp4'
    segments.append({'sceneId':f'clip-{i:02d}','startFrame':(i-1)*300,'endFrame':i*300,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
result=module.compose_segments(plan,segments,out/'composition')
(out/'COMPOSITION_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'frames':result['frames'],'mode':result['mode'],'path':result['path']}))
