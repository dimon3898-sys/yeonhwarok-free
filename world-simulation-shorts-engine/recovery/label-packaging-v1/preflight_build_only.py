#!/usr/bin/env python3
"""Build-only preflight, fail closed before parent pull. No image build or registry write."""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,sys,urllib.request,urllib.parse
PARENT="sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da"
MAX_ATTESTATION=64*1024
MAX_MANIFEST=1024*1024
def need(x,s):
    if not x: raise RuntimeError(s)
def document(raw,code):
    def pairs(items):
        value={}
        for key,item in items:
            need(key not in value,code);value[key]=item
        return value
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,code))
    except (ValueError,UnicodeError): raise RuntimeError(code) from None
    need(isinstance(value,dict),code)
    return value
def local_docker_info():
    environ=dict(os.environ)
    for key in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']:
        environ.pop(key,None)
    try:
        raw=subprocess.check_output(['docker','--host=unix:///var/run/docker.sock','info','--format','{{json .}}'],text=True,stderr=subprocess.STDOUT,env=environ)
    except (PermissionError,subprocess.CalledProcessError): raise RuntimeError('DOCKER_ACCESS_DENIED') from None
    except OSError: raise RuntimeError('DOCKER_ACCESS_UNAVAILABLE') from None
    info=document(raw,'DOCKER_INFO_INVALID')
    driver=info.get('Driver')
    need(driver in ['vfs','overlay2','overlayfs','fuse-overlayfs'],'DOCKER_STORAGE_DRIVER_UNSUPPORTED')
    root=pathlib.Path(info.get('DockerRootDir',''))
    need(root.is_absolute() and '..' not in root.parts and not root.is_symlink() and root.is_dir(),'DOCKER_DATA_ROOT_INVALID')
    return root,driver
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--billing-attestation",required=True);a=p.parse_args()
    output=pathlib.Path(a.out)
    need(output.is_absolute() and '..' not in output.parts
         and not any(node.is_symlink() for node in (output,*output.parents))
         and output.parent.is_dir() and not output.exists()
         and output!=pathlib.Path(a.billing_attestation).resolve(strict=False),
         'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED')
    need(os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RETRY_FORBIDDEN")
    need(os.environ.get("GITHUB_REPOSITORY")=="dimon3898-sys/yeonhwarok-free","REPO_MISMATCH")
    try:
        file=pathlib.Path(a.billing_attestation)
        need(file.is_file() and not file.is_symlink(),'LIVE_BILLING_ATTESTATION_REQUIRED')
        need(file.stat().st_size<=MAX_ATTESTATION,'BILLING_ATTESTATION_SIZE_LIMIT')
        with file.open('rb') as stream: att_raw=stream.read(MAX_ATTESTATION+1)
    except OSError: raise RuntimeError('LIVE_BILLING_ATTESTATION_REQUIRED') from None
    need(len(att_raw)<=MAX_ATTESTATION,'BILLING_ATTESTATION_SIZE_LIMIT')
    att=document(att_raw,'LIVE_BILLING_ATTESTATION_REQUIRED')
    need(att.get("accountCurrent") is True and type(att.get("actionsBudgetUSD")) is int and att["actionsBudgetUSD"]==0 and att.get("stopUsageAtLimit") is True and att.get("paymentMethodRegistered") is False,"LIVE_BILLING_ATTESTATION_REQUIRED")
    # Exact parent digest: registry manifest is read-only, before pull.
    url="https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/"+PARENT
    # Reuse successful G2 registry bearer-token flow; anonymous manifest GET may be denied.
    scope="repository:dimon3898-sys/world-simulation-shorts-engine:pull"
    token_url="https://ghcr.io/token?"+urllib.parse.urlencode({"service":"ghcr.io","scope":scope})
    try:
        with urllib.request.urlopen(token_url,timeout=45) as response: token_raw=response.read(MAX_ATTESTATION+1)
        need(len(token_raw)<=MAX_ATTESTATION,'PARENT_TOKEN_SIZE_LIMIT')
        token=document(token_raw,'PARENT_TOKEN_INVALID').get('token')
        need(isinstance(token,str) and 0<len(token)<=16384,'PARENT_TOKEN_INVALID')
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"})
        with urllib.request.urlopen(req,timeout=45) as response:
            raw=response.read(MAX_MANIFEST+1)
            returned=response.headers.get("Docker-Content-Digest")
        need(len(raw)<=MAX_MANIFEST,'PARENT_MANIFEST_SIZE_LIMIT')
    except RuntimeError: raise
    except Exception as e: raise RuntimeError("PARENT_MANIFEST_UNAVAILABLE:"+type(e).__name__)
    need(returned=="sha256:"+hashlib.sha256(raw).hexdigest(),"PARENT_REGISTRY_DIGEST_MISMATCH")
    need("sha256:"+hashlib.sha256(raw).hexdigest()==PARENT,"PARENT_DIGEST_MISMATCH")
    m=document(raw,'PARENT_MANIFEST_INVALID');need(m.get('schemaVersion')==2 and isinstance(m.get("layers"),list) and 0<len(m["layers"])<=256,"PARENT_MANIFEST_NOT_SINGLE_PLATFORM")
    sizes=[]
    for layer in m['layers']:
        need(isinstance(layer,dict) and type(layer.get('size')) is int and 0<=layer['size']<=128*1024**3,'PARENT_LAYER_INVALID')
        sizes.append(layer['size'])
    compressed=sum(sizes)
    root,driver=local_docker_info()
    try: free=shutil.disk_usage(root).free
    except OSError: raise RuntimeError('DAEMON_CAPACITY_UNAVAILABLE') from None
    need(type(free) is int and free>=0,'DAEMON_CAPACITY_UNAVAILABLE')
    # vfs copies each inherited layer prefix; use the existing conservative
    # cumulative-prefix estimate instead of undercounting it as overlay storage.
    basis=sum(size*(len(sizes)-i) for i,size in enumerate(sizes)) if driver=='vfs' else compressed
    estimate=basis*4+8*1024**3
    need(free>=estimate,"BLOCKED_DAEMON_CAPACITY")
    try:
        with output.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps({"status":"PASS","parentDigest":PARENT,"compressedLayerBytes":compressed,"freeBytes":free,"estimatedRequiredBytes":estimate,"costGate":"CURRENT_ATTESTED","scope":"BUILD_PREFLIGHT_ONLY","storageDriver":driver,"layerCount":len(sizes),"capacityEstimateBasis":"4x cumulative compressed prefixes +8GiB reserve" if driver=='vfs' else "4x compressed bytes +8GiB reserve","localDaemonEndpoint":"unix:///var/run/docker.sock"},indent=2)+"\n")
    except OSError: raise RuntimeError('PREFLIGHT_OUTPUT_UNAVAILABLE') from None
if __name__=="__main__":
    try:main()
    except Exception as e:
        code=str(e)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}(?::[A-Za-z][A-Za-z0-9_]{0,80})?',code):code='PREFLIGHT_FAILED'
        print("BLOCKED:"+code,file=sys.stderr);sys.exit(1)
