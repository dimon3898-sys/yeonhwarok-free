"""Encode only captured actual source-review windows and package safe review files.

PNGs are unmodified native-renderer output. The contact sheet/review burn-in are
explicit derivatives, never renderer frames or proof of unsupported ownership.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public-review'
sha = lambda b: hashlib.sha256(b).hexdigest()


def run(command):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout


def encode(report):
    rows = {r['globalFrame']: r for r in report['frames']}
    results = []
    for clip in report['clipsRequested']:
        count = clip['endFrame'] - clip['startFrame']
        for frame in range(clip['startFrame'], clip['endFrame']):
            source = ROOT / '.private/frames' / f'{frame:04}.png'
            if sha(source.read_bytes()) != rows[frame]['pngSHA256']:
                raise ValueError('ACTUAL_SEQUENCE_SOURCE_SHA_MISMATCH')
        clean = PUBLIC / (clip['id'] + '_SOURCE_REVIEW.mp4')
        review = PUBLIC / (clip['id'] + '_GLOBAL_FRAME_REVIEW.mp4')
        if not clean.exists():
            run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-framerate', '30', '-start_number', str(clip['startFrame']),
                '-i', str(ROOT / '.private/frames/%04d.png'), '-frames:v', str(count), '-an', '-c:v', 'libx264',
                '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', str(clean)])
        # This is a review-only annotation of verified global indices, not a map layer.
        text_file = ROOT / '.private' / (clip['id'] + '_REVIEW_LABEL.txt')
        text_file.write_text('QUALIFIED SOURCE REVIEW | ' + clip['id'] + ' | GLOBAL FRAME %{eif:n+' + str(clip['startFrame']) + ':d}')
        if not review.exists():
            run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(clean), '-vf',
                'drawtext=textfile=' + str(text_file) + ':fontcolor=white:fontsize=28:x=30:y=35:box=1:boxcolor=black@0.8',
                '-frames:v', str(count), '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', str(review)])
        outputs = []
        for file in [clean, review]:
            info = json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(file)]))
            video = [s for s in info['streams'] if s['codec_type'] == 'video']
            if len(video) != 1 or len(info['streams']) != 1:
                raise ValueError('SOURCE_REVIEW_VIDEO_ONLY_EXPECTED')
            v = video[0]
            if (v['width'], v['height'], v['r_frame_rate'], v['codec_name'], int(v['nb_read_frames'])) != (1080,1920,'30/1','h264',count):
                raise ValueError('ACTUAL_CLIP_TECHNICAL_FORMAT_MISMATCH')
            if abs(float(info['format']['duration']) - count / 30) > .002:
                raise ValueError('ACTUAL_CLIP_DURATION_MISMATCH')
            run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(file), '-f', 'null', '-'])
            outputs.append({'file': file.name, 'sha256': sha(file.read_bytes()), 'bytes': file.stat().st_size,
                'frames': count, 'durationSeconds': count / 30, 'fullDecode': 'PASS', 'audioStreams': 0})
        frame_receipt = {'schema': 'WORLD_ENGINE_ACTUAL_SOURCE_REVIEW_CLIP_V2', **clip,
            'purpose': 'QUALIFIED_SOURCE_REVIEW', 'requestedControlMorphVerified': False,
            'requestedLocalCameraAdmitted': False, 'actualDrawFrameIndices': list(range(clip['startFrame'],clip['endFrame'])),
            'frames': [{k: rows[f].get(k) for k in ['globalFrame','timeSeconds','pngSHA256','rawRGBASHA256','actualBounds',
                'truthKind','sourceAsOfDate','areaStateId','frontSource','visibleText']} for f in range(clip['startFrame'],clip['endFrame'])],
            'outputs': outputs, 'nvidiaHardwareVerified': False, 'visualQualityApproved': False}
        (PUBLIC / (clip['id'] + '_FRAMES.json')).write_text(json.dumps(frame_receipt, ensure_ascii=False, indent=2) + '\n')
        results.append(frame_receipt)
    return results


def contact(report):
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    image = Image.new('RGB', (1080, 2080), '#10151b')
    draw = ImageDraw.Draw(image)
    for index, frame in enumerate(report['stillsRequested']):
        row = next(r for r in report['frames'] if r['globalFrame'] == frame)
        file = ROOT / row['file']
        if sha(file.read_bytes()) != row['pngSHA256']:
            raise ValueError('ACTUAL_STILL_SHA_MISMATCH')
        with Image.open(file) as source:
            if source.size != (1080,1920):
                raise ValueError('ACTUAL_STILL_SIZE_MISMATCH')
            thumb = source.convert('RGB').resize((270,480), Image.Resampling.LANCZOS)
        x, y = (index % 4) * 270, (index // 4) * 520
        image.paste(thumb, (x,y))
        draw.text((x+8,y+488),f'{frame/30:02.0f}s | global {frame}',font=font,fill='white')
    image.save(PUBLIC / 'CONTACT_SHEET_16.png')


def compare_prior_actual_stills(report):
    previous = ROOT.parent / 'story-director-16frames-v1'
    prior = json.loads((previous / 'proof/FRAME_RENDER_REPORT.json').read_bytes())
    samples = [300, 600, 900, 1500]
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
    image = Image.new('RGB', (720, 2720), '#10151b')
    draw = ImageDraw.Draw(image)
    receipts = []
    for index, frame in enumerate(samples):
        old = next(r for r in prior['frames'] if r['globalFrame'] == frame)
        new = next(r for r in report['frames'] if r['globalFrame'] == frame)
        for column, (base,row,key,label) in enumerate([(previous,old,'png_sha256','PRIOR ACTUAL STILL'),(ROOT,new,'pngSHA256','NEW SOURCE REVIEW')]):
            raw = (base / row['file']).read_bytes()
            if sha(raw) != row[key]:
                raise ValueError('COMPARISON_ACTUAL_INPUT_SHA_MISMATCH')
            with Image.open(base / row['file']) as source:
                thumb = source.convert('RGB').resize((360,640),Image.Resampling.LANCZOS)
            x,y = column*360,index*680
            draw.text((x+8,y+8),f'{label} | {frame/30:.0f}s',font=font,fill='white')
            image.paste(thumb,(x,y+40))
        receipts.append({'globalFrame':frame,'priorPNG':old['png_sha256'],'newPNG':new['pngSHA256'],
            'sameGlobalTime':True,'cameraProfilesDiffer':True,'priorImageNewlyRendered':False})
    image.save(PUBLIC/'PRIOR_VS_NEW_4_TIMES.png')
    return receipts


if __name__ == '__main__':
    report = json.loads((ROOT / 'proof/ACTUAL_CAPTURE.json').read_bytes())
    if report['status'] != 'ACTUAL_SOURCE_REVIEW_DRAW_COMPLETE' or len(report['stillsRequested']) != 16:
        raise ValueError('COMPLETE_ACTUAL_SOURCE_REVIEW_CAPTURE_REQUIRED')
    clips = encode(report)
    contact(report)
    comparison = compare_prior_actual_stills(report)
    result = {'schema': 'WORLD_ENGINE_ASTRA_V2_REVIEW_MEDIA_VALIDATION_V1',
        'actualUniqueDrawFrames': len(report['frames']), 'actualStills': 16, 'actualSourceReviewWindows': 3,
        'originalGlobalTimePreserved': True, 'cleanClips': 3, 'burnedInReviewClips': 3,
        'backend': report['backend'], 'technicalMediaValidation': 'PASS',
        'requestedVisualContractStatus': 'NEEDS_REWORK_BLOCKED_CONTROL_AND_LOCAL_SOURCE',
        'clips': [{k: v for k, v in c.items() if k != 'frames'} for c in clips],
        'comparison':comparison,'currentReferenceVideoDirectlyWatchedThisRun':False,
        'full80SecondMP4Produced': False, 'paidGPUExecuted': False, 'nvidiaHardwareVerified': False,
        'visualQualityApproved': False, 'next': 'USER_REVIEW_REQUIRED'}
    (ROOT / 'reports/MEDIA_VALIDATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'clips'}))
