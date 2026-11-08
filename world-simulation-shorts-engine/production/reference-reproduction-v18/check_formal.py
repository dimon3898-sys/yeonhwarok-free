"""New input admission through the preserved Studio controller. Never submit/start."""
import hashlib
import json
import sys
from pathlib import Path

root, inputs, output, control, exports = map(Path, sys.argv[1:6])
parts=[int(x) for x in sys.argv[6].split(',')] if len(sys.argv)>6 else [1,2]
assert parts and all(x in (1,2) for x in parts)
output.mkdir(parents=True, exist_ok=False)
control.mkdir(parents=True, mode=0o700, exist_ok=False)
exports.mkdir(parents=True, mode=0o755, exist_ok=True)
handoff=root/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1'
sys.path.insert(0,str(handoff/'controller'))
from nvidia_controller import NvidiaPresentationController

def save(name, obj):
    with (output/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
receipt={'status':'RUNNING','scope':'NEW_INPUTS_FORMAL_CONTROLLER_NORMALIZATION_ONLY',
         'runtimeManifestSHA256':'659654d1cdb3b1a004e80b4fd67baa7d1b2a750abec4b66fce141dae0d2f7fa5',
         'gpuStarts':0,'renders':0,'oldPASSReruns':0,'clips':[]}
try:
    controller=NvidiaPresentationController(control_root=control,export_root=exports,
        image_digest='sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b',
        source_manifest=handoff/'RUNTIME_SOURCE_MANIFEST.json',expected_manifest_sha256=receipt['runtimeManifestSHA256'])
    for part in parts:
        input_file=inputs/f'KOREAN_WAR_REFERENCE_CANDIDATE_PART_0{part}.json'
        raw=input_file.read_bytes();prompt=json.loads(raw)
        normalized=controller._normal({'schema':'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1','prompt':prompt,'sceneId':'__timeline__'})
        plan=normalized['videoPlan'];runtime=plan['runtime']
        assert plan['durationSeconds']==10 and plan['totalFrames']==300 and plan['fps']==30
        assert plan['simulationType']=='GENERAL'
        save(f'FORMAL_SCENES_{part}.json',[r['scene'] for r in runtime['segments']])
        save(f'REQUEST_{part}.json',runtime)
        # The existing controller has already admitted and verified this prepared payload.
        matches=[]
        for cached in control.rglob('*.json'):
            try:value=json.loads(cached.read_bytes())
            except (ValueError,OSError):continue
            if isinstance(value,dict) and value.get('admission',{}).get('sourceQualificationSHA256')==plan['sourceQualificationSHA256'] and 'prepared' in value:matches.append(value['prepared'])
        assert len(matches)==1, ('EXACT_PREPARED_CACHE_REQUIRED',len(matches))
        save(f'PREPARED_{part}.json',matches[0])
        receipt['clips'].append({'part':part,'inputSHA256':hashlib.sha256(raw).hexdigest(),
            'frames':300,'sceneIds':[x['sceneId'] for x in runtime['segments']],
            'sourceQualificationSHA256':plan['sourceQualificationSHA256'],
            'runtimeWireSHA256':plan['runtimeWireSHA256'],'status':'PASS'})
    receipt['status']='PASS_CHANGED_INPUT_FORMAL_ADMISSION'
except Exception as error:
    receipt.update(status='BLOCKED',error=str(error),errorType=type(error).__name__)
    raise
finally:save('FORMAL_RESULT.json',receipt)
