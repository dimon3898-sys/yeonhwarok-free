from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import json,hashlib
from .backends import CPULocalBackend
from .second_event_camera import ROOT,SOURCES,PRESET

def second_command(command):
    command=list(command)
    if '--scene-json' not in command or '--url' not in command:return command
    scene=json.loads(Path(command[command.index('--scene-json')+1]).read_text());config=scene.get('second_event_camera',{})
    if config.get('preset')!=PRESET:raise RuntimeError('SECOND_CAMERA_PRESET_REQUIRED')
    if config.get('source_hashes')!={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}:raise RuntimeError('SECOND_CAMERA_SOURCE_MISMATCH')
    i=command.index('--url')+1;url=urlsplit(command[i])
    if url.path not in {'/render_production_earth.html','/static/render_production_earth.html'}:raise RuntimeError('SECOND_CAMERA_PAGE_INVALID')
    command[i]=urlunsplit(url._replace(path='/static/render_second_event_earth.html'));return command
class SecondEventBackend(CPULocalBackend):
    def run(self,command,cwd,progress):return super().run(second_command(command),cwd,progress)
