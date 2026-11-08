"""Compare persistent label placement at new scene/clip boundaries, without drawing."""
import json,sys
from pathlib import Path
a,b=[json.loads(Path(x).read_text())['frames'] for x in sys.argv[1:3]]
def same(x,y):
    if isinstance(x,(float,int)) and isinstance(y,(float,int)):return abs(x-y)<1e-6
    if isinstance(x,list) and isinstance(y,list):return len(x)==len(y) and all(same(u,v) for u,v in zip(x,y))
    return x==y
checks=[]
for name,left,right in [('part1-scene',a[149],a[150]),('part2-scene',b[149],b[150]),('clip-boundary',a[299],b[0])]:
    errors=[]
    if not same(left['bounds'],right['bounds']):errors.append('CAMERA_BOUNDS')
    lm={x['id']:x for x in left['drawn']};rm={x['id']:x for x in right['drawn']}
    for id in lm.keys()&rm.keys():
        for key in ['text','box','pinBox','connector','fontSize','alpha','pinScale']:
            if not same(lm[id].get(key),rm[id].get(key)):errors.append(id+':'+key)
    checks.append({'boundary':name,'status':'FAIL' if errors else 'PASS','continuousLabels':sorted(lm.keys()&rm.keys()),'errors':errors})
result={'status':'FAIL' if any(x['errors'] for x in checks) else 'PASS_CHANGED_INPUT_SEAMS','checks':checks,'gpuStarts':0,'renders':0,'referenceQualityApproved':False}
Path(sys.argv[3]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if result['status']=='FAIL':raise SystemExit(1)
