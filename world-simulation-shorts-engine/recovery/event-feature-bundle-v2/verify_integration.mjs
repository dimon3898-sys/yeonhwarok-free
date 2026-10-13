import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openFlowRuntime,root,sha} from './flow_runtime.mjs';
const out=path.join(root,'evidence/integration');await mkdir(out,{recursive:false});
const session=await openFlowRuntime(),report={schema:1,status:'STARTED',parentBaseline:'EVENT_SYSTEM_V1_FINAL_BASELINE',frames:[]};
try{
 for(const frame of [0,26,59,60,72,80,100,120,145,170,188,195,205,239]){
  const result=await session.page.evaluate(frame=>window.flowProof.capture(frame,{protect:true,png:true}),frame);
  const bytes=Buffer.from(result.png.split(',')[1],'base64');delete result.png;const d=result.diagnostic;
  assert.equal(sha(bytes),result.png_sha256);assert.equal(d.glError,0);
  assert.equal(d.flow.protection.protectedChangedPixels,0);assert.equal(d.flow.protection.markerChangedPixels,0);
  assert.equal(d.flow.protection.outsideRoiChangedPixels,0);
  if(frame<60){assert.equal(d.flow.enabled,false);assert.equal(d.flow.controls,null);}
  else{assert.equal(d.camera.cameraLocked,true);assert.equal(d.native.event.controls.state,'EVENT_READY');
   assert.equal(d.native.event.line,null);assert.equal(d.native.event.metric,null);
   assert.equal(d.flow.graphics.nativeStateRestored,true);assert.equal(d.flow.style.width,7);}
  await writeFile(path.join(out,String(frame).padStart(3,'0')+'.png'),bytes,{flag:'wx'});
  report.frames.push({...result,pngFile:String(frame).padStart(3,'0')+'.png'});
  console.log(JSON.stringify({phase:'FLOW_INTEGRATION',frame,state:d.state}));
 }
 // Flow OFF immediately after an overlay reproduces fresh native pixels at the same view.
 const off=await session.page.evaluate(()=>window.flowProof.capture(239,{flowEnabled:false,protect:true,png:true}));
 await session.page.evaluate(()=>window.flowProof.capture(120,{protect:true,png:false}));
 const again=await session.page.evaluate(()=>window.flowProof.capture(239,{flowEnabled:false,protect:true,png:true}));
 assert.equal(again.raw_rgba_sha256,off.raw_rgba_sha256);assert.equal(again.png_sha256,off.png_sha256);
 assert.equal(session.errors.length,0);report.extensionOffFreshNative='BIT_EXACT';report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{await writeFile(path.join(out,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session.close();}
console.log(JSON.stringify({status:report.status,frames:report.frames.length,off:report.extensionOffFreshNative}));
