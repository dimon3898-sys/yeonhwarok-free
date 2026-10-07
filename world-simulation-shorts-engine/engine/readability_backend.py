"""Page selection only. The original GPU-required worker/lifecycle is reused."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib
import json
from .backends import CPULocalBackend


def readable_command(command):
    command = list(command)
    if len(command) < 2 or command[0] != 'node' or Path(command[1]).name != 'render_production_scene.mjs':
        return command
    if '--scene-json' not in command or '--url' not in command:
        return command
    scene = json.loads(Path(command[command.index('--scene-json')+1]).read_text())
    policy = scene.get('visual_readability', {})
    if policy.get('version') != 'readability_v011':
        return command
    root = Path(__file__).resolve().parents[1]
    for name in ['web/readability_visual_adapter.js', 'web/render_readable_earth.html']:
        if policy.get('source_hashes', {}).get(name) != hashlib.sha256((root/name).read_bytes()).hexdigest():
            raise RuntimeError('READABILITY_SOURCE_MISMATCH')
    i = command.index('--url')+1
    url = urlsplit(command[i])
    if url.path not in {'/render_production_earth.html', '/static/render_production_earth.html'}:
        raise RuntimeError('READABILITY_RENDERER_PAGE_MISMATCH')
    command[i] = urlunsplit(url._replace(path='/static/render_readable_earth.html'))
    return command


class ReadabilityBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(readable_command(command), cwd, progress)
