"""Mobile UI and bounded UP2 details after the unchanged owner/CSRF guards.

Dispatch and authentication delegate to the preserved handler. Only sanitized
diagnostics attached to the original exception decorate its existing response.
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
        def _authenticate(self, mutation=False):
            token = super()._authenticate(mutation)
            self._up2_authenticated = True
            return token

        def _dispatch(self):
            # Handler instances may serve multiple requests on one connection.
            self._up2_authenticated = False
            self._up2_detail = None
            try:
                return super()._dispatch()
            except Exception as error:
                if (self._up2_authenticated and self.command == 'POST'
                        and self.path in {'/api/preflight', '/api/submissions'}
                        and getattr(error, 'code', None) == 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED'):
                    try:
                        # Only the controller's already-sanitized immutable snapshot;
                        # never read raw error.fields, messages, input or stderr here.
                        encoded = getattr(error, '_up2_public_diagnostic_json', None)
                        if type(encoded) is str and len(encoded) <= 16384:
                            detail = json.loads(encoded)
                            if (type(detail) is dict
                                    and detail.get('schema') == 'WORLD_ENGINE_UP2_DIAGNOSTIC_V1'
                                    and detail.get('code') == error.code
                                    and detail.get('sceneIdEncoding') == 'ZERO_BASED_INPUT_SCENE_INDEX'
                                    and detail.get('limit') == 16):
                                self._up2_detail = detail
                    except Exception:
                        pass  # Preserve the identical exception and HTTP status.
                raise

        def _send(self, status, body, content_type='application/json; charset=utf-8', extra=()):
            # The base _dispatch already checked target, Host/Origin and owner
            # authentication before serving these exact successful GET routes.
            # Other successful responses are delegated without change.
            if self.command == 'GET' and status == 200:
                if self.path == '/' and content_type.split(';', 1)[0] == 'text/html':
                    body = index
                elif self.path == '/app.js' and content_type.split(';', 1)[0] == 'text/javascript':
                    body = script
            detail = getattr(self, '_up2_detail', None)
            self._up2_detail = None
            if (detail is not None and getattr(self, '_up2_authenticated', False)
                    and self.command == 'POST'
                    and self.path in {'/api/preflight', '/api/submissions'}
                    and type(status) is int and 400 <= status <= 599
                    and type(body) is dict and type(body.get('error')) is dict
                    and body['error'].get('code') == 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED'):
                try:
                    body = {**body, 'error': {**body['error'], 'fields': detail['fields'],
                        'diagnostic': {key: detail[key] for key in ('schema', 'sceneIdEncoding', 'limit')}}}
                except Exception:
                    pass
            return super()._send(status, body, content_type, extra)

    return HandoffMobileHandler

