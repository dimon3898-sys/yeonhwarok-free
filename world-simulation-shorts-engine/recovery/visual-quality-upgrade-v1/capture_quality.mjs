/** Fixed dependency adapter over the persisted ASTRA capture/encoding implementation.
 * Node's official synchronous module hooks select only one exact runtime edge.
 * Neither original source bytes nor a final framebuffer are rewritten.
 */
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {registerHooks} from 'node:module';
import {open,lstat,rename,unlink} from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
export const originalCaptureURL=new URL('../astra-gpu-activation-v1/capture_astra.mjs',import.meta.url).href;
export const qualityRuntimeURL=new URL('./quality_runtime.mjs',import.meta.url).href;

/** Only the captured module's literal saved-runtime dependency can be remapped. */
export function resolveQualityCapture(specifier,context,nextResolve){
 if(context.parentURL===originalCaptureURL&&specifier==='./astra_runtime.mjs')
  return {url:qualityRuntimeURL,shortCircuit:true};
 return nextResolve(specifier,context);
}
export function assertQualityCaptureReport(report){
 assert.equal(report.status,'CAPTURE_TECHNICAL_PASS');assert.equal(report.astraApplied,true);
 assert.equal(report.astraProfileId,'VISUAL_QUALITY_UPGRADE_V1_F');
 const quality=report.runtime?.quality;
 assert.equal(quality?.profile,'F','INTEGRATED_QUALITY_RUNTIME_REQUIRED');
 assert.match(quality.cameraSceneSha256,/^[a-f0-9]{64}$/);
 assert.match(quality.profileSha256,/^[a-f0-9]{64}$/);assert.equal(quality.testOnly,false);
 const evidence=report.runtime.evidence;
 assert.equal(evidence.terrainPass.version,'ASTRA_VALID_SUPPORT_FEATHER_V1','QUALITY_BOUNDARY_FACTORY_REQUIRED');
 assert.equal(evidence.terrainPass.astra.boundary.enabled,true);
 assert.equal(evidence.territoryPass.qualityTerritory.expressionChanged,true,'QUALITY_TERRITORY_FACTORY_REQUIRED');
 assert.equal(report.frames.length,150);
 for(let frame=0;frame<150;frame++){
  const row=report.frames[frame],actual=row.diagnostic?.qualityActivation;
  assert.equal(row.frame,frame);assert.equal(actual?.profile,'F','QUALITY_FRAME_SELECTION_REQUIRED');
  assert.equal(actual.cameraSceneSha256,quality.cameraSceneSha256,'QUALITY_FRAME_CAMERA_BINDING_MISMATCH');
  assert.equal(actual.profileSha256,quality.profileSha256,'QUALITY_FRAME_PROFILE_BINDING_MISMATCH');
  assert.equal(actual.testOnly,false);
  assert.equal(row.diagnostic.terrain.version,'ASTRA_VALID_SUPPORT_FEATHER_V1');
  assert.equal(row.diagnostic.terrain.astra.boundary.enabled,true);
  assert.equal(row.diagnostic.territory.graphics.qualityTerritory.expressionChanged,true);
 }
 return true;
}

/** Invalidate only this fresh private capture if the new quality contract fails. */
export async function invalidateQualityCapture(report,options){
 assert.ok(typeof options?.outputRoot==='string'&&path.isAbsolute(options.outputRoot),'QUALITY_PRIVATE_ROOT_REQUIRED');
 assert.match(report.signature,/^[a-f0-9]{64}$/);
 const directory=path.join(options.outputRoot,'captures',report.signature),uid=process.getuid();
 let cursor=path.parse(directory).root;
 for(const component of directory.slice(cursor.length).split(path.sep)){
  cursor=path.join(cursor,component);const entry=await lstat(cursor);
  assert.ok(entry.isDirectory()&&!entry.isSymbolicLink(),'QUALITY_CAPTURE_PATH_UNSAFE');
  assert.ok([0,uid].includes(entry.uid)&&(!(entry.mode&0o022)||(entry.uid===0&&(entry.mode&0o1000))),
   'QUALITY_CAPTURE_PARENT_UNSAFE');
 }
 const unit=await open(directory,constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);
 try{
  const attrs=await unit.stat();assert.equal(attrs.uid,uid);assert.equal(attrs.mode&0o777,0o700);
  const anchor='/proc/self/fd/'+unit.fd,existing=await open(anchor+'/REPORT.json',
   constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  let data,identity;
  try{identity=await existing.stat();assert.ok(identity.isFile()&&identity.nlink===1&&identity.uid===uid
   &&(identity.mode&0o777)===0o600&&identity.size<=64*1024*1024);
   data=JSON.parse(await existing.readFile('utf8'));
  }finally{await existing.close();}
  assert.equal(data.signature,report.signature);assert.equal(data.astraProfileId,report.astraProfileId);
  assert.equal(data.activationSha256,report.activationSha256);assert.equal(data.status,'CAPTURE_TECHNICAL_PASS');
  const current=await lstat(anchor+'/REPORT.json');assert.equal(current.ino,identity.ino);assert.equal(current.dev,identity.dev);
  async function replace(name,value){
   const temporary=anchor+'/.quality-blocked-'+randomUUID()+'.json',file=await open(temporary,
    constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
   try{await file.writeFile(JSON.stringify(value)+'\n');await file.sync();}finally{await file.close();}
   try{await rename(temporary,anchor+'/'+name);}finally{await unlink(temporary).catch(error=>{if(error.code!=='ENOENT')throw error;});}
  }
  await replace('REPORT.json',{...data,status:'BLOCKED',error:'QUALITY_CAPTURE_VALIDATION_FAILED',
   qualityValidation:'BLOCKED',completedAt:new Date().toISOString()});
  await replace('CAPTURE_STATUS.json',{signature:report.signature,status:'BLOCKED',
   error:'QUALITY_CAPTURE_VALIDATION_FAILED',lastFrame:(data.frames?.length??0)-1,profile:'QUALITY_F'});
  await unit.sync();
 }finally{await unit.close();}
}

async function verifyExtension(){
 const result=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'prepare_quality.py'),
  '--verify-extension'],{maxBuffer:1024*1024})).stdout);
 assert.equal(result.status,'PASS');assert.match(result.manifestSha256,/^[a-f0-9]{64}$/);return result;
}
export async function captureQuality(options){
 const before=await verifyExtension();
 const hook=registerHooks({resolve:resolveQualityCapture});
 let inherited;
 try{inherited=await import(originalCaptureURL);}finally{hook.deregister();}
 const report=await inherited.captureAstra(options);
 try{
  assertQualityCaptureReport(report);
  assert.deepEqual(await verifyExtension(),before,'QUALITY_EXTENSION_CHANGED_DURING_CAPTURE');
 }catch(error){
  try{await invalidateQualityCapture(report,options);}catch(persistError){
   console.error(JSON.stringify({schema:'WORLD_ENGINE_QUALITY_CAPTURE_V1',status:'BLOCKED',
    errorCode:'QUALITY_CAPTURE_VALIDATION_FAILED',qualityStatePersisted:false,gpuRenderingVerified:false}));
  }
  throw error;
 }
 console.log(JSON.stringify({schema:'WORLD_ENGINE_QUALITY_CAPTURE_V1',status:'CAPTURE_TECHNICAL_PASS',
  profile:'VISUAL_QUALITY_UPGRADE_V1_F',captureId:report.signature,
  sourceSignature:report.runtimeSourceSignature,visualQualityVerified:false}));
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={};
  while(args.length){const key=args.shift();assert.ok(['--admission-file','--output-root'].includes(key)&&args.length,
   'EXPLICIT_RENDER_ARGUMENTS_REQUIRED');assert.ok(!Object.hasOwn(options,key),'DUPLICATE_RENDER_ARGUMENT');options[key]=args.shift();}
  await captureQuality({admissionFile:options['--admission-file'],outputRoot:options['--output-root']});
 }catch(error){console.error(JSON.stringify({schema:'WORLD_ENGINE_QUALITY_CAPTURE_V1',status:'BLOCKED',
  errorCode:/^[A-Z][A-Z0-9_]{1,95}$/.test(error?.message??'')?error.message:'QUALITY_CAPTURE_FAILED',
  gpuRenderingVerified:false,visualQualityVerified:false}));process.exitCode=2;}
}
