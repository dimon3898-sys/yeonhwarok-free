#!/usr/bin/env python3
"""Preserve bounded verified build evidence to recovery branch; never run by default."""
import argparse,hashlib,json,os,pathlib,subprocess,sys
BRANCH="recovery/g1-capture-diagnostic-contract-20261028"
ALLOWED={"PREFLIGHT.json","INSTALLED_RESULT.json","OCI_RESULT.json","BUILD_RESULT.json","SAFE_INDEX.json"}
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def run(*cmd):return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).strip()
def main():
    p=argparse.ArgumentParser();p.add_argument("--evidence",required=True);p.add_argument("--destination",required=True);a=p.parse_args()
    need(os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RETRY_FORBIDDEN")
    need(os.environ.get("GITHUB_REPOSITORY")=="dimon3898-sys/yeonhwarok-free","REPOSITORY_MISMATCH")
    need(os.environ.get("WORLD_ENGINE_LABEL355_BACKUP_APPROVED")=="true","BACKUP_APPROVAL_REQUIRED")
    root=pathlib.Path(a.evidence).resolve(strict=True)
    index=json.loads((root/"SAFE_INDEX.json").read_text())
    need(index.get("status")=="PREPARED_NOT_REMOTE_BACKED_UP","INDEX_NOT_PREPARED")
    rows=index["files"];need(rows and {r["name"] for r in rows}<=ALLOWED-{"SAFE_INDEX.json"},"UNSAFE_EVIDENCE_NAMES")
    need(index["totalBytes"]<=5*1024*1024,"EVIDENCE_TOO_LARGE")
    for row in rows:
        f=root/row["name"];need(f.is_file() and not f.is_symlink(),"FILE_MISSING")
        raw=f.read_bytes()
        need(len(raw)==row["bytes"] and hashlib.sha256(raw).hexdigest()==row["sha256"],"EVIDENCE_CHANGED")
    dest=pathlib.Path(a.destination)
    need(not dest.exists(),"DESTINATION_ALREADY_EXISTS")
    need(str(dest).startswith("world-simulation-shorts-engine/recovery/label-image-build-v1/evidence/actions-"),"DESTINATION_NOT_ALLOWED")
    need(run("git","status","--porcelain")=="","DIRTY_WORKTREE")
    run("git","fetch","--no-tags","origin",BRANCH)
    run("git","checkout","-B",BRANCH,"origin/"+BRANCH)
    dest.mkdir(parents=True)
    for name in sorted({r["name"] for r in rows}|{"SAFE_INDEX.json"}):
        (dest/name).write_bytes((root/name).read_bytes())
    run("git","add","--",str(dest))
    run("git","-c","user.name=github-actions[bot]","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m","Preserve label355 bounded build evidence [skip ci]")
    run("git","push","origin","HEAD:refs/heads/"+BRANCH)
    for name in sorted({r["name"] for r in rows}|{"SAFE_INDEX.json"}):
        remote=subprocess.check_output(["git","show","origin/"+BRANCH+":"+str(dest/name)])
        need(remote==(dest/name).read_bytes(),"REMOTE_READBACK_MISMATCH")
    print("REMOTE_EVIDENCE_READBACK_PASS")
if __name__=="__main__":
    try:main()
    except Exception as e:print("BLOCKED:"+str(e),file=sys.stderr);sys.exit(1)
