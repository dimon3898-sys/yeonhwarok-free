from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import json,hashlib
from .backends import CPULocalBackend
from .single_event_camera import ROOT,SOURCES,PRESET

def single_command(command):
    command=list(command)
    if '--scene-json' not in command or '--url' not in command:return command
    scene=json.loads(Path(command[command.index('--scene-json')+1]).read_text());config=scene.get('single_event_camera',{})
    if config.get('preset')!=PRESET:raise RuntimeError('SINGLE_CAMERA_PRESET_REQUIRED')
    if config.get('source_hashes')!={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}:raise RuntimeError('SINGLE_CAMERA_SOURCE_MISMATCH')
    i=command.index('--url')+1;url=urlsplit(command[i])
    if url.path not in {'/render_production_earth.html','/static/render_production_earth.html'}:raise RuntimeError('SINGLE_CAMERA_PAGE_INVALID')
    command[i]=urlunsplit(url._replace(path='/static/render_single_event_earth.html'));return command
class SingleEventBackend(CPULocalBackend):
    def run(self,command,cwd,progress):return super().run(single_command(command),cwd,progress)
