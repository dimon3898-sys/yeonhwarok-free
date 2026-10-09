"""Select the explicit v019 material page using the original NVIDIA transport."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
from .backends import CPULocalBackend
from .visual_quality_backend import quality_command
from .event_quality import _contract


def event_quality_command(command):
    mapped = quality_command(command)
    if '--scene-json' not in mapped or '--url' not in mapped:
        return mapped
    scene = json.loads(Path(mapped[mapped.index('--scene-json')+1]).read_text())
    if scene.get('event_quality') != _contract():
        raise RuntimeError('EVENT_QUALITY_SOURCE_MISMATCH')
    index = mapped.index('--url')+1
    url = urlsplit(mapped[index])
    if url.path != '/static/render_visual_quality_earth.html':
        raise RuntimeError('EVENT_QUALITY_RENDER_PAGE_INVALID')
    mapped[index] = urlunsplit(url._replace(path='/static/render_event_quality_earth.html'))
    return mapped


class EventQualityBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(event_quality_command(command), cwd, progress)
