#!/usr/bin/env python3
"""Fail-closed, read-only installed label image verifier. No rendering or prior suite."""
import argparse, hashlib, json, os, pathlib, stat, sys
def require(ok, code):
    if not ok: raise RuntimeError(code)
def digest(b): return hashlib.sha256(b).hexdigest()
def read(p): return p.read_bytes()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--expected",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    root=pathlib.Path(a.root).resolve(strict=True)
    expected=json.loads(pathlib.Path(a.expected).read_text())
    require(expected["runtimeSourceRows"]==355,"EXPECTED_ROWS")
    manifest_rel="world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json"
    startup_rel="world-simulation-shorts-engine/recovery/studio-cold-start-v2/STARTUP_MANIFEST.json"
    bootstrap_rel="world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py"
    manifest_raw=read(root/manifest_rel)
    require(digest(manifest_raw)==expected["runtimeManifestSHA256"],"MANIFEST_SHA")
    rows=json.loads(manifest_raw)["files"]
    require(len(rows)==355 and len({r["path"] for r in rows})==355,"MANIFEST_355_UNIQUE")
    checked=0
    for r in rows:
        rel=pathlib.PurePosixPath(r["path"])
        require(not rel.is_absolute() and ".." not in rel.parts,"PATH_TRAVERSAL")
        p=root.joinpath(*rel.parts)
        require(not p.is_symlink() and p.is_file(),"MISSING_OR_SYMLINK:"+str(rel))
        require(p.resolve().is_relative_to(root),"PATH_ESCAPE")
        raw=read(p)
        require(len(raw)==r["bytes"] and digest(raw)==r["sha256"],"SOURCE_HASH:"+str(rel))
        checked+=1
    startup_raw=read(root/startup_rel)
    require(digest(startup_raw)==expected["startupManifestSHA256"],"STARTUP_SHA")
    startup=json.loads(startup_raw)
    require(startup["runtimeManifestSHA256"]==expected["runtimeManifestSHA256"],"STARTUP_LINK")
    bootstrap=root/bootstrap_rel
    require(bootstrap.is_file() and not bootstrap.is_symlink(),"BOOTSTRAP_MISSING")
    pinned=startup["files"]["bootstrap.py"]
    bootstrap_raw=read(bootstrap)
    require(len(bootstrap_raw)==pinned["bytes"] and digest(bootstrap_raw)==pinned["sha256"],"BOOTSTRAP_SHA")
    # Must be run as UID1000 to prove the actual runtime identity can read files.
    require(os.geteuid()==1000,"UID1000_REQUIRED")
    result={"schema":"WORLD_ENGINE_INSTALLED_LABEL355_VERIFICATION_V1","status":"PASS","installedFilesVerified":checked,"uid":os.geteuid(),"runtimeManifestSHA256":digest(manifest_raw),"startupManifestSHA256":digest(startup_raw),"scope":"INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE","gpuExecuted":False}
    pathlib.Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print("BLOCKED:"+str(e),file=sys.stderr)
        sys.exit(1)
