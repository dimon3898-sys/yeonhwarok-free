"""Audit completed Studio output; no rendering, source smoothing or old-file writes.

The old 104E/7N support-edge scores are diagnostics, not a generic detector of
geographic image quality. Thresholds are frozen from the actual baseline's
off-edge controls. Visual judgment remains an independent review step.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
OLD=HERE.parent/'universal-source-pipeline-v2'
BASELINE_SHA='39c7fd94af3a228bb66b7543aadee843bdd1a4443ba436e858b21327b70abcca'
VERTICAL_THRESHOLD=12.133750066757203
HORIZONTAL_THRESHOLD=.75
W,H,N=1080,1920,180

def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def fail(code):raise ValueError(code)

def semantic_equal(a,b):
    if type(a) in (float,int) and type(b) in (float,int):
        return math.isfinite(a) and math.isfinite(b) and a==b
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(semantic_equal(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(semantic_equal(x,y) for x,y in zip(a,b))
    return a==b

def validate_video_probe(probe):
    streams=probe.get('streams',[]);frames=probe.get('frames',[])
    if len(streams)!=1:fail('FRAME_AUDIT_VIDEO_ONLY_ONE_STREAM_REQUIRED')
    stream=streams[0]
    if (stream.get('codec_name')!='h264' or [stream.get('width'),stream.get('height')]!=[W,H]
        or stream.get('avg_frame_rate')!='30/1' or int(stream.get('nb_frames',-1))!=N
        or abs(float(probe.get('format',{}).get('duration',-1))-6)>1e-6):
        fail('FRAME_AUDIT_6S_CANONICAL_VIDEO_REQUIRED')
    pts=[float(frame['best_effort_timestamp_time']) for frame in frames]
    if len(pts)!=N or any(abs(value-i/30)>1e-6 for i,value in enumerate(pts)):
        fail('FRAME_AUDIT_PTS_GAP_DUPLICATE_OR_REORDER')
    return pts

def scene_state(row):
    d=row.get('diagnostic',{});camera=d.get('camera',{});annotation=d.get('annotation',{})
    return {'frame':row.get('frame'),'globalFrame':row.get('globalFrame'),'timeSeconds':row.get('timeSeconds'),
        'fieldId':d.get('fieldId'),'sourceControlFrame':d.get('sourceControlFrame'),
        'ownerMasks':d.get('ownerMasks'),'unknownMask':d.get('unknownMask'),'contestedMask':d.get('contestedMask'),
        'sharedFront':d.get('sharedFront'),'actualCamera':d.get('actualCamera'),'camera':camera,
        'projectEventPoint':d.get('projectEventPoint'),'marker':d.get('marker'),
        'annotation':{k:annotation.get(k) for k in ('id','text','drawn','visibleFraction','roi','placement','reservation')},
        'localUsed':camera.get('admission',{}).get('localUsed')}

def compare_scene_states(old,new):
    if len(old)!=N or len(new)!=N:fail('FRAME_AUDIT_CAPTURE_SEQUENCE_INCOMPLETE')
    errors=[]
    for index,(before,after) in enumerate(zip(old,new)):
        a,b=scene_state(before),scene_state(after)
        if before.get('frame')!=index or after.get('frame')!=index:
            errors.append({'frame':index,'fields':['frameOrder']});continue
        changed=[name for name in a if not semantic_equal(a[name],b[name])]
        if changed:errors.append({'frame':index,'fields':changed})
    return {'sameStateFrames':N-len(errors),'stateDifferences':errors,
        'exactCameraOwnerFrontMarkerClock':not errors,
        'comparison':'Same encoded source frame index; exact numeric values, no geometry/camera tolerance or new source inference. Terrain style metadata is intentionally excluded.'}

def coverage(receipt,frames):
    asset=receipt.get('terrainAsset',{});box=asset.get('bounds');spacing=asset.get('pixelSpacing')
    if not isinstance(box,list) or len(box)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in box):
        fail('FRAME_AUDIT_TERRAIN_BOUNDS_REQUIRED')
    if not isinstance(spacing,list) or len(spacing)!=2 or any(type(v) not in (int,float) or v<=0 for v in spacing):
        fail('FRAME_AUDIT_NATIVE_SPACING_REQUIRED')
    margins=[];failures=[]
    for row in frames:
        b=row.get('diagnostic',{}).get('actualCamera',{}).get('bounds')
        if not isinstance(b,list) or len(b)!=4 or not (box[0]<b[0]<b[2]<box[2] and box[1]<b[1]<b[3]<box[3]):
            failures.append(row.get('frame'));continue
        margins.append([(b[0]-box[0])/spacing[0],(b[1]-box[1])/spacing[1],(box[2]-b[2])/spacing[0],(box[3]-b[3])/spacing[1]])
    return {'allActualViewportsStrictlyInsideSource':not failures and len(margins)==N,
        'sourceBoundaryCanEnterActualViewport':bool(failures),'outsideCoverageFrames':failures,
        'sourceBounds':box,'nativeSpacing':spacing,
        'minimumMarginNativePixelsBySide':[min(row[i] for row in margins) for i in range(4)] if margins else None,
        'configuredNativeGutter':receipt.get('nativeWindowPolicy',{}).get('gutterSourcePixels'),
        'scope':'Strict actual-camera containment. Native-window gutter/grid/budget policy has separate receipt validation; no unsupported terrain is generated.'}

def source_overlap(receipt,output=None):
    asset=receipt['terrainAsset'];new_path=REPO/asset['path']
    if not new_path.resolve().is_relative_to(REPO) or new_path.is_symlink():fail('FRAME_AUDIT_SOURCE_SCOPE')
    raw=new_path.read_bytes()
    if sha(raw)!=asset['sha256'] or len(raw)!=asset['bytes']:fail('FRAME_AUDIT_TERRAIN_FILE_HASH')
    before_path=REPO/'world-simulation-shorts-engine/web/flat_assets/natural_earth_1_east_asia.png'
    old_bounds=[104,7,152,63];new_bounds=asset['bounds'];step=1/60
    west,south,east,north=max(old_bounds[0],new_bounds[0]),max(old_bounds[1],new_bounds[1]),min(old_bounds[2],new_bounds[2]),min(old_bounds[3],new_bounds[3])
    if west>=east or south>=north:fail('FRAME_AUDIT_SOURCE_OVERLAP_MISSING')
    def pixels(bounds):
        values=[(west-bounds[0])/step,(bounds[3]-north)/step,(east-bounds[0])/step,(bounds[3]-south)/step]
        if any(abs(value-round(value))>1e-6 for value in values):fail('FRAME_AUDIT_SOURCE_GRIDS_NOT_ALIGNED')
        return tuple(round(value) for value in values)
    with Image.open(before_path) as old,Image.open(new_path) as new:
        if old.mode!='RGB' or new.mode!='RGB':fail('FRAME_AUDIT_SOURCE_RGB_REQUIRED')
        a=old.crop(pixels(old_bounds));b=new.crop(pixels(new_bounds));equal=a.size==b.size and a.tobytes()==b.tobytes()
        result={'decodedCommonSourceRGBExact':equal,'geographicOverlapBounds':[west,south,east,north],
            'overlapDimensions':list(a.size),'beforeRGBSHA256':sha(a.tobytes()),'recoveryRGBSHA256':sha(b.tobytes()),
            'newTerrainFileSHA256':sha(raw),'sourceOriginalSHA256':asset['sourceOriginalSHA256'],
            'resamplingOrSmoothingPerformed':False,'meaning':'Actual same-geographic native source-pixel overlap, not comparison of shaded rendered frames.'}
        if output is not None:
            w,h=min(a.width,256),min(a.height,256);aa=a.crop((0,0,w,h));bb=b.crop((0,0,w,h))
            diff=Image.fromarray(np.abs(np.asarray(aa).astype(np.int16)-np.asarray(bb).astype(np.int16)).astype(np.uint8))
            image=Image.new('RGB',(3*w,h+34),'#101820');d=ImageDraw.Draw(image)
            for i,(label,im) in enumerate([('OLD NATIVE PIXELS',aa),('WIDER NATIVE PIXELS',bb),('ABS RGB DIFFERENCE',diff)]):
                d.text((i*w+5,10),label,fill='white');image.paste(im,(i*w,34))
            new_output(output);image.save(output);result['comparisonPNG']=str(output.relative_to(HERE))
        return result

def source_trace(report,receipt,receipt_raw):
    asset=receipt['terrainAsset'];rows=report.get('terrainAssetHTTPRequests',[])
    matches=[row for row in rows if row.get('url')==asset['url'] or row.get('path')==asset['url']]
    valid=bool(matches) and all(row.get('httpStatus')==200 and row.get('sha256')==asset['sha256'] and row.get('bytes')==asset['bytes'] for row in matches)
    binding=report.get('terrainStyleReceiptSHA256')==sha(receipt_raw)
    style=semantic_equal(report.get('sourceStyle'),receipt)
    return {'actualTerrainHTTP200AndSHA':valid,'matchingHTTPResponses':matches,
        'terrainStyleReceiptFileSHA256':sha(receipt_raw),'captureReceiptFileSHAMatches':binding,
        'captureSourceStyleEqualsPinnedReceipt':style,'status':'PASS' if valid and binding and style else 'UNVERIFIED'}

def adapter_bindings(report):
    rows=report.get('adapterBindings',[]);checks=[]
    for row in rows:
        name=row.get('path');relative=Path(name) if isinstance(name,str) else None
        safe=relative is not None and not relative.is_absolute() and '..' not in relative.parts
        file=REPO/relative if safe else None
        safe=safe and file.resolve().is_relative_to(REPO) and not any(p.is_symlink() for p in [file,*file.parents])
        actual=sha(file.read_bytes()) if safe and file.is_file() else None
        checks.append({'path':name,'scopeValid':safe,'capturedSHA256':row.get('sha256'),
            'actualCurrentSHA256':actual,'shaMatch':actual is not None and actual==row.get('sha256')})
    return {'status':'PASS' if checks and all(r['shaMatch'] for r in checks) else 'UNVERIFIED',
        'filesChecked':len(checks),'bindings':checks,'meaning':'Captured full repository-relative adapter paths compared against actual current source bytes; no private file or arbitrary path is read.'}

def edge_metrics(a,bounds):
    x=(104-bounds[0])/(bounds[2]-bounds[0])*W;y=(bounds[3]-7)/(bounds[3]-bounds[1])*H
    y0,y1=sorted(round((bounds[3]-lat)/(bounds[3]-bounds[1])*H) for lat in [31,22])
    x0,x1=sorted(round((lon-bounds[0])/(bounds[2]-bounds[0])*W) for lon in [112,116])
    ix,iy=round(x),round(y)
    if not (6<=ix<W-6 and 6<=iy<H-6 and 0<=y0<y1<=H and 0<=x0<x1<=W):fail('FRAME_AUDIT_FORMER_EDGE_ROI_OUTSIDE_SAME_SCENE')
    left=a[y0:y1,ix-6:ix-2].astype(np.float32).mean(axis=1);right=a[y0:y1,ix+2:ix+6].astype(np.float32).mean(axis=1)
    top=a[iy-6:iy-2,x0:x1].astype(np.float32).mean(axis=0);bottom=a[iy+2:iy+6,x0:x1].astype(np.float32).mean(axis=0)
    vertical=float(np.median(np.abs(right-left).mean(axis=1)));horizontal=float(np.median(np.abs(bottom-top).mean(axis=1)))
    return {'seamXProjected':x,'seamYProjected':y,'verticalMedianAbsRgbJump':vertical,'horizontalMedianAbsRgbJump':horizontal,
        'verticalAboveFrozenBaselineControlP99':vertical>VERTICAL_THRESHOLD,'horizontalAboveFrozenBaselineControlP99':horizontal>HORIZONTAL_THRESHOLD}

def new_output(path):
    if path.exists() or path.is_symlink():fail('FRAME_AUDIT_REFUSE_EXISTING_OUTPUT')
    path.parent.mkdir(parents=True,exist_ok=True)

def read_exact(stream,size):
    parts=[];done=0
    while done<size:
        data=stream.read(size-done)
        if not data:break
        parts.append(data);done+=len(data)
    return b''.join(parts)

def audit(capture_root,decoded_root,baseline_decoded_root,terrain_receipt):
    root=Path(capture_root);decoded_root=Path(decoded_root);baseline_decoded_root=Path(baseline_decoded_root)
    report_file=root/'proof/CAPTURE_REPORT.json';report_raw=report_file.read_bytes();capture=json.loads(report_raw)
    if capture.get('status')!='SOFTWARE_PREVIEW_COMPLETE' or capture.get('fullDecode')!='PASS' or capture.get('newlyRenderedFrames')!=N or capture.get('totalFrames')!=N:
        fail('FRAME_AUDIT_COMPLETED_180_FRAME_CAPTURE_REQUIRED')
    video_row=capture['video'];name=video_row['file']
    if Path(name).name!=name or not name.endswith('.mp4'):fail('FRAME_AUDIT_CAPTURE_VIDEO_NAME')
    video=root/'public-review'/name;video_bytes=video.read_bytes()
    if sha(video_bytes)!=video_row['sha256'] or len(video_bytes)!=video_row['bytes']:fail('FRAME_AUDIT_CAPTURE_VIDEO_HASH')
    baseline_video=OLD/'public-review/WORLD_ENGINE_UNIVERSAL_SOURCE_DEMO_6S.mp4'
    if sha(baseline_video.read_bytes())!=BASELINE_SHA:fail('FRAME_AUDIT_BASELINE_IDENTITY')
    before=json.loads((OLD/'reports/ACTUAL_CAPTURE_REPORT.json').read_bytes())
    baseline=json.loads((HERE/'reports/BASELINE_VIDEO_AUDIT.json').read_bytes())
    if baseline['sourceMP4SHA256']!=BASELINE_SHA or baseline['frames']!=N:fail('FRAME_AUDIT_BASELINE_MEASUREMENTS')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-show_frames','-of','json',str(video)]))
    pts=validate_video_probe(probe);state=compare_scene_states(before['frames'],capture['frames'])
    receipt_raw=Path(terrain_receipt).read_bytes();receipt=json.loads(receipt_raw)
    cover=coverage(receipt,capture['frames']);trace=source_trace(capture,receipt,receipt_raw);bindings=adapter_bindings(capture)
    overlap=source_overlap(receipt,HERE/'public-review/SOURCE_NATIVE_OVERLAP.png')
    if decoded_root.exists():fail('FRAME_AUDIT_FRESH_DECODE_ROOT_REQUIRED')
    decoded_root.mkdir(parents=True,mode=0o700)
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-xerror','-i',str(video),'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE);rows=[]
    try:
        for index in range(N):
            raw=read_exact(process.stdout,W*H*3)
            if len(raw)!=W*H*3:fail('FRAME_AUDIT_SHORT_DECODE')
            a=np.frombuffer(raw,dtype=np.uint8).reshape(H,W,3)
            old_row=baseline['framesData'][index];old_file=baseline_decoded_root/old_row['decodedPNG']
            if old_file.is_symlink() or sha(old_file.read_bytes())!=old_row['decodedPNGSHA256']:fail('FRAME_AUDIT_BASELINE_DECODED_PNG_CHANGED')
            with Image.open(old_file) as im:old=np.asarray(im.convert('RGB'))
            current=decoded_root/f'{index:03d}.png';Image.fromarray(a).save(current)
            d=capture['frames'][index]['diagnostic'];black=float(np.mean(np.all(a<=2,axis=2)));rgb_mean=float(a.mean())
            difference=np.abs(a.astype(np.int16)-old.astype(np.int16))
            rows.append({'frame':index,'pts':pts[index],**edge_metrics(a,d['actualCamera']['bounds']),
                'decodedRGBSHA256':sha(raw),'decodedPNGSHA256':sha(current.read_bytes()),
                'blackPixelFraction':black,'meanRgb8':rgb_mean,'blackFrame':black>.99 or rgb_mean<1,
                'beforeAfterChangedPixels':int(np.count_nonzero(np.any(difference!=0,axis=2))),
                'beforeAfterMeanAbsRgb8Difference':float(difference.mean()),'glError':d.get('glError'),
                'markerSafe':d.get('marker',{}).get('safeArea') is True,
                'localUsed':d.get('camera',{}).get('admission',{}).get('localUsed'),
                'sourceGeometryUnchanged':d.get('sourceGeometryUnchanged') is True,
                'sameStateAsBaseline':not any(v['frame']==index for v in state['stateDifferences'])})
        if process.stdout.read(1):fail('FRAME_AUDIT_EXTRA_DECODED_FRAME')
        stderr=process.stderr.read().decode();exit_code=process.wait()
        if exit_code:fail('FRAME_AUDIT_FFMPEG_DECODE_FAILED')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
    samples=sorted(set([0,30,60,90,120,150,179,max(baseline['framesData'],key=lambda row:row['verticalMedianAbsRgbJump']/VERTICAL_THRESHOLD+row['horizontalMedianAbsRgbJump']/HORIZONTAL_THRESHOLD)['frame']]))
    contact=HERE/'public-review/BEFORE_AFTER_CONTACT_SHEET.png';new_output(contact)
    cell_w,cell_h,label,header=270,480,36,70
    sheet=Image.new('RGB',(4*cell_w,header+math.ceil(len(samples)/2)*(cell_h+label)),'#101820');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    draw.text((12,10),'ACTUAL ENCODED MP4 / SAME FRAME / BEFORE | RECOVERY',font=font,fill='white')
    draw.text((12,37),'SYNTHETIC DEMO / 1080x1920 / 30fps / NO HISTORICAL OR GPU QUALITY CLAIM',font=font,fill='#f4d78c')
    for n,index in enumerate(samples):
        x=(n%2)*2*cell_w;y=header+(n//2)*(cell_h+label)
        for side,(tag,directory) in enumerate([('BEFORE',baseline_decoded_root),('RECOVERY',decoded_root)]):
            draw.text((x+side*cell_w+6,y+9),f'{tag} f{index:03d} / {index/30:.2f}s',font=font,fill='white')
            with Image.open(directory/f'{index:03d}.png') as im:sheet.paste(im.convert('RGB').resize((cell_w,cell_h),Image.Resampling.LANCZOS),(x+side*cell_w,y+label))
    sheet.save(contact)
    checks={'videoContractAndPTS':True,'fullDecode180':len(rows)==N,'sameSceneCameraOwnerFrontMarkerClock':state['exactCameraOwnerFrontMarkerClock'],
        'noBlackFrames':not any(row['blackFrame'] for row in rows),'allGlErrorsZero':all(row['glError']==0 for row in rows),
        'markerSafeArea':all(row['markerSafe'] for row in rows),'noLocalAdmissionBypass':all(row['localUsed'] is False for row in rows),
        'sourceGeometryUnchanged':all(row['sourceGeometryUnchanged'] for row in rows),
        'sourceBoundaryOutsideEveryViewport':cover['allActualViewportsStrictlyInsideSource'],
        'nativeSourceOverlapRGBExact':overlap['decodedCommonSourceRGBExact'],'actualSourceHTTPAndReceipt':trace['status']=='PASS',
        'capturedAdapterSourceHashes':bindings['status']=='PASS'}
    flags={key:[row['frame'] for row in rows if row[key]] for key in ['verticalAboveFrozenBaselineControlP99','horizontalAboveFrozenBaselineControlP99']}
    result={'schema':'WORLD_ENGINE_G2_RECOVERY_FRAME_AUDIT_V1','technicalChecks':checks,'technicalStatus':'PASS' if all(checks.values()) else 'NEEDS_REWORK',
        'qualityDecision':'QUALITY_REVIEW_REQUIRED' if all(checks.values()) else 'NEEDS_REWORK',
        'qualityApproved':False,'manualVisualReviewPerformedByThisScript':False,'historicalG3':'BLOCKED','nvidiaVerified':False,
        'baselineMP4SHA256':BASELINE_SHA,'recoveryMP4SHA256':sha(video_bytes),'captureReportSHA256':sha(report_raw),
        'frames':N,'fps':30,'durationSeconds':6,'resolution':[W,H],'actualDecodeExitCode':exit_code,'actualDecodeStderr':stderr,
        'uniqueDecodedRGBFrames':len({row['decodedRGBSHA256'] for row in rows}),'sameScene':state,'sourceCoverage':cover,'sourceNativeOverlap':overlap,'actualSourceTrace':trace,'actualAdapterBindings':bindings,
        'formerEdgeDiagnostics':{'frozenThresholds':{'vertical':VERTICAL_THRESHOLD,'horizontal':HORIZONTAL_THRESHOLD},
            'thresholdSource':'Baseline180×6off-edge controls P99; never refit to recovered output',
            'aboveThresholdFrameIndices':flags,'interpretation':'Flags require image/source review. A natural geographic image edge is not automatically a tile defect. Source boundary is independently proven outside all camera views.'},
        'decodedImageDirectory':str(decoded_root),'contactFrameIndices':samples,'contactPNG':str(contact.relative_to(HERE)),
        'comparisonCondition':'Both sides are actual decoded H264 MP4 frame pixels at identical source time and1080×1920. Contact sheet alone is resized; full decodedPNG180frames are retained.',
        'limitations':['Automated metrics cannot approve final visual quality. Independent real-frame inspection is still required.',
            'Control-grid stairs are unchanged authored source geometry; no smoothing or increased geographic accuracy is claimed.',
            'No new historical geometry, G1 reproduction, NVIDIA execution, paid deployment or80s video is performed.'],
        'decodeCommand':command,'ffprobeCommand':['ffprobe','-v','error','-show_streams','-show_format','-show_frames','-of','json',str(video)],'framesData':rows}
    output=HERE/'reports/RECOVERY_FRAME_AUDIT.json';new_output(output);output.write_text(json.dumps(result,indent=2)+'\n')
    csvfile=HERE/'reports/RECOVERY_FRAME_AUDIT.csv';new_output(csvfile)
    with csvfile.open('w',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    md=HERE/'FRAME_AUDIT.md';new_output(md)
    lines=['# Actual encoded Studio frame audit','',f"Technical status: {result['technicalStatus']}. Visual status: {result['qualityDecision']}; no automatic quality approval.",'',
        f"Decoded all180frames at1080×1920/30fps/6seconds. Exit{exit_code}; sequential PTS verified. Recovery MP4 SHA256 `{result['recoveryMP4SHA256']}`.",'',
        f"Before/after exact scene-state frames: {state['sameStateFrames']}/180. Camera, owner/unknown/contested/shared-front, marker, glyph and frame clock compared; terrain style metadata intentionally excluded.",'',
        f"Source coverage all180viewports: {cover['allActualViewportsStrictlyInsideSource']}; decoded native overlap exact: {overlap['decodedCommonSourceRGBExact']}; actualHTTP/receipt: {trace['status']}.",'',
        f"Old support-edge thresholds remain vertical{VERTICAL_THRESHOLD} and horizontal{HORIZONTAL_THRESHOLD}. Flagged recovered frames: vertical{len(flags['verticalAboveFrozenBaselineControlP99'])}, horizontal{len(flags['horizontalAboveFrozenBaselineControlP99'])}.",'',
        'These are known-location diagnostics, not a generic image-quality test. Inspect flagged natural features before classifying a defect. No threshold was relaxed or refit.','',
        f"Comparison PNG shows actual encoded frames {samples}. The script performs no manual semantic review; independent reviewer must record their actual viewed frames separately.",'',
        'All180decoded PNGs remain in the new private scratch directory. Existing baseline source/video/cache files are not modified. HistoricalG3 remains BLOCKED.','',
        'Detailed results and exact commands: `reports/RECOVERY_FRAME_AUDIT.json`; per-frame data: `reports/RECOVERY_FRAME_AUDIT.csv`.']
    md.write_text('\n'.join(lines)+'\n');return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture-root',type=Path,required=True)
    parser.add_argument('--decoded-root',type=Path,default=Path('/workspace/g2-recovery-new-video'))
    parser.add_argument('--baseline-decoded-root',type=Path,default=Path('/workspace/g2-recovery-baseline-video/decoded-frames'))
    parser.add_argument('--terrain-receipt',type=Path,default=HERE/'fixtures/RECOVERY_STYLE_RECEIPT.json')
    args=parser.parse_args();result=audit(args.capture_root,args.decoded_root,args.baseline_decoded_root,args.terrain_receipt)
    print(json.dumps({'technicalStatus':result['technicalStatus'],'qualityDecision':result['qualityDecision'],'checks':result['technicalChecks'],'formerEdgeDiagnostics':result['formerEdgeDiagnostics']}))
