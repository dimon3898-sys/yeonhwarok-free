"""Version/hash checked page selection; certified worker and GPU profile reused."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib
import json
from .backends import CPULocalBackend
from .direction import ROOT, VERSION, SOURCES


def direction_command(command):
    command=list(command)
    if (len(command)<2 or command[0]!='node'
            or Path(command[1]).name!='render_production_scene.mjs'
            or '--scene-json' not in command or '--url' not in command):
        return command
    scene=json.loads(Path(command[command.index('--scene-json')+1]).read_text())
    config=scene.get('direction', {})
    if config.get('version') != VERSION:
        return command
    if set(config.get('source_hashes', {})) != set(SOURCES):
        raise RuntimeError('DIRECTION_SOURCE_SET_MISMATCH')
    for name, expected in config['source_hashes'].items():
        if name not in ('web/direction_visual_adapter.js','web/render_direction_earth.html',
                        'web/render_direction_flat.html','tools/direction_semantic_preflight.mjs'):
            raise RuntimeError('DIRECTION_SOURCE_INVALID')
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('DIRECTION_SOURCE_MISMATCH')
    i=command.index('--url')+1;url=urlsplit(command[i])
    flat=scene.get('render_mode')=='FLAT_MAP_PREMIUM'
    original='render_production_flat.html' if flat else 'render_production_earth.html'
    if url.path not in {'/'+original,'/static/'+original}:
        raise RuntimeError('DIRECTION_RENDERER_PAGE_MISMATCH')
    command[i]=urlunsplit(url._replace(path='/static/render_direction_'+('flat' if flat else 'earth')+'.html'))
    return command


class DirectionBackend(CPULocalBackend):
    def run(self, command, cwd, progress):
        return super().run(direction_command(command),cwd,progress)
