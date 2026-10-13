#!/usr/bin/env python3
"""Actual 150-frame candidate decode and source-matched comparison producer.

Technical success is separate from visual acceptance. The original MP4, source
reference, and original native checkpoint PNGs are read only. Public outputs are
only the five authorized comparison PNGs. SHA256SUMS is owned by publication.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REFERENCE_SHA = "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6"
REFERENCE_FILE = HERE / "data/REFERENCE_65379_COMPRESSED.mp4"
MOVIE_NAME = "WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4"
REFERENCE_START, REFERENCE_END = 5.181813, 10.181813
REFERENCE_MAP_CROP = [0, 211, 1080, 2131]
COLOR_MAP_ROI = [24, 9, 915, 1599]
STRICT_COUNTERS = ["protectedChangedPixels", "markerChangedPixels", "textChangedPixels", "outsideRoiChangedPixels", "safeAreaChangedPixels", "protectedBoundaryChangedPixels"]
EXPECTED_BACKGROUND_COUNTERS = ["backgroundOutsideSafeAreaChangedPixels", "partialAlphaForegroundChangedPixels", "transparentReservationBackgroundChangedPixels", "opaqueForegroundSupportPixels"]
CHECKPOINTS = [(0,"01_START.png","COMPARE_01_START.png"), (38,"02_ADVANCE.png","COMPARE_02_ADVANCE.png"), (75,"03_TRACKING.png","COMPARE_03_TRACKING.png"), (112,"04_CONTINUOUS_CONTROL.png","COMPARE_04_CONTINUOUS_CONTROL.png"), (149,"05_END.png","COMPARE_05_END.png")]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda:handle.read(1024*1024),b''):
            h.update(part)
    return h.hexdigest()


def json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.partial')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def preserve_write(path: Path, data: bytes) -> None:
    """Refuse to silently replace already produced review pixels."""
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:
            raise RuntimeError('EXISTING_DERIVED_ARTIFACT_DIFFERS: '+path.name)
        return
    path.write_bytes(data)


def png_bytes(image: Image.Image) -> bytes:
    buffer=io.BytesIO();image.save(buffer,format='PNG',optimize=True)
    return buffer.getvalue()


def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))


def frame_probe(path: Path) -> list[dict]:
    command=['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp,best_effort_timestamp_time,pts_time,pict_type,key_frame','-of','json',str(path)]
    return json.loads(subprocess.check_output(command))['frames']


def read_exact(stream, length: int) -> bytes:
    chunks=[];remaining=length
    while remaining:
        part=stream.read(remaining)
        if not part:break
        chunks.append(part);remaining-=len(part)
    return b''.join(chunks)


def screen_colors(map_image: Image.Image) -> dict:
    small=map_image.crop(tuple(COLOR_MAP_ROI)).resize((297,530),Image.Resampling.BOX)
    rgb=np.asarray(small);hsv=np.asarray(small.convert('HSV'))
    h,s,v=(hsv[:,:,i] for i in range(3))
    masks={'orange':(h<=35)&(s>=115)&(v>=65),'purple':(h>=170)&(h<=225)&(s>=90)&(v>=45)}
    result={}
    for name,mask in masks.items():
        pixels=rgb[mask]
        result[name]={'sample_pixels':int(mask.sum()),'screen_roi_fraction':round(float(mask.mean()),7),'median_rgb':np.median(pixels,axis=0).round(1).tolist() if len(pixels) else None,'mean_rgb':np.mean(pixels,axis=0).round(2).tolist() if len(pixels) else None}
    return result


def fonts():
    filename=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    return (ImageFont.truetype(str(filename),28),ImageFont.truetype(str(filename),22),ImageFont.truetype(str(filename),13)) if filename.exists() else (ImageFont.load_default(),)*3


def comparison_image(reference_map: Image.Image, candidate: Image.Image, *, source_frame: int, source_pts: float, candidate_frame: int) -> Image.Image:
    title,body,_=fonts()
    image=Image.new('RGB',(2184,2070),'#15191f')
    draw=ImageDraw.Draw(image)
    draw.text((20,12),'TARGET REFERENCE',font=title,fill='white')
    draw.text((1104,12),'5-SECOND REPRODUCTION CANDIDATE',font=title,fill='white')
    relative=source_pts-REFERENCE_START
    draw.text((20,54),f'Source frame {source_frame} | {source_pts:.6f}s | relative {relative:.6f}s',font=body,fill='#cbd5e1')
    draw.text((1104,54),f'Output frame {candidate_frame} | relative {candidate_frame/30:.6f}s',font=body,fill='#cbd5e1')
    image.paste(reference_map,(0,100));image.paste(candidate,(1104,100))
    draw.text((20,2032),'Nearest actual reference PTS; source phone UI retained. Visual parity requires user review.',font=body,fill='#cbd5e1')
    return image


def native_checkpoint_rows(report: dict) -> dict[int,dict]:
    rows=report.get('checkpoints')
    if not isinstance(rows,list):
        raise RuntimeError('PERSISTED_NATIVE_CHECKPOINT_MANIFEST_REQUIRED')
    output={}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('frame'),int):
            raise RuntimeError('INVALID_NATIVE_CHECKPOINT_ROW')
        if row.get('public') is not False or row.get('originalNativeCapture') is not True:
            raise RuntimeError('NATIVE_CHECKPOINT_MUST_BE_PRIVATE_ORIGINAL_CAPTURE')
        path=(HERE/row['path']).resolve()
        if not path.is_relative_to((HERE/'evidence/proof/checkpoints').resolve()):
            raise RuntimeError('NATIVE_CHECKPOINT_PATH_OUTSIDE_PRIVATE_CHECKPOINT_FOLDER')
        if file_sha(path)!=row['sha256']:
            raise RuntimeError('NATIVE_CHECKPOINT_SOURCE_HASH_MISMATCH')
        output[row['frame']]={**row,'resolved_path':path}
    if sorted(output)!=[frame for frame,_,_ in CHECKPOINTS]:
        raise RuntimeError('FIVE_NATIVE_CHECKPOINT_FRAMES_REQUIRED')
    return output


def validate_runtime_rows(report: dict) -> dict:
    rows=report.get('frames')
    if not isinstance(rows,list) or len(rows)!=150 or [row.get('frame') for row in rows]!=list(range(150)):
        raise RuntimeError('COMPLETE_CHRONOLOGICAL_150_NATIVE_ROWS_REQUIRED')
    strict_totals={key:0 for key in STRICT_COUNTERS}
    expected_totals={key:0 for key in EXPECTED_BACKGROUND_COUNTERS}
    bounds=[]
    for row in rows:
        protection=row.get('protection')
        if not isinstance(protection,dict) or protection.get('checked') is not True:
            raise RuntimeError('ACTUAL_NATIVE_PROTECTION_CHECK_REQUIRED')
        for key in STRICT_COUNTERS:
            if protection.get(key)!=0:raise RuntimeError('CRITICAL_NATIVE_PROTECTION_ERROR: '+key)
            strict_totals[key]+=protection[key]
        for key in EXPECTED_BACKGROUND_COUNTERS:
            value=protection.get(key,0)
            if not isinstance(value,int) or value<0:raise RuntimeError('INVALID_BACKGROUND_COUNTER')
            expected_totals[key]+=value
        if row.get('glError')!=0 or row.get('nativeDrawCount')!=2 or row.get('cameraLocked') is not False:
            raise RuntimeError('ACTUAL_NATIVE_GL_DRAW_OR_MOVING_CAMERA_STATE_FAILED')
        box=row.get('cameraBounds')
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in box) or box[2]<=box[0] or box[3]<=box[1]:
            raise RuntimeError('FINITE_ORDERED_ACTUAL_CAMERA_BOUNDS_REQUIRED')
        bounds.append(box)
        control=row.get('control')
        if not isinstance(control,dict) or control.get('geometryUnchanged') is not True or control.get('routeVisuals') is not False or control.get('standaloneFrontLine') is not False:
            raise RuntimeError('GEOMETRY_OR_NO_DECORATIVE_ROUTE_CONTRACT_FAILED')
    b=np.asarray(bounds,dtype=float)
    centers=(b[:,:2]+b[:,2:])/2;spans=b[:,2:]-b[:,:2]
    return {'status':'PASS','native_frames':150,'actual_native_draws_per_protected_frame':2,'actual_camera_locked':False,'strict_opaque_foreground_support_counters':strict_totals,'expected_background_dependent_counters':expected_totals,'opaque_foreground_scope':'ACTUAL_OPAQUE_FOREGROUND_ALPHA_SUPPORT_NOT_BOUNDING_BOX_BACKGROUND','full_marker_or_text_rgba_equality_claimed':False,'partial_alpha_policy':'FOREGROUND_SOURCE_AND_STYLE_UNCHANGED_BACKGROUND_DEPENDENT_COMPOSITE_EXPECTED','camera':{'bounds_first':bounds[0],'bounds_last':bounds[-1],'centre_first':centers[0].tolist(),'centre_last':centers[-1].tolist(),'span_first':spans[0].tolist(),'span_last':spans[-1].tolist(),'longitude_span_zoom_ratio':float(spans[0,0]/spans[-1,0]),'latitude_span_zoom_ratio':float(spans[0,1]/spans[-1,1]),'maximum_consecutive_centre_delta_degrees':float(np.linalg.norm(np.diff(centers,axis=0),axis=1).max()),'maximum_consecutive_log_span_delta':float(np.max(np.abs(np.diff(np.log(spans),axis=0)))),'source':'ACTUAL_NATIVE_FRAME_REPORT_NOT_INFERRED_REFERENCE_POSE'},'geometry_unchanged':True,'route_visuals':False,'standalone_front_line':False}


def run_audit(args) -> dict:
    report_path=args.report.resolve();movie=args.movie.resolve();private=args.output.resolve();public=HERE/'public-review'
    private.mkdir(parents=True,exist_ok=True)
    if movie!=(public/MOVIE_NAME).resolve():raise RuntimeError('AUTHORIZED_CANDIDATE_MOVIE_PATH_REQUIRED')
    source_sha=file_sha(REFERENCE_FILE)
    if source_sha!=REFERENCE_SHA:raise RuntimeError('TARGET_REFERENCE_SOURCE_HASH_MISMATCH')
    native_report=json.loads(report_path.read_text())
    if native_report.get('status')!='PASS':raise RuntimeError('COMPLETED_NATIVE_RENDER_REPORT_PASS_REQUIRED')
    if [native_report.get(k) for k in ['totalFrames','fps','width','height']]!=[150,30,1080,1920] or abs(float(native_report.get('durationSeconds',0))-5)>1e-9:
        raise RuntimeError('NATIVE_RENDER_OUTPUT_FORMAT_MISMATCH')
    movie_sha=file_sha(movie)
    if movie_sha!=native_report.get('video',{}).get('sha256'):raise RuntimeError('ORIGINAL_RENDERED_MP4_HASH_MISMATCH')
    runtime_validation=validate_runtime_rows(native_report)
    native_checkpoints=native_checkpoint_rows(native_report)
    checkpoints_before={frame:row['sha256'] for frame,row in native_checkpoints.items()}
    info=probe(movie)
    videos=[stream for stream in info['streams'] if stream['codec_type']=='video']
    if len(videos)!=1 or any(stream['codec_type']=='audio' for stream in info['streams']):raise RuntimeError('SINGLE_VIDEO_AND_NO_AUDIO_REQUIRED')
    video=videos[0]
    if [video.get(k) for k in ['codec_name','width','height','r_frame_rate','avg_frame_rate']]!=['h264',1080,1920,'30/1','30/1'] or abs(float(info['format']['duration'])-5)>1e-6:
        raise RuntimeError('ENCODED_5S_1080X1920_30FPS_H264_REQUIRED')
    times=frame_probe(movie)
    if len(times)!=150:raise RuntimeError('ENCODED_FRAME_COUNT_IS_NOT_150')
    pts=[float(row['best_effort_timestamp_time']) for row in times]
    if any(abs(timestamp-index/30)>1e-5 for index,timestamp in enumerate(pts)):raise RuntimeError('ENCODED_PTS_NOT_DETERMINISTIC_30FPS')
    source_times=json.loads((HERE/'evidence/reference_audit/FRAME_TIMESTAMPS.json').read_text())
    source_frames=json.loads((HERE/'evidence/reference_audit/FRAMES.json').read_text())
    tracking=json.loads((HERE/'evidence/reference_tracking/TRACKING_REPORT.json').read_text())
    if tracking.get('input_sha256')!=source_sha:raise RuntimeError('REFERENCE_TRACKING_INPUT_BINDING_MISMATCH')
    cached={row['frame']:row for row in tracking['records']}
    selected_reference={}
    for frame,_,_ in CHECKPOINTS:
        target=REFERENCE_START+frame/30
        index=min(range(len(source_times)),key=lambda i:abs(float(source_times[i]['best_effort_timestamp_time'])-target))
        if index not in cached:raise RuntimeError('MATCHED_REFERENCE_FRAME_NOT_IN_PERSISTED_TRACKING_INPUTS')
        source=cached[index]
        source_path=HERE/'evidence/reference_tracking'/source['full_png']
        if file_sha(source_path)!=source['full_png_sha256']:raise RuntimeError('REFERENCE_MATCHED_PNG_HASH_MISMATCH')
        image=Image.open(source_path).convert('RGB')
        if sha(image.tobytes())!=source_frames[index]['decoded_rgb_sha256']:raise RuntimeError('REFERENCE_MATCHED_RGB_DIFFERS_FROM_FULL_AUDIT')
        selected_reference[frame]={'image':image.crop(tuple(REFERENCE_MAP_CROP)),'frame':index,'pts':float(source_times[index]['best_effort_timestamp_time']),'target':target,'full_png_sha256':source['full_png_sha256']}
    rows,sheets,comparisons=[],[],[]
    _,_,small_font=fonts();sheet=None
    stderr_path=private/'DECODE_STDERR.txt'
    with stderr_path.open('wb') as stderr:
        process=subprocess.Popen(['ffmpeg','-v','error','-threads','2','-i',str(movie),'-map','0:v:0','-an','-vsync','0','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE,stderr=stderr)
        if process.stdout is None:raise RuntimeError('DECODE_RGB_PIPE_REQUIRED')
        try:
            for frame in range(150):
                raw=read_exact(process.stdout,1080*1920*3)
                if len(raw)!=1080*1920*3:raise RuntimeError('TRUNCATED_CANDIDATE_RGB_FRAME: '+str(frame))
                image=Image.frombytes('RGB',(1080,1920),raw)
                pixels=np.asarray(image.resize((270,480),Image.Resampling.BOX),dtype=float)
                mean=float(np.mean(pixels@np.asarray([.2126,.7152,.0722])));deviation=float(pixels.std())
                blank=mean<2 or deviation<.5
                if blank:raise RuntimeError('BLACK_OR_BLANK_CANDIDATE_FRAME: '+str(frame))
                thumbnail=image.resize((180,320),Image.Resampling.LANCZOS)
                rows.append({'frame':frame,'pts_seconds':pts[frame],'decoded_rgb_sha256':sha(raw),'thumbnail_rgb_sha256':sha(thumbnail.tobytes()),'mean_luma':round(mean,5),'rgb_standard_deviation':round(deviation,5),'black_or_blank':False,'screen_color_measurements':screen_colors(image)})
                tile=frame%30
                if tile==0:sheet=Image.new('RGB',(1080,1720),'#111111')
                x=(tile%6)*180;y=(tile//6)*344
                sheet.paste(thumbnail,(x,y));ImageDraw.Draw(sheet).text((x+3,y+324),f'{frame:03d} | {pts[frame]:.3f}s',font=small_font,fill='white')
                if tile==29:
                    path=private/f'CONTACT_{len(sheets):02d}_FRAMES_{frame-29:03d}_{frame:03d}.png';data=png_bytes(sheet);preserve_write(path,data)
                    sheets.append({'first_frame':frame-29,'last_frame':frame,'file':path.name,'sha256':sha(data),'frames':30})
                    print(json.dumps({'candidate_contact_sheet_ready':path.name,'decoded_frames':len(rows)}),flush=True)
                if frame in selected_reference:
                    native=native_checkpoints[frame];native_rgb=np.asarray(Image.open(native['resolved_path']).convert('RGB'),dtype=np.float32)
                    mse=float(np.mean((np.asarray(image,dtype=np.float32)-native_rgb)**2))
                    psnr=float('inf') if mse==0 else 10*math.log10(255**2/mse)
                    if psnr<34:raise RuntimeError('ENCODED_CHECKPOINT_DEVIATES_FROM_NATIVE_PIXELS: '+str(frame))
                    reference=selected_reference[frame]
                    name=next(comp for checkpoint,_,comp in CHECKPOINTS if checkpoint==frame)
                    figure=comparison_image(reference['image'],image,source_frame=reference['frame'],source_pts=reference['pts'],candidate_frame=frame)
                    figure_data=png_bytes(figure);figure_path=public/name;preserve_write(figure_path,figure_data)
                    comparisons.append({'candidate_frame':frame,'candidate_relative_seconds':frame/30,'actual_reference_frame':reference['frame'],'actual_reference_pts_seconds':reference['pts'],'actual_reference_relative_seconds':reference['pts']-REFERENCE_START,'reference_pts_error_from_requested_seconds':reference['pts']-reference['target'],'file':name,'sha256':sha(figure_data),'bytes':len(figure_data),'reference_source_full_png_sha256':reference['full_png_sha256'],'candidate_native_checkpoint_sha256':native['sha256'],'native_checkpoint_public':False,'candidate_decoded_vs_native_psnr_db':None if math.isinf(psnr) else round(psnr,5),'native_checkpoint_pixels_equal_decoded':mse==0,'reference_screen_color_measurements':screen_colors(reference['image']),'candidate_screen_color_measurements':rows[-1]['screen_color_measurements'],'reference_parity_claimed':False})
            if process.stdout.read(1):raise RuntimeError('UNEXPECTED_ADDITIONAL_CANDIDATE_FRAME')
            if process.wait()!=0 or stderr_path.stat().st_size:raise RuntimeError('CANDIDATE_DECODE_ERROR')
        except BaseException:
            process.kill();process.wait();raise
    if file_sha(movie)!=movie_sha or file_sha(REFERENCE_FILE)!=source_sha:raise RuntimeError('READ_ONLY_INPUT_CHANGED')
    if any(file_sha(row['resolved_path'])!=checkpoints_before[frame] for frame,row in native_checkpoints.items()):raise RuntimeError('ORIGINAL_NATIVE_CHECKPOINT_CHANGED')
    json_write(private/'FRAMES.json',rows);json_write(private/'FFPROBE.json',info);json_write(private/'FRAME_TIMESTAMPS.json',times)
    if [frame for sheet in sheets for frame in range(sheet['first_frame'],sheet['last_frame']+1)]!=list(range(150)):raise RuntimeError('CONTACT_SHEETS_DO_NOT_COVER_ALL_FRAMES_ONCE')
    allowed={MOVIE_NAME,'SCENE_PLAN.json','SHA256SUMS',*[row['file'] for row in comparisons]}
    public_files={path.name for path in public.iterdir() if path.is_file()}
    unexpected=sorted(public_files-allowed)
    if unexpected:raise RuntimeError('UNAUTHORIZED_PUBLIC_FILES: '+','.join(unexpected))
    result={'schema':'REFERENCE_REPRODUCTION_CANDIDATE_TECHNICAL_AUDIT_V1','status':'PASS','technicalStatus':'PASS','wholeVisualReview':'NOT_YET_REVIEWED_AT_TECHNICAL_AUDIT_TIME','fullVisualReviewClaimed':False,'referenceParityClaimed':False,'userReview':'REQUIRED','referenceRole':'USER_AUTHORIZED_TARGET_REFERENCE_COUNTERFACTUAL_MODERN_CONFLICT_NOT_HISTORICAL_KOREAN_WAR','referenceInputSha256':source_sha,'referenceInputUnchanged':True,'referenceIntervalSeconds':[REFERENCE_START,REFERENCE_END],'referenceInputReencoded':False,'candidateMovie':MOVIE_NAME,'candidateMp4Sha256':movie_sha,'candidateMp4Unchanged':True,'candidateReencoded':False,'durationSeconds':5.0,'decodedFrames':150,'width':1080,'height':1920,'fps':30,'videoCodec':'h264','audioStreams':0,'chronologicalPtsPass':True,'everyDecodedRgbSha256Recorded':True,'blackOrBlankFrames':0,'decodeStderrBytes':0,'originalNativeCheckpointsUnchanged':True,'nativeValidation':runtime_validation,'comparisons':comparisons,'contactSheets':sheets,'allFramesIncludedOnceInContactSheets':True,'visualReviewRequired':'Inspect all five contact sheets chronologically and all five reference-comparison figures; decoder success alone is not visual acceptance','screenColorContract':{'roiMapPixels':COLOR_MAP_ROI,'method':'Actual decoded RGB to Pillow HSV threshold colors; common screen ROI for source crop and output','limits':['Screen color fractions are not geographic territory area','Source YouTube controls outside ROI are excluded, but in-map badges/subtitles and camera changes may contaminate source color fractions','Camera framing and locked terrain/region visuals differ; direct color fraction equality is not semantic/fidelity certification','Opacity cannot be uniquely recovered from composited source footage'],'orangeHsv8bit':{'hue':[0,35],'saturation':[115,255],'value':[65,255]},'purpleHsv8bit':{'hue':[170,225],'saturation':[90,255],'value':[45,255]}},'publicAllowlist':sorted(allowed),'sha256sumsNeedsPublicationUpdateForComparisonPngs':True,'sourceCommit':native_report.get('sourceCommit'),'renderReportSha256':file_sha(report_path),'requiredTempOnlyFiles':0,'finalPromotion':False,'next':'WHOLE_CANDIDATE_VISUAL_REVIEW_THEN_USER_VIDEO_REVIEW_REQUIRED'}
    return result


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--movie',type=Path,default=HERE/'public-review'/MOVIE_NAME)
    parser.add_argument('--report',type=Path,default=HERE/'evidence/proof/REPORT.json')
    parser.add_argument('--output',type=Path,default=HERE/'evidence/candidate_audit')
    args=parser.parse_args()
    result_path=HERE/'evidence/CANDIDATE_AUDIT.json'
    try:
        report=run_audit(args)
        json_write(result_path,report)
        print(json.dumps({'status':'PASS','technicalStatus':'PASS','decodedFrames':150,'comparisonFigures':5,'wholeVisualReview':report['wholeVisualReview'],'candidateSha256':report['candidateMp4Sha256']}),flush=True)
        return 0
    except Exception as error:
        json_write(result_path,{'schema':'REFERENCE_REPRODUCTION_CANDIDATE_TECHNICAL_AUDIT_V1','status':'BLOCKED','technicalStatus':'BLOCKED','error':str(error),'fullVisualReviewClaimed':False,'referenceParityClaimed':False,'finalPromotion':False,'requiredTempOnlyFiles':0})
        print(json.dumps({'status':'BLOCKED','error':str(error)}),flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
