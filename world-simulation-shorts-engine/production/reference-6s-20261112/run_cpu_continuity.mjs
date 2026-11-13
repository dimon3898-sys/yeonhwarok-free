/** New sequential-state coverage; no Studio job and no GPU. */
import fs from'node:fs/promises';import path from'node:path';import{fileURLToPath}from'node:url';import assert from'node:assert/strict';import{createHash}from'node:crypto';
import{capturePresentation}from'../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),out='/workspace/reference6s-continuity',packageFile=path.join(p,'REGISTERED_RUNTIME_REQUEST.json'),bytes=await fs.readFile(packageFile),request=JSON.parse(bytes);
const gate=JSON.parse(await fs.readFile(path.join(p,'CPU_SCREEN_REVIEW.json')));assert.equal(gate.status,'PASS');assert.equal(gate.compilerInputSHA256,request.sourceInputSHA256);
await capturePresentation({packageFile,outputRoot:out,expectedSHA256:createHash('sha256').update(bytes).digest('hex'),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:Array.from({length:180},(_,i)=>i)});
const data=JSON.parse(await fs.readFile(path.join(out,'FRAME_EVIDENCE.json'))),frames=data.frames;assert.equal(frames.length,180);
const summary=[];let switches=[];
for(let f=0;f<180;f++){
 const row=frames[f],d=row.diagnostic;assert.equal(row.frame,f);assert.equal(d.glError,0);assert.ok(row.nonBlackPixels>1080*1920*.2);assert.deepEqual(d.camera.state.pose,request.segments[0].presentation.camera.frames[Math.min(f,149)]);
 const ids=d.features.map(v=>v.id);assert.deepEqual(ids,['IBERIA_YELLOW','MOROCCO_CYAN']);const alpha=d.features.map(v=>v.sourceAreas[0].alpha);assert.equal(alpha[0],1);if(f<=89)assert.equal(alpha[1],0);if(f>=119)assert.equal(alpha[1],1);
 const pins=[...d.markers.map(m=>m.locationId),...(d.presentationLabels?.drawn??[]).filter(l=>l.pinDrawn).map(l=>l.locationId)];if(f>=55)for(const id of ['COAST_PIN_A','COAST_PIN_B'])assert.ok(pins.includes(id),'missing pin '+id+' frame '+f);
 if(f>=55)assert.equal(d.presentationLabels.visibleCount,2);
 const a=d.camera.actualFactory.sourceAdmission;assert.ok(a.gutter>=1&&Math.max(...a.density)<=1+1e-8);
 if(f>=150)assert.equal(row.rawSHA256,frames[149].rawSHA256,'full hold raw pixel mismatch');
 if(f>0&&a.sha256!==frames[f-1].diagnostic.camera.actualFactory.sourceAdmission.sha256)switches.push(f);
 summary.push({frame:f,pngSHA256:row.pngSHA256,rawSHA256:row.rawSHA256,baseRawSHA256:row.baseRawSHA256,camera:d.camera.state.pose,terrain:a,areas:alpha,pins,labels:d.presentationLabels?.drawn.map(l=>({id:l.id,projected:l.projected,box:l.box,pin:l.pin,pinDrawn:l.pinDrawn})),nonBlackPixels:row.nonBlackPixels,glError:d.glError});
}
const result={status:'PASS_TECHNICAL_CONTINUITY_VISUAL_REVIEW_PENDING',frames:180,holdFrames:30,holdMatchesFrame149:true,rawHoldHash:frames[149].rawSHA256,sourceLevelSwitchFrames:switches,oldPassSuitesRerun:0,sequentialContextScope:'First complete stateful 180-frame path; prior seven sparse probes preserved',GPUExecutions:0,compilerInputSHA256:request.sourceInputSHA256,checks:['all180 actual GPU-free PNGs','exact authored camera per frame','native source density and coverage per frame','two independent area states per frame','both pins and labels throughout required interval','raw pixels identical149..179','zero GL errors','no blank frames']};
await fs.writeFile(path.join(out,'CONTINUITY_RESULT.json'),JSON.stringify(result,null,2)+'\n');await fs.writeFile(path.join(out,'FRAME_SUMMARY.json'),JSON.stringify(summary)+'\n');console.log(JSON.stringify(result));
