import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {normalizeProductionVisualProfile,validateAreaColorBindings,productionAreaStyle,evaluateProductionGeometryClock} from '../production_visual_profile.mjs';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 plan=JSON.parse(await readFile(new URL('../fixtures/PLAN_80S.json',import.meta.url),'utf8')),
 hook=registerHooks({resolve(s,c,next){if(s.startsWith('/modules/'))return{url:new URL('file://'+path.join(engine,'web/map_infographic_v1',s.slice(9))).href,shortCircuit:true};return next(s,c);}});
let compileProductionFocusPlan,evaluateProductionFocusFrame,deriveConservativeFocusBounds,geometryScreenSafety;
try{({compileProductionFocusPlan,evaluateProductionFocusFrame,deriveConservativeFocusBounds,geometryScreenSafety}=await import('../production_camera.mjs'));}finally{hook.deregister();}
test('source-qualified area colors bind supplied polygons; no complement or inferred unit ownership',()=>{
 const before=JSON.stringify(plan),bindings=validateAreaColorBindings(plan.productionV3.visualBindings.areaStyles,plan.legacyScenePlan,plan.productionV3.visualProfile.palette);
 assert.equal(bindings.length,5);assert.ok(bindings.every(row=>row.enemyComplementAdmitted===false&&row.measuredMilitaryControl===false));
 assert.deepEqual(bindings[0].color,plan.productionV3.visualProfile.palette[bindings[0].colorRole]);
 for(const change of [{areaId:'INVENTED'},{sourceGeometryRef:'WRONG'},{sourceStateId:'INVENTED'},{enemyComplementAdmitted:true},{sourceProof:{factsSHA256:'x',fields:['madeup']}}]){
  const rows=structuredClone(plan.productionV3.visualBindings.areaStyles);Object.assign(rows[0],change);
  assert.throws(()=>validateAreaColorBindings(rows,plan.legacyScenePlan,plan.productionV3.visualProfile.palette));
 }
 assert.equal(JSON.stringify(plan),before);
});
test('white core / gold halo and strong fill use original role style without decorative area contours',()=>{
 const profile=normalizeProductionVisualProfile(),style=productionAreaStyle(profile,[.1,.6,.9]);
 assert.deepEqual(style.AREA.fillColor,[.1,.6,.9,.62]);assert.equal(style.AREA.coreColor[3],0);assert.equal(style.AREA.glowGain,0);
 assert.equal(style.FRONT.width,4.8);assert.deepEqual(style.FRONT.coreColor,[1,.98,.91,1]);assert.deepEqual(style.FRONT.glowColor,[1,.66,.16,1]);
 assert.equal(profile.scalarV2ClassifierReused,false);assert.throws(()=>normalizeProductionVisualProfile({frontCoreWidthPixels:100}));
 assert.throws(()=>normalizeProductionVisualProfile({territoryOpacity:1}));
});
test('all 2400 V3 frames use explicit supplied source clock, arrival/reveal/holds and exact endpoints',()=>{
 let prior=-1;
 for(let frame=0;frame<plan.totalFrames;frame++){
  const actual=evaluateProductionGeometryClock(plan,frame),row=plan.productionV3.geometrySchedule.find(item=>frame>=item.startFrame&&frame<item.endFrame);
  assert.equal(actual.globalFrame,frame);assert.equal(actual.scheduleId,row.scheduleId);assert.equal(actual.eventDateFrontPrecisionClaimed,false);
  if(row.mode==='ARRIVAL_NO_EVENT'){assert.equal(actual.eventEnabled,false);assert.equal(actual.sourceGeometryFrame,null);continue;}
  assert.ok(Number.isInteger(actual.sourceGeometryFrame));assert.ok(actual.sourceGeometryFrame>=plan.legacyScenePlan.timing.event_start_frame);
  if(frame===row.startFrame)assert.equal(actual.sourceGeometryFrame,row.sourceStartFrame);
  if(frame===row.endFrame-1)assert.equal(actual.sourceGeometryFrame,row.sourceEndFrame);
  if(row.mode==='HOLD_SUPPLIED_SNAPSHOT')assert.equal(row.sourceStartFrame,row.sourceEndFrame);
  prior=actual.sourceGeometryFrame;
 }
 assert.ok(prior>=0);assert.throws(()=>evaluateProductionGeometryClock(plan,plan.totalFrames));
});
const line={type:'LineString',coordinates:[[-3,-2],[3,2]]},safe=[48,72,1032,1848],base=[-10,-20,10,20],anchor=[0,0];
test('global event focus uses full supplied geometry, original floor, safe area and smooth endpoint hold',()=>{
 const chapters=[{chapterId:'A',startFrame:0,endFrame:100},{chapterId:'B',startFrame:100,endFrame:200}],
  geometry={A:[line],B:[{type:'LineString',coordinates:[[-1,0],[7,3]]}]},
  p=compileProductionFocusPlan({chapters,totalFrames:200,approvedBounds:base,safeArea:safe,anchor,geometriesForChapter:c=>geometry[c.chapterId],approachFrames:30});
 assert.equal(p.ownership.newClosestDetailCertified,false);assert.ok(p.entries.every(row=>row.closerThanParentApprovedFloor===false));
 for(let frame=0;frame<200;frame++){
  const row=evaluateProductionFocusFrame(p,frame),b=row.flatBounds;
  assert.ok(b[2]-b[0]>=20-1e-12&&b[3]-b[1]>=40-1e-12);assert.equal(row.localAdmissionGranted,false);
  assert.deepEqual(evaluateProductionFocusFrame(p,frame),row);
  assert.equal(geometryScreenSafety({geometries:geometry[frame<100?'A':'B'],bounds:b,safeArea:safe}).wholeSuppliedGeometrySafe,true);
 }
 assert.deepEqual(evaluateProductionFocusFrame(p,100).flatBounds,evaluateProductionFocusFrame(p,99).flatBounds);
 assert.equal(evaluateProductionFocusFrame(p,199).cameraLocked,true);
});
test('unsafe protected graphics or approach crop retain preceding approved view instead of granting LOCAL',()=>{
 const p=compileProductionFocusPlan({chapters:[{chapterId:'A',startFrame:0,endFrame:100}],totalFrames:100,approvedBounds:base,
  safeArea:safe,anchor,geometriesForChapter:()=>[{type:'LineString',coordinates:[[2,0],[6,3]]}],
  validateBounds:bounds=>({valid:JSON.stringify(bounds)===JSON.stringify(base)})});
 assert.equal(p.entries[0].decision,'USE_CURRENT_VIEW');assert.equal(p.entries[0].reason,'PROTECTED_NATIVE_GRAPHICS_NOT_SAFE');
 for(const frame of [0,50,99])assert.deepEqual(evaluateProductionFocusFrame(p,frame).flatBounds,base);
 const wide=deriveConservativeFocusBounds({geometries:[{type:'LineString',coordinates:[[-15,0],[15,0]]}],anchor,approvedBounds:base,safeArea:safe});
 assert.ok(wide.bounds[2]-wide.bounds[0]>=30);assert.equal(wide.localAdmissionGranted,false);
});
test('unsafe current view is blocked rather than silently used as geometry or protected-layout fallback',()=>{
 const input={chapters:[{chapterId:'UNSAFE',startFrame:0,endFrame:100}],totalFrames:100,approvedBounds:base,safeArea:safe,anchor,
  geometriesForChapter:()=>[line]};
 assert.throws(()=>compileProductionFocusPlan({...input,validateBounds:()=>({valid:false})}),/PRODUCTION_FOCUS_NO_SAFE_CURRENT_VIEW/);
 assert.throws(()=>compileProductionFocusPlan({...input,geometriesForChapter:()=>[{type:'LineString',coordinates:[[-100,0],[100,0]]}]}),/PRODUCTION_FOCUS_NO_SAFE_CURRENT_VIEW/);
});
test('initial line reveal keeps original detail lock and framing; focus starts only in a later chapter',()=>{
 const shifted={type:'LineString',coordinates:[[2,0],[6,3]]},
  p=compileProductionFocusPlan({chapters:[{chapterId:'INITIAL',startFrame:60,endFrame:200},{chapterId:'LATER',startFrame:200,endFrame:400}],
   totalFrames:400,approvedBounds:base,safeArea:safe,anchor,geometriesForChapter:()=>[shifted],preserveInitialView:true});
 for(let frame=60;frame<200;frame++){const state=evaluateProductionFocusFrame(p,frame);assert.deepEqual(state.flatBounds,base);assert.equal(state.cameraLocked,true);}
 assert.equal(p.entries[0].decision,'USE_CURRENT_VIEW');assert.match(p.entries[0].reason,/INITIAL_PARENT_DETAIL_LOCK/);
 assert.deepEqual(evaluateProductionFocusFrame(p,200).flatBounds,base);
 assert.equal(evaluateProductionFocusFrame(p,201).cameraLocked,false);
});
