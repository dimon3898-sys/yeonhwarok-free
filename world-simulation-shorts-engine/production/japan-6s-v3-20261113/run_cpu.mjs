/** Consume the admitted V3 request once. No repeated compiler or old input. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),out='/workspace/japan6s-v3-cpu-a1',hash=b=>createHash('sha256').update(b).digest('hex');
const cp=JSON.parse(await fs.readFile(path.join(p,'CHECKPOINT.json'))),raw=await fs.readFile(path.join(p,'JAPAN_V3_SCENE_INPUT.json')),request=await fs.readFile(path.join(p,'RUNTIME_REQUEST.json'));
const write=(n,v)=>fs.writeFile(path.join(out,n),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
let stage='V3_PRESERVED_COMPILE_ADMISSION';
try{
 const compile=JSON.parse(await fs.readFile(path.join(p,'COMPILE_RESULT.json'))),delta=JSON.parse(await fs.readFile(path.join(p,'DELTA_TEST_RESULT.json')));
 assert.equal(compile.status,'PASS');assert.equal(delta.status,'PASS');assert.equal(hash(raw),'64985ed280eb1425f1a8cb8dc04d61f515a00ef84e9a9e704c6a60953d2cabbe');assert.equal(hash(request),'e483abd61096c2096df6534d00f0fa63516d1fd3c6e0a196f691f9109c7e7f83');
 stage='V3_OFFICIAL_CPU_PREPARATION_AND_CAPTURE';
 const receipt=await capturePresentation({packageFile:path.join(p,'RUNTIME_REQUEST.json'),outputRoot:out,expectedSHA256:hash(request),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS});
 stage='V3_NEW_FRAME_ASSERTIONS';
 const rows=JSON.parse(await fs.readFile(path.join(out,'FRAME_EVIDENCE.json'))).frames;
 assert.equal(rows.length,180);assert.equal(receipt.video.fullDecode,'PASS');assert.equal(receipt.video.frames,180);assert.match(receipt.runtime.backend,/SwiftShader/);
 const features=rows.map(r=>r.diagnostic.features.find(f=>f.id==='ILLUSTRATIVE_ROUTE'));
 for(let f=0;f<180;f++){
  assert.equal(rows[f].frame,f);assert.equal(rows[f].diagnostic.glError,0);assert.equal(rows[f].diagnostic.material.fullViewportCovered,true);
  if(f<24)assert.equal(features[f],undefined);else{assert.ok(features[f].admission);assert.ok(features[f].routeFraction>=features[f].objectFraction);}
  if(f>=150)assert.equal(rows[f].rawSHA256,rows[149].rawSHA256,'V3_FINAL_HOLD_DIFFERENCE '+f);
 }
 assert.notEqual(rows[0].rawSHA256,rows[14].rawSHA256);
 assert.ok(features.some(f=>f?.draw.echoes?.length===3));assert.ok(features.some(f=>f?.draw.preview?.drawn));
 assert.deepEqual(features[90].draw.object.graphicDimensions,[80,80]);assert.equal(features[149].objectFraction,1);
 assert.ok(features.slice(138,150).some(f=>f.draw.pulses.some(p=>p.endpoint==='ARRIVAL'&&p.alpha>.9)));
 for(const id of ['tokyo-location','nagoya-location'])assert.ok(rows.some(r=>r.diagnostic.locationRings?.some(x=>x.id===id&&x.draw.alpha>.9)));
 for(const [id,start,end] of [['tokyo-intro',8,60],['nagoya-pass',90,106],['kyoto-approach',120,130],['kyoto-arrival',146,180]])for(let f=start;f<end;f++)assert.ok(rows[f].diagnostic.presentationLabels.drawn.some(x=>x.id===id),'Missing label '+id+'/'+f);
 const summary=rows.map(r=>({frame:r.frame,rawSHA256:r.rawSHA256,baseRawSHA256:r.baseRawSHA256,camera:r.diagnostic.camera.bounds,labels:r.diagnostic.presentationLabels,locationRings:r.diagnostic.locationRings,feature:r.diagnostic.features.find(f=>f.id==='ILLUSTRATIVE_ROUTE')??null}));
 await write('FRAME_SUMMARY.json',summary);
 await write('NEW_INPUT_RESULT.json',{status:'V3_CPU_TECHNICAL_PASS_PENDING_VISUAL_REVIEW',video:receipt.video,inputSHA256:hash(raw),runtimeSHA256:hash(request),frames:180,final31RawFramesIdentical:true,objectDimensions:[80,80],actualRings:['TOKYO','NAGOYA','KYOTO_APPROACH','FLOW_ARRIVAL'],actualRouteEffects:['FOLLOW_OBJECT_REVEAL','BRIGHT_CORE','CYAN_HALO','FAINT_PLANNED_ROUTE','THREE_VECTOR_ECHOES'],oldPassReruns:0,GPUExecutions:0,costKRW:0});
 cp.status='V3_CPU_TECHNICAL_PASS_PENDING_VISUAL_REVIEW';cp.firstIncomplete='V3_INDEPENDENT_VISUAL_REVIEW';cp.video=receipt.video;cp.activeBlocker=null;
 console.log(JSON.stringify({status:cp.status,video:receipt.video}));
}catch(e){await fs.mkdir(out,{recursive:true});const failure={stage,message:e.message,stack:e.stack,inputSHA256:hash(raw),runtimeSHA256:hash(request),oldPassReruns:0,GPUExecutions:0};await write('TASK_FAILURE.json',failure);cp.status='V3_CPU_BLOCKED';cp.firstIncomplete=stage;cp.activeBlocker=failure;throw e;}
finally{await fs.writeFile(path.join(p,'CHECKPOINT.json'),JSON.stringify(cp,null,2)+'\n');}
