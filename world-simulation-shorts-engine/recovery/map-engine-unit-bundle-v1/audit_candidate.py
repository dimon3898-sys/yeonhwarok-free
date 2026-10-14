#!/usr/bin/env python3
"""Decode all 150 original output frames and make actual source comparisons.

Technical validation cannot certify reference-equivalent visual quality. Original
MP4 inputs and native PNGs remain read-only; public outputs are five comparisons.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'reference-reproduction-v1'
spec=importlib.util.spec_from_file_location('preserved_reference_audit_helpers',PRIOR/'audit_candidate.py')
helpers=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
sha,file_sha,json_write,preserve_write,png_bytes=(getattr(helpers,name) for name in ['sha','file_sha','json_write','preserve_write','png_bytes'])
REFERENCE_SHA='5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6'
REFERENCE_FILE=PRIOR/'data/REFERENCE_65379_COMPRESSED.mp4'
MOVIE_NAME='WORLD_ENGINE_MAP_ENGINE_UNIT_BUNDLE_5S.mp4'
BASELINE_ROOT=HERE.parent/'map-visual-upgrade-v1'
BASELINE_FILE=BASELINE_ROOT/'public-review/WORLD_ENGINE_MAP_VISUAL_UPGRADE_5S.mp4'
BASELINE_SHA='0630ab5c5e5e362d1a74ef65fd6041482d30f0ae1b12daa7f3f99490983c0772'
REFERENCE_START,REFERENCE_END=5.181813,10.181813
REFERENCE_MAP_CROP=[0,211,1080,2131]
CHECKPOINTS=helpers.CHECKPOINTS

def baseline_checkpoint_rows()->dict:
    """Use the fresh full baseline decode, not lossy screenshots of comparison PNGs."""
    if file_sha(BASELINE_FILE)!=BASELINE_SHA:raise RuntimeError('SAVED_BASELINE_MP4_SHA_MISMATCH')
    audit_root=HERE/'evidence/input_audit/candidate'
    report=json.loads((audit_root/'REPORT.json').read_text())
    old_frames=json.loads((BASELINE_ROOT/'evidence/candidate_audit/FRAMES.json').read_text())
    if (report.get('status')!='PASS' or report.get('inputSha256')!=BASELINE_SHA or
        report.get('freshDecodedRelevantFrames')!=150 or report.get('everyRelevantFrameMatchesPreservedRgbAudit') is not True):
        raise RuntimeError('FRESH_ACTUAL_BASELINE_150_FRAME_DECODE_REQUIRED')
    rows={}
    for row in report.get('baselineCheckpoints',[]):
        frame=row['sourceFrame'];p=(audit_root/row['file']).resolve()
        if not p.is_relative_to(audit_root.resolve()) or file_sha(p)!=row['sha256']:
            raise RuntimeError('ACTUAL_BASELINE_CHECKPOINT_HASH_MISMATCH')
        image=Image.open(p).convert('RGB')
        if image.size!=(1080,1920) or sha(image.tobytes())!=old_frames[frame]['decoded_rgb_sha256']:
            raise RuntimeError('BASELINE_PNG_IS_NOT_ACTUAL_ORIGINAL_DECODED_FRAME')
        if sha(image.tobytes())!=row['decodedRgbSha256'] or abs(row['ptsSeconds']-frame/30)>1e-5:
            raise RuntimeError('FRESH_BASELINE_RGB_OR_PTS_MISMATCH')
        rows[frame]={**row,'image':image}
    if sorted(rows)!=[frame for frame,_,_ in CHECKPOINTS]:raise RuntimeError('FIVE_FRESH_BASELINE_CHECKPOINTS_REQUIRED')
    return rows

def three_way_comparison(reference,baseline,candidate,*,source_frame,source_pts,candidate_frame):
    title,body,_=helpers.fonts()
    figure=Image.new('RGB',(3288,2070),'#15191f');draw=ImageDraw.Draw(figure)
    for x,heading in [(0,'TARGET REFERENCE'),(1104,'PRESERVED CURRENT 65409'),(2208,'NEW ENGINE / UNIT CANDIDATE')]:
        draw.text((x+20,12),heading,font=title,fill='white')
    draw.text((20,54),f'Source frame {source_frame} | PTS {source_pts:.6f}s | relative {source_pts-REFERENCE_START:.6f}s',font=body,fill='#cbd5e1')
    for x in (1104,2208):draw.text((x+20,54),f'Frame {candidate_frame} | relative {candidate_frame/30:.6f}s',font=body,fill='#cbd5e1')
    figure.paste(reference,(0,100));figure.paste(baseline,(1104,100));figure.paste(candidate,(2208,100))
    draw.text((20,2032),'Nearest actual reference PTS; phone chrome excluded from the reference map crop. Review image headings are outside the videos.',font=body,fill='#cbd5e1')
    return figure

def validate_runtime_rows(report:dict)->dict:
    rows=report.get('frames')
    if not isinstance(rows,list) or [row.get('frame') for row in rows]!=list(range(150)):
        raise RuntimeError('COMPLETE_CHRONOLOGICAL_150_NATIVE_ROWS_REQUIRED')
    bounds=[];roll=[];max_units=0;unit_overlap_frames=0
    for frame,row in enumerate(rows):
        d=row.get('diagnostic',{});gpu=d.get('gpu',{});protection=d.get('protection',{})
        if gpu.get('glError')!=0 or gpu.get('factoryCount')!=1 or gpu.get('nativeDrawCount')!=1:
            raise RuntimeError('ACTUAL_NATIVE_GL_FACTORY_DRAW_FAILURE: '+str(frame))
        if row.get('cameraLocked') is not False or d.get('cameraLocked') is not False:
            raise RuntimeError('CAMERA_LOCK_NOT_CLAIMED_FOR_MOVING_REFERENCE_SHOT')
        if d.get('surveyAdmissionPreserved') is not True or d.get('nativeEndpointGuardActive') is not True:
            raise RuntimeError('INHERITED_NATIVE_ADMISSION_GUARD_MUST_REMAIN_ACTIVE')
        for key in ['sourceUnchanged','nativeVisualCoreUnchanged','sourceGeometryUnchanged']:
            if protection.get(key) is not True:raise RuntimeError('IMMUTABLE_FINAL_SOURCE_OR_GEOMETRY_FAILURE: '+key)
        if protection.get('displayedNativeForeground') is not False:
            raise RuntimeError('EXPLICIT_NEW_SCENE_OPTIONAL_FOREGROUND_SCOPE_REQUIRED')
        control=row.get('control',{});territory=d.get('territory',{})
        for value in [control,territory]:
            if value.get('geometryUnchanged') is not True or value.get('routeVisuals') is not False or value.get('standaloneFrontLine') is not False:
                raise RuntimeError('TERRITORY_GEOMETRY_OR_NO_GUIDE_CONTRACT_FAILED: '+str(frame))
        if territory.get('continuousComplementaryOwnership') is not True or territory.get('arrowVisuals') is not False:
            raise RuntimeError('CONTINUOUS_COMPLEMENTARY_OWNERSHIP_REQUIRED: '+str(frame))
        frontier=d.get('frontierLight',{})
        if frontier.get('realControlBoundaryDerived') is not True or frontier.get('standaloneDecorativeLine') is not False:
            raise RuntimeError('LUMINOUS_CURRENT_CONTROL_BOUNDARY_ONLY_REQUIRED: '+str(frame))
        presentation=d.get('presentation',{})
        if presentation.get('cornerSamplesInside') is not True:
            raise RuntimeError('PRESENTATION_OVERSCAN_CORNER_OUTSIDE_NATIVE_SOURCE: '+str(frame))
        units=d.get('units',{})
        violation_count=lambda value:len(value) if isinstance(value,list) else value
        if violation_count(units.get('safeAreaViolations'))!=0 or violation_count(units.get('criticalCollisions'))!=0:
            raise RuntimeError('COMBAT_SAFE_AREA_OR_CRITICAL_COLLISION: '+str(frame))
        if units.get('noText') is not True or units.get('nationalFlags') is not True:
            raise RuntimeError('NO_RENDERED_TEXT_AND_ACTUAL_NATIONAL_BADGES_REQUIRED: '+str(frame))
        unit_overlap_frames+=int(bool(units.get('unitOverlaps',[])))
        count=units.get('count',len(units.get('units',[])))
        if isinstance(count,int):max_units=max(max_units,count)
        b=row.get('cameraBounds')
        if not isinstance(b,list) or len(b)!=4 or not all(isinstance(n,(int,float)) and math.isfinite(n) for n in b) or b[0]>=b[2] or b[1]>=b[3]:
            raise RuntimeError('FINITE_ORDERED_NATIVE_CAMERA_BOUNDS_REQUIRED')
        bounds.append(b)
        angle=row.get('rotationDegrees',d.get('camera',{}).get('rotationDegrees'))
        if not isinstance(angle,(int,float)) or not math.isfinite(angle):raise RuntimeError('FINITE_MEASURED_CAMERA_ROLL_REQUIRED')
        roll.append(angle)
    b=np.asarray(bounds,dtype=float);centers=(b[:,:2]+b[:,2:])/2;spans=b[:,2:]-b[:,:2]
    center_steps=np.diff(centers,axis=0)/spans[:-1]*np.asarray([1080,1920])
    max_step=float(np.linalg.norm(center_steps,axis=1).max())
    max_log_step=float(np.max(np.abs(np.diff(np.log(spans),axis=0))))
    max_roll_step=float(np.max(np.abs(np.diff(roll))))
    if max_step>25 or max_log_step>.04 or max_roll_step>.6:
        raise RuntimeError('LARGE_NATIVE_CAMERA_DISCONTINUITY: '+str([max_step,max_log_step,max_roll_step]))
    return {'status':'PASS','nativeFrames':150,'actualNativeDrawsPerFrame':1,'glErrors':0,'blackCornerGeometryFailures':0,
        'sourceUnchanged':True,'nativeVisualCoreUnchanged':True,'sourceGeometryUnchanged':True,
        'optionalNativeForegroundExcludedByNewScene':True,'oldNativeForegroundPixelIdentityClaimed':False,
        'safeAreaViolations':0,'criticalUnitCollisions':0,'unitOverlapFrames':unit_overlap_frames,'maximumMeasuredUnitCount':max_units,
        'noRenderedText':True,'actualNationalFlagBadges':True,
        'historicalPublicAssertion':False,'historicalPolicyScope':'SEPARATE_PRIVATE_VALIDATION_ONLY_PER_USER_CLARIFICATION',
        'routeVisuals':False,'arrowVisuals':False,'standaloneFrontLine':False,'continuousComplementaryOwnership':True,
        'frontierLight':{'realControlBoundaryDerived':True,'standaloneDecorativeLine':False,'isIntentionalCurrentBoundaryHighlight':True},
        'camera':{'boundsFirst':bounds[0],'boundsLast':bounds[-1],'rollFirst':roll[0],'rollLast':roll[-1],
            'maximumConsecutiveCenterDeltaPixels':max_step,'maximumConsecutiveLogSpanDelta':max_log_step,
            'maximumConsecutiveRollDeltaDegrees':max_roll_step,'longitudeSpanZoomRatio':float(spans[0,0]/spans[-1,0]),
            'source':'ACTUAL_NATIVE_DIAGNOSTICS_NOT_INFERRED_REFERENCE_POSE'},
        'geographicCoordinatesAltered':False,'visualParityClaimed':False}

def native_checkpoint_rows(report:dict)->dict:
    rows={}
    for row in report.get('checkpoints',[]):
        frame=row.get('frame');p=(HERE/row.get('path','')).resolve()
        if row.get('public') is not False or row.get('originalNativeCapture') is not True:
            raise RuntimeError('PRIVATE_ORIGINAL_NATIVE_CHECKPOINT_REQUIRED')
        if not p.is_relative_to((HERE/'evidence/proof/checkpoints').resolve()):raise RuntimeError('NATIVE_CHECKPOINT_PATH_OUTSIDE_PRIVATE_ROOT')
        if file_sha(p)!=row.get('sha256'):raise RuntimeError('NATIVE_CHECKPOINT_HASH_MISMATCH')
        rows[frame]={**row,'resolved_path':p}
    if sorted(rows)!=[frame for frame,_,_ in CHECKPOINTS]:raise RuntimeError('FIVE_PERSISTED_NATIVE_CHECKPOINTS_REQUIRED')
    return rows

def run_audit(args)->dict:
    report_path=args.report.resolve();movie=args.movie.resolve();private=args.output.resolve();public=HERE/'public-review'
    private.mkdir(parents=True,exist_ok=True)
    if movie!=(public/MOVIE_NAME).resolve():raise RuntimeError('AUTHORIZED_NEW_CANDIDATE_MOVIE_PATH_REQUIRED')
    if file_sha(REFERENCE_FILE)!=REFERENCE_SHA:raise RuntimeError('ACTUAL_TARGET_REFERENCE_HASH_MISMATCH')
    native_report=json.loads(report_path.read_text())
    if native_report.get('status')!='PASS':raise RuntimeError('COMPLETED_NATIVE_RENDER_REPORT_PASS_REQUIRED')
    if [native_report.get(k) for k in ['totalFrames','fps','width','height']]!=[150,30,1080,1920] or native_report.get('durationSeconds')!=5:
        raise RuntimeError('NATIVE_RENDER_FORMAT_MISMATCH')
    movie_sha=file_sha(movie)
    if movie_sha!=native_report.get('video',{}).get('sha256'):raise RuntimeError('ORIGINAL_NATIVE_MP4_HASH_MISMATCH')
    runtime_validation=validate_runtime_rows(native_report);native=native_checkpoint_rows(native_report);baseline=baseline_checkpoint_rows()
    info=helpers.probe(movie);videos=[stream for stream in info['streams'] if stream.get('codec_type')=='video']
    if len(videos)!=1 or any(stream.get('codec_type')=='audio' for stream in info['streams']):raise RuntimeError('SINGLE_H264_VIDEO_WITH_NO_AUDIO_REQUIRED')
    video=videos[0]
    if [video.get(k) for k in ['codec_name','width','height','r_frame_rate','avg_frame_rate']]!=['h264',1080,1920,'30/1','30/1'] or abs(float(info['format']['duration'])-5)>1e-6:
        raise RuntimeError('EXACT_5S_1080X1920_30FPS_H264_REQUIRED')
    times=helpers.frame_probe(movie)
    if len(times)!=150:raise RuntimeError('ACTUAL_ENCODED_FRAME_COUNT_IS_NOT_150')
    pts=[float(row['best_effort_timestamp_time']) for row in times]
    if any(abs(timestamp-index/30)>1e-5 for index,timestamp in enumerate(pts)):raise RuntimeError('ACTUAL_PTS_NOT_DETERMINISTIC_30FPS')
    source_times=json.loads((PRIOR/'evidence/reference_audit/FRAME_TIMESTAMPS.json').read_text())
    source_frames=json.loads((PRIOR/'evidence/reference_audit/FRAMES.json').read_text())
    tracking=json.loads((PRIOR/'evidence/reference_tracking/TRACKING_REPORT.json').read_text())
    if tracking.get('input_sha256')!=REFERENCE_SHA:raise RuntimeError('PERSISTED_REFERENCE_TRACKING_HASH_MISMATCH')
    cached={row['frame']:row for row in tracking['records']};selected={}
    for frame,_,_ in CHECKPOINTS:
        target=REFERENCE_START+frame/30
        index=min(range(len(source_times)),key=lambda i:abs(float(source_times[i]['best_effort_timestamp_time'])-target))
        if index not in cached:raise RuntimeError('MATCHED_REFERENCE_FRAME_NOT_IN_PERSISTED_TRACKING_CACHE')
        row=cached[index];p=PRIOR/'evidence/reference_tracking'/row['full_png']
        if file_sha(p)!=row['full_png_sha256']:raise RuntimeError('READ_ONLY_REFERENCE_PNG_HASH_MISMATCH')
        image=Image.open(p).convert('RGB')
        if sha(image.tobytes())!=source_frames[index]['decoded_rgb_sha256']:raise RuntimeError('MATCHED_REFERENCE_RGB_DIFFERS_FROM_FULL_ACTUAL_DECODE')
        selected[frame]={'image':image.crop(tuple(REFERENCE_MAP_CROP)),'frame':index,'pts':float(source_times[index]['best_effort_timestamp_time']),
            'target':target,'full_png_sha256':row['full_png_sha256']}
    rows=[];sheets=[];comparisons=[];_,_,small_font=helpers.fonts();sheet=None;previous_pixels=None
    stderr_path=private/'DECODE_STDERR.txt'
    with stderr_path.open('wb') as stderr:
        process=subprocess.Popen(['ffmpeg','-v','error','-threads','2','-i',str(movie),'-map','0:v:0','-an','-vsync','0','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE,stderr=stderr)
        if process.stdout is None:raise RuntimeError('ACTUAL_RGB_DECODE_PIPE_REQUIRED')
        try:
            for frame in range(150):
                raw=helpers.read_exact(process.stdout,1080*1920*3)
                if len(raw)!=1080*1920*3:raise RuntimeError('TRUNCATED_OUTPUT_RGB_FRAME: '+str(frame))
                image=Image.frombytes('RGB',(1080,1920),raw)
                pixels=np.asarray(image.resize((270,480),Image.Resampling.BOX),dtype=float)
                mean=float(np.mean(pixels@np.asarray([.2126,.7152,.0722])));deviation=float(pixels.std())
                if mean<2 or deviation<.5:raise RuntimeError('BLACK_OR_BLANK_OUTPUT_FRAME: '+str(frame))
                temporal_difference=None if previous_pixels is None else float(np.mean(np.abs(pixels-previous_pixels)))
                previous_pixels=pixels.copy()
                thumbnail=image.resize((180,320),Image.Resampling.LANCZOS)
                rows.append({'frame':frame,'pts_seconds':pts[frame],'decoded_rgb_sha256':sha(raw),
                    'thumbnail_rgb_sha256':sha(thumbnail.tobytes()),'mean_luma':round(mean,5),
                    'rgb_standard_deviation':round(deviation,5),'black_or_blank':False,
                    'mean_rgb_difference_from_previous_frame':None if temporal_difference is None else round(temporal_difference,5),
                    'screen_color_measurements':helpers.screen_colors(image)})
                tile=frame%30
                if tile==0:sheet=Image.new('RGB',(1080,1720),'#111111')
                x=(tile%6)*180;y=(tile//6)*344;sheet.paste(thumbnail,(x,y))
                ImageDraw.Draw(sheet).text((x+3,y+324),f'{frame:03d} | {pts[frame]:.3f}s',font=small_font,fill='white')
                if tile==29:
                    p=private/f'CONTACT_{len(sheets):02d}_FRAMES_{frame-29:03d}_{frame:03d}.png';data=png_bytes(sheet);preserve_write(p,data)
                    sheets.append({'first_frame':frame-29,'last_frame':frame,'file':p.name,'sha256':sha(data),'frames':30})
                    print(json.dumps({'candidate_contact_sheet_ready':p.name,'decoded_frames':len(rows)}),flush=True)
                if frame in selected:
                    original=native[frame];native_rgb=np.asarray(Image.open(original['resolved_path']).convert('RGB'),dtype=np.float32)
                    mse=float(np.mean((np.asarray(image,dtype=np.float32)-native_rgb)**2));psnr=float('inf') if mse==0 else 10*math.log10(255**2/mse)
                    if psnr<34:raise RuntimeError('ORIGINAL_ENCODED_CHECKPOINT_DEVIATES_FROM_NATIVE_PIXELS: '+str(frame))
                    reference=selected[frame];name=next(name for f,_,name in CHECKPOINTS if f==frame)
                    figure=three_way_comparison(reference['image'],baseline[frame]['image'],image,source_frame=reference['frame'],source_pts=reference['pts'],candidate_frame=frame)
                    data=png_bytes(figure);preserve_write(public/name,data)
                    comparisons.append({'candidate_frame':frame,'candidate_relative_seconds':frame/30,'actual_reference_frame':reference['frame'],
                        'actual_reference_pts_seconds':reference['pts'],'actual_reference_relative_seconds':reference['pts']-REFERENCE_START,
                        'reference_pts_error_from_requested_seconds':reference['pts']-reference['target'],'file':name,'sha256':sha(data),'bytes':len(data),
                        'reference_source_full_png_sha256':reference['full_png_sha256'],'candidate_native_checkpoint_sha256':original['sha256'],
                        'comparisonOrder':['REFERENCE','PRESERVED_CURRENT_65409','NEW_CANDIDATE'],
                        'baseline_mp4_sha256':BASELINE_SHA,'baseline_decoded_rgb_sha256':baseline[frame]['decodedRgbSha256'],
                        'baseline_checkpoint_png_sha256':baseline[frame]['sha256'],
                        'native_checkpoint_public':False,'candidate_decoded_vs_native_psnr_db':None if math.isinf(psnr) else round(psnr,5),
                        'native_checkpoint_pixels_equal_decoded':mse==0,'reference_screen_color_measurements':helpers.screen_colors(reference['image']),
                        'candidate_screen_color_measurements':rows[-1]['screen_color_measurements'],'reference_parity_claimed':False})
            if process.stdout.read(1):raise RuntimeError('UNEXPECTED_ADDITIONAL_OUTPUT_FRAME')
            if process.wait()!=0 or stderr_path.stat().st_size:raise RuntimeError('ACTUAL_OUTPUT_DECODE_ERROR')
        except BaseException:
            process.kill();process.wait();raise
    if file_sha(movie)!=movie_sha or file_sha(REFERENCE_FILE)!=REFERENCE_SHA or file_sha(BASELINE_FILE)!=BASELINE_SHA:
        raise RuntimeError('READ_ONLY_ORIGINAL_MOVIE_CHANGED')
    if any(file_sha(row['resolved_path'])!=row['sha256'] for row in native.values()):raise RuntimeError('READ_ONLY_NATIVE_CHECKPOINT_CHANGED')
    json_write(private/'FRAMES.json',rows);json_write(private/'FFPROBE.json',info);json_write(private/'FRAME_TIMESTAMPS.json',times)
    if [f for s in sheets for f in range(s['first_frame'],s['last_frame']+1)]!=list(range(150)):
        raise RuntimeError('CHRONOLOGICAL_CONTACT_SHEETS_DO_NOT_COVER_ALL_OUTPUT_FRAMES_ONCE')
    allowed={MOVIE_NAME,'SCENE_PLAN.json','SHA256SUMS',*[row['file'] for row in comparisons]}
    unexpected={p.name for p in public.iterdir() if p.is_file()}-allowed
    if unexpected:raise RuntimeError('UNAUTHORIZED_PUBLIC_REVIEW_FILES: '+','.join(sorted(unexpected)))
    return {'schema':'MAP_ENGINE_UNIT_CANDIDATE_TECHNICAL_AUDIT_V4','status':'PASS','technicalStatus':'PASS',
        'wholeVisualReview':'NOT_YET_REVIEWED_AT_TECHNICAL_AUDIT_TIME','fullVisualReviewClaimed':False,
        'referenceParityClaimed':False,'userReview':'REQUIRED','referenceInputSha256':REFERENCE_SHA,'referenceInputUnchanged':True,
        'preservedBaselineMp4Sha256':BASELINE_SHA,'preservedBaselineUnchanged':True,
        'baselineComparisonUsesFreshAll150FrameDecode':True,'threeWayComparisonOrder':['REFERENCE','PRESERVED_CURRENT_65409','NEW_CANDIDATE'],
        'referenceIntervalSeconds':[REFERENCE_START,REFERENCE_END],'referenceInputReencoded':False,'candidateMovie':MOVIE_NAME,
        'candidateMp4Sha256':movie_sha,'candidateMp4Unchanged':True,'candidateReencoded':False,'durationSeconds':5.0,
        'decodedFrames':150,'width':1080,'height':1920,'fps':30,'videoCodec':'h264','audioStreams':0,
        'chronologicalPtsPass':True,'everyDecodedRgbSha256Recorded':True,'blackOrBlankFrames':0,'decodeStderrBytes':0,
        'temporalMeasurements':{'maximumConsecutiveMeanRgbDifference':max(row['mean_rgb_difference_from_previous_frame'] or 0 for row in rows),
            'maximumConsecutiveMeanLumaDifference':max(abs(b['mean_luma']-a['mean_luma']) for a,b in zip(rows,rows[1:])),
            'limits':'Camera, territory advance and intentional thin frontier light also produce RGB changes; these measurements alone do not certify absence of flicker'},
        'originalNativeCheckpointsUnchanged':True,'nativeValidation':runtime_validation,'comparisons':comparisons,'contactSheets':sheets,
        'renderPerformance':native_report.get('performance',{}),
        'allFramesIncludedOnceInContactSheets':True,
        'visualReviewRequired':'Inspect every contact sheet chronologically and all source comparison figures; scripts cannot certify visual equivalence',
        'screenColorMeasurementLimits':['Screen color fractions are not geographic territory area','Source in-map badges/subtitles and camera changes contaminate color fractions',
            'Color fractions cannot certify semantic integrity or terrain fidelity','Opacity cannot be uniquely recovered from composited video'],
        'publicAllowlist':sorted(allowed),'sha256sumsNeedsPublicationUpdateForComparisonPngs':True,
        'sourceCommit':native_report['sourceCommit'],'renderReportSha256':file_sha(report_path),
        'requiredTempOnlyFiles':0,'finalPromotion':False,'next':'ACTUAL_WHOLE_VISUAL_COMPARISON_THEN_USER_VIDEO_REVIEW_REQUIRED'}

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument('--movie',type=Path,default=HERE/'public-review'/MOVIE_NAME)
    parser.add_argument('--report',type=Path,default=HERE/'evidence/proof/REPORT.json')
    parser.add_argument('--output',type=Path,default=HERE/'evidence/candidate_audit');args=parser.parse_args()
    result_path=HERE/'evidence/CANDIDATE_AUDIT.json'
    try:
        result=run_audit(args);json_write(result_path,result)
        print(json.dumps({'status':'PASS','technicalStatus':'PASS','decodedFrames':150,'comparisons':5,
            'wholeVisualReview':result['wholeVisualReview'],'candidateSha256':result['candidateMp4Sha256']}),flush=True);return 0
    except Exception as error:
        json_write(result_path,{'schema':'MAP_ENGINE_UNIT_CANDIDATE_TECHNICAL_AUDIT_V4','status':'BLOCKED','error':str(error),
            'fullVisualReviewClaimed':False,'referenceParityClaimed':False,'requiredTempOnlyFiles':0,'finalPromotion':False})
        print(json.dumps({'status':'BLOCKED','error':str(error)}),flush=True);return 1
if __name__=='__main__':raise SystemExit(main())
