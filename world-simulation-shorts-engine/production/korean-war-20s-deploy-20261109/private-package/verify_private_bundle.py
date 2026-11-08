"""Focused qualification of the new installer; never launches a renderer."""
from pathlib import Path
import hashlib, json, os, stat, tempfile, zipfile
import private_bundle as install

HERE=Path(__file__).resolve().parent
UID=int(os.environ.get('WORLD_ENGINE_TEST_UID',os.getuid()))
GID=int(os.environ.get('WORLD_ENGINE_TEST_GID',os.getgid()))
sha=lambda b:hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,separators=(',',':'))+'\n').encode()

def fixture(root, name, *, bad_path=False, duplicate=False, symlink=False, bad_file=False):
    archive=root/(name+'.zip'); value=b'private-byte-fixture\n'
    member='../escape.json' if bad_path else 'safe/registry.json'
    manifest=encoded({'schema':install.SCHEMA,'files':[{'path':member,'bytes':len(value),'sha256':('0'*64 if bad_file else sha(value))}]})
    with zipfile.ZipFile(archive,'x') as z:
        zi=zipfile.ZipInfo(member);zi.create_system=3;zi.external_attr=((stat.S_IFLNK if symlink else stat.S_IFREG)|0o600)<<16
        z.writestr(zi,value)
        if duplicate:z.writestr(zi,value)
        z.writestr(install.MANIFEST,manifest)
    return archive,{'schema':install.SCHEMA,'archiveSHA256':sha(archive.read_bytes()),'archiveBytes':archive.stat().st_size,
                    'manifestSHA256':sha(manifest),'files':1,'unpackedBytes':len(value),'roots':['safe'],
                    'registryRelativePath':member,'registrySHA256':sha(value)}

def destination(root,name):
    p=root/name;p.mkdir(mode=0o700);os.chown(p,UID,GID);return p

def main():
    test_parent=Path(os.environ.get('WORLD_ENGINE_TEST_ROOT',str(HERE)))
    root=Path(tempfile.mkdtemp(prefix='installer-check-',dir=test_parent));root.chmod(0o700);os.chown(root,UID,GID)
    results=[]
    for name,options,error in [('traversal',{'bad_path':True},'PATH_INVALID'),
                              ('duplicate',{'duplicate':True},'DUPLICATE_OR_COUNT'),
                              ('symlink',{'symlink':True},'ENTRY_TYPE'),
                              ('content-tamper',{'bad_file':True},'FILE_HASH')]:
        archive,receipt=fixture(root,name,**options);out=destination(root,name+'-out')
        try:install.unpack(archive,receipt,out,uid=UID,gid=GID)
        except RuntimeError as failure:
            assert str(failure)=='PRIVATE_PACKAGE_'+error,(name,str(failure))
            assert not list(out.iterdir());results.append({'name':name,'status':'PASS','code':str(failure)})
        else:raise AssertionError(name)
    archive,receipt=fixture(root,'positive');out=destination(root,'positive-out')
    env=install.unpack(archive,receipt,out,uid=UID,gid=GID)
    target=out/'safe/registry.json';assert target.stat().st_uid==UID and target.stat().st_gid==GID
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    assert stat.S_IMODE(target.parent.stat().st_mode)==0o700
    assert env[install.REGISTRY_KEYS[1]]==sha(target.read_bytes())
    results.append({'name':'owned0700-and600-exact-bytes-and-registry-pin','status':'PASS'})
    try:install.unpack(archive,receipt,out,uid=UID,gid=GID)
    except RuntimeError as failure:
        assert str(failure)=='PRIVATE_PACKAGE_DESTINATION_EXISTS';results.append({'name':'no-overwrite','status':'PASS'})
    else:raise AssertionError('overwrite')
    archive,receipt=fixture(root,'archive-tamper');out=destination(root,'archive-tamper-out')
    with archive.open('r+b') as f:f.seek(8);f.write(b'XX')
    try:install.unpack(archive,receipt,out,uid=UID,gid=GID)
    except RuntimeError as failure:
        assert str(failure)=='PRIVATE_PACKAGE_ARCHIVE_HASH';results.append({'name':'archive-tamper','status':'PASS'})
    else:raise AssertionError('archive-tamper')
    report={'schema':'WORLD_ENGINE_PRIVATE_INSTALLER_QUALIFICATION_V1','status':'PASS','checks':results,
            'priorCPUPassesRerun':False,'networkUsed':False,'gpuExecuted':False,
            'testedUid':UID,'testedGid':GID,'productionUid1000Verified':UID==GID==1000,
            'installerSHA256':sha((HERE/'private_bundle.py').read_bytes())}
    result_path=Path(os.environ.get('WORLD_ENGINE_TEST_RESULT',str(HERE/'PRIVATE_INSTALLER_QUALIFICATION.json')))
    result_path.write_bytes(encoded(report))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
