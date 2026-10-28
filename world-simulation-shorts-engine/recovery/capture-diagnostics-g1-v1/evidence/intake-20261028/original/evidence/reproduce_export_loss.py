"""Forensic CPU-only reproduction against an unchanged, blob-verified exporter.
These results demonstrate diagnostic information loss, not the GPU root cause.
"""
from pathlib import Path
import hashlib, importlib.util, json, os, tempfile

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'safe_capture_export.baseline.py'
b=SOURCE.read_bytes()
blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
assert blob=='6950a1b77a85c9edf49b2fd7c8c9675d1effbed3'
spec=importlib.util.spec_from_file_location('verified_baseline_exporter',SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def put(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')
    os.chmod(path,0o600)

cases=[
    ('known_code','GCUBE_NATIVE_DRAW_FAILED','GCUBE_NATIVE_DRAW_FAILED','UNCLASSIFIED'),
    ('wrapped_known_code','page.evaluate: Error: GCUBE_NATIVE_DRAW_FAILED',None,'PAGE_EVALUATION'),
    ('wrapped_unknown_exception','page.evaluate: TypeError: synthetic test exception',None,'PAGE_EVALUATION'),
    ('native_guard_code_not_allowlisted','GCUBE_ACTUAL_NATIVE_RUNTIME_REQUIRED',None,'UNCLASSIFIED'),
]
results=[]
with tempfile.TemporaryDirectory(prefix='we-forensic-',dir='/mnt/data') as tmp:
    root=Path(tmp)
    for name,message,expected_code,expected_category in cases:
        job=root/name; (job/'capture').mkdir(parents=True,mode=0o700)
        put(job/'LEASE_SUPERVISOR_RESULT.json',{'cleanupVerified':True,'reason':'GCUBE_CAPTURE_RUNTIME_FAILED'})
        put(job/'FIRST_CAPTURE_FAILURE.json',{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME'})
        put(job/'capture'/'CAPTURE_RECEIPT.json',{
            'failure':{'code':message,'diagnosticStage':'PAGE_EVALUATE_FIRST_NATIVE_DRAW'},
            'renderedFrames':0,'nvidiaVerified':False})
        out=module.export_failure(job,root/(name+'-export'))['diagnostic']
        assert out['capture']['code']==expected_code
        assert out['capture']['messageCategory']==expected_category
        assert out['missingEvidence']['capture'] is False
        results.append({'case':name,'synthetic_input':message,'output':out,'assertion':'MATCHES_BASELINE_BEHAVIOR'})
    job=root/'missing-receipt';job.mkdir()
    put(job/'LEASE_SUPERVISOR_RESULT.json',{'cleanupVerified':True,'reason':'GCUBE_CAPTURE_RUNTIME_FAILED'})
    put(job/'FIRST_CAPTURE_FAILURE.json',{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME'})
    out=module.export_failure(job,root/'missing-export')['diagnostic']
    assert out['missingEvidence']['capture'] is True
    results.append({'case':'missing_receipt_is_distinguished','output':out,'assertion':'MATCHES_BASELINE_BEHAVIOR'})
    job=root/'cleanup-unverified';job.mkdir()
    put(job/'LEASE_SUPERVISOR_RESULT.json',{'cleanupVerified':False})
    try:
        module.export_failure(job,root/'unexpected-export')
        raise AssertionError('cleanup guard bypassed')
    except ValueError as error:
        assert str(error)=='DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED'
        results.append({'case':'cleanup_guard_preserved','error':str(error),'assertion':'MATCHES_BASELINE_BEHAVIOR'})
report={
    'status':'DIAGNOSTIC_INFORMATION_LOSS_REPRODUCED',
    'scope':'Unchanged baseline exporter with synthetic receipts; no browser, GPU, image build or deployment',
    'repository_commit':'478c6c33648e94f662673cab533bf14b74133f91',
    'source_git_blob_sha':blob,
    'source_sha256':hashlib.sha256(b).hexdigest(),
    'cases':results,
    'gpu_root_cause':'NOT_ESTABLISHED',
    'diagnostic_fix_implemented':False,
    'tests_reexecuted_from_existing_PASS_suite':False,
}
(HERE/'diagnostic_loss_reproduction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'cases':len(results),'gpu_root_cause':report['gpu_root_cause'],'source_blob_verified':True},ensure_ascii=False))
