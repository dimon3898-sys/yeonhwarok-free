import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {validatePresentationFlows,validateHighlightRing,bindPresentationFlows,composePresentationFlowControls,highlightRingAt} from '../../recovery/universal-presentation-v2/presentation_flow.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {resolveRegionPlan} from '../../recovery/universal-presentation-v2/region_source.mjs';
import {compilePresentationCameraPlan,compilePresentationEnginePlan,evaluatePresentationCameraFrame,projectBounds,reprojectFlowPresentation,assertMovingProjectionAdmission} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
const p=new URL('./',import.meta.url),request=JSON.parse(await fs.readFile(new URL('RUNTIME_REQUEST.json',p))),{scene,region,presentation}=request.segments[0];
const base=compileExistingEnginePlan(scene),rows=[];
const test=(id,fn)=>{try{fn();rows.push({id,status:'PASS'});}catch(e){rows.push({id,status:'FAIL',message:e.message,stack:e.stack});}};
const options=presentation.flow;
test('new opt-in timing binds exact original event length',()=>{const r=validatePresentationFlows(options,{scene,engines:base});const e=bindPresentationFlows(base,r);assert.equal(e.plans[0].plan.totalFrames,156);assert.equal(e.plans[0].plan.holdFrame,126);});
test('omitted opt-in returns same new-scene engine object',()=>assert.equal(bindPresentationFlows(base,undefined),base));
for(const [id,mutate,code]of[
 ['unknown field',x=>x[0].countryName='arbitrary',/FLOW_FIELDS/],['unknown route',x=>x[0].routeId='MISSING',/SUPPLIED_UNIQUE/],['duplicate route',x=>x.push(structuredClone(x[0])),/SUPPLIED_UNIQUE/],['changed event duration',x=>x[0].timing.travel_frames++,/ORIGINAL_CLOCK/],['unbounded glow',x=>x[0].style.glowRadius=100,/STYLE_RANGE/],['invisible core',x=>x[0].style.coreColor[3]=0,/VISIBLE_CORE/],['null trail',x=>x[0].trail=null,/TRAIL_FIELDS/],['too many echoes',x=>x[0].trail.echoes=20,/TRAIL_RANGE/],['unknown reveal',x=>x[0].reveal.mode='RANDOM',/REVEAL_RANGE/]])test('reject '+id,()=>{const x=structuredClone(options);mutate(x);assert.throws(()=>validatePresentationFlows(x,{scene,engines:base}),code);});
test('ring cannot cross final hold',()=>assert.throws(()=>validateHighlightRing({frames:20,radiusPx:60,color:[1,1,1,1]},{startFrame:140,endFrame:180,totalFrames:180,holdFrames:30}),/FINISH_BEFORE_HOLD/));
test('single ring has exact zero endpoints and no repetition',()=>{const h=presentation.highlights[0];assert.equal(highlightRingAt(h,0,[500,900]).alpha,0);assert.ok(highlightRingAt(h,10,[500,900]).alpha>.9);assert.equal(highlightRingAt(h,23,[500,900]).alpha,0);assert.equal(highlightRingAt(h,24,[500,900]),null);});
let samples=[];
try{
 const rp=await resolveRegionPlan({scene,region}),plan=compilePresentationCameraPlan({scene,region,nativePlan:rp.nativePlan,baseCameraPlan:rp.baseCameraPlan,presentation}),engines=compilePresentationEnginePlan({scene,presentation});
 const binding=engines.plans[0],analysisProject=p=>projectBounds(plan.analysisBounds,p),analysisPrimitive=compileFlowRoute(binding.plan.intent,{project:analysisProject}),safe=rp.nativePlan.layout.safe;
 for(let f=0;f<180;f++){
  const camera=evaluatePresentationCameraFrame(plan,f),project=p=>projectBounds(camera.flatBounds,p),local=f-engines.globalEventStartFrame;
  for(const h of presentation.highlights){const l=scene.locations.find(l=>l.id===h.locationId),pulse=highlightRingAt(h,f,project(l.anchor));if(pulse&&pulse.alpha>0){const [x,y]=pulse.position,r=pulse.radius+2;assert.ok(x-r>=safe[0]&&x+r<=safe[2]&&y-r>=safe[1]&&y+r<=safe[3],`ring outside ${h.id}/${f}`);}}
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
const result={status:rows.every(x=>x.status==='PASS')?'PASS':'FAIL',scope:'New V3 opt-in contract and changed input only; not V1/V2 tests or renders',rows,samples,oldPassReruns:0};
await fs.writeFile(new URL('DELTA_TEST_RESULT.json',p),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:result.status,tests:rows.length,failures:rows.filter(x=>x.status==='FAIL')}));if(result.status!=='PASS')process.exitCode=1;
