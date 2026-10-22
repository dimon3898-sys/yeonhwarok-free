"""Rebind only terrain plan/pins in a new copy of the immutable source package."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parents[1]
OLD=HERE.parent/'universal-source-pipeline-v2'

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()

def build(native_file,destination):
    if destination.exists():raise ValueError('RECOVERY_SOURCE_ROOT_MUST_BE_NEW')
    original=load('_recovery_fixture_source_store',OLD/'tools/source_fixture_store.py')
    original.restore(destination)
    before={f.relative_to(destination).as_posix():sha(f.read_bytes()) for f in destination.rglob('*') if f.is_file()}
    native=json.loads(native_file.read_bytes());raw=canonical(native)
    (destination/'demo/NATIVE.json').write_bytes(raw)
    bundle=json.loads((destination/'demo/BUNDLE.json').read_bytes());bundle['native']['sha256']=sha(raw)
    raw=canonical(bundle);(destination/'demo/BUNDLE.json').write_bytes(raw)
    index=json.loads((destination/'INDEX.json').read_bytes());index['packages']['synthetic_zones_v2']['sha256']=sha(raw)
    (destination/'INDEX.json').write_bytes(canonical(index))
    changed=[name for name,digest in before.items() if sha((destination/name).read_bytes())!=digest]
    if set(changed)!={'INDEX.json','demo/BUNDLE.json','demo/NATIVE.json'}:
        raise ValueError('RECOVERY_UNEXPECTED_SOURCE_GEOMETRY_CHANGE')
    scene=OLD/'fixtures/DEMO_SOURCE_SCENE.json';target=HERE/'fixtures/DEMO_SOURCE_SCENE.json'
    if target.exists():raise ValueError('RECOVERY_SCENE_REFUSE_OVERWRITE')
    shutil.copyfile(scene,target)
    pack=load('_recovery_fixture_packager',OLD/'tools/package_fixture.py')
    pin=pack.package(destination,HERE/'fixtures/SOURCE_BUNDLE.zip',HERE/'fixtures/SOURCE_CATALOG_PIN.json')
    report={'schema':'WORLD_ENGINE_G2_RECOVERY_FIXTURE_REBIND_V1','status':'PASS',
        'oldCatalogPin':json.loads((OLD/'fixtures/SOURCE_CATALOG_PIN.json').read_bytes()),'newCatalogPin':pin,
        'sourcePayloadFiles':len(before),'changedPayloads':changed,'unchangedPayloads':len(before)-len(changed),
        'sourceOwnerFrontGeometryOrDatesChanged':False,'cameraOrPaletteOrSceneChanged':False,
        'sceneSHA256':sha(target.read_bytes()),'nativeInputSHA256':sha(native_file.read_bytes()),
        'nativeCanonicalSHA256':sha((destination/'demo/NATIVE.json').read_bytes()),
        'sourceRoot':str(destination),'requiredTempOnly':0}
    (HERE/'reports/FIXTURE_REBIND.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','sourceRoot':str(destination),'indexSHA256':pin['indexSHA256'],'unchangedSourcePayloads':len(before)-len(changed)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();build(a.native,a.destination)
