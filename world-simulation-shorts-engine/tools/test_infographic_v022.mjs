/** Native camera/material and actual 2D overlay contracts. No GPU pixels. */
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {webcrypto,createHash} from 'node:crypto';
import fsPromises from 'node:fs/promises';
import http from 'node:http';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';

const root=path.resolve('.'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const strip=file=>read(file).replace(/^import .*;$/gm,'').replace(/^export /gm,'');
if(process.argv[2]==='--canvas-snapshots'){await runCanvasSnapshots(process.argv[3]);process.exit(0);}
if(!process.argv[2])throw Error('Provide the explicitly selected v022 plan path');
const plan=JSON.parse(fs.readFileSync(process.argv[2]));
if(plan.scenes.length>1&&process.env.WORLD_ENGINE_NATIVE_SCENE_INDEX===undefined){
 const results=plan.scenes.map((scene,index)=>{
  const destination=process.argv[3]?path.join(process.argv[3],scene.scene_id):null,args=[process.argv[1],process.argv[2],...(destination?[destination]:[])];
  const output=execFileSync(process.execPath,args,{cwd:root,env:{...process.env,WORLD_ENGINE_NATIVE_SCENE_INDEX:String(index)},encoding:'utf8',maxBuffer:16*1024*1024});
  return {...JSON.parse(output.trim()),scene_id:scene.scene_id};
 });
 const result={passed:results.every(value=>value.passed),checks:results.reduce((sum,value)=>sum+value.checks,0),frames:results.reduce((sum,value)=>sum+value.frames,0),scene_count:results.length,scene_results:results,parent_renderer_family:'production-earth-v1',camera_trajectory:'UNCHANGED',material:'UNCHANGED',overlay_off:'UNCHANGED',audio:'UNCHANGED',source_scene_immutable:true,primary_motion_effect_peak:Math.max(...results.map(value=>value.primary_motion_effect_peak)),additional_texture_uploads:results.reduce((sum,value)=>sum+value.additional_texture_uploads,0),GPU:'NOT_RUN',pixel_quality:'NOT_RUN',scope:'All authored dynamic Production scenes, each executing actual inherited frame/overlay/audit methods; no NVIDIA pixels.'};
 if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});fs.writeFileSync(path.join(process.argv[3],'native-result.json'),JSON.stringify(result,null,2)+'\n');}
 console.log(JSON.stringify(result));process.exit(0);
}
const inputScene=structuredClone(plan.scenes[Number(process.env.WORLD_ENGINE_NATIVE_SCENE_INDEX||0)]);
assert.equal(inputScene.infographic?.version,'v022');
const family=inputScene.infographic.parent_renderer_family;
if(family==='story-progression-v021'){assert.equal(inputScene.reference_effects?.version,'v020');assert.equal(inputScene.story_progression?.version,'v021');}
const originalInput=JSON.stringify(inputScene),THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const flat=new Function('THREE',strip('web/flat_semantics.js')+';return {flatClamp,flatNumber,flatSmooth,flatCameraEase,flatWindow,flatCoordinate};')(THREE);
const geo=(lon,lat,radius=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(radius);
const earth=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',strip('web/earth_adapter.js')+';return {SceneEarthRenderer,GenericCamera};')(THREE,class{},class{},()=>null,geo,flat.flatClamp,flat.flatSmooth);
const polish=new Function('THREE','SceneEarthRenderer','incomingGeographicTransition','FlatSceneCore','flatCoordinate','polishFlatLabels','avoidCityLabelObstacles','flatPolishProjectedAircraftObstacles',strip('web/earth_polish_adapter.js')+';return {SceneEarthPolishRenderer};')(THREE,earth.SceneEarthRenderer,()=>null,class{},flat.flatCoordinate,()=>null,()=>null,()=>null);
const production=new Function('THREE','SceneFlatEntitySeparationPolishRenderer','SceneEarthPolishRenderer','flatClamp','flatNumber','flatSmooth','flatCameraEase','flatWindow','flatCoordinate',strip('web/production_visual_adapter.js')+';return {productionLabelScene,productionUsesRouteHeadAnchor,SceneProductionEarthRenderer};')(THREE,class{},polish.SceneEarthPolishRenderer,flat.flatClamp,flat.flatNumber,flat.flatSmooth,flat.flatCameraEase,flat.flatWindow,flat.flatCoordinate);
const single=new Function('THREE','SceneProductionEarthRenderer',strip('web/single_event_camera.js')+';return {singleCameraValues,installSingleCamera};')(THREE,class{});
const returning=new Function('singleCameraValues','installSingleCamera','SceneSingleEventRenderer',strip('web/return_wide_camera.js')+';return {returnCameraValues,installReturnCamera};')(single.singleCameraValues,single.installSingleCamera,class{});

// The recording context executes the original glyph/layout/shadow calls.
// Widths are deterministic fixture metrics, not a claim about font raster pixels.
class RecordingContext{
 constructor(){this.commands=[];this.stack=[];this.state={globalAlpha:1,font:'10px fixture'};return new Proxy(this,{get:(target,key)=>key in target?target[key]:target.state[key],set:(target,key,value)=>{if(key in target)target[key]=value;else{target.state[key]=value;target.commands.push(['set',key,value&&typeof value==='object'?{gradient_stops:structuredClone(value.stops)}:value]);}return true;}});}
 save(){this.commands.push(['save']);this.stack.push({...this.state});}
 restore(){assert(this.stack.length,'Balanced Canvas2D restore');this.commands.push(['restore']);this.state=this.stack.pop();}
 translate(...args){this.commands.push(['translate',...args]);}
 scale(...args){this.commands.push(['scale',...args]);}
 measureText(value){return {width:[...String(value)].reduce((sum,ch)=>sum+(ch===' '?.32:.55)*parseFloat(this.state.font.match(/([\d.]+)px/)?.[1]||10),0)};}
 createRadialGradient(...args){this.commands.push(['gradient',...args]);const stops=[];return {addColorStop:(...stop)=>{stops.push(stop);this.commands.push(['stop',...stop]);},stops};}
 fillRect(...args){this.commands.push(['fillRect',...args]);}
 fillText(...args){this.commands.push(['fillText',...args]);}
 strokeText(...args){this.commands.push(['strokeText',...args]);}
 drawImage(source,...args){this.commands.push(['drawImage',typeof source==='string'?source:'fixture',...args]);}
 moveTo(...args){this.commands.push(['moveTo',...args]);}
 lineTo(...args){this.commands.push(['lineTo',...args]);}
 closePath(){this.commands.push(['closePath']);}
 fill(...args){this.commands.push(['fill',...args]);}
 beginPath(){this.commands.push(['beginPath']);}
 arc(...args){this.commands.push(['arc',...args]);}
 stroke(){this.commands.push(['stroke']);}
 reset(){assert.equal(this.stack.length,0);this.commands=[];this.state={globalAlpha:1,font:'10px fixture'};}
}

const baseSource=fs.readFileSync(path.join(root,'../cinematic-world-map/src/renderer_v3.js'),'utf8');
let surface=baseSource.match(/const surfaceFragment=`([\s\S]*?)`;/)[1];
surface=surface.replace('uniform float uTime;','uniform float uTime,uReadability,uExposure,uCityGain;').replace('vec3 lights=vec3(1.,.46,.15)*city*dark*focus*.80;','vec3 lights=vec3(1.,.46,.15)*city*dark*focus*.80*uCityGain;').replace('gl_FragColor=vec4(diffuse+vec3(1.,.90,.74)*spec+lights,1.);','vec3 readable=day*vec3(.78,.87,.97)*uReadability;gl_FragColor=vec4((diffuse+readable+vec3(1.,.90,.74)*spec+lights)*uExposure,1.);');
const surfaceFixture={map:{surface:{fragmentShader:surface,uniforms:{}}},geographicHandoff:null};
polish.SceneEarthPolishRenderer.prototype.installPolishSurface.call(surfaceFixture);surface=surfaceFixture.map.surface.fragmentShader;

class ParentFixture{
 constructor(scene,plan){
  this.scene=new THREE.Scene();this.sceneSpec=production.productionLabelScene(scene);this.plan=plan;this.duration=scene.duration;this.w=2160;this.h=3840;
  this.camera=new THREE.PerspectiveCamera(64,9/16,.02,30);this.cam={scene:this.sceneSpec,camera:this.camera};
  this.ctx=new RecordingContext();this.actx=new RecordingContext();this.accum='accumulated map';this.canvas={};
  this.polishReady=true;this.geographicHandoff=null;this.labels=[];this.eventAudit=[];
  this.routes={routes:[],byId:()=>null,active:()=>null};this.graphics={items:[]};this.entities={items:[],update:()=>{}};
  this.effects={items:[],update:()=>{}};
  const texture=(width,height)=>{const value=new THREE.Texture();value.image={width,height};return value;};
  this.map={surface:{fragmentShader:surface,uniforms:Object.fromEntries(['uDay','uNight','uCloud','uTopo'].map(name=>[name,{value:texture(name==='uTopo'?2048:8192,name==='uTopo'?1024:4096)}]))}};
  this.gl={domElement:'unchanged map canvas',capabilities:{maxTextureSize:8192,getMaxAnisotropy:()=>8},properties:{get:()=>({__webglTexture:{}})}};
 }
 async init(){returning.installReturnCamera(this.cam);this.frame(0);return this;}
 incomingCityBoxes(){return [];}
 mapAt(t){this.shaderTime=t;}
 sceneAt(t){this.cam.update(t);this.mapAt(t);}
 frame(t,samples=1){return earth.SceneEarthRenderer.prototype.frame.call(this,t,samples);}
 project(point){return earth.SceneEarthRenderer.prototype.project.call(this,point);}
 overlay(t){return production.SceneProductionEarthRenderer.prototype.overlay.call(this,t);}
 drawStoryInformation(t){return production.SceneProductionEarthRenderer.prototype.drawStoryInformation.call(this,t);}
 dispatchEventAudit(t){return production.SceneProductionEarthRenderer.prototype.dispatchEventAudit.call(this,t);}
 audit(t){return {t,cameraPosition:this.camera.position.toArray(),cameraQuaternion:this.camera.quaternion.toArray(),cameraFov:this.camera.fov,labels:this.labels,meaningfulEventsRendered:this.eventAudit,textClipped:this.labels.filter(b=>b.x<0||b.y<0||b.x+b.width>this.w||b.y+b.height>this.h)};}
}
const camera=new Function('THREE','returnCameraValues','installReturnCamera','SceneReturnWideRenderer',strip('web/second_event_camera.js')+';return {SceneSecondEventRenderer};')(THREE,returning.returnCameraValues,returning.installReturnCamera,ParentFixture);
const manifest=JSON.parse(read('web/earth-detail/v018/manifest.json')),assets=Object.fromEntries(manifest.textures.map(source=>[source.url,fs.readFileSync(path.join(root,source.file))]));
const regionalDays=manifest.textures.filter(source=>source.role==='regional_day_relief');
const regionalMasks=manifest.textures.filter(source=>source.role==='regional_land_mask');
assert.equal(regionalDays.length,2);assert.equal(regionalMasks.length,2);
let delayedDecodeHash=null,releaseOnMaskURL=null,releaseDecode=null,deferredDecode=Promise.resolve();
// Force opposite completion orders without timers: the chosen verified day
// decode waits until the other region has progressed to requesting its mask.
// Both regions still run through the actual asynchronous SHA/source checks.
function delayRegionDecode(index){
 delayedDecodeHash=regionalDays[index].sha256;
 releaseOnMaskURL=regionalMasks.find(source=>source.region_id===regionalDays[1-index].region_id).url;
 deferredDecode=new Promise(resolve=>{releaseDecode=resolve;});
}
const mockTHREE={...THREE,TextureLoader:class{async loadAsync(url){assert(url.startsWith('data:image/png;base64,'));const bytes=Buffer.from(url.split(',')[1],'base64');assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');if(createHash('sha256').update(bytes).digest('hex')===delayedDecodeHash)await deferredDecode;const value=new THREE.Texture();value.image={width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)};return value;}}};
const quality=new Function('THREE','SceneSecondEventRenderer',strip('web/visual_quality_adapter.js')+';return {SceneVisualQualityRenderer,digestBytes,trustedStaticURL,validateQualityProfile,validateDetailManifest,qualityWeight,configureQualityTexture};')(mockTHREE,camera.SceneSecondEventRenderer);
const eventQuality=new Function('SceneVisualQualityRenderer','digestBytes','trustedStaticURL',strip('web/event_quality_adapter.js')+';return {SceneEventQualityRenderer,validateEventQualityProfile};')(quality.SceneVisualQualityRenderer,quality.digestBytes,quality.trustedStaticURL);
const effects=new Function('THREE','SceneEventQualityRenderer','digestBytes','trustedStaticURL','flatCoordinate','productionUsesRouteHeadAnchor',strip('web/reference_effects_adapter.js')+';return {createReferenceEffectsRenderer,SceneReferenceEffectsRenderer,validateReferenceEffectsEvents,validateReferenceEffectsProfile,characterRevealState,markerPopState};')(THREE,eventQuality.SceneEventQualityRenderer,quality.digestBytes,quality.trustedStaticURL,flat.flatCoordinate,production.productionUsesRouteHeadAnchor);

globalThis.location={origin:'http://localhost'};if(!globalThis.crypto)globalThis.crypto=webcrypto;
const buffers=Object.fromEntries(['visual_quality_v018.json','event_quality_v019.json','reference_effects_v020.json','story_progression_v021.json'].map(name=>['/static/'+name,fs.readFileSync(path.join(root,'web',name))]));
const manifestURL=JSON.parse(buffers['/static/visual_quality_v018.json']).regional_detail.manifest_url;
buffers[manifestURL]=fs.readFileSync(path.join(root,'web/earth-detail/v018/manifest.json'));
const profile=effects.validateReferenceEffectsProfile(JSON.parse(buffers['/static/reference_effects_v020.json']));
const oldFetch=globalThis.fetch,requests=[];
globalThis.fetch=async url=>{requests.push(url);const bytes=buffers[url]||assets[url];assert(bytes,'Only deployed verified resources may be fetched');if(url===releaseOnMaskURL)releaseDecode();return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};};
let checks=0;const check=operation=>{operation();checks++;};
// Promise.all keeps region results ordered, but independent verified day
// completions may issue mask fetches in either order. Count every URL so this
// comparison still rejects an added, missing or duplicated OFF request.
const requestInventory=urls=>[...new Set(urls)].sort().map(url=>[url,urls.filter(value=>value===url).length]);
const assertRequestInventory=(actual,expected)=>assert.deepEqual(requestInventory(actual),requestInventory(expected));

const story=new Function('SceneReferenceEffectsRenderer','createReferenceEffectsRenderer','digestBytes','trustedStaticURL',strip('web/story_progression_adapter.js')+';return {createStoryProgressionRenderer,SceneStoryProgressionRenderer,validateStoryProgressionProfile,validateStoryProgressionSelection};')(effects.SceneReferenceEffectsRenderer,effects.createReferenceEffectsRenderer,quality.digestBytes,quality.trustedStaticURL);
const storyProfile=story.validateStoryProgressionProfile(JSON.parse(buffers['/static/story_progression_v021.json']));
for(const name of ['profile','registry'])buffers['/static/infographic/v022/'+name+'.json']=fs.readFileSync(path.join(root,'web/infographic/v022',name+'.json'));
const oldDocument=globalThis.document;globalThis.document={fonts:{load:async()=>[],check:()=>true,*[Symbol.iterator](){yield {family:'Noto Cinema',weight:'400',status:'loaded'};yield {family:'Noto Cinema',weight:'700',status:'loaded'};}}};
class ProductionBaseFixture extends ParentFixture{
 async init(){this.cam=new earth.GenericCamera(this.camera,this.sceneSpec,this.routes);this.frame(0);return this;}
 overlay(t){return polish.SceneEarthPolishRenderer.prototype.overlay.call(this,t);}
}
const productionNative=new Function('THREE','SceneFlatEntitySeparationPolishRenderer','SceneEarthPolishRenderer','flatClamp','flatNumber','flatSmooth','flatCameraEase','flatWindow','flatCoordinate',strip('web/production_visual_adapter.js')+';return {SceneProductionEarthRenderer};')(THREE,class{},ProductionBaseFixture,flat.flatClamp,flat.flatNumber,flat.flatSmooth,flat.flatCameraEase,flat.flatWindow,flat.flatCoordinate);
const infographic=new Function('THREE','SceneStoryProgressionRenderer','SceneProductionEarthRenderer','createStoryProgressionRenderer','characterRevealState','markerPopState','digestBytes','trustedStaticURL','validateQualityProfile','validateDetailManifest','qualityWeight','configureQualityTexture','SceneVisualQualityRenderer','validateEventQualityProfile','SceneEventQualityRenderer',strip('web/infographic_adapter.js')+';return {SceneProductionRegionalRenderer,createInfographicRenderer,SceneInfographicRenderer,SceneProductionInfographicRenderer,validateInfographicSelection,validateInfographicProfile,validateInfographicGeometry,prepareInfographicGeometry,projectInfographicGeometry,infographicGraphemes,infographicRevealState,layoutInfographicLabels,drawInfographicLabels};')(mockTHREE,story.SceneStoryProgressionRenderer,productionNative.SceneProductionEarthRenderer,story.createStoryProgressionRenderer,effects.characterRevealState,effects.markerPopState,quality.digestBytes,quality.trustedStaticURL,quality.validateQualityProfile,quality.validateDetailManifest,quality.qualityWeight,quality.configureQualityTexture,quality.SceneVisualQualityRenderer,eventQuality.validateEventQualityProfile,eventQuality.SceneEventQualityRenderer);
try{
 const baselineScene=structuredClone(inputScene);delete baselineScene.infographic;
 const createBase=scene=>family==='production-earth-v1'?new infographic.SceneProductionRegionalRenderer(scene,plan):story.createStoryProgressionRenderer(scene,plan);
 if(family==='story-progression-v021')delayRegionDecode(0);
 const baseline=createBase(baselineScene);await baseline.init();const baseRequests=requests.splice(0);
 if(family==='story-progression-v021')delayRegionDecode(1);
 const off=infographic.createInfographicRenderer(baselineScene,plan);await off.init();const offRequests=requests.splice(0);
 delayedDecodeHash=null;releaseOnMaskURL=null;
 const on=infographic.createInfographicRenderer(inputScene,plan);await on.init();const onRequests=requests.splice(0);
 const selected=inputScene.infographic,fps=String(selected.fps).includes('/')?Number(selected.fps.split('/')[0])/Number(selected.fps.split('/')[1]):Number(selected.fps),total=selected.total_frames;
 check(()=>assert.equal(off.constructor,baseline.constructor));
 check(()=>{assertRequestInventory(offRequests,baseRequests);if(family==='story-progression-v021'){const masks=urls=>urls.filter(url=>regionalMasks.some(source=>source.url===url));assert.notDeepEqual(masks(offRequests),masks(baseRequests));}});
 check(()=>assertRequestInventory(onRequests.filter(url=>!url.startsWith('/static/infographic/v022/')),baseRequests));
 check(()=>assert.deepEqual(onRequests.filter(url=>url.startsWith('/static/infographic/v022/')).sort(),['/static/infographic/v022/profile.json','/static/infographic/v022/registry.json']));
 check(()=>{assert.throws(()=>assertRequestInventory([...offRequests,'ADDED_ASSET'],baseRequests),assert.AssertionError);if(baseRequests.length)assert.throws(()=>assertRequestInventory(offRequests.slice(1),baseRequests),assert.AssertionError);});
 const originalSpec=JSON.stringify(on.sceneSpec),receipts=[],coverage={},omissions={},markerCoverage={},geometryLayerCoverage={},geometryWidthCoverage={},stateTargets={},frames=[],primaryCounts={};let changedFrames=0,primaryPeak=0,steadyMarkerFrames=0;
 const materialValue=value=>value?.isTexture?{image:value.image,colorSpace:value.colorSpace,wrapS:value.wrapS,wrapT:value.wrapT,minFilter:value.minFilter,magFilter:value.magFilter,anisotropy:value.anisotropy,generateMipmaps:value.generateMipmaps}:value?.toArray?value.toArray():value;
 for(let frame=0;frame<total;frame++){
  const t=frame/fps;for(const renderer of [baseline,off,on]){renderer.ctx.reset();renderer.actx.reset();renderer.frame(t);}
  const before=baseline.audit(t),inactive=off.audit(t),after=on.audit(t),receipt=after.infographic;
  assert.deepEqual(off.ctx.commands,baseline.ctx.commands);assert.deepEqual(off.actx.commands,baseline.actx.commands);const inactiveComparable=structuredClone(inactive),beforeComparable=structuredClone(before);if(family==='production-earth-v1'){delete inactiveComparable.regionalLOD.initialization_seconds;delete beforeComparable.regionalLOD.initialization_seconds;}assert.deepEqual(inactiveComparable,beforeComparable);
  for(const renderer of [off,on]){
   assert.deepEqual(renderer.camera.position.toArray(),baseline.camera.position.toArray());assert.deepEqual(renderer.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(renderer.camera.fov,baseline.camera.fov);assert.deepEqual(renderer.cam.values(t),baseline.cam.values(t));assert.equal(renderer.shaderTime,baseline.shaderTime);
   assert.equal(renderer.map.surface.fragmentShader,baseline.map.surface.fragmentShader);assert.deepEqual(Object.keys(renderer.map.surface.uniforms),Object.keys(baseline.map.surface.uniforms));
   for(const [name,uniform] of Object.entries(renderer.map.surface.uniforms))assert.deepEqual(materialValue(uniform.value),materialValue(baseline.map.surface.uniforms[name].value));
  }
  assert.deepEqual(on.actx.commands,baseline.actx.commands);assert.equal(JSON.stringify(on.sceneSpec),originalSpec);assert.equal(JSON.stringify(inputScene),originalInput);assert.equal(on.ctx.stack.length,0);
  assert.equal(receipt.frame,frame);assert.equal(receipt.added_sfx,0);assert.equal(receipt.added_routes,0);assert.equal(receipt.added_entities,0);assert.equal(receipt.additional_texture_uploads,family==='production-earth-v1'?(on.regionalMaterialReceipt?.texture_uploads||0):0);assert.equal(receipt.subtitle.owner,'ffmpeg');assert.equal(receipt.subtitle.native_drawn,false);
  assert(receipt.primary_motion_effect_count<=1,`Distinct primary marker and label overlap at frame ${frame}`);primaryPeak=Math.max(primaryPeak,receipt.primary_motion_effect_count);primaryCounts[frame]=receipt.primary_motion_effect_count;
  for(const label of receipt.labels){const source=selected.labels.find(value=>value.id===label.id);if(source){assert.equal(label.text,source.text);assert.equal(label.font.weight,label.role==='EVENT_TITLE'?700:400);assert.equal(label.source_ref?.semantic_segment_ref??null,source.source_ref?.semantic_segment_ref??null);coverage[label.id]=(coverage[label.id]||0)+1;}else assert(label.id.startsWith('WATERMARK_'));assert(label.box.x>=receipt.layout.safe_area.left-1e-7&&label.box.y>=receipt.layout.safe_area.top-1e-7&&label.box.x+label.box.width<=receipt.layout.safe_area.right+1e-7&&label.box.y+label.box.height<=receipt.layout.safe_area.bottom+1e-7);}
  for(const omitted of receipt.layout.omitted)omissions[omitted.reason]=(omissions[omitted.reason]||0)+1;
  for(const marker of receipt.markers){assert(marker.coordinate_role);markerCoverage[marker.id]=(markerCoverage[marker.id]||0)+1;if(marker.phase==='PERSISTENT'){assert.equal(marker.scale,1);steadyMarkerFrames++;}}
  for(const geometry of receipt.geometry){if(geometry.layer_id)geometryLayerCoverage[geometry.layer_id]=(geometryLayerCoverage[geometry.layer_id]||0)+1;const widthKey=geometry.geometry_id+'@'+geometry.line_width_px_1080;geometryWidthCoverage[widthKey]=(geometryWidthCoverage[widthKey]||0)+1;assert.equal(geometry.boundary_draw_progress,false);assert(geometry.line_width_px_1080>=2&&geometry.line_width_px_1080<=5);assert.equal(geometry.holes_preserved,true);assert(selected.geometry_ids.includes(geometry.geometry_id));const record=selected.geometries.find(value=>value.id===geometry.geometry_id);assert.notEqual(record.geometry_type,'Point');assert.equal(geometry.source_sha256,record.sha256);(stateTargets[geometry.geometry_id]||=new Set()).add(geometry.state_after);}
  if(JSON.stringify(on.ctx.commands)!==JSON.stringify(baseline.ctx.commands))changedFrames++;
  if(receipt.geometry.length||receipt.markers.length||receipt.labels.length)receipts.push(structuredClone(receipt));
  frames.push({frame,position:on.camera.position.toArray(),quaternion:on.camera.quaternion.toArray(),FOV:on.camera.fov,target:on.cam.values(t),infographic:{geometry_count:receipt.geometry.length,marker_count:receipt.markers.length,label_count:receipt.labels.length,primary_motion_effect_count:receipt.primary_motion_effect_count}});
 }
 check(()=>assert.equal(JSON.stringify(inputScene),originalInput));
 check(()=>assert.equal(JSON.stringify(on.sceneSpec),originalSpec));
 check(()=>assert.equal(frames.length,total));
 check(()=>assert(changedFrames>0,'ON must execute actual overlay operations'));
 check(()=>assert.equal(primaryPeak,1));
 check(()=>{for(const marker of selected.markers)assert.equal(markerCoverage[marker.id],marker.end_frame-marker.start_frame);});
 check(()=>assert(steadyMarkerFrames>0,'Pins persist after introduction'));
 check(()=>{for(const label of selected.labels)assert((coverage[label.id]||0)>0,`Actually visible text: ${label.id}`);});
 check(()=>{assert(!Object.keys(omissions).some(reason=>reason==='TEXT_TOO_LONG_FOR_SAFE_LAYOUT'));});
 check(()=>{for(const receipt of receipts){assert(!receipt.labels.some(label=>label.role==='TTS_SUBTITLE'));assert.equal(new Set(receipt.labels.map(label=>`${label.role}|${label.text}|${label.target_id}`)).size,receipt.labels.length);}});
 check(()=>{for(const receipt of receipts)for(const label of receipt.labels)if(label.phase==='STEADY'){assert.equal(label.visible_graphemes,label.total_graphemes);assert.equal(label.steady_style,'Constant text-local outline and 3px shadow; no oscillation');}});
 check(()=>{const records=selected.geometries.filter(value=>value.geometry_role==='canal_centerline');for(const record of records){assert.equal(record.geometry_type,'MultiLineString');assert(!on.infographicPrepared.get(record.id).triangles.length);assert.equal(on.infographicPrepared.get(record.id).lines.length,record.coordinates.length);}
  if(selected.geometry_layers){const expected={};for(let frame=0;frame<total;frame++){const latest=new Map();for(const layer of selected.geometry_layers)if(frame>=layer.start_frame&&frame<layer.end_frame)latest.set(layer.geometry_ref,layer);for(const layer of latest.values())expected[layer.id]=(expected[layer.id]||0)+1;}assert.deepEqual(geometryLayerCoverage,expected);for(const layer of selected.geometry_layers){if(layer.end_frame>layer.primary_until_frame)assert((geometryWidthCoverage[layer.geometry_ref+'@2']||0)>0);}}
 });
 check(()=>{for(const receipt of receipts)for(const obstacle of receipt.layout.critical_geometry_obstacles){assert(selected.geometry_ids.includes(obstacle.geometry_id));assert(['Verified critical canal line bounds','Compact verified geometry bounds'].includes(obstacle.policy));}});
 const typography=JSON.parse(buffers['/static/infographic/v022/profile.json']).typography;
 check(()=>{assert.equal(typography.EVENT_TITLE.weight,700);assert.equal(typography.LOCATION_LABEL.weight,400);assert(typography.EVENT_TITLE.size_px>typography.LOCATION_LABEL.size_px&&typography.LOCATION_LABEL.size_px>typography.SUPPORT_DATA.size_px);});
 check(()=>{assert.deepEqual(infographic.infographicGraphemes('가 e\u0301'),['가',' ','e\u0301']);for(let frame=0;frame<17;frame++)assert(!infographic.infographicRevealState('e\u0301',0,17,frame).visible.includes('e'));
  for(const text of ['WWW WWW WWW WWW WWW','AAA\nBBB']){
   const ctx=new RecordingContext();ctx.measureText=value=>({width:[...String(value)].reduce((sum,ch)=>sum+(ch===' '?30:70),0)});
   const layout=infographic.layoutInfographicLabels(ctx,[{id:'WRAPPED',event_id:'WRAPPED',role:'EVENT_TITLE',text,font_size:72,font_weight:700,primary:true,anchor:{x:540,y:500},start_frame:0,reveal_end_frame:17,end_frame:60,intro_mode:'CHARACTER_REVEAL',opacity:1}],{width:1080,height:1920});
   for(let frame=0;frame<17;frame++){ctx.reset();const source=infographic.infographicRevealState(text,0,17,frame);infographic.drawInfographicLabels(ctx,layout,frame);const expected=layout.labels[0].lineGlyphIndices.flat().filter(index=>index<source.visible.length).map(index=>source.graphemes[index]);assert.deepEqual(ctx.commands.filter(command=>command[0]==='fillText').map(command=>command[1]),expected);}
  }
 });
 check(()=>{const ctx=new RecordingContext(),layout=infographic.layoutInfographicLabels(ctx,[{id:'A',event_id:'A',role:'EVENT_TITLE',text:'AUTHORED STATUS',font_size:72,font_weight:700,primary:true,anchor:{x:1080*.5,y:1920*.3},start_frame:0,end_frame:60},{id:'B',event_id:'B',role:'LOCATION_LABEL',text:'AUTHORED PLACE',font_size:58,font_weight:400,primary:false,anchor:{x:1080*.5,y:1920*.3},start_frame:0,end_frame:60}],{width:1080,height:1920});assert(layout.passed);assert.equal(layout.labels.length,2);assert.equal(layout.labels[0].role,'EVENT_TITLE');
  const camera=new THREE.PerspectiveCamera(36,1080/1920,.001,100);camera.position.set(3,0,0);camera.lookAt(0,0,0);camera.updateMatrixWorld(true);
  const point=earth.SceneEarthRenderer.prototype.project.call({camera,w:1080,h:1920},geo(30,0,1.00008));assert(point.visible&&point.x>1080);
  const offscreen=infographic.layoutInfographicLabels(ctx,[{id:'OFFSCREEN',event_id:'OFFSCREEN',role:'LOCATION_LABEL',text:'REAL LOCATION',font_size:58,font_weight:400,anchor:point,start_frame:0}],{width:1080,height:1920});assert.deepEqual(offscreen.omitted,[{id:'OFFSCREEN',reason:'OFFSCREEN'}]);assert.equal(offscreen.labels.length,0);
  const limited=new RecordingContext();limited.measureText=value=>({width:40*[...String(value)].length});const support=infographic.layoutInfographicLabels(limited,[{id:'LIMITED',event_id:'LIMITED',role:'SUPPORT_DATA',text:'1234567890 1234567890',font_size:48,font_weight:400,max_lines:1,anchor:{x:540,y:500},start_frame:0}],{width:1080,height:1920});assert.deepEqual(support.omitted,[{id:'LIMITED',reason:'TEXT_TOO_LONG_FOR_SAFE_LAYOUT'}]);assert.equal(support.labels.length,0);
 });
 check(()=>{const bad=structuredClone(inputScene);bad.infographic.events[0].target_geometry_refs=[bad.infographic.events[0].location_point_ref];assert.throws(()=>infographic.validateInfographicSelection(bad),/POINT_NOT_AN_AREA_OR_LINE/);});
 check(()=>{const bad=structuredClone(selected.geometries.find(value=>value.geometry_type==='Point'));bad.coordinates=[Infinity,0];assert.throws(()=>infographic.validateInfographicGeometry(bad),/COORDINATE_INVALID/);});
 check(()=>{const bad=structuredClone(selected.geometries[0]);bad.source_file_sha256='unknown';assert.throws(()=>infographic.validateInfographicGeometry(bad),/SOURCE_INVALID/);});
 check(()=>{const bad=structuredClone(inputScene);bad.infographic.labels[0].text='INVENTED FACT';assert.throws(()=>infographic.validateInfographicSelection(bad),/TEXT_SOURCE_MISMATCH/);});
 check(()=>{const bad=structuredClone(inputScene);bad.infographic.markers[0].geometry_ref=bad.infographic.geometry_ids.find(id=>selected.geometries.find(g=>g.id===id).geometry_type!=='Point');assert.throws(()=>infographic.validateInfographicSelection(bad),/MARKER_SOURCE_INVALID/);});
 check(()=>{const bad=structuredClone(inputScene);bad.infographic.total_frames++;assert.throws(()=>infographic.validateInfographicSelection(bad),/FRAME_GRID_INVALID/);});
 check(()=>{const bad=structuredClone(JSON.parse(buffers['/static/infographic/v022/profile.json']));bad.typography.EVENT_TITLE.weight=600;assert.throws(()=>infographic.validateInfographicProfile(bad),/UNVERIFIED_FONT_WEIGHT/);});
 check(()=>{const bad=structuredClone(inputScene);const hypothesis=bad.infographic.events.find(event=>event.evidence_type==='hypothetical_scenario');if(hypothesis){hypothesis.watermark=null;assert.throws(()=>infographic.validateInfographicSelection(bad),/WATERMARK_REQUIRED/);}});
 const {frameEvidence}=await import('./scene_diagnostic_journal.mjs');
 check(()=>{const t=selected.events[0].start_frame/fps;on.frame(t);const audit=on.audit(t),captured=frameEvidence({sceneId:inputScene.scene_id,frameIndex:selected.events[0].start_frame,t,audit,errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});assert.deepEqual(captured.infographic,audit.infographic);});
 check(()=>{const ctx=on.ctx,spec=on.sceneSpec,fill=ctx.stroke;ctx.stroke=()=>{throw Error('INJECTED_NATIVE_CANVAS_FAILURE');};try{assert.throws(()=>on.overlay(selected.events[0].start_frame/fps),/INJECTED_NATIVE/);assert.equal(on.ctx,ctx);assert.equal(on.sceneSpec,spec);assert.equal(ctx.stack.length,0);}finally{ctx.stroke=fill;ctx.reset();}});
 const badHash=infographic.createInfographicRenderer({...inputScene,infographic:{...selected,profile_sha256:'0'.repeat(64)}},plan);await assert.rejects(()=>badHash.init(),/RESOURCE_HASH_MISMATCH/);checks++;
 const badURL=infographic.createInfographicRenderer({...inputScene,infographic:{...selected,registry_url:'https://untrusted.example/registry.json'}},plan);await assert.rejects(()=>badURL.init(),/SOURCE_URL_INVALID|RESOURCE_SOURCE_INVALID/);checks++;
 const badRecord=structuredClone(inputScene);badRecord.infographic.geometries[0].source_version+='unverified';const tampered=infographic.createInfographicRenderer(badRecord,plan);await assert.rejects(()=>tampered.init(),/REGISTRY_RECORD_MISMATCH/);checks++;
 const result={passed:true,checks,frames:total,fps,parent_renderer_family:family,camera_trajectory:'UNCHANGED',material:'UNCHANGED',wide:'UNCHANGED',overlay_off:'UNCHANGED',audio:'UNCHANGED',source_scene_immutable:true,parent_overlay_duplicate_labels:'SUPPRESSED_BY_SINGLE_OWNER',primary_motion_effect_peak:primaryPeak,changed_overlay_frames:changedFrames,actual_draw_commands:'EXECUTED',marker_persistent_frames:steadyMarkerFrames,marker_coverage:markerCoverage,geometry_layer_coverage:geometryLayerCoverage,geometry_width_coverage:geometryWidthCoverage,text_coverage:coverage,layout_omissions:omissions,geometry_state_coverage:Object.fromEntries(Object.entries(stateTargets).map(([id,states])=>[id,[...states]])),glyph_metrics:'Recording fixture metrics; actual font pixels tested separately with --canvas-snapshots',font_weight:{event_title:700,location:400,support:400},font_sources:selected.font_sources,additional_texture_uploads:family==='production-earth-v1'?(on.regionalMaterialReceipt?.texture_uploads||0):0,regional_lod:family==='production-earth-v1'?on.regionalMaterialReceipt:null,added_sfx:0,added_routes:0,added_entities:0,GPU:'NOT_RUN',shader_compile:'NVIDIA_NOT_RUN',pixel_quality:'NOT_RUN',request_order_regression:{request_identity:'SAME_URL_MULTISET_AND_COUNTS',completion_order_reversed:family==='story-progression-v021'},scope:'Actual inherited production or v021 frame/overlay/audit, actual native Three camera and shader assembly. Recording Canvas2D observes operations; no NVIDIA pixels.'};
 if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});fs.writeFileSync(path.join(process.argv[3],'native-result.json'),JSON.stringify(result,null,2)+'\n');fs.writeFileSync(path.join(process.argv[3],'frame-receipts.json'),JSON.stringify({frames,receipts},null,2)+'\n');}
 console.log(JSON.stringify(result));
}finally{globalThis.fetch=oldFetch;globalThis.document=oldDocument;}

/** Bounded test-only diagnostics. Never emit browser stderr, command, env,
 * raw exception message, URL, filesystem path or unknown check identifier. */
function safeCanvasFailure(error,phase){
 const message=String(error?.message||''),types=new Set(['Error','TypeError','SyntaxError','ReferenceError','RangeError','TimeoutError','TargetClosedError']);
 const checks=new Set(['COUNTRY_EGY_REGISTRY_PRESENT','COUNTRY_EGY_REAL_POLYGON_VISIBLE','COUNTRY_SGP_REGISTRY_PRESENT','COUNTRY_SGP_REAL_POLYGON_VISIBLE','POLYGON_HOLE_EMPTY_REAL_PIXELS','MULTIPOLYGON_ISLANDS_NO_BRIDGE','ANTIMERIDIAN_FRONT_POLYGON_FILLED','ANTIMERIDIAN_BACKSIDE_NO_FALSE_CHORD','HORIZON_PARTIAL_POLYGON_CLIPPED','HORIZON_BACKSIDE_ENTIRELY_HIDDEN','LINE4PX_ACTUAL_PIXEL_WIDTH','FOUR_ROLES_MEASURED_WITH_ACTUAL_FONTS','LABEL_COLLISION_RESOLVED','CJK_ENGLISH_NUMERIC_REAL_INK','REAL_BOLD_DIFFERS_FROM_REGULAR','GRAPHEME_REVEAL_DOES_NOT_SPLIT_COMBINING']);
 const phases=new Set(['BROWSER_LAUNCH','PAGE_CREATE','PAGE_LOAD','BROWSER_EVALUATION','SNAPSHOT_WRITE','METRICS_WRITE']);
 const known=new Set(['ACTUAL_FONT_LOAD_FAILED','INFOGRAPHIC_GEOMETRY_SOURCE_INVALID','INFOGRAPHIC_GEOMETRY_COORDINATE_INVALID','INFOGRAPHIC_POLYGON_RING_INVALID','INFOGRAPHIC_POLYGON_AREA_INVALID','INFOGRAPHIC_POLYGON_TRIANGULATION_FAILED','INFOGRAPHIC_AMBIGUOUS_ANTIPODAL_LINE','INFOGRAPHIC_GRAPHEME_SEGMENTER_UNAVAILABLE','INFOGRAPHIC_TEXT_SOURCE_INVALID','INFOGRAPHIC_LABEL_ROLE_INVALID','INFOGRAPHIC_UNVERIFIED_FONT_WEIGHT','INFOGRAPHIC_TEXT_LINE_LIMIT_INVALID','INFOGRAPHIC_TEXT_WRAPPING_SOURCE_INVALID']);
 let code='UNCLASSIFIED',check=null,library=null;
 const failed=message.match(/CANVAS_CHECK_FAILED:([A-Z0-9_]+)/);if(failed&&checks.has(failed[1])){code='CHECK_FAILED';check=failed[1];}
 else{const candidate=[...known].find(value=>message.includes(value));if(candidate)code=candidate;
 else if(/Executable doesn't exist|ENOENT|spawn[^\n]*not found/i.test(message))code='EXECUTABLE_MISSING';
 else if(/error while loading shared libraries|cannot open shared object file/i.test(message))code='SHARED_LIBRARY_MISSING';
 else if(/No usable sandbox|SUID sandbox helper|Running as root without --no-sandbox/i.test(message))code='SANDBOX_CONFIGURATION';
 else if(/crashpad[^\n]*--database is required/i.test(message))code='CRASHPAD_DATABASE_REQUIRED';
 else if(/Permission denied|EACCES|Access denied/i.test(message))code='PERMISSION_DENIED';
 else if(error?.name==='TimeoutError')code='TIMEOUT';
 else if(/Target page, context or browser has been closed/i.test(message))code='BROWSER_CLOSED_BEFORE_READY';}
 const shared=message.match(/(?:loading shared libraries:\s*|open shared object file[^\n]*?)([A-Za-z0-9_.+-]+\.so(?:\.[0-9]+)*)/);
 const libraries=new Set(['libX11.so.6','libX11-xcb.so.1','libXcomposite.so.1','libXdamage.so.1','libXext.so.6','libXfixes.so.3','libXrandr.so.2','libXss.so.1','libXtst.so.6','libxcb.so.1','libatk-1.0.so.0','libatk-bridge-2.0.so.0','libatspi.so.0','libasound.so.2','libcairo.so.2','libcups.so.2','libdbus-1.so.3','libdrm.so.2','libexpat.so.1','libfontconfig.so.1','libfreetype.so.6','libgbm.so.1','libglib-2.0.so.0','libgobject-2.0.so.0','libgtk-3.so.0','libnspr4.so','libnss3.so','libnssutil3.so','libpango-1.0.so.0','libpangocairo-1.0.so.0','libsmime3.so','libvulkan.so.1']);
 if(shared&&libraries.has(shared[1]))library=shared[1];
 const signal=message.match(/signal[=:]\s*(SIG[A-Z]+)/)?.[1],signals=new Set(['SIGABRT','SIGTRAP','SIGSEGV','SIGILL','SIGBUS','SIGKILL','SIGTERM']);
 const exit=message.match(/exitCode[=:]\s*(\d+)/)?.[1],locations=[];
 for(const match of String(error?.stack||'').matchAll(/(test_infographic_v022\.mjs|infographic_adapter\.js|reference_effects_adapter\.js|<anonymous>):(\d+):(\d+)/g)){
  const line=Number(match[2]),column=Number(match[3]);if(line>0&&line<100000&&column>0&&column<100000)locations.push({file:match[1]==='<anonymous>'?'browser_evaluation':match[1],line,column});if(locations.length>=8)break;
 }
 return {phase:phases.has(phase)?phase:'UNKNOWN',exception_type:types.has(error?.name)?error.name:'OTHER',code,check,shared_library:library,process_signal:signals.has(signal)?signal:null,process_exit_code:exit!==undefined&&Number(exit)<=255?Number(exit):null,locations,raw_details:'OMITTED',GPU:'NOT_RUN'};
}

async function runCanvasSnapshots(outputPath){
// Deliberately CPU Canvas2D only. This tool is not a GPU renderer or production
// scene renderer. Artificial polygons below are topology test fixtures only.
const repo=path.resolve('..');
const app=path.join(repo,'world-simulation-shorts-engine');
const out=path.resolve(outputPath||'/tmp/world-infographic-v022/canvas-snapshot');
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const {chromium}=require('playwright');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const assets={
 '/three.js':path.join(repo,'cinematic-world-map/node_modules/three/build/three.module.js'),
 '/adapter.js':path.join(app,'web/infographic_adapter.js'),
 '/reference.js':path.join(app,'web/reference_effects_adapter.js'),
 '/registry.json':path.join(app,'web/infographic/v022/registry.json'),
 '/regular.otf':path.join(app,'web/fonts/NotoSansCJKkr-Regular.otf'),
 '/bold.otf':path.join(app,'web/fonts/NotoSansCJKkr-Bold.otf'),
};
await fsPromises.mkdir(out,{recursive:true});
const hashes=Object.fromEntries(await Promise.all(Object.entries(assets).map(async([key,value])=>[key,sha(await fsPromises.readFile(value))])));
const html=`<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:'Noto Cinema';font-style:normal;font-weight:400;src:url('/regular.otf')}
@font-face{font-family:'Noto Cinema';font-style:normal;font-weight:700;src:url('/bold.otf')}
body{margin:0;background:#101a22}canvas{display:block}</style><canvas id="canvas" width="1080" height="1920"></canvas>`;
const server=http.createServer(async(req,res)=>{
 try{if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end(html);return;}
 const file=assets[req.url];if(!file){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',req.url.endsWith('.js')?'text/javascript':req.url.endsWith('.json')?'application/json':'font/otf');
 res.end(await fsPromises.readFile(file));
 }catch{res.writeHead(500);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser,phase='BROWSER_LAUNCH';
try{
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu','--disable-gpu-compositing']});
 phase='PAGE_CREATE';const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 phase='PAGE_LOAD';await page.goto(`http://127.0.0.1:${server.address().port}/`,{waitUntil:'networkidle'});
 phase='BROWSER_EVALUATION';const metrics=await page.evaluate(async()=>{
  const THREE=await import('/three.js');
  const strip=source=>source.replace(/^import .*;\s*$/gm,'').replace(/^export /gm,'');
  const referenceSource=await(await fetch('/reference.js')).text();
  const reference=new Function('THREE','SceneEventQualityRenderer','digestBytes','trustedStaticURL','flatCoordinate','productionUsesRouteHeadAnchor',strip(referenceSource)+'\nreturn {characterRevealState,markerPopState};')(THREE,class{},()=>{throw Error('UNUSED');},()=>{throw Error('UNUSED');},()=>{throw Error('UNUSED');},()=>{throw Error('UNUSED');});
  const source=await(await fetch('/adapter.js')).text();
  const helpers=new Function('THREE','SceneStoryProgressionRenderer','SceneProductionEarthRenderer','createStoryProgressionRenderer','characterRevealState','markerPopState','digestBytes','trustedStaticURL',strip(source)+'\nreturn {prepareInfographicGeometry,projectInfographicGeometry,layoutInfographicLabels,drawInfographicLabels,infographicGraphemes};')(THREE,class{},class{},()=>{throw Error('UNUSED');},reference.characterRevealState,reference.markerPopState,()=>{throw Error('UNUSED');},()=>{throw Error('UNUSED');});
  await document.fonts.load('400 64px "Noto Cinema"','수에즈 운하 CANAL 12');
  await document.fonts.load('700 64px "Noto Cinema"','수에즈 운하 CANAL 12');
  await document.fonts.ready;
  if(!document.fonts.check('400 64px "Noto Cinema"')||!document.fonts.check('700 64px "Noto Cinema"'))throw Error('ACTUAL_FONT_LOAD_FAILED');
  const registry=await(await fetch('/registry.json')).json();
  const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d',{willReadFrequently:true}),width=canvas.width,height=canvas.height;
  const normal=([lon,lat])=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180));
  const camera=(coordinate,distance,fov=36)=>{const value=new THREE.PerspectiveCamera(fov,width/height,.001,100);value.position.copy(normal(coordinate).multiplyScalar(distance));value.lookAt(0,0,0);value.updateMatrixWorld(true);return value;};
  const pixelPoint=(coordinate,value)=>{const p=normal(coordinate).multiplyScalar(1.00008).project(value);return {x:(p.x*.5+.5)*width,y:(.5-p.y*.5)*height};};
  const base={crs:'EPSG:4326',sha256:'0'.repeat(64),source_file_sha256:'1'.repeat(64),source_feature_sha256:'2'.repeat(64),source_id:'EXPLICIT_TEST_FIXTURE',source_feature_id:'TOPOLOGY',source_version:'TEST_ONLY',license:{spdx:'CC0-1.0'},scale:'ARTIFICIAL_TEST_ONLY',provenance:'Artificial topology fixture; not authored story geometry'};
  const fixture=(id,type,coordinates)=>({...base,id,geometry_type:type,coordinates});
  const close=points=>[...points,points[0]],square=(left,bottom,right,top)=>close([[left,bottom],[right,bottom],[right,top],[left,top]]);
  const filled=point=>{const values=ctx.getImageData(Math.round(point.x),Math.round(point.y),1,1).data;return values[3]>0;};
  const finiteProjected=projected=>[...projected.polygons.flat(),...projected.segments.flat()].every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=-.01&&p.x<=width+.01&&p.y>=-.01&&p.y<=height+.01);
  const countInk=()=>{const data=ctx.getImageData(0,0,width,height).data;let count=0,left=width,top=height,right=0,bottom=0;for(let i=0;i<data.length;i+=4)if(data[i+3]>0){count++;const x=(i/4)%width,y=Math.floor(i/4/width);left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}return {pixels:count,bounds:count?{left,top,right,bottom}:null};};
  const draw=(projected,{fill=true,stroke=true,lineWidth=4}={})=>{ctx.clearRect(0,0,width,height);ctx.fillStyle='#79b8cf';ctx.strokeStyle='#f3f1e5';ctx.lineWidth=lineWidth;ctx.lineJoin='round';ctx.lineCap='round';if(fill){ctx.beginPath();for(const polygon of projected.polygons){ctx.moveTo(polygon[0].x,polygon[0].y);for(const p of polygon.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath();}ctx.fill();}if(stroke){ctx.beginPath();for(const segment of projected.segments){ctx.moveTo(segment[0].x,segment[0].y);ctx.lineTo(segment[1].x,segment[1].y);}ctx.stroke();}};
  const snapshots=[],checks=[],check=(name,condition,details={})=>{if(!condition)throw Error(`CANVAS_CHECK_FAILED:${name}:${JSON.stringify(details)}`);checks.push({name,status:'PASS',...details});};
  const capture=name=>snapshots.push({name,png:canvas.toDataURL('image/png')});
  for(const [id,target,distance] of [['COUNTRY_EGY',[30,27],1.42],['COUNTRY_SGP',[103.82,1.35],1.02]]){
   const record=registry.geometries.find(g=>g.id===id);check(`${id}_REGISTRY_PRESENT`,!!record);
   const prepared=helpers.prepareInfographicGeometry(record),projected=helpers.projectInfographicGeometry(prepared,camera(target,distance),width,height);draw(projected);const ink=countInk();
   check(`${id}_REAL_POLYGON_VISIBLE`,projected.visible&&ink.pixels>100&&finiteProjected(projected),{pixels:ink.pixels,triangles:prepared.triangles.length,bounds:projected.bounds,source_geometry_sha256:record.sha256});capture(id);
  }
  const hole=fixture('TEST_HOLE','Polygon',[square(-12,-12,12,12),square(-4,-4,4,4)]),frontCamera=camera([0,0],3);
  let prepared=helpers.prepareInfographicGeometry(hole),projected=helpers.projectInfographicGeometry(prepared,frontCamera,width,height);draw(projected);
  check('POLYGON_HOLE_EMPTY_REAL_PIXELS',!filled(pixelPoint([0,0],frontCamera))&&filled(pixelPoint([8,0],frontCamera)),{ink:countInk(),topology_fixture:true});capture('TEST_POLYGON_HOLE');
  const multi=fixture('TEST_MULTIPOLYGON','MultiPolygon',[[square(-13,-6,-5,6)],[square(5,-6,13,6)]]);
  prepared=helpers.prepareInfographicGeometry(multi);projected=helpers.projectInfographicGeometry(prepared,frontCamera,width,height);draw(projected);
  check('MULTIPOLYGON_ISLANDS_NO_BRIDGE',!filled(pixelPoint([0,0],frontCamera))&&filled(pixelPoint([-9,0],frontCamera))&&filled(pixelPoint([9,0],frontCamera)),{ink:countInk(),topology_fixture:true});capture('TEST_MULTIPOLYGON');
  const seam=fixture('TEST_ANTIMERIDIAN','Polygon',[close([[175,-8],[-175,-8],[-175,8],[175,8]])]),seamCamera=camera([180,0],2);
  prepared=helpers.prepareInfographicGeometry(seam);projected=helpers.projectInfographicGeometry(prepared,seamCamera,width,height);draw(projected);
  check('ANTIMERIDIAN_FRONT_POLYGON_FILLED',filled(pixelPoint([180,0],seamCamera))&&finiteProjected(projected)&&projected.bounds.width<width*.65,{ink:countInk(),bounds:projected.bounds,topology_fixture:true});
  const away=helpers.projectInfographicGeometry(prepared,frontCamera,width,height);
  check('ANTIMERIDIAN_BACKSIDE_NO_FALSE_CHORD',!away.visible&&away.polygons.length===0&&away.segments.length===0,{topology_fixture:true});capture('TEST_ANTIMERIDIAN');
  const horizon=fixture('TEST_HORIZON','Polygon',[square(40,-16,105,16)]),horizonCamera=camera([0,0],3,80);
  prepared=helpers.prepareInfographicGeometry(horizon);projected=helpers.projectInfographicGeometry(prepared,horizonCamera,width,height);draw(projected);
  check('HORIZON_PARTIAL_POLYGON_CLIPPED',projected.visible&&finiteProjected(projected)&&filled(pixelPoint([50,0],horizonCamera)),{ink:countInk(),bounds:projected.bounds,topology_fixture:true});capture('TEST_HORIZON');
  const hidden=fixture('TEST_BEHIND_HORIZON','Polygon',[square(100,-10,120,10)]);
  projected=helpers.projectInfographicGeometry(helpers.prepareInfographicGeometry(hidden),frontCamera,width,height);
  check('HORIZON_BACKSIDE_ENTIRELY_HIDDEN',!projected.visible,{topology_fixture:true});
  const line=fixture('TEST_LINE4PX','LineString',[[-12,0],[12,0]]);
  projected=helpers.projectInfographicGeometry(helpers.prepareInfographicGeometry(line),frontCamera,width,height);draw(projected,{fill:false,lineWidth:4});
  const vertical=[];for(let y=height/2-10;y<=height/2+10;y++){const alpha=ctx.getImageData(width/2,y,1,1).data[3];if(alpha>127)vertical.push(y);}
  check('LINE4PX_ACTUAL_PIXEL_WIDTH',vertical.length===4,{full_coverage_pixels:vertical.length,nominal_px:4,topology_fixture:true});capture('TEST_LINE4PX');
  ctx.clearRect(0,0,width,height);
  const labels=[
   {id:'TEST_EVENT',event_id:'TEST_EVENT',role:'EVENT_TITLE',text:'CANAL CLOSED',font_size:72,font_weight:700,primary:true,anchor:{x:width*.5,y:height*.25}},
   {id:'TEST_LOCATION',event_id:'TEST_LOCATION',role:'LOCATION_LABEL',text:'수에즈 운하 SUEZ',font_size:54,font_weight:400,primary:false,anchor:{x:width*.5,y:height*.25}},
   {id:'TEST_DATA',event_id:'TEST_DATA',role:'SUPPORT_DATA',text:'12 DAYS · 1080 × 1920',font_size:44,font_weight:400,primary:false,anchor:{x:width*.5,y:height*.43}},
   {id:'TEST_TTS_FIXTURE',event_id:'TEST_TTS_FIXTURE',role:'TTS_SUBTITLE',text:'실제 한국어 글꼴과 숫자 123',font_size:48,font_weight:400,primary:false,anchor:{x:width*.5,y:height*.25}},
  ].map(label=>({...label,start_frame:0,reveal_end_frame:17,end_frame:60,opacity:1,intro_mode:'CHARACTER_REVEAL',source_ref:'EXPLICIT_TEST_FIXTURE',semantic_segment_ref:null}));
  const layout=helpers.layoutInfographicLabels(ctx,labels,{width,height}),receipts=helpers.drawInfographicLabels(ctx,layout,30);
  check('FOUR_ROLES_MEASURED_WITH_ACTUAL_FONTS',layout.labels.length===4&&layout.passed&&layout.labels.every(box=>box.ink_metrics.every(m=>m.ascent>0&&m.width>0)&&box.glyph_metric_scope==='Canvas2D actual font metrics'),{layout,receipts});
  check('LABEL_COLLISION_RESOLVED',layout.labels.every((a,i)=>layout.labels.slice(i+1).every(b=>!(a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y))),{event_priority_first:layout.labels[0].role==='EVENT_TITLE'});
  check('CJK_ENGLISH_NUMERIC_REAL_INK',layout.labels.every(box=>{const data=ctx.getImageData(Math.floor(box.x)-5,Math.floor(box.y)-5,Math.ceil(box.width)+10,Math.ceil(box.height)+10).data;return data.some((v,i)=>i%4===3&&v>127);}),{ink:countInk()});
  capture('TEST_REAL_FONT_LABELS');
  const boldComparison={};
  for(const weight of [400,700]){ctx.clearRect(0,0,width,height);ctx.font=`${weight} 72px 'Noto Cinema'`;ctx.fillStyle='#f3f1e5';ctx.fillText('수에즈 CANAL 123',100,220);boldComparison[weight]={ink:countInk(),width:ctx.measureText('수에즈 CANAL 123').width};capture(`TEST_REAL_FONT_WEIGHT_${weight}`);}
  check('REAL_BOLD_DIFFERS_FROM_REGULAR',boldComparison[700].ink.pixels>boldComparison[400].ink.pixels*1.10,{boldComparison});
  check('GRAPHEME_REVEAL_DOES_NOT_SPLIT_COMBINING',helpers.infographicGraphemes('가 e\u0301').length===3);
  return {checks,snapshots,font_face_status:[...document.fonts].map(face=>({family:face.family,weight:face.weight,status:face.status})),boldComparison,execution_scope:'Actual CPU Chromium Canvas2D pixels; not production GPU frames',gpu_result:'NOT_RUN',production_scene:false};
 });
 phase='SNAPSHOT_WRITE';for(const snapshot of metrics.snapshots){const bytes=Buffer.from(snapshot.png.split(',')[1],'base64');await fsPromises.writeFile(path.join(out,`${snapshot.name}.png`),bytes);snapshot.file=`${snapshot.name}.png`;snapshot.sha256=sha(bytes);delete snapshot.png;}
 metrics.source_hashes=hashes;metrics.chromium_version=browser.version();metrics.launch_flags=['--no-sandbox','--disable-gpu','--disable-gpu-compositing'];metrics.total_pass=metrics.checks.length;metrics.fail=0;
 phase='METRICS_WRITE';await fsPromises.writeFile(path.join(out,'metrics.json'),JSON.stringify(metrics,null,2)+'\n');
 assert.equal(metrics.fail,0);console.log(JSON.stringify({status:'PASS',checks:metrics.total_pass,out,gpu_result:'NOT_RUN',snapshots:metrics.snapshots.length}));
}catch(error){
 const failure=safeCanvasFailure(error,phase);console.log(JSON.stringify({passed:false,diagnostic:failure}));
 throw Error('INFOGRAPHIC_CANVAS_'+(failure.check||failure.code));
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}

}
