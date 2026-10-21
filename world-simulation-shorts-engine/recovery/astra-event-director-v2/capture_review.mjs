/** Actual native-renderer draw/readPixels. Bounded 16 stills + 3 source-review windows.
 * A blocked ownership/camera goal remains blocked when a diagnostic clip exists.
 */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {readFile,writeFile,mkdir,open,unlink,rename,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {openEventDirectorRuntime} from './runtime_adapter.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url)),REPO=path.resolve(ROOT,'../../..'),sha=v=>createHash('sha256').update(v).digest('hex');
const args=Object.fromEntries(process.argv.slice(2).map(a=>{const m=/^--(prepared|probe)=(.+)$/.exec(a);assert.ok(m,'DIRECTOR_CAPTURE_ARGUMENT_UNSUPPORTED');return[m[1],m[2]];}));
assert.equal(typeof args.prepared,'string','DIRECTOR_PREPARED_RECEIPT_REQUIRED');
const stills=Array.from({length:16},(_,i)=>i*150),clips=[
 {id:'M1',startFrame:600,endFrame:700,goal:'INCHEON_APPROACH',goalStatus:'BLOCKED_REQUESTED_LOCAL_AND_EVENT_CONTROL'},
 {id:'M2',startFrame:865,endFrame:965,goal:'SEOUL_CONTROL_AND_FRONT_MORPH',goalStatus:'BLOCKED_CONTROL_ENDPOINTS_AND_TRANSITION_EVIDENCE'},
 {id:'M3',startFrame:965,endFrame:1100,goal:'RESULT_WIDEN_AND_NORTH_CONTEXT',goalStatus:'PARTIAL_REGIONAL_CAMERA_ONLY_CONTROL_UNKNOWN'}],
 frames=args.probe?[Number(args.probe)]:[...new Set([...stills,...clips.flatMap(c=>Array.from({length:c.endFrame-c.startFrame},(_,i)=>c.startFrame+i))])].sort((a,b)=>a-b),
 probe=args.probe!==undefined,
 sourceCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:REPO,encoding:'utf8'}).trim();
for(const d of ['.private/frames','proof','public-review'])await mkdir(path.join(ROOT,d),{recursive:true});
const lockPath=path.join(ROOT,'.private/ACTUAL_CAPTURE_LOCK.json'),lock=await open(lockPath,'wx');
await lock.writeFile(JSON.stringify({pid:process.pid,kind:probe?'PROBE':'SOURCE_REVIEW',frames:frames.length})+'\n');await lock.close();
const report={schema:'WORLD_ENGINE_ASTRA_V2_ACTUAL_CAPTURE_V1',status:'IN_PROGRESS',purpose:'QUALIFIED_SOURCE_REVIEW',
 sourceCommit,startedAt:new Date().toISOString(),
 captureKind:'ACTUAL_WORLD_ENGINE_WEBGL2_DRAW_READPIXELS_CANVAS_PNG',backend:null,
 width:1080,height:1920,fps:30,totalSourceFrames:2400,stillsRequested:probe?[]:stills,clipsRequested:probe?[]:clips,
 full80SecondVideoProduced:false,oldMovieOrFramesReused:false,sceneReinitializedPerFrame:false,
 paidGPUExecuted:false,nvidiaHardwareVerified:false,productionEligible:false,visualQualityApproved:false,frames:[]};
const clock=performance.now();let runtime,failure;
const safe=value=>JSON.parse(JSON.stringify(value,(k,v)=>['geometry','coordinates','compiledPlan','legacyScenePlan','v5Plan','baseCameraPlan','boundarySegments'].includes(k)?undefined:v));
try{
 runtime=await openEventDirectorRuntime({preparedFile:args.prepared,
  normalizationFile:path.join(ROOT,'fixtures/NORMALIZED_SOURCE_REVIEW.json'),
  cameraProfileFile:path.join(ROOT,'fixtures/CAMERA_REVIEW_PROFILE.json'),cameraAdmissionFile:path.join(ROOT,'fixtures/CAMERA_ADMISSION.json')});
 report.backend=runtime.info.backend;assert.match(report.backend,/SwiftShader/i);
 report.sourceSignature=runtime.sourceSignature;report.sourceBindings=runtime.directorSourceRecords;
 report.runtimeInfo=safe(runtime.info);
 for(const frame of frames){
  const at=performance.now(),captured=await runtime.page.evaluate(async globalFrame=>{
   const c=await window.longVideoProof.capture(globalFrame,{png:true});
   if(!c.diagnostic.eventDirector||c.diagnostic.eventDirector.globalFrame!==globalFrame)throw Error('DIRECTOR_ACTUAL_CONSUMER_NOT_EXECUTED');
   return c;
  },frame),d=captured.diagnostic;
  assert.equal(d.glError,0);assert.equal(d.frame,frame);
  const png=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(png),captured.png_sha256);
  assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1920);
  const index=stills.indexOf(frame),name=probe?'PROBE_'+String(frame).padStart(4,'0')+'.png':
   index>=0?'FRAME_'+String(index).padStart(2,'0')+'_T'+String(frame/30).padStart(3,'0')+'.png':null,
   paths=[...(!probe?[path.join(ROOT,'.private/frames',String(frame).padStart(4,'0')+'.png')]:[]),
    ...(name?[path.join(ROOT,probe?'proof':'public-review',name)]:[])];
  for(const file of paths){if(await stat(file).then(()=>true,()=>false))assert.deepEqual(await readFile(file),png,'DIRECTOR_REFUSE_DIFFERENT_EXISTING_OUTPUT');
   else await writeFile(file,png,{flag:'wx'});}
  const row={globalFrame:frame,timeSeconds:frame/30,sampleIndex:index>=0?index:null,
   file:name?(probe?'proof/':'public-review/')+name:null,pngSHA256:captured.png_sha256,rawRGBASHA256:captured.raw_rgba_sha256,
   bytes:png.length,captureWallMilliseconds:performance.now()-at,newActualDraw:true,glError:0,
   chapterId:d.eventDirector.chapterId,eventId:d.eventDirector.eventId,truthKind:d.eventDirector.truthKind,
   sourceAsOfDate:d.eventDirector.sourceAsOfDate,sceneHash:d.eventDirector.derivedSceneSHA256,
   camera:safe(d.camera?.productionCamera?.astraDirector??d.camera),
   actualBounds:d.camera?.camera?.flatBounds??d.camera?.flatBounds,
   areaStateId:d.area?.controls?.stateId??null,areaCount:d.area?.graphics?.areas?.length??0,
   frontCount:d.area?.graphics?.fronts?.length??0,frontSource:safe(d.frontV4?.selection),
   terrain:safe(d.terrain),eventDirector:safe(d.eventDirector),
   visibleText:[d.area?.date?.event?.text,d.area?.date?.geometry?.text,
    d.eventDirector.sourceAvailability?.event?.text,d.eventDirector.sourceAvailability?.qualification?.text,
    d.eventDirector.additionalFront?.event?.text,d.eventDirector.additionalFront?.qualification?.text].filter(Boolean),
   markerEvidence:'NO_VERIFIED_HISTORICAL_UNIT_COORDINATES',audio:{enabled:false,gain:0,cues:[]},qualityState:'USER_REVIEW_REQUIRED'};
  report.frames.push(row);
  await writeFile(path.join(ROOT,'.private/frames',String(frame).padStart(4,'0')+'.json'),JSON.stringify(row)+'\n');
  if(!probe&&(index>=0||report.frames.length%10===0)){
   const checkpoint=path.join(ROOT,'proof/ACTUAL_CAPTURE_PROGRESS.json');
   await writeFile(checkpoint+'.writing',JSON.stringify(report,null,2)+'\n');await rename(checkpoint+'.writing',checkpoint);
  }
  if(index>=0||probe||report.frames.length%10===0)console.log(JSON.stringify({frame,done:report.frames.length,total:frames.length,pngSHA256:row.pngSHA256}));
 }
 assert.deepEqual(runtime.errors,[]);await runtime.close();runtime=null;
 assert.deepEqual(report.frames.map(r=>r.globalFrame),frames);report.status='ACTUAL_SOURCE_REVIEW_DRAW_COMPLETE';
 report.requestedVisualContractStatus='NEEDS_REWORK_BLOCKED_CONTROL_AND_LOCAL_SOURCE';
}catch(e){failure=e;report.status='ACTUAL_RENDER_FAILED';report.error=String(e.stack);}
finally{
 try{await runtime?.close();}catch(e){failure??=e;report.closeError=String(e.stack);}
 report.completedAt=new Date().toISOString();report.wallSeconds=(performance.now()-clock)/1000;
 const file=path.join(ROOT,'proof',probe?'PROBE_'+String(args.probe).padStart(4,'0')+'.json':'ACTUAL_CAPTURE.json');
 await writeFile(file+'.writing',JSON.stringify(report,null,2)+'\n');await rename(file+'.writing',file);await unlink(lockPath);
}
if(failure)throw failure;
console.log(JSON.stringify({status:report.status,actualFrames:report.frames.length,backend:report.backend,visualQualityApproved:false}));
