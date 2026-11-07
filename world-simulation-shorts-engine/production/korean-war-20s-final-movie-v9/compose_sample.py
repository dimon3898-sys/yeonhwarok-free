"""Validate the four actual scene receipts and call the unchanged frame-verifying composer."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--artifacts',required=True,type=Path)
parser.add_argument('--destination',required=True,type=Path)
parser.add_argument('--source-commit',required=True)
args=parser.parse_args()
here=Path(__file__).resolve().parent
source=here.parents[1]/'recovery/universal-auto-video-v2/compose.py'
spec=importlib.util.spec_from_file_location('existing_world_engine_composer',source)
composer=importlib.util.module_from_spec(spec);spec.loader.exec_module(composer)
expected={1:'5a80189cee9e6930671a80c56c1f46021101d8ffd7e23b773c900c7e7c68adaf',2:'53a618173b3e07c572a3104548979c857a3c081d165ce70c4fc01ff51f3e8c77'}
rows=[];newFrames=0;reusedFrames=0;allFrames=[]
for receiptPath in args.artifacts.rglob('CHUNK_RECEIPT.json'):
    receipt=json.loads(receiptPath.read_bytes())
    assert receipt['status']=='PASS_ACTUAL_150_ORDERED_FRAMES_ENCODED'
    assert receipt['inputSHA256']==expected[receipt['clip']]
    assert receipt['runtimeManifestSHA256']=='f007273ae3dbb4ddead292e0c325b9a16eb7fb2680133d96ac8c3cb0cc14eab1'
    matches=list(args.artifacts.rglob(receipt['file']))
    assert len(matches)==1
    video=matches[0].resolve()
    assert composer.digest_file(video)==receipt['sha256']
    run=json.loads((receiptPath.parent/'RUN_RESULT.json').read_bytes())
    assert run['status']=='PASS' and run['sourceCommit']==args.source_commit
    sequence=json.loads((receiptPath.parent/'PNG_SEQUENCE.json').read_bytes())['frames']
    assert [x['frame'] for x in sequence]==list(range(receipt['startFrame'],receipt['endFrame']))
    allFrames.extend((receipt['clip']-1)*300+x['frame'] for x in sequence)
    newFrames+=receipt['newFrames'];reusedFrames+=len(receipt['reusedFrames'])
    rows.append({'sceneId':f'clip-{receipt["clip"]:02d}-start-{receipt["startFrame"]:03d}','startFrame':receipt['globalStartFrame'],'endFrame':receipt['globalEndFrame'],'path':str(video),'sha256':receipt['sha256']})
rows.sort(key=lambda r:r['startFrame'])
assert len(rows)==4 and newFrames==594 and reusedFrames==6
assert sorted(allFrames)==list(range(600)),'FULL_SAMPLE_FRAME_COVERAGE'
plan={'schema':'WORLD_ENGINE_NEUTRAL_VIDEO_PLAN_V1','durationSeconds':20,'fps':30,'resolution':{'width':1080,'height':1920},'scenes':[{k:r[k] for k in ['sceneId','startFrame','endFrame']} for r in rows]}
result=composer.compose_segments(plan,rows,args.destination)
proof={'producer':'UNCHANGED_TEN_SECOND_RUNTIME_EXECUTED_AT_ITS_FOUR_SCENE_RESET_BOUNDARIES','newFrames':newFrames,'reusedFrames':reusedFrames,'totalFrames':600,'sourceInputSHA256':expected,'paidGpuExecutions':0,'imageBuilds':0,'oldPassSuitesRerun':0,'technical':result['technical'],'compositionReceipt':result['receiptPath'],'outputSHA256':result['sha256'],'visualQualityPass':False}
(args.destination/'SOURCE_AND_REUSE_RECEIPT.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['path','status','sha256','frames','technical','quality']},indent=2))
