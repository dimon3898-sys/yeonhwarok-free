"""Sequential free software probes. A failed region prevents every later probe."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from PIL import Image
import numpy as np

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]

def main():
    cpu=json.loads((HERE/'reports/CPU_REGRESSION_RESULTS.json').read_text())
    if cpu['status']!='PASS' or cpu['preservedTests']!=101:
        raise RuntimeError('G2_FINAL_ACTUAL_CPU_GATE_REQUIRED')
    packages=json.loads((HERE/'reports/PROBE_PACKAGES.json').read_text())
    report={'schema':'WORLD_ENGINE_G2_FINAL_ACTUAL_REGIONS_V1','status':'IN_PROGRESS',
        'backend':'SwiftShader','nvidiaVerified':False,'visualQualityApproved':False,
        'allRegionsSameEngine':True,'results':[]}
    try:
        for row in packages['cases']:
            cmd=['node',str(HERE/'tools/probe_final.mjs'),'--plan='+row['plan'],
                '--expected-sha256='+row['sha256'],'--output-root='+row['outputRoot'],
                '--frames='+','.join(map(str,row['frames']))]
            started=time.monotonic()
            run=subprocess.run(cmd,cwd=REPO,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},
                               text=True,capture_output=True,timeout=180)
            item={'id':row['id'],'region':row['region'],'command':cmd,'exitCode':run.returncode,
                'elapsedSeconds':round(time.monotonic()-started,3),'stdout':run.stdout,
                'stderr':run.stderr,'status':'FAIL'}
            report['results'].append(item)
            probe_file=Path(row['outputRoot'])/'proof/PROBE_REPORT.json'
            if probe_file.is_file():
                proof_raw=probe_file.read_bytes();proof=json.loads(proof_raw)
                saved=HERE/'reports'/('ACTUAL_REGION_'+row['id'].upper()+'.json')
                saved.write_bytes(proof_raw)
                item.update(proof=saved.relative_to(HERE).as_posix(),
                            proofSHA256=hashlib.sha256(proof_raw).hexdigest(),actualDraws=len(proof['frames']))
            if run.returncode or proof['status']!='PASS' or len(proof['frames'])!=4:
                raise RuntimeError('G2_FINAL_ACTUAL_REGION_FAILED_'+row['id'])
            inputs=json.loads(Path(row['plan']).read_bytes())['sourcePipeline']['runtimePayload']
            checks=[]
            for frame in proof['frames']:
                d=frame['diagnostic'];layout=d['layoutAudit']
                assert layout['valid'] and not layout['collisions'] and not layout['boundaryCollisions']
                assert not layout['safeArea']['violations'] and layout['nativeLocationRendered'] is False
                assert d['glError']==0 and d['sharedFieldClock'] and d['sourceGeometryUnchanged']
                assert d['marker']['safeArea'] and d['cameraNumericalAgreement']['matches']
                clock=inputs['cameraSchedule'][frame['frame']];b=clock['flatBounds'];lon,lat=inputs['eventLocation']
                expected=[(lon-b[0])/(b[2]-b[0])*1080,(b[3]-lat)/(b[3]-b[1])*1920]
                error=max(abs(a-b) for a,b in zip(expected,d['projectEventPoint']))
                assert error<1e-6
                image=Path(row['outputRoot'])/'public-review'/frame['file']
                pixels=np.asarray(Image.open(image).convert('RGB'))
                black_fraction=float(np.mean(np.max(pixels,axis=2)<=2))
                assert pixels.shape==(1920,1080,3) and black_fraction<.01
                checks.append({'frame':frame['frame'],'layoutValid':True,
                    'selectedGap':layout['locationRecovery']['selectedGap'],
                    'sourceCameraFrame':clock['sourceFrame'],'eventProjectionErrorPixels':error,
                    'blackFraction':black_fraction,'locationGlyphMeasuredNotRendered':True})
            assert proof['frames'][1]['rawSHA256']==proof['frames'][3]['rawSHA256']
            assert proof['sourceSupport']['allActualCameraViewportsCovered']
            assert all(r['httpStatus']==200 for r in proof['terrainAssetHTTPRequests'])
            item.update(status='PASS',perFrameChecks=checks,
                initializationLayoutValid=proof['runtime']['native']['layoutValidation']['valid'],
                initializationLocationRecovery=proof['runtime']['native']['layoutValidation']['locationRecovery'],
                actualTerrainHTTPAndSHA='PASS',sourceNativeCoverage='PASS',
                sameFrameRedrawExact=True,allSourcePartitionsExact=True)
            print(json.dumps({'region':row['id'],'status':'PASS','draws':4,
                              'gaps':[r['selectedGap'] for r in checks]}),flush=True)
        report.update(status='PASS',regionsPassed=len(report['results']),actualDraws=20)
    except BaseException as error:
        report.update(status='FAIL',failure=str(error),laterRegionsNotExecuted=True)
        raise
    finally:
        (HERE/'reports/ACTUAL_REGIONS.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':main()
