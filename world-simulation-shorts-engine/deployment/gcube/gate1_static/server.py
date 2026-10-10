"""Gate 1 only: authenticated, single-frame download service. No video imports."""
from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))
from bootstrap import environment_evidence, prepare_user_environment, redact, worker_environment, LIMIT


def verify_bundle(bundle):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    for row in manifest['files']:
        target = bundle / row['file']
        if not target.resolve().is_relative_to(bundle.resolve()):
            raise ValueError('BUNDLE_PATH_INVALID')
        content = target.read_bytes()
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('FROZEN_SOURCE_INTEGRITY_FAILED')
    plan = json.loads((bundle / 'compiled-plan.json').read_text())
    if hashlib.sha256((bundle / 'renderer.mjs').read_bytes()).hexdigest() != plan['provenance']['shaderHash']:
        raise ValueError('RENDERER_SOURCE_CHANGED')
    if plan['gate'] != 1 or plan['kind'] != 'STATIC_ONLY':
        raise ValueError('STATIC_SCENE_REQUIRED')
    return manifest


class ProofService:
    def __init__(self, bundle, state, password, worker=None):
        self.bundle, self.state = Path(bundle), Path(state)
        self.manifest = verify_bundle(self.bundle)
        self.password = password.encode()
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.worker = worker or self.run_worker
        self.sessions = {}
        self.jobs = {}
        self.lock = threading.Lock()
        self.busy = False
        self.login_failures = {}

    def run_worker(self, mode, output, emit):
        if mode not in {'probe', 'proof'}:
            raise ValueError('PUBLIC_WORKER_MODE_INVALID')
        preferred = os.environ.get('WORLD_ENGINE_GPU_PROFILE', 'vulkan')
        if preferred not in {'vulkan', 'egl'}:
            raise ValueError('GPU_PROFILE_INVALID')
        env = worker_environment(os.environ)
        # The browser subprocess never receives the owner code or sessions.
        env.pop('WORLD_ENGINE_OWNER_CODE', None)
        env['WORLD_ENGINE_RENDER_MODE'] = 'gpu-required'
        env['STATIC_PROOF_BUNDLE'] = str(self.bundle)
        runtime = {'result': 'NOT_RUN'}
        runtime_error = None
        from gpu_runtime_facts import graphics_runtime_inventory
        try:
            from graphics_runtime import prepare_graphics_runtime
            updates, runtime = prepare_graphics_runtime(env)
            env.update(updates)
        except Exception as error:
            runtime_error = {'name': type(error).__name__, 'message': redact(error), 'stack': redact(traceback.format_exc())}
            runtime = {'status': 'FAIL', 'error': runtime_error}
        profiles = [preferred] + (['egl'] if preferred == 'vulkan' else [])
        selected = None
        attempts = {}
        for profile in profiles:
            env['WORLD_ENGINE_GPU_PROFILE'] = profile
            attempt_output = output / profile
            attempt_output.mkdir(mode=0o700)
            context = {'environment': environment_evidence(env), 'graphics_runtime': runtime,
                       'inventory': graphics_runtime_inventory(env)}
            context_file = attempt_output / 'context.json'
            context_file.write_text(json.dumps(context))
            env['GATE1_ATTEMPT_CONTEXT'] = str(context_file)
            emit({'stage': 'GPU_CAPABILITY_' + profile.upper(), 'result': 'IN_PROGRESS'})
            if runtime_error:
                diagnostic = {**context, 'backend': profile, 'error_code': 'GRAPHICS_RUNTIME_PREPARATION_FAILED',
                              'failed_stage': 'GRAPHICS_RUNTIME', 'error': runtime_error,
                              'capability_result': {'result': 'FAIL'}, 'worker_process': {'result': 'NOT_RUN'},
                              'stages': [{'name': name, 'result': 'PASS' if name in {'START', 'ENVIRONMENT'} else 'FAIL' if name in {'GRAPHICS_RUNTIME', 'RESULT'} else 'NOT_RUN'}
                                         for name in ['START', 'ENVIRONMENT', 'GRAPHICS_RUNTIME', 'BROWSER_LAUNCH', 'PAGE_CREATE', 'PAGE_LOAD', 'WEBGL2_CREATE', 'GPU_IDENTITY', 'READPIXELS', 'RESULT']]}
                (attempt_output / 'diagnostic.json').write_text(json.dumps(diagnostic))
                attempts[profile] = diagnostic
                emit({'stage': 'GRAPHICS_RUNTIME_PREPARATION_FAILED', 'result': 'FAIL'})
                continue
            process = self.child('probe', attempt_output, env, emit)
            diagnostic = self.read_attempt(attempt_output, profile, context, process)
            attempts[profile] = diagnostic
            code = process['exit_code']
            if code == 0 and diagnostic.get('capability_result', {}).get('result') == 'PASS':
                selected = profile
                break
        if selected is None:
            return False, {'schema_version': 2, 'purpose': 'GATE1_STATIC_PROOF', 'attempts': attempts,
                           'error_code': diagnostic['error_code'], 'failed_stage': diagnostic.get('failed_stage'),
                           'capability_result': {'result': 'FAIL'}, 'peak_memory': 'UNKNOWN',
                           'gpu_visual_quality': 'NOT_RUN'}
        diagnostic = {**diagnostic, 'attempts': attempts}
        if mode == 'probe':
            return True, diagnostic
        env['WORLD_ENGINE_GPU_PROFILE'] = selected
        emit({'stage': 'ONE_FRAME_' + selected.upper(), 'result': 'IN_PROGRESS'})
        process = self.child('proof', output, env, emit)
        diagnostic = {**self.read_attempt(output, selected, context, process), 'attempts': attempts}
        png = output / 'SUEZ_STATIC_PROOF_RTX4080S.png'
        ok = process['exit_code'] == 0 and diagnostic.get('capability_result', {}).get('result') == 'PASS' and diagnostic.get('frame_count') == 1 and png.is_file()
        return ok, diagnostic

    @staticmethod
    def read_attempt(output, profile, context, process):
        filename = output / 'diagnostic.json'
        if filename.is_file():
            diagnostic = json.loads(filename.read_text())
        else:
            diagnostic = {'error_code': 'WORKER_TIMEOUT' if process['timed_out'] else 'WORKER_PROCESS_FAILED',
                          'failed_stage': 'WORKER', 'capability_result': {'result': 'FAIL'}}
        diagnostic.update(backend=profile, worker_process=process, **context)
        browser = output / 'chromium-process.json'
        diagnostic['chromium_process'] = json.loads(browser.read_text()) if browser.is_file() else {'exit_code': 'UNKNOWN', 'signal': 'UNKNOWN'}
        for stream in ('stdout', 'stderr'):
            filename = output / ('chromium.' + stream + '.log')
            diagnostic['chromium_' + stream] = redact(filename.read_text(errors='replace')) if filename.is_file() else ''
        return diagnostic

    @staticmethod
    def child(mode, output, env, emit):
        # Each child has its own process group and a deadline. A watchdog also
        # kills Chromium descendants when a child exits or stops emitting.
        process = subprocess.Popen(['node', str(HERE / 'worker.mjs'), mode, str(output)],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        timed_out = threading.Event()
        stderr = []

        def read_stderr():
            size = 0
            for line in process.stderr:
                if size < LIMIT:
                    value = redact(line, env)[:LIMIT - size]
                    stderr.append(value)
                    size += len(value)

        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()
        stdout = []
        size = 0

        def terminate():
            timed_out.set()
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        timer = threading.Timer(180, terminate)
        timer.start()
        try:
            for line in process.stdout:
                if size < LIMIT:
                    value = redact(line, env)[:LIMIT - size]
                    stdout.append(value)
                    size += len(value)
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and isinstance(row.get('stage'), str):
                        emit({key: row[key] for key in ('stage', 'result', 'elapsed_seconds') if key in row})
                except ValueError:
                    pass
            code = process.wait(timeout=5)
            reader.join(timeout=3)
            return {'exit_code': code if code >= 0 else None, 'signal': -code if code < 0 else None,
                    'timed_out': timed_out.is_set(), 'stdout': ''.join(stdout), 'stderr': ''.join(stderr),
                    'capture_limit_bytes': LIMIT}
        finally:
            timer.cancel()
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.stdout.close()
            process.wait(timeout=5)
            reader.join(timeout=3)
            process.stderr.close()

    def start_job(self, mode):
        with self.lock:
            if self.busy:
                return None
            self.busy = True
            job_id = secrets.token_hex(16)
            job = {'id': job_id, 'mode': mode, 'status': 'RUNNING', 'started': time.time(), 'events': []}
            self.jobs[job_id] = job
        output = self.state / job_id
        output.mkdir(mode=0o700)

        def emit(event):
            row = {**event, 'elapsed_seconds': round(time.time() - job['started'], 3)}
            with self.lock:
                job['events'].append(row)
                job['events'] = job['events'][-100:]
            print(json.dumps({'job': job_id, **row}), flush=True)

        def run():
            try:
                ok, diagnostic = self.worker(mode, output, emit)
                temporary = output / 'diagnostic.json.tmp'
                temporary.write_text(json.dumps(diagnostic, indent=2))
                temporary.replace(output / 'diagnostic.json')
                with self.lock:
                    job['diagnostic'] = diagnostic
                    job['status'] = 'PASS' if ok else 'FAIL'
            except Exception as error:
                diagnostic = {'error_code': 'STATIC_PROOF_WORKER_FAILED', 'failed_stage': 'SERVER_BOOTSTRAP',
                              'error': {'name': type(error).__name__, 'message': redact(error), 'stack': redact(traceback.format_exc())},
                              'capability_result': {'result': 'FAIL'}, 'peak_memory': 'UNKNOWN'}
                (output / 'diagnostic.json').write_text(json.dumps(diagnostic))
                with self.lock:
                    job.update(status='FAIL', diagnostic=diagnostic)
            finally:
                emit({'stage': 'FINISHED', 'result': job['status']})
                with self.lock:
                    self.busy = False

        threading.Thread(target=run, daemon=True).start()
        return job_id


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'Gate1StaticProof'

        def log_message(self, *_):
            pass  # No owner code, query strings or cookie logging.

        def reply(self, status, body, content_type='application/json', headers=None):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            for key, value in {'Content-Type': content_type, 'Content-Length': str(len(body)),
                               'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                               'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'",
                               **(headers or {})}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def session(self):
            pairs = [x.strip().partition('=') for x in self.headers.get('Cookie', '').split(';')]
            token = next((v for k, _, v in pairs if k == 'proof_session'), '')
            value = service.sessions.get(token)
            if value and value['expires'] > time.time():
                return value
            return None

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/healthz':
                self.reply(200, {'ok': True, 'authentication_required': True, 'renderer': 'MAP_INFOGRAPHIC_RENDERER_V1', 'gate': 1, 'auto_render': False})
                return
            if path in {'/', '/ui.js', '/ui.css'}:
                file, mime = {'/': ('index.html', 'text/html; charset=utf-8'), '/ui.js': ('ui.js', 'text/javascript'), '/ui.css': ('ui.css', 'text/css')}[path]
                self.reply(200, (HERE / file).read_bytes(), mime)
                return
            session = self.session()
            if not session:
                self.reply(401, {'error': 'LOGIN_REQUIRED'})
                return
            if path == '/api/session':
                self.reply(200, {'authenticated': True, 'csrf': session['csrf'], 'source': service.manifest['source_identity']})
                return
            if path.startswith('/api/jobs/'):
                job_id = path.removeprefix('/api/jobs/')
                with service.lock:
                    job = service.jobs.get(job_id)
                    public = json.loads(json.dumps(job)) if job else None
                self.reply(200 if public else 404, public or {'error': 'JOB_NOT_FOUND'})
                return
            parts = path.strip('/').split('/')
            if len(parts) == 3 and parts[0] == 'download' and parts[2] in {'png', 'diagnostic'}:
                job = service.jobs.get(parts[1])
                if not job or job['status'] == 'RUNNING':
                    self.reply(409, {'error': 'OUTPUT_NOT_READY'})
                    return
                if parts[2] == 'png' and (job['status'] != 'PASS' or job['mode'] != 'proof'):
                    self.reply(409, {'error': 'GPU_PROOF_NOT_PASSED'})
                    return
                filename = 'SUEZ_STATIC_PROOF_RTX4080S.png' if parts[2] == 'png' else 'SUEZ_STATIC_PROOF_RTX4080S.diagnostic.json'
                file = service.state / job['id'] / ('SUEZ_STATIC_PROOF_RTX4080S.png' if parts[2] == 'png' else 'diagnostic.json')
                if not file.is_file():
                    self.reply(404, {'error': 'OUTPUT_MISSING'})
                    return
                self.reply(200, file.read_bytes(), 'image/png' if parts[2] == 'png' else 'application/json',
                           {'Content-Disposition': 'attachment; filename="' + filename + '"'})
                return
            self.reply(404, {'error': 'NOT_FOUND'})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                self.reply(400, {'error': 'REQUEST_INVALID'})
                return
            if path == '/auth/login':
                address = self.client_address[0]
                failures, since = service.login_failures.get(address, (0, time.time()))
                if time.time() - since > 60:
                    failures, since = 0, time.time()
                if failures >= 10:
                    self.reply(429, {'error': 'LOGIN_RATE_LIMITED'})
                    return
                if not isinstance(body.get('password'), str) or not hmac.compare_digest(body['password'].encode(), service.password):
                    service.login_failures[address] = (failures + 1, since)
                    self.reply(403, {'error': 'LOGIN_FAILED'})
                    return
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                service.sessions[token] = {'csrf': csrf, 'expires': time.time() + 43200}
                secure = '; Secure' if self.headers.get('X-Forwarded-Proto') == 'https' else ''
                self.reply(200, {'authenticated': True, 'csrf': csrf}, headers={'Set-Cookie': f'proof_session={token}; HttpOnly; SameSite=Strict; Path=/{secure}'})
                return
            session = self.session()
            if not session:
                self.reply(401, {'error': 'LOGIN_REQUIRED'})
                return
            if not hmac.compare_digest(self.headers.get('X-Proof-CSRF', ''), session['csrf']):
                self.reply(403, {'error': 'CSRF_REQUIRED'})
                return
            if path not in {'/api/check-gpu', '/api/generate'} or body:
                self.reply(400, {'error': 'FIXED_STATIC_SCENE_ONLY'})
                return
            job_id = service.start_job('probe' if path == '/api/check-gpu' else 'proof')
            self.reply(202 if job_id else 409, {'job': job_id} if job_id else {'error': 'PROOF_ALREADY_RUNNING'})

    return Handler


def main():
    import pwd
    account = pwd.getpwnam('engine')
    password = os.environ.get('WORLD_ENGINE_OWNER_CODE', '')
    if len(password) < 12:
        sys.exit('WORLD_ENGINE_OWNER_CODE_REQUIRED_MIN_12')
    if os.environ.get('WORLD_ENGINE_RENDER_MODE', 'gpu-required') != 'gpu-required':
        sys.exit('CPU_FALLBACK_NOT_ALLOWED')
    # Same audited provider-device group preservation as the existing image.
    if os.getuid() == 0:
        from gpu_access import collect_device_groups
        runtime = Path('/run/world-engine')
        runtime.mkdir(exist_ok=True, mode=0o700)
        os.chown(runtime, account.pw_uid, account.pw_gid)
        os.setgroups(collect_device_groups())
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.environ.update(prepare_user_environment(account, '/run/world-engine'))
    service = ProofService(os.environ.get('STATIC_PROOF_BUNDLE', str(HERE / 'bundle')),
                           os.environ.get('STATIC_PROOF_STATE', '/tmp/gate1-static-output'), password)
    port = int(os.environ.get('PORT', '8000'))
    print(json.dumps({'stage': 'GATE1_STATIC_SERVICE', 'result': 'PASS', 'port': port, 'auto_render': False}), flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), make_handler(service)).serve_forever()


if __name__ == '__main__':
    main()
