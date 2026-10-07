"""Per-job, owner-only diagnostic evidence. Never copy arbitrary files or env dumps."""
from __future__ import annotations
import contextlib,hashlib,json,math,os,re,resource,stat,subprocess,threading,time,zipfile,uuid
from pathlib import Path
from .storage import canonical

SENSITIVE=re.compile(r'owner.?code|cookie|authorization|token|session|secret|password',re.I)
JOB=re.compile(r'job_[a-f0-9]{12}')
SCENE=re.compile(r'S\d{3,5}')
EXPORT_NAMES={'manifest.json','job.json','scene-plan.json','frame-audit.json','failed-invariant.json','renderer-diagnostics.json','gpu-diagnostics.json','stdout.txt','stderr.txt','ffmpeg-diagnostics.json','audio-diagnostics.json','checkpoint.json','qc.json','timings.json','preflight.json','packaging-error.json','python-exception.json','subprocess-diagnostics.json','scene-input-capture.json'}

class Redactor:
    def __init__(self):
        self.values=[v for k,v in os.environ.items() if SENSITIVE.search(k) and len(v)>=4]
    def text(self,value):
        value=str(value)
        for secret in self.values:value=value.replace(secret,'[REDACTED]')
        value=re.sub(r'https?://[^\s\"\'<>]+','[URL omitted]',value)
        value=re.sub(r'(?<![\w])/(?:[\w.\-]+/)+[\w.\-]*','[path omitted]',value)
        # Preserve structured error names, omit any text containing credential keys.
        if SENSITIVE.search(value):return '[sensitive text omitted]'
        return value
    def clean(self,value):
        if isinstance(value,dict):return {str(k):self.clean(v) for k,v in value.items() if not SENSITIVE.search(str(k))}
        if isinstance(value,(list,tuple)):return [self.clean(v) for v in value]
        if isinstance(value,float) and not math.isfinite(value):return {'non_finite':str(value)}
        if isinstance(value,str):return self.text(value)
        if value is None or isinstance(value,(bool,int,float)):return value
        return self.text(type(value).__name__)

def durable_json(path,value):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.writing')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        data=json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode()
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
        dfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if temp.exists():temp.unlink()

class DiagnosticBundle:
    def __init__(self,project_dir,job_id,plan=None,*,state_root=None):
        if not JOB.fullmatch(job_id):raise ValueError('INVALID_DIAGNOSTIC_JOB')
        self.project=Path(project_dir).resolve();self.job_id=job_id
        self.root=self.project/'diagnostics'/job_id
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.root.is_symlink() or not self.root.resolve().is_relative_to(self.project):raise ValueError('INVALID_DIAGNOSTIC_PATH')
        self.redactor=Redactor();self.lock=threading.RLock();self.started=time.monotonic();self.samples=[];self.stop=threading.Event();self.scene_times={};self.process_records=[]
        self.state_root=Path(state_root) if state_root else None
        if self.state_root:
            owner_file=self.state_root/'owner-code.txt'
            if owner_file.is_file() and not owner_file.is_symlink():
                info=owner_file.stat()
                if info.st_uid==os.getuid() and info.st_mode&0o077==0 and info.st_size<=4096:
                    value=owner_file.read_text().strip()
                    if len(value)>=4:self.redactor.values.append(value)
        previous=self._existing(self.root/'bundle-state.json')
        if previous:
            self.started=previous['monotonic_start']
            self.scene_times=(self._existing(self.root/'timings-live.json') or {}).get('scenes',{})
            self.samples=self._existing(self.root/'gpu-samples.json') or []
        else:self.write('bundle-state.json',dict(monotonic_start=self.started))
        self.reserve=self.root/'zip-reserve.bin'
        if not self.reserve.exists():
            with self.reserve.open('xb') as stream:stream.write(b'\0'*(4*1024**2));stream.flush();os.fsync(stream.fileno())
        if plan is not None:
            self.write('scene-plan.json',plan)
            captures=[]
            for scene in plan.get('scenes',[]):
                sid=scene.get('scene_id','')
                if not SCENE.fullmatch(sid):raise ValueError('INVALID_DIAGNOSTIC_SCENE')
                persisted=self.project/'scene_json'/(sid+'.json')
                actual=self._existing(persisted)
                self.write(sid+'.json',actual if actual is not None else scene)
                captures.append(dict(scene_id=sid,source='actual_persisted_renderer_input' if actual is not None else 'approved_plan_without_persisted_input',matches_approved_plan=actual==scene if actual is not None else None,browser_started=False))
            self.write('scene-input-capture.json',captures)
            self.write('job.json',dict(job_id=job_id,project_id=plan.get('project_id'),version=plan.get('version'),status='INITIALIZING',actual_approved_plan_sha256=hashlib.sha256(canonical(plan)).hexdigest(),scene_input_source='approved immutable plan; browser input capture updates each started scene'))
    def write(self,name,value):
        if not re.fullmatch(r'[\w.-]+\.json',name):raise ValueError('INVALID_DIAGNOSTIC_FILE')
        with self.lock:durable_json(self.root/name,self.redactor.clean(value))
    def log(self,channel,line):
        if channel not in ('stdout','stderr'):raise ValueError('INVALID_LOG_CHANNEL')
        text=self.redactor.text(line.rstrip())+'\n';path=self.root/(channel+'.txt')
        with self.lock:
            fd=os.open(path,os.O_APPEND|os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
            try:
                # Bounded logs; audits live separately without this log cap.
                if os.fstat(fd).st_size<16*1024**2:os.write(fd,text.encode()[:65536]);os.fsync(fd)
            finally:os.close(fd)
    def begin_scene(self,command):
        sid=None
        if '--scene-json' in command:
            p=Path(command[command.index('--scene-json')+1]);scene=json.loads(p.read_text());sid=scene['scene_id']
            if not SCENE.fullmatch(sid):raise ValueError('INVALID_DIAGNOSTIC_SCENE')
            self.write(sid+'.json',scene)
            captures=self._existing(self.root/'scene-input-capture.json') or []
            for capture in captures:
                if capture['scene_id']==sid:capture.update(source='actual_subprocess_scene_input',subprocess_started=True)
            self.write('scene-input-capture.json',captures)
        self.scene_times[sid]=dict(scene_id=sid,start_at=time.time(),monotonic_start=time.monotonic(),frames=0)
        self.write('timings-live.json',{'scenes':self.scene_times})
        self.write('job.json',dict(job_id=self.job_id,status='SCENE_START',scene_id=sid))
        return sid
    def event(self,event):
        sid=event.get('scene_id');row=self.scene_times.get(sid)
        if row:
            row['frames']=max(row.get('frames',0),int(event.get('completed_frames',0)))
            self.write('timings-live.json',{'scenes':self.scene_times})
        self.write('job.json',dict(job_id=self.job_id,status='RUNNING',last_progress=event))
    def end_scene(self,sid,*,code,seconds):
        row=self.scene_times.setdefault(sid,dict(scene_id=sid));row.update(end_at=time.time(),duration_seconds=seconds,return_code=code,gpu_result='COMPLETED' if code==0 else 'FAILED')
        self.write('timings-live.json',{'scenes':self.scene_times})
    def start_samples(self):
        def sample():
            while not self.stop.is_set():
                try:
                    p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
                    if p.returncode==0:
                        for row in p.stdout.splitlines():
                            name,memory,util=[v.strip() for v in row.split(',')];self.samples.append(dict(model=name,memory_used_mib=float(memory),utilization_percent=float(util),elapsed_seconds=time.monotonic()-self.started))
                except (OSError,ValueError,subprocess.SubprocessError):pass
                if self.samples:
                    try:self.write('gpu-samples.json',self.samples)
                    except OSError:pass
                self.stop.wait(1)
        self.sampler=threading.Thread(target=sample,daemon=True);self.sampler.start()
    def stop_samples(self):
        self.stop.set()
        if hasattr(self,'sampler'):self.sampler.join(4)
    @contextlib.contextmanager
    def record_processes(self):
        # One isolated worker process owns this scoped observer. Never change a
        # subprocess command, input, environment, output, exception or exit code.
        original=subprocess.run
        def observed(command,*args,**kwargs):
            executable=Path(command[0]).name if isinstance(command,(list,tuple)) and command else None
            if executable not in {'ffmpeg','ffprobe','espeak-ng'}:return original(command,*args,**kwargs)
            start=time.monotonic();completed=None;failure=None
            try:
                completed=original(command,*args,**kwargs);return completed
            except BaseException as error:
                failure=error;raise
            finally:
                def text(value):return value.decode(errors='replace') if isinstance(value,bytes) else str(value or '')
                value=completed if completed is not None else failure
                row=dict(category=executable,return_code=getattr(value,'returncode',None),duration_seconds=time.monotonic()-start,stdout_tail=text(getattr(value,'stdout',None))[-12000:],stderr_tail=text(getattr(value,'stderr',None))[-12000:],exception_type=type(failure).__name__ if failure else None)
                self.process_records.append(self.redactor.clean(row))
                try:self.write('subprocess-diagnostics.json',self.process_records)
                except OSError:pass # Keep the original pipeline outcome authoritative.
        subprocess.run=observed
        try:yield
        finally:subprocess.run=original
    def _existing(self,path):
        p=Path(path)
        if p.is_file() and not p.is_symlink():
            try:return json.loads(p.read_text())
            except (OSError,ValueError):return None
    def finish(self,*,status,error=None,result=None):
        self.stop_samples()
        if self.reserve.exists():self.reserve.unlink() # Keep space available for error-path packaging.
        error=self.redactor.clean(error or {});diag=error.get('subprocess',error.get('diagnostics',{}));root=diag.get('root_cause',{})
        native=[];secondary=[];renderer=[]
        # Only explicit journal names below the private job directory are read.
        for folder in sorted(self.root.glob('S*')):
            if not folder.is_dir() or folder.is_symlink() or not SCENE.fullmatch(folder.name):continue
            journal=folder/'frame-audit.jsonl'
            if journal.is_file() and not journal.is_symlink():
                for line in journal.read_text().splitlines():
                    try:native.append(self.redactor.clean(json.loads(line)))
                    except ValueError:secondary.append({'code':'TRUNCATED_AUDIT_JOURNAL','scene_id':folder.name})
            for name in ('renderer-diagnostics.json','failed-invariant.json','ffmpeg-diagnostics.json'):
                value=self._existing(folder/name)
                if value is not None:
                    renderer.append({'scene_id':folder.name,'type':name,'record':value})
                    if name=='failed-invariant.json' and not root:root=value
                    if name=='ffmpeg-diagnostics.json':secondary.extend(value.get('secondary_errors',[]))
            scene=self._existing(folder/'scene-input.json')
            if scene is not None:
                self.write(folder.name+'.json',scene)
                captures=self._existing(self.root/'scene-input-capture.json') or []
                for capture in captures:
                    if capture['scene_id']==folder.name:capture.update(source='actual_browser_final_scene_spec',browser_started=True)
                self.write('scene-input-capture.json',captures)
        recorded={r.get('scene_id') for r in native}
        saved=self._existing(self.project/'renders/scene_results.json') or {}
        for scene in saved.get('scenes',[]):
            sid=scene.get('scene_id')
            if sid in recorded or not SCENE.fullmatch(str(sid)):continue
            path=Path(scene.get('audit',''))
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(self.project):
                if hashlib.sha256(path.read_bytes()).hexdigest()!=scene.get('audit_sha256'):continue
                for index,row in enumerate(self._existing(path) or []):
                    native.append({**self.redactor.clean(row),'scene_id':sid,'frame_index':index,'source':'cached_native_audit','errors':{'not_available':'not recorded by original cached worker'}})
        self.write('frame-audit.json',native)
        failed=root.get('failed_invariants',[])
        self.write('failed-invariant.json',dict(PRIMARY_ERROR=root.get('code') or error.get('code') or None,FAILED_INVARIANT=failed,SECONDARY_ERROR=secondary,scene_id=error.get('scene_id') or root.get('scene_id'),frame_index=root.get('frame_index'),stage=error.get('failed_stage'),return_code=diag.get('return_code'),evidence=error,status=status))
        self.write('renderer-diagnostics.json',renderer)
        self.write('ffmpeg-diagnostics.json',dict(image2pipe=[r for r in renderer if r['type']=='ffmpeg-diagnostics.json'],processes=self._existing(self.root/'subprocess-diagnostics.json') or []))
        self.write('job.json',dict(job_id=self.job_id,status=status,error=error,total_seconds=time.monotonic()-self.started))
        for name,path in [('checkpoint.json',self.project/'renders/checkpoint.json'),('audio-diagnostics.json',self.project/'audio/audio_report.json'),('qc.json',self.project/'qc/qc_report.json')]:
            value=self._existing(path)
            if value is not None and not (self.root/name).exists():self.write(name,value)
        if result:
            self.write('qc.json',result.get('qc',{}))
            if not (self.root/'audio-diagnostics.json').exists():self.write('audio-diagnostics.json',dict(report=self._existing(self.project/'audio/audio_report.json'),metrics=result.get('metrics')))
        gpu={}
        if self.state_root:
            for path in (self.state_root/'gcube-runtime.json',self.state_root.parent/'runtime/gcube-runtime.json',self.state_root/'runtime/gcube-runtime.json',self.state_root.parent/'gcube-runtime.json'):
                value=self._existing(path)
                if value:
                    from deployment.gcube.boot_status import safe_gpu_diagnostics
                    actual=value.get('gpu',{});gpu=dict(verified=actual.get('gpu_rendering_verified'),profile=actual.get('gpu_profile'),diagnostics=safe_gpu_diagnostics(actual.get('diagnostics')));break
        self.write('gpu-diagnostics.json',dict(startup=gpu,samples=self.samples,model=self.samples[0]['model'] if self.samples else None,memory_peak_mib=max((s['memory_used_mib'] for s in self.samples),default=None),measurement_status='MEASURED' if self.samples else 'NOT_AVAILABLE'))
        usage=resource.getrusage(resource.RUSAGE_CHILDREN)
        timings=dict(total_seconds=time.monotonic()-self.started,scenes=[{k:v for k,v in row.items() if k!='monotonic_start'} for row in self.scene_times.values()],child_cpu_seconds=usage.ru_utime+usage.ru_stime,child_peak_rss_kib=usage.ru_maxrss,metrics=(result or {}).get('metrics'),measured=True)
        final=(result or {}).get('outputs',{}).get('final')
        if final and Path(final).is_file():
            from .rendering import probe_video
            timings.update(final_mp4_size=Path(final).stat().st_size,final_mp4_duration=float(probe_video(Path(final))['format']['duration']))
        self.write('timings.json',timings)
        return self.package()
    def package(self):
        destination=self.root/f'WORLD_ENGINE_GPU_DIAGNOSTIC_{self.job_id}.zip'
        if destination.exists():
            if destination.is_symlink() or not zipfile.is_zipfile(destination):raise ValueError('EXISTING_DIAGNOSTIC_CONFLICT')
            return destination
        files=[p for p in self.root.iterdir() if p.is_file() and not p.is_symlink() and p.name!='manifest.json' and (p.name in EXPORT_NAMES or SCENE.fullmatch(p.stem) and p.suffix=='.json')]
        payloads={}
        for p in sorted(files):
            text=p.read_text()
            value=json.dumps(self.redactor.clean(json.loads(text)),ensure_ascii=False,allow_nan=False) if p.suffix=='.json' else '\n'.join(self.redactor.text(line) for line in text.splitlines())
            payloads[p.name]=value.encode()
        for folder in sorted(self.root.glob('S*')):
            if not folder.is_dir() or folder.is_symlink() or not SCENE.fullmatch(folder.name):continue
            for source in ('frame-audit.jsonl','failed-invariant.json','preparation.json','frame-attempt.json','renderer-diagnostics.json','ffmpeg-diagnostics.json'):
                p=folder/source
                if not p.is_file() or p.is_symlink():continue
                raw=p.read_text()
                if source.endswith('.jsonl'):
                    records=[]
                    for index,line in enumerate(raw.splitlines()):
                        if not line:continue
                        try:value=self.redactor.clean(json.loads(line))
                        except ValueError:value={'code':'TRUNCATED_AUDIT_JOURNAL','line_index':index,'raw_omitted':True}
                        records.append(json.dumps(value,ensure_ascii=False,allow_nan=False))
                    payloads['native-journals/'+folder.name+'/'+source]='\n'.join(records).encode()
                else:
                    try:value=self.redactor.clean(json.loads(raw))
                    except ValueError:value={'code':'TRUNCATED_DIAGNOSTIC_RECORD','raw_omitted':True}
                    payloads['native-journals/'+folder.name+'/'+source]=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            p=folder/'scene-input.json'
            if p.is_file() and not p.is_symlink():payloads[folder.name+'.json']=json.dumps(self.redactor.clean(json.loads(p.read_text())),ensure_ascii=False,allow_nan=False).encode()
        self.write('manifest.json',dict(schema_version=1,job_id=self.job_id,created_at=time.time(),files=[dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in payloads.items()],security='Allowlisted job artifacts; credential keys/values, URL queries, env dumps excluded',gpu_evidence='Actual journals only; no synthetic GPU PASS',archive_contains_mp4=False))
        payloads['manifest.json']=(self.root/'manifest.json').read_bytes()
        destination=self.root/f'WORLD_ENGINE_GPU_DIAGNOSTIC_{self.job_id}.zip'
        if destination.exists():
            if destination.is_symlink() or not zipfile.is_zipfile(destination):raise ValueError('EXISTING_DIAGNOSTIC_CONFLICT')
            return destination
        temp=destination.with_suffix('.zip.writing')
        if temp.exists():temp.unlink()
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in payloads.items():archive.writestr(name,data)
        with temp.open('rb') as stream:os.fsync(stream.fileno())
        os.chmod(temp,0o600);os.replace(temp,destination)
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return destination

def diagnostic_outputs(project_dir,pid,version):
    root=Path(project_dir).resolve();rows=[]
    for path in sorted((root/'diagnostics').glob('job_*/WORLD_ENGINE_GPU_DIAGNOSTIC_job_*.zip')):
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not JOB.fullmatch(path.parent.name):continue
        if path.name!=f'WORLD_ENGINE_GPU_DIAGNOSTIC_{path.parent.name}.zip' or not zipfile.is_zipfile(path):continue
        relative=path.relative_to(root).as_posix()
        row=dict(name=path.name,path=relative,bytes=path.stat().st_size,url=f'/download/{pid}/{version}/{relative}',diagnostic=True)
        try:
            timings=json.loads((path.parent/'timings.json').read_text());gpu=json.loads((path.parent/'gpu-diagnostics.json').read_text())
            row['diagnostic_metrics']=dict(total_seconds=timings.get('total_seconds'),scenes=timings.get('scenes'),final_mp4_duration=timings.get('final_mp4_duration'),final_mp4_size=timings.get('final_mp4_size'),cpu_seconds=timings.get('child_cpu_seconds'),gpu_model=gpu.get('model'),gpu_memory_peak_mib=gpu.get('memory_peak_mib'))
        except (OSError,ValueError):pass
        rows.append(row)
    return rows


def recover_bundle(project_dir,job_id,state,error=None):
    root=Path(project_dir)/'diagnostics'/job_id
    destination=root/f'WORLD_ENGINE_GPU_DIAGNOSTIC_{job_id}.zip'
    if destination.is_file() and not destination.is_symlink() and zipfile.is_zipfile(destination):return destination
    if not root.is_dir():return None
    bundle=DiagnosticBundle(project_dir,job_id)
    try:return bundle.finish(status=state,error=error)
    except Exception as failure:
        if bundle.reserve.exists():bundle.reserve.unlink()
        bundle.write('packaging-error.json',{'code':'DIAGNOSTIC_PACKAGING_FAILED','error_type':type(failure).__name__})
        return bundle.package()
