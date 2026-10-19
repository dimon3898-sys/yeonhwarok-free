/** Bounded original encoder; only its one runtime import selects completion. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const file=new URL('../universal-auto-video-v2/long_capture.mjs',import.meta.url),
 originalURL=file.href+'?completion-v2-fixed-entry',runtimeURL=new URL('./capture_runtime.mjs',import.meta.url).href;
export function resolveCapture(specifier,context,next){
 if(context.parentURL===originalURL&&specifier==='./long_runtime.mjs')return{url:runtimeURL,shortCircuit:true};
 return next(specifier,context);
}
export async function captureLongScene(options){
 assert.equal(process.version,'v24.19.0','COMPLETION_PINNED_NODE_REQUIRED');
 assert.equal(createHash('sha256').update(await readFile(file)).digest('hex'),
  'a4a6904dabd9a3306ffeafe0c1b0035f6062af81a56f62a0eb55dd055924d4d0','COMPLETION_ORIGINAL_ENCODER_CHANGED');
 const root=fileURLToPath(new URL('../verified-front-data-v4-recovery/',import.meta.url)),
  raw=await readFile(path.join(root,'FRONT_FILES.json')),manifest=JSON.parse(raw),bound={...options,
   frontProfileFile:path.join(root,'FRONT_PROFILE.json'),expectedFrontProfileSha256:manifest.files['FRONT_PROFILE.json'],
   frontManifestFile:path.join(root,'FRONT_FILES.json'),expectedFrontManifestSha256:createHash('sha256').update(raw).digest('hex')};
 const hook=registerHooks({resolve:resolveCapture});let preserved;
 try{preserved=await import(originalURL);}finally{hook.deregister();}
 return preserved.captureLongScene(bound);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={},keys={'--plan-file':'planFile','--plan-sha256':'expectedPlanSha256',
   '--scene-id':'sceneId','--admission-file':'admissionFile','--output-root':'outputRoot'};
  while(args.length){const key=args.shift();assert.ok(keys[key]&&args.length&&!Object.hasOwn(options,keys[key]),'COMPLETION_CAPTURE_ARGS_INVALID');options[keys[key]]=args.shift();}
  assert.equal(Object.keys(options).length,5,'COMPLETION_CAPTURE_ARGS_REQUIRED');
  const result=await captureLongScene(options);
  console.log(JSON.stringify({status:result.status,frames:result.completedFrames,profile:'VISUAL_UNIFIED_COMPLETION_V2',visualQualityVerified:false}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',code:'COMPLETION_CAPTURE_FAILED',gpuRenderingVerified:false}));process.exitCode=2;}
}
