/** One exact Node24 runtime edge into the unchanged bounded native capture. */
import assert from 'node:assert/strict';
import {readFile,lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const captureFile=new URL('../universal-auto-video-v2/long_capture.mjs',import.meta.url),
 runtimeFile=new URL('../universal-auto-video-v2/long_runtime.mjs',import.meta.url),
 hashes=new Map([[captureFile.href,'a4a6904dabd9a3306ffeafe0c1b0035f6062af81a56f62a0eb55dd055924d4d0'],
 [runtimeFile.href,'ee50049ad9967b22d5aa7dae09bd9e5295d22882c5d5c3db2b2cd4dec25dc606']]);
// Fixed query ensures the same original bytes have a fresh module instance;
// an earlier software measurement import cannot bypass the one runtime edge.
export const originalCaptureURL=new URL(captureFile.href+'?production-v3-fixed-entry').href,
 productionRuntimeURL=new URL('./long_runtime.mjs',import.meta.url).href;
export function resolveProductionCapture(specifier,context,nextResolve){
 if(context.parentURL===originalCaptureURL&&specifier==='./long_runtime.mjs')
  return{url:productionRuntimeURL,shortCircuit:true};
 return nextResolve(specifier,context);
}
export async function captureLongScene(options){
 assert.equal(process.version,'v24.19.0','PRODUCTION_PINNED_NODE_REQUIRED');
 for(const [url,expected]of hashes){
  assert.ok(!(await lstat(fileURLToPath(url))).isSymbolicLink(),'PRODUCTION_PARENT_CAPTURE_SYMLINK_FORBIDDEN');
  assert.equal(createHash('sha256').update(await readFile(fileURLToPath(url))).digest('hex'),expected,'PRODUCTION_PARENT_CAPTURE_SOURCE_CHANGED');
 }
 const hook=registerHooks({resolve:resolveProductionCapture});let parent;
 try{parent=await import(originalCaptureURL);}finally{hook.deregister();}
 return parent.captureLongScene(options);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={},mapping={'--plan-file':'planFile','--plan-sha256':'expectedPlanSha256',
   '--scene-id':'sceneId','--admission-file':'admissionFile','--output-root':'outputRoot'};
  while(args.length){const flag=args.shift();assert.ok(mapping[flag]&&args.length&&!Object.hasOwn(options,mapping[flag]),'PRODUCTION_EXPLICIT_ARGUMENT_REQUIRED');options[mapping[flag]]=args.shift();}
  assert.equal(Object.keys(options).length,Object.keys(mapping).length,'PRODUCTION_COMPLETE_ARGUMENTS_REQUIRED');
  const report=await captureLongScene(options);console.log(JSON.stringify({status:report.status,path:report.video.path,
   sha256:report.video.sha256,sceneId:report.sceneId,frames:report.completedFrames,productionProfile:'UNIVERSAL_PRODUCTION_V3',visualQualityVerified:false}));
 }catch(error){const message=error?.message??'',code=/^[A-Z][A-Z0-9_]{2,95}$/.test(message)?message:'PRODUCTION_CAPTURE_FAILED';
  console.error(JSON.stringify({schema:'WORLD_ENGINE_PRODUCTION_CAPTURE_FAILURE_V3',status:'BLOCKED',errorCode:code,gpuRenderingVerified:false}));process.exitCode=2;}
}
