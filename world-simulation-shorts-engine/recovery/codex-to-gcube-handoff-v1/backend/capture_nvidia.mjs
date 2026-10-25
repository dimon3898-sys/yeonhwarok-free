/** Gated new NVIDIA profile over pinned Studio capture consumers.
 * The authenticated controller/worker owns fresh consent, policy, common GPU
 * lease, source closure, process supervision and delivery. This is not an API.
 */
import {readFile,lstat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {selectBackend,validateExecutionPermit,sha} from './profile_contract.mjs';
import {assertPrivateWorkspace} from './private_workspace.mjs';

const HERE=path.dirname(fileURLToPath(import.meta.url)),ROOT=path.dirname(HERE);
const check=(value,code)=>{if(!value)throw Error(code);};
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);

export async function privateDocument(file,{maximum=24*1024**2}={}){
 check(typeof file==='string'&&path.isAbsolute(file)&&!file.split(path.sep).includes('..'),'HANDOFF_PRIVATE_DOCUMENT_PATH_REQUIRED');
 for(let current=file;;current=path.dirname(current)){
  const stat=await lstat(current);
  check(!stat.isSymbolicLink(),'HANDOFF_DOCUMENT_SYMLINK_FORBIDDEN');
  if(current===file)check(stat.isFile()&&stat.uid===process.getuid()&&!(stat.mode&0o077)&&stat.nlink===1&&stat.size<=maximum,'HANDOFF_PRIVATE_DOCUMENT_REQUIRED');
  else check(stat.isDirectory()&&!(stat.mode&0o022),'HANDOFF_PRIVATE_ANCESTOR_REQUIRED');
  if(current===path.dirname(current))break;
 }
 const raw=await readFile(file);check(raw.length<=maximum,'HANDOFF_EXECUTION_DOCUMENT_TOO_LARGE');
 let value;try{value=JSON.parse(raw);}catch{throw Error('HANDOFF_EXECUTION_JSON_INVALID');}
 return{raw,value};
}

export function validateVariantManifest(metadata){
 check(metadata.schema==='WORLD_ENGINE_PINNED_GPU_ADAPTER_VARIANTS_V1'&&metadata.variants.length===3,'HANDOFF_VARIANT_MANIFEST_REQUIRED');
 const expectedVariants=new Map([
  ['capture_vulkan.generated.mjs',{original:'world-simulation-shorts-engine/recovery/universal-presentation-v2/capture_presentation.mjs',sha256:'fc17ceb56499184a6f4ae6888d617f7b1b67e4fd508320eb295493161596753e'}],
  ['presentation_runtime_vulkan.generated.mjs',{original:'world-simulation-shorts-engine/recovery/universal-presentation-v2/presentation_runtime.mjs',sha256:'631d69debd02ed24584a72499febc5f541d3adcfc411095906c444c03e90d0a6'}],
  ['region_source_vulkan.generated.mjs',{original:'world-simulation-shorts-engine/recovery/universal-presentation-v2/region_source.mjs',sha256:'bf89be2fa74d3b55f6651106cb35171c10ceaffd802bb505dbd3d31cca2bd008'}],
 ]),seen=new Set();
 for(const row of metadata.variants){
  check(typeof row.original==='string'&&row.original.startsWith('world-simulation-shorts-engine/recovery/universal-presentation-v2/')&&!row.original.split('/').includes('..')&&expectedVariants.has(row.variant),'HANDOFF_VARIANT_PATH_INVALID');
  check(hex(row.originalSHA256)&&hex(row.variantSHA256),'HANDOFF_VARIANT_SHA_REQUIRED');
  const expected=expectedVariants.get(row.variant);
  check(expected&&!seen.has(row.variant)&&row.original===expected.original&&row.originalSHA256===expected.sha256,'HANDOFF_EXACT_VARIANT_SET_REQUIRED');seen.add(row.variant);
 }
 check(seen.size===expectedVariants.size,'HANDOFF_EXACT_VARIANT_SET_REQUIRED');
 return metadata.variants;
}
export async function verifyGeneratedSources(){
 const metadata=JSON.parse(await readFile(path.join(HERE,'GENERATED_SOURCE_MANIFEST.json'),'utf8'));
 const rows=validateVariantManifest(metadata),repo=path.resolve(ROOT,'../../..'),actual=[];
 for(const row of rows){
  for(const [file,expected]of [[path.join(repo,row.original),row.originalSHA256],[path.join(ROOT,row.variant),row.variantSHA256]]){
   const stat=await lstat(file);check(stat.isFile()&&!stat.isSymbolicLink(),'HANDOFF_VARIANT_REGULAR_FILE_REQUIRED');
   check(sha(await readFile(file))===expected,'HANDOFF_CAPTURE_SOURCE_CHANGED');
  }
  actual.push({variant:row.variant,sha256:row.variantSHA256});
 }
 return actual;
}

export function classifyCaptureFailure(error){
 const message=typeof error?.message==='string'?error.message:'';
 const code=/^[A-Z][A-Z0-9_]{2,120}$/.test(message)?message:'GCUBE_CAPTURE_RUNTIME_FAILED';
 let stage='RENDER_RUNTIME';
 if(/POLICY|APPROVAL|AUTHORIZATION|COST|PLAN_SHA|PRIVATE_DOCUMENT/.test(code))stage='APPROVAL_OR_INPUT';
 else if(/SOURCE|PACKAGE|VARIANT|FRAME_RANGE|SCENE|QUALIFICATION/.test(code))stage='SOURCE_OR_SCENE';
 else if(/SANDBOX|BROWSER_IDENTITY|EXECUTABLE/.test(code)||error?.code==='EPERM'||error?.code==='EACCES')stage='RUNTIME_PERMISSIONS';
 else if(/NVIDIA|VULKAN|NATIVE_CONTEXT|STABILITY|READBACK/.test(code))stage='GPU_NATIVE_DRAW';
 else if(/ENCODER|VIDEO|DECODE/.test(code))stage='ENCODING_OR_DECODE';
 else if(/DEADLINE|EXPIRED/.test(code))stage='DEADLINE';
 return{code,stage};
}

export async function prepareNvidiaRuntimeRequest({request,cacheRoot,privateWorkspaceRoot,publicExportRoot}={}){
 check(request?.totalFrames===180,'GCUBE_EXACT_180_FRAMES_REQUIRED');
 await assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot});
 await verifyGeneratedSources();
 const {prepareRuntimeRequest}=await import(pathToFileURL(path.join(ROOT,'capture_vulkan.generated.mjs')).href);
 return prepareRuntimeRequest({request,cacheRoot,privateWorkspaceRoot,publicExportRoot});
}

export async function verifyNvidiaPreparedRuntimeRequest({prepared,privateWorkspaceRoot,publicExportRoot}={}){
 await assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot});
 await verifyGeneratedSources();
 const {verifyPreparedRuntimeRequest}=await import(pathToFileURL(path.join(ROOT,'capture_vulkan.generated.mjs')).href);
 return verifyPreparedRuntimeRequest(prepared,{privateWorkspaceRoot,publicExportRoot});
}

export async function captureNvidiaPresentation({packageFile,outputRoot,expectedSHA256,expectedSourceQualificationSHA256,depsRoot,authorizationFile,expectedAuthorizationSHA256,planFile,expectedPlanSHA256,backend='vulkan',rootTestOnly=false,privateWorkspaceRoot,publicExportRoot}={}){
 check(selectBackend({GPU_BACKEND:backend})==='vulkan','HANDOFF_NVIDIA_PROFILE_EXPLICIT_REQUIRED');
 check(typeof rootTestOnly==='boolean','HANDOFF_ROOT_TEST_FLAG_INVALID');
 const [plan,approval,runtime]=await Promise.all([
  privateDocument(planFile),privateDocument(authorizationFile,{maximum:16*1024}),privateDocument(packageFile,{maximum:8*1024**2}),
 ]);
 check(hex(expectedAuthorizationSHA256)&&sha(approval.raw)===expectedAuthorizationSHA256,'HANDOFF_AUTHORIZATION_SHA_MISMATCH');
 const permit=validateExecutionPermit({plan:plan.value,planWire:plan.raw,approval:approval.value,packageWire:runtime.raw,expectedPlanSHA256,expectedPackageSHA256:expectedSHA256});
 check(expectedSourceQualificationSHA256===permit.sourceQualificationSHA256,'HANDOFF_SOURCE_QUALIFICATION_SEAL_REQUIRED');
 await assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot});
 check([packageFile,authorizationFile,planFile,outputRoot].every(file=>typeof file==='string'&&file.startsWith(privateWorkspaceRoot+path.sep)),'HANDOFF_EXECUTION_FILES_PRIVATE_ROOT_REQUIRED');
 // Source variants are checked before importing their executable Node code.
 const variants=await verifyGeneratedSources();
 const {captureVulkanDerived}=await import(pathToFileURL(path.join(ROOT,'capture_vulkan.generated.mjs')).href);
 const receipt=await captureVulkanDerived({packageFile,outputRoot,expectedSHA256,expectedSourceQualificationSHA256,depsRoot,rootTestOnly,executionDeadline:permit.deadlineUnixMilliseconds,privateWorkspaceRoot,publicExportRoot});
 check(receipt.schema==='WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1'&&receipt.status==='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'&&receipt.softwareOnly===false&&receipt.nvidiaVerified===true&&receipt.totalFrames===180&&receipt.renderedFrames===180&&receipt.video?.frames===180&&receipt.video?.fullDecode==='PASS','HANDOFF_HARDWARE_CAPTURE_RECEIPT_REQUIRED');
 await verifyGeneratedSources();
 return{...receipt,executionPermit:{...permit,authorizationSHA256:expectedAuthorizationSHA256},sourceVariants:variants,rootTestOnly,productionEligible:!rootTestOnly,providerBillingStopControlled:false,visualQualityApproved:false};
}

/** Explicit extension entry: absent selector delegates to the exact old path. */
export async function captureWithBackend(options={},environ=process.env){
 const selected=selectBackend(environ);
 if(selected==='swiftshader'){
  const old=await import('../../universal-presentation-v2/capture_presentation.mjs');
  return old.capturePresentation(options);
 }
 return captureNvidiaPresentation({...options,backend:'vulkan'});
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args={};let rootTestOnly=false;
 try{
  for(const arg of process.argv.slice(2)){
   if(arg==='--root-test-no-sandbox'){check(!rootTestOnly,'HANDOFF_DUPLICATE_ARGUMENT');rootTestOnly=true;continue;}
   const match=/^--(package|output-root|expected-sha256|expected-source-qualification-sha256|deps-root|authorization|expected-authorization-sha256|plan-file|expected-plan-sha256|backend|private-workspace-root|public-export-root)=(.+)$/.exec(arg);
   check(match&&!Object.hasOwn(args,match[1]),'HANDOFF_CAPTURE_ARGUMENT_INVALID');args[match[1]]=match[2];
  }
  const result=await captureNvidiaPresentation({packageFile:args.package,outputRoot:args['output-root'],expectedSHA256:args['expected-sha256'],expectedSourceQualificationSHA256:args['expected-source-qualification-sha256'],depsRoot:args['deps-root'],authorizationFile:args.authorization,expectedAuthorizationSHA256:args['expected-authorization-sha256'],planFile:args['plan-file'],expectedPlanSHA256:args['expected-plan-sha256'],backend:args.backend??process.env.GPU_BACKEND,rootTestOnly,privateWorkspaceRoot:args['private-workspace-root'],publicExportRoot:args['public-export-root']});
  process.stdout.write(JSON.stringify({status:result.status,nvidiaVerified:result.nvidiaVerified,renderedFrames:result.renderedFrames,video:result.video,providerBillingStopControlled:false})+'\n');
 }catch(error){process.stderr.write(JSON.stringify({status:'FAILED',...classifyCaptureFailure(error),hardwareResult:'SEE_PRIVATE_CAPTURE_RECEIPT_IF_CREATED'})+'\n');process.exitCode=1;}
}
