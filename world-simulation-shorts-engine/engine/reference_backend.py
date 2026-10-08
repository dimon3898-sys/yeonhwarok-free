"""Checked v013 page selection over the unchanged production worker/GPU profile."""
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import hashlib,json
from .direction_backend import DirectionBackend,direction_command
from .reference_master import ROOT,VERSION,SOURCES


def reference_command(command):
    command=list(command)
    if len(command)<2 or command[0]!='node' or Path(command[1]).name!='render_production_scene.mjs' or '--scene-json' not in command or '--url' not in command:return command
    scene=json.loads(Path(command[command.index('--scene-json')+1]).read_text());p=scene.get('direction',{})
    if p.get('version')!=VERSION:return direction_command(command)
    if set(p.get('source_hashes',{}))!=set(SOURCES):raise RuntimeError('REFERENCE_SOURCE_SET_MISMATCH')
    for name,digest in p['source_hashes'].items():
        if name not in SOURCES:raise RuntimeError('REFERENCE_SOURCE_INVALID')
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('REFERENCE_SOURCE_MISMATCH')
    i=command.index('--url')+1;url=urlsplit(command[i]);kind='flat' if scene.get('render_mode')=='FLAT_MAP_PREMIUM' else 'earth'
    if url.path not in {'/render_production_'+kind+'.html','/static/render_production_'+kind+'.html'}:raise RuntimeError('REFERENCE_PAGE_MISMATCH')
    command[i]=urlunsplit(url._replace(path='/static/render_reference_'+kind+'.html'));return command


class ReferenceBackend(DirectionBackend):
    def run(self,command,cwd,progress):
        # CPULocalBackend is the historical worker name; gpu-required remains
        # enforced by its unchanged validated Chromium wrapper/admission gate.
        from .backends import CPULocalBackend
        return CPULocalBackend.run(self,reference_command(command),cwd,progress)
