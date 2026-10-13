/** Focused Flow V2 regression. Background/protected rectangles are deliberately
 * synthetic GPU fixtures; this does not certify production Terrain or Glyphs.
 * The unchanged V1 line evaluator/pass and current Flow GPU pass are exercised
 * on one native 1080x1920 WebGL2 canvas, without copying a finished map frame.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {generateDetailExtentCandidates} from '../../web/map_infographic_v1/detail_data_profile_v1.mjs';
import {createEventDetailFramingRequest} from '../../web/map_infographic_v1/visual_detail_admission_v1.mjs';

const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.dirname(engine);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const fixtures=[];
for(const key of ['a','b','c']){
 const relative='fixtures/synthetic-'+key+'.json',bytes=await readFile(path.join(root,relative));
 fixtures.push({key,fixture:JSON.parse(bytes),source:{path:path.relative(repo,path.join(root,relative)),sha256:sha(bytes),bytes:bytes.length}});
}

// Only pure contract evidence is simulated here. No synthetic certificate can
// authorize real imagery or production: the existing API enforces that fact.
function detailRequest(geometry,anchor,currentBounds,safeArea){
 const output=[1080,1920],given={eventGeometry:geometry,eventAnchor:anchor,currentBounds,output,safeArea};
 const candidates=generateDetailExtentCandidates(given),evidenceByCandidate={};
 for(const candidate of candidates){
  const b=candidate.projectedGeometryBounds,middle=(b[1]+b[3])/2;
  evidenceByCandidate[candidate.id]={evidenceKind:'SYNTHETIC_TEST_ONLY',
   render:{verified:true,sha256:'a'.repeat(64),byteLength:1234,width:1080,height:1920,
    candidateBounds:candidate.bounds,geometryBinding:candidate.geometryBinding},
   semantic:{sameGeography:true,sameObject:true,relationCorrect:true,geometryMeaningPreserved:true,metricMateriallyTrue:true},
   protection:{cameraV5:true,eventV2:true,rendererVisual:true,geometry:true,marker:true},
   visual:{terrain:'VISUAL_PASS',coastline:'VISUAL_PASS',canal:'VISUAL_PASS',marker:'VISUAL_PASS',labels:'VISUAL_PASS',
    safeArea:'VISUAL_PASS',metric:'VISUAL_PASS',lineReadable:true,metricRelated:true},
   layout:{verified:true,candidateBounds:candidate.bounds,geometryBinding:candidate.geometryBinding,
    metricBounds:[b[2]+20,middle-20,b[2]+170,middle+20],protectedGraphics:[]},
   quality:{gisAbsoluteAccuracyCertified:false,coastAlignmentMeasured:false,nativeTexelToScreenPixelRatio:[1,1]}};
 }
 const request=createEventDetailFramingRequest({...given,currentCameraState:{bounds:currentBounds,output},
  evidenceByCandidate,surveyDetailStatus:'LOCAL_NOT_ADMITTED'});
 assert.equal(request.certificate?.productionEligible,false,'Synthetic producer evidence cannot certify production');
 assert.equal(request.surveyAdmissionModified,false);
 return request;
}
const framing={};
for(const {key,fixture} of fixtures.slice(0,2)){
 const request=detailRequest(fixture.intent.route_geometry,fixture.intent.start_anchor,
  fixture.context.cameraState.camera.flatBounds,fixture.context.safeArea);
 assert.equal(request.decision,fixture.expected.detail_decision);
 framing[key]={decision:request.decision,startBounds:fixture.context.cameraState.camera.flatBounds,
  targetBounds:request.targetFraming.bounds,wholeGeometryVisible:request.admission.selectedCandidate.wholeGeometryVisible,
  currentCoverage:request.admission.audits[0].candidate.screenCoverage,
  targetCoverage:request.admission.selectedCandidate.screenCoverage,productionEligible:false};
}
const narrowGeometry={type:'LineString',coordinates:[[0,-1],[.01,0],[0,1]]};
const narrowRequest=detailRequest(narrowGeometry,[.01,0],[-5,-10,5,10],[48,72,1032,1848]);
assert.equal(narrowRequest.decision,'DETAIL_APPROACH_REQUIRED');
assert.equal(narrowRequest.admission.selectedCandidate.wholeGeometryVisible,true);
assert.equal(narrowRequest.admission.selectedCandidate.sourceCoordinateCount,narrowGeometry.coordinates.length);
framing.longNarrow={decision:narrowRequest.decision,targetBounds:narrowRequest.targetFraming.bounds,
 wholeGeometryVisible:true,sourceCoordinateCount:narrowGeometry.coordinates.length,productionEligible:false,
 evidenceScope:'PURE_SYNTHETIC_DETAIL_CONTRACT_NOT_PRODUCTION_ADMISSION'};

const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{cwd:repo,stdio:['ignore','pipe','pipe']});
let browser,serverError='';server.stderr.on('data',data=>{serverError=(serverError+data).slice(-4096);});
try{
 const url=await new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(Error('SYNTHETIC_SERVER_TIMEOUT')),10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timeout);try{resolve(JSON.parse(line).url);}catch(error){reject(error);}});
  server.once('error',reject);server.once('exit',code=>{clearTimeout(timeout);reject(Error('SYNTHETIC_SERVER_EXIT_'+code));});
 });
 browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 assert.equal(browser.version(),'154.0.8037.57');
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
 await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
 await page.goto(url+'/runtime-config.json',{waitUntil:'load'});
 const result=await page.evaluate(async({fixtures,framing})=>{
  const THREE=await import('/three.js');
  const {compileFlowIntent,compileFlowPlan,compileFlowRoute,evaluateFlowFrame,sampleFlowRoute}=await import('/modules/flow_core_v2.mjs');
  const {createFlowGraphicPass,captureFlowNativeGlState}=await import('/modules/flow_graphic_pass_v2.mjs');
  const {selectEventLineStyle}=await import('/modules/event_style_v1.mjs');
  const {evaluateGeographicLineReveal}=await import('/modules/event_line_v1.mjs');
  const fail=message=>{throw Error('SYNTHETIC_ASSERT_'+message);};
  const check=(condition,message)=>{if(!condition)fail(message);};
  const equal=(a,b,message)=>check(JSON.stringify(a)===JSON.stringify(b),message);
  const close=(a,b,message)=>check(Math.abs(a-b)<1e-9,message);
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.appendChild(canvas);
  const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});check(gl,'WEBGL2_REQUIRED');
  const ext=gl.getExtension('WEBGL_debug_renderer_info'),backend=gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER);
  check(backend.includes('SwiftShader'),'PINNED_SWIFTSHADER_REQUIRED');
  // Same THREE flat geographic camera math as the unchanged native renderer.
  // This is an explicit synthetic callback, never a production projector.
  function projection(bounds){
   const [west,south,east,north]=bounds,c=(west+east)/2,lat=(south+north)/2,cos=Math.cos(lat*Math.PI/180);
   const camera=new THREE.OrthographicCamera(-(east-west)*cos/2,(east-west)*cos/2,(north-south)/2,-(north-south)/2,.1,10);
   camera.position.z=5;camera.updateMatrixWorld();
   return point=>{const v=new THREE.Vector3((point[0]-c)*cos,point[1]-lat,0).project(camera);
    return[(v.x*.5+.5)*1080,(.5-v.y*.5)*1920];};
  }
  const nativeVao=gl.createVertexArray(),nativeBuffer=gl.createBuffer(),nativeIndex=gl.createBuffer(),nativeUniform=gl.createBuffer();
  gl.bindVertexArray(nativeVao);gl.bindBuffer(gl.ARRAY_BUFFER,nativeBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([1,2,3,4]),gl.STATIC_DRAW);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,nativeIndex);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array([0,1]),gl.STATIC_DRAW);
  gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);gl.enableVertexAttribArray(0);gl.vertexAttribDivisor(0,2);
  gl.bindBuffer(gl.UNIFORM_BUFFER,nativeUniform);gl.bufferData(gl.UNIFORM_BUFFER,64,gl.STATIC_DRAW);gl.bindBufferBase(gl.UNIFORM_BUFFER,1,nativeUniform);
  const texture=gl.createTexture(),sampler=gl.createSampler();gl.activeTexture(gl.TEXTURE3);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(3,sampler);
  const ids=new WeakMap();let nextId=0;
  function serialize(value){
   if(value===null||typeof value!=='object')return value;
   if(ArrayBuffer.isView(value))return Array.from(value);
   if(Array.isArray(value))return value.map(serialize);
   if(Object.getPrototypeOf(value)!==Object.prototype){if(!ids.has(value))ids.set(value,++nextId);return{nativeObject:ids.get(value),type:value.constructor.name};}
   return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,serialize(item)]));
  }
  const snapshotState=()=>JSON.stringify(serialize(captureFlowNativeGlState(gl)));
  function seedState(){
   gl.bindVertexArray(nativeVao);gl.bindBuffer(gl.ARRAY_BUFFER,nativeBuffer);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,nativeIndex);
   gl.bindBufferBase(gl.UNIFORM_BUFFER,1,nativeUniform);gl.activeTexture(gl.TEXTURE3);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(3,sampler);
   gl.viewport(17,19,1030,1880);gl.scissor(11,12,1055,1890);gl.enable(gl.SCISSOR_TEST);
   gl.enable(gl.DEPTH_TEST);gl.depthMask(true);gl.depthFunc(gl.GEQUAL);gl.depthRange(.2,.9);
   gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.ONE,gl.ZERO,gl.ZERO,gl.ONE);gl.blendEquationSeparate(gl.FUNC_REVERSE_SUBTRACT,gl.FUNC_ADD);
   gl.colorMask(true,false,true,true);gl.clearColor(.13,.17,.19,.91);gl.pixelStorei(gl.PACK_ALIGNMENT,8);gl.pixelStorei(gl.UNPACK_ALIGNMENT,8);
  }
  const colors={MARKER:[.95,.21,.25,1],TEXT:[.93,.93,.97,1],PANEL:[.31,.43,.66,1]};
  function clearNative(graphics){
   gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.disable(gl.SCISSOR_TEST);gl.colorMask(true,true,true,true);
   gl.clearColor(.14,.21,.24,1);gl.clear(gl.COLOR_BUFFER_BIT);
   gl.enable(gl.SCISSOR_TEST);gl.scissor(0,0,540,1920);gl.clearColor(.46,.35,.13,1);gl.clear(gl.COLOR_BUFFER_BIT);
   for(const item of graphics){const b=item.box;gl.scissor(Math.floor(b[0]),1920-Math.ceil(b[3]),Math.ceil(b[2])-Math.floor(b[0]),Math.ceil(b[3])-Math.floor(b[1]));
    gl.clearColor(...colors[item.kind]);gl.clear(gl.COLOR_BUFFER_BIT);}
   gl.disable(gl.SCISSOR_TEST);gl.finish();
  }
  function pixels(){const bytes=new Uint8Array(1080*1920*4);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,bytes);return bytes;}
  const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  const theme={primary:[.7,.52,.11],primaryWidth:5,secondaryWidth:3,glowRadius:2,glowGain:.1};
  const style=selectEventLineStyle({role:'PRIMARY',theme,primaryMaterialColor:theme.primary,
   backgroundSamples:[[.46,.35,.13],[.14,.21,.24]]});
  seedState();const constructorBefore=snapshotState();const pass=createFlowGraphicPass({canvas,style});
  check(snapshotState()===constructorBefore,'CONSTRUCTOR_NATIVE_GL_STATE_CHANGED');
  const cases=[];
  for(const {key,fixture,source} of fixtures){
   const before=JSON.stringify(fixture),intent=compileFlowIntent(fixture.intent),plan=compileFlowPlan(intent,fixture.timeline);
   const bounds=framing[key]?.targetBounds??fixture.context.cameraState.camera.flatBounds,project=projection(bounds);
   const eventContext={...fixture.context,cameraState:{...fixture.context.cameraState,camera:{flatBounds:bounds}},project};
   const primitive=compileFlowRoute(intent,{project});
   equal(intent.route_geometry,fixture.intent.route_geometry,key+'_SOURCE_GEOMETRY_CHANGED');
   const controls=Array.from({length:plan.totalFrames},(_v,frame)=>evaluateFlowFrame(plan,frame,{primitive,eventContext}));
   let departureRuns=0,arrivalRuns=0,lastDeparture=false,lastArrival=false,maxHeadingDelta=0,maxFractionDelta=0;
   for(const [index,c] of controls.entries()){
    equal(c.routeReveal,evaluateGeographicLineReveal(primitive,c.routeFraction),key+'_V1_REVEAL_DIFF');
    const sample=sampleFlowRoute(primitive,c.objectFraction);equal(sample.position,c.objectPosition,key+'_ARCLENGTH_POSITION_DIFF');
    close(sample.distancePixels,c.objectFraction*primitive.totalLengthPixels,key+'_ARCLENGTH_DISTANCE_DIFF');
    check(c.objectFraction<=c.routeFraction+1e-12,key+'_OBJECT_OVERTAKES_REVEAL');
    if(index){check(c.objectFraction>=controls[index-1].objectFraction,key+'_MOTION_REVERSES');
     maxHeadingDelta=Math.max(maxHeadingDelta,Math.abs(c.heading-controls[index-1].heading));
     maxFractionDelta=Math.max(maxFractionDelta,c.objectFraction-controls[index-1].objectFraction);}
    if(c.departurePulse.active&&!lastDeparture)departureRuns++;if(c.arrivalPulse.active&&!lastArrival)arrivalRuns++;
    lastDeparture=c.departurePulse.active;lastArrival=c.arrivalPulse.active;
    if(c.hold){check(c.objectFraction===1&&c.routeFraction===1&&!c.directionalActive,key+'_HOLD_INCOMPLETE');
     check(c.departurePulse.alpha===0&&c.arrivalPulse.alpha===0,key+'_PULSE_REPEATS_DURING_HOLD');}
   }
   check(departureRuns===1&&arrivalRuns===1,key+'_PULSE_NOT_ONE_SHOT');
   check(maxHeadingDelta<.25,key+'_HEADING_JUMP_'+maxHeadingDelta);check(maxFractionDelta<.018,key+'_MOTION_SPEED_JUMP');
   const speedFrames=Array.from({length:17},(_v,index)=>plan.timing.object_start_frame+
    Math.round((plan.timing.travel_frames-1)*index/16));
   const beatFrames=plan.timeline.flatMap(beat=>[beat.startFrame,beat.endFrame-1]);
   const pulseFrames=[plan.timing.object_start_frame+Math.floor(plan.timing.departure_pulse_frames/2),
    plan.arrivalFrame+Math.floor(plan.timing.arrival_pulse_frames/2)];
   const markerRevealFrames=key==='c'?[16,17,18,19,73,74,75]:[];
   const chosen=[...new Set([...speedFrames,...beatFrames,...pulseFrames,...markerRevealFrames])].sort((a,b)=>a-b);
   const graphics=fixture.context.protectedGraphics,frames=[];
   const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
   async function capture(c){
    clearNative(graphics);const base=pixels();seedState();const stateBefore=snapshotState();
    const diagnostic=pass.draw({primitive,controls:c,safeArea:eventContext.safeArea,protectedGraphics:graphics,flowIntent:intent});
    check(snapshotState()===stateBefore,key+'_DRAW_NATIVE_GL_STATE_CHANGED_'+c.frame);gl.finish();const actual=pixels();
    check(gl.getError()===gl.NO_ERROR,key+'_GL_ERROR');
    let changed=0,protectedChanged=0,markerChanged=0,outside=0,unsafe=0;
    const a=new Uint32Array(base.buffer),b=new Uint32Array(actual.buffer);
    for(let index=0;index<a.length;index++)if(a[index]!==b[index]){
     changed++;const x=index%1080,y=1919-Math.floor(index/1080);
     if(!diagnostic.rois.some(box=>inside(x,y,box)))outside++;
     if(!inside(x,y,eventContext.safeArea))unsafe++;
     if(graphics.some(item=>inside(x,y,item.box)))protectedChanged++;
     if(graphics.some(item=>item.kind==='MARKER'&&inside(x,y,item.box)))markerChanged++;
    }
    check(protectedChanged===0,key+'_PROTECTED_NATIVE_PIXEL_CHANGED');check(outside===0,key+'_PIXEL_OUTSIDE_ROI');
    check(unsafe===0,key+'_PIXEL_OUTSIDE_SAFE_AREA');
    return{actual,record:{frame:c.frame,state:c.state,routeFraction:c.routeFraction,objectFraction:c.objectFraction,
     objectPosition:c.objectPosition,heading:c.heading,directionalFraction:c.directionalFraction,
     departurePulse:c.departurePulse,arrivalPulse:c.arrivalPulse,changedPixels:changed,protectedChangedPixels:protectedChanged,
     markerChangedPixels:markerChanged,outsideRoiChangedPixels:outside,unsafeChangedPixels:unsafe,
     rawRgbaSha256:await digest(actual),glError:0,nativeStateRestored:true,diagnostic}};
   }
   for(const frame of chosen){const actual=await capture(controls[frame]);frames.push(actual.record);
    if(controls[frame].routeFraction>0)check(actual.record.changedPixels>0,key+'_NO_VISIBLE_ROUTE_'+frame);}
   const contribution={};
   const componentFrame=plan.timing.object_start_frame+Math.floor(plan.timing.travel_frames/3);
   const full=await capture(controls[componentFrame]);
   for(const [name,omit] of [['object',{objectVisible:false,movingObjectVisible:false}],['direction',{directionalActive:false}]]){
    const without=await capture({...controls[componentFrame],...omit});let changed=0;
    for(let index=0;index<full.actual.length;index+=4)if(full.actual[index]!==without.actual[index]
     ||full.actual[index+1]!==without.actual[index+1]||full.actual[index+2]!==without.actual[index+2])changed++;
    check(changed>0,key+'_INVISIBLE_'+name);contribution[name]={frame:componentFrame,pixelContribution:changed};
   }
   const pulseFrame=plan.arrivalFrame+Math.floor(plan.timing.arrival_pulse_frames/2),pulseFull=await capture(controls[pulseFrame]);
   const noPulse=await capture({...controls[pulseFrame],arrivalPulse:{...controls[pulseFrame].arrivalPulse,active:false}});let pulsePixels=0;
   for(let index=0;index<pulseFull.actual.length;index+=4)if(pulseFull.actual[index]!==noPulse.actual[index]
    ||pulseFull.actual[index+1]!==noPulse.actual[index+1]||pulseFull.actual[index+2]!==noPulse.actual[index+2])pulsePixels++;
   check(pulsePixels>0,key+'_INVISIBLE_ARRIVAL_PULSE');contribution.arrivalPulse={frame:pulseFrame,pixelContribution:pulsePixels};
   const holdFrames=frames.filter(frame=>frame.state==='ROUTE_HOLD');check(new Set(holdFrames.map(f=>f.rawRgbaSha256)).size===1,key+'_HOLD_NOT_STABLE');
   const negatives=[];
   if(key==='c'){
    check(frames.some(f=>f.diagnostic.object?.protectedOverlaps.some(item=>item.kind==='MARKER')),'C_OBJECT_NEVER_PASSES_MARKER');
    const under=controls.filter(c=>c.objectPosition[0]>=518&&c.objectPosition[0]<=562);
    check(under.length>1&&under.at(-1).objectFraction>under[0].objectFraction,'C_OCCLUSION_STOPS_ARCLENGTH');
    for(const negative of [...fixture.negative_cases,{id:'OBJECT_SAFE_AREA_SUBGUARD',
     route_geometry:{type:'LineString',coordinates:[[.6,5],[2,5]]}}]){
     const input={...fixture.intent,route_geometry:negative.route_geometry,start_anchor:negative.route_geometry.coordinates[0],
      end_anchor:negative.route_geometry.coordinates.at(-1)};
     const nIntent=compileFlowIntent(input),nPlan=compileFlowPlan(nIntent,fixture.timeline),nPrimitive=compileFlowRoute(nIntent,{project});
     const nControls=evaluateFlowFrame(nPlan,nPlan.timing.object_start_frame,{primitive:nPrimitive,eventContext});
     clearNative(graphics);seedState();const stateBefore=snapshotState();let message=null;
     try{pass.draw({primitive:nPrimitive,controls:nControls,safeArea:eventContext.safeArea,protectedGraphics:graphics,flowIntent:nIntent});}
     catch(error){message=error.message;}
     check(message!==null,'C_NEGATIVE_NOT_REJECTED_'+negative.id);
     check(snapshotState()===stateBefore,'C_REJECTED_DRAW_CORRUPTS_NATIVE_GL');check(gl.getError()===0,'C_REJECTED_DRAW_GL_ERROR');
     if(negative.id.startsWith('TEXT_'))check(message.includes('PROTECTED_GRAPHIC_COLLISION'),'C_TEXT_GATE_WRONG_REJECTION');
     else check(message.includes('OUTSIDE_SAFE_AREA'),'C_SAFE_AREA_GATE_WRONG_REJECTION');
     negatives.push({id:negative.id,result:'REJECTED',reason:message,nativeStateRestored:true,glError:0});
    }
   }
   check(JSON.stringify(fixture)===before,key+'_FIXTURE_MUTATED');
   cases.push({key:key.toUpperCase(),id:fixture.id,source,result:'PASS',dataMode:intent.data_mode,productionEligible:false,
    bounds,projectedRouteLengthPixels:primitive.totalLengthPixels,coordinateCount:intent.route_geometry.coordinates.length,
    geometryUnchanged:true,coreControlFramesChecked:controls.length,gpuFramesChecked:chosen.length,speedFrames,
    maxConsecutiveHeadingDeltaRadians:maxHeadingDelta,maxConsecutiveArcFractionDelta:maxFractionDelta,
    departurePulseRuns:departureRuns,arrivalPulseRuns:arrivalRuns,stableHold:true,componentContribution:contribution,
    allProtectedChangedPixels:frames.reduce((sum,f)=>sum+f.protectedChangedPixels,0),
    allMarkerChangedPixels:frames.reduce((sum,f)=>sum+f.markerChangedPixels,0),
    allOutsideRoiChangedPixels:frames.reduce((sum,f)=>sum+f.outsideRoiChangedPixels,0),
    allUnsafeChangedPixels:frames.reduce((sum,f)=>sum+f.unsafeChangedPixels,0),negativeCases:negatives,frames});
  }
  seedState();const disposeBefore=snapshotState();pass.dispose();check(snapshotState()===disposeBefore,'DISPOSE_NATIVE_GL_STATE_CHANGED');
  check(gl.getError()===0,'DISPOSE_GL_ERROR');
  return{schema:1,result:'PASS',scope:'FOCUSED_SYNTHETIC_GPU_REGRESSION_NOT_NATIVE_TERRAIN_OR_GLYPH_CERTIFICATION',
   output:[1080,1920],backend,projection:'Synthetic THREE flat geographic callback identical to native flat camera math',
   style,passEvidence:pass.evidence,constructorStateRestored:true,disposeStateRestored:true,cases,
   detailFraming:{...framing,scope:'PURE_SYNTHETIC_DETAIL_CONTRACT_NOT_PRODUCTION_ADMISSION'},
   assertions:['UNCHANGED_V1_ARCLENGTH_ENGINE','CANONICAL_NATIVE_WEBGL2','ROUTE_REVEAL','DIRECTIONAL_CHEVRON_VISIBLE',
    'FIXTURE_OBJECT_VISIBLE','DETERMINISTIC_SMOOTH_TRAVEL','ONE_SHOT_ENDPOINT_PULSES','STABLE_ROUTE_HOLD',
    'PROTECTED_NATIVE_PIXELS_ZERO','MARKER_OCCLUSION_CONTINUOUS_PROGRESS','STRICT_TEXT_COLLISION_REJECTED',
    'FULL_GRAPHIC_SAFE_AREA_REJECTED','ACTUAL_NATIVE_GL_STATE_RESTORED']};
 },{fixtures,framing});
 assert.deepEqual(errors,[],'Browser/runtime errors');
 result.toolchain={node:process.version,playwright:require('playwright/package.json').version,chromium:browser.version()};
 result.createdUtc=new Date().toISOString();
 await mkdir(path.join(root,'evidence'),{recursive:true});
 await writeFile(path.join(root,'evidence/SYNTHETIC_GPU.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({result:result.result,cases:result.cases.map(c=>({key:c.key,result:c.result,gpuFrames:c.gpuFramesChecked,
  protectedChangedPixels:c.allProtectedChangedPixels,markerChangedPixels:c.allMarkerChangedPixels,negativeCases:c.negativeCases})),
  detailFraming:framing,output:'evidence/SYNTHETIC_GPU.json'}));
}catch(error){if(serverError)error.serverDiagnostic=serverError;throw error;}
finally{await browser?.close();server.kill();}
