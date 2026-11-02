/** Focused qualification of the new quality Scene only. No browser or GPU launch. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileScenePlan} from '../../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {evaluateAreaFrame} from '../../../web/map_infographic_v1/area_core_v3.mjs';
import {analyzePresentationPrompt} from '../../universal-presentation-v2/presentation_prompt.mjs';
import {canonicalJSON,pointInCountry} from '../../universal-presentation-v2/region_source.mjs';
import {validatePresentation,compilePresentationEnginePlan,assertPresentationBoundaryContinuity,
 evaluatePresentationCameraFrame,projectBounds} from '../../universal-presentation-v2/presentation_plan.mjs';
import {prepareRuntimeRequest} from '../../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs';

const HERE=path.dirname(fileURLToPath(import.meta.url)),ROOT=path.resolve(HERE,'..');
const sha=x=>createHash('sha256').update(x).digest('hex');
const geometrySHA=x=>sha(canonicalJSON(x));
const inputPath=path.join(ROOT,'QUALITY_LABELS_10S.json');
const inputRaw=await fs.readFile(inputPath),input=JSON.parse(inputRaw);
const checks=[];
const check=(name,fn)=>{fn();checks.push({name,status:'PASS'});};
const polygonSHA='dce5948b914856654d0018bf361bbb581a8a4cc39b43fca4bdb457ce0f8bedd8';
const scenes=input.data.scenes.map(row=>({row,scene:compileScenePlan({topic:input.data.topic,facts:row.facts,
 output:{width:1080,height:1920,fps:30}})}));
const {sceneOverrides,...sharedPresentation}=input.presentation;
const presentations=scenes.map(({row,scene})=>validatePresentation({...sharedPresentation,
 ...sceneOverrides?.[row.sceneId]},{scene,region:input.region}));

check('existing two-segment 10-second path retained',()=>{
 assert.equal(input.schema,'WORLD_ENGINE_PRESENTATION_PROMPT_V2');
 assert.deepEqual(input.data.resolution,{width:1080,height:1920});
 assert.equal(input.data.fps,30);assert.equal(input.data.durationSeconds,10);
 assert.deepEqual(input.data.scenes.map(r=>[r.startFrame,r.endFrame]),[[0,150],[150,300]]);
 assert.deepEqual(input.presentation.transitions,[{type:'CUT',frame:150}]);
 assert(scenes.every(({scene})=>scene.timing.total_frames===150));
});
check('real country polygon retained; artificial rectangles and counts removed',()=>{
 for(const {scene}of scenes){
  assert.equal(scene.geometries.length,2);
  const country=scene.geometries.find(g=>g.id==='COUNTRY_NAM');
  const border=scene.geometries.find(g=>g.id==='NAM_COAST_ACCENT');
  assert.equal(geometrySHA(country.geometry),polygonSHA);
  assert.deepEqual(border.geometry,{type:'LineString',coordinates:country.geometry.coordinates[0].slice(140,155)});
  assert.equal(border.geometry.coordinates.length,15);
  assert(border.geometry.coordinates.length<=128,'Existing area line capacity is preserved');
  assert(scene.areas.every(a=>a.geometry_ref==='COUNTRY_NAM'));
  assert(scene.front_lines.every(f=>f.geometry_ref==='NAM_COAST_ACCENT'));
  assert.equal(scene.routes?.length??0,0);assert.equal(scene.metrics?.length??0,0);
  for(const location of scene.locations)assert(pointInCountry(location.anchor,
   {geometry_type:country.geometry.type,coordinates:country.geometry.coordinates}),location.id);
  assert(country.geometry.coordinates[0].some(p=>JSON.stringify(p)===JSON.stringify(
   scene.locations.find(l=>l.id==='NAM_COAST').anchor)));
  assert(border.geometry.coordinates.some(p=>JSON.stringify(p)===JSON.stringify(
   scene.locations.find(l=>l.id==='NAM_COAST').anchor)));
 }
 assert(presentations.every(p=>p.labels.items.every(l=>l.role!=='NUMERIC')));
 assert.equal(input.data.simulationType,'GENERAL');
 assert(input.data.scenes.every(s=>s.facts.source_notes.every(n=>n.note.includes('not historical'))));
});
check('new coast accent compiles inside the unchanged existing area line capacity',()=>{
 for(const {scene}of scenes){
  const engines=compileExistingEnginePlan(scene);
  assert.equal(engines.plans.length,1);
  assert.equal(engines.plans[0].engine,'EXISTING_AREA_V3');
 }
});
check('source-state, color, country label and camera seam are continuous',()=>{
 assert.equal(assertPresentationBoundaryContinuity(
  {scene:scenes[0].scene,presentation:presentations[0]},
  {scene:scenes[1].scene,presentation:presentations[1]}).status,'SOURCE_STATE_CONTINUITY_CONFIRMED');
 const a=presentations[0].camera.keyframes.at(-1),b=presentations[1].camera.keyframes[0];
 assert.deepEqual(a.center,b.center);assert.equal(a.zoom,b.zoom);
 const aHold=presentations[0].camera.keyframes.at(-2),bHold=presentations[1].camera.keyframes[1];
 assert.deepEqual(aHold.center,a.center);assert.equal(aHold.zoom,a.zoom);
 assert.deepEqual(bHold.center,b.center);assert.equal(bHold.zoom,b.zoom);
 const labels=presentations.map(p=>p.labels.items.find(l=>l.id==='namibia-country'));
 assert.deepEqual(labels[0],labels[1]);assert.equal(labels[0].revealFrames,1);assert.equal(labels[0].exitFrames,1);
 assert.equal(presentations[1].mapStyle.revealFrames,1);
});
check('style and event windows opt in to connected consumers',()=>{
 for(const p of presentations){
  assert.equal(p.mapStyle.preset,'COUNTRY_FOCUS_V1');assert.equal(p.mapStyle.countryFill,false);
  assert(p.labels.items.every(l=>l.style==='REFERENCE_V1'));
  const event=p.labels.items.find(l=>l.role==='EVENT');
  assert.equal(event.pin,'HERO');assert.equal(event.reveal,'GRAPHEME_POP');
  const h=p.highlights.find(h=>h.id===event.eventId);
  assert.equal(event.locationId,h.locationId);assert(event.startFrame>=h.startFrame&&event.endFrame<=h.endFrame);
 }
 assert.equal(presentations[0].highlights[0].locationId,'WINDHOEK');
 assert.equal(presentations[1].highlights[0].locationId,'NAM_COAST');
});

const args=process.argv.slice(2),options={};
for(const arg of args){const index=arg.indexOf('=');assert(index>2,'Use --key=value');options[arg.slice(2,index)]=arg.slice(index+1);}
assert(Object.keys(options).every(k=>['private-root','public-root','output'].includes(k)),'Unknown option');
let preparation={status:'NOT_RUN',reason:'Actual source checkout/private workspace required; no source or pixel PASS inferred from structural checks.'};
if(Object.keys(options).length){
 assert(Object.keys(options).length===3,'Supply --private-root, --public-root and --output together');
 const privateRoot=path.resolve(options['private-root']),publicRoot=path.resolve(options['public-root']),output=path.resolve(options.output);
 await fs.mkdir(output,{mode:0o700});
 const analysis=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true});
 await fs.writeFile(path.join(output,'ANALYSIS.json'),JSON.stringify(analysis,null,2)+'\n',{flag:'wx'});
 assert.equal(analysis.status,'PASS',JSON.stringify(analysis.issues));
 assert.equal(analysis.renderRequests.length,2);assert.equal(analysis.totalFrames,300);
 const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,
  sourceInputSHA256:analysis.inputSHA256,transitions:analysis.transitionPlan,
  segments:analysis.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,
   scene:r.scene,region:r.region,presentation:r.presentation,inputTrace:r.inputTrace}))};
 const prepared=await prepareRuntimeRequest({request,cacheRoot:path.join(privateRoot,'quality-scene-sources'),
  privateWorkspaceRoot:privateRoot,publicExportRoot:publicRoot});
 const inside=(p,b)=>p[0]>=b[0]-1e-8&&p[0]<=b[2]+1e-8&&p[1]>=b[1]-1e-8&&p[1]<=b[3]+1e-8;
 const points=g=>g.type==='Polygon'?g.coordinates.flat():g.type==='MultiPolygon'?g.coordinates.flat(2):g.coordinates;
 const frames=[];
 for(const segment of prepared.segments){
  const engine=compilePresentationEnginePlan({scene:segment.scene,presentation:segment.presentation});
  for(let frame=0;frame<segment.endFrame-segment.startFrame;frame++){
   const camera=evaluatePresentationCameraFrame(segment.presentationPlan,frame),bounds=camera.flatBounds,
    project=p=>projectBounds(bounds,p),safe=segment.nativePlan.layout.safe,source=segment.sourceStyle.terrainAsset;
   assert(camera.camera.noCloserThanApprovedStop,'Existing detail guard');
   const gutter=Math.min((bounds[0]-source.bounds[0])/source.pixelSpacing[0],(bounds[1]-source.bounds[1])/source.pixelSpacing[1],
    (source.bounds[2]-bounds[2])/source.pixelSpacing[0],(source.bounds[3]-bounds[3])/source.pixelSpacing[1]);
   assert(gutter>=1-1e-8,'Full camera source coverage');
   const local=frame-engine.globalEventStartFrame,areas=[];
   if(local>=0)for(const binding of engine.plans){
    assert.equal(binding.engine,'EXISTING_AREA_V3');
    const state=evaluateAreaFrame(binding.plan,binding.plan.startFrame+local,{project});
    for(const area of state.areas)if(area.alpha>0){assert(points(area.geometry).every(p=>inside(project(p),safe)),
     `UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE frame=${segment.startFrame+frame}`);areas.push(area.id);}
   }
   const labels=segment.presentation.labels.items.filter(l=>frame>=l.startFrame&&frame<l.endFrame);
   for(const l of labels)assert(inside(project(l.anchor),safe),`Label anchor outside safe: ${l.id}`);
   frames.push({frame:segment.startFrame+frame,segment:segment.sceneId,localFrame:frame,bounds,
    minimumSourceGutterPixels:gutter,activeAreas:areas,activeLabelIds:labels.map(l=>l.id)});
  }
 }
 assert.equal(frames.length,300);assert.deepEqual(frames[149].bounds,frames[150].bounds);
 await fs.writeFile(path.join(output,'REQUEST.json'),JSON.stringify(request,null,2)+'\n',{flag:'wx'});
 await fs.writeFile(path.join(output,'PREPARED.json'),JSON.stringify(prepared,null,2)+'\n',{flag:'wx'});
 await fs.writeFile(path.join(output,'CPU_FRAME_AUDIT.json'),JSON.stringify({schema:'WORLD_ENGINE_QUALITY_SCENE_CPU_FRAMES_V1',
  sourceQualificationSHA256:prepared.sourceQualificationSHA256,frames,pixelRendering:false,visualQuality:'NOT_RUN'},null,2)+'\n',{flag:'wx'});
 preparation={status:'PASS',sourceQualificationSHA256:prepared.sourceQualificationSHA256,frames:300,
  sourceAdmission:'ACTUAL_FILES',cameraCoverage:'PASS',wholeCountrySafeFootprint:'PASS',sceneSeam:'PASS',
  labelPixels:'NOT_RUN_BY_THIS_TEST',gpu:'NOT_RUN'};
}
const result={schema:'WORLD_ENGINE_QUALITY_SCENE_FOCUSED_RESULT_V1',status:'PASS',inputSHA256:sha(inputRaw),
 normalizedInputSHA256:sha(canonicalJSON(input)),countryPolygonSHA256:polygonSHA,checks,preparation,
 oldPassReruns:0,gpuStarts:0,fullRenders:0,visualQuality:'REQUIRES_NEW_VIDEO_REVIEW'};
if(options.output)await fs.writeFile(path.join(path.resolve(options.output),'SCENE_RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result,null,2));
