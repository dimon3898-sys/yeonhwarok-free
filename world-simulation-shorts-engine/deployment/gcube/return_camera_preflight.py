"""450-frame return-to-wide camera math + unchanged production collect-all admission."""
import json,subprocess
from pathlib import Path
from engine.qa_planner import generate_deployment_plan
from engine.return_wide_camera import PRESET,ROOT
from engine.return_wide_qc import camera_qc
from deployment.gcube.framegrid_preflight import check

def run(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    plan=generate_deployment_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?',duration=15,qa_mode=True,direction_profile=PRESET,quality='HIGH',tts=False,subtitles=False,bgm=True,sfx=True))
    path=folder/'plan.json';path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    result=subprocess.run(['node','tools/test_return_wide_camera.mjs',str(path)],cwd=ROOT,capture_output=True,text=True,check=True)
    geometry=json.loads(result.stdout);(folder/'camera.json').write_text(result.stdout)
    camera=camera_qc(plan,geometry['audits']);assert camera['passed'],camera
    native=check(plan,folder/'collect-all');assert native['passed'],native
    records=native['scenes'][0]['checks'][1]['report']['pose_records'];assert len(records)==450
    for actual,expected in zip(records,geometry['audits']):
        assert actual['frame_index']==expected['frame_index']
        assert actual['cameraPosition']==expected['cameraPosition']
        assert actual['cameraFov']==expected['cameraFov']
    report=dict(passed=True,timeline=plan['scenes'][0]['return_wide_camera']['timeline'],frames=450,gap=0,overlap=0,last_end_frame=450,baseline_first_360_identical=geometry['baseline_first_360_identical'],camera_qa=camera,collect_all=native['passed'],GPU='NOT_RUN',scope='camera math/native geometry and fixture label planning; actual GPU post-draw camera QC NOT_RUN')
    (folder/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('::notice title=Return-wide camera::'+json.dumps(report));return report
if __name__=='__main__':
    import sys
    run(sys.argv[1])

def media(folder):
    """Real 15s CPU codec/audio/QC fixture; never a GPU scene render."""
    folder=Path(folder);plan=json.loads((folder/'plan.json').read_text());geometry=json.loads((folder/'camera.json').read_text())
    from engine.audio_stability import create_audio,finish_video
    from engine.reference_concat import concat
    from engine.return_wide_qc import run_qc
    from engine.qc import probe_video
    movie=folder/'synthetic.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=1080x1920:rate=30','-frames:v','450','-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1',str(movie)],check=True,capture_output=True)
    assembled=folder/'assembled.mp4';concat([movie],assembled,dict(output_width=1080,output_height=1920,fps=30))
    audio=create_audio(plan,folder/'audio');output=finish_video(assembled,folder/'final',plan,audio,{'enabled':False})
    report=run_qc(Path(output['final']),plan,geometry['audits'],folder/'qc')
    print('::notice title=Return-wide synthetic technical QC::'+json.dumps(dict(passed=report['passed'],failures=report['failures'],camera_qa=report['camera_qa'],excluded_production=report['production_policy_not_applicable'],scope='synthetic CPU codec/audio and camera fixture; physical NVIDIA pixels NOT_RUN')))
    assert report['passed'],report['failures']
    probe=probe_video(Path(output['final']));stream=next(s for s in probe['streams'] if s['codec_type']=='video');assert int(stream['nb_frames'])==450 and float(probe['format']['duration'])==15
    return report
