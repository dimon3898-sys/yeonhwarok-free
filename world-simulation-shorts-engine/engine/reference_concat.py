"""Lossless frame-clock concat for variable-length reference-master beats.

Bookworm FFmpeg rounds MP4 format durations to milliseconds. Using those
rounded values as concat offsets can turn an exact 30 fps sequence into a
slightly slower average. Explicit frame-count durations preserve the clock;
legacy concat and all encoding/QC policies are unchanged.
"""
from fractions import Fraction
from pathlib import Path
import json
import hashlib
import subprocess
from .qc import probe_video


def packet_clock(movie):
    result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_packets','-show_entries','packet=pts,duration,data_hash',
        '-show_data_hash','sha256','-of','json',str(movie)],
        capture_output=True,text=True,check=True)
    return json.loads(result.stdout)['packets']


def parameter_set(movie):
    result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_streams','-show_data_hash','sha256','-show_entries','stream=extradata_hash',
        '-of','json',str(movie)],capture_output=True,text=True,check=True)
    return json.loads(result.stdout)['streams'][0]['extradata_hash']


def file_hash(movie):
    with Path(movie).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verified_assembly(movie):
    try:
        movie=Path(movie);record=json.loads(movie.with_suffix('.frame-clock.json').read_text())
        return (record['contract']=='REFERENCE_MASTER_FRAME_COUNT_CONCAT_V1' and
                record['packet_payloads_unchanged'] is True and record['pts_sequential'] is True and
                record['file_sha256']==file_hash(movie))
    except (OSError,ValueError,KeyError,TypeError):return False


def concat(scenes,destination,settings):
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    if not scenes:raise RuntimeError('CONCAT_INPUT_INVALID')
    fps=Fraction(settings['fps']);signature=None;parameters=None;inputs=[];total=0
    for movie in scenes:
        streams=[s for s in probe_video(movie)['streams'] if s['codec_type']=='video']
        if len(streams)!=1:raise RuntimeError('CONCAT_INPUT_INVALID')
        s=streams[0];current=tuple(s.get(k) for k in ('codec_name','width','height','avg_frame_rate','time_base','pix_fmt'))
        if (s['codec_name']!='h264' or s['pix_fmt']!='yuv420p' or
            s['width']!=settings['output_width'] or s['height']!=settings['output_height'] or
            Fraction(s['avg_frame_rate'])!=fps or signature is not None and current!=signature):
            raise RuntimeError('CONCAT_INPUT_INCOMPATIBLE')
        signature=current;n=int(s['nb_frames']);ticks=Fraction(1,1)/fps/Fraction(s['time_base'])
        packets=packet_clock(movie);pts=sorted(int(p['pts']) for p in packets)
        if n<=0 or ticks.denominator!=1 or len(packets)!=n or pts!=[i*int(ticks) for i in range(n)]:
            raise RuntimeError('CONCAT_INPUT_FRAME_CLOCK_INVALID')
        current_parameters=parameter_set(movie)
        if parameters is not None and current_parameters!=parameters:
            raise RuntimeError('CONCAT_INPUT_PARAMETER_SETS_INCOMPATIBLE')
        parameters=current_parameters
        inputs.append((Path(movie),n,packets));total+=n
    listing=destination.with_suffix('.concat.txt')
    with listing.open('x',encoding='utf-8') as stream:
        stream.write('ffconcat version 1.0\n')
        for movie,n,_ in inputs:
            escaped=str(movie.resolve()).replace("'","'\\''")
            stream.write(f"file '{escaped}'\nduration {float(Fraction(n,1)/fps):.15f}\n")
    result=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-f','concat','-safe','0','-auto_convert','0',
        '-i',str(listing),'-map','0:v:0','-c:v','copy','-an','-movflags','+faststart',str(destination)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('SCENE_ASSEMBLY_FAILED: '+result.stderr[-2000:])
    output=packet_clock(destination);meta=probe_video(destination);s=next(s for s in meta['streams'] if s['codec_type']=='video')
    tick=Fraction(1,1)/fps/Fraction(s['time_base'])
    if (len(output)!=total or tick.denominator!=1 or
        sorted(int(p['pts']) for p in output)!=[i*int(tick) for i in range(total)] or
        [p['data_hash'] for p in output]!=[p['data_hash'] for _,_,packets in inputs for p in packets] or
        Fraction(s['avg_frame_rate'])!=fps):
        raise RuntimeError('CONCAT_OUTPUT_FRAME_CLOCK_INVALID')
    destination.with_suffix('.frame-clock.json').write_text(json.dumps(dict(
        contract='REFERENCE_MASTER_FRAME_COUNT_CONCAT_V1',frames=total,fps=str(fps),
        file_sha256=file_hash(destination),packet_payloads_unchanged=True,parameter_sets_identical=True,pts_sequential=True,source_frame_counts=[n for _,n,_ in inputs])))
