"""Build an isolated NVIDIA variant of the existing candidate runtime.

No capture entry, browser, encoder, registry activation, or image installation.
The existing engine still owns rendering; output requires separate integration.
"""
from pathlib import Path
import hashlib
import json
import sys

SOURCE_SHA256 = '4e5357dd9f493911e385608ff52841150ac8bad043002153f9ff02170a765f56'
GUARD_URL = '/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs'

def replace_once(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('NVIDIA_CANDIDATE_ANCHOR_MISMATCH')
    return source.replace(old, new)

def derive(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('NVIDIA_CANDIDATE_SOURCE_PIN_MISMATCH')
    source = raw.decode('utf-8')
    source = replace_once(source, "import * as THREE from '/three.js';",
        "import * as THREE from '/three.js';\nimport {assertNvidiaVulkanContext,validateNativeStability} from '" + GUARD_URL + "';")
    source = replace_once(source, "PRESENTATION_RUNTIME_SCHEMA='WORLD_ENGINE_PRESENTATION_RUNTIME_V2'",
        "PRESENTATION_RUNTIME_SCHEMA='WORLD_ENGINE_NVIDIA_PRESENTATION_RUNTIME_V1'")
    source = replace_once(source, "const debug=gl.getExtension('WEBGL_debug_renderer_info'),backend=String(gl.getParameter(debug?debug.UNMASKED_RENDERER_WEBGL:gl.RENDERER));\n assert(backend.includes('SwiftShader'),'UP2_FREE_SOFTWARE_BACKEND_REQUIRED');",
        "const{backend}=assertNvidiaVulkanContext(gl);")
    source = replace_once(source, 'let factory,graphics,last,lastBasePixels,disposed=false;',
        'let factory,graphics,last,lastBasePixels,disposed=false,nativeStabilityProof=null;')
    source = replace_once(source, 'nvidiaVerified:false',
        'get nvidiaVerified(){return nativeStabilityProof!==null;}', count=2)
    source = replace_once(source, 'softwareOnly:true', 'softwareOnly:false')
    source = replace_once(source, 'actualGPUVerified:false',
        'get actualGPUVerified(){return nativeStabilityProof!==null;}')
    source = replace_once(source, 'get diagnostic(){return last;},dispose(){',
        'recordNativeStability(proof){validateNativeStability(proof,backend);nativeStabilityProof=copy(proof);},get diagnostic(){return last;},dispose(){')
    # Keep factory/lifecycle, camera, label, source policy, per-pixel/height checks,
    # and async prepareFrame byte-for-byte outside these narrow native changes.
    return source.encode('utf-8')

def write_new(source, destination):
    data = derive(Path(source).read_bytes())
    with Path(destination).open('xb') as out:
        out.write(data)
    return {'sourceSHA256':SOURCE_SHA256,'variantSHA256':hashlib.sha256(data).hexdigest(),
        'bytes':len(data),'nativeGuardURL':GUARD_URL,'installed':False,'gpuVerified':False}

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: derive_runtime.py SOURCE_FILE NEW_OUTPUT_FILE')
    print(json.dumps(write_new(sys.argv[1],sys.argv[2])))
