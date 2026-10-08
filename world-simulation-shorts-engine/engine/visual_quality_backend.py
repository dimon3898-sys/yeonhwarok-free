"""Reuse the verified NVIDIA transport; opt-in selects only a surface adapter."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
from .backends import CPULocalBackend
from .second_event_backend import second_command
from .visual_quality import _contract


def quality_command(command):
    mapped = second_command(command)
    if '--scene-json' not in mapped or '--url' not in mapped:
        return mapped
    scene = json.loads(Path(mapped[mapped.index('--scene-json')+1]).read_text())
    if scene.get('visual_quality') != _contract():
        raise RuntimeError('VISUAL_QUALITY_SOURCE_MISMATCH')
    index = mapped.index('--url')+1
    url = urlsplit(mapped[index])
    if url.path != '/static/render_second_event_earth.html':
        raise RuntimeError('VISUAL_QUALITY_RENDER_PAGE_INVALID')
    mapped[index] = urlunsplit(url._replace(path='/static/render_visual_quality_earth.html'))
    return mapped


class VisualQualityBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(quality_command(command), cwd, progress)
