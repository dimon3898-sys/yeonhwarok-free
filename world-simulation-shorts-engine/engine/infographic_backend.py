"""Source-checked v022 overlay over the existing GPU-required transport.

Page selection is the only transport change. Chromium flags, audited JPEG
extraction, encoder lifecycle and GPU admission remain the original backend.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .backends import CPULocalBackend


def infographic_command(command):
    mapped = list(command)
    if '--scene-json' not in mapped or '--url' not in mapped:
        return mapped
    scene = json.loads(Path(mapped[mapped.index('--scene-json') + 1]).read_text())
    from .infographic_contract import validate_scene_infographic
    checked = validate_scene_infographic(scene)
    if not checked['passed']:
        raise RuntimeError('INFOGRAPHIC_SCENE_SOURCE_MISMATCH')
    family = scene['infographic']['parent_renderer_family']
    if family == 'story-progression-v021':
        from .story_progression_backend import story_progression_command
        mapped = story_progression_command(mapped)
        expected = '/static/render_story_progression_earth.html'
    elif family == 'production-earth-v1':
        expected = '/static/render_production_earth.html'
    else:
        raise RuntimeError('INFOGRAPHIC_RENDERER_FAMILY_INVALID')
    index = mapped.index('--url') + 1
    url = urlsplit(mapped[index])
    if url.path != expected:
        raise RuntimeError('INFOGRAPHIC_PARENT_RENDER_PAGE_INVALID')
    mapped[index] = urlunsplit(url._replace(path='/static/render_infographic_earth.html'))
    return mapped


class InfographicBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(infographic_command(command), cwd, progress)
