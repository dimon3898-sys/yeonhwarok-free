"""Fetch main, fast-forward safely, then start a fresh authenticated gateway.

Used by the existing postStartCommand path only inside GitHub Codespaces.
No reset, stash, clean, forced update, renderer request, or secret logging.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

from deployment.security import SecurityError, private_json

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
EXPECTED_REPOSITORY = 'dimon3898-sys/yeonhwarok-free'


def _git(repo, arguments, *, timeout=15, error_code='GIT_FAILED', accepted=(0,)):
    command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
               '-C', str(repo), *arguments]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    except subprocess.TimeoutExpired:
        raise SecurityError('GIT_TIMEOUT', 'Git 자동 업데이트 시간이 초과됐습니다. 강제 덮어쓰기는 하지 않습니다. Git 화면에서 상태를 확인해 주세요.') from None
    except OSError:
        raise SecurityError('GIT_UNAVAILABLE', 'Git 실행 환경을 확인해 주세요.') from None
    if result.returncode not in accepted:
        # Native Git stderr may contain credential-bearing URLs; never echo it.
        raise SecurityError(error_code, 'Git 자동 업데이트를 완료하지 못했습니다. 기존 변경 사항은 보존했습니다.')
    return result


def validate_repository(repo):
    repo = Path(repo).resolve()
    root = _git(repo, ['rev-parse', '--show-toplevel']).stdout.strip()
    if Path(root).resolve() != repo:
        raise SecurityError('AUTOSTART_WRONG_REPOSITORY', '지정된 World Engine 저장소만 업데이트할 수 있습니다.')
    value = _git(repo, ['remote', 'get-url', 'origin']).stdout.strip()
    if value.startswith('git@github.com:'):
        host, path = 'github.com', value[len('git@github.com:'):]
    else:
        try:
            parsed = urlsplit(value)
            invalid = (parsed.scheme not in {'https', 'ssh'} or parsed.query or parsed.fragment or
                       parsed.password or parsed.username not in {None, 'git'} or parsed.port is not None)
        except ValueError:
            invalid = True
        if invalid:
            raise SecurityError('AUTOSTART_WRONG_REPOSITORY', '공식 저장소 origin 설정을 확인해 주세요.')
        host, path = parsed.hostname, parsed.path.lstrip('/')
    if host != 'github.com' or path.removesuffix('.git') != EXPECTED_REPOSITORY:
        raise SecurityError('AUTOSTART_WRONG_REPOSITORY', '공식 World Engine 저장소 origin만 허용됩니다.')


def _clean(repo):
    if _git(repo, ['status', '--porcelain=v1', '--untracked-files=no']).stdout:
        raise SecurityError('GIT_DIRTY', '저장소에 수정된 파일이 있어 자동 반영을 중단했습니다. Git 화면에서 변경 사항을 확인해 주세요.')


def _check_added_paths(repo, before, target):
    # Git may overwrite ignored files when they become tracked. Protect them
    # explicitly as well as ordinary untracked files, including rename targets.
    added = _git(repo, ['diff', '--no-renames', '--name-only', '--diff-filter=A', '-z',
                        before, target]).stdout.split('\0')
    for relative in filter(None, added):
        candidate = repo / relative
        if not candidate.is_relative_to(repo) or '..' in Path(relative).parts:
            raise SecurityError('GIT_LOCAL_COLLISION', '새 파일 경로를 안전하게 확인할 수 없습니다.')
        if candidate.exists() or candidate.is_symlink():
            raise SecurityError('GIT_LOCAL_COLLISION', '새 main 파일과 기존 로컬 파일이 겹칩니다. 기존 파일은 보존했습니다.')
        for parent in candidate.parents:
            if parent == repo:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise SecurityError('GIT_LOCAL_COLLISION', '새 main 경로와 기존 로컬 경로가 겹칩니다. 기존 파일은 보존했습니다.')


def synchronize_main(repo, *, timeout=45, before_update=None):
    repo = Path(repo).resolve()
    validate_repository(repo)
    branch = _git(repo, ['symbolic-ref', '--quiet', 'HEAD'], error_code='GIT_DETACHED').stdout.strip()
    if branch != 'refs/heads/main':
        raise SecurityError('GIT_BRANCH', 'main 이외의 브랜치는 자동 변경하지 않습니다. Git 화면에서 main을 확인해 주세요.')
    _clean(repo)
    before = _git(repo, ['rev-parse', '--verify', 'HEAD^{commit}']).stdout.strip()
    # Never trust shared FETCH_HEAD or apply configured remote tracking refmaps.
    private_ref = 'refs/world-engine/autostart/' + uuid.uuid4().hex
    _git(repo, ['fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
                '--refmap=', 'origin', 'refs/heads/main:' + private_ref],
         timeout=timeout, error_code='GIT_FETCH_FAILED')
    target = _git(repo, ['rev-parse', '--verify', private_ref + '^{commit}']).stdout.strip()
    def unchanged():
        if (_git(repo, ['rev-parse', 'HEAD']).stdout.strip() != before or
                _git(repo, ['symbolic-ref', '--quiet', 'HEAD']).stdout.strip() != branch):
            raise SecurityError('GIT_CHANGED', '다른 Git 작업이 진행됐습니다. 기존 상태를 보존했습니다.')
        _clean(repo)
    try:
        if (not re.fullmatch(r'[a-f0-9]{40,64}', before) or
                not re.fullmatch(r'[a-f0-9]{40,64}', target)):
            raise SecurityError('GIT_INVALID_COMMIT', 'main 커밋을 확인할 수 없습니다.')
        unchanged()
        if before == target:
            return {'before_commit': before, 'after_commit': target, 'status': 'up_to_date'}
        ancestor = _git(repo, ['merge-base', '--is-ancestor', before, target], accepted=(0, 1))
        if ancestor.returncode:
            raise SecurityError('GIT_DIVERGED', '로컬 커밋과 main이 달라 자동 덮어쓰기를 중단했습니다. Git 화면에서 확인해 주세요.')
        _check_added_paths(repo, before, target)
        if before_update is not None:
            before_update()
        unchanged()
        _check_added_paths(repo, before, target)
        _git(repo, ['merge', '--ff-only', '--no-autostash', '--no-edit', target],
             timeout=timeout, error_code='GIT_UPDATE_FAILED')
        after = _git(repo, ['rev-parse', '--verify', 'HEAD^{commit}']).stdout.strip()
        if after != target:
            raise SecurityError('GIT_CHANGED', '업데이트 결과를 확인할 수 없습니다. 기존 Git 이력은 보존했습니다.')
        return {'before_commit': before, 'after_commit': after, 'status': 'updated'}
    finally:
        # Delete only this attempt's ref and only if its value is still ours.
        # A cleanup failure must not hide the original fixed error or readiness.
        try:
            _git(repo, ['update-ref', '-d', private_ref, target])
        except SecurityError:
            pass


def automatic_start(args):
    """Run once under a deployment-owned lock; child imports updated files afresh."""
    from deployment import start_codespace as startup
    state = Path(args.state_root).resolve()
    if Path(args.state_root).is_symlink() or not state.is_relative_to(APP / 'deployment/runtime'):
        raise SecurityError('UNSAFE_STATE_ROOT', '기존 deployment/runtime 상태 폴더만 사용합니다.')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    history = state / 'startup-history'
    if (history.is_symlink() or (history.exists() and not history.is_dir()) or
            not history.resolve().is_relative_to(state)):
        raise SecurityError('UNSAFE_STATE_ROOT', '비공개 시작 기록 폴더가 안전하지 않습니다.')
    lockpath = state / 'autostart.lock'
    fd = os.open(lockpath, os.O_WRONLY | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.fchmod(fd, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SecurityError('AUTOSTART_BUSY', '자동 시작이 이미 진행 중입니다.') from None
        run_id = 'autostart_' + uuid.uuid4().hex[:12]
        report = {'format': 'world-codespaces-autostart-v1', 'run_id': run_id,
                  'started_at': datetime.now(timezone.utc).isoformat(),
                  'status': 'starting', 'server_ready': False, 'new_render_requests': 0}
        def save():
            private_json(history / (run_id + '.json'), report)
            private_json(state / 'startup-update.json', report)
        try:
            pid = startup._read_record(state / 'server.pid', pid=True)
            old = startup._owned_process(pid, state, args) if pid is not None else None
            if old is not None:
                startup._assert_idle(state)
            else:
                # Persisted interrupted/queued tickets are allowed after Stop;
                # the preserved gateway's normal checkpoint recovery owns them.
                startup._assert_no_worker(state)
                startup._ports_free(args)
            def prepare_update():
                # Close the verified idle gateway before checkout changes so
                # its HTTP API cannot admit a renderer against changing files.
                if old is not None:
                    startup._stop_owned(old, state, args)
                    report['previous_server_stopped_for_update'] = True
                startup._assert_no_worker(state)
                startup._ports_free(args)
            report['sync'] = synchronize_main(REPO, before_update=prepare_update)
            command = [sys.executable, str(APP / 'deployment/start_codespace.py'),
                       '--state-root', str(state), '--port', str(args.port),
                       '--internal-port', str(args.internal_port), '--no-sync']
            if args.refresh:
                command.append('--refresh')
            child = subprocess.run(command, cwd=APP, capture_output=True, text=True,
                                   timeout=60, env=os.environ.copy())
            if child.returncode:
                raise SecurityError('SERVER_START_FAILED', '서버 시작을 완료하지 못했습니다. 비공개 시작 기록을 확인해 주세요.')
            result = json.loads(child.stdout)
            if (result.get('status') not in {'started', 'refreshed', 'already_running'} or
                    not startup._healthy(args.port)):
                raise SecurityError('SERVER_NOT_READY', '7860 서버 준비 상태를 확인하지 못했습니다.')
            report.update(status='ready', server_ready=True,
                          server_status=result['status'], port=args.port,
                          completed_at=datetime.now(timezone.utc).isoformat())
            save()
            print(json.dumps({**result, 'automatic_main_sync': report['sync']['status'],
                              'git_commit': report['sync']['after_commit']}))
            return 0
        except Exception as error:
            code = getattr(error, 'code', None) or ('AUTOSTART_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'AUTOSTART_FAILED')
            report.update(status='blocked', error_code=code,
                          completed_at=datetime.now(timezone.utc).isoformat())
            save()
            if isinstance(error, (SecurityError, startup.StartupError)):
                raise SecurityError(code, str(error)) from None
            raise SecurityError(code, '자동 시작을 완료하지 못했습니다. 기존 파일과 시작 기록은 보존했습니다.') from None
    finally:
        os.close(fd)
