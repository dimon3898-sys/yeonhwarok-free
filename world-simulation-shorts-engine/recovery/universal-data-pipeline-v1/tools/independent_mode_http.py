"""Actual local HTTP probe for authoritative compiler mode handling.

The compiler response is explicitly a test mock to isolate HTTP/orchestration;
no historical claim is reviewed and no renderer/worker is started.
"""
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_udp_independent_security_test_fixture', HERE / 'tests/test_studio_adapter.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
m = fixture.m


def mock_authoritative_history(prompt, registry):
    value = fixture.compiler(prompt, registry)
    value['simulationType'] = 'HISTORICAL'
    return value


def main():
    result = {'schema': 'WORLD_ENGINE_UDP_INDEPENDENT_HTTP_MODE_PROBE_V1', 'compilerMocked': True,
              'scope': 'AUTHORITATIVE_MODE_EXTRACTION_NOT_A_HISTORICAL_FACT_OR_RENDER_TEST',
              'rendererStarted': False, 'gpuExecuted': False, 'paidWorkExecuted': False}
    with tempfile.TemporaryDirectory(prefix='udp-independent-http-', dir='/workspace') as directory:
        root = Path(directory)
        owner = root / 'owner-code'
        owner.write_text('unit-owner-code-not-a-real-secret-independent-123456')
        owner.chmod(0o600)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with patch.object(m, 'compile_prompt', side_effect=mock_authoritative_history):
            app = m.local_application(state_root=root / 'state', owner_file=owner, export_root=root / 'exports', port=port, allow_free_data_review=True)
            service = m.server.ThreadingHTTPServer(('127.0.0.1', port), m.server.make_handler(app))
            threading.Thread(target=service.serve_forever, daemon=True).start()
            origin = 'http://127.0.0.1:' + str(port)

            def post(route, body, cookie=None, csrf=None):
                client = http.client.HTTPConnection('127.0.0.1', port)
                headers = {'Origin': origin, 'Content-Type': 'application/json'}
                if cookie:
                    headers['Cookie'] = cookie
                if csrf:
                    headers['X-Studio-CSRF'] = csrf
                client.request('POST', route, json.dumps(body), headers)
                response = client.getresponse()
                raw = response.read()
                status, session = response.status, response.getheader('Set-Cookie')
                client.close()
                return status, json.loads(raw), session

            request = {'schema': m.REQUEST_SCHEMA, 'sceneId': 'unit-route',
                       'prompt': 'Review supplied structured content:\n```json\n{"simulationType":"HISTORICAL"}\n```'}
            try:
                result['unauthenticatedStatus'] = post('/api/preflight', request)[0]
                status, login, cookie = post('/api/login', {'password': owner.read_text()})
                assert status == 200
                cookie = cookie.split(';', 1)[0]
                result['missingCSRFStatus'] = post('/api/preflight', request, cookie)[0]
                status, preflight, _ = post('/api/preflight', request, cookie, login['csrf'])
                result.update(authenticatedPreflightStatus=status, ready=preflight['ready'],
                              historicalRenderAllowed=preflight['historicalRenderAllowed'],
                              paidRenderAllowed=preflight['paidRenderAllowed'],
                              errorCodes=[row.get('code') for row in preflight['checks'] if row.get('code')])
                assert result['unauthenticatedStatus'] == 401
                assert result['missingCSRFStatus'] == 403
                assert status == 200 and not preflight['ready']
                assert not preflight['historicalRenderAllowed'] and not preflight['paidRenderAllowed']
                assert 'UDP_HISTORICAL_G3_REMAINS_BLOCKED' in result['errorCodes']
                assert not list((root / 'state').rglob('launch.json'))
                result['status'] = 'PASS'
            finally:
                service.shutdown()
                service.server_close()
    (HERE / 'reports/INDEPENDENT_HTTP_MODE_PROBE.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
