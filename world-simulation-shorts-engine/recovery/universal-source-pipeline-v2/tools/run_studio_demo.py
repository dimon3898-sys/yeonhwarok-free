"""One real authenticated Studio software job. No G1 or historical rerender."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_source_actual_studio_service',HERE/'studio_service.py')
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)


def run(private,source_root):
    private.mkdir(mode=0o700,exist_ok=False)
    state=private/'state';state.mkdir(mode=0o700)
    owner=private/'owner-code';owner.write_text(secrets.token_urlsafe(32));owner.chmod(0o600)
    exports=HERE/'captures';exports.mkdir(mode=0o700,exist_ok=True)
    pin=hashlib.sha256((source_root/'INDEX.json').read_bytes()).hexdigest()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    options=dict(state_root=state,owner_file=owner,export_root=exports,port=port,
        image_digest='sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5',
        source_root=source_root,expected_index_sha256=pin,allow_software_source_review=True)
    app=service.local_application(**options)
    http=service.server.ThreadingHTTPServer(('127.0.0.1',port),service.server.make_handler(app))
    threading.Thread(target=http.serve_forever,daemon=True).start()
    try:
        # Reuse the original mobile browser auth/CSRF/HTTP exercise unchanged;
        # request JSON selects the new explicit family, not the G1 renderer.
        subprocess.run(['node',str(HERE.parent/'studio-integration-gates-v1/tools/mobile_client.mjs'),
            f'http://127.0.0.1:{port}',str(private),str(HERE/'fixtures/DEMO_SOURCE_SCENE.json')],check=True,timeout=180)
        mobile=json.loads((private/'MOBILE_HTTP_START.json').read_bytes());job_id=mobile['jobId']
        http.shutdown();http.server_close()
        app2=service.local_application(**options)
        after=app2.controller.start(mobile['submissionId'],'source-reconnect-new-key-20261022',consent=True)
        assert after['jobId']==job_id
        last=None
        for _ in range(190):
            status=app2.controller.status(job_id)
            key=(status['state'],status.get('processedFrames'))
            if key!=last:print(json.dumps(status),flush=True);last=key
            if status['state'] in {'COMPLETED','FAILED','INTERRUPTED'}:break
            time.sleep(5)
        report={**mobile,'finalState':status,'controllerRestartDuplicateJobId':after['jobId'],
            'httpServerStoppedDuringRender':True,'sourceIndexSHA256':pin,'sourceRoot':str(source_root),
            'classification':'SYNTHETIC_DEMO_NOT_HISTORICAL_G3','g1ReRendered':False,
            'nvidiaVerified':False,'deploymentPerformed':False,'paidGpuExecuted':False,'userApproved':False}
        (HERE/'reports/STUDIO_DEMO_EXECUTION.json').write_text(json.dumps(report,indent=2)+'\n')
        if status['state']!='COMPLETED':raise RuntimeError('SOURCE_DEMO_JOB_NOT_COMPLETED')
    finally:http.shutdown();http.server_close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--private-root',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True)
    args=p.parse_args();run(args.private_root,args.source_root)
