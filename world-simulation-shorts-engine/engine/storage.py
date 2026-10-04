"""Durable, immutable plan versions and mutable job checkpoints, scoped to this app."""
from __future__ import annotations
import hashlib,json,os,re,threading,uuid
from datetime import datetime,timezone
from pathlib import Path

class EngineError(Exception):
    def __init__(self,code,message,details=None,status=400):
        super().__init__(message);self.code=code;self.message=message;self.details=details;self.status=status
    def as_dict(self):return {'code':self.code,'message':self.message,'details':self.details}

def now():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def plan_hash(plan):
    content={k:v for k,v in plan.items() if k not in {'plan_hash','gate','retention_gate','approval','validation','created_at'}}
    return hashlib.sha256(canonical(content)).hexdigest()
def atomic_json(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if exclusive:
        with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        return
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def readable(plan):
    story=plan.get('story',plan.get('story_plan',{}));req=plan.get('request',{})
    lines=[f"# {plan.get('title',req.get('topic','Scene Plan'))}",f"\n총 길이: {plan.get('duration',req.get('duration'))}초 · 품질: {req.get('quality','HIGH')}",f"\n훅: {story.get('hook',plan.get('hook',''))}",'\n| 장면 | 시간 | 장소 | 역할/주요 사건 | 카메라 | 조명 |','|---|---|---|---|---|---|']
    for s in plan['scenes']:
        events=', '.join(x.get('kind','') for x in s['visual_events'])
        lines.append(f"| {s['scene_id']} | {s['start_time']:g}–{s['start_time']+s['duration']:g}s | {s['location']} | {s.get('role',s['scene_type'])}: {events} | {s['camera_preset']} | {s['lighting_preset']} |")
    lines+=['\n## 사실과 가정']
    for claim in story.get('claims',[]):lines.append(f"- **{claim.get('status',claim.get('fact_status',''))}**: {claim.get('text','')}")
    lines+=['\n## 검수',json.dumps(plan.get('gate',{}),ensure_ascii=False,indent=2)]
    return '\n'.join(lines)+'\n'

class ProjectStore:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
    def path(self,pid):
        if not re.fullmatch(r'project_[a-z0-9_]{6,64}',pid):raise EngineError('INVALID_PROJECT','잘못된 프로젝트 ID입니다.')
        p=self.root/pid
        if not p.is_dir():raise EngineError('NOT_FOUND','프로젝트를 찾을 수 없습니다.',status=404)
        return p
    def version_path(self,pid,version=None):
        p=self.path(pid);version=version or read_json(p/'project.json')['current_version']
        if not re.fullmatch(r'v\d{3,}',version):raise EngineError('INVALID_VERSION','잘못된 버전입니다.')
        v=p/'versions'/version
        if not v.is_dir():raise EngineError('NOT_FOUND','버전을 찾을 수 없습니다.',status=404)
        return v
    def create(self,request,plan):
        with self.lock:
            pid='project_'+uuid.uuid4().hex[:12];p=self.root/pid;p.mkdir()
            for name in ['prompt','research','story','scene_json','assets','audio','renders','previews','qc','final','versions','revisions']: (p/name).mkdir()
            atomic_json(p/'prompt'/'request_v001.json',request,True)
            meta={'id':pid,'title':request['topic'],'created_at':now(),'updated_at':now(),'current_version':'v001','status':'planned','versions':['v001']}
            atomic_json(p/'project.json',meta,True);self.write_version(pid,'v001',plan);return self.get(pid)
    def write_version(self,pid,version,plan):
        for scene in plan['scenes']:scene.setdefault('render_time_offset',scene['start_time'])
        if 'render_context' not in plan:
            hero=next((s for s in plan['scenes'] if s['lighting_preset']=='HERO'),plan['scenes'][0])
            plan['render_context']={'lighting_anchor':plan['scenes'][0]['coordinates'],'hero_anchor':hero['coordinates']}
        plan['project_id']=pid;plan['version']=version
        # Persist the certificate for the normalized rendering inputs. A blocked
        # plan may be reviewed/revised but cannot be approved or rendered.
        from .schema import validate_plan
        plan['gate']=validate_plan(plan)
        if plan['gate']['passed']:
            from .estimation import estimate_cpu_render
            plan.setdefault('metadata',{})['estimates']=estimate_cpu_render(plan,self.root)
        plan['plan_hash']=plan_hash(plan)
        v=self.path(pid)/'versions'/version;v.mkdir()
        for name in ['story','scene_json','assets','audio','renders','previews','qc','final']:(v/name).mkdir()
        atomic_json(v/'scene_plan.json',plan,True)
        (v/'scene_plan_readable.md').write_text(readable(plan),encoding='utf-8')
        (v/'script.txt').write_text('\n\n'.join(s['narration'] for s in plan['scenes'])+'\n',encoding='utf-8')
        atomic_json(v/'story'/'story_plan.json',plan.get('story',{}),True)
        for s in plan['scenes']:atomic_json(v/'scene_json'/(s['scene_id']+'.json'),s,True)
        atomic_json(v/'status.json',{'status':'planned','progress':{'stage':'기획 완료','completed':0,'total':len(plan['scenes'])},'updated_at':now(),'outputs':[]},True)
    def get(self,pid,version=None):
        p=self.path(pid);meta=read_json(p/'project.json');version=version or meta['current_version'];v=self.version_path(pid,version)
        return {'project':meta,'plan':read_json(v/'scene_plan.json'),'version':version}
    def list(self):
        records=[]
        for p in self.root.glob('project_*/project.json'):
            try:records.append(read_json(p))
            except (OSError,ValueError):continue
        return sorted(records,key=lambda x:x['created_at'],reverse=True)
    def set_status(self,pid,version,**kwargs):
        with self.lock:
            v=self.version_path(pid,version);state=read_json(v/'status.json');state.update(kwargs);state['updated_at']=now();atomic_json(v/'status.json',state)
            p=self.path(pid);meta=read_json(p/'project.json')
            if version==meta['current_version']:meta.update(status=state['status'],updated_at=now());atomic_json(p/'project.json',meta)
            return state
    def status(self,pid,version=None):
        data=self.get(pid,version);v=self.version_path(pid,data['version']);state=read_json(v/'status.json');state['version']=data['version'];return state
    def approve(self,pid,version,digest):
        with self.lock:
            data=self.get(pid,version);p=data['plan']
            from .schema import validate_plan
            gate=validate_plan(p)
            if not gate.get('passed'):raise EngineError('PLAN_GATE_FAILED','계획 검수에서 실패했습니다.',gate)
            if not digest or digest!=p['plan_hash'] or plan_hash(p)!=digest:raise EngineError('PLAN_CHANGED','현재 계획의 해시와 승인이 일치하지 않습니다.')
            v=self.version_path(pid,version);approval=v/'approval.json'
            if not approval.exists():atomic_json(approval,{'plan_hash':digest,'approved_at':now(),'user_approval':True},True)
            return self.set_status(pid,version,status='approved')
    def require_approved(self,pid,version):
        data=self.get(pid,version);v=self.version_path(pid,version)
        if not (v/'approval.json').exists():raise EngineError('APPROVAL_REQUIRED','Scene Plan 승인이 필요합니다.',status=409)
        approval=read_json(v/'approval.json')
        if approval['plan_hash']!=plan_hash(data['plan']):raise EngineError('PLAN_CHANGED','승인 후 계획이 변경되었습니다.',status=409)
        return data['plan']
    def add_version(self,pid,plan):
        with self.lock:
            p=self.path(pid);meta=read_json(p/'project.json');version=f"v{max(int(x[1:]) for x in meta['versions'])+1:03}"
            self.write_version(pid,version,plan);meta['versions'].append(version);meta['current_version']=version;meta['updated_at']=now();meta['status']='planned';atomic_json(p/'project.json',meta);return self.get(pid,version)
    def recover(self):
        for meta in self.list():
            for version in meta['versions']:
                state=self.status(meta['id'],version)
                if state['status'] in {'rendering','queued'}:self.set_status(meta['id'],version,status='interrupted',progress={'stage':'작업 재개 가능: 완료 Scene 유지'},error=None)
