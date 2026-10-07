import http.client,json,secrets,subprocess,tempfile,threading,unittest,zipfile
from pathlib import Path
from engine.gpu_bundle import DiagnosticBundle
from engine.storage import ProjectStore
from tests.test_gpu_bundle import make_plan,JID,ROOT
from deployment.gcube.server import BoundedHTTPServer,GcubeApplication,GcubeHandler
class MobileBundleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.code=secrets.token_urlsafe(32);access=self.root/'owner.txt';access.write_text(self.code);access.chmod(0o600)
  self.app=GcubeApplication(self.root/'runtime','http://127.0.0.1:8001',access,disk_floor=0)
  self.server=BoundedHTTPServer(('127.0.0.1',0),GcubeHandler,self.app);self.app.public_port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.origin='https://android-bundle.service.gcube.ai:24999';p=make_plan();created=self.app.store.create(p['request'],p);self.pid=created['project']['id'];version=self.app.store.version_path(self.pid,'v001');p=self.app.store.get(self.pid)['plan']
  self.bundle=DiagnosticBundle(version,JID,p);self.zip=self.bundle.finish(status='FAILED',error={'code':'FRAME_AUDIT_FAILED','scene_id':'S002','failed_stage':'scene_start','subprocess':{'return_code':1,'root_cause':{'code':'FRAME_AUDIT_FAILED','frame_index':0,'failed_invariants':['WEBGL_ERROR']}}})
  self.app.store.set_status(self.pid,'v001',status='failed',job_id=JID,error={'code':'SCENE_RENDERER_EXIT','scene_id':'S002','failed_stage':'scene_start','diagnostics':{'return_code':1,'root_cause':{'code':'FRAME_AUDIT_FAILED','frame_index':0,'failed_invariants':['WEBGL_ERROR']}}})
  self.relative=self.zip.relative_to(version).as_posix();self.path=f'/download/{self.pid}/v001/{self.relative}'
  self.addCleanup(self.close)
 def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2);self.app.scheduler.close()
 def call(self,method,path,body=None,extra=None):
  headers={'Host':self.origin[8:],'X-Forwarded-Proto':'http','X-Forwarded-For':'8.8.8.8, 10.0.0.2','X-Envoy-External-Address':'10.0.0.2'}
  if method=='POST':headers.update(Origin=self.origin,**{'Content-Type':'application/json'})
  headers.update(extra or {});c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10);c.request(method,path,json.dumps(body) if body is not None else None,headers);r=c.getresponse();result=(r.status,dict(r.getheaders()),r.read());c.close();return result
 def login(self):
  status,headers,_=self.call('POST','/auth/login',{'password':self.code});self.assertEqual(status,200);self.assertIn('Secure',headers['Set-Cookie']);return headers['Set-Cookie'].split(';',1)[0]
 def test_failed_status_lists_diagnostic_download(self):
  cookie=self.login();s,_,body=self.call('GET',f'/api/projects/{self.pid}/status',extra={'Cookie':cookie});self.assertEqual(s,200);state=json.loads(body);self.assertEqual(state['status'],'failed');self.assertTrue(any(o.get('diagnostic') for o in state['outputs']))
 def test_authenticated_zip_get_head_and_range(self):
  cookie=self.login();s,h,b=self.call('GET',self.path,extra={'Cookie':cookie});self.assertEqual(s,200);self.assertEqual(b,self.zip.read_bytes());self.assertIn('attachment',h['Content-Disposition']);self.assertEqual(h['Content-Type'],'application/zip')
  s,_,b=self.call('HEAD',self.path,extra={'Cookie':cookie});self.assertEqual(s,200);self.assertEqual(b,b'')
  s,_,b=self.call('GET',self.path,extra={'Cookie':cookie,'Range':'bytes=0-15'});self.assertEqual(s,206);self.assertEqual(len(b),16)
 def test_wrong_owner_and_unauthenticated_download_blocked(self):
  self.assertEqual(self.call('POST','/auth/login',{'password':'not-owner'})[0],401);self.assertEqual(self.call('GET',self.path)[0],401)
 def test_forged_origin_and_path_traversal_blocked(self):
  cookie=self.login();self.assertEqual(self.call('GET',self.path,extra={'Cookie':cookie,'Origin':'https://forged.example'})[0],403)
  self.assertGreaterEqual(self.call('GET',f'/download/{self.pid}/v001/diagnostics/../../status.json',extra={'Cookie':cookie})[0],400)
 def test_mobile_polling_waits_until_failure_zip_becomes_available(self):
  import os,time
  self.delayed=True;cancel=threading.Event()
  hold=self.zip.with_suffix('.hold');os.replace(self.zip,hold);self.app.store.set_status(self.pid,'v001',status='failed',diagnostic_pending=True)
  def publish():
   while not (self.root/'mobile-page-ready').exists():
    if cancel.wait(.05):return
   time.sleep(1);os.replace(hold,self.zip);self.app.store.set_status(self.pid,'v001',status='failed',diagnostic_pending=False)
  thread=threading.Thread(target=publish,daemon=True);thread.start()
  try:self.test_android_emulated_failed_screen_downloads_valid_zip()
  finally:cancel.set();thread.join(10)
 def test_android_emulated_failed_screen_downloads_valid_zip(self):
  cert=self.root/'cert.pem';key=self.root/'key.pem'
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=android-bundle.service.gcube.ai'],check=True,capture_output=True)
  p=subprocess.run(['node',str(ROOT/'tests/gpu_bundle_mobile.mjs')],cwd=ROOT,input=json.dumps({'port':self.server.server_port,'code':self.code,'pid':self.pid,'origin':self.origin,'filename':self.zip.name,'folder':str(self.root),'cert':str(cert),'key':str(key),'pending':getattr(self,'delayed',False)}),capture_output=True,text=True,timeout=60)
  self.assertEqual(p.returncode,0,p.stderr[-2000:]);report=json.loads(p.stdout);self.assertTrue(report['passed']);self.assertEqual(report['gpu_draw'],'NOT_RUN');self.assertTrue(zipfile.is_zipfile(self.root/self.zip.name))
if __name__=='__main__':unittest.main()
