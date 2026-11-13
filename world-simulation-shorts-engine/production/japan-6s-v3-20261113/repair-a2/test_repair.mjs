import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {validatePresentationFlows,validateHighlightRing,bindPresentationFlows,composePresentationFlowControls,highlightRingAt} from '../../../recovery/universal-presentation-v2/presentation_flow.mjs';
import {compileExistingEnginePlan} from '../../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '../../../web/map_infographic_v1/flow_core_v2.mjs';
import {resolveRegionPlan} from '../../../recovery/universal-presentation-v2/region_source.mjs';
import {compilePresentationCameraPlan,compilePresentationEnginePlan,evaluatePresentationCameraFrame,projectBounds,reprojectFlowPresentation,assertMovingProjectionAdmission} from '../../../recovery/universal-presentation-v2/presentation_plan.mjs';
const p=new URL('./',import.meta.url),request=JSON.parse(await fs.readFile(new URL('RUNTIME_REQUEST.json',p))),{scene,region,presentation}=request.segments[0];
const base=compileExistingEnginePlan(scene),rows=[];
const test=(id,fn)=>{try{fn();rows.push({id,status:'PASS'});}catch(e){rows.push({id,status:'FAIL',message:e.message,stack:e.stack});}};
const options=presentation.flow;
const old=JSON.parse(await fs.readFile(new URL('../JAPAN_V3_SCENE_INPUT.json',p)));
const historical=JSON.parse(await fs.readFile(new URL('../cpu-a1/FRAME_SUMMARY.json',p)));
test('legacy ring clock matches all 180 saved diagnostics',()=>{
 for(const h of old.presentation.highlights)for(let f=0;f<180;f++){
  const actual=highlightRingAt(h,f,[500,900]);
  const saved=historical[f].locationRings?.find(x=>x.id===h.id)?.draw;
  assert.equal(!!actual,!!saved);
  if(actual){assert.equal(actual.radius,saved.radius);assert.equal(actual.alpha,saved.alpha);}
 }
});
test('new contract accepts bounded effects',()=>{validatePresentationFlows(options,{scene,engines:base});for(const h of presentation.highlights)validateHighlightRing(h.ring,{...h,totalFrames:180,holdFrames:30});});
for(const [key,value,pattern] of [['radiusPx',97,/RING_RADIUS/],['widthPx',11,/STYLE_RANGE/],['glowRadiusPx',17,/STYLE_RANGE/],['holdAlpha',.8,/STYLE_RANGE/]])test('reject unsafe '+key,()=>assert.throws(()=>validateHighlightRing({...presentation.highlights[0].ring,[key]:value},{startFrame:0,endFrame:180,totalFrames:180,holdFrames:30}),pattern));
for(const [key,value,pattern] of [['spacingPixels',65,/TRAIL_RANGE/],['alpha',.7,/TRAIL_RANGE/],['scale',0,/TRAIL_SCALE/],['fadeEndFraction',1,/TRAIL_FADE/]])test('reject unsafe trail '+key,()=>{const bad=structuredClone(options);bad[0].trail[key]=value;assert.throws(()=>validatePresentationFlows(bad,{scene,engines:base}),pattern);});
test('destination settles before hold and remains exact through frame179',()=>{const h=presentation.highlights.find(h=>h.id==='destination-settle');const settled=highlightRingAt(h,149,[160,1000]);assert.equal(settled.alpha,.55);for(let f=150;f<180;f++)assert.deepEqual(highlightRingAt(h,f,[160,1000]),settled);assert.equal(highlightRingAt(h,180,[160,1000]),null);});
const fresh=JSON.parse(await fs.readFile(new URL('JAPAN_V3_SCENE_INPUT.json',p)));
test('camera labels geography route and all event clocks preserved',()=>{assert.deepEqual(fresh.data,old.data);assert.deepEqual(fresh.region,old.region);assert.deepEqual(fresh.presentation.camera,old.presentation.camera);assert.deepEqual(fresh.presentation.labels,old.presentation.labels);assert.deepEqual(fresh.presentation.flow[0].timing,old.presentation.flow[0].timing);});
let samples=[];
try{
 const rp=await resolveRegionPlan({scene,region}),plan=compilePresentationCameraPlan({scene,region,nativePlan:rp.nativePlan,baseCameraPlan:rp.baseCameraPlan,presentation}),engines=compilePresentationEnginePlan({scene,presentation});
 const binding=engines.plans[0],analysisProject=p=>projectBounds(plan.analysisBounds,p),analysisPrimitive=compileFlowRoute(binding.plan.intent,{project:analysisProject}),safe=rp.nativePlan.layout.safe;
 for(let f=0;f<180;f++){
  const camera=evaluatePresentationCameraFrame(plan,f),project=p=>projectBounds(camera.flatBounds,p),local=f-engines.globalEventStartFrame;
  for(const h of presentation.highlights){const l=scene.locations.find(l=>l.id===h.locationId),pulse=highlightRingAt(h,f,project(l.anchor));if(pulse&&pulse.alpha>0){const [x,y]=pulse.position,r=pulse.radius+(h.ring.widthPx??1.6)/2+Math.max(1,h.ring.glowRadiusPx??0);assert.ok(x-r>=safe[0]&&x+r<=safe[2]&&y-r>=safe[1]&&y+r<=safe[3],`ring outside ${h.id}/${f}`);}}
  let controls=null;
  if(local>=0){const model=evaluateFlowFrame(binding.plan,local,{primitive:analysisPrimitive,eventContext:{cameraState:plan.analysisCamera,project:analysisProject,safeArea:safe,scalePlan:rp.nativePlan,heightSource:null,protectedBoxes:[]}}),primitive=compileFlowRoute(binding.plan.intent,{project});
   controls=composePresentationFlowControls(reprojectFlowPresentation({modelControls:model,primitive,flowIntent:binding.plan.intent}),primitive,binding.presentationFlow);
   assertMovingProjectionAdmission({primitive,controls,camera,modelCamera:plan.analysisCamera,safeArea:safe,sourceBounds:[104,7,152,63],project,sourceGeometry:binding.plan.intent.route_geometry,currentBounds:camera.flatBounds,protectedGraphics:[],flowIntent:binding.plan.intent});
   assert.ok(controls.routeFraction>=controls.objectFraction);if(f>=150){assert.equal(controls.objectFraction,1);assert.equal(controls.routeFraction,1);assert.equal(controls.arrivalPulse.active,false);}
  }
  samples.push({frame:f,cameraBounds:camera.flatBounds,objectFraction:controls?.objectFraction,routeFraction:controls?.routeFraction});
 }
 assert.notDeepEqual(samples[0].cameraBounds,samples[14].cameraBounds);
 for(let f=150;f<180;f++)assert.deepEqual(samples[f].cameraBounds,samples[149].cameraBounds);
 rows.push({id:'180 new V3 camera/route/ring ROI and final hold math',status:'PASS'});
}catch(e){rows.push({id:'180 new V3 camera/route/ring ROI and final hold math',status:'FAIL',message:e.message,stack:e.stack});}
const result={status:rows.every(x=>x.status==='PASS')?'PASS':'FAIL',scope:'Changed effect contract, bounded projection, protected story invariants; legacy diagnostic comparison uses saved output, no old render/tests rerun',rows,samples,oldPassReruns:0};
await fs.writeFile(new URL('REPAIR_TEST_RESULT.json',p),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:result.status,tests:rows.length,failures:rows.filter(x=>x.status==='FAIL')}));if(result.status!=='PASS')process.exitCode=1;
