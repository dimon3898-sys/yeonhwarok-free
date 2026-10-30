#!/usr/bin/env python3
"""Build-only preflight, fail closed before parent pull. No image build or registry write."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,urllib.request,urllib.parse
PARENT="sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da"
def need(x,s):
    if not x: raise RuntimeError(s)
def run(*args): return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip()
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--billing-attestation",required=True);a=p.parse_args()
    need(os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RETRY_FORBIDDEN")
    need(os.environ.get("GITHUB_REPOSITORY")=="dimon3898-sys/yeonhwarok-free","REPO_MISMATCH")
    att=json.loads(pathlib.Path(a.billing_attestation).read_text())
    need(att.get("accountCurrent") is True and att.get("actionsBudgetUSD")==0 and att.get("stopUsageAtLimit") is True and att.get("paymentMethodRegistered") is False,"LIVE_BILLING_ATTESTATION_REQUIRED")
    # Exact parent digest: registry manifest is read-only, before pull.
    url="https://ghcr.io/v2/dimon3898-sys/world-simulation-shorts-engine/manifests/"+PARENT
    # Reuse successful G2 registry bearer-token flow; anonymous manifest GET may be denied.
    scope="repository:dimon3898-sys/world-simulation-shorts-engine:pull"
    token_url="https://ghcr.io/token?"+urllib.parse.urlencode({"service":"ghcr.io","scope":scope})
    try:
        with urllib.request.urlopen(token_url,timeout=45) as response: token=json.load(response)["token"]
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"})
        with urllib.request.urlopen(req,timeout=45) as response:
            raw=response.read()
            returned=response.headers.get("Docker-Content-Digest")
    except Exception as e: raise RuntimeError("PARENT_MANIFEST_UNAVAILABLE:"+type(e).__name__)
    need(returned=="sha256:"+hashlib.sha256(raw).hexdigest(),"PARENT_REGISTRY_DIGEST_MISMATCH")
    need("sha256:"+hashlib.sha256(raw).hexdigest()==PARENT,"PARENT_DIGEST_MISMATCH")
    m=json.loads(raw);need(isinstance(m.get("layers"),list) and len(m["layers"])>0,"PARENT_MANIFEST_NOT_SINGLE_PLATFORM")
    compressed=sum(x["size"] for x in m["layers"])
    root=run("docker","info","--format","{{.DockerRootDir}}")
    free=shutil.disk_usage(root).free
    estimate=compressed*4+8*1024**3
    need(free>=estimate,"BLOCKED_DAEMON_CAPACITY")
    pathlib.Path(a.out).write_text(json.dumps({"status":"PASS","parentDigest":PARENT,"compressedLayerBytes":compressed,"freeBytes":free,"estimatedRequiredBytes":estimate,"costGate":"CURRENT_ATTESTED","scope":"BUILD_PREFLIGHT_ONLY"},indent=2)+"\n")
if __name__=="__main__":
    try:main()
    except Exception as e:print("BLOCKED:"+str(e),file=sys.stderr);sys.exit(1)
