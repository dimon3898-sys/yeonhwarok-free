"""Verify actual observed frames and publish a new, accurately labelled preview."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parents[1]
PRESERVED=HERE.parent/'universal-overnight-v3'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')

def finalize(output,inputs,baseline,commit):
    output,inputs,baseline=map(Path,(output,inputs,baseline))
    receipt=read(output/'PREVIEW_RECEIPT.json')
    assert receipt['status']=='SOFTWARE_PREVIEW_TECHNICAL_PASS' and receipt['completedFrames']==150
    assert receipt['hardwareVerified'] is False and receipt['fullDecodeVerified'] is True
    trace=read(output/'RECONCILIATION_CAPTURE.json')
    assert trace['sourceCheckoutCommit']==commit
    rows=[json.loads(line) for line in (output/'FRAMES.ndjson').read_text().splitlines()]
    old={row['globalFrame']:row for row in map(json.loads,(baseline/'FRAMES.ndjson').read_text().splitlines())}
    r=receipt['range'];assert len(rows)==150 and r['endFrame']-r['startFrame']==150
    compact=[];camera=[];sample_count=0
    for index,row in enumerate(rows):
        frame=r['startFrame']+index;assert row['globalFrame']==frame and row['localFrame']==index
        d=row['diagnostic'];o=d['reconciliation'];assert d['frame']==frame==o['originalGlobalFrame']==o['frame']
        assert d['universalVideo']['globalFrame']==frame and d['sourceIntegrity']['fictional65422SceneUsed'] is False
        assert d['terrain']['astra']['gpuUploadExecuted'] and d['terrain']['astra']['actualMaterialFactorySelected']
        assert o['sourcePixelsModified'] is False and o['scalarSelected'] is False and o['nationalUnitsSelected'] is False
        assert all(o['executedDraws'][key]==o['instantiatedFactories'][key]==1 for key in
                   ('PRESERVED_V5_CAMERA','ASTRA_REFERENCE_SOURCE','SUPPLIED_AREA_FRONT'))
        b=old[frame];assert b['rawRgbaSha256']==row['rawRgbaSha256'] and b['pngSha256']==row['pngSha256']
        assert digest(output/'frames'/f'{index:06d}.png')==row['pngSha256']
        sampled=o['sampledForStagePixels'];sample_count+=sampled
        assert (len(o['pixelStages'])==3)==sampled
        if sampled:
            for stage in o['pixelStages']:
                assert len(stage['beforeRGBA_SHA256'])==len(stage['afterRGBA_SHA256'])==64
                assert (stage['beforeRGBA_SHA256']!=stage['afterRGBA_SHA256'])==(stage['changedPixels']>0)
        bounds=d['camera']['camera']['flatBounds'];camera.append({'frame':frame,'bounds':bounds})
        compact.append({'globalFrame':frame,'localFrame':index,'actualRGBA_SHA256':row['rawRgbaSha256'],
            'actualPNG_SHA256':row['pngSha256'],'cameraBounds':bounds,
            'instantiatedFactories':o['instantiatedFactories'],'executedDraws':o['executedDraws'],
            'pixelStages':o['pixelStages'],'sourceManifestSHA256':o['sourceBinding']['sourceManifestSHA256'],
            'preservedRawPixelsBitExact':True,'scalarSelected':False,'nationalUnitsSelected':False,
            'actualV5Turn':d['camera']['productionCamera']['completionV2'].get('actualV5Turn'),
            'globalClockPreserved':True,'physicalNvidiaVerified':False})
    assert sample_count==3
    spec=importlib.util.spec_from_file_location('_actual_trace_camera',HERE/'camera_pixel_activity.py')
    metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)
    measured=metric.assess_camera_activity(camera)
    assert measured['status']=='NUMERIC_SUBPIXEL_ONLY'
    sys.path.insert(0,str(PRESERVED))
    from preview_audio import render_preview_sfx,mux_preview_sfx
    plan=read(inputs/'PLAN.json');request=read(inputs/'PREVIEW_REQUEST.json');submission=read(inputs/'SUBMISSION.json')
    sfx=render_preview_sfx(submission['sfx'],plan,request,output/'SFX.wav')
    final=output/'WORLD_ENGINE_RENDER_PATH_RECONCILIATION_5S_SOFTWARE.mp4'
    mux=mux_preview_sfx(output/'preview.mp4',output/'SFX.wav',final,plan,request)
    subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',str(final),'-f','null','-'],check=True,capture_output=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)],
                                  check=True,capture_output=True,text=True).stdout)
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert video['codec_name']=='h264' and (video['width'],video['height'])==(1080,1920)
    assert video['avg_frame_rate']=='30/1' and int(video['nb_read_frames'])==150 and float(probe['format']['duration'])==5.0
    ownmanifest=digest(HERE/'RECONCILIATION_FILES.json')
    assert all(row['sourceManifestSHA256']==ownmanifest for row in compact)
    proof=HERE/'proof';proof.mkdir(exist_ok=True)
    save(proof/'ACTUAL_FRAME_TRACE_150.json',{'schema':'WORLD_ENGINE_RECONCILIATION_ACTUAL_150_V1',
       'sourceCheckoutCommit':commit,'sourceManifestSHA256':ownmanifest,'originalGlobalRange':r,
       'rendererSourceIsPreserved':True,'softwareTraceOnly':True,'candidateImageExecuted':False,
       'physicalNvidiaVerified':False,'visualQualityPass':False,'frames':compact})
    save(proof/'CAMERA_ACTIVITY_ACTUAL.json',measured)
    save(proof/'SFX_RECEIPT.json',sfx);save(proof/'MUX_RECEIPT.json',mux)
    save(proof/'FFPROBE.json',probe)
    for name in ('RECONCILIATION_CAPTURE.json','PREVIEW_RECEIPT.json','FREE_RENDER_RESULT.json'):
        destination=proof/name;assert not destination.exists();shutil.copyfile(output/name,destination)
    public=HERE/'public-review';assert not public.exists();public.mkdir()
    names=[final.name]
    shutil.copyfile(final,public/final.name)
    for row in receipt['checkpoints']:
        source=output/row['file'];assert digest(source)==row['sha256'];names.append(source.name)
        shutil.copyfile(source,public/source.name)
    comparison=HERE/'reports/OLD_VS_KNOWN_NEW.png'
    shutil.copyfile(comparison,public/comparison.name);names.append(comparison.name)
    (public/'SHA256SUMS').write_text(''.join(digest(public/name)+'  '+name+'\n' for name in sorted(names)))
    result={'schema':'WORLD_ENGINE_RECONCILIATION_NEW_VIDEO_RESULT_V1','status':'TECHNICAL_SOFTWARE_PASS_VISUAL_NEEDS_REWORK',
      'sourceCheckoutCommit':commit,'sourceManifestSHA256':ownmanifest,'range':r,'actualCapturedFrames':150,
      'all150RawRGBAAndPngEqualPreservedBaseline':True,'sampledStagePixelFrames':3,
      'actualSourceAndAreaAndCameraDrawsPerFrame':1,'cameraPixelActivity':measured,
      'softwareCaptureAndEncodingWallSeconds':receipt['totalWallMs']/1000,
      'candidateImageExecuted':False,'physicalNvidiaVerified':False,'full80Rendered':False,
      'sourceTimelineReset':False,'newVisualDesignClaimed':False,'visualQualityPass':False,
      'user66461Identity':'UNKNOWN_FILE_NOT_SUPPLIED','video':{'file':final.name,'sha256':digest(final),'bytes':final.stat().st_size},
      'secretOrPrivateStatePublished':False,'sourceContextQualification':'ORIGINAL_HISTORICAL_SCHEMATIC_NOT_OBSERVED_DAILY_BILATERAL_CONTROL'}
    save(HERE/'reports/NEW_VIDEO_RESULT.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--inputs',required=True)
    p.add_argument('--baseline',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
    print(json.dumps(finalize(a.output,a.inputs,a.baseline,a.commit),ensure_ascii=False))
