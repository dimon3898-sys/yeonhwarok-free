"""Bounded render failure evidence; never serialize commands, request bodies or env."""
from __future__ import annotations

import os
from pathlib import Path
import re
import traceback


def safe_tail(lines):
    result = []
    secrets = [value for key, value in os.environ.items()
               if re.search(r'OWNER_CODE|TOKEN|SECRET|PASSWORD|AUTHORIZATION|COOKIE', key, re.I)
               and len(value) >= 4]
    for value in list(lines)[-25:]:
        line = str(value)[:8192]
        for secret in secrets:
            line = line.replace(secret, '[REDACTED]')
        if re.search(r'owner[-_ ]?code|password|cookie|authorization|secret|token|request.body', line, re.I):
            result.append('[sensitive log line omitted]')
            continue
        line = re.sub(r'https?://[^\s"\'<>]+', '[URL omitted]', line)
        line = re.sub(r'[^\s"\'<>]*\?[^\s"\'<>]*', '[query omitted]', line)
        line = re.sub(r'(?<![\w])/(?:[\w.\-]+/)+[\w.\-]*', '[path omitted]', line)
        result.append(line[:1200])
    return result


class RenderProcessError(RuntimeError):
    def __init__(self, *, returncode, duration, stdout=(), stderr=(), category='SCENE_RENDERER'):
        self.code = category + ('_EXIT' if returncode is not None else '_START_FAILED')
        self.diagnostics = dict(command_category=category, return_code=returncode,
                                duration_seconds=round(duration, 3),
                                stdout_tail=safe_tail(stdout), stderr_tail=safe_tail(stderr))
        super().__init__(self.code)


def failure_record(error, *, stage=None, scene_id=None):
    code = getattr(error, 'code', None)
    if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,80}', code):
        code = ('STORAGE_WRITE_FAILED' if isinstance(error, PermissionError) else
                'ASSET_NOT_FOUND' if isinstance(error, FileNotFoundError) else
                'SCENE_PREP_FAILED' if stage == 'scene_start' else 'WORKER_FAILED')
    messages = {'SCENE_RENDERER_EXIT': '장면 렌더러가 오류로 종료되었습니다.',
                'SCENE_RENDERER_START_FAILED': '장면 렌더러 프로세스를 시작하지 못했습니다.',
                'STORAGE_WRITE_FAILED': '작업 저장 공간에 쓸 수 없습니다.',
                'ASSET_NOT_FOUND': '필요한 장면 파일을 찾지 못했습니다.',
                'SCENE_PREP_FAILED': '장면 준비 중 오류가 발생했습니다.',
                'JOB_TIMEOUT': '영상 생성 제한 시간을 초과했습니다.'}
    record = dict(code=code, message=messages.get(code, '영상 생성 단계에서 오류가 발생했습니다.'),
                  error_type=type(error).__name__, failed_stage=stage, scene_id=scene_id)
    record['trace'] = [dict(file=Path(frame.filename).name, function=frame.name, line=frame.lineno)
                       for frame in traceback.extract_tb(error.__traceback__)[-12:]]
    if isinstance(error, RenderProcessError):
        record['subprocess'] = error.diagnostics
    # The original str(error) can contain passwords, URL queries or request data.
    return record
