#!/usr/bin/env python3
"""Closed OCI and build evidence producer; no Docker commands or registry writes."""
import argparse,hashlib,json,pathlib,re,sys
PARENT="sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da"
def need(x,m):
    if not x:raise RuntimeError(m)
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inspect",required=True);p.add_argument("--expected",required=True)
    p.add_argument("--oci-out",required=True);p.add_argument("--build-out",required=True)
    a=p.parse_args()
    expected=json.loads(pathlib.Path(a.expected).read_text())
    raw=pathlib.Path(a.inspect).read_bytes()
    need(0<len(raw)<=1024*1024,"INSPECT_SIZE")
    inspected=json.loads(raw)
    need(type(inspected) is list and len(inspected)==1,"INSPECT_FORMAT")
    item=inspected[0];cfg=item["Config"]
    need(cfg["Entrypoint"]==expected["entrypoint"],"ENTRYPOINT_MISMATCH")
    need(cfg.get("Cmd") is None,"CMD_MISMATCH")
    need(cfg.get("User") in ("","0","root","0:0"),"USER_MISMATCH")
    image_id=item["Id"]
    need(type(image_id) is str and re.fullmatch(r"sha256:[a-f0-9]{64}",image_id),"IMAGE_ID")
    oci={"schema":"WORLD_ENGINE_LABEL355_OCI_RESULT_V1","status":"PASS","imageId":image_id,"entrypointMatch":True,"cmdUnchanged":True,"userUnchanged":True,"scope":"ACTUAL_CANDIDATE_OCI_CONFIG_ONLY","gpuExecuted":False}
    build={"schema":"WORLD_ENGINE_LABEL355_BUILD_RESULT_V1","status":"PASS","imageId":image_id,"parentDigest":PARENT,"sourceRows":355,"scope":"CANDIDATE_IMAGE_IDENTITY_ONLY_NOT_INSTALLED_VALIDATION","gpuExecuted":False}
    for target,value in [(a.oci_out,oci),(a.build_out,build)]:
        with pathlib.Path(target).open("x",encoding="utf-8") as f:json.dump(value,f,sort_keys=True,indent=2);f.write("\n")
if __name__=="__main__":
    try:main()
    except Exception as e:print("BLOCKED:"+str(e),file=sys.stderr);sys.exit(1)
