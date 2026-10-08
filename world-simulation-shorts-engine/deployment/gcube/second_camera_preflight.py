"""720-frame second-event camera math and actual production collect-all admission."""
import json,subprocess
from pathlib import Path
from engine.qa_planner import generate_deployment_plan
from engine.second_event_camera import PRESET,ROOT
from engine.second_event_qc import camera_qc
from deployment.gcube.framegrid_preflight import check

def run(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    plan=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=24,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True))
    path=folder/'plan.json';path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    result=subprocess.run(['node','tools/test_second_event_camera.mjs',str(path)],cwd=ROOT,capture_output=True,text=True)
    if result.returncode:
        print('::error title=Second-event native camera verifier::'+json.dumps(dict(return_code=result.returncode,stderr=result.stderr[-5000:])))
        result.check_returncode()
    geometry=json.loads(result.stdout);(folder/'camera.json').write_text(result.stdout)
    camera=camera_qc(plan,geometry['audits']);assert camera['passed'],camera
    native=check(plan,folder/'collect-all')
    if not native['passed']:
        print('::error title=Second-event collect-all preflight::'+json.dumps(native))
    assert native['passed'],native
    records=native['scenes'][0]['checks'][1]['report']['pose_records'];assert len(records)==720
    for actual,expected in zip(records,geometry['audits']):
        assert actual['frame_index']==expected['frame_index']
        assert actual['cameraPosition']==expected['cameraPosition']
        assert actual['cameraFov']==expected['cameraFov']
    config=plan['scenes'][0]['second_event_camera']
    report=dict(passed=True,timeline=config['timeline'],adaptive_wide=config['adaptive_wide'],adaptive_projection=geometry['adaptive_projection'],frames=720,gap=0,overlap=0,last_end_frame=720,baseline_first_360_identical=geometry['baseline_first_360_identical'],scene_json_init_scope_passed=geometry['scene_json_init_scope_passed'],first_event_focus_labels_identical=geometry['first_event_focus_labels_identical'],maximum_quaternion_step_degrees=geometry['maximum_quaternion_step_degrees'],maximum_translation_step=geometry['maximum_translation_step'],camera_qa=camera,collect_all=native['passed'],GPU='NOT_RUN',scope='camera math/native geometry and fixture label planning; actual GPU post-draw camera QC NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('::notice title=Second-event camera::'+json.dumps(report));return report

def media(folder):
    """Real 24s CPU codec/audio/QC fixture; never a GPU scene render."""
    folder=Path(folder);plan=json.loads((folder/'plan.json').read_text());geometry=json.loads((folder/'camera.json').read_text())
    from engine.audio_stability import create_audio,finish_video
    from engine.reference_concat import concat
    from engine.second_event_qc import run_qc
    from engine.qc import probe_video
    movie=folder/'synthetic.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=1080x1920:rate=30','-frames:v','720','-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1',str(movie)],check=True,capture_output=True)
    assembled=folder/'assembled.mp4';concat([movie],assembled,dict(output_width=1080,output_height=1920,fps=30))
    audio=create_audio(plan,folder/'audio');output=finish_video(assembled,folder/'final',plan,audio,{'enabled':False})
    report=run_qc(Path(output['final']),plan,geometry['audits'],folder/'qc')
    print('::notice title=Second-event synthetic technical QC::'+json.dumps(dict(passed=report['passed'],failures=report['failures'],camera_qa=report['camera_qa'],excluded_production=report['production_policy_not_applicable'],scope='synthetic CPU codec/audio and camera fixture; physical NVIDIA pixels NOT_RUN')))
    assert report['passed'],report['failures']
    probe=probe_video(Path(output['final']));stream=next(s for s in probe['streams'] if s['codec_type']=='video');assert int(stream['nb_frames'])==720 and float(probe['format']['duration'])==24
    return report

if __name__=='__main__':
    import sys
    run(sys.argv[1])
