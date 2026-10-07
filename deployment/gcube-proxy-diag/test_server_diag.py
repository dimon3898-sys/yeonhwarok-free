"""Real HTTP owner gateway; diagnostic rejection never admits rendering."""
import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from unittest.mock import patch
from server_diag import Application, Server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.owner = secrets.token_urlsafe(32)
        self.temp = tempfile.TemporaryDirectory()
        self.records = []
        self.app = Application(self.owner, Path(self.temp.name)/'private', record=self.records.append)
        self.server = Server(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.cookie = None

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2); self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        values = {'Host':'e.gcube.ai:24999', 'X-Forwarded-Proto':'https',
                  'X-Forwarded-For':'203.0.113.8, 10.42.0.2', 'Origin':'https://e.gcube.ai:24999'}
        if self.cookie: values['Cookie'] = self.cookie
        values.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        if data is not None: values['Content-Type']='application/json'
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        connection.request(method,path,body=data,headers=values)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        self.assertNotIn('Access-Control-Allow-Origin',result[1])
        self.assertNotIn(self.owner.encode(),result[2])
        self.assertNotIn(b'203.0.113.8',result[2]); self.assertNotIn(b'10.42.0.2',result[2])
        return result

    def login(self):
        status, values, body = self.request('POST','/auth/login',{'password':self.owner})
        self.assertEqual(status,200); self.assertTrue(json.loads(body)['authenticated'])
        self.assertTrue(all(flag in values['Set-Cookie'] for flag in ('Secure','HttpOnly','SameSite=Strict')))
        self.cookie = values['Set-Cookie'].split(';',1)[0]

    def test_owner_missing_wrong_correct_and_read_only_routes(self):
        self.assertEqual(self.request('GET','/diag.json')[0],401)
        for owner in (None, 'wrong'):
            self.assertEqual(self.request('POST','/auth/login',{'password':owner})[0],401)
        self.assertIsNone(self.app.origin)
        self.login()
        status, _, body = self.request('GET','/diag.json')
        self.assertEqual(status,200); report=json.loads(body)
        self.assertEqual(report['validation']['status'],'PASS')
        self.assertFalse(report['engine_ready']); self.assertEqual(report['gpu'],'NOT_RUN')
        self.assertEqual(self.app.origin,'https://e.gcube.ai:24999')
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertEqual(self.request('GET','/auth/session')[0],200)

    def test_invalid_headers_preserve_403_even_with_correct_owner(self):
        status, values, body = self.request('POST','/auth/login',{'password':self.owner},
                                         {'X-Forwarded-Proto':'http', 'Authorization':'Bearer secret-sentinel'})
        self.assertEqual(status,403); self.assertNotIn('Set-Cookie',values)
        self.assertIsNone(self.app.origin)
        self.assertEqual(json.loads(body)['validation']['FAILED_VALIDATION_RULE'],'X_FORWARDED_PROTO_NOT_HTTPS')
        self.assertNotIn('secret-sentinel', json.dumps(self.records))
        self.assertNotIn(self.owner, json.dumps(self.records))

    def test_bad_proxy_mobile_page_contains_safe_copy_and_cost_warning(self):
        status, values, body = self.request('GET','/',headers={'X-Forwarded-Proto':'http'})
        self.assertEqual(status,403); self.assertIn('text/html',values['Content-Type'])
        text=body.decode(); self.assertIn('FAILED_VALIDATION_RULE',text)
        self.assertIn('진단 결과 복사',text); self.assertIn('Workload를 중지',text)
        self.assertIn('frame-ancestors',values['Content-Security-Policy'])

    def test_external_origin_and_host_still_rejected(self):
        for attack, expected in [({'Origin':'https://attacker.example'},403),
                                 ({'Host':'attacker.example'},400),
                                 ({'X-Forwarded-Host':'attacker.example'},400)]:
            self.assertEqual(self.request('POST','/auth/login',{'password':self.owner},attack)[0],expected)

    def test_all_engine_and_gpu_and_mutation_routes_unavailable(self):
        self.login()
        for path in ('/api/projects','/api/gcube/gpu','/gcube/gpu','/api/projects/project_test/render',
                     '/api/projects/project_test/approve','/api/projects/project_test/resume',
                     '/api/projects/project_test/revise','/api/assets','/auth/logout'):
            for method in ('GET','POST','PUT','DELETE'):
                with self.subTest(path=path,method=method):
                    self.assertEqual(self.request(method,path,{} if method=='POST' else None)[0],405)

    def test_health_live_but_never_engine_ready(self):
        status,_,body=self.request('GET','/healthz',headers={'Host':'localhost:8000','X-Forwarded-Proto':'http'})
        self.assertEqual(status,200); report=json.loads(body)
        self.assertFalse(report['engine_ready']); self.assertEqual(report['rendering'],'DISABLED')
        self.assertEqual(self.request('GET','/readyz')[0],503)
        self.assertEqual(self.request('GET','/diag.json?token=do-not-log')[0],400)

    def test_no_gpu_probe_or_subprocess_on_login_or_diagnostics(self):
        with patch('subprocess.run', side_effect=AssertionError('GPU_OR_RENDER_NOT_ALLOWED')), \
             patch('subprocess.Popen', side_effect=AssertionError('GPU_OR_RENDER_NOT_ALLOWED')):
            self.login(); self.assertEqual(self.request('GET','/diag.json')[0],200)
            self.assertEqual(self.request('GET','/',headers={'X-Forwarded-Proto':'http'})[0],403)

    def test_secret_required_and_no_existing_path_overwrite(self):
        with self.assertRaisesRegex(RuntimeError,'WORLD_ENGINE_OWNER_CODE_REQUIRED'):
            Application('short',Path(self.temp.name)/'other')
        with self.assertRaises(FileExistsError): Application(self.owner,Path(self.temp.name)/'private')


if __name__=='__main__': unittest.main()
