#!/usr/bin/env python3
"""Bounded evidence preparation only; no git push or registry operation."""
import argparse,hashlib,json,pathlib,sys
MAX_BYTES=5*1024*1024
ALLOW={"PREFLIGHT.json","INSTALLED_RESULT.json","OCI_RESULT.json","BUILD_RESULT.json"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True);p.add_argument("--index",required=True)
    a=p.parse_args();root=pathlib.Path(a.evidence).resolve(strict=True)
    items=[];total=0
    for f in sorted(root.iterdir()):
        if f.name not in ALLOW or not f.is_file() or f.is_symlink():continue
        data=f.read_bytes();total+=len(data)
        if total>MAX_BYTES:raise RuntimeError("EVIDENCE_SIZE_LIMIT")
        items.append({"name":f.name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    if not items:raise RuntimeError("NO_SAFE_EVIDENCE")
    pathlib.Path(a.index).write_text(json.dumps({"schema":"WORLD_ENGINE_LABEL355_SAFE_EVIDENCE_INDEX_V1","files":items,"totalBytes":total,"status":"PREPARED_NOT_REMOTE_BACKED_UP"},indent=2)+"\n")
if __name__=="__main__":
    try:main()
    except Exception as e:print("BLOCKED:"+str(e),file=sys.stderr);sys.exit(1)
