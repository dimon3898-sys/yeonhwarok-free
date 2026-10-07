"""Replay the user-confirmed v007 capture structure through all validators.

Hostname and addresses are substituted; external browser TLS/Origin was not
provided in the capture and is never inferred from upstream HTTP.
"""
from email.message import Message
import json
from pathlib import Path
import subprocess
import shutil
import unittest
from unittest.mock import patch

from deployment.gcube import proxy, test_server as gateway
from deployment.gcube.server import GcubePolicy, SECURE_LOGIN_JS
from deployment.security import SecurityError

CAPTURE = json.loads((Path(__file__).parent/'fixtures/gcube_v007_internal_http.json').read_text())
HEADERS = CAPTURE['headers']
ORIGIN = 'https://' + HEADERS['Host']
PEER = CAPTURE['trusted_peer']
NODE_TEST_BIN = shutil.which('node')


def envelope(**changes):
    h = Message()
    for name, value in {**HEADERS, **changes}.items():
        if value is None: continue
        for item in value if isinstance(value, list) else [value]: h[name] = item
    return h


class CapturedHTTPContracts(unittest.TestCase):
    def test_same_capture_all_static_stages_then_auth_preconditions(self):
        h = envelope()
        self.assertEqual(proxy.provider_origin(h['Host']), ORIGIN)
        xf_host, proto, port, xff, forwarded, envoy = proxy.parse_forwarding(h, PEER)
        self.assertEqual(proto, 'http'); self.assertEqual(len(xff), 2); self.assertTrue(envoy)
        self.assertIsNone(xf_host); self.assertIsNone(port); self.assertEqual(forwarded, [])
        origin, summary = proxy.request_envelope(h, peer_ip=PEER)
        self.assertEqual(origin, ORIGIN); self.assertEqual(summary['forwarded_proto'], 'http')
        self.assertFalse(summary['forwarded_proto_is_browser_tls_proof'])
        for bound in (None, ORIGIN):
            policy = GcubePolicy(origin=bound)
            self.assertEqual(policy.check_request(h,method='GET',peer_ip=PEER),ORIGIN)
            for verb in ('POST','PUT','PATCH','DELETE'):
                with self.assertRaises(SecurityError): policy.check_request(h,method=verb,peer_ip=PEER)
                self.assertEqual(policy.check_request(envelope(Origin=ORIGIN),method=verb,peer_ip=PEER),ORIGIN)
            for origin in ('http://'+HEADERS['Host'], 'https://attacker.example', 'null'):
                with self.assertRaises(SecurityError):
                    policy.check_request(envelope(Origin=origin),method='POST',peer_ip=PEER)

    def test_a_b_trusted_http_and_https_dynamic_ports(self):
        for port in (443,24999,31042,65535):
            host='captured-workload.service.gcube.ai'+(':'+str(port) if port!=443 else '')
            for proto in ('http','https'):
                h=envelope(Host=host, Origin='https://'+host, **{'X-Forwarded-Proto':proto})
                self.assertEqual(GcubePolicy().check_request(h,method='POST',peer_ip=PEER),'https://'+host)

    def test_c_d_e_f_g_h_i_k_attack_matrix(self):
        attacks = [
            ('untrusted_peer', {}, '10.42.99.99'),
            ('public_peer', {}, '8.8.4.4'),
            ('nongcube_host', {'Host':'attacker.example'}, PEER),
            ('legacy_nongcube_service', {'Host':'captured-workload.gcube.ai:24999'}, PEER),
            ('comma_proto', {'X-Forwarded-Proto':'http,https'}, PEER),
            ('duplicate_proto', {'X-Forwarded-Proto':['http','http']}, PEER),
            ('malformed_proto', {'X-Forwarded-Proto':'HTTP'}, PEER),
            ('malformed_proto_controls', {'X-Forwarded-Proto':'http\r\nInjected: yes'}, PEER),
            ('forged_host', {'X-Forwarded-Host':'attacker.example'}, PEER),
            ('another_gcube_host', {'X-Forwarded-Host':'another-workload.service.gcube.ai:24999'}, PEER),
            ('malformed_xff', {'X-Forwarded-For':'8.8.8.8, invalid'}, PEER),
            ('missing_xff', {'X-Forwarded-For':None}, PEER),
            ('single_xff', {'X-Forwarded-For':'8.8.8.8'}, PEER),
            ('extra_xff', {'X-Forwarded-For':'8.8.8.8, 10.42.0.2, 127.0.0.1'}, PEER),
            ('ipv6_profile_unobserved', {'X-Forwarded-For':'2001:4860:4860::8888, 10.42.0.2'}, PEER),
            ('second_xff_public', {'X-Forwarded-For':'8.8.8.8, 8.8.4.4'}, PEER),
            ('missing_envoy', {'X-Envoy-External-Address':None}, PEER),
            ('envoy_public', {'X-Envoy-External-Address':'8.8.4.4'}, PEER),
            ('forged_origin', {'Origin':'https://attacker.example'}, PEER),
            ('http_origin', {'Origin':'http://'+HEADERS['Host']}, PEER),
            ('incorrect_port', {'X-Forwarded-Port':'31042'}, PEER),
            ('conflicting_rfc_proto', {'Forwarded':'for=8.8.8.8;proto=https'}, PEER),
        ]
        for name,changes,peer in attacks:
            with self.subTest(case=name),self.assertRaises(SecurityError):
                GcubePolicy().check_request(envelope(Origin=ORIGIN,**changes) if 'Origin' not in changes else envelope(**changes),method='POST',peer_ip=peer)

    def test_private_address_is_only_trusted_when_it_is_the_exact_pod(self):
        with patch('deployment.gcube.proxy.pod_addresses',return_value=frozenset({'10.42.0.8'})):
            self.assertEqual(GcubePolicy().check_request(envelope(),peer_ip='10.42.0.8'),ORIGIN)
            with self.assertRaises(SecurityError):GcubePolicy().check_request(envelope(),peer_ip='10.42.0.9')

    def test_https_profile_and_local_development_are_preserved(self):
        for xff in ('8.8.8.8','8.8.8.8, 10.42.0.2, ::1','2001:4860:4860::8888'):
            h=envelope(**{'X-Forwarded-Proto':'https','X-Forwarded-For':xff})
            self.assertEqual(GcubePolicy().check_request(h,peer_ip=PEER),ORIGIN)
        origin='http://localhost:8000'
        local=Message();local['Host']='localhost:8000';local['Origin']=origin
        self.assertEqual(GcubePolicy(origin=origin,local_mode=True).check_request(local,method='POST',peer_ip='127.0.0.1'),origin)


class CapturedHTTPGateway(unittest.TestCase):
    setUp = gateway.GatewayTests.setUp
    tearDown = gateway.GatewayTests.tearDown
    call = gateway.GatewayTests.call

    def test_get_login_owner_session_health_and_proxy_end_to_end_without_render(self):
        h={**HEADERS,'X-Forwarded-Host':None}
        self.assertEqual(self.call('GET','/',origin=ORIGIN,headers=h)[0],303)
        status,_,body=self.call('GET','/auth/login',origin=ORIGIN,headers=h)
        self.assertEqual(status,200);self.assertIn(b'owner-login-fields" disabled',body)
        self.assertIn(b'/auth/secure-login.js',body)
        self.assertEqual(self.call('GET','/auth/secure-login.js',origin=ORIGIN,headers=h)[0],200)
        for password in (None,'wrong'):
            status,fields,_=self.call('POST','/auth/login',{'password':password},origin=ORIGIN,headers=h)
            self.assertEqual(status,401);self.assertNotIn('Set-Cookie',fields);self.assertIsNone(self.app.bound_origin)
        status,fields,_=self.call('POST','/auth/login',{'password':gateway.PASSWORD},origin=ORIGIN,headers=h)
        self.assertEqual(status,200);self.assertTrue(all(v in fields['Set-Cookie'] for v in ('Secure','HttpOnly','SameSite=Strict')))
        self.cookie=fields['Set-Cookie'].split(';',1)[0]
        self.assertEqual(self.app.bound_origin,ORIGIN)
        for path in ('/auth/session','/api/health','/api/projects','/api/gcube/proxy'):
            self.assertEqual(self.call('GET',path,origin=ORIGIN,headers=h)[0],200)
        report=json.loads(self.call('GET','/api/gcube/proxy',origin=ORIGIN,headers=h)[2])
        self.assertEqual(report['status'],'PASS');self.assertEqual(report['forwarded_proto'],'http')
        self.assertFalse(report['forwarded_proto_is_browser_tls_proof'])
        self.assertEqual(self.app.store.list(),[])

    def test_all_mutations_reject_http_missing_or_forged_origin_before_body(self):
        for path in ('/auth/login','/auth/logout','/api/projects','/api/assets',
                     '/api/projects/project_abcdef123456/approve','/api/projects/project_abcdef123456/render',
                     '/api/projects/project_abcdef123456/revise','/api/projects/project_abcdef123456/resume'):
            for origin in (None,'http://'+HEADERS['Host'],'https://attacker.example'):
                status,fields,_=self.call('POST',path,{},origin=ORIGIN,headers={**HEADERS,'Origin':origin,'X-Forwarded-Host':None})
                self.assertEqual(status,403);self.assertNotIn('Set-Cookie',fields)
        self.assertIsNone(self.app.bound_origin);self.assertEqual(self.app.store.list(),[])

    def test_browser_form_stays_disabled_on_http_and_enables_only_on_https(self):
        harness = '''
let mockForm={addEventListener:(name,fn)=>globalThis.submit=fn};
let mockFields={disabled:true};let mockNotice={hidden:false};
globalThis.document={getElementById:id=>({'owner-login-form':mockForm,'owner-login-fields':mockFields,'owner-https-required':mockNotice})[id]};
globalThis.window={location:{protocol:process.argv[1]},isSecureContext:process.argv[2]==='true'};
'''+SECURE_LOGIN_JS+'''
let prevented=false;globalThis.submit({preventDefault:()=>prevented=true});
process.stdout.write(JSON.stringify({disabled:mockFields.disabled,hidden:mockNotice.hidden,prevented}));
'''
        for proto,secure,expected in [('http:','false',True),('https:','false',True),('https:','true',False)]:
            self.assertIsNotNone(NODE_TEST_BIN, 'Node runtime is required for the browser security test')
            result=subprocess.run([NODE_TEST_BIN,'-e',harness,proto,secure],capture_output=True,text=True,check=True)
            state=json.loads(result.stdout);self.assertEqual(state['disabled'],expected);self.assertEqual(state['prevented'],expected)


if __name__=='__main__':unittest.main()
