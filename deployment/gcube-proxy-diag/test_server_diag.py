"""Real HTTP owner gateway; diagnostic rejection never admits rendering."""
import http.client
import json
from pathlib import Path
import secrets
import socket
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
        status, fields, body = self.request('GET', '/')
        self.assertEqual(status, 200); self.assertIn('text/html', fields['Content-Type'])
        self.assertIn(b'/auth/login', body)
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
        self.assertEqual(self.request('GET','/diag.json?token=do-not-log')[0],401)

    def test_read_only_queries_are_ignored_and_never_authenticate(self):
        sentinel = secrets.token_hex(24)
        for path in ('/', '/auth/login'):
            status, fields, body = self.request('GET', path+'?password='+sentinel+'&next=https://attacker.example')
            self.assertEqual(status, 200); self.assertNotIn('Set-Cookie', fields)
            self.assertNotIn(sentinel.encode(), body)
            self.assertEqual(self.records[-1]['target']['status'], 'PASS')
        self.assertIsNone(self.app.origin)
        self.assertEqual(self.request('GET', '/diag.json?token='+sentinel)[0], 401)
        self.login()
        status, _, body = self.request('GET', '/diag.json?token='+sentinel)
        self.assertEqual(status, 200); self.assertTrue(json.loads(body)['target']['query_present'])
        self.assertNotIn(sentinel, json.dumps(self.records)); self.assertNotIn(sentinel.encode(), body)
        status, fields, body = self.request('POST', '/auth/login?password='+sentinel, {'password':self.owner})
        self.assertEqual(status,400); self.assertNotIn('Set-Cookie',fields)
        self.assertEqual(json.loads(body)['validation']['FAILED_VALIDATION_RULE'], 'TARGET_HAS_QUERY')

    def test_absolute_target_must_match_strict_proxy_origin_and_port(self):
        self.assertEqual(self.request('GET', 'https://e.gcube.ai:24999/auth/login?probe=1')[0],200)
        self.assertIsNone(self.app.origin)
        for target, rule in (
                ('https://other.service.gcube.ai:24999/diag.json','TARGET_AUTHORITY_MISMATCH'),
                ('https://e.gcube.ai:25000/diag.json','TARGET_AUTHORITY_MISMATCH'),
                ('http://e.gcube.ai:24999/diag.json','TARGET_SCHEME_ORIGIN_MISMATCH'),
                ('https://attacker.example/diag.json','TARGET_AUTHORITY_MISMATCH'),
                ('https://secret@e.gcube.ai:24999/diag.json','TARGET_AUTHORITY_OR_USERINFO_INVALID'),
                ('//e.gcube.ai:24999/diag.json','TARGET_FORM_INVALID'),
                ('ftp://e.gcube.ai:24999/diag.json','TARGET_SCHEME_NOT_ALLOWED')):
            status, fields, body = self.request('GET',target)
            self.assertEqual(status,400); self.assertNotIn('Set-Cookie',fields)
            self.assertEqual(json.loads(body)['validation']['FAILED_VALIDATION_RULE'],rule)
            self.assertEqual(self.records[-1]['validation']['FAILED_VALIDATION_RULE'],rule)
        self.login()
        self.assertEqual(self.request('GET','https://e.gcube.ai:24999/diag.json?probe=1')[0],200)

    def test_target_rejection_still_captures_masked_proxy_failure(self):
        for path, rule in (('/diag.json#secret-fragment','TARGET_HAS_FRAGMENT'),
                           ('/'+('a'*4096),'TARGET_TOO_LONG')):
            status, fields, body = self.request('GET',path,headers={'X-Forwarded-Proto':'http',
                      'Authorization':'Bearer secret-sentinel','Cookie':'owner-secret'})
            self.assertEqual(status,400); self.assertNotIn('Set-Cookie',fields)
            report = json.loads(body)
            self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'],rule)
            self.assertEqual(report['proxy_validation']['FAILED_VALIDATION_RULE'],'X_FORWARDED_PROTO_NOT_HTTPS')
            self.assertTrue(report['headers']['Host']['present']); self.assertFalse(report['engine_ready'])
            self.assertEqual(report, self.records[-1])
            for secret in ('secret-fragment','secret-sentinel','owner-secret'):
                self.assertNotIn(secret,json.dumps(self.records)); self.assertNotIn(secret.encode(),body)

    def test_target_pass_does_not_mask_original_forwarding_rejection(self):
        status,_,body=self.request('GET','/diag.json?probe=1',headers={'X-Forwarded-Proto':'http'})
        self.assertEqual(status,403); report=json.loads(body)
        self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'],'X_FORWARDED_PROTO_NOT_HTTPS')
        self.assertTrue(report['target']['query_present']); self.assertEqual(report['target']['status'],'PASS')
        self.assertIsNone(self.app.origin)

    def test_query_post_and_proxy_failure_are_both_reported_without_auth(self):
        status, fields, body=self.request('POST','/auth/login?token=secret-query',{'password':self.owner},
                                         {'X-Forwarded-Proto':'http'})
        report=json.loads(body)
        self.assertEqual(status,400); self.assertNotIn('Set-Cookie',fields)
        self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'],'TARGET_HAS_QUERY')
        self.assertEqual(report['proxy_validation']['FAILED_VALIDATION_RULE'],'X_FORWARDED_PROTO_NOT_HTTPS')
        self.assertNotIn('secret-query',json.dumps(self.records)); self.assertIsNone(self.app.origin)

    def test_absolute_admission_is_not_run_when_proxy_context_is_rejected(self):
        status, fields, body=self.request('GET','https://e.gcube.ai:24999/diag.json',
                                         headers={'X-Forwarded-Proto':'http'})
        report=json.loads(body)
        self.assertEqual(status,403);self.assertNotIn('Set-Cookie',fields)
        self.assertEqual(report['target']['status'],'NOT_RUN')
        self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'],'X_FORWARDED_PROTO_NOT_HTTPS')

    def test_parser_exception_is_structured_and_does_not_echo_exception(self):
        with patch('target.urlsplit',side_effect=ValueError('secret-parser-input')):
            status,_,body=self.request('GET','/diag.json')
        self.assertEqual(status,400); report=json.loads(body)
        self.assertEqual(report['validation']['FAILED_VALIDATION_RULE'],'TARGET_PARSE_FAILED')
        self.assertEqual(report,self.records[-1]); self.assertNotIn(b'secret-parser-input',body)
        self.assertNotIn('secret-parser-input',json.dumps(self.records))

    def test_raw_control_and_http_parser_failure_never_echo_request_line(self):
        for target,version in ((b'/diag.json?token=secret-control\x01', b'HTTP/1.1'),
                               (b'/diag.json?token=secret-version', b'BADVERSION'),
                               (b'/diag.json?token=secret-line\tvalue', b'HTTP/1.1'),
                               (b'/diag.json?token='+b'a'*66000,b'HTTP/1.1')):
            with socket.create_connection(self.server.server_address,timeout=5) as s:
                s.sendall(b'GET '+target+b' '+version+b'\r\nHost: e.gcube.ai:24999\r\nX-Forwarded-Proto: https\r\n\r\n')
                chunks=[]
                while True:
                    try: chunk=s.recv(8192)
                    except ConnectionResetError: break
                    if not chunk:break
                    chunks.append(chunk)
            response=b''.join(chunks)
            self.assertIn(b'FAILED_VALIDATION_RULE',response)
            for secret in (b'secret-control',b'secret-version',b'secret-line',b'a'*256):
                self.assertNotIn(secret,response);self.assertNotIn(secret.decode(),json.dumps(self.records))
            self.assertTrue(self.records[-1]['validation']['FAILED_VALIDATION_RULE'].startswith('TARGET_'))

    def test_queries_never_bypass_origin_or_owner_and_no_network_fetch(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('TARGET_FETCH_FORBIDDEN')):
            self.assertEqual(self.request('GET','https://e.gcube.ai:24999/auth/login?next=https://attacker.example')[0],200)
            self.assertEqual(self.request('POST','/auth/login',{'password':'wrong'})[0],401)
            self.assertEqual(self.request('POST','/auth/login',{'password':self.owner},
                {'Origin':'https://attacker.example'})[0],403)
        self.assertIsNone(self.app.origin)

    def test_unsafe_absolute_post_never_reads_password_body_or_binds_origin(self):
        status, fields, body = self.request('POST','http://e.gcube.ai:24999/auth/login',{'password':self.owner})
        self.assertEqual(status,400); self.assertNotIn('Set-Cookie',fields)
        self.assertEqual(json.loads(body)['validation']['FAILED_VALIDATION_RULE'],'TARGET_SCHEME_ORIGIN_MISMATCH')
        self.assertIsNone(self.app.origin)

    def test_query_is_not_decoded_and_unknown_path_cannot_become_login(self):
        for path in ('/%61uth/login?probe=1','/%3Fprobe=1','/diag.json/../auth/login?probe=1'):
            status, fields, body=self.request('GET',path)
            self.assertNotEqual(status,200); self.assertNotIn('Set-Cookie',fields)
        self.assertIsNone(self.app.origin)

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
