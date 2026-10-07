"""Fresh diagnostic-image HTTP proof. No engine/GPU/frame/render requests."""
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time

engine = Path(__file__).resolve().parents[2] / 'world-simulation-shorts-engine'
sys.path.insert(0, str(engine))
from deployment.gcube.container_proxy_smoke import LOOPBACK_RELAY


def main():
    env_file, name = Path(sys.argv[1]), sys.argv[2]
    owner = next(line.partition('=')[2] for line in env_file.read_text().splitlines()
                 if line.startswith('WORLD_ENGINE_OWNER_CODE='))
    cookie = None
    base = {'Host':'localhost:8000', 'X-Forwarded-Host':'e.gcube.ai:24999',
            'X-Forwarded-Proto':'https', 'X-Forwarded-Port':'24999',
            'X-Forwarded-For':'203.0.113.8, 10.42.0.2',
            'X-Envoy-External-Address':'203.0.113.8'}
    subprocess.run(['docker','exec','--detach',name,'python','-c',LOOPBACK_RELAY],check=True)

    def call(method, path, body=None, changes=None, direct=False):
        headers = dict(base)
        if method=='POST': headers['Origin']='https://e.gcube.ai:24999'
        if cookie: headers['Cookie']=cookie
        headers.update(changes or {})
        data=json.dumps(body).encode() if body is not None else None
        if data is not None: headers['Content-Type']='application/json'
        connection=http.client.HTTPConnection('127.0.0.1',18012 if direct else 18010,timeout=5)
        connection.request(method,path,body=data,headers=headers)
        response=connection.getresponse(); result=response.status,dict(response.getheaders()),response.read()
        connection.close()
        assert owner.encode() not in result[2]
        assert b'203.0.113.8' not in result[2]
        assert 'Access-Control-Allow-Origin' not in result[1]
        return result

    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        try:
            status,_,body=call('GET','/healthz')
            if status==200 and json.loads(body).get('diagnostic_mode')=='PROXY_ONLY': break
        except (OSError,http.client.HTTPException,ValueError): pass
        time.sleep(.5)
    else: raise AssertionError('DIAGNOSTIC_CONTAINER_NOT_LIVE')
    live_at=time.monotonic()
    assert json.loads(body)['engine_ready'] is False
    assert json.loads(body)['gpu']=='NOT_RUN'
    assert call('GET','/readyz')[0]==503
    assert call('GET','/diag.json')[0]==401
    for password in (None,'wrong'):
        assert call('POST','/auth/login',{'password':password})[0]==401
    status,fields,body=call('POST','/auth/login',{'password':owner})
    assert status==200 and json.loads(body)['authenticated'] is True
    cookie=fields['Set-Cookie'].split(';',1)[0]
    assert all(value in fields['Set-Cookie'] for value in ('Secure','HttpOnly','SameSite=Strict'))
    status,_,body=call('GET','/diag.json')
    report=json.loads(body)
    assert status==200 and report['validation']['status']=='PASS'
    assert report['headers']['X-Forwarded-For']['values'][0]['entry_count']==2
    assert report['engine_ready'] is False and report['rendering']=='DISABLED'
    assert call('GET','/')[0]==200
    attacks=[({'X-Forwarded-Proto':'http'},'X_FORWARDED_PROTO_NOT_HTTPS'),
             ({'X-Forwarded-Proto':'https, http'},'SINGLE_HEADER_WHITESPACE_OR_COMMA'),
             ({'X-Forwarded-For':'203.0.113.8:54321'},'IP_NODE_FORMAT'),
             ({'X-Forwarded-Port':'25000'},'X_FORWARDED_PORT_AUTHORITY_DISAGREE'),
             ({'Origin':'https://attacker.example'},'ORIGIN_EFFECTIVE_OR_BOUND_AUTHORITY_MISMATCH')]
    for changes,rule in attacks:
        status,_,body=call('POST','/auth/login',{'password':owner},changes)
        assert status==403 and json.loads(body)['validation']['FAILED_VALIDATION_RULE']==rule
    status,_,body=call('GET','/diag.json',direct=True)
    assert status==403 and json.loads(body)['validation']['FAILED_VALIDATION_RULE']=='FORWARDED_PEER_NOT_TRUSTED'
    for route in ('/api/projects','/gcube/gpu.json','/api/projects/project_test/render'):
        assert call('GET',route)[0]==405
    subprocess.run(['docker','exec',name,'python','-c',
        "from pathlib import Path; assert any(r.split()[1]=='00000000:1F40' and r.split()[3]=='0A' for r in Path('/proc/net/tcp').read_text().splitlines()[1:])"],check=True)
    while time.monotonic()-live_at<61:
        assert subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',name],text=True).strip()=='true'
        assert call('GET','/auth/session')[0]==200
        time.sleep(min(2,max(.01,61-(time.monotonic()-live_at))))
    print(json.dumps({'diagnostic_image_http':'PASS','bind':'0.0.0.0:8000','owner_login':'PASS',
        'strict_proxy_rejection':'PASS','untrusted_bridge_peer_rejected':True,
        'gpu':'NOT_RUN','render_requested':False,'server_alive_seconds':round(time.monotonic()-live_at,3)}))


if __name__=='__main__': main()
