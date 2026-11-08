"""Authored presentation inputs only; preserve the reviewed facts and old inputs."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

source, destination = map(Path, sys.argv[1:])
destination.mkdir(parents=True, exist_ok=False)
sha = lambda b: hashlib.sha256(b).hexdigest()
def save(name, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    with (destination/name).open('xb') as stream: stream.write(raw)
    return sha(raw)
def camera(rows):
    return {'mode':'KEYFRAMES','keyframes':[{'frame':f,'center':p,'zoom':z} for f,p,z in rows]}
def label(id, text, location, start, end, *, event=None, pin='NONE', role='EVENT', pop=False, priority=80):
    row = dict(id=id, role=role, text=text, locationId=location, startFrame=start, endFrame=end,
               revealFrames=16 if pop else 1, exitFrames=1, priority=priority,
               style='REFERENCE_V1', pin=pin)
    if event: row['eventId']=event
    if pop: row['reveal']='GRAPHEME_POP'
    return row
def assign(p, rows, labels):
    p['camera']=camera(rows)
    p['labels']={'enabled':True,'items':labels}
    events={}
    for item in labels:
        if 'eventId' not in item: continue
        key=item['eventId']
        if key not in events: events[key]={'id':key,'locationId':item['locationId'],'startFrame':item['startFrame'],'endFrame':item['endFrame']}
        else:
            assert events[key]['locationId']==item['locationId']
            events[key]['startFrame']=min(events[key]['startFrame'],item['startFrame'])
            events[key]['endFrame']=max(events[key]['endFrame'],item['endFrame'])
    p['highlights']=list(events.values())
    # A geographic background tint, never a claim of military ownership.
    p['territoryColors']={key:[1,.8,.1,.14] for key in p['territoryColors']}

D=[128.605026,35.868735]; I=[126.640288,37.478094]; S=[126.997785,37.568295]
inputs=[]; receipts=[]
for part in (1,2):
    name=f'KOREAN_WAR_20S_PART_0{part}.json'; raw=(source/name).read_bytes()
    inputs.append(deepcopy(json.loads(raw)))
    receipts.append({'part':part,'sourceFile':name,'sourceSHA256':sha(raw)})
a,b=inputs; p=a['presentation']; q=p['sceneOverrides']['incheon']
assign(p,[(0,[127.5,38.2],.25),(12,[127.5,38.2],.25),(60,D,.55),(149,D,.55)],[
 label('intro','한국전쟁','SEOUL',0,46,role='COUNTRY'),
 label('busan-context','부산','BUSAN',0,150,event='busan-context',pin='CONTEXT',priority=50),
 label('defense','낙동강 방어','DAEGU',36,150,event='south',pin='HERO',pop=True,priority=100),
 label('september','1950.09 초','DAEGU',64,150,event='south',role='NUMERIC'),
])
assign(q,[(0,D,.55),(30,[127.7,36.7],.45),(65,I,.70),(149,I,.70)],[
 label('defense','낙동강 방어','DAEGU',0,24,event='south',pin='HERO',priority=100),
 label('september','1950.09 초','DAEGU',0,24,event='south',role='NUMERIC'),
 label('busan-context','부산','BUSAN',0,24,event='busan-context',pin='CONTEXT',priority=50),
 label('seoul-context','서울','SEOUL',24,150,event='seoul-context',pin='CONTEXT',priority=50),
 label('incheon','인천상륙작전','INCHEON',38,150,event='landing',pin='HERO',pop=True,priority=100),
 label('landing-date','1950.09.15','INCHEON',65,150,event='landing',role='NUMERIC'),
])
p=b['presentation']; q=p['sceneOverrides']['seoul']
assign(p,[(0,I,.70),(20,I,.70),(110,S,.85),(149,S,.85)],[
 label('incheon','인천상륙작전','INCHEON',0,35,event='landing',pin='HERO',priority=100),
 label('landing-date','1950.09.15','INCHEON',0,35,event='landing',role='NUMERIC'),
 label('seoul-context','서울','SEOUL',0,35,event='seoul-context',pin='CONTEXT',priority=50),
 label('advance-direction','진격 방향(개략)','DIRECTION_LABEL',35,105,event='advance',pop=True,priority=100),
 label('seoul','서울','SEOUL',100,150,event='capital',pin='HERO',pop=True,priority=100),
])
assign(q,[(0,S,.85),(149,S,.85)],[
 label('seoul','서울','SEOUL',0,18,event='capital',pin='HERO',priority=100),
 label('recapture','서울 수복','SEOUL',18,150,event='capital',pin='HERO',pop=True,priority=100),
 label('recapture-date','1950.09.28','SEOUL',50,150,event='capital',role='NUMERIC'),
])
for index,item in enumerate(inputs):
    original=json.loads((source/receipts[index]['sourceFile']).read_bytes())
    assert {k:v for k,v in item.items() if k!='presentation'}=={k:v for k,v in original.items() if k!='presentation'}
    name=f'KOREAN_WAR_REFERENCE_CANDIDATE_PART_0{index+1}.json'
    receipts[index].update(candidateFile=name,candidateSHA256=save(name,item),changedScope='presentation only; facts, source geometry, dates, source policy and region unchanged')
save('INPUT_CHANGE_RECEIPT.json',{'status':'CANDIDATE_NOT_YET_VALIDATED','inputs':receipts,'runtimeChanges':0,'oldPASSReruns':0,'gpuStarts':0})
