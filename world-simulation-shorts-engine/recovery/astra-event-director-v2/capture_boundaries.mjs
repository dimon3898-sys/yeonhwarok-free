/** Additional actual adjacency checks. Source-global frames and owners unchanged. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {openEventDirectorRuntime} from './runtime_adapter.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url)),sha=x=>createHash('sha256').update(x).digest('hex'),
 preparedFile=process.argv[2],main=JSON.parse(await readFile(path.join(ROOT,'proof/ACTUAL_CAPTURE.json'))),
 profile=JSON.parse(await readFile(path.join(ROOT,'fixtures/HISTORY_EVENT_PROFILE_V2.json'))),
 cuts=[...new Set([...profile.chapters.slice(1).map(x=>x.startFrame),...profile.sourceSchedule.slice(1).map(x=>x.startFrame)])],
 frames=[...new Set(cuts.flatMap(f=>[f-1,f,f+1]))].sort((a,b)=>a-b),report={schema:'WORLD_ENGINE_ASTRA_V2_ACTUAL_BOUNDARY_REVIEW_V1',
 status:'IN_PROGRESS',backend:main.backend,sourceSignature:main.sourceSignature,frames:[],
 actualDraws:0,existingMainDrawsReused:0,fullOwnerContinuityVerified:false,sourceSnapshotsNotMorphs:true,
 nvidiaHardwareVerified:false,visualQualityApproved:false};
assert.equal(main.status,'ACTUAL_SOURCE_REVIEW_DRAW_COMPLETE');await mkdir(path.join(ROOT,'adjacent'),{recursive:true});
let runtime,failure;
try{
 for(const frame of frames){
  const previous=main.frames.find(x=>x.globalFrame===frame);
  if(previous){
   const raw=await readFile(path.join(ROOT,'.private/frames',String(frame).padStart(4,'0')+'.png'));
   assert.equal(sha(raw),previous.pngSHA256);report.frames.push({globalFrame:frame,pngSHA256:previous.pngSHA256,
    rawRGBASHA256:previous.rawRGBASHA256,source:'ACTUAL_MAIN_CAPTURE_ALREADY_DRAWN',newDraw:false,
    actualBounds:previous.actualBounds,truthKind:previous.truthKind,sourceDate:previous.sourceAsOfDate,
    chapterId:previous.chapterId,eventId:previous.eventId,visibleText:previous.visibleText,glError:previous.glError});
   report.existingMainDrawsReused++;continue;
  }
  if(!runtime)runtime=await openEventDirectorRuntime({preparedFile,
   normalizationFile:path.join(ROOT,'fixtures/NORMALIZED_SOURCE_REVIEW.json'),
   cameraProfileFile:path.join(ROOT,'fixtures/CAMERA_REVIEW_PROFILE.json'),cameraAdmissionFile:path.join(ROOT,'fixtures/CAMERA_ADMISSION.json')});
  assert.equal(runtime.sourceSignature,main.sourceSignature,'ADJACENT_SAME_SELECTED_RUNTIME_SOURCE_REQUIRED');
  const c=await runtime.page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),frame),
   raw=Buffer.from(c.png.split(',')[1],'base64'),d=c.diagnostic,file='adjacent/FRAME_'+String(frame).padStart(4,'0')+'.png';
  assert.equal(sha(raw),c.png_sha256);assert.equal(d.glError,0);assert.equal(d.eventDirector.globalFrame,frame);
  await writeFile(path.join(ROOT,file),raw,{flag:'wx'});
  report.frames.push({globalFrame:frame,pngSHA256:c.png_sha256,rawRGBASHA256:c.raw_rgba_sha256,file,
   source:'NEW_ACTUAL_BOUNDARY_DRAW',newDraw:true,actualBounds:d.camera.camera.flatBounds,
   truthKind:d.eventDirector.truthKind,sourceDate:d.eventDirector.sourceAsOfDate,
   chapterId:d.eventDirector.chapterId,eventId:d.eventDirector.eventId,
   visibleText:[d.area?.date?.event?.text,d.area?.date?.geometry?.text,d.eventDirector.sourceAvailability?.event?.text,
    d.eventDirector.sourceAvailability?.qualification?.text,d.eventDirector.additionalFront?.event?.text,
    d.eventDirector.additionalFront?.qualification?.text].filter(Boolean),glError:d.glError});
  report.actualDraws++;console.log(JSON.stringify({boundaryFrame:frame,done:report.frames.length,total:frames.length}));
 }
 if(runtime){assert.deepEqual(runtime.errors,[]);await runtime.close();runtime=null;}
 let previous='';for(const r of report.frames)if(r.sourceDate){assert.ok(r.sourceDate>=previous,'ADJACENT_SOURCE_DATE_REGRESSION');previous=r.sourceDate;}
 report.status='ACTUAL_BOUNDARY_DRAW_COMPLETE';
}catch(e){failure=e;report.status='ACTUAL_BOUNDARY_DRAW_FAILED';report.error=String(e.stack);}
finally{try{await runtime?.close();}catch(e){failure??=e;report.closeError=String(e.stack);}
 await writeFile(path.join(ROOT,'proof/BOUNDARY_CAPTURE.json'),JSON.stringify(report,null,2)+'\n');}
if(failure)throw failure;
