"""Select the v021 overlay page over the unchanged certified v020 transport."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
from .backends import CPULocalBackend
from .reference_effects_backend import reference_effects_command
from .story_progression import _selection, _strict_equal, progression_qc


def story_progression_command(command):
    mapped = reference_effects_command(command)
    if '--scene-json' not in mapped or '--url' not in mapped:
        return mapped
    scene = json.loads(Path(mapped[mapped.index('--scene-json') + 1]).read_text())
    selected = scene.get('story_progression')
    if (not isinstance(selected, dict)
            or not _strict_equal(selected, _selection(scene, selected.get('fps')))
            or not progression_qc(scene)['passed']):
        raise RuntimeError('STORY_PROGRESSION_SOURCE_MISMATCH')
    index = mapped.index('--url') + 1
    url = urlsplit(mapped[index])
    if url.path != '/static/render_reference_effects_earth.html':
        raise RuntimeError('STORY_PROGRESSION_RENDER_PAGE_INVALID')
    mapped[index] = urlunsplit(url._replace(path='/static/render_story_progression_earth.html'))
    return mapped


class StoryProgressionBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(story_progression_command(command), cwd, progress)
