#!/usr/bin/env python3
"""Offline bounded safe OCI receipt producer/validator; no Docker invocation."""
import argparse, hashlib, json, os, pathlib, re
PARENT='sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
SCHEMA='WORLD_ENGINE_IMAGE_CONFIG_SAFE_V1'
HASH=re.compile(r'sha256:[0-9a-f]{64}\Z')
HEX=re.compile(r'[0-9a-f]{64}\Z')
FIELDS={'schema','status','imageId','parentDigest','os','architecture','rootfsType','rootfsDiffIDs','entrypointSHA256','cmdSHA256','userSHA256','historySHA256','historyCount','gpuExecuted'}
def require(ok,why):
    if not ok: raise ValueError(why)
def pairs(seq):
    out={}
    for k,v in seq:
        require(k not in out,'DUPLICATE_KEY');out[k]=v
    return out
def parse(raw):
    require(0<len(raw)<=131072,'SIZE_LIMIT')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE')))
def canonical(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def validate(d):
    require(type(d) is dict and set(d)==FIELDS,'FIELDS')
    require(d['schema']==SCHEMA and d['status']=='CAPTURED_NOT_COMPARED','STATUS')
    require(type(d['imageId']) is str and HASH.fullmatch(d['imageId']),'IMAGE_ID')
    require(d['parentDigest']==PARENT and d['os']=='linux' and d['architecture']=='amd64' and d['rootfsType']=='layers','PLATFORM')
    ids=d['rootfsDiffIDs'];require(type(ids) is list and 0<len(ids)<=1024 and all(type(v) is str and HASH.fullmatch(v) for v in ids),'LAYERS')
    require(all(type(d[k]) is str and HEX.fullmatch(d[k]) for k in ('entrypointSHA256','cmdSHA256','userSHA256','historySHA256')),'DIGESTS')
    require(type(d['historyCount']) is int and 0<=d['historyCount']<=4096 and d['gpuExecuted'] is False,'COUNT_GPU')
    require(len(canonical(d))<=131072,'OUTPUT_SIZE')
    return d
def produce(inspect,expected_id,verified_parent_digest):
    require(type(inspect) is list and len(inspect)==1 and type(inspect[0]) is dict,'INSPECT')
    item=inspect[0];cfg=item['Config'];root=item['RootFS']
    require(type(cfg) is dict and type(root) is dict,'INSPECT_TYPES')
    require(item['Id']==expected_id and type(expected_id) is str and HASH.fullmatch(expected_id),'IMAGE_ID_MISMATCH')
    require(item.get('Os')=='linux' and item.get('Architecture')=='amd64' and root.get('Type')=='layers','PLATFORM')
    # Docker inspect does not reliably identify a pinned parent; caller must supply verified provenance.
    require(verified_parent_digest==PARENT,'PARENT_NOT_ATTESTED')
    history=item.get('History',[])
    require(type(history) is list and len(history)<=4096,'HISTORY')
    d=dict(schema=SCHEMA,status='CAPTURED_NOT_COMPARED',imageId=expected_id,parentDigest=PARENT,os='linux',architecture='amd64',rootfsType='layers',rootfsDiffIDs=root['Layers'],entrypointSHA256=digest(cfg.get('Entrypoint')),cmdSHA256=digest(cfg.get('Cmd')),userSHA256=digest(cfg.get('User')),historySHA256=digest(history),historyCount=len(history),gpuExecuted=False)
    return validate(d)
def safe_read(path):
    p=pathlib.Path(path);require(not p.is_symlink() and p.is_file(),'INPUT_PATH')
    require(p.stat().st_size<=131072,'INPUT_SIZE')
    return p.read_bytes()
def main():
    a=argparse.ArgumentParser();a.add_argument('--inspect',required=True);a.add_argument('--image-id',required=True);a.add_argument('--verified-parent-digest',required=True);a.add_argument('--out',required=True);args=a.parse_args()
    data=produce(parse(safe_read(args.inspect)),args.image_id,args.verified_parent_digest)
    out=pathlib.Path(args.out);require(not out.is_symlink(),'OUTPUT_SYMLINK')
    with out.open('x',encoding='utf8') as f: json.dump(data,f,sort_keys=True,separators=(',',':'));f.write('\n')
if __name__=='__main__':main()
