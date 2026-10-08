#!/usr/bin/env python3
"""Authenticated mobile gateway and durable single worker. Approved core is unchanged."""
from __future__ import annotations

import argparse
from collections import deque
import fcntl
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
import uuid

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
from server import Application, Handler
from engine.storage import ProjectStore, EngineError, atomic_json, now, plan_hash, read_json
from engine.failures import failure_record, RenderProcessError, safe_tail
from deployment.security import (OwnerSessions, RateLimiter, RequestPolicy, SecurityError,
                                 content_length, ensure_access_file, owned_path, private_json)


def checked_state_root(value):
    p = Path(value).absolute()
    if p.is_symlink():
        raise SecurityError('UNSAFE_STATE_ROOT', '별도의 새 상태 폴더를 사용해 주세요.')
    p = p.resolve()
    protected = [APP_ROOT, APP_ROOT.parent / 'deliverables', APP_ROOT.parent / 'cinematic-world-map']
    protected += [APP_ROOT / n for n in ('projects', 'cache', 'web', 'engine', 'data', 'assets', 'library')]
    protected += list(APP_ROOT.glob('projects-*'))
    # APP itself is forbidden, but APP/deployment/runtime is an intentional writable mount.
    if p == APP_ROOT or any(p == x or p.is_relative_to(x) or x.is_relative_to(p)
                            for x in protected if x != APP_ROOT):
        raise SecurityError('UNSAFE_STATE_ROOT', '기존 프로젝트 밖의 새 상태 폴더를 사용해 주세요.')
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = p / 'mobile-state.json'
    if not marker.exists():
        if any((p / x).exists() for x in ('project.json', 'scene_plan.json', 'versions')):
            raise SecurityError('UNSAFE_STATE_ROOT', '기존 프로젝트를 상태 폴더로 사용할 수 없습니다.')
        private_json(marker, {'format': 'world-mobile-runtime-v1', 'created_at': now()})
    elif read_json(marker).get('format') != 'world-mobile-runtime-v1':
        raise SecurityError('UNSAFE_STATE_ROOT', '상태 폴더 형식을 확인해 주세요.')
    return p


class DurableJobs:
    """Two admitted tickets at most: one running, one queued; no old tree recovery."""
    def __init__(self, app, runner=None):
        self.app, self.root = app, app.state_root / 'jobs'
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.runner = runner or self.process_runner
        self.condition = threading.Condition(threading.RLock())
        self.pending, self.active = deque(), None
        self.tickets, self.cancellation = {}, {}
        self.stopping = False
        self.thread = None

    def _save(self, ticket):
        ticket['updated_at'] = now()
        private_json(self.root / (ticket['job_id'] + '.json'), ticket)

    def _plan(self, ticket):
        plan = self.app.store.require_approved(ticket['project_id'], ticket['version'])
        if plan_hash(plan) != ticket['plan_hash']:
            raise EngineError('PLAN_CHANGED', '승인된 계획과 작업이 일치하지 않습니다.', status=409)
        self.app.check_plan_budget(plan)
        return plan

    def start(self):
        with self.condition:
            if self.thread:
                return
            records = []
            for path in self.root.glob('job_*.json'):
                try:
                    records.append(read_json(path))
                except (OSError, ValueError):
                    continue  # Retain a corrupt receipt; never silently overwrite it.
            for ticket in sorted(records, key=lambda record: str(record.get('created_at', ''))):
                if not re.fullmatch(r'job_[a-f0-9]{12}', ticket.get('job_id', '')):
                    continue
                self.tickets[ticket['job_id']] = ticket
                if ticket.get('status') not in {'queued', 'rendering', 'interrupted'} or not ticket.get('resume_on_restart', False):
                    continue
                try:
                    self._plan(ticket)
                    if self.app.store.status(ticket['project_id'], ticket['version'])['status'] == 'complete':
                        ticket['status'] = 'complete'
                    elif len(self.pending) < 2:
                        ticket['status'] = 'queued'
                        ticket['internal_url'] = self.app.base_url
                        self.pending.append(ticket['job_id'])
                    else:
                        ticket['status'] = 'interrupted'
                        ticket['error_code'] = 'RESUME_CAPACITY'
                except Exception:
                    ticket['status'] = 'blocked'
                    ticket['error_code'] = 'APPROVAL_OR_PLAN_CHANGED'
                self._save(ticket)
            self.thread = threading.Thread(target=self._loop, name='mobile-owner-worker', daemon=True)
            self.thread.start()

    def submit(self, pid, version):
        plan = self.app.store.require_approved(pid, version)
        from engine.schema import validate_plan
        if not validate_plan(plan)['passed']:
            raise EngineError('PLAN_GATE_FAILED', '계획 검수를 통과해야 합니다.')
        self.app.check_plan_budget(plan)
        with self.condition:
            if self.stopping:
                raise EngineError('WORKER_STOPPING', '작업 종료 중입니다.', status=503)
            for ticket in self.tickets.values():
                if ticket['project_id'] == pid and ticket['version'] == version and ticket['status'] in {'queued', 'rendering'}:
                    return dict(ticket)
            if self.app.store.status(pid, version)['status'] == 'complete':
                return {'status': 'complete', 'outputs': self.app.outputs(pid, version)}
            if (int(self.active is not None) + len(self.pending)) >= 2:
                raise EngineError('JOB_QUEUE_FULL', '작업 1개와 대기 1개까지만 허용됩니다.', status=429)
            jid = 'job_' + uuid.uuid4().hex[:12]
            ticket = {'job_id': jid, 'project_id': pid, 'version': version,
                      'plan_hash': plan_hash(plan), 'status': 'queued', 'resume_on_restart': True,
                      'created_at': now(), 'internal_url': self.app.base_url,
                      'selected_scene_ids': list(plan.get('metadata', {}).get('rhythm_sample_render_authorization', {}).get('renderable_scene_ids', [s['scene_id'] for s in plan['scenes']]))}
            self.tickets[jid] = ticket
            self._save(ticket)
            self.pending.append(jid)
            self.app.store.set_status(pid, version, status='queued', job_id=jid, error=None,
                                      progress={'stage': '렌더 대기', 'completed': 0, 'total': len(plan['scenes'])})
            self.condition.notify_all()
            return dict(ticket)

    def _loop(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.pending or self.stopping)
                if self.stopping:
                    return
                jid = self.pending.popleft()
                ticket = self.tickets[jid]
                if ticket['status'] != 'queued':
                    continue
                self.active = jid
                cancel = threading.Event()
                self.cancellation[jid] = cancel
                ticket['status'] = 'rendering'
                self._save(ticket)
            try:
                plan = self._plan(ticket)
                self.app.store.set_status(ticket['project_id'], ticket['version'],
                                          status='rendering', job_id=jid, error=None)
                self.runner(ticket, plan, cancel)
                state = self.app.store.status(ticket['project_id'], ticket['version'])
                ticket['status'] = state['status'] if state['status'] in {'complete', 'failed'} else 'interrupted'
            except Exception as error:
                ticket['status'] = 'interrupted' if cancel.is_set() else 'failed'
                ticket['error_code'] = 'WORKER_INTERRUPTED' if cancel.is_set() else 'WORKER_FAILED'
                if not cancel.is_set():
                    current = self.app.store.status(ticket['project_id'], ticket['version'])
                    progress = current.get('progress', {})
                    evidence = failure_record(error, stage=progress.get('stage'), scene_id=progress.get('scene_id'))
                    evidence.update(created_at=now(), job_id=jid)
                    failure = self.root / (jid + '.failure.json')
                    if not failure.exists():
                        private_json(failure, evidence)
                    # A worker's specific failure must survive the outer exit-1 wrapper.
                    if current.get('status') != 'failed' or not current.get('error'):
                        public = {key: evidence[key] for key in ('code', 'message', 'failed_stage', 'scene_id')}
                        if 'subprocess' in evidence:
                            public['diagnostics'] = evidence['subprocess']
                        self.app.store.set_status(ticket['project_id'], ticket['version'], status='failed',
                                                  error=public, failed_at=evidence['created_at'], diagnostic_pending=True)
                    ticket['error_code'] = self.app.store.status(ticket['project_id'], ticket['version'])['error']['code']
            finally:
                # The gateway survives a killed worker and packages its fsynced
                # journals before exposing the terminal state to the owner.
                try:
                    from engine.gpu_bundle import recover_bundle
                    current = self.app.store.status(ticket['project_id'], ticket['version'])
                    recover_bundle(self.app.store.version_path(ticket['project_id'], ticket['version']),
                                   jid, current['status'], current.get('error'))
                except Exception as packaging_error:
                    print('DIAGNOSTIC_RECOVERY_FAILED '+type(packaging_error).__name__, file=sys.stderr, flush=True)
                state = self.app.store.status(ticket['project_id'], ticket['version'])
                self.app.store.set_status(ticket['project_id'], ticket['version'], status=state['status'], diagnostic_pending=False)
                with self.condition:
                    if cancel.is_set():
                        ticket['status'] = 'interrupted' if self.stopping else 'cancelled'
                    self._save(ticket)
                    self.active = None
                    self.cancellation.pop(jid, None)
                    self.condition.notify_all()

    def cancel(self, jid):
        with self.condition:
            ticket = self.tickets.get(jid)
            if not ticket:
                raise EngineError('NOT_FOUND', '작업을 찾을 수 없습니다.', status=404)
            ticket['resume_on_restart'] = False
            if jid in self.pending:
                self.pending.remove(jid)
                ticket['status'] = 'cancelled'
                self.app.store.set_status(ticket['project_id'], ticket['version'], status='interrupted',
                                          error={'code': 'USER_CANCELLED', 'message': '완료된 작업은 보존했습니다.'})
            elif jid == self.active:
                self.cancellation[jid].set()
            self._save(ticket)
            return dict(ticket)

    def close(self, timeout=15):
        with self.condition:
            self.stopping = True
            for jid in self.pending:
                self.tickets[jid]['status'] = 'interrupted'
                self._save(self.tickets[jid])
            if self.active:
                self.cancellation[self.active].set()
            self.condition.notify_all()
        if self.thread:
            self.thread.join(timeout)

    def process_runner(self, ticket, plan, cancel):
        ticket_path = self.root / (ticket['job_id'] + '.json')
        started = time.monotonic()
        try:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker-ticket', str(ticket_path),
                                     '--state-root', str(self.app.state_root)],
                                    cwd=APP_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', start_new_session=True)
        except OSError as error:
            raise RenderProcessError(returncode=None, duration=time.monotonic()-started,
                                     stderr=[type(error).__name__], category='JOB_WORKER') from error
        tails = {'stdout': deque(maxlen=25), 'stderr': deque(maxlen=25)}
        def drain(name, stream):
            for line in stream:
                tails[name].extend(safe_tail([line]))
        readers = [threading.Thread(target=drain, args=(name, stream), daemon=True)
                   for name, stream in [('stdout', proc.stdout), ('stderr', proc.stderr)]]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + self.app.maximum_job_seconds
        timed_out = False
        try:
            while proc.poll() is None:
                if cancel.wait(.2) or time.monotonic() >= deadline:
                    timed_out = not cancel.is_set()
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=5)
                    break
            for reader in readers:
                reader.join(timeout=2)
            if timed_out:
                error = RenderProcessError(returncode=proc.returncode, duration=time.monotonic()-started,
                                           stdout=tails['stdout'], stderr=tails['stderr'], category='JOB_WORKER')
                error.code = 'JOB_TIMEOUT'
                raise error
            if proc.returncode and not cancel.is_set():
                raise RenderProcessError(returncode=proc.returncode, duration=time.monotonic()-started,
                                         stdout=tails['stdout'], stderr=tails['stderr'], category='JOB_WORKER')
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=10)
            for reader in readers:
                reader.join(timeout=2)
            for stream in (proc.stdout, proc.stderr):
                stream.close()


class MobileApplication(Application):
    def __init__(self, state_root, internal_url, access_file, *, public_origins=(), public_port=7860,
                 maximum_duration=180, maximum_projects=30, disk_floor=2 * 1024**3,
                 maximum_job_seconds=4 * 3600, runner=None):
        from engine.qa_planner import configure_qa_schema
        configure_qa_schema()
        self.state_root = checked_state_root(state_root)
        self.maximum_duration, self.maximum_projects = maximum_duration, maximum_projects
        self.disk_floor, self.maximum_job_seconds = disk_floor, maximum_job_seconds
        self.upload_root = self.state_root / 'uploads'
        self.upload_root.mkdir(exist_ok=True, mode=0o700)
        ensure_access_file(access_file)
        self.sessions = OwnerSessions(access_file, self.state_root / 'auth.json')
        self.policy = RequestPolicy(public_origins, local_port=public_port)
        self.rate = RateLimiter()
        super().__init__(self.state_root / 'projects', internal_url)
        self.scheduler = DurableJobs(self, runner)

    def outputs(self, pid, version):
        from engine.gpu_bundle import diagnostic_outputs
        return super().outputs(pid, version) + diagnostic_outputs(self.store.version_path(pid, version), pid, version)

    def start_render(self, pid, version):
        return self.scheduler.submit(pid, version)

    def check_disk(self):
        if shutil.disk_usage(self.state_root).free < self.disk_floor:
            raise EngineError('STORAGE_RESERVE', '남은 저장 공간이 부족합니다.', status=507)

    def active_project_ticket(self, pid):
        with self.scheduler.condition:
            return next((dict(t) for t in self.scheduler.tickets.values()
                         if t['project_id'] == pid and t['status'] in {'queued', 'rendering'}), None)

    def check_plan_budget(self, plan):
        if not 5 <= float(plan['duration']) <= self.maximum_duration or len(plan['scenes']) > 40:
            raise EngineError('DEPLOYMENT_JOB_LIMIT', '배포 서버의 영상 길이·장면 제한을 초과했습니다.')
        self.check_disk()

    def validate_request(self, value):
        if not isinstance(value, dict):
            raise EngineError('INVALID_JSON', '요청 객체가 필요합니다.')
        allowed = {'topic', 'duration', 'style', 'quality', 'pace', 'tts', 'subtitles', 'bgm', 'sfx',
                   'narration_audio', 'narration_asset_id', 'narration_cues', 'narration_timing', 'tts_language', 'production_preset', 'qa_mode', 'direction_profile'}
        if set(value) - allowed:
            raise EngineError('UNSUPPORTED_INPUT', '지원하지 않는 입력 필드가 있습니다.')
        if not isinstance(value.get('topic'), str) or not 1 <= len(value['topic'].strip()) <= 2000:
            raise EngineError('TOPIC_LENGTH', '주제는 1~2000자여야 합니다.')
        try:
            duration = float(value.get('duration', 20))
        except (ValueError, TypeError):
            raise EngineError('INVALID_DURATION', '영상 길이를 확인해 주세요.') from None
        if not 5 <= duration <= self.maximum_duration:
            raise EngineError('DEPLOYMENT_JOB_LIMIT', '배포 서버의 영상 길이 제한을 초과했습니다.')
        for key in ('tts', 'subtitles', 'bgm', 'sfx', 'qa_mode'):
            if key in value and not isinstance(value[key], bool):
                raise EngineError('INVALID_OPTION', 'ON/OFF 설정을 확인해 주세요.')
        if len(str(value.get('style', ''))) > 120 or value.get('quality', 'HIGH') not in {'FAST', 'HIGH', 'CINEMA'}:
            raise EngineError('INVALID_OPTION', '스타일·품질 설정을 확인해 주세요.')
        if value.get('pace', 'FAST_PLUS') not in {'FAST_PLUS', 'FAST', 'NORMAL', 'CINEMATIC'}:
            raise EngineError('INVALID_OPTION', '속도 설정을 확인해 주세요.')
        if value.get('production_preset') not in {None, 'PRODUCTION_DEFAULT', 'LEGACY'}:
            raise EngineError('INVALID_OPTION', '기본 연출 설정을 확인해 주세요.')
        if value.get('direction_profile') not in {None, 'REFERENCE_MASTER', 'FAST_PLUS_LEGACY'}:
            raise EngineError('INVALID_OPTION', '연출 프로파일을 확인해 주세요.')
        value.setdefault('pace', 'FAST_PLUS')
        if 'tts_language' in value and value['tts_language'] not in {'en', 'ko', 'ja', 'zh', 'es', 'fr', 'de', 'pt'}:
            raise EngineError('INVALID_OPTION', '지원하는 음성 언어를 선택해 주세요.')
        if value.get('narration_audio') or value.get('narration_asset_id'):
            source = self.asset(value.get('narration_asset_id'), 'narration')
            if value.get('narration_audio') != source['path']:
                raise EngineError('INVALID_ASSET', '등록된 음성 파일을 사용해 주세요.')
            if float(source['probe']['format']['duration']) > duration + .1:
                raise EngineError('NARRATION_DURATION', '나레이션이 영상보다 깁니다.')
        for key in ('narration_cues', 'narration_timing'):
            if key in value and (not isinstance(value[key], list) or len(value[key]) > 300):
                raise EngineError('INVALID_TIMING', '자막 타이밍 목록을 확인해 주세요.')
        self.check_disk()
        if len(self.store.list()) >= self.maximum_projects:
            raise EngineError('PROJECT_LIMIT', '보존 가능한 프로젝트 수 한도에 도달했습니다.', status=429)
        return value

    def asset(self, aid, kind=None):
        if not re.fullmatch(r'asset_[a-f0-9]{12}', aid or ''):
            raise EngineError('INVALID_ASSET', '등록된 파일을 선택해 주세요.')
        folder = owned_path(self.upload_root, aid)
        source = read_json(folder / 'source.json')
        path = owned_path(folder, Path(source['path']).name)
        if str(path) != source['path'] or not path.is_file() or source.get('owner') != 'single-owner' or (kind and source['kind'] != kind):
            raise EngineError('INVALID_ASSET', '등록된 파일을 선택해 주세요.')
        return source


class InternalHandler(Handler):
    """Private callback listener: no client-IP auth exemption on public listener."""
    def do_POST(self):
        self.json({'error': {'code': 'READ_ONLY_INTERNAL'}}, 405)

    def dispatch(self, method):
        path = urlsplit(self.path).path
        if method in {'GET', 'HEAD'} and path == '/favicon.ico':
            # Chromium requests this independently of renderer page assets.
            # Match the approved core's empty response, without widening access.
            self.send_response(204)
            self.end_headers()
            return
        if method not in {'GET', 'HEAD'} or not (path.startswith(('/static/', '/vendor/', '/v3-src/', '/v3/assets/', '/bridge/')) or
                                               re.fullmatch(r'/render(?:_[a-z_]+)?\.html', path) or
                                               re.fullmatch(r'/api/projects/project_[a-z0-9_]{6,64}/versions/v\d{3,}/plan', path)):
            return self.json({'error': {'code': 'READ_ONLY_INTERNAL'}}, 403)
        super().dispatch(method)

    def log_message(self, *args):
        pass


LOGIN_HTML = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Engine · 소유자 로그인</title><style>body{font-family:system-ui;background:#0b1520;color:#eff5fa;max-width:28rem;margin:8vh auto;padding:1.5rem}input,button{box-sizing:border-box;width:100%;font:inherit;padding:.9rem;margin:.5rem 0;border-radius:.5rem}button{background:#a4d8ee;color:#10202b;border:0}p{line-height:1.7}</style><h1>World Engine</h1><p>소유자 접근 코드를 입력하세요.<br>코드는 서버의 비공개 접근 파일에 저장되어 있습니다.</p><form id="owner-login-form" action="/auth/login" method="post"><label for="owner-password">접근 코드</label><input id="owner-password" name="password" type="password" autocomplete="current-password" required maxlength="512"><button id="owner-login-submit" type="submit">로그인</button></form></html>'''


class MobileHandler(Handler):
    protocol_version = 'HTTP/1.0'

    def setup(self):
        self.request.settimeout(12)
        super().setup()

    def log_message(self, *args):
        # Request strings can contain user topics/file names; no credential/query logs.
        pass

    def end_headers(self):
        self.send_header('X-Frame-Options', 'DENY')
        # Preserve same-origin form POST Origin; no-referrer can turn it into null.
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Cache-Control', 'no-store')
        if getattr(self, '_effective_origin', '').startswith('https://'):
            self.send_header('Strict-Transport-Security', 'max-age=31536000')
        super().end_headers()

    def _token(self):
        try:
            c = SimpleCookie(self.headers.get('Cookie', ''))
            return c[self.app.sessions.cookie_name].value if self.app.sessions.cookie_name in c else None
        except Exception:
            return None

    def _cookie(self, token, delete=False):
        value = token or ''
        age = 0 if delete else self.app.sessions.lifetime
        result = f'{self.app.sessions.cookie_name}={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict'
        if getattr(self, '_effective_origin', '').startswith('https://'):
            result += '; Secure'
        self.send_header('Set-Cookie', result)

    def _html(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def body(self):
        size = content_length(self.headers, 64 * 1024)
        if self.headers.get_content_type() != 'application/json':
            raise SecurityError('INVALID_CONTENT_TYPE', 'JSON 요청이 필요합니다.', 415)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise SecurityError('INCOMPLETE_BODY', '요청이 완료되지 않았습니다.')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise SecurityError('INVALID_JSON', '올바른 JSON이 필요합니다.') from None
        if not isinstance(value, dict):
            raise SecurityError('INVALID_JSON', '요청 객체가 필요합니다.')
        return value

    def error(self, exc):
        if isinstance(exc, (EngineError, SecurityError)):
            self.json({'error': {'code': exc.code, 'message': str(exc)}}, exc.status)
        elif isinstance(exc, (socket.timeout, TimeoutError)):
            self.json({'error': {'code': 'REQUEST_TIMEOUT', 'message': '요청 시간이 초과했습니다.'}}, 408)
        else:
            self.json({'error': {'code': 'REQUEST_FAILED', 'message': '요청을 처리하지 못했습니다.'}}, 400)

    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        try:
            target = urlsplit(self.path)
            if len(self.path) > 4096 or target.scheme or target.netloc:
                raise SecurityError('INVALID_TARGET', '요청 주소를 확인해 주세요.')
            self._effective_origin = self.app.policy.check_request(
                self.headers, method=method, peer_ip=self.client_address[0])
            if method == 'POST':
                content_length(self.headers, 16 * 1024**2 if target.path == '/api/assets' else 64 * 1024)
            path = unquote(target.path)
            if method in {'GET', 'HEAD'} and path == '/api/health':
                return self.json({'ok': True, 'authentication_required': True, 'render_backend': 'CPU_LOCAL'})
            if path == '/auth/login':
                if method in {'GET', 'HEAD'}:
                    return self._html(LOGIN_HTML)
                return self._login()
            token = self._token()
            if not self.app.sessions.claims(token):
                if path.startswith(('/api/', '/media/', '/download/', '/auth/')):
                    raise SecurityError('AUTH_REQUIRED', '소유자 로그인이 필요합니다.', 401)
                self.send_response(303)
                self.send_header('Location', '/auth/login')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if method == 'POST' and not self.app.rate.allow(('api', self.client_address[0]), count=30):
                raise SecurityError('RATE_LIMIT', '잠시 후 다시 시도해 주세요.', 429)
            if path == '/auth/session' and method == 'GET':
                return self.json({'authenticated': True})
            if path == '/auth/logout' and method == 'POST':
                self.app.sessions.logout(token)
                self.send_response(303)
                self._cookie(None, True)
                self.send_header('Location', '/auth/login')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if path == '/api/production-default' and method == 'GET':
                from engine.production import production_default_status
                record = production_default_status()
                return self.json({k: record.get(k) for k in ('active', 'preset', 'recommended')})
            if path == '/api/projects' and method == 'POST':
                from engine.qa_planner import generate_deployment_plan as generate_plan
                request = self.app.validate_request(self.body())
                plan = generate_plan(request)
                self.app.check_plan_budget(plan)
                return self.json(self.app.store.create(request, plan), 201)
            parts = path.strip('/').split('/')
            if method == 'POST' and len(parts) == 4 and parts[:2] == ['api', 'projects'] and parts[3] in {'approve', 'render'}:
                data = self.body()
                allowed = {'version', 'plan_hash'} if parts[3] == 'approve' else {'version'}
                if set(data) - allowed:
                    raise EngineError('UNSUPPORTED_INPUT', '지원하지 않는 입력 필드가 있습니다.')
                version = data.get('version') or self.app.store.get(parts[2])['version']
                if parts[3] == 'approve':
                    active = self.app.active_project_ticket(parts[2])
                    if active:
                        if active['version'] != version or active['plan_hash'] != data.get('plan_hash'):
                            raise EngineError('PROJECT_RENDER_ACTIVE', '현재 영상 생성이 끝난 뒤 새 버전을 승인해 주세요.', status=409)
                        # A reopened browser may repeat the same approval. Avoid
                        # racing worker status writes or resetting rendering to approved.
                        return self.json(self.app.store.get(parts[2], version))
                    self.app.store.approve(parts[2], version, data.get('plan_hash'))
                    return self.json(self.app.store.get(parts[2], version))
                return self.json(self.app.start_render(parts[2], version), 202)
            if method == 'POST' and len(parts) == 6 and parts[:2] == ['api', 'projects'] and parts[3] == 'revisions' and parts[5] == 'approve':
                if self.body():
                    raise EngineError('UNSUPPORTED_INPUT', '지원하지 않는 입력 필드가 있습니다.')
                if self.app.active_project_ticket(parts[2]):
                    raise EngineError('PROJECT_RENDER_ACTIVE', '현재 영상 생성이 끝난 뒤 수정을 승인해 주세요.', status=409)
                from engine.revisions import approve_revision
                return self.json(approve_revision(self.app.store, parts[2], parts[4]))
            if method == 'POST' and len(parts) == 4 and parts[:2] == ['api', 'projects'] and parts[3] in {'revise', 'clip'}:
                data = self.body()
                version = data.get('version') or self.app.store.get(parts[2])['version']
                if parts[3] == 'revise':
                    if set(data) - {'version', 'request'} or not isinstance(data.get('request'), str) or not 1 <= len(data['request']) <= 2000:
                        raise EngineError('INVALID_REVISION', '수정 요청은 1~2000자여야 합니다.')
                    from engine.revisions import preview_revision
                    self.app.check_disk()
                    return self.json(preview_revision(self.app.store, parts[2], version, data['request']))
                if set(data) - {'version', 'scene_id', 'asset_id'}:
                    raise EngineError('INVALID_ASSET', '등록된 영상 파일을 사용해 주세요.')
                self.app.asset(data.get('asset_id'), 'clip')
                from engine.revisions import preview_clip_revision
                return self.json(preview_clip_revision(self.app.store, parts[2], version, data.get('scene_id'), data.get('asset_id'), self.app.upload_root))
            if method == 'POST' and len(parts) == 4 and parts[:2] == ['api', 'jobs'] and parts[3] == 'cancel':
                if self.body():
                    raise EngineError('UNSUPPORTED_INPUT', '지원하지 않는 입력 필드가 있습니다.')
                return self.json(self.app.scheduler.cancel(parts[2]))
            if method in {'GET', 'HEAD'} and parts[0] in {'media', 'download'}:
                if len(parts) < 4:
                    raise EngineError('INVALID_FILE', '파일을 찾을 수 없습니다.', status=404)
                version = self.app.store.version_path(parts[1], parts[2])
                relative = '/'.join(parts[3:])
                candidate = owned_path(version, relative)
                allowed = {x['path'] for x in self.app.outputs(parts[1], parts[2])}
                if relative not in allowed:
                    raise EngineError('INVALID_FILE', '공개 가능한 결과 파일이 아닙니다.', status=404)
                if len(self.headers.get('Range', '')) > 96:
                    raise EngineError('INVALID_RANGE', '범위를 확인해 주세요.', status=416)
                return self.file(candidate, parts[0] == 'download', method == 'HEAD')
            if path.startswith('/render') or path.startswith(('/vendor/', '/v3-src/', '/v3/assets/', '/bridge/')):
                raise EngineError('PRIVATE_RENDER_ENDPOINT', '내부 렌더 경로입니다.', status=404)
            # Original authenticated UI/static/plan/read-only and approved operations.
            return super().dispatch(method)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.error(exc)

    def _login(self):
        if not self.app.rate.allow(('login', self.client_address[0]), count=8):
            raise SecurityError('RATE_LIMIT', '잠시 후 다시 시도해 주세요.', 429)
        size = content_length(self.headers, 2048)
        raw = self.rfile.read(size)
        form = self.headers.get_content_type() == 'application/x-www-form-urlencoded'
        try:
            value = parse_qs(raw.decode(), strict_parsing=True).get('password', [''])[0] if form else json.loads(raw)['password']
        except (ValueError, KeyError, TypeError, UnicodeError):
            value = None
        token = self.app.sessions.login(value)
        if not token:
            raise SecurityError('LOGIN_FAILED', '접근 코드를 확인해 주세요.', 401)
        if form:
            self.send_response(303)
            self._cookie(token)
            self.send_header('Location', '/')
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            body = b'{"authenticated":true}'
            self.send_response(200)
            self._cookie(token)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def upload_asset(self, query):
        kind = query.get('kind', [''])[0]
        name = Path(query.get('filename', [''])[0]).name
        suffix = Path(name).suffix.lower()
        if query.get('license', [''])[0] != 'user_owned' or kind not in {'narration', 'clip'} or suffix not in ({'.mp4'} if kind == 'clip' else {'.wav', '.mp3'}):
            raise EngineError('INVALID_ASSET', '사용 권한이 있는 WAV/MP3/MP4만 업로드할 수 있습니다.')
        size = content_length(self.headers, 16 * 1024**2)
        self.app.check_disk()
        if not self.app.upload_root.resolve().is_relative_to(APP_ROOT):
            raise EngineError('MEDIA_STATE_ROOT', '미디어 상태 폴더는 앱 내부의 전용 볼륨이어야 합니다.')
        if len(list(self.app.upload_root.glob('asset_*'))) >= 50:
            raise EngineError('ASSET_LIMIT', '업로드 파일 보존 한도에 도달했습니다.', status=429)
        aid = 'asset_' + uuid.uuid4().hex[:12]
        folder = self.app.upload_root / aid
        folder.mkdir(mode=0o700)
        destination = folder / ('source' + suffix)
        import hashlib
        digest, deadline = hashlib.sha256(), time.monotonic() + 120
        with destination.open('xb') as f:
            left = size
            while left:
                if time.monotonic() > deadline:
                    raise SecurityError('UPLOAD_TIMEOUT', '업로드 시간이 초과했습니다.', 408)
                chunk = self.rfile.read(min(65536, left))
                if not chunk:
                    raise SecurityError('INCOMPLETE_UPLOAD', '업로드가 완료되지 않았습니다.')
                f.write(chunk)
                digest.update(chunk)
                left -= len(chunk)
        with destination.open('rb') as f:
            header = f.read(16)
        if suffix == '.wav':
            valid, fmt = header[:4] == b'RIFF' and header[8:12] == b'WAVE', 'wav'
        elif suffix == '.mp3':
            valid, fmt = header[:3] == b'ID3' or (len(header) > 1 and header[0] == 255 and header[1] & 224 == 224), 'mp3'
        else:
            valid, fmt = header[4:8] == b'ftyp', 'mov'
        if not valid:
            raise EngineError('INVALID_MEDIA_SIGNATURE', '파일 내용과 형식이 일치하지 않습니다.')
        command = ['ffprobe', '-v', 'error', '-protocol_whitelist', 'file', '-format_whitelist', fmt, '-f', fmt]
        if fmt == 'mov':
            command += ['-enable_drefs', '0']
        command += ['-show_format', '-show_streams', '-of', 'json', str(destination)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode or len(result.stdout) > 128 * 1024:
            raise EngineError('INVALID_MEDIA', '미디어를 읽을 수 없습니다.')
        media = json.loads(result.stdout)
        duration = float(media['format']['duration'])
        streams = media['streams']
        if not 0 < duration <= self.app.maximum_duration + .1 or not 1 <= len(streams) <= 2:
            raise EngineError('MEDIA_LIMIT', '미디어 길이·스트림 제한을 초과했습니다.')
        video = [s for s in streams if s.get('codec_type') == 'video']
        audio = [s for s in streams if s.get('codec_type') == 'audio']
        if kind == 'clip':
            if len(video) != 1 or video[0].get('codec_name') not in {'h264', 'hevc', 'mpeg4'} or not 1 <= int(video[0].get('width', 0)) <= 3840 or not 1 <= int(video[0].get('height', 0)) <= 3840:
                raise EngineError('MEDIA_LIMIT', '영상 코덱·해상도를 확인해 주세요.')
        elif video or not audio:
            raise EngineError('MEDIA_LIMIT', '음성 스트림이 필요합니다.')
        if any(s.get('codec_name') not in {'aac', 'mp3', 'pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_f32le'} or not 1 <= int(s.get('channels', 0)) <= 2 or int(s.get('sample_rate', 0)) > 96000 for s in audio):
            raise EngineError('MEDIA_LIMIT', '음성 코덱·채널·샘플레이트를 확인해 주세요.')
        record = {'asset_id': aid, 'source_id': aid, 'kind': kind, 'original_name': name,
                  'path': str(destination.resolve()), 'sha256': digest.hexdigest(), 'bytes': size,
                  'license': 'USER_SUPPLIED_RIGHTS', 'user_owned': True, 'rights_declared': True,
                  'owner': 'single-owner', 'author': 'User-provided', 'uploaded_at': now(), 'probe': media}
        private_json(folder / 'source.json', record)
        return self.json(record, 201)


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler, application, *, maximum_connections=16):
        self.slots = threading.BoundedSemaphore(maximum_connections)
        super().__init__(address, handler)
        self.application = application

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def worker(ticket_path, state_root):
    from engine.qa_planner import configure_qa_schema
    configure_qa_schema()
    root = checked_state_root(state_root)
    ticket_path = Path(ticket_path).resolve()
    if ticket_path.parent != root / 'jobs' or not re.fullmatch(r'job_[a-f0-9]{12}\.json', ticket_path.name):
        raise SecurityError('INVALID_TICKET', '작업 파일을 확인해 주세요.')
    ticket = read_json(ticket_path)
    store = ProjectStore(root / 'projects')  # Worker does not call recover().
    pid, version = ticket['project_id'], ticket['version']
    plan = store.require_approved(pid, version)
    if plan_hash(plan) != ticket['plan_hash']:
        raise EngineError('PLAN_CHANGED', '승인된 계획이 변경되었습니다.')
    authorized_scenes = list(plan.get('metadata', {}).get('rhythm_sample_render_authorization', {}).get('renderable_scene_ids', [s['scene_id'] for s in plan['scenes']]))
    selected_scenes = ticket.get('selected_scene_ids', authorized_scenes)
    if selected_scenes != authorized_scenes:
        raise EngineError('TICKET_SCENE_CHANGED', '승인된 작업의 장면 선택이 변경되었습니다.')
    internal = urlsplit(ticket['internal_url'])
    if internal.scheme != 'http' or internal.hostname != '127.0.0.1' or internal.path not in {'', '/'}:
        raise SecurityError('INVALID_RENDER_ORIGIN', '내부 렌더 주소를 확인해 주세요.')
    def interrupted(signum, frame):
        raise KeyboardInterrupt('owned worker interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    last_progress = {}
    bundle = None
    result = None
    failure = None
    def progress(event):
        event = {'stage': event} if isinstance(event, str) else dict(event)
        stage = event.get('stage', '')
        last_progress.update(stage=stage, scene_id=event.get('scene_id'))
        if bundle:
            bundle.event(event)
        names = {'asset_resolution': 'GIS·자산 검수', 'narration_preflight': '음성·사운드 검수',
                 'scene_start': '장면 준비', 'scene_render': '장면 렌더링', 'scene_complete': '장면 저장',
                 'scene_cache': '완료 장면 재사용', 'scene_assembly': '장면 결합', 'audio': '오디오 합성',
                 'audio_mix': '오디오 합성', 'subtitle': '자막 합성', 'automatic_qc': '전체 영상 검수'}
        sid = event.get('scene_id')
        index = next((i + 1 for i, s in enumerate(plan['scenes']) if s['scene_id'] == sid), 1)
        total = len(plan['scenes'])
        event['label'] = (f'Scene {index}/{total} · ' if sid else '') + names.get(stage, stage)
        if event.get('total_frames'):
            event['percent'] = round(90 * (index - 1 + event.get('completed_frames', 0) / event['total_frames']) / total, 1)
            event['label'] = f'Scene {index}/{total} · 장면 렌더링'
        elif stage in {'scene_cache', 'scene_complete'}:
            event['percent'] = round(90 * index / total, 1)
        elif stage in {'scene_assembly', 'audio', 'audio_mix', 'subtitle'}:
            event['percent'] = 92
        elif stage == 'automatic_qc':
            event['percent'] = 97
        store.set_status(pid, version, status='rendering', progress=event,
                         job_id=ticket['job_id'], error=None)
    try:
        from engine.gpu_bundle import DiagnosticBundle
        bundle = DiagnosticBundle(store.version_path(pid, version), ticket['job_id'], plan, state_root=root)
        bundle.start_samples()
        from engine.pipeline_stability import render_project
        with bundle.record_processes():
            result = render_project(store.version_path(pid, version), plan, ticket['internal_url'], progress,
                                    scene_filter=selected_scenes, diagnostic=bundle)
        from deployment.resume_evidence import finalize_resume_evidence
        resume_evidence = finalize_resume_evidence(root, store.version_path(pid, version),
                                                  expected_plan_hash=ticket['plan_hash'], result=result)
        store.set_status(pid, version, status='complete', result=result, error=None, diagnostic_pending=True,
                         resume_evidence=resume_evidence,
                         progress={'stage': '최종 MP4 준비 완료', 'completed': len(plan['scenes']), 'total': len(plan['scenes'])})
    except KeyboardInterrupt:
        failure = dict(code='WORKER_INTERRUPTED', failed_stage=last_progress.get('stage'), scene_id=last_progress.get('scene_id'))
        store.set_status(pid, version, status='interrupted', error=None, diagnostic_pending=True,
                         progress={'stage': '완료 Scene 보존 · 이어서 생성 가능'})
        return 130
    except Exception as error:
        record = failure_record(error, stage=last_progress.get('stage'), scene_id=last_progress.get('scene_id'))
        failure = record
        if bundle:
            try: bundle.write('python-exception.json', dict(error_type=type(error).__name__,message=str(error),trace=record.get('trace')))
            except OSError: pass
        record.update(created_at=now(), job_id=ticket['job_id'])
        private_json(root / 'jobs' / (ticket['job_id'] + '.failure.json'),
                     record)
        public = {key: record[key] for key in ('code', 'message', 'failed_stage', 'scene_id')}
        if 'subprocess' in record:
            public['diagnostics'] = record['subprocess']
        store.set_status(pid, version, status='failed', failed_at=record['created_at'], error=public, diagnostic_pending=True)
        return 1
    finally:
        if bundle:
            bundle.stop_samples()
            try:
                bundle.finish(status='FAILED' if failure else 'SUCCESS', error=failure, result=result)
            except Exception as zip_error:
                # A ZIP failure never replaces the original render failure.
                print('DIAGNOSTIC_PACKAGING_FAILED '+type(zip_error).__name__, file=sys.stderr, flush=True)
                try:
                    if bundle.reserve.exists(): bundle.reserve.unlink()
                    bundle.write('packaging-error.json', dict(code='DIAGNOSTIC_PACKAGING_FAILED', error_type=type(zip_error).__name__))
                    bundle.package()
                except Exception:
                    pass
        state = store.status(pid, version)
        store.set_status(pid, version, status=state['status'], diagnostic_pending=False)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--access-file')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--internal-port', type=int, default=7861)
    parser.add_argument('--public-origin', action='append', default=[])
    parser.add_argument('--max-duration', type=float, default=180)
    parser.add_argument('--max-projects', type=int, default=30)
    parser.add_argument('--maximum-job-seconds', type=int, default=4 * 3600)
    parser.add_argument('--worker-ticket')
    args = parser.parse_args(argv)
    if args.worker_ticket:
        return worker(args.worker_ticket, args.state_root)
    runtime = checked_state_root(args.state_root)
    lease = (runtime / 'server.lock').open('a')
    os.chmod(runtime / 'server.lock', 0o600)
    try:
        fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise SecurityError('RUNTIME_IN_USE', '이 상태 폴더의 서버가 이미 실행 중입니다.') from None
    access = args.access_file or str(Path(args.state_root) / 'owner-code.txt')
    app = MobileApplication(args.state_root, f'http://127.0.0.1:{args.internal_port}', access,
                            public_origins=args.public_origin, public_port=args.port,
                            maximum_duration=args.max_duration, maximum_projects=args.max_projects,
                            maximum_job_seconds=args.maximum_job_seconds)
    internal = BoundedHTTPServer(('127.0.0.1', args.internal_port), InternalHandler, app)
    public = BoundedHTTPServer((args.host, args.port), MobileHandler, app)
    internal_thread = threading.Thread(target=internal.serve_forever, daemon=True, name='private-render-http')
    internal_thread.start()
    app.scheduler.start()
    stopping = threading.Event()
    def stop(signum, frame):
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=public.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f'Mobile gateway ready on port {args.port}; owner code is in the private access file. No code is printed.', flush=True)
    try:
        public.serve_forever()
    finally:
        app.scheduler.close()
        internal.shutdown()
        public.server_close()
        internal.server_close()
        internal_thread.join(2)
        lease.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (SecurityError, EngineError) as error:
        print(f'Mobile startup blocked: {error.code}. Check deployment configuration.', file=sys.stderr)
        sys.exit(2)
