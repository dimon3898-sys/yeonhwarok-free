/** New-input verification harness only. The official renderer remains unchanged. */
import fs from'node:fs/promises';import path from'node:path';import{fileURLToPath}from'node:url';import{createHash}from'node:crypto';import assert from'node:assert/strict';
import{capturePresentation}from'../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),packageFile=path.join(p,'RUNTIME_REQUEST.json'),raw=await fs.readFile(packageFile),hash=x=>createHash('sha256').update(x).digest('hex'),out='/workspace/japan6s-cpu-a1';
let stage='OFFICIAL_SOURCE_PREPARATION_AND_CAPTURE';
try{
 const receipt=await capturePresentation({packageFile,outputRoot:out,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS});
 stage='NEW_INPUT_180_FRAME_ASSERTIONS';
 const rows=JSON.parse(await fs.readFile(path.join(out,'FRAME_EVIDENCE.json'))).frames;
 assert.equal(rows.length,180);assert.equal(receipt.video.frames,180);assert.equal(receipt.video.fullDecode,'PASS');
 const summary=rows.map((row,f)=>{
  assert.equal(row.frame,f);const d=row.diagnostic;assert.equal(d.glError,0);assert.equal(d.material.fullViewportCovered,true);
  assert.ok(d.suppliedLocations.every(l=>l.inSafe));
  const feature=d.features.find(x=>x.id==='ILLUSTRATIVE_ROUTE');
  if(f<60)assert.equal(feature,undefined);else {assert.ok(feature);assert.ok(feature.admission);if(f>=89)assert.equal(feature.routeFraction,1);}
  assert.ok(d.presentationLabels.drawn.some(x=>x.id==='tokyo-label'));assert.ok(d.presentationLabels.drawn.some(x=>x.id==='kyoto-label'));
  return{frame:f,rawSHA256:row.rawSHA256,pngSHA256:row.pngSHA256,nonBlackPixels:row.nonBlackPixels,cameraBounds:d.camera.bounds,locations:d.suppliedLocations,labels:d.presentationLabels.drawn.map(x=>({id:x.id,pinDrawn:x.pinDrawn,projected:x.projected})),route:feature?{state:feature.state,routeFraction:feature.routeFraction,objectFraction:feature.objectFraction,projectedRoute:feature.projectedRoute,arrivalPulse:feature.arrivalPulse,draw:feature.draw}:null,source:{id:receipt.sourceCredits[0].sourceId,originalSHA256:d.material.sourceOriginalSHA256,terrainSHA256:d.material.terrainSHA256,fullViewportCovered:d.material.fullViewportCovered},glError:d.glError};
 });
 assert.equal(summary[60].route.routeFraction,0);assert.ok(summary[75].route.routeFraction>0&&summary[75].route.routeFraction<1);
 for(let f=150;f<180;f++){assert.equal(rows[f].rawSHA256,rows[150].rawSHA256);assert.deepEqual(summary[f].cameraBounds,summary[149].cameraBounds);}
 assert.notDeepEqual(summary[0].cameraBounds,summary[59].cameraBounds);assert.notDeepEqual(summary[119].cameraBounds,summary[149].cameraBounds);
 const span=r=>r.cameraBounds[2]-r.cameraBounds[0];assert.ok(span(summary[149])<span(summary[119]));
 const result={status:'PASS_ACTUAL_CPU_NEW_JAPAN_180_PENDING_VISUAL_REVIEW',frames:180,width:1080,height:1920,fps:30,durationSeconds:6,routeStartFrame:60,routeCompleteFrame:89,whole30FrameHoldIdentical:true,sourceGeometryAndLocationsUnchanged:true,rendererCodeChanges:0,oldPassReruns:0,GPUExecutions:0,video:receipt.video};
 await fs.writeFile(path.join(out,'FRAME_SUMMARY.json'),JSON.stringify(summary,null,2)+'\n',{flag:'wx'});await fs.writeFile(path.join(out,'NEW_INPUT_RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result));
}catch(error){await fs.mkdir(out,{recursive:true});await fs.writeFile(path.join(out,'TASK_FAILURE.json'),JSON.stringify({status:'FAIL',stage,originalMessage:String(error.message),stack:error.stack,inputFile:'JAPAN_6S_INPUT.json',inputFileSHA256:hash(await fs.readFile(path.join(p,'JAPAN_6S_INPUT.json'))),runtimeRequestSHA256:hash(raw),rendererCodeChanges:0,GPUExecutions:0},null,2)+'\n',{flag:'wx'});throw error;}
