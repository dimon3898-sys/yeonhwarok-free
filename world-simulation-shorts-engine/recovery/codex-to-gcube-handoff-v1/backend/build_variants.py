"""Versioned, fail-closed adapter derivation; never edits original sources."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent.parent
UP2=HERE.parent/'universal-presentation-v2'
PINS={
    'capture_presentation.mjs':'fc17ceb56499184a6f4ae6888d617f7b1b67e4fd508320eb295493161596753e',
    'presentation_runtime.mjs':'631d69debd02ed24584a72499febc5f541d3adcfc411095906c444c03e90d0a6',
    'region_source.mjs':'bf89be2fa74d3b55f6651106cb35171c10ceaffd802bb505dbd3d31cca2bd008',
}

def replace(source,old,new,count=1):
    actual=source.count(old)
    if actual!=count:
        raise RuntimeError('GCUBE_VARIANT_UNIQUE_ANCHOR_REQUIRED:'+str(count)+':'+str(actual))
    return source.replace(old,new)

def derive_capture(source):
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
    source=replace(source,"const request=JSON.parse(raw);", "const request=JSON.parse(raw);check(request.totalFrames===180,'GCUBE_EXACT_180_FRAMES_REQUIRED');")
    source=replace(source,"['/recovery/universal-presentation-v2/',HERE]", "['/recovery/universal-presentation-v2/',path.join(ENGINE,'recovery/universal-presentation-v2')],['/recovery/codex-to-gcube-handoff-v1/',HERE]")
    source=replace(source,"schema:'WORLD_ENGINE_PRESENTATION_CAPTURE_V2'", "schema:'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1'")
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
    source=replace(source,"schema:'WORLD_ENGINE_PRESENTATION_FRAMES_V2'", "schema:'WORLD_ENGINE_NVIDIA_PRESENTATION_FRAMES_V1'")
    source=replace(source,"   check(stream?.codec_name==='h264'", "   check(probe.streams.filter(s=>s.codec_type==='video').length===1&&!probe.streams.some(s=>s.codec_type==='audio'),'GCUBE_SILENT_SINGLE_VIDEO_STREAM_REQUIRED');\n   check(stream?.codec_name==='h264'")
    start=source.index("if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){")
    source=source[:start]+"// Library-only derived adapter; the gated capture_nvidia.mjs entry owns execution.\n"
    return source

def derive_runtime(source):
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

if __name__=='__main__':main()
