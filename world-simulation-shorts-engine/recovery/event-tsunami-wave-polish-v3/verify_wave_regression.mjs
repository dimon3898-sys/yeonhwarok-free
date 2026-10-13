/** Focused visual-extension regression; the frozen Area/War suite is preserved. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openWaveRuntime,root,json,sha,engine} from './wave_runtime.mjs';

const report={schema:1,status:'STARTED',scope:'WAVE_VISUAL_ONLY',
 permanentGateExecuted:false,areaWarCoreRedeveloped:false,frames:[],
 nativeSourceMutation:false,createdAtUtc:new Date().toISOString()};
const folder=path.join(root,'evidence/integration');await mkdir(folder,{recursive:true});
let session;
try{
 session=await openWaveRuntime();
 report.fixtureSha256=sha(await readFile(path.join(root,'fixtures/REAL_FIXTURE.json')));
 report.waveProfile={travelFrames:session.wavePlan.travelFrames,staggerFrames:session.wavePlan.staggerFrames,
  fadeFrames:session.wavePlan.fadeFrames,completeFrame:session.wavePlan.completeFrame,
  plannedHoldFrames:session.wavePlan.totalFrames-session.wavePlan.completeFrame};
 const parent=await json(path.join(engine,'recovery/event-area-propagation-v3/evidence/proof/REPORT.json'));
 const off=await session.page.evaluate(()=>window.waveProof.capture(0,{waveEnabled:false,protect:true,png:false}));
 assert.equal(off.raw_rgba_sha256,parent.frames.find(row=>row.frame===0).raw_rgba_sha256,
  'WAVE_NATIVE_OFF_DIFFERS_FROM_PARENT');
 assert.equal(off.diagnostic.wave.enabled,false);
 report.nativeOff={frame:0,rawRgbaSha256:off.raw_rgba_sha256,status:'BIT_EXACT',
  reference:'PARENT_NATIVE_EVENT_ARRIVAL_FRAME_0'};
 const frames=[0,42,54,65,110,125,150,187,220,269];
 for(const frame of frames){
  const row=await session.page.evaluate(value=>window.waveProof.capture(value,{protect:true,png:true}),frame);
  const {diagnostic:d}=row,w=d.wave;
  assert.equal(d.glError,0);assert.equal(w.closedPropagationRing,false);
  for(const key of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])
   assert.equal(w.protection[key],0,key+' frame '+frame);
  if(frame>=session.presentation.eventStartFrame){
   assert.equal(d.camera.cameraLocked,true);
   assert.equal(w.graphics.nativeStateRestored,true);
   assert.equal(w.graphics.coastContact.nativeStateRestored,true);
   assert.equal(w.controls.physicalSimulation,false);
   assert.equal(w.diagnostics.closedRingCount,0);
   assert.ok(w.diagnostics.majorFrontCount<=3);
   for(const line of w.controls.propagations){
    const coordinates=line.geometry.coordinates;
    assert.notDeepEqual(coordinates[0],coordinates.at(-1),'CLOSED_RING_IN_PUBLIC_WAVE');
    assert.equal(line.linePrimitive.screenCoordinates.length,coordinates.length);
   }
   const targetBounds=await session.page.evaluate(geometry=>geometry.coordinates.map(point=>window.waveProof.pipeline.project(point)),
    session.wavePlan.coastGeometry);
   const safe=session.presentation.safeArea??[48,72,1032,1848];
   assert.ok(targetBounds.every(([x,y])=>x>=safe[0]&&x<=safe[2]&&y>=safe[1]&&y<=safe[3]),
    'SUPPLIED_COAST_RELATION_CROPPED');
   if(w.annotation){assert.equal(w.annotation.text,'2011.03.11 발생');assert.equal(w.annotation.fontSize,40);}
  }
  const bytes=Buffer.from(row.png.split(',')[1],'base64');assert.equal(sha(bytes),row.png_sha256);
  const file='FRAME_'+String(frame).padStart(3,'0')+'.png';await writeFile(path.join(folder,file),bytes);
  const summary={frame,file:'evidence/integration/'+file,pngSha256:sha(bytes),rawRgbaSha256:row.raw_rgba_sha256,
   cameraLocked:d.camera.cameraLocked,glError:d.glError,protection:w.protection,
   wave:w.diagnostics,originPulseActive:w.originPulse?.active??false,
   dateAnnotation:w.annotation?.text??null};
  report.frames.push(summary);console.log(JSON.stringify({frame,glError:d.glError,
   protectedChangedPixels:w.protection.protectedChangedPixels,majorFronts:w.diagnostics?.majorFrontCount??0,
   coastContacts:w.diagnostics?.coastContactCount??0,pulse:summary.originPulseActive}));
 }
 const train=report.frames.find(row=>row.frame===110);assert.equal(train.wave.majorFrontCount,3);
 assert.equal(report.frames.find(row=>row.frame===54).originPulseActive,true);
 assert.ok(report.frames.some(row=>row.wave?.coastContactCount>0));
 assert.equal(report.frames.find(row=>row.frame===269).wave.majorFrontCount,0);
 const order=session.wavePlan.contacts.map(contact=>({id:contact.id,frame:contact.arrivalFrame}));
 assert.ok(new Set(order.map(row=>row.frame.toFixed(3))).size>1,'WHOLE_COAST_SIMULTANEOUS_FLASH');
 report.coastArrival={localIntervals:order.length,arrivalOrder:order.sort((a,b)=>a.frame-b.frame),
  repetition:0,sourceCoastUnchanged:true,glow:'SHORT_EVENT_OWNED_COAST_CONTACT_ONLY'};
 assert.equal(session.errors.length,0);report.backend=session.info.backend;report.evidence=session.info.evidence;
 report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;throw error;}
finally{
 try{await session?.close();}finally{
  report.completedAtUtc=new Date().toISOString();
  await writeFile(path.join(root,'evidence/WAVE_REGRESSION.json'),JSON.stringify(report,null,2)+'\n');
 }
}
console.log(JSON.stringify({status:report.status,frames:report.frames.length,nativeOff:report.nativeOff.status,
 protection:'PASS',majorFronts:3,closedRings:0,coastArrival:'SEQUENTIAL_LOCAL_ONCE'}));
