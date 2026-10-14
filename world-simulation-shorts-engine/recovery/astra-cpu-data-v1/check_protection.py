"""Recheck preserved file pins; reuse manifests without re-auditing ASTRA ZIP."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
ENGINE=REPO/'world-simulation-shorts-engine'
BASE='21036824888dffbe232934d0332420c5910b98a4'


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def main():
    pins={}
    def add(path,record):
        resolved=(REPO/path).resolve()
        if REPO not in resolved.parents:
            raise ValueError('inventory escapes repository')
        relative=resolved.relative_to(REPO).as_posix()
        pair=(record['sha256'],record['bytes'])
        if relative in pins and pins[relative]!=pair:raise ValueError('protected inventories disagree')
        pins[relative]=pair
    prefix='world-simulation-shorts-engine/recovery/'
    frontier=json.loads((ENGINE/'recovery/moving-frontier-glow-fix-v1/manifests/HASH_MANIFEST.json').read_bytes())
    for item in frontier['required_files']:add(item['path'],item)
    master=json.loads((REPO/'deliverables/MASTER_V3_SHA256.json').read_bytes())
    for name,item in master['files'].items():add('deliverables/'+name,item)
    for filename,field in [('evidence/BASELINE_BINDINGS.json','media'),('inputs/INPUT_MANIFEST.json','files')]:
        document=json.loads((ENGINE/'recovery/astra-map-quality-v1'/filename).read_bytes())
        for item in document[field]:add(item['path'],item)
    flat=REPO/'deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v004'
    for item in json.loads((flat/'FILE_MANIFEST.json').read_bytes())['files']:
        add((flat/item['file']).relative_to(REPO),item)
    # Exact parent Git bytes for Final manifests, beyond the reused old inventories.
    for name in ['event-v1-final/FINAL_MANIFEST.json','event-flow-v2-final/FINAL_MANIFEST.json',
                 'event-area-v3-final/FINAL_MANIFEST.json','v5/manifests/final/FINAL_HASH_MANIFEST.json']:
        path=prefix+name
        original=subprocess.run(['git','show',BASE+':'+path],cwd=REPO,check=True,capture_output=True).stdout
        add(path,{'sha256':hashlib.sha256(original).hexdigest(),'bytes':len(original)})
    records=[]
    for name,(expected,size) in sorted(pins.items()):
        path=REPO/name
        actual=digest(path) if path.is_file() else None
        records.append({'path':name,'expectedSHA256':expected,'actualSHA256':actual,
                        'bytes':path.stat().st_size if path.is_file() else None,
                        'status':'PASS' if actual==expected and path.stat().st_size==size else 'FAIL'})
    changed=subprocess.run(['git','diff','--name-only',BASE,'--','.',
                            ':!world-simulation-shorts-engine/recovery/astra-cpu-data-v1'],
                            cwd=REPO,check=True,capture_output=True,text=True).stdout.splitlines()
    report={'schema':'ASTRA_CPU_PROTECTION_V1','baseCommit':BASE,'records':records,
            'checkedFiles':len(records),'changedProtectedPaths':changed,
            'ASTRAInternal24MemberAuditRepeated':False,
            'status':'PASS' if not changed and all(r['status']=='PASS' for r in records) else 'FAIL'}
    (ROOT/'evidence/PROTECTION_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='records'}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
