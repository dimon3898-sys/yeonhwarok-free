// Native-layout-derived Collision Synthetic Fixture; never a production route.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(engine);
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const fixture=JSON.parse(await readFile(path.join(engine,'recovery/event-v1-candidate/fixtures/collision-synthetic.json'),'utf8'));
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{stdio:['ignore','pipe','inherit']});
let browser;
try {
 const url=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('SERVER_TIMEOUT')),10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);resolve(JSON.parse(line).url);});
  server.once('error',reject);server.once('exit',code=>reject(Error('SERVER_EXIT_'+code)));
 });
 browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
 await page.goto(url+'/runtime-config.json');
 const report=await page.evaluate(async fixture=>{
  const {createEventGpuPipeline}=await import('/modules/event_gpu_pipeline_v1.mjs');
  const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
  const {compileEventPlan}=await import('/modules/event_timeline_v1.mjs');
  const {compileGeographicLinePrimitive,evaluateGeographicLineReveal}=await import('/modules/event_line_v1.mjs');
  const {validateEventLineFootprint}=await import('/modules/event_line_pass_v1.mjs');
  const {chooseMetricPlacement}=await import('/modules/event_layout_adapter_v1.mjs');
  const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('HTTP_'+r.status);return r.json();};
  const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
   load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
  const originalInputs=JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input});
  const [width,height]=REGIONAL.layout.canonical;
  async function make(eventPlan=null){
   const canvas=document.createElement('canvas');document.body.appendChild(canvas);
   const pipeline=await createEventGpuPipeline({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,
    heightSource:input.heightSource,contextTerrain:input.contextTerrain,eventPlan});
   return {pipeline,dispose(){pipeline.dispose();canvas.remove();}};
  }
  const native=await make(),nativeDiagnostic=native.pipeline.drawFrame(fixture.camera_frame,{eventEnabled:false});
  const baseline=new Uint8Array(native.pipeline.readPixels()),layout=nativeDiagnostic.gpu.layout;
  const renderer=native.pipeline.evidence.gpu,bounds=nativeDiagnostic.camera.flatBounds,safeArea=native.pipeline.layoutContract.safeArea;
  const marker=layout.find(item=>item.role==='MARKER'&&item.kind==='MARKER');
  if(!marker)throw Error('SYNTHETIC_NATIVE_GEOGRAPHIC_MARKER_REQUIRED');
  const anchor=[marker.box[0]+marker.box[2]/2,marker.box[1]+marker.box[3]/2];
  const geographicAnchor=native.pipeline.layoutContract.eventAnchor;
  const project=([x,y])=>[(x-bounds[0])/(bounds[2]-bounds[0])*width,(bounds[3]-y)/(bounds[3]-bounds[1])*height];
  const inverse=([x,y])=>[bounds[0]+x/width*(bounds[2]-bounds[0]),bounds[3]-y/height*(bounds[3]-bounds[1])];
  const protectedGraphics=layout.map(item=>{
   const padding=item.kind==='TEXT'?(item.outlineRadius??item.metrics?.outlineRadius??0)+2:2;
   return {kind:item.role==='MARKER'&&item.kind==='MARKER'?'MARKER':item.kind==='TEXT'?'TEXT':'PANEL',
    box:[item.box[0]-padding,item.box[1]-padding,item.box[0]+item.box[2]+padding,item.box[1]+item.box[3]+padding]};
  });
  const style={width:REGIONAL.theme.primaryWidth,coreColor:REGIONAL.theme.primaryCoreColor,
   glowRadius:REGIONAL.theme.glowRadius,glowGain:REGIONAL.theme.glowGain,glowColor:REGIONAL.theme.glowColor};
  const intentFor=(coordinates,direction='FORWARD')=>compileEventIntent({data_mode:fixture.data_mode,
   line:{geometry:{type:'LineString',coordinates},direction,style_role:'PRIMARY',source:fixture.source}});
  let selected=null;const candidates=[];
  for(const direction of fixture.derivation.candidate_screen_directions){
   const length=Math.hypot(...direction),halfSpan=marker.box[2]*fixture.derivation.half_span_marker_sizes;
   const delta=direction.map(value=>value/length*halfSpan);
   const coordinates=[inverse(anchor.map((value,index)=>value-delta[index])),[...geographicAnchor],inverse(anchor.map((value,index)=>value+delta[index]))];
   const intent=intentFor(coordinates),primitive=compileGeographicLinePrimitive(intent,{project});
   try {validateEventLineFootprint(primitive,{style,safeArea,protectedGraphics});selected={coordinates,screenDirection:direction};candidates.push({direction,status:'SELECTED'});break;}
   catch(e){candidates.push({direction,status:'REJECTED',reason:e.message});}
  }
  if(!selected)throw Error('SYNTHETIC_MARKER_CROSSING_NO_VALID_NATIVE_CORRIDOR');
  native.dispose();
  const pixelDiff=(a,b,x,y)=>{const i=((height-1-y)*width+x)*4;return a[i]!==b[i]||a[i+1]!==b[i+1]||a[i+2]!==b[i+2]||a[i+3]!==b[i+3];};
  const inside=(x,y,box)=>x+.5>=box[0]&&y+.5>=box[1]&&x+.5<=box[2]&&y+.5<=box[3];
  const results=[];
  for(const direction of fixture.derivation.direction_cases){
   const intent=intentFor(selected.coordinates,direction),plan=compileEventPlan(intent,fixture.timeline),before=JSON.stringify(intent);
   const primitive=compileGeographicLinePrimitive(intent,{project}),beforePrimitive=JSON.stringify(primitive),runtime=await make(plan),frames=[];
   for(const eventFrame of [1,3,5,7,9,plan.totalFrames-1]){
    const diagnostic=runtime.pipeline.drawFrame(fixture.camera_frame,{eventEnabled:true,eventFrame}),actual=new Uint8Array(runtime.pipeline.readPixels());
    const expected=evaluateGeographicLineReveal(primitive,diagnostic.event.controls.lineFraction);
    let changed=0,outside=0,protectedChanged=0;
    for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(pixelDiff(actual,baseline,x,y)){
     changed++;if(!diagnostic.event.rois.some(box=>inside(x,y,box)))outside++;
     if(diagnostic.event.protectedBoxes.some(box=>inside(x,y,box)))protectedChanged++;
    }
    frames.push({eventFrame,fraction:diagnostic.event.controls.lineFraction,changed,outside,protectedChanged,
     path:diagnostic.event.line.path,expectedPath:expected.path,tip:diagnostic.event.line.path.at(-1)??null,
     visibleLengthPixels:diagnostic.event.line.visibleLengthPixels,expectedLengthPixels:expected.visibleLengthPixels,
     nativeLayoutExact:JSON.stringify(diagnostic.gpu.layout)===JSON.stringify(nativeDiagnostic.gpu.layout),
     nativeCameraExact:JSON.stringify(diagnostic.gpu.actualCamera)===JSON.stringify(nativeDiagnostic.gpu.actualCamera),
     markerOcclusions:diagnostic.event.line.markerOcclusions??[]});
   }
   runtime.pipeline.drawFrame(fixture.camera_frame,{eventEnabled:false});
   const restored=new Uint8Array(runtime.pipeline.readPixels());let restoredDiff=0;
   for(let index=0;index<baseline.length;index++)if(baseline[index]!==restored[index])restoredDiff++;
   results.push({direction,derivedIntent:intent,frames,restoredByteDifference:restoredDiff,
    intentUnchanged:JSON.stringify(intent)===before,primitiveUnchanged:JSON.stringify(primitive)===beforePrimitive});runtime.dispose();
  }
  async function rejected(coordinates){
   const runtime=await make(compileEventPlan(intentFor(coordinates),fixture.timeline));
   let reason=null;try{runtime.pipeline.drawFrame(fixture.camera_frame,{eventEnabled:true,eventFrame:9});}catch(e){reason=e.message;}
   runtime.dispose();return reason;
  }
  const negative=[];
  for(const role of fixture.negative_roles){
   const item=layout.find(value=>value.role===role);if(!item)throw Error('SYNTHETIC_NATIVE_NEGATIVE_ROLE_MISSING_'+role);
   const center=[item.box[0]+item.box[2]/2,item.box[1]+item.box[3]/2];
   const halfSpan=Math.min(8,item.box[2]/4);
   negative.push({role,kind:item.kind,reason:await rejected([inverse([center[0]-halfSpan,center[1]]),inverse([center[0]+halfSpan,center[1]])])});
  }
  const linePadding=style.width/2+Math.max(.5,style.glowRadius)+1;
  const safeChecks={
   endpoint:await rejected([inverse([safeArea[0]-2,safeArea[1]+100]),inverse([safeArea[0]+20,safeArea[1]+100])]),
   halo:await rejected([inverse([safeArea[0]+linePadding/2,safeArea[1]+100]),inverse([safeArea[0]+linePadding+20,safeArea[1]+100])])
  };
  // A Marker type never gains an exemption in the independent Metric placer.
  let metricMarkerReason=null;
  try {chooseMetricPlacement({anchor,measurement:{atlasDimensions:[42,18]},safeArea,
   protectedBoxes:[{kind:'MARKER',box:safeArea}],markerSize:marker.box[2],gap:18});}
  catch(e){metricMarkerReason=e.message;}
  return {status:'PASS',scope:fixture.scope,fixtureId:fixture.id,renderer,anchor,geographicAnchor,
   selectedScreenDirection:selected.screenDirection,candidates,results,negative,safeChecks,metricMarkerReason,
   protectedInputsUnchanged:originalInputs===JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input})};
 },fixture);
 assert.match(report.renderer,/SwiftShader/);assert.equal(errors.length,0);assert.equal(report.protectedInputsUnchanged,true);
 for(const result of report.results){
  assert.equal(result.intentUnchanged,true);assert.equal(result.primitiveUnchanged,true);assert.equal(result.restoredByteDifference,0);
  for(const frame of result.frames){
   assert.equal(frame.outside,0);assert.equal(frame.protectedChanged,0);assert.equal(frame.nativeLayoutExact,true);assert.equal(frame.nativeCameraExact,true);
   assert.deepEqual(frame.path,frame.expectedPath);assert.equal(frame.visibleLengthPixels,frame.expectedLengthPixels);
   if(frame.fraction>0){assert.ok(frame.changed>0);assert.ok(frame.markerOcclusions.length>0);}
  }
  const midpoint=result.frames.find(frame=>frame.fraction===.5);
  assert.ok(Math.hypot(midpoint.tip[0]-report.anchor[0],midpoint.tip[1]-report.anchor[1])<1e-7,'arc-length progresses behind native Marker');
  assert.equal(result.frames.at(-1).fraction,1);
 }
 for(const item of report.negative)assert.equal(item.reason,'EVENT_LINE_PROTECTED_GRAPHIC_COLLISION',item.role);
 assert.equal(report.safeChecks.endpoint,'EVENT_GEOMETRY_OUTSIDE_SAFE_AREA');
 assert.equal(report.safeChecks.halo,'EVENT_LINE_HALO_OUTSIDE_SAFE_AREA');
 assert.equal(report.metricMarkerReason,'EVENT_METRIC_LAYOUT_BLOCKED');
 const arg=process.argv.indexOf('--report');
 if(arg>=0){if(!process.argv[arg+1])throw Error('REPORT_PATH_REQUIRED');await writeFile(process.argv[arg+1],JSON.stringify(report,null,2)+'\n');}
 console.log(JSON.stringify(report));
} finally {await browser?.close();server.kill();}
