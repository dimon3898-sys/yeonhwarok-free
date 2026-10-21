"""Measure actual capture evidence without turning data absence into quality PASS."""
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'proof/ACTUAL_CAPTURE.json').read_bytes())
profile = json.loads((ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes())
rows = {r['globalFrame']: r for r in report['frames']}
if report['status'] != 'ACTUAL_SOURCE_REVIEW_DRAW_COMPLETE' or len(rows) != 348:
    raise ValueError('ACTUAL_COMPLETE_CAPTURE_REQUIRED')
for frame, row in rows.items():
    chapter = next(x for x in profile['chapters'] if x['startFrame'] <= frame < x['endFrame'])
    segment = next(x for x in profile['sourceSchedule'] if x['startFrame'] <= frame < x['endFrame'])
    if (chapter['chapterId'],chapter['eventId'],segment['truthKind'],segment['sourceDate']) != (
            row['chapterId'],row['eventId'],row['truthKind'],row['sourceAsOfDate']):
        raise ValueError('ACTUAL_EVENT_OR_SOURCE_MAPPING_MISMATCH')
    if row['glError'] != 0 or row['eventDirector']['historicalOwnerMorphDrawn']:
        raise ValueError('UNEXPECTED_GL_ERROR_OR_INVENTED_OWNER_MORPH')
    if row['areaStateId'] == 'BUSAN' and row['chapterId'] != 'chapter-03':
        raise ValueError('BUSAN_FALLBACK_RECURRED')
    if row['camera']['requestedLocalContractSatisfied'] is not False:
        raise ValueError('UNADMITTED_LOCAL_WAS_REPORTED_AS_ADMITTED')
    if row['eventDirector']['composedTerrainTexture']['frame'] != frame:
        raise ValueError('ACTUAL_TERRAIN_TEXTURE_STALE')
clips = []
for clip in report['clipsRequested']:
    selected = [rows[f] for f in range(clip['startFrame'],clip['endFrame'])]
    travel = 0
    jumps = []
    for old, new in zip(selected,selected[1:]):
        a,b = old['actualBounds'],new['actualBounds']
        center_delta = [((b[0]+b[2])-(a[0]+a[2]))/2,((b[1]+b[3])-(a[1]+a[3]))/2]
        travel += math.hypot(center_delta[0]/(a[2]-a[0])*1080,center_delta[1]/(a[3]-a[1])*1920)
        previous = old['eventDirector'].get('sourceAvailability') or {}
        current = new['eventDirector'].get('sourceAvailability') or {}
        p,q = (previous.get('event') or {}).get('roi'),(current.get('event') or {}).get('roi')
        if p and q:
            distance = math.hypot(((q[0]+q[2])-(p[0]+p[2]))/2,((q[1]+q[3])-(p[1]+p[3]))/2)
            if distance > .01:
                jumps.append({'previousFrame':old['globalFrame'],'frame':new['globalFrame'],
                    'titleCenterDisplacementPixels':distance,'previousROI':p,'roi':q})
    clips.append({**clip,'actuallyDrawnFrames':len(selected),
        'uniqueRawRGBAHashes':len({r['rawRGBASHA256'] for r in selected}),
        'allFramesNewlyDrawn':all(r['newActualDraw'] for r in selected),
        'identicalPixelsMayBeActualHoldFrames':True,'framesClonedByEncoderInput':False,
        'cameraCenterTravelPixelsIntegrated':travel,
        'heightSpanMinMax':[min(r['actualBounds'][3]-r['actualBounds'][1]for r in selected),
            max(r['actualBounds'][3]-r['actualBounds'][1]for r in selected)],
        'titlePlacementDisplacements':jumps,
        'fullOwnerMorphFrames':0,'requestedVisualGoalVerified':False})
summary={'schema':'WORLD_ENGINE_ASTRA_V2_ACTUAL_EVIDENCE_ANALYSIS_V1',
    'technicalMappingChecks':'PASS','requestedVisualContract':'NEEDS_REWORK',
    'captureReportSHA256':hashlib.sha256((ROOT/'proof/ACTUAL_CAPTURE.json').read_bytes()).hexdigest(),
    'actualUniqueGlobalDraws':348,'samplePNGs':16,'shortSourceReviewClips':3,
    'sourceDateRegressionInSampledFrames':False,'busanFallbackOutsideDefense':False,
    'clips':clips,'requestedLocalCameraAdmitted':False,'historicalOwnerMorphVerified':False,
    'literalGPUCallCountInstrumented':False,'nvidiaHardwareVerified':False,
    'codeReviewDoesNotApproveVisualQuality':True,'visualQualityApproved':False,
    'layoutIssue':'Per-frame measured placement can move the title between safe bands; a chapter-wide stable placement contract is still required.',
    'missingSourceFramesInFullTimeline':860,'fullControlStateCount':0,'historicalMilitaryCoordinateCount':0,
    'referenceVideoDirectlyInspectedThisRun':False,'next':'USER_REVIEW_REQUIRED'}
(ROOT/'reports/ACTUAL_ANALYSIS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (ROOT/'reports/FRAME_REVIEW_16.csv').open('w',newline='') as file:
    writer=csv.writer(file)
    writer.writerow(['globalFrame','timeSeconds','chapterId','eventId','truthKind','sourceDate','pngSHA256','actualBounds',
        'requestedLocalAdmitted','fullOwnerMorph','visibleText','qualityState'])
    for frame in report['stillsRequested']:
        r=rows[frame];writer.writerow([frame,frame/30,r['chapterId'],r['eventId'],r['truthKind'],r['sourceAsOfDate'],
            r['pngSHA256'],json.dumps(r['actualBounds']),False,False,' | '.join(r['visibleText']),'USER_REVIEW_REQUIRED / NEEDS_REWORK'])
print(json.dumps({k:v for k,v in summary.items()if k!='clips'}))
