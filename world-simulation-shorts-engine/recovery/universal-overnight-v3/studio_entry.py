"""Preserved HTTPS/auth/CSRF UI with an authenticated preview-only profile."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
from urllib.parse import urlsplit
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value

prior=load('_overnight_preserved_web',HERE.parent/'universal-integration-v1/studio_entry.py')
controller=load('_overnight_web_controller',HERE/'studio_controller.py')

def verify_extension():return load('_overnight_web_manifest',HERE/'package_manifest.py').verify_sources()

class Application(prior.Application):
    def __init__(self,*args,**kwargs):
        kwargs.setdefault('controller_factory',controller.StudioController)
        super().__init__(*args,**kwargs)
    def handler(self):
        original,app=super().handler(),self
        class Handler(original):
            def _dispatch(self):
                target=urlsplit(self.path)
                if self.command=='GET' and target.path in {'/api/integration/profile','/app.js'} and not (
                    target.scheme or target.netloc or target.query or target.fragment):
                    with app.core.lock:
                        if app.normal is None:return super()._dispatch()
                        self._configured_policy();self._authenticate(False)
                        if target.path=='/api/integration/profile':
                            return self._send(200,{'schema':'WORLD_ENGINE_OVERNIGHT_STUDIO_STATUS_V3',
                                'profile':'OVERNIGHT_SAFE_V3','promptSchema':'WORLD_ENGINE_STUDIO_PROMPT_V2',
                                'operation':'PREVIEW_5S','frameCount':150,'globalTimelinePreserved':True,
                                'full80Allowed':False,'renderAllowed':False,'gpuRenderingVerified':False,
                                'softwareValidationAvailableThroughPublicAPI':False})
                        source=(prior.proxy.parent.server.original.HERE/'web/app.js').read_text()
                        for key in ('job','start-','resume-'):
                            source=source.replace('world-studio-'+key,'world-studio-overnight-v3-'+key)
                        source += r'''
// Candidate-only labels; original UI/assets remain unchanged.
(() => {
 const byId=id=>document.getElementById(id);
 const duration=byId('duration'),profile=byId('profile');
 if(duration){duration.value='80';duration.disabled=true;}
 if(profile){profile.value='V4_ARCHIVAL_80S';profile.disabled=true;}
 const label=document.querySelector('label[for="duration"]');
 if(label)label.textContent='원본 Scene 길이 · 출력은 연속 5초 Preview';
 const start=byId('start');if(start)start.textContent='5초 Preview 제작';
 const form=byId('production-form');
 if(form){const note=document.createElement('p');note.className='hint';
  note.textContent='OVERNIGHT_SAFE_V3 · 원본 80초 시간축에서 150프레임만 제작합니다. 80초 전체 제작은 차단됩니다.';form.prepend(note);}
 const revision=byId('revision-form');if(revision)revision.hidden=true;
})();
'''
                        return self._send(200,source.encode(),'text/javascript; charset=utf-8')
                return super()._dispatch()
        return Handler

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--state-root',required=True,type=Path)
    parser.add_argument('--owner-file',required=True,type=Path);parser.add_argument('--export-root',type=Path,default=Path('/world-storage'))
    parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args(argv);verify_extension()
    prior.proxy.load_file('_overnight_proxy_manifest',prior.PROXY/'manifest.py').verify_sources()
    app=Application(args.state_root,args.owner_file,args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'),args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server=prior.proxy.original.StudioHTTPServer((args.host,args.port),app.handler())
    print(json.dumps({'stage':'STUDIO_OVERNIGHT_PREVIEW_STARTED','full80Allowed':False,
        'renderAllowed':False,'gpuRenderingVerified':False}),flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
