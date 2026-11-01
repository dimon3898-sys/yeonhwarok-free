"""New diagnostic bridge integration; synthetic controller, real handler/auth chain.
No compiler, renderer, GPU, prior PASS suite, or network listener is executed.
"""
import ast
from contextlib import redirect_stdout
from copy import deepcopy
from email.message import Message
import hashlib
from http.cookies import SimpleCookie
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

RECOVERY = Path(__file__).resolve().parent.parent
PROFILE = RECOVERY / 'codex-to-gcube-handoff-v1'
CODE = 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

original = module('up2_test_original_http', RECOVERY / 'production-studio-mvp-v1/server.py')
mobile = module('up2_test_mobile_http', PROFILE / 'mobile/handler.py')
controller_ast = ast.parse((PROFILE / 'controller/nvidia_controller.py').read_text())
helpers = {'re': re, 'json': json}
selected = [node for node in controller_ast.body if (
    isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith('_UP2_') for t in node.targets))
    or isinstance(node, ast.FunctionDef) and node.name in {'_up2_diagnostic', '_normal_with_up2_diagnostic'}]
exec(compile(ast.Module(body=selected, type_ignores=[]), '<actual-controller-helpers>', 'exec'), helpers)

# Keep the exact handler methods in both deployed intermediate wrappers, but do
# not execute setup bootstrap, frozen-manifest scans or physical GPU admission.
https_ast = ast.parse((RECOVERY / 'studio-https-bootstrap-v1/https_server.py').read_text())
https_nodes = []
for node in https_ast.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'fail': https_nodes.append(node)
    if isinstance(node, ast.ClassDef) and node.name == '_ApplicationProxy': https_nodes.append(node)
    if isinstance(node, ast.ClassDef) and node.name == 'Application':
        node = deepcopy(node)
        node.body = [method for method in node.body if isinstance(method, ast.FunctionDef) and method.name == 'handler']
        https_nodes.append(node)
https_ns = dict(original=original, security=original.security, TTL=600,
                urlsplit=urlsplit, unquote=unquote, SimpleCookie=SimpleCookie, SimpleNamespace=SimpleNamespace)
exec(compile(ast.Module(body=https_nodes, type_ignores=[]), '<actual-https-handler>', 'exec'), https_ns)
proxy_ast = ast.parse((RECOVERY / 'studio-https-proxy-fix-v1/proxy_server.py').read_text())
proxy_class = deepcopy(next(n for n in proxy_ast.body if isinstance(n, ast.ClassDef) and n.name == 'Application'))
proxy_class.body = [m for m in proxy_class.body if isinstance(m, ast.FunctionDef) and m.name == 'handler']
proxy_ns = dict(parent=SimpleNamespace(server=SimpleNamespace(Application=https_ns['Application']), security=original.security),
                _audit_rate=original.security.RateLimiter(), request_diagnostics=lambda *_: {}, json=json)
exec(compile(ast.Module(body=[proxy_class], type_ignores=[]), '<actual-proxy-handler>', 'exec'), proxy_ns)

class Up2Error(Exception):
    code = CODE
    status = 422
    def __init__(self, code=CODE):
        super().__init__('OWNER_SECRET should never be displayed')
        self.code = code
        self.fields = [{'issues': [{'code':'REGION_SOURCE_NOT_ADMITTED', 'field':'$.presentation.sceneOverrides.privateScene.sourceRegionId', 'message':'TOKEN_SECRET'},
                                  {'code':'TOKEN_SECRET', 'field':'/private/OWNER_SECRET'}],
                        'blockedSceneIds':['privateScene'], 'headers':{'Authorization':'TOKEN_SECRET'}}]

class ProbeController:
    def __init__(self): self.error = Up2Error(); self.calls = 0; self.seen = None
    def preflight(self, value):
        self.calls += 1
        def normalize(_):
            if self.error: raise self.error
            return {'valid':True, 'ready':True, 'totalFrames':300}
        try: return helpers['_normal_with_up2_diagnostic'](normalize, value)
        except Exception as error:
            self.seen = error
            raise
    submit = preflight

class DetailBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        owner = root / 'owner.txt'; owner.write_text('synthetic-owner-for-new-tests'); owner.chmod(0o600)
        self.controller = ProbeController()
        config = original.StudioConfig(root/'private', owner, 'http://127.0.0.1:18081', root/'exports', host='127.0.0.1', port=18081, local_test_only=True)
        self.normal = original.StudioApplication(config, self.controller)
        self.token = self.normal.sessions.login('synthetic-owner-for-new-tests'); self.csrf = self.normal.token_csrf(self.token)
        app = proxy_ns['Application'].__new__(proxy_ns['Application'])
        app.normal = self.normal; app.core = SimpleNamespace(lock=threading.RLock(), public_origin=config.public_origin)
        example = root/'example.json'; example.write_text('{}')
        handler = mobile.wrap_handler(app.handler(), example_file=example, expected_example_sha256=hashlib.sha256(b'{}').hexdigest())
        class Capture(handler):
            def _headers(self, status, content_type, length, extra=()):
                self.status = status
        self.handler = Capture.__new__(Capture)
        self.value = {'prompt':{'data':{'scenes':[{'sceneId':'privateScene'}]}}}
    def tearDown(self): self.temp.cleanup()
    def call(self, path='/api/preflight', *, auth=True, csrf=True, origin='http://127.0.0.1:18081'):
        h = self.handler; h.command='POST'; h.path=path; h.client_address=('127.0.0.1',12345)
        raw=json.dumps(self.value).encode(); h.rfile=io.BytesIO(raw); h.wfile=io.BytesIO(); h._parsed_body=None
        h.headers=Message()
        for k,v in {'Host':'127.0.0.1:18081','Origin':origin,'Content-Type':'application/json','Content-Length':str(len(raw))}.items(): h.headers[k]=v
        if auth: h.headers['Cookie']='world_studio_session='+self.token
        if csrf: h.headers['X-Studio-CSRF']=self.csrf
        output=io.StringIO()
        with redirect_stdout(output): h._handle()
        return h.status,json.loads(h.wfile.getvalue()),output.getvalue()
    def test_422_preflight_and_submit_retain_safe_fields_and_original_exception(self):
        for path in ('/api/preflight','/api/submissions'):
            status,body,logs=self.call(path)
            self.assertEqual(status,422); self.assertIs(self.controller.seen,self.controller.error)
            self.assertFalse(body['renderAllowed']); self.assertEqual(body['error']['code'],CODE)
            self.assertEqual(body['error']['fields']['blockedSceneIds'],['scene[0]'])
            self.assertEqual(body['error']['fields']['issues'][0],{'code':'REGION_SOURCE_NOT_ADMITTED','field':'$.presentation.sceneOverrides[0].sourceRegionId'})
            self.assertEqual(body['error']['fields'],json.loads(logs)['fields'])
            self.assertNotRegex(json.dumps(body)+logs,r'OWNER_SECRET|TOKEN_SECRET|privateScene|/private/')
    def test_auth_csrf_and_origin_failures_never_expose_details(self):
        for kwargs,status in [({'auth':False},401),({'csrf':False},403),({'origin':'https://foreign.example'},403)]:
            actual,body,_=self.call(**kwargs)
            self.assertEqual(actual,status); self.assertNotIn('diagnostic',body['error']); self.assertNotIn('fields',body['error'])
        self.assertEqual(self.controller.calls,0)
    def test_prior_detail_cannot_leak_into_later_denied_or_unrelated_request(self):
        self.call();status,body,_=self.call(auth=False)
        self.assertEqual(status,401);self.assertNotIn('fields',body['error'])
        self.controller.error=Up2Error('UNRELATED_FAILURE');status,body,logs=self.call()
        self.assertEqual(status,422);self.assertEqual(body['error'],{'code':'UNRELATED_FAILURE'});self.assertEqual(logs,'')
    def test_normal_response_unchanged(self):
        self.controller.error=None;status,body,logs=self.call()
        self.assertEqual(status,200);self.assertEqual(body,{'valid':True,'ready':True,'totalFrames':300});self.assertEqual(logs,'')
    def test_logging_failure_does_not_erase_response_snapshot_or_original_error(self):
        with patch.dict(helpers,{'print':lambda *a,**k: (_ for _ in ()).throw(OSError('synthetic sink failure'))}):
            status,body,_=self.call()
        self.assertEqual(status,422);self.assertIs(self.controller.seen,self.controller.error)
        self.assertEqual(body['error']['fields']['blockedSceneIds'],['scene[0]'])
    def test_raw_exception_without_snapshot_keeps_old_error_only_response(self):
        error=Up2Error()
        def raw_failure(_): raise error
        self.controller.preflight=raw_failure
        status,body,_=self.call()
        self.assertEqual(status,422);self.assertEqual(body,{'error':{'code':CODE},'renderAllowed':False})

if __name__=='__main__': unittest.main(verbosity=2)
