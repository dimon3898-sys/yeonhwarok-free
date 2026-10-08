"""Entire synthetic JPEG -> scene MP4 -> concat -> real audio -> QC path.

These are generated test patterns, NOT map renders or GPU success evidence.
Native pose/eligibility records are explicitly projections, never post-draw proof.
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time
from PIL import Image, ImageDraw
from engine.assets import APP_ROOT
from engine.qa_planner import generate_deployment_plan
from engine.audio import create_subtitles, ESpeakProvider
from engine.audio_stability import create_audio, finish_video
from engine.qc import probe_video, run_qc, valid_scene_file
from engine.reference_concat import concat as _concat
from engine.pipeline_stability import checked_concat as _legacy_concat
from .asset_audit import audit_assets

REQUEST=dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=12,qa_mode=True,quality='HIGH',pace='FAST_PLUS',tts=False,subtitles=False,bgm=True,sfx=True,direction_profile='REFERENCE_MASTER')

def run(directory):
    started=time.monotonic();directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    plan=generate_deployment_plan(REQUEST);(directory/'plan.json').write_text(json.dumps(plan,ensure_ascii=False))
    command=['node',str(APP_ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(directory/'plan.json'),'--output',str(directory/'poses.json')]
    subprocess.run(command,cwd=APP_ROOT,check=True,capture_output=True,text=True,timeout=90)
    poses=json.loads((directory/'poses.json').read_text());movies=[];audits=[];times=[]
    for scene in plan['scenes']:
        sid=scene['scene_id'];folder=directory/sid;folder.mkdir();frames=[];begin=time.monotonic()
        for i in range(round(scene['duration']*30)):
            # Frame-varying readable image covering the full canvas; not terrain.
            image=Image.new('RGB',(2160,3840),(35+i%50,70+i%65,105+i%70))
            draw=ImageDraw.Draw(image);draw.rectangle((i*19%1700,180,i*19%1700+320,2600),fill=(180,120,55))
            draw.text((220,330),'SYNTHETIC PIPELINE TEST - NO GPU MAP',fill='white')
            file=folder/f'{i:04}.jpg';image.save(file,quality=99)
            with Image.open(file) as decoded:
                decoded.load();dimensions=list(decoded.size)
            frames.append(dict(path=str(file),decoded=dimensions))
        output=folder/'scene.mp4'
        fixture=dict(internalWidth=2160,internalHeight=3840,outputWidth=1080,outputHeight=1920,fps=30,quality='HIGH',destination=str(output),frames=frames)
        (folder/'pipe.json').write_text(json.dumps(fixture))
        pipe=subprocess.run(['node',str(APP_ROOT/'tools/check_jpeg_pipe.mjs'),str(folder/'pipe.json')],cwd=APP_ROOT,capture_output=True,text=True,timeout=240)
        if pipe.returncode:raise RuntimeError('SYNTHETIC_PIPE_FAILED: '+sid+' '+pipe.stderr[-1500:])
        assert valid_scene_file(output,scene['duration'],1080,1920,30)
        movie=probe_video(output);video=next(s for s in movie['streams'] if s['codec_type']=='video')
        assert video['pix_fmt']=='yuv420p' and int(video['nb_frames'])==round(scene['duration']*30)
        movies.append(output);audits.append([r for r in poses['pose_records'] if r['scene_id']==sid])
        times.append(dict(scene_id=sid,seconds=round(time.monotonic()-begin,3),frames=len(frames)))
    settings=dict(output_width=1080,output_height=1920,fps=30)
    baseline=directory/'legacy-offset-assembled.mp4';_legacy_concat(movies,baseline,settings)
    baseline_meta=probe_video(baseline)
    concat=directory/'assembled.mp4';_concat(movies,concat,settings)
    audio=create_audio(plan,directory/'audio');subtitles=create_subtitles(plan,directory/'audio',audio.get('narration_cues',[]))
    audio_meta=probe_video(Path(audio['file']));assert float(audio_meta['format']['duration'])==12
    outputs=finish_video(concat,directory/'final',plan,audio,subtitles)
    baseline_outputs=finish_video(baseline,directory/'legacy-offset-final',plan,audio,subtitles)
    def clock(path):
        meta=probe_video(Path(path));s=next(s for s in meta['streams'] if s['codec_type']=='video')
        return dict(avg_frame_rate=s['avg_frame_rate'],stream_duration=s['duration'],format_duration=meta['format']['duration'],frames=s['nb_frames'],time_base=s['time_base'])
    frame_clock=dict(before=clock(baseline_outputs['final']),after=clock(outputs['final']),
        source_clocks=[clock(movie) for movie in movies],
        verification=json.loads(concat.with_suffix('.frame-clock.json').read_text()))
    qc=run_qc(Path(outputs['final']),plan,audits,directory/'qc',subtitles=subtitles,sound_cues=audio.get('sfx_library'))
    optional={}
    for option in ('subtitles','tts'):
        altered=copy.deepcopy(plan);altered['options'][option]=True
        try:
            if option=='subtitles':
                output=create_subtitles(altered,directory/'audio',[])
                optional[option]=dict(status='PASS',captions=len(output.get('captions',[])))
                finish_video(concat,directory/'subtitled',altered,audio,output)
            else:
                result=create_audio(altered,directory/'tts_audio')
                optional[option]=dict(status='PASS',narration_count=len(result['narration_cues']))
        except RuntimeError as error:
            code=str(error).split(':',1)[0]
            if option=='tts' and code in {'NARRATION_EXCEEDS_SCENE','TTS_PROVIDER_UNAVAILABLE'}:
                optional[option]=dict(status='EXPECTED_POLICY_REJECTION',code=code)
            else:raise
    report=dict(passed=qc['passed'],scene_jpeg_ffmpeg='PASS',concat='PASS',audio='PASS',
                qc_failures=qc['failures'],qc_warnings=qc['warnings'],decoded_frames=qc['decoded_frames'],
                optional=optional,assets=audit_assets(),scene_times=times,total_seconds=round(time.monotonic()-started,3),
                gpu_render='NOT_RUN',frame_clock=frame_clock,scope='Synthetic patterns at HIGH internal/output resolution; native pose/layout eligibility only. QC pipeline exercised; no post-GPU-draw, map aesthetics or production MP4 validation claim.')
    (directory/'REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({key:value for key,value in report.items() if key!='assets'},ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    import sys
    if len(sys.argv)==2: result=run(sys.argv[1])
    else:
        with tempfile.TemporaryDirectory(prefix='synthetic-pipeline-') as directory:result=run(directory)
    raise SystemExit(0 if result['passed'] else 1)
