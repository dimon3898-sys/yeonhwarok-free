"""Response-only static UI decoration after the unchanged handler's guards.

This wrapper does not override request dispatch, authentication, CSRF, policy,
login/setup/API/download routes, response headers, or controller admission.
"""
from pathlib import Path
import hashlib
import html
import json
import re

HERE = Path(__file__).resolve().parent


def ui_bytes(example_file, expected_example_sha256):
    path = Path(example_file)
    if (not path.is_absolute() or '..' in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))
            or not path.is_file() or path.stat().st_size > 4 * 1024 ** 2
            or not re.fullmatch(r'[a-f0-9]{64}', expected_example_sha256 or '')):
        raise RuntimeError('HANDOFF_MOBILE_EXAMPLE_SOURCE_REQUIRED')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_example_sha256:
        raise RuntimeError('HANDOFF_MOBILE_EXAMPLE_SHA_MISMATCH')
    example = json.loads(raw)
    if not isinstance(example, dict):
        raise RuntimeError('HANDOFF_MOBILE_EXAMPLE_OBJECT_REQUIRED')
    template = (HERE / 'index.html').read_text()
    if template.count('__HANDOFF_EXAMPLE_JSON__') != 1:
        raise RuntimeError('HANDOFF_MOBILE_EXAMPLE_ANCHOR_INVALID')
    text = json.dumps(example, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return (template.replace('__HANDOFF_EXAMPLE_JSON__', html.escape(text)).encode(),
            (HERE / 'app.js').read_bytes())


def wrap_handler(base_handler, *, example_file, expected_example_sha256):
    index, script = ui_bytes(example_file, expected_example_sha256)

    class HandoffMobileHandler(base_handler):
        def _send(self, status, body, content_type='application/json; charset=utf-8', extra=()):
            # The base _dispatch already checked target, Host/Origin and owner
            # authentication before serving these exact successful GET routes.
            # Every other response is byte-for-byte delegated without change.
            if self.command == 'GET' and status == 200:
                if self.path == '/' and content_type.split(';', 1)[0] == 'text/html':
                    body = index
                elif self.path == '/app.js' and content_type.split(';', 1)[0] == 'text/javascript':
                    body = script
            return super()._send(status, body, content_type, extra)

    return HandoffMobileHandler
