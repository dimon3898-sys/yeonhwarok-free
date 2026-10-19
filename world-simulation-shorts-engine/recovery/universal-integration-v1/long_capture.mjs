/** Reuse the exact bounded encoder/capture; replace only its runtime import. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const captureFile=new URL('../universal-auto-video-v2/long_capture.mjs',import.meta.url),
 originalURL=captureFile.href+'?universal-integration-v1-fixed-entry',runtimeURL=new URL('./capture_runtime.mjs',import.meta.url).href,
 parentRoot=fileURLToPath(new URL('../verified-front-data-v4-recovery/',import.meta.url));
export function resolveCapture(specifier,context,nextResolve){
 if(context.parentURL===originalURL&&specifier==='./long_runtime.mjs')return{url:runtimeURL,shortCircuit:true};
 return nextResolve(specifier,context);
}
export async function captureLongScene(options){
 assert.equal(process.version,'v24.19.0','INTEGRATION_PINNED_NODE_REQUIRED');
 const raw=await readFile(fileURLToPath(captureFile));
 assert.equal(createHash('sha256').update(raw).digest('hex'),'a4a6904dabd9a3306ffeafe0c1b0035f6062af81a56f62a0eb55dd055924d4d0','INTEGRATION_ORIGINAL_CAPTURE_CHANGED');
 const manifestRaw=await readFile(path.join(parentRoot,'FRONT_FILES.json')),manifest=JSON.parse(manifestRaw),
  bound={...options,frontProfileFile:path.join(parentRoot,'FRONT_PROFILE.json'),expectedFrontProfileSha256:manifest.files['FRONT_PROFILE.json'],
   frontManifestFile:path.join(parentRoot,'FRONT_FILES.json'),expectedFrontManifestSha256:createHash('sha256').update(manifestRaw).digest('hex')};
 const hook=registerHooks({resolve:resolveCapture});let parent;
 try{parent=await import(originalURL);}finally{hook.deregister();}return parent.captureLongScene(bound);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={},keys={'--plan-file':'planFile','--plan-sha256':'expectedPlanSha256','--scene-id':'sceneId','--admission-file':'admissionFile','--output-root':'outputRoot'};
  while(args.length){const k=args.shift();assert.ok(keys[k]&&args.length&&!Object.hasOwn(options,keys[k]),'INTEGRATION_CAPTURE_ARGS_INVALID');options[keys[k]]=args.shift();}
  assert.equal(Object.keys(options).length,5,'INTEGRATION_CAPTURE_ARGS_REQUIRED');
  const result=await captureLongScene(options);console.log(JSON.stringify({status:result.status,frames:result.completedFrames,integrationProfile:'VISUAL_UNIFIED_V1',visualQualityVerified:false}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',code:'INTEGRATION_CAPTURE_FAILED',gpuRenderingVerified:false}));process.exitCode=2;}
}
