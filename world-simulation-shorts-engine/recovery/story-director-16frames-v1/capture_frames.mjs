/** Actual random-access still capture. No encoder, movie input, or image synthesis. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,open,unlink,rename,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {openDirectorRuntime,loadSourceOptions} from './runtime_adapter.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url)),REPO=path.resolve(ROOT,'../../..');
const hash=x=>createHash('sha256').update(x).digest('hex');
const options=Object.fromEntries(process.argv.slice(2).map(x=>{const m=/^--(prepared|profile|camera-bridge|bindings)=(.+)$/.exec(x);if(!m)throw Error('UNKNOWN_CAPTURE_ARGUMENT');return[m[1],m[2]];}));
assert.ok(options.prepared,'EXISTING_VERIFIED_PREPARATION_RECEIPT_REQUIRED');
const sources=await loadSourceOptions(options.prepared),sourceBytes=await readFile(sources.planFile),sourceHash=hash(sourceBytes);
assert.equal(sourceHash,sources.expectedPlanSha256);
const originalDocument=JSON.parse(sourceBytes),sampleFrames=Array.from({length:16},(_,i)=>i*150),
 adjacentFrames=[1599,1600,1601,1665,1666,1667,1732,1733,1734],allFrames=[...new Set([...sampleFrames,...adjacentFrames])].sort((a,b)=>a-b);
assert.equal(originalDocument.totalFrames,2400);assert.equal(originalDocument.fps,30);
const browserBindings=options.bindings?JSON.parse(await readFile(options.bindings,'utf8')):[];
await Promise.all(['proof','public-review','adjacent','.private'].map(x=>mkdir(path.join(ROOT,x),{recursive:true})));
const lockFile=path.join(ROOT,'.private/CAPTURE_LOCK.json'),lock=await open(lockFile,'wx');
await lock.writeFile(JSON.stringify({pid:process.pid,startedAt:new Date().toISOString()})+'\n');await lock.close();
const report={schema:'WORLD_ENGINE_STORY_DIRECTOR_ACTUAL_FRAMES_V1',status:'IN_PROGRESS',
 captureKind:'ACTUAL_WORLD_ENGINE_WEBGL2_DRAW_READPIXELS_CANVAS_PNG',previewKind:'SOFTWARE_PREVIEW',
 sourceCheckoutCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:REPO,encoding:'utf8'}).trim(),
 sourcePlanSHA256:sourceHash,totalSourceFrames:2400,fps:30,width:1080,height:1920,
 requestedGlobalFrames:sampleFrames,adjacentRequestedGlobalFrames:adjacentFrames,
 oneRuntime:true,sceneReinitializedPerFrame:false,oldMovieOrFramesReused:false,
 paidGpuExecuted:false,nvidiaHardwareVerified:false,mp4Produced:false,visualQualityApproved:false,
 startedAtUtc:new Date().toISOString(),frames:[],adjacentFrames:[]};
const full=[];let runtime,failure;const started=performance.now();
// Retain selected actual diagnostics without publishing internal Scene bodies.
function safe(value){
 if(value===undefined)return null;
 return JSON.parse(JSON.stringify(value,(key,v)=>['coordinates','geometry','boundarySegments','v5Plan','baseCameraPlan',
  'cameraKeyframeBinding','boundaryKeyframeBinding','compiledPlan','legacyScenePlan'].includes(key)?undefined:v));
}
function diagnostic(d){
 const controls=d.area?.controls;
 return{frame:d.frame,width:d.width,height:d.height,glError:d.glError,
  camera:safe(d.camera),area:{controls:controls?{frame:controls.frame,stateId:controls.stateId,origin:controls.origin,
   areas:safe(controls.areas),fronts:safe(controls.fronts),timeStep:safe(controls.timeStep),dataMode:controls.dataMode,
   stateProgress:safe(controls.stateProgress),hold:safe(controls.hold),activeFeatures:safe(controls.activeFeatures)}:null,
   graphics:safe(d.area?.graphics),date:safe(d.area?.date),geometryUnchanged:d.area?.geometryUnchanged},
  terrain:safe(d.terrain),foreground:safe(d.foreground),productionV3:safe(d.productionV3),
  completionV2:safe(d.completionV2),sourceIntegrity:safe(d.sourceIntegrity),universalVideo:safe(d.universalVideo),
  sourceQualification:safe(d.sourceQualification),frontSource:safe(d.frontSource),frontV4:safe(d.frontV4),
  boundaryPreservation:safe(d.boundaryPreservation),visualQualityApproved:false};
}
try{
 runtime=await openDirectorRuntime({...sources,directorProfileFile:options.profile??null,
  cameraBridgeFile:options['camera-bridge']??null,browserBindings});
 report.backend=runtime.info.backend;report.runtimeInfo=safe(runtime.info);
 report.sourceSignature=runtime.sourceSignature;report.directorSourceRecords=runtime.directorSourceRecords;
 report.directorProfileSHA256=runtime.storyDirector?.profileSHA256??null;
 report.originalSceneRanges=runtime.storyDirector?.sourceSceneRanges;
 assert.match(report.backend,/SwiftShader/i);assert.equal(runtime.info.productionEligible,false);
 for(const frame of allFrames){
  const at=performance.now(),captured=await runtime.page.evaluate(async globalFrame=>{
   const c=await window.longVideoProof.capture(globalFrame,{png:true});
   const config=await(await fetch('/runtime-config.json',{cache:'no-store'})).json(),
    chapters=config.universalVideo.plan.productionV3.eventChapters,
    chapter=chapters.find(x=>globalFrame>=x.startFrame&&globalFrame<x.endFrame),
    entry=config.storyDirector?.profile?.chapters?.find(x=>x.chapterId===chapter?.chapterId),
    target=entry?.targetAnchor??entry?.anchor??null;
   c.directorSample={globalFrame,chapterId:chapter?.chapterId,eventId:chapter?.eventId,
    target,projectedTarget:target?window.longVideoProof.pipeline.project(target):null};return c;
  },frame);
  assert.equal(captured.diagnostic.frame,frame);assert.equal(captured.diagnostic.glError,0);
  const png=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(hash(png),captured.png_sha256);
  assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1920);
  const index=sampleFrames.indexOf(frame),file=index>=0?'FRAME_'+String(index).padStart(2,'0')+'_T'+String(frame/30).padStart(3,'0')+'.png':
   'ADJACENT_GLOBAL_'+String(frame).padStart(4,'0')+'.png',directory=index>=0?'public-review':'adjacent';
  const destination=path.join(ROOT,directory,file),existing=await stat(destination).then(()=>true,()=>false);
  if(existing)assert.deepEqual(await readFile(destination),png,'EXISTING_PNG_DIFFERS_REFUSE_OVERWRITE');
  else await writeFile(destination,png,{flag:'wx'});
  const row={sampleIndex:index>=0?index:null,frame,globalFrame:frame,timeSeconds:frame/30,
   file:directory+'/'+file,bytes:png.length,png_sha256:captured.png_sha256,raw_rgba_sha256:captured.raw_rgba_sha256,
   directRendererOutput:true,newDrawExecuted:true,existingIdenticalPngPreserved:existing,captureWallMilliseconds:performance.now()-at,
   directorSample:captured.directorSample,diagnostic:diagnostic(captured.diagnostic)};
  full.push({...row,diagnostic:captured.diagnostic});
  if(index>=0)report.frames.push(row);if(adjacentFrames.includes(frame))report.adjacentFrames.push(row);
  console.log(JSON.stringify({globalFrame:frame,sampleIndex:row.sampleIndex,file:row.file,pngSha256:row.png_sha256}));
 }
 assert.equal(report.frames.length,16);assert.equal(report.adjacentFrames.length,9);
 assert.equal(new Set(report.frames.map(x=>x.globalFrame)).size,16);
 assert.deepEqual(runtime.errors,[]);await runtime.close();runtime=null;
 assert.equal(hash(await readFile(sources.planFile)),sourceHash,'SOURCE_SCENE_CHANGED_AFTER_DRAW');
 report.status='FRAME_RENDER_PASS';report.visualGate='VISUAL_REVIEW_REQUIRED';report.actualFramesRendered=allFrames.length;
}catch(e){failure=e;report.status='FRAME_RENDER_FAILED';report.error=String(e.stack);}
finally{
 try{await runtime?.close();}catch(e){failure??=e;report.closeError=String(e.stack);}
 report.completedAtUtc=new Date().toISOString();report.wallSeconds=(performance.now()-started)/1000;
 await writeFile(path.join(ROOT,'.private/FULL_FRAME_DIAGNOSTICS.json'),JSON.stringify(full)+'\n');
 const file=path.join(ROOT,'proof/FRAME_RENDER_REPORT.json');await writeFile(file+'.writing',JSON.stringify(report,null,2)+'\n');await rename(file+'.writing',file);
 await unlink(lockFile);
}
if(failure)throw failure;
console.log(JSON.stringify({status:report.status,frames:16,actualFramesRendered:report.actualFramesRendered,backend:report.backend,seconds:report.wallSeconds,visualQualityApproved:false}));
