"""Collect-all native/static preflight; never constructs a WebGL renderer."""
import json,math,subprocess,time
from pathlib import Path
from .assets import APP_ROOT,validate_assets
from .backends import quality_settings
from .schema import validate_plan

def collect_all(project_dir,plan,bundle):
    start=time.monotonic();checks=[];scenes=[]
    def run(name,callback):
        try:
            result=callback();passed=not isinstance(result,dict) or result.get('passed',True)
            checks.append(dict(name=name,passed=bool(passed),result=result));return result
        except Exception as error:checks.append(dict(name=name,passed=False,error_type=type(error).__name__));return None
    run('Scene_JSON',lambda:validate_plan(plan))
    run('licensed_assets',lambda:validate_assets(plan))
    from deployment.gcube.asset_audit import audit_assets
    run('deployed_assets',audit_assets)
    folder=Path(project_dir)
    # Actual persisted plan bytes used by the internal renderer page.
    plan_path=folder/'scene_plan.json'
    for scene in plan.get('scenes',[]):
        sid=scene.get('scene_id');record=dict(scene_id=sid,checks=[])
        try:
            quality=scene.get('render_quality',plan.get('options',{}).get('quality','HIGH'))
            quality=quality.get('preset',quality.get('mode','HIGH')) if isinstance(quality,dict) else quality
            settings=quality_settings(str(quality),scene)
            duration=float(scene['duration']);frames=duration*settings['fps']
            if not math.isfinite(duration) or duration<=0 or abs(frames-round(frames))>1e-7:raise ValueError('DURATION_FRAME_GRID_INVALID')
            input_path=folder/'scene_json'/(sid+'.json')
            if json.loads(input_path.read_text())!=scene:raise ValueError('RENDERER_SCENE_INPUT_MISMATCH')
            record['checks'].append(dict(name='duration_scene_input',passed=True,frames=round(frames),settings=settings))
        except Exception as error:record['checks'].append(dict(name='duration_scene_input',passed=False,error=str(error).split(':')[0]))
        try:
            p=subprocess.run(['node',str(APP_ROOT/'tools/collect_all_preflight.mjs'),'--plan',str(plan_path),'--scene',sid],cwd=APP_ROOT,capture_output=True,text=True,timeout=90)
            native=json.loads(p.stdout)
            record['checks'].append(dict(name='native_geometry_camera_route_entity_all_frames',passed=p.returncode==0 and native['passed'],report=native))
        except Exception as error:record['checks'].append(dict(name='native_geometry_camera_route_entity_all_frames',passed=False,error_type=type(error).__name__))
        record['passed']=all(c['passed'] for c in record['checks']);scenes.append(record)
    def paths():
        for name in ('renders','audio','qc','final','scene_json'):
            target=folder/name;target.mkdir(parents=True,exist_ok=True)
            probe=target/('diagnostic-write-'+bundle.job_id)
            with probe.open('x') as stream:stream.write('ok')
            probe.unlink()
        return {'passed':True,'checkpoint':'durable original checkpoint retained','output_attempt':'original _next_attempt; existing outputs never overwritten'}
    run('paths_checkpoint',paths)
    def encoder():
        p=subprocess.run(['ffmpeg','-hide_banner','-encoders'],capture_output=True,text=True,timeout=10)
        return {'passed':p.returncode==0 and 'libx264' in p.stdout and 'aac' in p.stdout,'image2pipe':'lazy after audited/decoded JPEG','actual_frame_encode':'NOT_RUN'}
    run('FFmpeg_command_capabilities',encoder)
    def concat_policy():
        signatures=set()
        for scene in plan['scenes']:
            quality=scene.get('render_quality',plan.get('options',{}).get('quality','HIGH'))
            quality=quality.get('preset',quality.get('mode','HIGH')) if isinstance(quality,dict) else quality
            settings=quality_settings(str(quality),scene);seconds=float(scene['duration'])
            if not math.isfinite(seconds) or seconds<=0:raise ValueError('CONCAT_SCENE_DURATION_INVALID')
            signatures.add(tuple(settings[key] for key in ('output_width','output_height','fps')))
        return dict(passed=len(signatures)==1,resolution_consistency=len(signatures)==1,strict_final_qc='unchanged; real pixels/audio required after render',pixel_qc='NOT_RUN')
    run('Concat_QC_policy',concat_policy)
    def sound():
        from .audio_stability import create_audio
        from .audio import create_subtitles
        audio_path=folder/'audio/audio_report.json'
        audio=json.loads(audio_path.read_text()) if audio_path.is_file() else create_audio(plan,folder/'audio')
        from .audio import _stereo
        if not Path(audio['file']).is_file() or len(_stereo(Path(audio['file'])))==0:raise ValueError('AUDIO_CHECKPOINT_INVALID')
        subtitle_path=folder/'audio/subtitle_report.json'
        if subtitle_path.is_file():subtitles=json.loads(subtitle_path.read_text())
        else:
            subtitles=create_subtitles(plan,folder/'audio',audio.get('narration_cues',[]))
            from .storage import atomic_json
            atomic_json(subtitle_path,subtitles,exclusive=True)
        bundle.write('audio-diagnostics.json',{'actual_audio':audio,'subtitles':subtitles})
        return {'passed':True,'audio':'PREPARED','TTS':plan.get('options',{}).get('tts'),'subtitle':plan.get('options',{}).get('subtitles')}
    run('Audio_Subtitle',sound)
    report=dict(passed=all(c['passed'] for c in checks) and all(s['passed'] for s in scenes),checks=checks,scenes=scenes,seconds=time.monotonic()-start,actual_approved_plan=True,gpu_draw='NOT_RUN')
    bundle.write('preflight.json',report)
    if not report['passed']:raise RuntimeError('COLLECT_ALL_PREFLIGHT_FAILED')
    return report
