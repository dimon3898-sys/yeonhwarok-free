"""Standalone HTTP/auth persistence fixture; does not admit GPU rendering."""
import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from deployment.gcube.server import BoundedHTTPServer,GcubeApplication,GcubeHandler

def run():
    with tempfile.TemporaryDirectory(prefix='gateway-only-') as folder:
        root=Path(folder);code=secrets.token_urlsafe(32);access=root/'owner.txt';access.write_text(code);access.chmod(0o600)
        app=GcubeApplication(root/'runtime','http://127.0.0.1:8001',access,disk_floor=0)
        server=BoundedHTTPServer(('0.0.0.0',8000),GcubeHandler,app);app.public_port=8000
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='https://pipeline-smoke.service.gcube.ai:24999'
        def call(method,path,body=None,extra=None):
            # The verified upstream profile requires a globally routable first
            # address. TEST-NET documentation IPs deliberately are not global.
            # This fixture address is a header only, never a network destination.
            headers={'Host':origin[8:],'X-Forwarded-Proto':'http','X-Forwarded-For':'8.8.8.8, 10.0.0.2','X-Envoy-External-Address':'10.0.0.2'}
            if method=='POST':headers.update(Origin=origin,**{'Content-Type':'application/json'})
            headers.update(extra or {})
            connection=http.client.HTTPConnection('127.0.0.1',8000,timeout=5)
            connection.request(method,path,json.dumps(body) if body is not None else None,headers)
            response=connection.getresponse();result=(response.status,dict(response.getheaders()),response.read());connection.close();return result
        try:
            assert call('GET','/api/health')[0]==200
            assert call('GET','/api/projects')[0]==401
            assert call('POST','/auth/login',{'password':'wrong'})[0]==401
            status,headers,_=call('POST','/auth/login',{'password':code});assert status==200
            cookie=headers['Set-Cookie'];assert all(value in cookie for value in ['Secure','HttpOnly','SameSite=Strict'])
            cookie=cookie.split(';',1)[0]
            assert call('GET','/api/projects',extra={'Cookie':cookie})[0]==200
            assert call('POST','/auth/logout',{},extra={'Cookie':cookie,'Origin':'https://forged.example'})[0]==403
            until=time.monotonic()+61
            while time.monotonic()<until:
                assert thread.is_alive() and call('GET','/api/health')[0]==200
                time.sleep(min(3,max(0,until-time.monotonic())))
            return dict(passed=True,bind='0.0.0.0:8000',login='PASS',secure_cookie='PASS',forged_origin='BLOCKED',server_persistence_seconds=61,gpu_ready='NOT_TESTED',scope='Gateway/auth fixture only; production ENTRYPOINT requires NVIDIA independently')
        finally:
            server.shutdown();server.server_close();thread.join(2);app.scheduler.close()

if __name__=='__main__':print(json.dumps(run()))
