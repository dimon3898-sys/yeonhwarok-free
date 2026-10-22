/** Synthetic CPU layout tests plus separately labeled archived actual diagnostics. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
const web=new URL('../../../web/map_infographic_v1/',import.meta.url),
 production=new URL('../../universal-production-v3/production_visual_profile.mjs',import.meta.url),
 old=new URL('../../astra-event-director-v2/',import.meta.url),copy=x=>structuredClone(x),
 sha=x=>createHash('sha256').update(x).digest('hex');
const hook=registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('/modules/'))return{url:new URL(specifier.slice(9),web).href,shortCircuit:true};
 if(specifier==='/production-v3/production_visual_profile.mjs')return{url:production.href,shortCircuit:true};
 return next(specifier,context);
}});
let api,chooseMetricPlacement;
try{api=await import('../stable_annotation.mjs');({chooseMetricPlacement}=await import(new URL('event_layout_adapter_v1.mjs',web)));}
finally{hook.deregister();}
const binding={sceneSHA256:'a'.repeat(64),cameraSHA256:'b'.repeat(64),layoutSHA256:'c'.repeat(64),codeSHA256:'d'.repeat(64)},
 safeArea=[0,0,500,800];
function frame(globalFrame){return{globalFrame,protectedGraphics:[{kind:'MARKER',box:[300,300,340,340]}],
 boundarySegments:[{a:[30,370],b:[470,370],radiusPx:8}]};}
function input(){return{chapterId:'synthetic-chapter',startFrame:10,endFrame:14,safeArea:copy(safeArea),binding:copy(binding),
 labels:[{id:'event',atlasEnvelope:[170,45],preferredAnchor:[250,120]}],frames:[10,11,12,13].map(frame)};}
function draw(plan,frame){return{...copy(frame),binding:copy(plan.binding),labels:copy(plan.labels)};}
function overlaps(a,b){return a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];}

test('SYNTHETIC: existing glyph dimensions and original Layout produce one immutable reservation',()=>{
 const args=input(),snapshot=JSON.stringify(args),plan=api.compileStableAnnotationChapter(args);
 assert.equal(plan.status,'READY');assert.equal(JSON.stringify(args),snapshot);
 assert.deepEqual(plan.placements.event.atlasEnvelope,[170,45]);
 assert.equal(plan.placements.event.placement.version,'EVENT_LAYOUT_ADAPTER_V1');
 assert.equal(plan.placements.event.version,'AREA_ANNOTATION_V3');
 assert.equal(Object.isFrozen(plan.placements.event.placement.roi),true);
 for(const f of args.frames){const result=api.evaluateStableAnnotationFrame(plan,draw(plan,f));
  assert.equal(result.placements,plan.placements);assert.equal(result.nativeGraphicsMoved,false);}
});
test('SYNTHETIC: moving obstacles do not switch title bands after random seek',()=>{
 const args=input();args.frames[1].protectedGraphics.push({kind:'TEXT',box:[200,85,300,150]});
 const plan=api.compileStableAnnotationChapter(args);assert.equal(plan.status,'READY');
 const sequential=args.frames.map(f=>JSON.stringify(api.evaluateStableAnnotationFrame(plan,draw(plan,f)).placements));
 for(const i of [3,0,2,1,3,1,0])assert.equal(JSON.stringify(api.evaluateStableAnnotationFrame(plan,draw(plan,args.frames[i])).placements),sequential[i]);
 const roi=plan.placements.event.reservation.box;
 for(const f of args.frames)for(const row of f.protectedGraphics)assert.equal(overlaps(roi,row.box),false);
});
test('SYNTHETIC: boundary radius, native marker and text reservations are all preserved',()=>{
 const args=input();args.labels[0].preferredAnchor=[250,370];
 const plan=api.compileStableAnnotationChapter(args);assert.equal(plan.status,'READY');
 assert.equal(overlaps(plan.placements.event.reservation.box,[22,362,478,378]),false);
 assert.equal(plan.boundaryProtection,'UNCHANGED_NATIVE_RADIUS_AABB_UNION_OVER_ALL_FRAMES');
 assert.equal(plan.uniqueNativeExclusions,2);
});
test('SYNTHETIC: event and qualifier have different full-atlas reservations',()=>{
 const args=input();args.labels.push({id:'qualifier',atlasEnvelope:[260,55],preferredAnchor:[250,120]});
 const plan=api.compileStableAnnotationChapter(args);assert.equal(plan.status,'READY');
 assert.equal(overlaps(plan.placements.event.reservation.box,plan.placements.qualifier.reservation.box),false);
 for(const f of args.frames)assert.equal(api.evaluateStableAnnotationFrame(plan,draw(plan,f)).status,'LAYOUT_VALIDATED');
});
test('SYNTHETIC: incomplete, duplicated, reordered or overbroad frame coverage is blocked',()=>{
 for(const mutate of [x=>x.frames.pop(),x=>x.frames[2].globalFrame=11,x=>x.frames.reverse(),x=>x.endFrame=15]){
  const args=input();mutate(args);assert.equal(api.compileStableAnnotationChapter(args).status,'BLOCKED');}
});
test('SYNTHETIC: projected graphics and boundary arrays are independently mandatory',()=>{
 for(const field of ['protectedGraphics','boundarySegments']){const args=input();delete args.frames[1][field];
  assert.equal(api.compileStableAnnotationChapter(args).reason,'STABLE_ANNOTATION_COMPLETE_PROJECTED_CONTEXT_REQUIRED');}
});
test('SYNTHETIC: full-screen union with no common safe slot fails closed',()=>{
 const args=input();args.frames.forEach((f,i)=>{f.boundarySegments=[];f.protectedGraphics=[{kind:'PANEL',box:i%2?[0,400,500,800]:[0,0,500,400]}];});
 const plan=api.compileStableAnnotationChapter(args);
 assert.equal(plan.status,'BLOCKED');assert.equal(plan.reason,'STABLE_ANNOTATION_NO_CHAPTER_WIDE_SLOT');
 assert.equal(plan.renderAllowed,false);
});
test('SYNTHETIC: measured atlas, positive boundary radius and safe viewport are mandatory',()=>{
 for(const malformed of [null,[],42])assert.equal(api.compileStableAnnotationChapter(malformed).status,'BLOCKED');
 for(const mutate of [x=>x.labels[0].atlasEnvelope=[0,45],x=>x.frames[0].boundarySegments[0].radiusPx=0,
  x=>x.safeArea=[500,0,0,800],x=>x.labels.push(copy(x.labels[0])),x=>x.binding.sceneSHA256='unknown']){
  const args=input();mutate(args);assert.equal(api.compileStableAnnotationChapter(args).status,'BLOCKED');}
 const args=input();args.labels[0].atlasEnvelope=[501,45];
 assert.equal(api.compileStableAnnotationChapter(args).reason,'STABLE_ANNOTATION_ATLAS_EXCEEDS_SAFE_AREA');
});
test('SYNTHETIC: changed current-frame context rejects even a formerly admitted plan',()=>{
 const args=input(),plan=api.compileStableAnnotationChapter(args),current=draw(plan,args.frames[0]);
 current.protectedGraphics.push({kind:'MARKER',box:[...plan.placements.event.reservation.box]});
 assert.throws(()=>api.evaluateStableAnnotationFrame(plan,current),/PROJECTED_CONTEXT_DRIFT/);
 current.protectedGraphics.pop();current.boundarySegments[0].a[0]++;
 assert.throws(()=>api.evaluateStableAnnotationFrame(plan,current),/PROJECTED_CONTEXT_DRIFT/);
});
test('SYNTHETIC: changed atlas, binding, frame range or safe area rejects drawing',()=>{
 const args=input(),plan=api.compileStableAnnotationChapter(args);
 for(const [mutate,expected] of [[x=>x.labels[0].atlasEnvelope[0]++,/DRAW_MEASURED_ATLAS_DRIFT/],
  [x=>x.binding.cameraSHA256='f'.repeat(64),/SOURCE_BINDING_DRIFT/],
  [x=>x.globalFrame=14,/FRAME_OUTSIDE_CHAPTER/],[x=>x.safeArea=[1,0,500,800],/SAFE_AREA_DRIFT/]]){
  const current=draw(plan,args.frames[0]);mutate(current);assert.throws(()=>api.evaluateStableAnnotationFrame(plan,current),expected);}
});
test('SYNTHETIC: deserialized READY and compact receipt cannot authorize a draw',()=>{
 const args=input(),plan=api.compileStableAnnotationChapter(args),receipt=api.stableAnnotationReceipt(plan);
 assert.equal(receipt.renderingNotPerformed,true);assert.equal(receipt.nvidiaHardwareVerified,false);
 assert.equal(receipt.visualQualityApproved,false);
 for(const fake of [copy(plan),receipt])assert.throws(()=>api.evaluateStableAnnotationFrame(fake,draw(plan,args.frames[0])),/COMPILED_PLAN_REQUIRED/);
});
test('SYNTHETIC: later mutation of caller inputs cannot rewrite the original plan',()=>{
 const args=input(),plan=api.compileStableAnnotationChapter(args),first=draw(plan,args.frames[0]);
 args.frames[0].protectedGraphics[0].box[0]++;args.labels[0].atlasEnvelope[0]++;args.binding.sceneSHA256='f'.repeat(64);
 assert.equal(api.evaluateStableAnnotationFrame(plan,first).status,'LAYOUT_VALIDATED');
});
test('SYNTHETIC: exclusion order and duplicate native guards do not affect deterministic placements',()=>{
 const args=input(),first=api.compileStableAnnotationChapter(args);
 for(const f of args.frames)f.protectedGraphics.push(copy(f.protectedGraphics[0]));
 const second=api.compileStableAnnotationChapter(args);
 assert.deepEqual(api.stableAnnotationReceipt(first),api.stableAnnotationReceipt(second));
});
test('ARCHIVED ACTUAL ROI: saved f641→642 same-chapter title relocation is 1487 pixels',async()=>{
 const report=JSON.parse(await readFile(new URL('reports/VISUAL_INSPECTION.json',old))),
  step=report.measuredTitleRelocationFromActualDiagnostics.largestSteps.find(x=>x.frame===642);
 assert.equal(step.previousFrame,641);assert.deepEqual(step.fromROI,[311,1646,769,1701]);
 assert.deepEqual(step.toROI,[311,159,769,214]);assert.equal(step.titleCenterStepPixels,1487);
 assert.equal(report.titleRelocationRemediation.status,'NOT_IMPLEMENTED_IN_THIS_CAPTURE');
});
let actualPresent=true;try{for(const f of [640,641,642])await stat(new URL(`.private/frames/${String(f).padStart(4,'0')}.json`,old));}
catch{actualPresent=false;}
test('ARCHIVED ACTUAL GUARDS: three captured-frame exclusions keep the measured common reservation (not whole-chapter proof)',
 {skip:!actualPresent},async()=>{
 const records=await Promise.all([640,641,642].map(async f=>JSON.parse(await readFile(new URL(`.private/frames/${String(f).padStart(4,'0')}.json`,old))))),
  placements=records.map(x=>x.eventDirector.sourceAvailability.event.placement),
  args={chapterId:'archived-three-frame-regression-only',startFrame:640,endFrame:643,safeArea:placements[0].safeArea,
   binding:{sceneSHA256:records[0].sceneHash,cameraSHA256:sha(await readFile(new URL('camera_bridge.mjs',old))),
    layoutSHA256:sha(await readFile(new URL('event_layout_adapter_v1.mjs',web))),codeSHA256:sha(await readFile(new URL('../stable_annotation.mjs',import.meta.url)))},
   labels:[{id:'event',atlasEnvelope:placements[0].atlasDimensions,preferredAnchor:[540,252]}],
   frames:records.map((x,i)=>({globalFrame:x.globalFrame,
    // These are the original consumer's already-expanded graphics AND boundary
    // AABBs, not guessed geometry or omitted boundary protection.
    protectedGraphics:placements[i].protectedBoxes.map(box=>({kind:'PANEL',box})),boundarySegments:[]}))};
 assert.deepEqual(args.labels[0].atlasEnvelope,[458,55]);
 assert.equal(placements[1].protectedBoxes.length,507);
 const plan=api.compileStableAnnotationChapter(args);
 assert.equal(plan.status,'READY');
 assert.deepEqual(plan.placements.event.reservation.box,[311,101.25396825396825,769,156.25396825396825]);
 for(const f of args.frames){const result=api.evaluateStableAnnotationFrame(plan,draw(plan,f));
  assert.deepEqual(result.placements.event.reservation.box,plan.placements.event.reservation.box);
  for(const row of f.protectedGraphics)assert.equal(overlaps(result.placements.event.reservation.box,row.box),false);}
 const full={...args,chapterId:'chapter-04',startFrame:600,endFrame:800};
 assert.equal(api.compileStableAnnotationChapter(full).reason,'STABLE_ANNOTATION_ALL_CHAPTER_FRAMES_REQUIRED');
 console.log(JSON.stringify({evidence:'ARCHIVED_ACTUAL_THREE_FRAME_GUARD_REGRESSION',status:plan.status,
  reservation:plan.status==='READY'?plan.placements.event.reservation.box:null,
  guardCounts:placements.map(x=>x.protectedBoxes.length),wholeChapterAdmission:false,
  newDrawPerformed:false,nvidiaHardwareVerified:false,visualQualityApproved:false}));
});
