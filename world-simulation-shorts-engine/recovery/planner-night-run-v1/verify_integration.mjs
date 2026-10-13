/** Focused changed-layer checks, not the approval-only Permanent Gate. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openNightRuntime,root} from './night_runtime.mjs';
const frames=[0,6,30,70,74,84,115,123,158,174,178,188,205,210,245,261,265,275,292,298,342,384,419];
const pngFrames=new Set([30,74,158,245,342,419]);
await mkdir(path.join(root,'evidence/integration'),{recursive:true});
let session;const samples=[];
try{
 session=await openNightRuntime();
 for(const frame of frames){
  const row=await session.page.evaluate(({frame,png})=>window.nightProof.capture(frame,{protect:true,png}),{frame,png:pngFrames.has(frame)});
  const diagnostic=row.diagnostic;
  assert.equal(diagnostic.glError,0);assert.equal(diagnostic.nativeDrawCount,1);assert.equal(diagnostic.camera.cameraLocked,true);
  for(const key of ['protectedChangedPixels','markerChangedPixels','textChangedPixels','outsideRoiChangedPixels',
   'safeAreaChangedPixels','protectedBoundaryChangedPixels'])assert.equal(diagnostic.protection[key],0);
  assert.equal(diagnostic.area.geometryUnchanged,true);
  for(const track of diagnostic.flowTracks){assert.equal(track.preflight.passed,true);
   assert.equal(track.motion.objectPositionUnchanged,true);assert.equal(track.motion.objectHeadingUnchanged,true);}
  if(row.png){await writeFile(path.join(root,'evidence/integration',String(frame).padStart(3,'0')+'.png'),Buffer.from(row.png.split(',')[1],'base64'));delete row.png;}
  samples.push(row);console.log(JSON.stringify({phase:'NIGHT_FOCUSED_INTEGRATION',frame,state:diagnostic.area.controls.stateId,
   actors:diagnostic.flowTracks.filter(track=>track.actorVisible).length,protected:diagnostic.protection.protectedChangedPixels}));
 }
 assert.equal(session.errors.length,0);
 await writeFile(path.join(root,'evidence/INTEGRATION.json'),JSON.stringify({schema:1,status:'PASS',scope:'CHANGED_CAUSAL_COMPOSITION_ONLY',
  focusedFrames:frames,samples,runtime:session.info,permanentGateExecuted:false,fullVisualReviewClaimed:false,
  geometryUnchanged:true,requiredTempOnlyFiles:0})+'\n');
 console.log(JSON.stringify({status:'PASS',focusedFrames:frames.length,nativeFactoryCount:1,protection:0}));
}finally{await session?.close();}
