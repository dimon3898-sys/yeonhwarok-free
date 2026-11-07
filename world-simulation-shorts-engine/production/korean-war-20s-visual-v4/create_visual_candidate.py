"""Create a separate data-only visual candidate; never modify protected inputs."""
import json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'korean-war-20s-detail-v2'
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(name,data):
    target=HERE/name
    with target.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
seal=json.loads((OLD/'SOURCE_SEAL.json').read_bytes())
receipt={'schema':'WORLD_ENGINE_KW20_DATA_ONLY_VISUAL_CHANGE_V1','reason':'Observed actual V2 pixels too dark; geographic emphasis weaker than reference.','sourceCommit':'ceee49fc512074e33179344663b02367c3e875d6','priorPixelsRun':42336067180,'runtimeChanged':False,'sourceDataChanged':False,'oldPassSuitesRerun':0,'clips':[]}
inputs=[]
for i in (1,2):
    name=f'KOREAN_WAR_20S_PART_{i:02d}.json'
    original=json.loads((OLD/name).read_bytes())
    candidate=json.loads((OLD/name).read_bytes())
    for presentation in [candidate['presentation'],*candidate['presentation']['sceneOverrides'].values()]:
        for key,rgba in presentation['territoryColors'].items():
            assert rgba==[1,.80,.10,.18]
            presentation['territoryColors'][key]=[1,.80,.10,.52]
    assert candidate['data']==original['data'] and candidate['region']==original['region']
    write(name,candidate)
    raw=(HERE/name).read_bytes()
    inputs.append({'path':str((HERE/name).relative_to(ROOT)),'bytes':len(raw),'sha256':sha(raw)})
    receipt['clips'].append({'clip':i,'originalSHA256':sha((OLD/name).read_bytes()),'newSHA256':sha(raw),'onlyChange':'Existing territoryColors alpha 0.18 -> 0.52; existing supported maximum 0.60','factsRegionCameraLabelsTimingUnchanged':True})
seal['inputs']=inputs
seal['schema']='WORLD_ENGINE_KW20_VISUAL_SOURCE_SEAL_V4'
seal['sourceBaseCommit']='66657645850eff36e6c6b5f90c78a74dc401256a'
write('SOURCE_SEAL.json',seal);write('VISUAL_CHANGE_RECEIPT.json',receipt)
print(json.dumps(receipt))
