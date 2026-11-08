"""Check new source pins without a browser, socket, GPU, or prior test suite."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys

def qualify(preserved_repo, context, reference, destination):
    old, ctx, ref, out=map(Path,[preserved_repo,context,reference,destination])
    assert not out.exists(),'FRESH_SOURCE_ONLY_CHECKOUT_REQUIRED'
    meta=json.loads((ctx/'CONTEXT.json').read_text())
    assert meta['imageBuilt'] is False and meta['rawDataIncluded'] is False
    shutil.copytree(old,out)
    shutil.copytree(ctx/'overlay',out,dirs_exist_ok=True)
    root=out/'world-simulation-shorts-engine/recovery'
    for leaf in ['presentation_runtime.mjs','presentation_plan.mjs']:
        shutil.copyfile(ref/('PARENT_'+leaf),root/'universal-presentation-v2'/leaf)
    for row in meta['overlay']:
        b=(out/row['path']).read_bytes()
        assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],'NEW_OVERLAY_PIN_MISMATCH'
    module=(root/'codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs').resolve().as_uri()
    script='import {verifyGeneratedSources} from '+json.dumps(module)+';console.log(JSON.stringify(await verifyGeneratedSources()));'
    result=subprocess.run(['node','--input-type=module','-e',script],check=True,text=True,capture_output=True,timeout=30)
    variants=json.loads(result.stdout)
    assert len(variants)==3
    return {'schema':'WORLD_ENGINE_NEW_NATIVE_SOURCE_PIN_CHECK_V1','status':'SOURCE_ONLY_PIN_PASS',
      'overlayFilesChecked':len(meta['overlay']),'generatedVariants':variants,
      'runtimeManifestSHA256':meta['runtimeManifestSHA256'],'startupManifestSHA256':meta['startupManifestSHA256'],
      'scope':'New additive overlay and three source-variant links in an isolated source checkout; not installed-image qualification',
      'oldTestsRerun':False,'browserStarted':False,'unixSocketAttempted':False,'gpuExecuted':False,'imageBuilt':False}

if __name__=='__main__':
    if len(sys.argv)!=5: raise SystemExit('PRESERVED_REPOSITORY NEW_CONTEXT PARENT_REFERENCE NEW_DESTINATION')
    print(json.dumps(qualify(*sys.argv[1:]),indent=2))
