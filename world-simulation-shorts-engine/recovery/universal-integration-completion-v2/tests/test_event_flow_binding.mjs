import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {canonicalSourceJSON,canonicalSourceSHA,normalizeEventFlowRequest,compileCompletionEventFlow,
 evaluateCompletionEventFlowFrame,createCompletionEventFlowPass,completionProtectedGraphics} from '../event_flow_binding.mjs';
import {evaluateFlowFrame,compileFlowIntent,compileFlowPlan} from '../../../web/map_infographic_v1/flow_core_v2.mjs';
import {compileEventIntent} from '../../../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan} from '../../../web/map_infographic_v1/event_timeline_v1.mjs';
import {evaluateGeographicLineReveal} from '../../../web/map_infographic_v1/event_line_v1.mjs';
import {classifyEventLineProtection} from '../../../web/map_infographic_v1/event_occlusion_policy_v1.mjs';
const fixture=JSON.parse(await readFile(new URL('../fixtures/SYNTHETIC_GLOBAL_EVENT.json',import.meta.url),'utf8'));
const clone=value=>structuredClone(value),theme={primary:[.7,.1,.2],secondary:[.2,.1,.8],primaryWidth:5,secondaryWidth:4,glowRadius:2,glowGain:.08};
function compiled(request=fixture.request,sources=fixture.trustedSources){return compileCompletionEventFlow(request,
 {fps:fixture.fps,totalFrames:fixture.totalFrames,trustedSources:sources,allowSynthetic:true});}
function context(){return{project:([lon,lat])=>[200+(lon+61)*100,500+(-lat-28)*150],safeArea:[48,72,1032,1848],
 cameraState:{scale:'REGIONAL',projection:'EXISTING_NATIVE_TEST_PROJECTION',cameraLocked:true,settle:{locked:true},
  camera:{flatBounds:[-61,-33,-55,-27]},admission:{status:'LOCAL_NOT_ADMITTED',effectiveScale:'REGIONAL',localUsed:false}},
 scalePlan:{scale:{name:'REGIONAL'}},nativeBoundarySourceVerified:true,boundarySegments:[],protectedGraphics:[{kind:'MARKER',box:[390,640,410,660]},
  {kind:'TEXT',box:[800,100,950,150]}]};}
function instrument(){const calls=[],owned=[];const create=kind=>options=>{const pass={draw(value){calls.push({kind,value:JSON.parse(JSON.stringify(value,(_key,item)=>typeof item==='function'?'CPU_NATIVE_PROJECTION_FUNCTION':item))});return{drawn:true,cpuSpy:true};},dispose(){owned.push(kind);}};return pass;};
 return{calls,owned,consumers:{line:create('line'),flow:create('flow'),area:create('area'),metric:({intent})=>({
  primitive:{atlasDimensions:[160,50],alphaBounds:[4,4,150,40],inkDimensions:[150,40]},pass:create('metric')()})}};}

test('source-bound global fixture uses the preserved plans and remains CPU evidence',()=>{
 const binding=compiled();assert.equal(binding.request.flows[0].plan.version,'FLOW_PLAN_V2');
 assert.equal(binding.request.events[0].plan.version,'EVENT_TIMELINE_V1');assert.equal(binding.request.areas[0].plan.version,'AREA_PLAN_V3');
 assert.equal(binding.historicalUnitsInferred,false);assert.equal(binding.gpuOutputVerified,false);
});
test('JSON property ordering from persistence is accepted without accepting extra fields',()=>{
 const sorted=JSON.parse(canonicalSourceJSON(fixture.request));assert.deepEqual(normalizeEventFlowRequest(sorted),normalizeEventFlowRequest(fixture.request));
});
test('ignored unknown legacy nested fields cannot silently enter the plan',()=>{
 const request=clone(fixture.request);request.events[0].plan.intent.line.fakeCameraRoll=30;
 assert.throws(()=>normalizeEventFlowRequest(request),/COMPLETION_EVENT_FLOW_NON_CANONICAL_PLAN/);
});
test('unknown request fields and duplicate IDs reject',()=>{
 assert.throws(()=>normalizeEventFlowRequest({...fixture.request,qualityApproved:true}),/FIELDS_UNSUPPORTED/);
 const request=clone(fixture.request);request.flows[0].id=request.events[0].id;
 assert.throws(()=>normalizeEventFlowRequest(request),/DUPLICATE_ID/);
});
test('declared VERIFIED text without a trusted catalog never admits production',()=>{
 assert.throws(()=>compileCompletionEventFlow(fixture.request,{fps:30,totalFrames:180,allowSynthetic:true,trustedSources:[]}),/VERIFIED_SOURCE_PAYLOAD_BINDING_REQUIRED/);
});
test('synthetic fixture cannot enter a production context',()=>{
 assert.throws(()=>compileCompletionEventFlow(fixture.request,{fps:30,totalFrames:180,trustedSources:fixture.trustedSources}),/SYNTHETIC_EVENT_FLOW_NOT_PRODUCTION/);
});
test('source hash, role, payload and verification class all bind',()=>{
 for(const mutate of [row=>row.sha256='0'.repeat(64),row=>row.role='METRIC',row=>row.payload={untrusted:true},row=>row.verificationStatus='VERIFIED']){
  const sources=clone(fixture.trustedSources);mutate(sources[0]);assert.throws(()=>compiled(fixture.request,sources),/VERIFIED_SOURCE_PAYLOAD_BINDING_REQUIRED/);
 }
});
test('Flow object role and full timing cannot be changed under a geometry-only source claim',()=>{
 const request=clone(fixture.request),intent=clone(request.flows[0].plan.intent);intent.object_role='UNVERIFIED_ALTERNATE_FORCE';
 request.flows[0].plan=compileFlowPlan(compileFlowIntent(intent),request.flows[0].plan.timing);
 assert.throws(()=>compiled(request),/VERIFIED_SOURCE_PAYLOAD_BINDING_REQUIRED/);
});
test('canonical source hashes agree with Python canonical UTF-8 JSON',async()=>{
 const payload={z:'남반구',a:{b:2,a:[1,2]}};const js=await canonicalSourceSHA(payload),
  py=spawnSync('python',['-c','import hashlib,json; print(hashlib.sha256(json.dumps({"z":"남반구","a":{"b":2,"a":[1,2]}},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest())'],{encoding:'utf8'});
 assert.equal(py.status,0);assert.equal(js,py.stdout.trim());
});
test('event reveal and metric use original timing after actual camera lock',()=>{
 const binding=compiled(),at=evaluateCompletionEventFlowFrame(binding,30,context());
 assert.equal(at.events[0].controls.state,'METRIC_REVEAL');assert.equal(at.events[0].controls.metricValue,'12.5');
 assert.equal(at.events[0].controls.metricUnit,'km');assert.equal(at.gpuOutputVerified,false);
 const moving=context();moving.cameraState.cameraLocked=false;
 assert.throws(()=>evaluateCompletionEventFlowFrame(binding,30,moving),/GEOGRAPHIC_ARRIVAL_REQUIRED/);
});
test('hidden route preserves original arc-length position, heading, pulse and hold',()=>{
 const binding=compiled(),ctx=context();
 for(let frame=10;frame<102;frame++){
  const selected=evaluateCompletionEventFlowFrame(binding,frame,ctx),flow=selected.flows[0],original=evaluateFlowFrame(
   binding.request.flows[0].plan,frame,{primitive:flow.primitive,eventContext:{...ctx,cameraState:ctx.cameraState,protectedBoxes:ctx.protectedGraphics.map(row=>row.box)}});
  assert.deepEqual(flow.controls,original);assert.equal(flow.drawControls.routeFraction,0);assert.equal(flow.drawControls.directionalActive,false);
  assert.deepEqual(flow.drawControls.objectPosition,original.objectPosition);assert.equal(flow.drawControls.heading,original.heading);
  assert.ok(evaluateGeographicLineReveal(flow.primitive,flow.drawControls.routeFraction).path.length<2);
 }
 const arrival=evaluateCompletionEventFlowFrame(binding,72,ctx).flows[0];assert.equal(arrival.controls.arrivalPulse.active,true);
 assert.equal(evaluateCompletionEventFlowFrame(binding,90,ctx).flows[0].controls.hold,true);
});
test('arrival cue references only the explicitly supplied area and exact frame',()=>{
 const binding=compiled(),ctx=context();assert.equal(evaluateCompletionEventFlowFrame(binding,69,ctx).arrivalCues.length,0);
 const at=evaluateCompletionEventFlowFrame(binding,70,ctx);assert.deepEqual(at.arrivalCues,[{flowId:'transport',areaId:'arrival-area',frame:70,geometryFromSuppliedAreaOnly:true}]);
 assert.equal(at.areas.length,1);assert.equal(evaluateCompletionEventFlowFrame(binding,71,ctx).arrivalCues.length,0);
});
test('arrival does not invent or retime area geometry',()=>{
 const request=clone(fixture.request);request.flows[0].arrivalAreaId='unknown';
 assert.throws(()=>normalizeEventFlowRequest(request),/ARRIVAL_AREA_CLOCK_BINDING_REQUIRED/);
 request.flows[0].arrivalAreaId='arrival-area';request.flows[0].plan.arrivalFrame++;
 assert.throws(()=>normalizeEventFlowRequest(request),/NON_CANONICAL_PLAN/);
});
test('all supplied Area operations invoke original evaluator with no geometry mutation',()=>{
 const binding=compiled(),before=canonicalSourceJSON(binding.request),types=new Set();
 for(let frame=70;frame<145;frame++)for(const row of evaluateCompletionEventFlowFrame(binding,frame,context()).areas)
  row.controls.activeFeatures.forEach(value=>types.add(value));
 for(const name of ['AREA_REVEAL','AREA_GROW','AREA_MOVE','AREA_CONTRACT','FRONT_LINE','STATE_TRANSITION','TIME_STEP','AREA_HOLD'])assert.ok(types.has(name),name);
 assert.equal(canonicalSourceJSON(binding.request),before);
});
test('Area requires parent detail lock even without an active Event or Flow',()=>{
 const ctx=context();ctx.cameraState.cameraLocked=false;
 assert.throws(()=>evaluateCompletionEventFlowFrame(compiled(),120,ctx),/AREA_REQUIRES_PARENT_DETAIL_LOCK/);
});
test('southern and western fixture requires no country, camera or history branch',()=>{
 assert.ok(fixture.request.flows[0].plan.intent.route_geometry.coordinates.every(point=>point[0]<0&&point[1]<0));
 const selected=evaluateCompletionEventFlowFrame(compiled(),40,context());assert.equal(selected.flows[0].controls.objectRole,'GENERIC_TRANSPORT');
 assert.ok(selected.flows[0].controls.objectPosition.every(Number.isFinite));
});
test('out of range geometry and wrapped line are rejected by preserved contracts',()=>{
 for(const coordinates of [[[0,95],[1,80]],[[179,0],[-179,1]]])assert.throws(()=>compileEventIntent({data_mode:'SYNTHETIC_TEST',line:{geometry:{type:'LineString',coordinates},source:fixture.request.events[0].plan.intent.line.source,direction:'FORWARD',style_role:'PRIMARY'}}));
});
test('strict projected safe area prevents evaluating a cropped event',()=>{
 const ctx=context();ctx.safeArea=[48,72,250,1848];assert.throws(()=>evaluateCompletionEventFlowFrame(compiled(),30,ctx),/GEOMETRY_OUTSIDE_SAFE_AREA/);
});
test('typed marker protection is preserved and text remains strict',()=>{
 const ctx=context(),value=classifyEventLineProtection({protectedGraphics:ctx.protectedGraphics});
 assert.deepEqual(value.markerOcclusions,[ctx.protectedGraphics[0].box]);assert.deepEqual(value.strictBoxes,[ctx.protectedGraphics[1].box]);
 const diagnostic={camera:{protectedGraphics:ctx.protectedGraphics},area:{date:{event:{reservation:{kind:'TEXT',box:[100,200,250,250]}}}}},before=clone(diagnostic);
 assert.equal(completionProtectedGraphics(diagnostic).length,3);assert.deepEqual(diagnostic,before);
});
test('real original pass interfaces receive line, metric, Flow object and Area controls in CPU instrumentation',async()=>{
 const instrumentation=instrument(),binding=compiled(),pass=await createCompletionEventFlowPass({binding,theme,consumers:instrumentation.consumers,testOnlyCPU:true});
 const a=pass.drawFrame(30,context()),b=pass.drawFrame(72,context());
 assert.ok(instrumentation.calls.some(row=>row.kind==='line'));assert.ok(instrumentation.calls.some(row=>row.kind==='metric'));
 assert.ok(instrumentation.calls.some(row=>row.kind==='flow'));assert.ok(instrumentation.calls.some(row=>row.kind==='area'));
 for(const row of instrumentation.calls.filter(row=>row.kind==='flow')){assert.equal(row.value.controls.routeFraction,0);assert.equal(row.value.controls.directionalActive,false);}
 assert.equal(a.gpuOutputVerified,false);assert.equal(b.cpuInstrumentation,true);assert.equal(a.realFactorySelected,false);
 pass.dispose();assert.ok(instrumentation.owned.length>=4);
});
test('CPU spies cannot be passed as production GPU factories',async()=>{
 await assert.rejects(()=>createCompletionEventFlowPass({binding:compiled(),theme,consumers:instrument().consumers}),/TEST_CONSUMERS_FORBIDDEN/);
});
test('concurrent Area, Event, Flow and glyph are ordered and reserve text before geography',async()=>{
 const request=clone(fixture.request);request.events[0].startFrame=60;
 const binding=compiled(request),instrumentation=instrument(),ctx=context(),before=clone(ctx.protectedGraphics),
  pass=await createCompletionEventFlowPass({binding,theme,consumers:instrumentation.consumers,testOnlyCPU:true});
 pass.drawFrame(90,ctx);assert.deepEqual(instrumentation.calls.map(row=>row.kind),['area','line','flow','metric']);
 for(const row of instrumentation.calls.filter(row=>row.kind!=='metric'))assert.equal(row.value.protectedGraphics.length,3);
 assert.deepEqual(ctx.protectedGraphics,before);pass.dispose();
});
test('additional Area draw rejects missing or unverified native boundary masks',async()=>{
 const instrumentation=instrument(),pass=await createCompletionEventFlowPass({binding:compiled(),theme,consumers:instrumentation.consumers,testOnlyCPU:true});
 for(const changes of [{nativeBoundarySourceVerified:false},{boundarySegments:null}])
  assert.throws(()=>pass.drawFrame(90,{...context(),...changes}),/AREA_NATIVE_BOUNDARY_SUPPORT_REQUIRED/);
 assert.equal(instrumentation.calls.length,0);pass.dispose();
});
test('empty current historical selection allocates no GPU owner and infers no events',async()=>{
 const binding=compileCompletionEventFlow({schema:'WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1',events:[],flows:[],areas:[]},{fps:30,totalFrames:2400});
 const pass=await createCompletionEventFlowPass({binding}),selected=pass.drawFrame(100,context());
 assert.equal(selected.emptySelection,true);assert.equal(selected.events.length,0);assert.equal(selected.flows.length,0);assert.equal(selected.areas.length,0);
 assert.equal(pass.evidence.originalFactories,false);pass.dispose();
});
test('timeline overflow and malformed frame never fall back to old rendering',()=>{
 assert.throws(()=>compileCompletionEventFlow(fixture.request,{fps:30,totalFrames:100,trustedSources:fixture.trustedSources,allowSynthetic:true}),/TIMELINE_OUT_OF_RANGE/);
 assert.throws(()=>evaluateCompletionEventFlowFrame(compiled(),180,context()),/FRAME_OUT_OF_RANGE/);
 assert.throws(()=>evaluateCompletionEventFlowFrame(compiled(),1,{...context(),project:null}),/NATIVE_PROJECTION_REQUIRED/);
});
test('production routes require the hidden route presentation',()=>{
 const request={schema:'WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1',events:[],flows:[],areas:[]},raw=clone(fixture.request.flows[0].plan.intent);
 delete raw.version;delete raw.provenance_class;raw.data_mode='PRODUCTION';raw.route_source={source_type:'CPU_TEST_CATALOG_NOT_HISTORY',source_reference:'test-only',verification_status:'VERIFIED'};
 const intent=compileFlowIntent(raw),plan=compileFlowPlan(intent,fixture.request.flows[0].plan.timing),row={id:'p',plan,sourceBindings:fixture.request.flows[0].sourceBindings,routeVisibility:'VISIBLE'};
 request.flows.push(row);assert.throws(()=>compileCompletionEventFlow(request,{fps:30,totalFrames:180,trustedSources:[]}),/PRODUCTION_ROUTE_MUST_BE_HIDDEN/);
});
test('Python bridge performs actual local canonical compiler validation',()=>{
 const py=`import json,sys;sys.path.insert(0,${JSON.stringify(fileURLToPath(new URL('..',import.meta.url)))});from event_flow_contract import normalize_event_flow;print(json.dumps(normalize_event_flow(json.load(open(${JSON.stringify(fileURLToPath(new URL('../fixtures/SYNTHETIC_GLOBAL_EVENT.json',import.meta.url)))}))["request"])))`,
  result=spawnSync('python',['-B','-c',py],{encoding:'utf8',timeout:30000});
 assert.equal(result.status,0,result.stderr);assert.deepEqual(JSON.parse(result.stdout),normalizeEventFlowRequest(fixture.request));
});
test('Python admission uses actual preserved geometry catalog and rejects swapped or absent authority',async()=>{
 const catalog=JSON.parse(await readFile(new URL('../SOURCE_DATA_CATALOG.json',import.meta.url),'utf8')),
  source=catalog.trustedSources.find(row=>row.payload.type==='LineString'),
  intent=compileEventIntent({data_mode:'PRODUCTION',line:{geometry:source.payload,source:{source_type:'MANIFEST_BOUND_APPROXIMATE_SOURCE',
   source_reference:source.sourceId,verification_status:'VERIFIED'},direction:'FORWARD',style_role:'PRIMARY'}}),
  plan=compileEventPlan(intent,{fps:30,profile:{ready_frames:2,line_reveal_frames:20,line_hold_frames:5,metric_reveal_frames:2,information_hold_frames:20}}),
  request={schema:'WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1',events:[{id:'preserved-geometry-cpu-test',startFrame:0,plan,
   sourceBindings:[{role:'GEOMETRY',sourceId:source.sourceId,sha256:source.sha256}]}],flows:[],areas:[]},
  py=`import json,sys;from pathlib import Path;sys.path.insert(0,${JSON.stringify(fileURLToPath(new URL('..',import.meta.url)))});from event_flow_contract import validate_event_flow,EventFlowContractError;r=json.loads(sys.argv[1]);c=json.load(open(${JSON.stringify(fileURLToPath(new URL('../SOURCE_DATA_CATALOG.json',import.meta.url)))}))["trustedSources"];proof=validate_event_flow(r,fps=30,total_frames=2400,trusted_sources=c);assert proof["counts"]["events"]==1 and proof["gpuOutputVerified"] is False;rejected=0\nfor sources in ([],[{**x,"payload":{"swapped":True}} for x in c]):\n try:validate_event_flow(r,fps=30,total_frames=2400,trusted_sources=sources)\n except EventFlowContractError as error:\n  assert error.code=="COMPLETION_VERIFIED_SOURCE_PAYLOAD_BINDING_REQUIRED";rejected+=1\nassert rejected==2;print(json.dumps({"goodSourceReceipt":proof,"rejectedUnauthorizedCatalogs":rejected}))`,
  result=spawnSync('python',['-B','-c',py,JSON.stringify(request)],{encoding:'utf8',timeout:30000});
 assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).rejectedUnauthorizedCatalogs,2);
});
