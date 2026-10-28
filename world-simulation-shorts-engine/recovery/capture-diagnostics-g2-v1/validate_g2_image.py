#!/usr/bin/env python3
"""Candidate-image CPU integration. Runs no old suite and never calls render.

The installed startup source verifier is executed against the NEW 353-file
closure. The real service handler is exercised with disposable private state.
ENTRYPOINT pins and admission guards are checked separately from this harness;
these checks are not a claim of GPU admission or production startup success.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

sys.dont_write_bytecode = True
REC = 'world-simulation-shorts-engine/recovery/'
NS = REC + 'codex-to-gcube-handoff-v1/'
START = REC + 'studio-cold-start-v2/'
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
SENTINEL = b'G2_PRIVATE_SENTINEL_NOT_FOR_EXPORT'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def private_json(path, value):
    write_json(path, value)
    path.chmod(0o600)


def service_routes(serve, contract, temporary):
    state = temporary / 'service-state'
    state.mkdir(mode=0o700)
    (state / 'production').mkdir(mode=0o700)
    owner = state / 'owner-code'
    owner.write_text(secrets.token_urlsafe(48))
    owner.chmod(0o600)
    exports = temporary / 'service-exports'
    exports.mkdir(mode=0o700)
    # No operational values or registered origin are read. Missing policy keeps
    # the actual application in setup mode, where production admission blocks.
    config = serve.configuration({'GPU_BACKEND':'vulkan',
        'WORLD_ENGINE_STUDIO_STATE_ROOT':str(state), 'WORLD_ENGINE_STUDIO_PORT':'8080'},
        export_root=exports, host='127.0.0.1')
    need(config['configuration_error']=='STUDIO_OPERATOR_POLICY_REQUIRED', 'G2_SETUP_MUST_BLOCK_PRODUCTION')
    app, server_type = serve.application(contract, config)
    need(app.normal is None, 'G2_SETUP_MODE_REQUIRED')
    server = server_type(('127.0.0.1', 8080), app.handler())
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':0.05}, daemon=True)
    thread.start()
    results=[]
    try:
        for route in ('/healthz','/','/login','/setup'):
            conn=http.client.HTTPConnection('127.0.0.1',8080,timeout=5)
            try:
                conn.request('GET',route,headers={'Host':'127.0.0.1:8080'})
                response=conn.getresponse()
                raw=response.read(1024*1024)
                need(response.status==200,'G2_INSTALLED_SERVICE_ROUTE_FAILED')
                kind=response.getheader('Content-Type','').split(';')[0]
                if route=='/healthz':
                    body=json.loads(raw)
                    need(body.get('serviceAlive') is True and body.get('renderAllowed') is False
                        and body.get('gpuRenderingVerified') is False,'G2_HEALTH_CONTRACT_INVALID')
                else:
                    need(kind=='text/html' and b'<html' in raw.lower(),'G2_INSTALLED_HTML_ROUTE_INVALID')
                results.append({'path':route,'status':response.status,'contentType':kind})
            finally:
                conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    return {'status':'PASS','port':8080,'mode':'SETUP','routes':results,
        'productionAdmission':'BLOCKED_MISSING_OPERATOR_POLICY', 'ownerAuthenticationTested':False,
        'gpuAdmissionTested':False,'renderStartRequested':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(ROOT))
    p.add_argument('--stage-receipt',type=Path,required=True)
    p.add_argument('--image-config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--node-deps',default=os.environ.get('WORLD_ENGINE_NODE_DEPS'))
    args=p.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    report={'schema':'WORLD_ENGINE_G2_IMAGE_VALIDATION_V1','status':'BLOCKED',
        'scope':'NEW_CANDIDATE_IMAGE_CPU_INTEGRATION','g0g1Rerun':False,
        'gpuExecuted':False,'renderedFrames':0,'gpuRootCause':'UNKNOWN','checks':{}}
    step='IDENTITY'
    try:
        need(os.getuid()==1000 and os.getgid()==1000,'G2_VALIDATION_UID_1000_REQUIRED')
        need(args.root.is_absolute() and args.root.is_dir(),'G2_INSTALLED_ROOT_REQUIRED')
        facts=json.loads(args.stage_receipt.read_bytes())
        manifest=args.root/NS/'RUNTIME_SOURCE_MANIFEST.json'
        startup=args.root/START
        step='ENTRYPOINT_CONFIG'
        cfg=json.loads(args.image_config.read_bytes())
        if isinstance(cfg,list): cfg=cfg[0]
        cfg=cfg.get('Config',cfg)
        entry=['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',
            str(startup/'bootstrap.py'),'--startup-manifest',str(startup/'STARTUP_MANIFEST.json'),
            '--startup-manifest-sha256',facts['startupManifestSHA256'],
            '--source-manifest',str(manifest),'--source-manifest-sha256',facts['runtimeManifestSHA256'],
            '--export-root','/world-storage']
        need(cfg.get('Entrypoint')==entry and cfg.get('Cmd') in (None,[]),'G2_ENTRYPOINT_PIN_CHAIN_MISMATCH')
        need(cfg.get('User') in ('0','root','0:0',''),'G2_ENTRYPOINT_ROOT_REQUIRED')
        report['checks']['entrypoint']={'status':'PASS','type':'IMAGE_CONFIG_EXACT_PIN_CONTRACT',
            'productionStartupExecuted':False,'gpuAdmissionTested':False}
        step='INSTALLED_STARTUP_AND_RUNTIME'
        boot=module('_g2_installed_bootstrap',startup/'bootstrap.py')
        boot.verify_startup(startup/'STARTUP_MANIFEST.json',facts['startupManifestSHA256'])
        need(boot.SOURCE_SHA==facts['runtimeManifestSHA256'],'G2_BOOTSTRAP_RUNTIME_PIN_MISMATCH')
        try:
            boot.container_parent()
        except RuntimeError as error:
            need(str(error)=='COLD_START_ROOT_TINI_ENTRYPOINT_REQUIRED','G2_STARTUP_ADMISSION_GUARD_CHANGED')
        else:
            raise RuntimeError('G2_STARTUP_ADMISSION_GUARD_NOT_ENFORCED')
        serve,contract=boot.source_contract(manifest,facts['runtimeManifestSHA256'])
        need(len(contract.files)==353,'G2_EXPECTED_353_RUNTIME_FILES')
        need(NS+'backend/capture_operation_diagnostics.mjs' in contract.files,'G2_DIAGNOSTIC_SOURCE_NOT_PINNED')
        report['checks']['runtimeClosure']={'status':'PASS','sourceFiles':len(contract.files),
            'runtimeManifestSHA256':facts['runtimeManifestSHA256'],
            'startupManifestSHA256':facts['startupManifestSHA256'],
            'productionVerifierExecuted':True,'bootstrapPin':'PASS','startupAdmissionGuard':'PASS'}
        with tempfile.TemporaryDirectory(prefix='world-engine-g2-') as td:
            temp=Path(td)
            temp.chmod(0o700)
            job=temp/('studio-'+'2'*32)
            job.mkdir(mode=0o700)
            (job/'capture').mkdir(mode=0o700)
            step='INSTALLED_NODE_CHROMIUM_PLAYWRIGHT'
            need(isinstance(args.node_deps,str) and Path(args.node_deps).is_absolute(),'G2_NODE_DEPS_PATH_REQUIRED')
            node=shutil.which('node')
            need(node is not None,'G2_NODE_EXECUTABLE_MISSING')
            process=subprocess.run([node,str(Path(__file__).with_name('validate_g2_browser.mjs')),
                str(args.root),str(job),args.node_deps],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=75,check=False)
            try: browser=json.loads(process.stdout)
            except (ValueError,UnicodeError): raise RuntimeError('G2_BROWSER_RESULT_INVALID') from None
            write_json(out/'IMAGE_BROWSER_PROBE.json',browser)
            need(process.returncode==0 and browser.get('status')=='PASS',browser.get('errorCode','G2_BROWSER_FAILED'))
            report['checks']['browser']=browser
            step='INSTALLED_SAFE_EXPORT'
            private_json(job/'LEASE_SUPERVISOR_RESULT.json',{'cleanupVerified':True,'reason':'HANDOFF_CAPTURE_PROCESS_FAILED'})
            private_json(job/'FIRST_CAPTURE_FAILURE.json',{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME'})
            checkpoint=json.loads((job/'capture/CAPTURE_OPERATION_CHECKPOINT.json').read_bytes())
            private_json(job/'capture/CAPTURE_RECEIPT.json',{'renderedFrames':0,'nvidiaVerified':False,
                'failure':{'code':'page.evaluate: Error: '+SENTINEL.decode(),
                    'diagnosticStage':'PAGE_EVALUATE_FIRST_NATIVE_DRAW'},'captureOperations':checkpoint})
            exports=temp/'safe-exports'
            exports.mkdir(mode=0o700)
            exporter=module('_g2_installed_post_cleanup_export',args.root/NS/'controller/capture_diagnostics_safe.py')
            result=exporter.export_after_cleanup(job,exports,(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat())
            need(result.get('status')=='EXPORTED','G2_INSTALLED_SAFE_EXPORT_FAILED')
            destination=exports/('capture-diagnostic-'+job.name)
            raw=(destination/'CAPTURE_DIAGNOSTIC.json').read_bytes()
            need(SENTINEL not in raw and b'private.invalid' not in raw,'G2_PRIVATE_VALUE_EXPORTED')
            sums=(destination/'SHA256SUMS').read_text()
            need(sums==sha(raw)+'  CAPTURE_DIAGNOSTIC.json\n','G2_SAFE_EXPORT_SHA_MISMATCH')
            safe=json.loads(raw)
            inner=safe['capture']['operations']
            need(safe['capture']['code']=='GCUBE_NATIVE_READBACK_INVALID'
                and inner['firstFailure']['operationId']=='READBACK'
                and inner['firstFailure']['sourceId']=='NATIVE_GUARD'
                and inner['lastCompletedOperation']=='INPUT_CANVAS'
                and inner['cleanupFailure']['errorCode']=='UNCLASSIFIED_EXCEPTION'
                and safe['capture']['nvidiaVerified'] is False
                and safe['capture']['renderedFrames']==0,'G2_SAFE_DIAGNOSTIC_CHAIN_FAILED')
            (out/'SAFE_CAPTURE_DIAGNOSTIC.json').write_bytes(raw)
            (out/'SAFE_CAPTURE_SHA256SUMS').write_text(sha(raw)+'  SAFE_CAPTURE_DIAGNOSTIC.json\n')
            report['checks']['safeExport']={'status':'PASS','sha256':sha(raw),'privateValueAbsent':True,
                'postCleanupExporterExecuted':True,'firstFailurePreserved':True,'cleanupFailurePreserved':True}
            step='INSTALLED_SERVICE_ROUTES'
            report['checks']['service']=service_routes(serve,contract,temp)
        report['status']='G2_IMAGE_CPU_PASS'
    except Exception as error:
        message=str(error)
        report['failedStep']=step
        known_types={'RuntimeError','AssertionError','ValueError','TypeError','KeyError','ImportError',
            'ModuleNotFoundError','FileNotFoundError','PermissionError','TimeoutError','TimeoutExpired',
            'JSONDecodeError','OSError','ConnectionRefusedError','RemoteDisconnected'}
        report['exceptionType']=type(error).__name__ if type(error).__name__ in known_types else 'UNKNOWN'
        report['errorCode']=message if re.fullmatch(r'[A-Z][A-Z0-9_]{2,120}',message) else 'G2_IMAGE_VALIDATION_FAILED'
    write_json(out/'VALIDATION_RESULT.json',report)
    allowed=['IMAGE_BROWSER_PROBE.json','SAFE_CAPTURE_DIAGNOSTIC.json','SAFE_CAPTURE_SHA256SUMS','VALIDATION_RESULT.json']
    rows=[]
    for name in allowed:
        file=out/name
        if file.exists():
            raw=file.read_bytes()
            need(SENTINEL not in raw and b'private.invalid' not in raw,'G2_EVIDENCE_SECRET_SENTINEL_FOUND')
            rows.append(sha(raw)+'  '+name)
    (out/'SHA256SUMS').write_text('\n'.join(rows)+'\n')
    print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='G2_IMAGE_CPU_PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
