"""Read-only byte preservation and old-cache metadata checks; writes new report only."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
BASE='0069e9af1c0888843289d312d86bad29ac26007e'
PIN='cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def verify():
    raw=(HERE/'reports/PROTECTION_BASELINE.json').read_bytes()
    if sha(raw)!=PIN:raise ValueError('RECOVERY_PROTECTION_BASELINE_CHANGED')
    baseline=json.loads(raw);errors=[]
    def check(file,row,kind):
        if file.is_symlink() or not file.is_file():errors.append({'kind':kind,'path':str(file),'error':'MISSING_OR_SYMLINK'});return
        if file.stat().st_size!=row['bytes'] or sha(file.read_bytes())!=row['sha256']:
            errors.append({'kind':kind,'path':str(file),'error':'BYTE_CHANGE'})
    for row in baseline['protectedFiles']:
        file=REPO/row['path'] if row['scope']=='REPOSITORY' else Path(row['resolvedAuditPath'])
        check(file,row,'PROTECTED')
    for name,namespace in baseline['existingNamespaces'].items():
        for row in namespace['files']:check(REPO/row['path'],row,'ORIGINAL_NAMESPACE')
    metadata_count=0
    for snapshot in baseline['existingCacheMetadataSnapshots']:
        root=Path(snapshot['root'])
        for row in snapshot['files']:
            file=root/row['path'];metadata_count+=1
            if not file.exists():errors.append({'kind':'EXISTING_CACHE','path':str(file),'error':'REMOVED'});continue
            stat=file.lstat()
            if (stat.st_size,stat.st_mtime_ns,stat.st_ino,stat.st_mode,file.is_symlink())!=(row['bytes'],row['mtimeNS'],row['inode'],row['mode'],row['symlink']):
                errors.append({'kind':'EXISTING_CACHE','path':str(file),'error':'METADATA_CHANGED'})
    prefix=HERE.relative_to(REPO).as_posix()+'/'
    changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=REPO,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=REPO,text=True).splitlines()
    outside=[name for name in changed+untracked if not name.startswith(prefix)]
    findings=[];checked=0
    for f in HERE.rglob('*'):
        if f.is_file() and f.suffix in {'.py','.mjs','.json','.md','.csv','.txt'} and not any(v in f.parts for v in ('captures','__pycache__')):
            checked+=1;data=f.read_bytes()
            for pattern in [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{40,}',rb'\bAKIA[A-Z0-9]{16}\b']:
                if re.search(pattern,data):findings.append(str(f.relative_to(HERE)))
    result={'schema':'WORLD_ENGINE_G2_RECOVERY_PROTECTION_V1','status':'PASS' if not(errors or outside or findings) else 'FAIL',
        'baselineCommit':BASE,'baselineSHA256':PIN,'protectedUniqueFiles':len(baseline['protectedFiles']),
        'protectedFilesChanged':len([r for r in errors if r['kind']=='PROTECTED']),
        'oldNamespaceFilesVerified':sum(len(v['files']) for v in baseline['existingNamespaces'].values()),
        'oldCacheFilesMetadataVerified':metadata_count,'oldG1ReRendered':False,'errors':errors,
        'outsideNamespaceChanges':outside,'secretScan':{'strongPatternTextFilesChecked':checked,'findings':findings},
        'existingSourceAssetCacheDeletionPerformed':False,'paidGpuExecuted':False,'finalPromoted':False}
    (HERE/'reports/PROTECTION_FINAL.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','protectedUniqueFiles','protectedFilesChanged','oldNamespaceFilesVerified','oldCacheFilesMetadataVerified','outsideNamespaceChanges')}))
    if result['status']!='PASS':raise SystemExit(1)
    return result

if __name__=='__main__':verify()
