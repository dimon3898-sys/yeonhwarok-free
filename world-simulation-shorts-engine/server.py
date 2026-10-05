#!/usr/bin/env python3
"""Local/LAN HTTP app; no paid API, CDN, proxy bypass, or global state dependence."""
from __future__ import annotations
import argparse,hashlib,json,mimetypes,os,re,threading,time,traceback,urllib.parse,uuid
from http import HTTPStatus
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from engine.storage import ProjectStore,EngineError,atomic_json,read_json,now

APP=Path(__file__).resolve().parent
V3=APP.parent/'cinematic-world-map'

class Application:
    def __init__(self,projects,base_url):
        self.store=ProjectStore(projects);self.store.recover();self.base_url=base_url;self.jobs={};self.lock=threading.RLock();self.render_lock=threading.Lock()
    def outputs(self,pid,version):
        v=self.store.version_path(pid,version);items=[]
        candidates=[v/'scene_plan.json',v/'scene_plan_readable.md',v/'script.txt',v/'assets'/'source_report.md']
        result_path=v/'renders'/'project_result.json'
        if result_path.is_file():
            result=read_json(result_path)
            if result.get('qc',{}).get('passed'):
                candidates=[Path(p) for p in result.get('outputs',{}).values() if isinstance(p,str)]+candidates
                candidates.extend(Path(s['movie']) for s in result.get('scenes',[]) if s.get('complete'))
        seen=set()
        for p in candidates:
            p=p.resolve()
            if p.is_file() and p.is_relative_to(v) and p not in seen:
                seen.add(p)
                rel=p.relative_to(v).as_posix();items.append({'name':p.name,'path':rel,'bytes':p.stat().st_size,'url':f'/download/{pid}/{version}/{rel}','media_url':f'/media/{pid}/{version}/{rel}'})
        return items
    def status(self,pid,version=None):
        state=self.store.status(pid,version);state['outputs']=self.outputs(pid,state['version']);return state
    def start_render(self,pid,version):
        plan=self.store.require_approved(pid,version)
        from engine.schema import validate_plan
        gate=validate_plan(plan)
        if not gate['passed']:raise EngineError('PLAN_GATE_FAILED','검수 실패로 렌더링을 중단합니다.',gate)
        with self.lock:
            active=next((j for j in self.jobs.values() if j['project_id']==pid and j['version']==version and j['status'] in {'queued','rendering'}),None)
            if active:return active
            state=self.status(pid,version)
            if state['status']=='complete':return {'job_id':state.get('job_id'),'status':'complete','outputs':state['outputs']}
            jid='job_'+uuid.uuid4().hex[:12];job={'job_id':jid,'project_id':pid,'version':version,'status':'queued','started_at':now()};self.jobs[jid]=job
            self.store.set_status(pid,version,status='queued',job_id=jid,progress={'stage':'렌더 대기','completed':0,'total':len(plan['scenes'])})
            threading.Thread(target=self._render,args=(job,plan),daemon=True,name=jid).start();return job.copy()
    def _render(self,job,plan):
        pid,version=job['project_id'],job['version'];v=self.store.version_path(pid,version)
        def progress(event):
            if isinstance(event,str):event={'stage':event}
            event=dict(event);stage=event.get('stage','');total=len(plan['scenes'])
            names={'asset_resolution':'GIS·자산 출처 검수','narration_preflight':'나레이션 길이·사운드 타이밍 검수','scene_start':'장면 준비','scene_render':'장면 렌더링','scene_complete':'장면 저장 완료','scene_cache':'검증된 장면 재사용','scene_assembly':'장면 결합','audio':'오디오 합성','audio_mix':'오디오 합성','subtitle':'자막 합성','automatic_qc':'전체 프레임·사운드 자동 검수','complete':'최종 MP4 준비 완료'}
            index=event.get('scene_index')
            if index is None and event.get('scene_id'):
                index=next((i+1 for i,s in enumerate(plan['scenes']) if s['scene_id']==event['scene_id']),None)
            label=names.get(stage,stage)
            if index is not None:
                event['scene_index']=index;event['scene_total']=total;label=f"Scene {index}/{total} · {label}"
            event['label']=label
            if event.get('total_frames'):
                frames=int(event.get('completed_frames',0));limit=int(event['total_frames']);fraction=frames/max(1,limit)
                event['percent']=round(90*((index or 1)-1+fraction)/total,1)
                event['detail']=f"{frames}/{limit} 프레임 저장 · 완료 프레임은 체크포인트에 기록됩니다."
                if frames>=15 and event.get('elapsed_seconds'):
                    seconds=float(event['elapsed_seconds'])*(limit-frames)/frames
                    event['detail']+=f" 현재 속도 기준 이 장면 약 {round(seconds/60)}분 남음"
                    event['estimated_scene_remaining_seconds']=round(seconds)
            elif stage in {'scene_cache','scene_complete','scene_start'}:
                done=event.get('completed',index or 0)
                event['percent']=round(90*float(done)/total,1)
            elif stage in {'scene_assembly','audio','audio_mix','subtitle'}:event['percent']=92
            elif stage=='automatic_qc':event['percent']=97
            self.store.set_status(pid,version,status='rendering',progress=event)
        with self.render_lock:
            job['status']='rendering';progress({'stage':'GIS·자산 검수','completed':0,'total':len(plan['scenes'])})
            try:
                from engine.rendering import render_project
                result=render_project(v,plan,self.base_url,progress)
                job['status']='complete';job['ended_at']=now()
                self.store.set_status(pid,version,status='complete',progress={'stage':'최종 MP4 준비 완료','completed':len(plan['scenes']),'total':len(plan['scenes'])},result=result,error=None)
            except Exception as exc:
                code=getattr(exc,'code','RENDER_FAILED');job['status']='failed';job['ended_at']=now()
                detail={'code':code,'message':str(exc),'traceback':traceback.format_exc()}
                atomic_json(v/'qc'/('failure_'+job['job_id']+'.json'),detail,True)
                self.store.set_status(pid,version,status='failed',error={'code':code,'message':str(exc)},progress={'stage':'실패: 완료 Scene을 보존했습니다. 원인 수정 후 재개할 수 있습니다.'})

class Handler(BaseHTTPRequestHandler):
    server_version='WorldSimulation/1.0'
    def log_message(self,format,*args):
        if self.path.startswith('/api/') and ('status' in self.path):return
        super().log_message(format,*args)
    @property
    def app(self):return self.server.application
    def json(self,value,status=200):
        b=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
    def body(self):
        if int(self.headers.get('Content-Length',0))>2_000_000:raise EngineError('REQUEST_TOO_LARGE','요청이 너무 큽니다.',status=413)
        try:return json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        except (ValueError,UnicodeError):raise EngineError('INVALID_JSON','올바른 요청 형식이 아닙니다.')
    def error(self,exc):
        if isinstance(exc,EngineError):return self.json({'error':exc.as_dict()},exc.status)
        if hasattr(exc,'as_dict'):
            record=exc.as_dict()
            if 'details' not in record:record['details']={k:v for k,v in record.items() if k not in {'code','message'}}
            return self.json({'error':record},400)
        code=getattr(exc,'code','VALIDATION_ERROR' if isinstance(exc,(ValueError,KeyError)) else 'INTERNAL_ERROR')
        details=getattr(exc,'details',None)
        self.json({'error':{'code':code,'message':str(exc),'details':details}},400 if code!='INTERNAL_ERROR' else 500)
    def dispatch(self,method):
        try:
            path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path);q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            parts=path.strip('/').split('/');store=self.app.store
            if method in {'GET','HEAD'} and path=='/favicon.ico':self.send_response(204);self.end_headers();return
            if method=='GET' and path=='/api/health':return self.json({'ok':True,'name':'World Simulation Shorts Engine','renderer':'MASTER_V3','render_backend':'CPU_LOCAL','public_url_configured':bool(os.environ.get('WORLD_ENGINE_PUBLIC_URL'))})
            if method=='POST' and path=='/api/assets':return self.upload_asset(q)
            if path=='/api/projects':
                if method=='GET':return self.json({'projects':store.list()})
                if method=='POST':
                    from engine.planner import generate_plan
                    req=self.body();plan=generate_plan(req);return self.json(store.create(req,plan),201)
            if len(parts)>=3 and parts[:2]==['api','projects']:
                pid=parts[2]
                if len(parts)==3 and method=='GET':return self.json(store.get(pid,q.get('version',[None])[0]))
                if len(parts)==4 and parts[3]=='status' and method=='GET':return self.json(self.app.status(pid,q.get('version',[None])[0]))
                if len(parts)==4 and parts[3]=='versions' and method=='GET':
                    meta=store.get(pid)['project'];return self.json({'versions':[{'version':v,**self.app.status(pid,v)} for v in reversed(meta['versions'])]})
                if len(parts)==6 and parts[3]=='versions' and parts[5]=='plan' and method=='GET':return self.json(store.get(pid,parts[4])['plan'])
                if method=='POST' and len(parts)==4:
                    data=self.body();version=data.get('version') or store.get(pid)['version']
                    if parts[3]=='approve':store.approve(pid,version,data.get('plan_hash'));return self.json(store.get(pid,version))
                    if parts[3]=='render':return self.json(self.app.start_render(pid,version),202)
                    if parts[3]=='revise':
                        from engine.revisions import preview_revision
                        return self.json(preview_revision(store,pid,version,data.get('request','')))
                    if parts[3]=='clip':
                        from engine.revisions import preview_clip_revision
                        return self.json(preview_clip_revision(store,pid,version,data.get('scene_id'),data.get('asset_id'),APP/'library'/'uploads'))
                if method=='POST' and len(parts)==6 and parts[3]=='revisions' and parts[5]=='approve':
                    from engine.revisions import approve_revision
                    return self.json(approve_revision(store,pid,parts[4]))
            if method in {'GET','HEAD'}:
                if parts[0] in {'download','media'} and len(parts)>=4:
                    v=store.version_path(parts[1],parts[2]);rel='/'.join(parts[3:]);p=(v/rel).resolve()
                    if not p.is_relative_to(v) or p.suffix.lower() not in {'.mp4','.png','.jpg','.jpeg','.md','.json','.txt','.wav','.mp3','.ass','.srt','.zip'}:raise EngineError('INVALID_FILE','파일 경로가 허용되지 않습니다.',status=404)
                    return self.file(p,parts[0]=='download',method=='HEAD')
                if path in {'/','/index.html'}:return self.file(APP/'web'/'index.html',head=method=='HEAD')
                if path=='/render_transition.html':return self.file(APP/'web'/'render_transition.html',head=method=='HEAD')
                if path=='/render_flat_polish.html':return self.file(APP/'web'/'render_flat_polish.html',head=method=='HEAD')
                if path=='/render_flat_separation_polish.html':return self.file(APP/'web'/'render_flat_separation_polish.html',head=method=='HEAD')
                if path=='/render_earth_polish.html':return self.file(APP/'web'/'render_earth_polish.html',head=method=='HEAD')
                if path=='/render_flat.html':return self.file(APP/'web'/'render_flat.html',head=method=='HEAD')
                if path=='/render.html':return self.file(APP/'web'/'render.html',head=method=='HEAD')
                if parts[0]=='static':return self.scoped(APP/'web','/'.join(parts[1:]),method)
                if parts[0]=='vendor' and len(parts)>1 and parts[1]=='three':return self.scoped(V3/'node_modules'/'three','/'.join(parts[2:]),method)
                if parts[0]=='v3-src':return self.scoped(V3/'src','/'.join(parts[1:]),method)
                if path=='/bridge/renderer_v3.js':
                    source=(V3/'src'/'renderer_v3.js').read_text().split('\nconst app=new Renderer();')[0]
                    source=re.sub(r"from './([^']+)'",r"from '/v3-src/\1'",source)
                    b=source.encode();self.send_response(200);self.send_header('Content-Type','text/javascript; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
                if parts[:2]==['v3','assets']:return self.scoped(V3/'assets','/'.join(parts[2:]),method)
            raise EngineError('NOT_FOUND','요청을 찾을 수 없습니다.',status=404)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as exc:self.error(exc)
    def upload_asset(self,q):
        kind=q.get('kind',[''])[0];name=Path(q.get('filename',[''])[0]).name;license_name=q.get('license',[''])[0]
        allowed={'narration':{'.wav','.mp3'},'clip':{'.mp4'}}
        if kind not in allowed or Path(name).suffix.lower() not in allowed[kind]:raise EngineError('INVALID_ASSET','WAV/MP3 나레이션 또는 MP4 영상만 사용할 수 있습니다.')
        if license_name!='user_owned':raise EngineError('ASSET_RIGHTS_REQUIRED','사용 권한을 확인한 파일만 업로드할 수 있습니다.')
        size=int(self.headers.get('Content-Length',0))
        if not 0<size<=256*1024*1024:raise EngineError('ASSET_TOO_LARGE','파일은 256MiB 이하여야 합니다.',status=413)
        aid='asset_'+uuid.uuid4().hex[:12];folder=APP/'library'/'uploads'/aid;folder.mkdir(parents=True)
        dest=folder/('source'+Path(name).suffix.lower());sha=hashlib.sha256()
        with dest.open('xb') as f:
            left=size
            while left:
                chunk=self.rfile.read(min(left,65536))
                if not chunk:raise EngineError('INCOMPLETE_UPLOAD','파일 업로드가 완료되지 않았습니다.')
                f.write(chunk);sha.update(chunk);left-=len(chunk)
        import subprocess
        probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(dest)],capture_output=True,text=True)
        if probe.returncode:raise EngineError('INVALID_MEDIA','미디어 파일을 읽을 수 없습니다.')
        media=json.loads(probe.stdout)
        expected='audio' if kind=='narration' else 'video'
        if not any(s['codec_type']==expected for s in media['streams']):raise EngineError('INVALID_MEDIA','파일에 필요한 미디어 스트림이 없습니다.')
        metadata={'asset_id':aid,'source_id':aid,'kind':kind,'original_name':name,'path':str(dest),'sha256':sha.hexdigest(),'bytes':size,'license':'USER_SUPPLIED_RIGHTS','user_owned':True,'rights_declared':True,'author':'User-provided','uploaded_at':now(),'probe':media}
        atomic_json(folder/'source.json',metadata,True);return self.json(metadata,201)
    def scoped(self,root,rel,method):
        root=root.resolve();p=(root/rel).resolve()
        if not p.is_relative_to(root) or any(x.startswith('.') for x in Path(rel).parts):raise EngineError('INVALID_FILE','허용되지 않는 경로입니다.',status=404)
        return self.file(p,head=method=='HEAD')
    def file(self,p,attachment=False,head=False):
        if not p.is_file():raise EngineError('NOT_FOUND','파일을 찾을 수 없습니다.',status=404)
        total=p.stat().st_size;start,end=0,total-1;range_header=self.headers.get('Range');code=200
        if range_header:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not m:raise EngineError('INVALID_RANGE','지원하지 않는 범위입니다.',status=416)
            a,b=m.groups()
            if not a:start=max(0,total-int(b))
            else:start=int(a);end=min(end,int(b)) if b else end
            if start> end or start>=total:raise EngineError('INVALID_RANGE','범위가 파일 크기를 초과합니다.',status=416)
            code=206
        mime=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
        if p.suffix in {'.js','.mjs'}:mime='text/javascript'
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('X-Content-Type-Options','nosniff')
        if code==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
        if attachment:self.send_header('Content-Disposition',f"attachment; filename*=UTF-8''{urllib.parse.quote(p.name)}")
        self.end_headers()
        if head:return
        with p.open('rb') as f:
            f.seek(start);left=end-start+1
            while left:
                chunk=f.read(min(left,65536))
                if not chunk:break
                self.wfile.write(chunk);left-=len(chunk)
    def do_GET(self):self.dispatch('GET')
    def do_HEAD(self):self.dispatch('HEAD')
    def do_POST(self):
        origin=self.headers.get('Origin')
        if origin and urllib.parse.urlsplit(origin).netloc!=self.headers.get('Host'):
            return self.json({'error':{'code':'INVALID_ORIGIN','message':'다른 사이트의 요청은 허용하지 않습니다.'}},403)
        self.dispatch('POST')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8090);parser.add_argument('--projects',default=str(APP/'projects'));args=parser.parse_args()
    address='127.0.0.1' if args.host in {'0.0.0.0','::'} else args.host
    server=ThreadingHTTPServer((args.host,args.port),Handler);server.application=Application(args.projects,f'http://{address}:{args.port}')
    print(f'World Engine ready at http://{address}:{args.port} (bind={args.host}; projects={args.projects})',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.shutdown()
