"""Versioned, fail-closed adapter derivation; never edits original sources."""
from pathlib import Path
import difflib
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent.parent
UP2=HERE.parent/'universal-presentation-v2'
PINS={
    'capture_presentation.mjs':'fc17ceb56499184a6f4ae6888d617f7b1b67e4fd508320eb295493161596753e',
    'presentation_runtime.mjs':'62461ee8f49265554d3858848ec106586937e62ae4fb3ce90c39a96909266d72',
    'region_source.mjs':'bf89be2fa74d3b55f6651106cb35171c10ceaffd802bb505dbd3d31cca2bd008',
}

def replace(source,old,new,count=1):
    actual=source.count(old)
    if actual!=count:
        raise RuntimeError('GCUBE_VARIANT_UNIQUE_ANCHOR_REQUIRED:'+str(count)+':'+str(actual))
    return source.replace(old,new)

def derive_capture(source):
    source=replace(source,"check(Number.isSafeInteger(request.totalFrames)&&request.totalFrames>=2&&request.totalFrames<=240,'UP2_RUNTIME_TOTAL_FRAMES');", "check([6,10].includes(request.durationSeconds===undefined?6:request.durationSeconds)&&request.totalFrames===(request.durationSeconds===undefined?6:request.durationSeconds)*30,'UP2_RUNTIME_TOTAL_FRAMES');")
    source=replace(source,"return{schema:'WORLD_ENGINE_PREPARED_PRESENTATION_V2',totalFrames:request.totalFrames", "return{schema:'WORLD_ENGINE_PREPARED_PRESENTATION_V2',...(request.durationSeconds===10?{durationSeconds:10}:{}),totalFrames:request.totalFrames")
    old_private="async function newPrivateRoot(root){check(typeof root==='string'&&path.isAbsolute(root)&&within(root,'/workspace')&&!within(root,REPO),'UP2_NEW_PRIVATE_ROOT_REQUIRED');for(let p=path.dirname(root);p!==path.dirname(p);p=path.dirname(p)){const stat=await lstat(p);check(stat.isDirectory()&&!stat.isSymbolicLink()&&!(stat.mode&0o022),'UP2_PRIVATE_ROOT_ANCESTOR_UNSAFE');}await mkdir(root,{mode:0o700});const stat=await lstat(root);check(stat.isDirectory()&&!stat.isSymbolicLink()&&stat.uid===process.getuid()&&!(stat.mode&0o077),'UP2_PRIVATE_ROOT_PERMISSIONS');}"
    source=replace(source,old_private,"// New profile only: explicit qualified POSIX root, never inferred /workspace.\n")
    source=replace(source,"import {compilePresentationCameraPlan,assertPresentationBoundaryContinuity} from './presentation_plan.mjs';", "import {compilePresentationCameraPlan,assertPresentationBoundaryContinuity} from '../universal-presentation-v2/presentation_plan.mjs';\nimport {buildVulkanLaunchOptions} from './backend/profile_contract.mjs';\nimport {createFreshPrivateDirectory as newPrivateRoot} from './backend/private_workspace.mjs';")
    source=replace(source,"from './region_source.mjs';","from './region_source_vulkan.generated.mjs';")
    source=replace(source,"export async function verifyPreparedRuntimeRequest(prepared){", "export async function verifyPreparedRuntimeRequest(prepared,{privateWorkspaceRoot,publicExportRoot}={}){")
    source=replace(source,"verifyRegionQualification({prepared:segment})", "verifyRegionQualification({prepared:segment,privateWorkspaceRoot,publicExportRoot})")
    source=replace(source,"verifyRegionQualification({prepared})", "verifyRegionQualification({prepared,privateWorkspaceRoot,publicExportRoot})",2)
    source=replace(source,"outputRoot:path.join(cacheRoot,'segment-'+String(index).padStart(3,'0'))", "outputRoot:path.join(cacheRoot,'segment-'+String(index).padStart(3,'0')),privateWorkspaceRoot,publicExportRoot")
    source=replace(source,"export async function prepareRuntimeRequest({request,cacheRoot}={}){", "export async function prepareRuntimeRequest({request,cacheRoot,privateWorkspaceRoot,publicExportRoot}={}){")
    source=replace(source,"await newPrivateRoot(cacheRoot);", "await newPrivateRoot(cacheRoot,{privateWorkspaceRoot,publicExportRoot});")
    source=replace(source,"export async function capturePresentation({packageFile,outputRoot,expectedSHA256,expectedSourceQualificationSHA256,depsRoot=process.env.WORLD_ENGINE_NODE_DEPS,probeFrames=null,prepareOnly=false}={}){", "export async function captureVulkanDerived({packageFile,outputRoot,expectedSHA256,expectedSourceQualificationSHA256,depsRoot=process.env.WORLD_ENGINE_NODE_DEPS,probeFrames=null,prepareOnly=false,rootTestOnly=false,executionDeadline,privateWorkspaceRoot,publicExportRoot}={}){\n check(!prepareOnly&&probeFrames===null&&Number.isFinite(executionDeadline),'GCUBE_FULL_CAPTURE_AUTHORITY_REQUIRED');\n check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');")
    source=replace(source,"await newPrivateRoot(outputRoot);const payload=await prepareRuntimeRequest({request,cacheRoot:path.join(outputRoot,'sources')});", "await newPrivateRoot(outputRoot,{privateWorkspaceRoot,publicExportRoot});const payload=await prepareRuntimeRequest({request,cacheRoot:path.join(outputRoot,'sources'),privateWorkspaceRoot,publicExportRoot});")
    source=replace(source,"const request=JSON.parse(raw);", "const request=JSON.parse(raw);check([6,10].includes(request.durationSeconds===undefined?6:request.durationSeconds)&&request.totalFrames===(request.durationSeconds===undefined?6:request.durationSeconds)*30,'GCUBE_EXACT_180_FRAMES_REQUIRED');")
    source=replace(source,"['/recovery/universal-presentation-v2/',HERE]", "['/recovery/universal-presentation-v2/',path.join(ENGINE,'recovery/universal-presentation-v2')],['/recovery/codex-to-gcube-handoff-v1/',HERE]")
    source=replace(source,"schema:'WORLD_ENGINE_PRESENTATION_CAPTURE_V2'", "schema:request.durationSeconds===10?'WORLD_ENGINE_NVIDIA_TEN_SECOND_CAPTURE_V1':'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1',...(request.durationSeconds===10?{durationSeconds:10}:{})")
    source=replace(source,"renderedFrames:0,softwareOnly:true,nvidiaVerified:false", "renderedFrames:0,softwareOnly:false,nvidiaVerified:false")
    source=replace(source,"paidExecuted:false", "paidExecutionAttempted:false,providerBillingStopControlled:false")
    launch="browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});"
    source=replace(source,launch,"check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');const launchProfile=buildVulkanLaunchOptions({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']},{uid:process.getuid(),rootTestOptIn:rootTestOnly});receipt.browserProfile=launchProfile.evidence;receipt.paidExecutionAttempted=true;browser=await chromium.launch(launchProfile.options);")
    source=replace(source,"window.createRuntime=(await import('/recovery/universal-presentation-v2/presentation_runtime.mjs')).createPresentationRuntime", "window.createRuntime=(await import('/recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs')).createNvidiaPresentationRuntime")
    marker="  const frames=probeFrames??Array.from({length:request.totalFrames},(_,i)=>i),"
    guard="""  const firstNativeProof=await page.evaluate(async()=>{
   const first=window.payload.segments[0];if(first.startFrame!==0)throw Error('GCUBE_INITIAL_SEGMENT_REQUIRED');
   const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);
   window.runtime=await window.createRuntime({canvas,...first});window.currentSegment=0;
   const{runThreeNativeDraws}=await import('/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs');
   const proof=await runThreeNativeDraws({runtime:window.runtime,canvas});return{proof,evidence:window.runtime.evidence};
  });
  receipt.nativeStability=[{segmentIndex:0,...firstNativeProof.proof}];receipt.nvidiaVerified=true;receipt.actualGpuDrawVerified=true;
  runtimeEvidence.push({segmentIndex:0,...firstNativeProof.evidence,nativeStability:firstNativeProof.proof});
"""
    source=replace(source,marker,guard+marker)
    source=replace(source,"for(const frame of frames){const capture=await page.evaluate", "for(const frame of frames){check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');const capture=await page.evaluate")
    source=replace(source,"window.currentSegment=index;initialized=window.runtime.evidence;", "window.currentSegment=index;const{runThreeNativeDraws}=await import('/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs');const proof=await runThreeNativeDraws({runtime:window.runtime,canvas});initialized={...window.runtime.evidence,nativeStability:proof};")
    source=replace(source,"if(capture.initialized)runtimeEvidence.push({segmentIndex:capture.segmentIndex,...capture.initialized});", "if(capture.initialized){runtimeEvidence.push({segmentIndex:capture.segmentIndex,...capture.initialized});receipt.nativeStability.push({segmentIndex:capture.segmentIndex,...capture.initialized.nativeStability});}")
    source=replace(source,"schema:'WORLD_ENGINE_PRESENTATION_FRAMES_V2'", "schema:'WORLD_ENGINE_NVIDIA_PRESENTATION_FRAMES_V1',...(request.durationSeconds===10?{durationSeconds:10,totalFrames:300}:{})")
    source=replace(source,"   check(stream?.codec_name==='h264'", "   check(probe.streams.filter(s=>s.codec_type==='video').length===1&&!probe.streams.some(s=>s.codec_type==='audio'),'GCUBE_SILENT_SINGLE_VIDEO_STREAM_REQUIRED');\n   check(stream?.codec_name==='h264'")
    start=source.index("if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){")
    source=source[:start]+"// Library-only derived adapter; the gated capture_nvidia.mjs entry owns execution.\n"
    return source

def derive_runtime(source):
    source=replace(source,"from './presentation_label_layer.mjs';", "from '../universal-presentation-v2/presentation_label_layer.mjs';")
    source=replace(source,"from './presentation_plan.mjs';", "from '../universal-presentation-v2/presentation_plan.mjs';\nimport {assertNvidiaVulkanContext,validateNativeStability} from './backend/native_guard.mjs';")
    source=replace(source,"PRESENTATION_RUNTIME_SCHEMA='WORLD_ENGINE_PRESENTATION_RUNTIME_V2'", "PRESENTATION_RUNTIME_SCHEMA='WORLD_ENGINE_NVIDIA_PRESENTATION_RUNTIME_V1'")
    source=replace(source,"export async function createPresentationRuntime(","export async function createNvidiaPresentationRuntime(")
    old="const debug=gl.getExtension('WEBGL_debug_renderer_info'),backend=String(gl.getParameter(debug?debug.UNMASKED_RENDERER_WEBGL:gl.RENDERER));\n assert(backend.includes('SwiftShader'),'UP2_FREE_SOFTWARE_BACKEND_REQUIRED');"
    source=replace(source,old,"const{backend}=assertNvidiaVulkanContext(gl);")
    source=replace(source,"let factory,graphics,last,lastBasePixels,disposed=false;", "let factory,graphics,last,lastBasePixels,disposed=false,nativeStabilityProof=null;")
    source=replace(source,"nvidiaVerified:false", "get nvidiaVerified(){return nativeStabilityProof!==null;}",2)
    source=replace(source,"softwareOnly:true", "softwareOnly:false")
    source=replace(source,"actualGPUVerified:false", "get actualGPUVerified(){return nativeStabilityProof!==null;}")
    source=replace(source,"get diagnostic(){return last;},dispose(){", "recordNativeStability(proof){validateNativeStability(proof,backend);nativeStabilityProof=copy(proof);},get diagnostic(){return last;},dispose(){")
    # Preserve the already deployed diagnostic adapter when deriving the label
    # runtime; regenerating an uninstrumented variant would discard evidence.
    source=replace(source,"inputTrace=null}={}){", "inputTrace=null,diagnostics=null}={}){\n const observe=(operation,task)=>diagnostics?diagnostics.run(operation,task,{sourceId:'PRESENTATION_RUNTIME'}):task();")
    source=replace(source,"const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});assert(gl,'UP2_WEBGL2_REQUIRED');", "const gl=await observe('WEBGL_CONTEXT',()=>{const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});assert(gl,'UP2_WEBGL2_REQUIRED');return gl;});")
    source=replace(source,"const{backend}=assertNvidiaVulkanContext(gl);", "const{backend}=await observe('RENDERER_IDENTIFICATION',()=>assertNvidiaVulkanContext(gl));")
    source=replace(source,"factory=await createMapInfographicRenderer({canvas,plan:nativePlan,layoutPlan:nativePlan,outputRenderer:renderer,terrainTreatment});", "factory=await observe('MAP_TEXTURE_PREPARATION',()=>createMapInfographicRenderer({canvas,plan:nativePlan,layoutPlan:nativePlan,outputRenderer:renderer,terrainTreatment}));")
    source=replace(source,"graphics=await createMovingGraphicPass({renderer,factory,width:1080,height:1920});", "graphics=await observe('GRAPHICS_PREPARATION',()=>createMovingGraphicPass({renderer,factory,width:1080,height:1920}));")
    source=replace(source,"}catch(error){passes.forEach(pass=>pass.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();throw error;}", "}catch(error){if(diagnostics){await diagnostics.cleanup(()=>passes.forEach(pass=>pass.dispose()));await diagnostics.cleanup(()=>graphics?.dispose());await diagnostics.cleanup(()=>factory?.dispose());await diagnostics.cleanup(()=>renderer.dispose());}\n  else{passes.forEach(pass=>pass.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();}throw error;}")
    return source

def derive_region(source):
    source=replace(source,"import {promisify} from 'node:util';", "import {promisify} from 'node:util';\nimport {assertPrivateWorkspace,assertQualifiedPrivatePath,ensureQualifiedPrivateDirectory} from './backend/private_workspace.mjs';")
    source=replace(source,"const CATALOG=path.join(HERE,'REGION_SOURCE_CATALOG.json')", "const CATALOG=path.join(HERE,'../universal-presentation-v2/REGION_SOURCE_CATALOG.json')")
    start=source.index('async function safeCacheRoot(value){')
    end=source.index('\n}\n',start)+3
    original=source[start:end]
    if "within(value,'/workspace')" not in original or original.count('async function')!=1:
        raise RuntimeError('GCUBE_REGION_CACHE_ANCHOR_INVALID')
    source=replace(source,original,"async function safeCacheRoot(value,options){return ensureQualifiedPrivateDirectory(value,options);}\n")
    source=replace(source,"export async function prepareRegionTerrain({regionPlan,bounds,outputRoot}={}){", "export async function prepareRegionTerrain({regionPlan,bounds,outputRoot,privateWorkspaceRoot,publicExportRoot}={}){")
    source=replace(source,"cache=await safeCacheRoot(outputRoot);", "cache=await safeCacheRoot(outputRoot,{privateWorkspaceRoot,publicExportRoot});")
    source=replace(source,"export async function verifyRegionQualification({prepared,qualification}={}){", "export async function verifyRegionQualification({prepared,qualification,privateWorkspaceRoot,publicExportRoot}={}){")
    source=replace(source,"  const e=prepared.regionEvidence;", "  await assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot});\n  const e=prepared.regionEvidence;")
    source=replace(source,"dir=path.dirname(png);check(within(png,'/workspace')&&!within(png,REPO)", "dir=path.dirname(png);await assertQualifiedPrivatePath(dir,{privateWorkspaceRoot,publicExportRoot});check(within(png,privateWorkspaceRoot)&&png!==privateWorkspaceRoot&&!within(png,REPO)")
    return source

def verify_existing():
    """Read-only packaging gate; do not regenerate historical variants/patches."""
    repo=HERE.parents[2]
    metadata=json.loads((HERE/'backend/GENERATED_SOURCE_MANIFEST.json').read_text())
    targets={'capture_vulkan.generated.mjs':'capture_presentation.mjs',
             'presentation_runtime_vulkan.generated.mjs':'presentation_runtime.mjs',
             'region_source_vulkan.generated.mjs':'region_source.mjs'}
    rows=metadata.get('variants',[])
    if metadata.get('schema')!='WORLD_ENGINE_PINNED_GPU_ADAPTER_VARIANTS_V1' or len(rows)!=len(targets):
        raise RuntimeError('GCUBE_EXISTING_VARIANT_MANIFEST_REQUIRED')
    seen=set()
    for row in rows:
        target=row.get('variant')
        if target not in targets or target in seen:
            raise RuntimeError('GCUBE_EXISTING_VARIANT_SET_MISMATCH')
        seen.add(target)
        original=targets[target]
        expected_original=str((UP2/original).relative_to(repo))
        if row.get('original')!=expected_original or row.get('originalSHA256')!=PINS[original]:
            raise RuntimeError('GCUBE_EXISTING_ORIGINAL_PIN_MISMATCH:'+original)
        for file,expected in [(UP2/original,PINS[original]),(HERE/target,row.get('variantSHA256'))]:
            if file.is_symlink() or not file.is_file():
                raise RuntimeError('GCUBE_EXISTING_REGULAR_SOURCE_REQUIRED')
            if hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('GCUBE_EXISTING_SOURCE_SHA_MISMATCH:'+file.name)
    actual=(HERE/'presentation_runtime_vulkan.generated.mjs').read_bytes()
    candidate=derive_runtime((UP2/'presentation_runtime.mjs').read_bytes().decode()).encode()
    if actual!=candidate:
        raise RuntimeError('GCUBE_EXISTING_RUNTIME_DERIVATION_MISMATCH')
    closure=json.loads((HERE/'RUNTIME_SOURCE_MANIFEST.json').read_text())
    label_hashes={}
    for name in ['presentation_labels.mjs','presentation_label_layer.mjs']:
        file=UP2/name
        relative=str(file.relative_to(repo))
        matches=[row for row in closure['files'] if row.get('path')==relative]
        if len(matches)!=1 or file.is_symlink() or not file.is_file():
            raise RuntimeError('GCUBE_LABEL_SOURCE_ROW_REQUIRED:'+name)
        raw=file.read_bytes()
        if matches[0].get('sha256')!=hashlib.sha256(raw).hexdigest() or matches[0].get('bytes')!=len(raw):
            raise RuntimeError('GCUBE_LABEL_SOURCE_PIN_MISMATCH:'+name)
        label_hashes[name]=hashlib.sha256(raw).hexdigest()
    return {'schema':'WORLD_ENGINE_EXISTING_LABEL_VARIANT_LINKAGE_V1','status':'PASS',
            'scope':'READ_ONLY_EXISTING_VARIANT_PINS_LABEL_MODULES_AND_RUNTIME_DERIVATION',
            'variantRows':len(rows),'runtimeDerivationMatches':True,'labelModuleSHA256':label_hashes,
            'historicalPatchRegeneration':'NOT_RUN','filesWritten':0,'gpuExecuted':False}

def main():
    rows=[]
    for original,derive,target in [
        ('capture_presentation.mjs',derive_capture,'capture_vulkan.generated.mjs'),
        ('presentation_runtime.mjs',derive_runtime,'presentation_runtime_vulkan.generated.mjs'),
        ('region_source.mjs',derive_region,'region_source_vulkan.generated.mjs'),
    ]:
        raw=(UP2/original).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=PINS[original]:
            raise RuntimeError('GCUBE_ORIGINAL_SOURCE_PIN_MISMATCH:'+original)
        candidate=derive(raw.decode()).encode()
        destination=HERE/target
        if destination.exists() and destination.read_bytes()!=candidate:
            raise RuntimeError('GCUBE_GENERATED_VARIANT_ALREADY_DIFFERS')
        if not destination.exists():destination.write_bytes(candidate)
        patch=''.join(difflib.unified_diff(raw.decode().splitlines(True),candidate.decode().splitlines(True),fromfile=original+'@8d2798d',tofile=target))
        patchfile=HERE/'backend'/ (target+'.patch')
        if patchfile.exists() and patchfile.read_text()!=patch:raise RuntimeError('GCUBE_VARIANT_DIFF_ALREADY_DIFFERS')
        if not patchfile.exists():patchfile.write_text(patch)
        rows.append({'original':str((UP2/original).relative_to(HERE.parents[2])), 'originalSHA256':PINS[original], 'variant':target,'variantSHA256':hashlib.sha256(candidate).hexdigest(),'diff':str(patchfile.relative_to(HERE)),'oldFileModified':False})
    receipt={'schema':'WORLD_ENGINE_PINNED_GPU_ADAPTER_VARIANTS_V1','profile':'GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1','variants':rows,'defaultSoftwareFilesChanged':False,'coreRendererChanged':False,'actualGPUValidation':'NOT_TESTED','paidGPUExecuted':False}
    manifest=HERE/'backend/GENERATED_SOURCE_MANIFEST.json'
    data=(json.dumps(receipt,indent=2)+'\n').encode()
    if manifest.exists() and manifest.read_bytes()!=data:raise RuntimeError('GCUBE_VARIANT_MANIFEST_ALREADY_DIFFERS')
    if not manifest.exists():manifest.write_bytes(data)
    print(json.dumps(receipt))

if __name__=='__main__':
    if sys.argv[1:]==['--verify-existing']:
        print(json.dumps(verify_existing(),sort_keys=True))
    elif sys.argv[1:]:
        raise RuntimeError('GCUBE_VARIANT_ARGUMENT_UNSUPPORTED')
    else:
        main()
