#!/usr/bin/env python3
"""Future read-only verification of selected public v003 files; no Git mutation."""
import argparse,datetime,hashlib,json,re,subprocess,sys,urllib.request
from pathlib import Path
from urllib.parse import quote

LIMIT=100*1024*1024
CHUNK=1024*1024

def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(CHUNK),b''):h.update(block)
    return h.hexdigest()

def child(folder,name):
    if not isinstance(name,str) or Path(name).name!=name:raise ValueError('INVALID_PUBLIC_FILE_NAME')
    p=(folder/name).resolve()
    if not p.is_relative_to(folder) or not p.is_file():raise ValueError('PUBLIC_FILE_MISSING')
    return p

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--delivery-dir',required=True,type=Path)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();repo=args.repo.resolve();folder=args.delivery_dir.resolve()
    if not re.fullmatch('[a-f0-9]{40}',args.commit):raise ValueError('ACTUAL_PUBLISHED_COMMIT_REQUIRED')
    if not folder.is_relative_to(repo/'deliverables') or folder.name!='SUEZ_CLOSURE_75S_TTS_v003':raise ValueError('EXACT_V003_DELIVERY_DIRECTORY_REQUIRED')
    if args.output.exists():raise ValueError('EXISTING_VERIFICATION_REPORT_PRESERVED')
    remote=subprocess.check_output(['git','-C',str(repo),'ls-remote','origin','refs/heads/main'],text=True,stderr=subprocess.PIPE).split()[0]
    if remote!=args.commit:raise ValueError('PUSHED_MAIN_COMMIT_MISMATCH')
    manifest=child(folder,'DELIVERY_MANIFEST.json');delivery=json.loads(manifest.read_text())
    if delivery.get('project_id')!='project_594442ec2df9' or delivery.get('version')!='v003' or delivery.get('automatic_qc_passed') is not True:raise ValueError('EXACT_QC_PASSED_V003_DELIVERY_REQUIRED')
    files={manifest:(manifest.stat().st_size,file_sha(manifest))}
    for item in delivery['files']:
        p=child(folder,item['name'])
        if p.stat().st_size!=item['bytes'] or file_sha(p)!=item['sha256']:raise ValueError('LOCAL_DELIVERY_BYTES_SHA_MISMATCH')
        files[p]=(item['bytes'],item['sha256'])
    archive=child(folder.parent,folder.name+'.zip');parts=[];parts_doc=None
    if archive.stat().st_size<=LIMIT:
        files[archive]=(archive.stat().st_size,file_sha(archive))
    else:
        pm=child(folder.parent,archive.name+'.parts.json');parts_doc=json.loads(pm.read_text());files[pm]=(pm.stat().st_size,file_sha(pm))
        if parts_doc.get('original_bytes')!=archive.stat().st_size or parts_doc.get('original_sha256')!=file_sha(archive):raise ValueError('PRESERVED_ZIP_PARTS_SOURCE_MISMATCH')
        for item in parts_doc['parts']:
            p=child(pm.parent,item['name'])
            if item['bytes']>90*1024*1024 or p.stat().st_size!=item['bytes'] or file_sha(p)!=item['sha256']:raise ValueError('LOCAL_PART_BYTES_SHA_MISMATCH')
            parts.append(p);files[p]=(item['bytes'],item['sha256'])
    remote_whole=hashlib.sha256();part_set=set(parts);rows=[]
    # Dict insertion preserves split manifest order for the remote whole-ZIP SHA.
    for p,(expected_size,expected_sha) in files.items():
        if expected_size>LIMIT:raise ValueError('OVERSIZED_LOOSE_FILE_MUST_NOT_BE_ORDINARY_GIT_PUBLISHED')
        rel=p.relative_to(repo).as_posix();url='https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'+args.commit+'/'+quote(rel,safe='/');h=hashlib.sha256();size=0
        with urllib.request.urlopen(url,timeout=120) as response:
            if response.status!=200:raise ValueError('PUBLIC_HTTP_200_REQUIRED')
            for block in iter(lambda:response.read(CHUNK),b''):
                h.update(block);size+=len(block)
                if p in part_set:remote_whole.update(block)
        if size!=expected_size or h.hexdigest()!=expected_sha:raise ValueError('PUBLIC_BYTES_SHA_MISMATCH')
        rows.append({'path':rel,'url':url,'http_status':200,'bytes':size,'sha256':h.hexdigest(),'matches_local':True})
    if parts_doc and remote_whole.hexdigest()!=parts_doc['original_sha256']:raise ValueError('REMOTE_REASSEMBLED_ZIP_SHA_MISMATCH')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as out:
        json.dump({'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':args.commit,'remote_main':remote,'project_id':'project_594442ec2df9','version':'v003','plan_hash':delivery['plan_hash'],'files':rows,'remote_reassembled_ZIP_sha256':remote_whole.hexdigest() if parts_doc else None,'scope':'Actual public GitHub file HTTP/bytes/SHA only; no real-phone, public-app, audio-listening or aesthetic claim'},out,indent=2);out.write('\n')
    print(args.output)

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Do not echo credentials, proxies, request headers or raw network errors.
        print(json.dumps({'verification_failed':True,'error_type':type(error).__name__,'detail':str(error) if isinstance(error,ValueError) else 'Verification failed; source and existing reports preserved'}),file=sys.stderr)
        raise SystemExit(1)
