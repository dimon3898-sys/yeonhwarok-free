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
    original = rendering.render_project
    if not isinstance(original, FunctionType):
        return original(*args, **kwargs)  # Existing injected unit test backend.
    namespace = dict(original.__globals__)
    namespace['_concat'] = checked_concat
    namespace['create_audio'] = create_audio
    namespace['finish_video'] = finish_video
    run = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    run.__kwdefaults__ = original.__kwdefaults__
    return run(*args, **kwargs)
