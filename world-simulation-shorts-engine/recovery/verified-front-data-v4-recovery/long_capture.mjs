/** Fixed native-manager shim: one image-local, hash-bound archival capture. */
import assert from 'node:assert/strict';
import {readFile,lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export const root=path.dirname(fileURLToPath(import.meta.url));
const digest=raw=>createHash('sha256').update(raw).digest('hex'),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const keys=['planFile','expectedPlanSha256','sceneId','admissionFile','outputRoot'];
async function localFile(name){
 const file=path.join(root,name);
 assert.ok(!(await lstat(file)).isSymbolicLink(),'FRONT_EXECUTION_FIXED_FILE_SYMLINK_FORBIDDEN');
 const info=await lstat(file);assert.ok(info.isFile()&&info.size>0&&info.size<=16*1024*1024,'FRONT_EXECUTION_BOUNDED_FIXED_FILE_REQUIRED');
 return{file,raw:await readFile(file)};
}
export async function fixedCaptureOptions(options){
 assert.ok(options&&Object.keys(options).length===keys.length&&keys.every(key=>typeof options[key]==='string'&&options[key]),'FRONT_EXECUTION_FIXED_CAPTURE_ARGUMENTS_REQUIRED');
 const manifestRecord=await localFile('FRONT_FILES.json'),manifest=JSON.parse(manifestRecord.raw);
 assert.equal(manifest.schema,'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4','FRONT_EXECUTION_SOURCE_MANIFEST_REQUIRED');
 assert.equal(manifest.profileId,'VERIFIED_ARCHIVAL_FRONT_V4','FRONT_EXECUTION_PROFILE_REQUIRED');
 for(const name of ['long_capture.mjs','front_capture.mjs','front_runtime.mjs','FRONT_PROFILE.json']){
  const record=await localFile(name);assert.ok(hex(manifest.files?.[name]),'FRONT_EXECUTION_CAPTURE_SOURCE_NOT_MANIFESTED');
  assert.equal(digest(record.raw),manifest.files[name],'FRONT_EXECUTION_CAPTURE_SOURCE_CHANGED');
 }
 return{...options,frontProfileFile:path.join(root,'FRONT_PROFILE.json'),expectedFrontProfileSha256:manifest.files['FRONT_PROFILE.json'],
  frontManifestFile:manifestRecord.file,expectedFrontManifestSha256:digest(manifestRecord.raw)};
}
export async function captureLongScene(options){
 const bound=await fixedCaptureOptions(options),capture=await import(new URL('./front_capture.mjs',import.meta.url).href);
 return capture.captureLongScene(bound);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={},mapping={'--plan-file':'planFile','--plan-sha256':'expectedPlanSha256',
   '--scene-id':'sceneId','--admission-file':'admissionFile','--output-root':'outputRoot'};
  while(args.length){const flag=args.shift();assert.ok(mapping[flag]&&args.length&&!Object.hasOwn(options,mapping[flag]),'FRONT_EXECUTION_EXPLICIT_ARGUMENT_REQUIRED');options[mapping[flag]]=args.shift();}
  const report=await captureLongScene(options);console.log(JSON.stringify({status:report.status,path:report.video.path,sha256:report.video.sha256,
   sceneId:report.sceneId,frames:report.completedFrames,archivalFrontProfile:'VERIFIED_ARCHIVAL_FRONT_V4',visualQualityVerified:false}));
 }catch(error){const code=/^[A-Z][A-Z0-9_]{2,95}$/.test(error?.message??'')?error.message:'FRONT_EXECUTION_CAPTURE_FAILED';
  console.error(JSON.stringify({schema:'WORLD_ENGINE_ARCHIVAL_FRONT_EXECUTION_FAILURE_V4',status:'BLOCKED',errorCode:code,gpuRenderingVerified:false}));process.exitCode=2;}
}
