"""New missing startup boundary checks, never the prior JSON reader suite."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

def main(destination):
    destination=destination.resolve()
    prepare.need(not destination.exists(),'FRESH_TEST_DESTINATION_REQUIRED')
    raw,startup=prepare.candidate()
    worker=(HERE/'baseline/worker.py').read_bytes()
    prepare.need(prepare.sha(worker)=='75edd4919e545b06f0bab139a3ad106f11a26f072896a8cf4f1983165b0157b0','UNCHANGED_WORKER_PIN')
    for name,data in [('bootstrap.py',raw),('STARTUP_MANIFEST.json',startup),('worker.py',worker)]:
        prepare.write(destination/name,data)
    module=load('_v14_new_startup_check',destination/'bootstrap.py')
    bundle=module.verify_startup(destination/'STARTUP_MANIFEST.json',prepare.sha(startup))
    prepare.need(bundle['runtimeManifestSHA256']==module.SOURCE_SHA==prepare.RUNTIME_PIN,'SOURCE_PIN_LINK')
    child=load('_v14_unchanged_child_check',destination/'worker.py')
    prepare.need(child.bootstrap(destination/'STARTUP_MANIFEST.json',prepare.sha(startup)).SOURCE_SHA==prepare.RUNTIME_PIN,'CHILD_BOOTSTRAP_LINK')
    try: module.verify_startup(destination/'STARTUP_MANIFEST.json','0'*64)
    except RuntimeError as error: prepare.need(str(error)=='COLD_START_MANIFEST_CHANGED','HASH_GUARD_CHANGED')
    else: raise RuntimeError('HASH_GUARD_BYPASSED')
    result={'status':'PASS','checks':['exact assignment-only AST delta','real parent startup manifest verification','real child bootstrap verification','wrong startup hash rejected'],
        'bootstrapSHA256':prepare.sha(raw),'startupSHA256':prepare.sha(startup),
        'runtimeManifestSHA256':prepare.RUNTIME_PIN,'oldPASSReruns':0,'gpuStarts':0,'renders':0,
        'scope':'Previously missing parent/child startup boundary only; actual container ENTRYPOINT pending'}
    prepare.write(HERE/'evidence/CPU_RESULT.json',prepare.encoded(result))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
