"""Offline, fail-closed, bounded diagnostic exporter; does not modify capture runtime."""
import hashlib, json, os, re, time
from pathlib import Path

ALLOWED_STAGES = {'RENDER_RUNTIME','APPROVAL_OR_INPUT','SOURCE_OR_SCENE','RUNTIME_PERMISSIONS','GPU_NATIVE_DRAW','ENCODING_OR_DECODE','DEADLINE'}
CODE = re.compile(r'^[A-Z][A-Z0-9_]{2,120}$')

def safe_code(value):
    return value if isinstance(value,str) and CODE.fullmatch(value) else None

def read_json_safe(path):
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            return None
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None

def export_failure(job_root, destination, *, deadline_seconds=5):
    """Read only bounded, allowlisted fields; create a new exclusive output folder."""
    start=time.monotonic()
    job=Path(job_root); dest=Path(destination)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError('DIAGNOSTIC_DESTINATION_EXISTS')
    first=read_json_safe(job/'capture'/'FIRST_CAPTURE_FAILURE.json')
    supervisor=read_json_safe(job/'LEASE_SUPERVISOR_RESULT.json')
    receipt=read_json_safe(job/'capture'/'CAPTURE_RECEIPT.json')
    code=safe_code(first.get('code')) if isinstance(first,dict) else None
    stage=first.get('stage') if isinstance(first,dict) and first.get('stage') in ALLOWED_STAGES else None
    reason=safe_code(supervisor.get('reason')) if isinstance(supervisor,dict) else None
    cleanup=supervisor.get('cleanupVerified') if isinstance(supervisor,dict) else None
    cleanup=cleanup if type(cleanup) is bool else None
    capture_code=None
    if isinstance(receipt,dict) and isinstance(receipt.get('failure'),dict):
        capture_code=safe_code(receipt['failure'].get('code'))
    payload={'schema':'WORLD_ENGINE_CAPTURE_DIAGNOSTIC_SAFE_V1','firstFailure':{'code':code,'stage':stage},'supervisor':{'reason':reason,'cleanupVerified':cleanup},'capture':{'code':capture_code},'missingEvidence':{'first':first is None,'supervisor':supervisor is None,'capture':receipt is None}}
    if time.monotonic()-start >= deadline_seconds:
        raise TimeoutError('DIAGNOSTIC_DEADLINE_EXCEEDED')
    dest.mkdir(mode=0o700,parents=False,exist_ok=False)
    content=(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode()
    target=dest/'CAPTURE_DIAGNOSTIC.json'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(content);f.flush();os.fsync(f.fileno())
    digest=hashlib.sha256(content).hexdigest()
    (dest/'SHA256SUMS').write_text(f'{digest}  CAPTURE_DIAGNOSTIC.json\n')
    return {'sha256':digest,'diagnostic':payload}
