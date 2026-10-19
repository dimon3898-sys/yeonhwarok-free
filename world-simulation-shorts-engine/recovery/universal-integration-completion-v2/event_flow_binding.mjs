/** Supplied-data binding over preserved Event V1, Flow V2 and Area V3 owners.
 * No map renderer, geometry engine, camera director or physics is duplicated.
 * Node execution is pure CPU compilation/instrumentation; browser pass creation
 * is a deferred real consumer, never evidence that pixels have been rendered.
 */
const moduleURL = name => typeof window === 'undefined'
 ? new URL(`../../web/map_infographic_v1/${name}`, import.meta.url).href : `/modules/${name}`;
const [eventCore, eventLine, flowCore, areaCore, occlusion, layoutCore, styleCore, eventContract] = await Promise.all([
 import(moduleURL('event_timeline_v1.mjs')), import(moduleURL('event_line_v1.mjs')),
 import(moduleURL('flow_core_v2.mjs')), import(moduleURL('area_core_v3.mjs')),
 import(moduleURL('event_occlusion_policy_v1.mjs')), import(moduleURL('event_layout_adapter_v1.mjs')),
 import(moduleURL('event_style_v1.mjs')),import(moduleURL('event_contract_v1.mjs'))]);
export const EVENT_FLOW_REQUEST_SCHEMA = 'WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1';
export const EVENT_FLOW_BINDING_VERSION = 'WORLD_ENGINE_COMPLETION_EVENT_FLOW_BINDING_V1';
const copy = value => structuredClone(value);
export function canonicalSourceJSON(value){
 if(value===null||typeof value!=='object')return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(canonicalSourceJSON).join(',')+']';
 return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonicalSourceJSON(value[key])).join(',')+'}';
}
export async function canonicalSourceSHA(value){
 const bytes=new TextEncoder().encode(canonicalSourceJSON(value));
 const cryptoOwner=globalThis.crypto??(await import('node:crypto')).webcrypto;
 return [...new Uint8Array(await cryptoOwner.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
}
const same = (a,b) => canonicalSourceJSON(a) === canonicalSourceJSON(b);
const plain = value => value && typeof value === 'object' && !Array.isArray(value)
 && [Object.prototype,null].includes(Object.getPrototypeOf(value));
const id = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value);
const sha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function fail(code){throw Object.assign(Error(code),{code});}
function exact(value, keys, optional=[]){
 if(!plain(value)||Object.keys(value).some(key=>!keys.includes(key)&&!optional.includes(key))
  ||keys.some(key=>!Object.hasOwn(value,key)))fail('COMPLETION_EVENT_FLOW_FIELDS_UNSUPPORTED');
}
function integer(value,min=0){if(!Number.isSafeInteger(value)||value<min)fail('COMPLETION_EVENT_FLOW_INTEGER_REQUIRED');return value;}
function bindings(input, roles){
 if(!Array.isArray(input)||input.length!==roles.length)fail('COMPLETION_EVENT_FLOW_SOURCE_BINDINGS_REQUIRED');
 const values=input.map(value=>{exact(value,['role','sourceId','sha256']);
  if(!roles.includes(value.role)||!id(value.sourceId)||!sha(value.sha256))fail('COMPLETION_EVENT_FLOW_SOURCE_BINDING_INVALID');return copy(value);});
 if(new Set(values.map(value=>value.role)).size!==roles.length)fail('COMPLETION_EVENT_FLOW_SOURCE_BINDING_INVALID');
 return values.sort((a,b)=>a.role.localeCompare(b.role));
}
function canonicalPlan(input,kind){
 if(!plain(input))fail('COMPLETION_EVENT_FLOW_CANONICAL_PLAN_REQUIRED');
 let result;
 if(kind==='event')result=eventCore.compileEventPlan(eventContract.compileEventIntent(input.intent),
  {fps:input.fps,profile:input.profile,seed:input.seed});
 else if(kind==='flow')result=flowCore.compileFlowPlan(flowCore.compileFlowIntent(input.intent),input.timing);
 else result=areaCore.compileAreaPlan(areaCore.compileAreaIntent(input.intent),
  {fps:input.fps,start_frame:input.startFrame,total_frames:input.totalFrames,operations:input.operations});
 // Semantic equality prevents hidden ignored fields while accepting key-order
 // changes caused by an ordinary canonical JSON persistence layer.
 if(!same(result,input))fail('COMPLETION_EVENT_FLOW_NON_CANONICAL_PLAN');return result;
}
/** Canonical legacy plans reject extra nested fields by recompilation/equality. */
export function normalizeEventFlowRequest(input){
 exact(input,['schema','events','flows','areas']);
 if(input.schema!==EVENT_FLOW_REQUEST_SCHEMA)fail('COMPLETION_EVENT_FLOW_SCHEMA_REQUIRED');
 for(const key of ['events','flows','areas'])if(!Array.isArray(input[key])||input[key].length>32)
  fail('COMPLETION_EVENT_FLOW_BOUNDED_ARRAY_REQUIRED');
 const events=input.events.map(row=>{exact(row,['id','startFrame','plan','sourceBindings']);
  if(!id(row.id))fail('COMPLETION_EVENT_FLOW_ID_INVALID');integer(row.startFrame);
  const plan=canonicalPlan(row.plan,'event'),roles=[];
  if(plan.intent.line)roles.push('GEOMETRY');if(plan.intent.metric)roles.push('METRIC');
  return{id:row.id,startFrame:row.startFrame,plan,sourceBindings:bindings(row.sourceBindings,roles)};});
 const flows=input.flows.map(row=>{exact(row,['id','plan','sourceBindings','routeVisibility'],['arrivalAreaId']);
  if(!id(row.id)||!['HIDDEN','VISIBLE'].includes(row.routeVisibility)
   ||(row.arrivalAreaId!==undefined&&!id(row.arrivalAreaId)))fail('COMPLETION_EVENT_FLOW_ID_OR_VISIBILITY_INVALID');
  return{id:row.id,plan:canonicalPlan(row.plan,'flow'),sourceBindings:bindings(row.sourceBindings,['GEOMETRY','OBJECT_GRAPHIC','FLOW_PLAN']),
   routeVisibility:row.routeVisibility,...(row.arrivalAreaId===undefined?{}:{arrivalAreaId:row.arrivalAreaId})};});
 const areas=input.areas.map(row=>{exact(row,['id','plan','sourceBindings']);if(!id(row.id))fail('COMPLETION_EVENT_FLOW_ID_INVALID');
  return{id:row.id,plan:canonicalPlan(row.plan,'area'),sourceBindings:bindings(row.sourceBindings,['AREA_INTENT'])};});
 const all=[...events,...flows,...areas];
 if(new Set(all.map(row=>row.id)).size!==all.length)fail('COMPLETION_EVENT_FLOW_DUPLICATE_ID');
 for(const flow of flows)if(flow.arrivalAreaId!==undefined){const area=areas.find(row=>row.id===flow.arrivalAreaId);
  if(!area||area.plan.startFrame!==flow.plan.arrivalFrame)fail('COMPLETION_ARRIVAL_AREA_CLOCK_BINDING_REQUIRED');}
 return{schema:EVENT_FLOW_REQUEST_SCHEMA,events,flows,areas};
}
function expectedPayload(row,role,kind){
 if(kind==='event')return role==='GEOMETRY'?row.plan.intent.line.geometry:row.plan.intent.metric;
 if(kind==='flow')return role==='GEOMETRY'?row.plan.intent.route_geometry:role==='OBJECT_GRAPHIC'?row.plan.intent.object_graphic:row.plan;
 return row.plan.intent;
}
/** Trusted catalog is loaded and SHA-verified by the server, never by a prompt. */
export function compileCompletionEventFlow(input,{fps,totalFrames,trustedSources=[],allowSynthetic=false}={}){
 const request=normalizeEventFlowRequest(input);integer(fps,1);integer(totalFrames,1);
 if(fps!==30||typeof allowSynthetic!=='boolean'||!Array.isArray(trustedSources))fail('COMPLETION_EVENT_FLOW_CONTEXT_REQUIRED');
 const catalog=new Map();
 for(const record of trustedSources){exact(record,['sourceId','sha256','role','verificationStatus','payload']);
  if(!id(record.sourceId)||!sha(record.sha256)||catalog.has(record.sourceId)
   ||!['VERIFIED','SYNTHETIC_TEST'].includes(record.verificationStatus))fail('COMPLETION_TRUSTED_SOURCE_CATALOG_INVALID');
  catalog.set(record.sourceId,record);}
 for(const [kind,rows]of [['event',request.events],['flow',request.flows],['area',request.areas]])for(const row of rows){
  const plan=row.plan,start=kind==='event'?row.startFrame:plan.startFrame;
  if(plan.fps!==fps||start+plan.totalFrames>totalFrames)fail('COMPLETION_EVENT_FLOW_TIMELINE_OUT_OF_RANGE');
  const synthetic=plan.intent.data_mode==='SYNTHETIC_TEST';
  if(synthetic&&!allowSynthetic)fail('COMPLETION_SYNTHETIC_EVENT_FLOW_NOT_PRODUCTION');
  if(kind==='flow'&&!synthetic&&row.routeVisibility!=='HIDDEN')fail('COMPLETION_PRODUCTION_ROUTE_MUST_BE_HIDDEN');
  // Ocean/land exclusion contracts require a separately supplied actual coast
  // mask; this thin binding does not pretend all media are interchangeable.
  if(kind==='area'&&!synthetic&&(plan.intent.propagations.length||plan.intent.impacts.length))
   fail('COMPLETION_PROPAGATION_MEDIUM_MASK_BINDING_REQUIRED');
  for(const binding of row.sourceBindings){const record=catalog.get(binding.sourceId);
   if(!record||record.sha256!==binding.sha256||record.role!==binding.role
    ||record.verificationStatus!==(synthetic?'SYNTHETIC_TEST':'VERIFIED')
    ||!same(record.payload,expectedPayload(row,binding.role,kind)))fail('COMPLETION_VERIFIED_SOURCE_PAYLOAD_BINDING_REQUIRED');}
 }
 return eventContract.freezeEventData({version:EVENT_FLOW_BINDING_VERSION,fps,totalFrames,request,
  sourceAuthority:'SERVER_VERIFIED_IMMUTABLE_CATALOG',cameraOwnership:'READ_ONLY_PARENT',
  historicalUnitsInferred:false,geometryInferred:false,cpuCompilationOnly:true,gpuOutputVerified:false});
}
function protect(input){
 const graphics=input??[];occlusion.classifyEventLineProtection({protectedGraphics:graphics});return copy(graphics);
}
function eventContext(context){
 return{cameraState:context.cameraState,project:context.project,safeArea:context.safeArea,
  scalePlan:context.scalePlan,heightSource:context.heightSource??null,
  protectedBoxes:protect(context.protectedGraphics).map(row=>row.box)};
}
/** Exact frame consumers are the existing evaluator functions, not a new clock. */
export function evaluateCompletionEventFlowFrame(binding,frame,context={}){
 if(binding?.version!==EVENT_FLOW_BINDING_VERSION)fail('COMPLETION_EVENT_FLOW_COMPILED_BINDING_REQUIRED');
 integer(frame);if(frame>=binding.totalFrames)fail('COMPLETION_EVENT_FLOW_FRAME_OUT_OF_RANGE');
 const reservations=protect(context.protectedGraphics);
 if(typeof context.project!=='function')fail('COMPLETION_EVENT_FLOW_NATIVE_PROJECTION_REQUIRED');
 const result={frame,events:[],flows:[],areas:[],arrivalCues:[],protectedGraphics:reservations,
  cpuEvaluationOnly:true,gpuOutputVerified:false};
 for(const row of binding.request.events)if(frame>=row.startFrame&&frame<row.startFrame+row.plan.totalFrames){
  const controls=eventCore.evaluateEventFrame(row.plan,frame-row.startFrame,eventContext(context));
  result.events.push({id:row.id,controls,intent:row.plan.intent,
   primitive:row.plan.intent.line?eventLine.compileGeographicLinePrimitive(row.plan.intent,{project:context.project}):null});
 }
 for(const row of binding.request.flows)if(frame>=row.plan.startFrame&&frame<row.plan.endFrame){
  const primitive=flowCore.compileFlowRoute(row.plan.intent,{project:context.project}),
   controls=flowCore.evaluateFlowFrame(row.plan,frame,{primitive,eventContext:eventContext(context)});
  // Original createEventLinePass(visibleFraction=0) returns drawn:false. Only
  // presentation controls are suppressed; positions/headings/arc-length stay
  // byte-semantically those returned by the original Flow evaluator.
  const drawControls=row.routeVisibility==='HIDDEN'?{...copy(controls),routeFraction:0,routeActive:false,directionalActive:false}:controls;
  result.flows.push({id:row.id,primitive,controls,drawControls,intent:row.plan.intent,routeVisibility:row.routeVisibility});
  if(row.arrivalAreaId!==undefined&&frame===row.plan.arrivalFrame)
   result.arrivalCues.push({flowId:row.id,areaId:row.arrivalAreaId,frame,geometryFromSuppliedAreaOnly:true});
 }
 for(const row of binding.request.areas)if(frame>=row.plan.startFrame&&frame<row.plan.endFrame){
  const controls=areaCore.evaluateAreaFrame(row.plan,frame,{project:context.project});
  if(context.cameraState?.cameraLocked!==true||context.cameraState?.settle?.locked!==true)
   fail('COMPLETION_AREA_REQUIRES_PARENT_DETAIL_LOCK');
  result.areas.push({id:row.id,controls});
 }
 return result;
}
/** Preserve native/date/metric reservations before applying an added pass. */
export function completionProtectedGraphics(diagnostic){
 const result=[...(diagnostic?.camera?.protectedGraphics??[])];
 for(const item of [diagnostic?.area?.date?.event,diagnostic?.area?.date?.geometry])
  if(item?.reservation)result.push(item.reservation);
 return protect(result);
}
/** Browser factory: original GPU pass factories, sharing the existing canvas.
 * ``consumers`` is ONLY for explicit CPU instrumentation tests. Production never
 * passes that option. It does not make injected spies into GPU output evidence.
 */
export async function createCompletionEventFlowPass({canvas,binding,theme,consumers=null,testOnlyCPU=false}={}){
 if(binding?.version!==EVENT_FLOW_BINDING_VERSION)fail('COMPLETION_EVENT_FLOW_COMPILED_BINDING_REQUIRED');
 if(consumers!==null&&testOnlyCPU!==true)fail('COMPLETION_EVENT_FLOW_TEST_CONSUMERS_FORBIDDEN');
 if(!binding.request.events.length&&!binding.request.flows.length&&!binding.request.areas.length){
  let disposed=false;
  return{evidence:{version:EVENT_FLOW_BINDING_VERSION,emptySelection:true,originalFactories:false,
    cpuInstrumentation:testOnlyCPU,actualGPUOutputVerified:false},
   drawFrame(frame,context){if(disposed)fail('COMPLETION_EVENT_FLOW_PASS_DISPOSED');
    return{...evaluateCompletionEventFlowFrame(binding,frame,context),consumerResults:{events:[],flows:[],areas:[]},
     emptySelection:true,realFactorySelected:false,gpuOutputVerified:false};},dispose(){disposed=true;}};
 }
 let owner=null,gl=null,stateOwner=null;
 const entries=new Map(),passes=[];
 if(consumers===null){
  if(typeof window==='undefined'||!canvas||canvas.width!==1080||canvas.height!==1920)
   fail('COMPLETION_EVENT_FLOW_BROWSER_NATIVE_CANVAS_REQUIRED');
  const [THREE,lineGPU,metricGPU,metricCore,flowGPU,areaGPU]=await Promise.all([
   import('/three.js'),import(moduleURL('event_line_pass_v1.mjs')),import(moduleURL('event_metric_pass_v1.mjs')),
   import(moduleURL('event_metric_v1.mjs')),import(moduleURL('flow_graphic_pass_v2.mjs')),import(moduleURL('area_overlay_pass_v3.mjs'))]);
  gl=canvas.getContext('webgl2');if(!gl)fail('COMPLETION_EVENT_FLOW_NATIVE_WEBGL2_REQUIRED');
  stateOwner=flowGPU;const saved=stateOwner.captureFlowNativeGlState(gl);
  try{owner=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});owner.autoClear=false;
   owner.outputColorSpace=THREE.LinearSRGBColorSpace;owner.toneMapping=THREE.NoToneMapping;
   consumers={line:options=>lineGPU.createEventLinePass({renderer:owner,...options}),
    metric:options=>{if(!document.fonts?.check('40px Gate1Bold'))fail('COMPLETION_EXISTING_GLYPH_FONT_NOT_READY');
     const primitive=metricCore.compileMetricAnnotation(options.intent,{style:{fontSize:40,minFontSize:40,
      fontFamily:'Gate1Bold',lineHeight:1.28,outlineRadius:1.4,maxWidth:960,maxLines:1}});
     return{primitive,pass:metricGPU.createEventMetricPass({renderer:owner,primitive,color:[1,1,1]})};},
    flow:options=>flowGPU.createFlowGraphicPass({canvas,...options}),area:()=>areaGPU.createAreaOverlayPass({canvas})};
  }finally{stateOwner.restoreFlowNativeGlState(gl,saved);}
 }
 for(const key of ['line','metric','flow','area'])if(typeof consumers?.[key]!=='function')fail('COMPLETION_EVENT_FLOW_REAL_CONSUMER_REQUIRED');
 try{
  for(const row of binding.request.events){const style=row.plan.intent.line?styleCore.selectEventLineStyle({
    role:row.plan.intent.line.style_role,theme,primaryMaterialColor:theme.primary}):null;
   const entry={line:style?consumers.line({style}):null,metric:row.plan.intent.metric?consumers.metric({intent:row.plan.intent}):null};
   entries.set(row.id,entry);if(entry.line)passes.push(entry.line);if(entry.metric)passes.push(entry.metric.pass);}
  for(const row of binding.request.flows){const style=styleCore.selectEventLineStyle({role:'PRIMARY',theme,primaryMaterialColor:theme.primary});
   const pass=consumers.flow({style});entries.set(row.id,{flow:pass});passes.push(pass);}
  if(binding.request.areas.length){const pass=consumers.area();entries.set('::AREA_OWNER',{area:pass});passes.push(pass);}
 }catch(error){for(const pass of passes)pass.dispose?.();owner?.dispose();throw error;}
 let disposed=false;
 return{evidence:{version:EVENT_FLOW_BINDING_VERSION,originalFactories:true,finishedFrameBlit:false,
  cpuInstrumentation:testOnlyCPU,actualGPUOutputVerified:false,
  drawHook:'AFTER_PARENT_DRAW_BEFORE_CAPTURE_WITH_FULL_PROTECTED_RESERVATIONS'},
  drawFrame(frame,context){
   if(disposed)fail('COMPLETION_EVENT_FLOW_PASS_DISPOSED');
   const selected=evaluateCompletionEventFlowFrame(binding,frame,context),results={events:[],flows:[],areas:[]},
    saved=gl?stateOwner.captureFlowNativeGlState(gl):null;
   try{
    owner?.resetState();
    if(selected.areas.length&&(context.nativeBoundarySourceVerified!==true||!Array.isArray(context.boundarySegments)))
     fail('COMPLETION_AREA_NATIVE_BOUNDARY_SUPPORT_REQUIRED');
    if(selected.areas.length&&(typeof context.parentGeographicFrontPresent!=='boolean'||context.parentGeographicFrontPresent))
     fail('COMPLETION_AREA_PARENT_FRONT_LAYER_BINDING_REQUIRED');
    const reservations=copy(selected.protectedGraphics),placements=new Map();
    // Reserve complete metric slots before any geographic pass; typography is
    // drawn last. Multiple labels use the original layout rejection policy.
    for(const row of selected.events){const entry=entries.get(row.id);
     if(entry.metric){const measurement=entry.metric.primitive,
       boxes=reservations.map(item=>item.box),common={anchor:context.project(row.intent.metric.anchor),measurement,
        safeArea:context.safeArea,protectedBoxes:boxes,markerSize:40,gap:18},
       placement=row.primitive?layoutCore.chooseRelatedMetricPlacement({...common,linePrimitive:row.primitive,
        markerOcclusions:occlusion.classifyEventLineProtection({protectedGraphics:reservations}).markerOcclusions,
        linePaddingPixels:10}):layoutCore.chooseMetricPlacement(common);
      placements.set(row.id,placement);reservations.push({kind:'TEXT',box:copy(placement.roi)});}
    }
    // Area -> geographic Event -> object/endpoint -> measured glyph. Existing
    // native foreground is masked throughout rather than moved or repainted.
    for(const row of selected.areas)results.areas.push({id:row.id,result:entries.get('::AREA_OWNER').area.draw({controls:row.controls,
     project:context.project,safeArea:context.safeArea,protectedGraphics:reservations,
     primaryMaterialColor:theme.primary,boundarySegments:context.boundarySegments})});
    for(const row of selected.events){const entry=entries.get(row.id),line=entry.line&&row.controls.lineActive?
      entry.line.draw({primitive:row.primitive,visibleFraction:row.controls.lineFraction,safeArea:context.safeArea,protectedGraphics:reservations}):null;
     results.events.push({id:row.id,line,metric:null});}
    for(const row of selected.flows)results.flows.push({id:row.id,result:entries.get(row.id).flow.draw({primitive:row.primitive,
     controls:row.drawControls,safeArea:context.safeArea,protectedGraphics:reservations,flowIntent:row.intent})});
    owner?.resetState();
    for(const row of selected.events)if(entries.get(row.id).metric&&row.controls.metricActive)
     results.events.find(value=>value.id===row.id).metric=entries.get(row.id).metric.pass.draw({
      visibleFraction:row.controls.metricFraction,placement:placements.get(row.id)});
   }finally{if(gl)stateOwner.restoreFlowNativeGlState(gl,saved);}
   return{...selected,consumerResults:results,realFactorySelected:!testOnlyCPU,cpuInstrumentation:testOnlyCPU,gpuOutputVerified:false};
  },dispose(){if(disposed)return;for(const pass of passes)pass.dispose?.();owner?.dispose();disposed=true;}};
}

// Bounded local CPU normalization for the Python prompt parser. No browser,
// network, graphics factory, filesystem writes or GPU command is entered.
if(typeof process!=='undefined'&&['--normalize','--admit'].includes(process.argv?.[2])){
 try{let raw='';for await(const chunk of process.stdin){raw+=chunk;if(Buffer.byteLength(raw)>4*1024*1024)fail('COMPLETION_EVENT_FLOW_INPUT_TOO_LARGE');}
  const input=JSON.parse(raw);let value;
  if(process.argv[2]==='--normalize')value=normalizeEventFlowRequest(input);
  else{exact(input,['request','fps','totalFrames','trustedSources']);
   const binding=compileCompletionEventFlow(input.request,{fps:input.fps,totalFrames:input.totalFrames,trustedSources:input.trustedSources,allowSynthetic:false});
   value={schema:'WORLD_ENGINE_COMPLETION_EVENT_FLOW_CPU_ADMISSION_V1',status:'CPU_SOURCE_BOUND',
    counts:{events:binding.request.events.length,flows:binding.request.flows.length,areas:binding.request.areas.length},
    requestSHA256:await canonicalSourceSHA(binding.request),sourceAuthority:binding.sourceAuthority,
    noHistoricalUnitsInferred:true,cpuCompilationOnly:true,gpuOutputVerified:false,renderStarted:false};}
  process.stdout.write(JSON.stringify({ok:true,value}));}
 catch(error){const code=error.code??error.message;process.stdout.write(JSON.stringify({ok:false,code:/^[A-Z][A-Z0-9_]{1,127}$/.test(code)?code:'COMPLETION_EVENT_FLOW_INVALID'}));process.exitCode=1;}
}
