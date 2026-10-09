"""Select v020 overlay page; keep the certified NVIDIA/encoder transport."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
from .backends import CPULocalBackend
from .event_quality_backend import event_quality_command
from .reference_effects import _contract, _events


def reference_effects_command(command):
    mapped = event_quality_command(command)
    if '--scene-json' not in mapped or '--url' not in mapped:
        return mapped
    scene = json.loads(Path(mapped[mapped.index('--scene-json') + 1]).read_text())
    if scene.get('reference_effects') != dict(**_contract(), events=_events(scene)):
        raise RuntimeError('REFERENCE_EFFECTS_SOURCE_MISMATCH')
    index = mapped.index('--url') + 1
    url = urlsplit(mapped[index])
    if url.path != '/static/render_event_quality_earth.html':
        raise RuntimeError('REFERENCE_EFFECTS_RENDER_PAGE_INVALID')
    mapped[index] = urlunsplit(url._replace(path='/static/render_reference_effects_earth.html'))
    return mapped


class ReferenceEffectsBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(reference_effects_command(command), cwd, progress)
