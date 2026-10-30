#!/usr/bin/env python3
"""Fail-closed, read-only installed label image verifier. No rendering or prior suite."""
import argparse, hashlib, json, os, pathlib, re, stat, sys
MAX_SOURCE_BYTES=128*1024*1024
def require(ok, code):
    if not ok: raise RuntimeError(code)
def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(p):
    p=pathlib.Path(p)
    require(p.is_absolute() and ".." not in p.parts,"ABSOLUTE_PATH_REQUIRED")
    require(not any(part.is_symlink() for part in (p,*p.parents)),"SYMLINK_FORBIDDEN")
    return p
def read(p):
    p=canonical(p)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_SOURCE_BYTES,"BOUNDED_REGULAR_SOURCE_REQUIRED")
        raw=stream.read(MAX_SOURCE_BYTES+1)
        after=os.fstat(stream.fileno())
    require(len(raw)==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),"SOURCE_CHANGED_DURING_READ")
    return raw
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--expected",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    root=canonical(a.root).resolve(strict=True)
    expected_path=canonical(a.expected).resolve(strict=True)
    out=canonical(a.out)
    require(out!=expected_path,"OUTPUT_EXPECTED_OVERWRITE_FORBIDDEN")
    require(not out.is_relative_to(root),"OUTPUT_VERIFIED_ROOT_FORBIDDEN")
    require(not out.exists(),"OUTPUT_FRESH_PATH_REQUIRED")
    expected=json.loads(read(expected_path))
    require(expected["runtimeSourceRows"]==355,"EXPECTED_ROWS")
    manifest_rel="world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json"
    startup_rel="world-simulation-shorts-engine/recovery/studio-cold-start-v2/STARTUP_MANIFEST.json"
    bootstrap_rel="world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
    manifest_raw=read(root/manifest_rel)
    require(digest(manifest_raw)==expected["runtimeManifestSHA256"],"MANIFEST_SHA")
    manifest=json.loads(manifest_raw)
    require(manifest.get("schema")=="WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1","MANIFEST_SCHEMA")
    rows=manifest["files"]
    require(isinstance(rows,list) and all(isinstance(r,dict) and set(r)=={"path","bytes","sha256"} and isinstance(r["path"],str) and type(r["bytes"]) is int and r["bytes"]>0 and re.fullmatch("[a-f0-9]{64}",str(r["sha256"])) for r in rows),"MANIFEST_ROW")
    require(len(rows)==355 and len({r["path"] for r in rows})==355,"MANIFEST_355_UNIQUE")
    checked=0
    for r in rows:
        rel=pathlib.PurePosixPath(r["path"])
        require(not rel.is_absolute() and ".." not in rel.parts and str(rel)==r["path"] and "\\" not in r["path"],"PATH_TRAVERSAL")
        p=root.joinpath(*rel.parts)
        require(not p.is_symlink() and p.is_file(),"MISSING_OR_SYMLINK:"+str(rel))
        require(p.resolve().is_relative_to(root),"PATH_ESCAPE")
        raw=read(p)
        require(len(raw)==r["bytes"] and digest(raw)==r["sha256"],"SOURCE_HASH:"+str(rel))
        checked+=1
    startup_raw=read(root/startup_rel)
    require(digest(startup_raw)==expected["startupManifestSHA256"],"STARTUP_SHA")
    startup=json.loads(startup_raw)
    require(startup.get("schema")=="WORLD_ENGINE_STUDIO_COLD_START_FILES_V2" and set(startup.get("files",{}))=={"bootstrap.py","worker.py"},"STARTUP_CONTRACT")
    require(all(isinstance(row,dict) and set(row)=={"bytes","sha256"} and type(row["bytes"]) is int and row["bytes"]>0 and re.fullmatch("[a-f0-9]{64}",str(row["sha256"])) for row in startup["files"].values()),"STARTUP_FILE_ROW")
    require(startup["runtimeManifestSHA256"]==expected["runtimeManifestSHA256"],"STARTUP_LINK")
    bootstrap=root/bootstrap_rel
    require(bootstrap.is_file() and not bootstrap.is_symlink(),"BOOTSTRAP_MISSING")
    pinned=startup["files"]["bootstrap.py"]
    bootstrap_raw=read(bootstrap)
    require(len(bootstrap_raw)==pinned["bytes"] and digest(bootstrap_raw)==pinned["sha256"],"BOOTSTRAP_SHA")
    require(re.findall(rb"(?m)^SOURCE_SHA = '([a-f0-9]{64})'$",bootstrap_raw)==[expected["runtimeManifestSHA256"].encode()],"BOOTSTRAP_SOURCE_PIN")
    worker=root/startup_rel
    worker=worker.parent/"worker.py"
    require(worker.is_file() and not worker.is_symlink(),"WORKER_MISSING_OR_SYMLINK")
    pinned=startup["files"]["worker.py"]
    worker_raw=read(worker)
    require(len(worker_raw)==pinned["bytes"] and digest(worker_raw)==pinned["sha256"],"WORKER_SHA")
    # Must be run as UID1000 to prove the actual runtime identity can read files.
    require(os.geteuid()==1000,"UID1000_REQUIRED")
    result={"schema":"WORLD_ENGINE_INSTALLED_LABEL355_VERIFICATION_V1","status":"PASS","installedFilesVerified":checked,"uid":os.geteuid(),"runtimeManifestSHA256":digest(manifest_raw),"startupManifestSHA256":digest(startup_raw),"scope":"INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE","gpuExecuted":False}
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,"w") as stream:
        stream.write(json.dumps(result,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print("BLOCKED:"+str(e),file=sys.stderr)
        sys.exit(1)
