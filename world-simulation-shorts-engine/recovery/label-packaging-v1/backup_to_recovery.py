#!/usr/bin/env python3
"""Preserve bounded verified build evidence to recovery branch; never run by default."""
import argparse,json,os,pathlib,re,stat,subprocess,sys
from backup_build_evidence import canonical,collect_evidence,document
BRANCH="recovery/g1-capture-diagnostic-contract-20261028"
PREFIX="world-simulation-shorts-engine/recovery/label-image-build-v1/evidence/actions-"
ORIGINS={"https://github.com/dimon3898-sys/yeonhwarok-free.git","https://github.com/dimon3898-sys/yeonhwarok-free","git@github.com:dimon3898-sys/yeonhwarok-free.git"}
MAX_INDEX_BYTES=64*1024
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def run(*cmd):return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).strip()
def index_bytes(file):
    file=canonical(file);before=file.stat()
    need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_INDEX_BYTES,"INDEX_SIZE_LIMIT")
    with file.open('rb') as handle:raw=handle.read(MAX_INDEX_BYTES+1)
    after=file.stat()
    need(len(raw)==before.st_size and len(raw)<=MAX_INDEX_BYTES and (before.st_ino,before.st_mtime_ns,before.st_size)==(after.st_ino,after.st_mtime_ns,after.st_size),"INDEX_CHANGED")
    return raw
def main():
    p=argparse.ArgumentParser();p.add_argument("--evidence",required=True);p.add_argument("--destination",required=True);a=p.parse_args()
    need(os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RETRY_FORBIDDEN")
    need(os.environ.get("GITHUB_REPOSITORY")=="dimon3898-sys/yeonhwarok-free","REPOSITORY_MISMATCH")
    need(os.environ.get("WORLD_ENGINE_LABEL355_BACKUP_APPROVED")=="true","BACKUP_APPROVAL_REQUIRED")
    run_id=os.environ.get("GITHUB_RUN_ID","")
    need(re.fullmatch(r'[1-9][0-9]{0,19}',run_id),"RUN_ID_REQUIRED")
    need(a.destination==PREFIX+run_id,"DESTINATION_NOT_ALLOWED")
    root=canonical(a.evidence)
    index_raw=index_bytes(root/"SAFE_INDEX.json");index=document(index_raw)
    need(set(index)=={'schema','files','totalBytes','status'} and type(index.get('totalBytes')) is int and isinstance(index.get('files'),list),"INDEX_CONTRACT_INVALID")
    need(all(isinstance(row,dict) and set(row)=={'name','bytes','sha256'} and type(row.get('bytes')) is int for row in index['files']),"INDEX_CONTRACT_INVALID")
    # Recompute from the safe producer contracts and actual bounded bytes. Never
    # trust caller-provided totalBytes, duplicate rows, or filename-only safety.
    computed,payloads=collect_evidence(root)
    need(index==computed,"INDEX_EVIDENCE_MISMATCH")
    payloads={**payloads,"SAFE_INDEX.json":index_raw}
    dest=pathlib.Path(a.destination)
    need(not dest.exists(),"DESTINATION_ALREADY_EXISTS")
    canonical(pathlib.Path.cwd()/dest)
    need(run("git","status","--porcelain")=="","DIRTY_WORKTREE")
    need(run("git","rev-parse","--show-toplevel")==str(pathlib.Path.cwd()),"REPOSITORY_ROOT_REQUIRED")
    need(run("git","remote","get-url","origin") in ORIGINS and run("git","remote","get-url","--push","--all","origin") in ORIGINS,"ORIGIN_NOT_ALLOWED")
    run("git","fetch","--no-tags","origin",BRANCH)
    run("git","checkout","-B",BRANCH,"origin/"+BRANCH)
    # Recheck after checkout and preserve the validated byte snapshot, even if
    # the source directory was inside a worktree replaced by checkout.
    canonical(pathlib.Path.cwd()/dest)
    need(not dest.exists(),"DESTINATION_ALREADY_EXISTS")
    dest.mkdir(parents=True)
    for name,raw in sorted(payloads.items()):
        with (dest/name).open('xb') as handle:handle.write(raw)
    run("git","add","--",str(dest))
    run("git","-c","user.name=github-actions[bot]","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m","Preserve label355 bounded build evidence [skip ci]")
    run("git","push","origin","HEAD:refs/heads/"+BRANCH)
    run("git","fetch","--no-tags","origin",BRANCH)
    for name,raw in sorted(payloads.items()):
        remote=subprocess.check_output(["git","show","origin/"+BRANCH+":"+str(dest/name)])
        need(remote==raw and (dest/name).read_bytes()==raw,"REMOTE_READBACK_MISMATCH")
    print("REMOTE_EVIDENCE_READBACK_PASS")
if __name__=="__main__":
    try:main()
    except Exception as e:
        code=str(e)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}',code):code='BACKUP_FAILED'
        print("BLOCKED:"+code,file=sys.stderr);sys.exit(1)
