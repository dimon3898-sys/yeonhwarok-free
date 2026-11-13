/** V2 input-only compile/capture evidence. No product renderer changes. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest,capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),out='/workspace/japan6s-v2-cpu-a1';
const hash=b=>createHash('sha256').update(b).digest('hex');
const write=(dir,name,value)=>fs.writeFile(path.join(dir,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
const raw=await fs.readFile(path.join(p,'JAPAN_V2_SCENE_INPUT.json')),input=JSON.parse(raw);
const cp=JSON.parse(await fs.readFile(path.join(p,'CHECKPOINT.json')));
let stage='V2_FORMAL_COMPILE',runtimeSHA=null;
try {
 const result=await analyzePresentationPrompt(input);
 await write(p,'COMPILE_RESULT.json',result);
 assert.equal(result.status,'PASS',JSON.stringify(result.issues));
 const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:result.totalFrames,sourceInputSHA256:result.inputSHA256,
  segments:result.renderRequests.map(({sceneId,startFrame,endFrame,scene,region,presentation})=>({sceneId,startFrame,endFrame,scene,region,presentation})),
  transitions:result.transitionPlan,inputTrace:{inputFile:'JAPAN_V2_SCENE_INPUT.json',fileSHA256:hash(raw),compilerInputSHA256:result.inputSHA256,compilerVersion:result.compilerVersion}};
 stage='V2_RUNTIME_REQUEST_VALIDATION';validateRuntimeRequest(request);assert.equal(request.totalFrames,180);
 await write(p,'RUNTIME_REQUEST.json',request);
 await write(p,'COMPILED_SCENES.json',request.segments.map(s=>({sceneId:s.sceneId,scene:s.scene})));
 const packageFile=path.join(p,'RUNTIME_REQUEST.json');runtimeSHA=hash(await fs.readFile(packageFile));
 await write(p,'INPUT_ADMISSION.json',{status:'V2_FORMAL_COMPILE_AND_RUNTIME_SCHEMA_PASS',inputSHA256:hash(raw),runtimeSHA256:runtimeSHA,compilerInputSHA256:result.inputSHA256,frames:180,oldPassReruns:0,productCodeChanges:0,GPUExecutions:0,sourcePreparation:'Next: performed once by official capturePresentation before any draw'});
 cp.status='V2_COMPILE_PASS_PENDING_CPU';cp.firstIncomplete='V2_OFFICIAL_SOURCE_PREPARATION_AND_CAPTURE';
 await fs.writeFile(path.join(p,'CHECKPOINT.json'),JSON.stringify(cp,null,2)+'\n');
 stage='V2_OFFICIAL_SOURCE_PREPARATION_AND_CAPTURE';
 const receipt=await capturePresentation({packageFile,outputRoot:out,expectedSHA256:runtimeSHA,depsRoot:process.env.WORLD_ENGINE_NODE_DEPS});
 stage='V2_NEW_INPUT_FRAME_ASSERTIONS';
 const rows=JSON.parse(await fs.readFile(path.join(out,'FRAME_EVIDENCE.json'))).frames;
 assert.equal(rows.length,180);assert.equal(receipt.video.frames,180);assert.equal(receipt.video.fullDecode,'PASS');
 assert.equal(receipt.sourceCredits[0].sourceId,'NE1_EAST_ASIA_NATIVE_V1');
 const summary=rows.map((row,f)=>{
  assert.equal(row.frame,f);const d=row.diagnostic;
  assert.equal(d.glError,0);assert.equal(d.material.fullViewportCovered,true);
  assert.ok(d.suppliedLocations.every(l=>l.inSafe));assert.equal(d.suppliedLocations.length,3);
  const labels=d.presentationLabels.drawn;
  for(const [id,start] of [['tokyo-label',0],['nagoya-label',72],['kyoto-label',114]]){
   if(f<start)assert.ok(!labels.some(l=>l.id===id));
   if(f>=start+16)assert.ok(labels.some(l=>l.id===id),'Missing stable label '+id+' at '+f);
  }
  const feature=d.features.find(x=>x.id==='ILLUSTRATIVE_ROUTE');
  if(f<60)assert.equal(feature,undefined);else{
   assert.ok(feature.admission);if(f>=89)assert.equal(feature.routeFraction,1);
   if(feature.draw.object)assert.deepEqual(feature.draw.object.graphicDimensions,[64,64]);
  }
  return {frame:f,rawSHA256:row.rawSHA256,nonBlackPixels:row.nonBlackPixels,cameraBounds:d.camera.bounds,
   locations:d.suppliedLocations,labels:labels.map(l=>({id:l.id,projected:l.projected,pinDrawn:l.pinDrawn})),
   route:feature?{state:feature.state,routeFraction:feature.routeFraction,objectFraction:feature.objectFraction,projectedRoute:feature.projectedRoute,draw:feature.draw}:null,
   source:{id:receipt.sourceCredits[0].sourceId,originalSHA256:d.material.sourceOriginalSHA256,terrainSHA256:d.material.terrainSHA256,fullViewportCovered:true},glError:0};
 });
 assert.equal(summary[60].route.routeFraction,0);assert.ok(summary[75].route.routeFraction>0&&summary[75].route.routeFraction<1);
 for(let f=150;f<180;f++){assert.equal(rows[f].rawSHA256,rows[150].rawSHA256);assert.deepEqual(summary[f].cameraBounds,summary[149].cameraBounds);}
 assert.notDeepEqual(summary[0].cameraBounds,summary[59].cameraBounds);
 const span=x=>x.cameraBounds[2]-x.cameraBounds[0];assert.ok(span(summary[149])<span(summary[119]));assert.ok(span(summary[0])<9);
 await write(out,'FRAME_SUMMARY.json',summary);
 await write(out,'NEW_INPUT_RESULT.json',{status:'V2_ACTUAL_CPU_TECHNICAL_PASS_PENDING_VISUAL_COMPARISON',inputSHA256:hash(raw),runtimeSHA256:runtimeSHA,video:receipt.video,frames:180,final30RawFramesIdentical:true,sequentialLabels:['tokyo-label','nagoya-label','kyoto-label'],movingObjectDimensions:[64,64],sourceGeometryAndOriginalRouteUnchanged:true,productCodeChanges:0,oldPassReruns:0,GPUExecutions:0,costKRW:0});
 cp.status='V2_CPU_TECHNICAL_PASS_PENDING_VISUAL_COMPARISON';cp.firstIncomplete='V1_V2_INDEPENDENT_VISUAL_COMPARISON';cp.activeBlocker=null;
 cp.video=receipt.video;cp.nextAction='Inspect existing V1 evidence against actual V2 MP4 frames; no rerender.';
 console.log(JSON.stringify({status:cp.status,video:receipt.video}));
} catch(error) {
 await fs.mkdir(out,{recursive:true});
 const failure={status:'FAIL',stage,code:error.code??String(error.message).split(':')[0],originalMessage:String(error.message),stack:error.stack,inputSHA256:hash(raw),runtimeSHA256:runtimeSHA,classification:stage.includes('COMPILE')||stage.includes('VALIDATION')?'INPUT_OR_CONTRACT':stage.includes('ASSERTIONS')?'ACTUAL_OUTPUT_ASSERTION':'CPU_PREPARATION_OR_CAPTURE',GPUExecutions:0,oldPassReruns:0};
 await write(out,'TASK_FAILURE.json',failure);cp.status='V2_BLOCKED';cp.firstIncomplete=stage;cp.activeBlocker=failure;cp.nextAction='Resolve this failure only; preserve output and logs. Do not advance or rerun any valid PASS.';throw error;
} finally {await fs.writeFile(path.join(p,'CHECKPOINT.json'),JSON.stringify(cp,null,2)+'\n');}
