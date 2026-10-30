#!/usr/bin/env python3
"""Bounded evidence preparation only; no git push or registry operation."""
import argparse,hashlib,json,pathlib,re,stat,sys
MAX_BYTES=5*1024*1024
ALLOW={"PREFLIGHT.json","INSTALLED_RESULT.json","OCI_RESULT.json","BUILD_RESULT.json"}
PARENT="sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da"
def need(ok,code):
    if not ok:raise RuntimeError(code)
def canonical(p):
    p=pathlib.Path(p)
    need(p.is_absolute() and '..' not in p.parts,"EVIDENCE_ABSOLUTE_PATH_REQUIRED")
    need(not any(x.is_symlink() for x in (p,*p.parents)),"EVIDENCE_SYMLINK_FORBIDDEN")
    return p
def document(raw):
    def pairs(items):
        value={}
        for k,v in items:
            need(k not in value,"EVIDENCE_DUPLICATE_JSON_KEY")
            value[k]=v
        return value
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
                         parse_constant=lambda _:need(False,"EVIDENCE_JSON_INVALID"))
    except (UnicodeDecodeError,json.JSONDecodeError):raise RuntimeError("EVIDENCE_JSON_INVALID")
    need(type(value) is dict,"EVIDENCE_JSON_INVALID")
    return value
def integer(value):return type(value) is int and 0<=value<2**63
def safe_evidence_bytes(name,raw):
    """Only reviewed producer summaries; never raw logs, prompts or credentials."""
    need(name in ALLOW,"UNSAFE_EVIDENCE_NAME")
    need(0<len(raw)<=MAX_BYTES,"EVIDENCE_SIZE_LIMIT")
    value=document(raw)
    if name=='PREFLIGHT.json':
        required={'status','parentDigest','compressedLayerBytes','freeBytes','estimatedRequiredBytes','costGate','scope'}
        optional={'storageDriver','layerCount','capacityEstimateBasis','localDaemonEndpoint'}
        need(required<=set(value)<=required|optional,"EVIDENCE_FIELDS_INVALID")
        need(value['status']=='PASS' and value['parentDigest']==PARENT
             and value['costGate']=='CURRENT_ATTESTED' and value['scope']=='BUILD_PREFLIGHT_ONLY',"EVIDENCE_VALUE_INVALID")
        need(all(integer(value[k]) for k in ['compressedLayerBytes','freeBytes','estimatedRequiredBytes'])
             and value['compressedLayerBytes']>0 and value['estimatedRequiredBytes']>0
             and value['freeBytes']>=value['estimatedRequiredBytes'],"EVIDENCE_VALUE_INVALID")
        if 'storageDriver' in value:need(value['storageDriver'] in {'vfs','overlay2','overlayfs','fuse-overlayfs'},"EVIDENCE_VALUE_INVALID")
        if 'layerCount' in value:need(integer(value['layerCount']) and 0<value['layerCount']<=1024,"EVIDENCE_VALUE_INVALID")
        if 'capacityEstimateBasis' in value:need(value['capacityEstimateBasis'] in {'4x cumulative compressed prefixes +8GiB reserve','4x compressed bytes +8GiB reserve'},"EVIDENCE_VALUE_INVALID")
        if 'localDaemonEndpoint' in value:need(value['localDaemonEndpoint']=='unix:///var/run/docker.sock',"EVIDENCE_VALUE_INVALID")
    elif name=='INSTALLED_RESULT.json':
        need(set(value)=={'schema','status','installedFilesVerified','uid','runtimeManifestSHA256','startupManifestSHA256','scope','gpuExecuted'},"EVIDENCE_FIELDS_INVALID")
        need(value['schema']=='WORLD_ENGINE_INSTALLED_LABEL355_VERIFICATION_V1' and value['status']=='PASS'
             and type(value['installedFilesVerified']) is int and value['installedFilesVerified']==355
             and type(value['uid']) is int and value['uid']==1000 and value['gpuExecuted'] is False
             and value['scope']=='INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE',"EVIDENCE_VALUE_INVALID")
        need(all(type(value[k]) is str and re.fullmatch('[a-f0-9]{64}',value[k]) for k in ['runtimeManifestSHA256','startupManifestSHA256']),"EVIDENCE_VALUE_INVALID")
    elif name=='OCI_RESULT.json':
        need(set(value)=={'schema','status','imageId','entrypointMatch','cmdUnchanged','userUnchanged','scope','gpuExecuted'},"EVIDENCE_FIELDS_INVALID")
        need(value['schema']=='WORLD_ENGINE_LABEL355_OCI_RESULT_V1' and value['status']=='PASS'
             and type(value['imageId']) is str and re.fullmatch('sha256:[a-f0-9]{64}',value['imageId'])
             and value['entrypointMatch'] is True and value['cmdUnchanged'] is True and value['userUnchanged'] is True
             and value['scope']=='ACTUAL_CANDIDATE_OCI_CONFIG_ONLY' and value['gpuExecuted'] is False,"EVIDENCE_VALUE_INVALID")
    elif name=='BUILD_RESULT.json':
        need(set(value)=={'schema','status','imageId','parentDigest','expectedSourceRows','scope','gpuExecuted'},"EVIDENCE_FIELDS_INVALID")
        need(value['schema']=='WORLD_ENGINE_LABEL355_BUILD_RESULT_V1' and value['status']=='IDENTITY_ONLY'
             and type(value['imageId']) is str and re.fullmatch('sha256:[a-f0-9]{64}',value['imageId'])
             and value['parentDigest']==PARENT and type(value['expectedSourceRows']) is int and value['expectedSourceRows']==355
             and value['scope']=='CANDIDATE_IMAGE_IDENTITY_ONLY_NOT_BUILD_OR_INSTALLED_VALIDATION'
             and value['gpuExecuted'] is False,"EVIDENCE_VALUE_INVALID")
    else:
        raise RuntimeError("UNREVIEWED_EVIDENCE_SCHEMA")
    return value
def collect_evidence(root):
    """Return the exact bounded byte snapshot and matching index without writes."""
    root=canonical(root)
    need(root.is_dir(),"EVIDENCE_DIRECTORY_REQUIRED")
    items=[];total=0;payloads={}
    for f in sorted(root.iterdir()):
        if f.name not in ALLOW or not f.is_file() or f.is_symlink():continue
        before=f.stat()
        need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_BYTES-total,"EVIDENCE_SIZE_LIMIT")
        with f.open('rb') as handle:data=handle.read(MAX_BYTES-total+1)
        after=f.stat()
        need(len(data)==before.st_size and len(data)<=MAX_BYTES-total,"EVIDENCE_SIZE_LIMIT")
        need((before.st_ino,before.st_mtime_ns,before.st_size)==(after.st_ino,after.st_mtime_ns,after.st_size),"EVIDENCE_CHANGED_DURING_READ")
        safe_evidence_bytes(f.name,data);total+=len(data);payloads[f.name]=data
        items.append({"name":f.name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    need(bool(items),"NO_SAFE_EVIDENCE")
    return {"schema":"WORLD_ENGINE_LABEL355_SAFE_EVIDENCE_INDEX_V1","files":items,"totalBytes":total,"status":"PREPARED_NOT_REMOTE_BACKED_UP"},payloads
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True);p.add_argument("--index",required=True)
    a=p.parse_args();root=canonical(a.evidence);index=canonical(a.index)
    need(index==root/'SAFE_INDEX.json',"INDEX_PATH_REQUIRED")
    need(not index.exists(),"INDEX_ALREADY_EXISTS")
    value,_=collect_evidence(root)
    # Exclusive creation preserves a competing or previous evidence index.
    with index.open('x',encoding='utf-8') as output:output.write(json.dumps(value,indent=2)+'\n')
if __name__=="__main__":
    try:main()
    except Exception as e:print("BLOCKED:"+str(e),file=sys.stderr);sys.exit(1)
