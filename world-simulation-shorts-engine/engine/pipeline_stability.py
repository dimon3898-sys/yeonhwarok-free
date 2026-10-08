"""Additive assembly validation over the immutable certified render function.

Each invocation has its own globals; no shared monkeypatch, renderer or cache
quality override. The original function and promotion evidence remain intact.
"""
from types import FunctionType
from . import rendering
from .audio_stability import create_audio, finish_video


def checked_concat(scenes, destination, settings):
    if not scenes:
        raise RuntimeError('CONCAT_INPUT_INVALID')
    signature = None
    for movie in scenes:
        metadata = rendering.probe_video(movie)
        videos = [stream for stream in metadata['streams'] if stream['codec_type'] == 'video']
        if len(videos) != 1:
            raise RuntimeError('CONCAT_INPUT_INVALID')
        stream = videos[0]
        current = tuple(stream.get(key) for key in ('codec_name', 'width', 'height', 'avg_frame_rate', 'time_base', 'pix_fmt'))
        if (stream.get('codec_name') != 'h264' or stream.get('pix_fmt') != 'yuv420p'
                or stream.get('width') != settings['output_width'] or stream.get('height') != settings['output_height']
                or signature is not None and signature != current):
            raise RuntimeError('CONCAT_INPUT_INCOMPATIBLE')
        signature = current
    return rendering._concat(scenes, destination, settings)


def render_project(*args, **kwargs):
    diagnostic = kwargs.pop('diagnostic', None)
    original = rendering.render_project
    if not isinstance(original, FunctionType):
        return original(*args, **kwargs)  # Existing injected unit test backend.
    namespace = dict(original.__globals__)
    namespace['_concat'] = checked_concat
    namespace['create_audio'] = create_audio
    namespace['finish_video'] = finish_video
    if len(args)>1 and any(scene.get('visual_readability') for scene in args[1].get('scenes', [])):
        from .readability_backend import ReadabilityBackend
        namespace['CPULocalBackend'] = ReadabilityBackend
    if len(args)>1 and any(scene.get('direction') for scene in args[1].get('scenes', [])):
        from .direction_backend import DirectionBackend
        from .direction import direction_qc
        if any(s.get('direction',{}).get('version')=='reference_master_v013' for s in args[1]['scenes']):
            from .reference_concat import concat as reference_concat
            namespace['_concat']=reference_concat
            from .reference_concat import verified_assembly
            from pathlib import Path
            valid_original=namespace['valid_scene_file']
            def valid_reference_file(path,*values,**options):
                if Path(path).name.startswith('assembled_muted') and not verified_assembly(path):return False
                return valid_original(path,*values,**options)
            namespace['valid_scene_file']=valid_reference_file
            from .reference_backend import ReferenceBackend
            from .reference_master import perceptual_qc
            DirectionBackend=ReferenceBackend
            direction_qc=perceptual_qc
            from .reference_preflight import collect,native_perceptual_qc
            perceptual_native=native_perceptual_qc(args[1],collect(args[1]))
            if not perceptual_native['passed']:raise RuntimeError('REFERENCE_PERCEPTUAL_PREFLIGHT_FAILED')
        report = direction_qc(args[1])
        if diagnostic:
            diagnostic.write('direction-plan.json', dict(qc=report,
                scenes=[dict(scene_id=s['scene_id'], direction=s.get('direction')) for s in args[1]['scenes']]))
        if not report['passed']:
            raise RuntimeError('DIRECTION_PREFLIGHT_FAILED')
        namespace['CPULocalBackend'] = DirectionBackend
    if len(args)>1 and args[1].get('metadata',{}).get('camera_test_preset')=='SINGLE_EVENT_CAMERA_TEST':
        from .single_event_backend import SingleEventBackend
        from .reference_concat import concat as reference_concat
        namespace['CPULocalBackend']=SingleEventBackend
        namespace['_concat']=reference_concat
    if len(args)>1 and args[1].get('metadata',{}).get('camera_test_preset')=='SINGLE_EVENT_RETURN_TO_WIDE_TEST':
        from .return_wide_backend import ReturnWideBackend
        from .return_wide_qc import run_qc as return_qc
        from .reference_concat import concat as reference_concat
        namespace['CPULocalBackend']=ReturnWideBackend
        namespace['_concat']=reference_concat
        namespace['run_qc']=return_qc
    if diagnostic:
        from .gpu_preflight import collect_all
        preflight = collect_all(args[0], args[1], diagnostic)
        if any(s.get('direction') for s in args[1].get('scenes', [])):
            preflight['direction'] = dict(qc=report,
                perceptual=locals().get('perceptual_native'),
                scenes=[dict(scene_id=s['scene_id'], beats=s['direction']['beats']) for s in args[1]['scenes']])
            diagnostic.write('preflight.json', preflight)
        backend = namespace['CPULocalBackend']
        namespace['CPULocalBackend'] = lambda: backend(diagnostic=diagnostic)
        def recorded_audio(*values, **options):
            result = create_audio(*values, **options)
            diagnostic.write('audio-diagnostics.json', result)
            return result
        namespace['create_audio'] = recorded_audio
    run = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    run.__kwdefaults__ = original.__kwdefaults__
    return run(*args, **kwargs)
