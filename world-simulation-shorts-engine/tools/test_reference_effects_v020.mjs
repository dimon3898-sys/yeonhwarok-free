/** Native camera/material and actual 2D overlay contracts. No GPU pixels. */
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {webcrypto,createHash} from 'node:crypto';

const root=path.resolve('.'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const strip=file=>read(file).replace(/^import .*;$/gm,'').replace(/^export /gm,'');
if(!process.argv[2])throw Error('Provide the explicitly selected v020 plan path');
const plan=JSON.parse(fs.readFileSync(process.argv[2])),inputScene=structuredClone(plan.scenes[0]);
assert.equal(inputScene.reference_effects?.version,'v020');
const originalInput=JSON.stringify(inputScene),THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const flat=new Function('THREE',strip('web/flat_semantics.js')+';return {flatClamp,flatNumber,flatSmooth,flatCameraEase,flatWindow,flatCoordinate};')(THREE);
const geo=(lon,lat,radius=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(radius);
const earth=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',strip('web/earth_adapter.js')+';return {SceneEarthRenderer};')(THREE,class{},class{},()=>null,geo,flat.flatClamp,flat.flatSmooth);
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
  this.routes={routes:[],byId:()=>null};this.graphics={items:[]};this.entities={items:[],update:()=>{}};
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
const mockTHREE={...THREE,TextureLoader:class{async loadAsync(url){assert(url.startsWith('data:image/png;base64,'));const bytes=Buffer.from(url.split(',')[1],'base64');assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');const value=new THREE.Texture();value.image={width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)};return value;}}};
const quality=new Function('THREE','SceneSecondEventRenderer',strip('web/visual_quality_adapter.js')+';return {SceneVisualQualityRenderer,digestBytes,trustedStaticURL};')(mockTHREE,camera.SceneSecondEventRenderer);
const eventQuality=new Function('SceneVisualQualityRenderer','digestBytes','trustedStaticURL',strip('web/event_quality_adapter.js')+';return {SceneEventQualityRenderer};')(quality.SceneVisualQualityRenderer,quality.digestBytes,quality.trustedStaticURL);
const effects=new Function('THREE','SceneEventQualityRenderer','digestBytes','trustedStaticURL','flatCoordinate','productionUsesRouteHeadAnchor',strip('web/reference_effects_adapter.js')+';return {createReferenceEffectsRenderer,SceneReferenceEffectsRenderer,validateReferenceEffectsEvents,validateReferenceEffectsProfile,characterRevealState,markerPopState};')(THREE,eventQuality.SceneEventQualityRenderer,quality.digestBytes,quality.trustedStaticURL,flat.flatCoordinate,production.productionUsesRouteHeadAnchor);

globalThis.location={origin:'http://localhost'};if(!globalThis.crypto)globalThis.crypto=webcrypto;
const buffers=Object.fromEntries(['visual_quality_v018.json','event_quality_v019.json','reference_effects_v020.json'].map(name=>['/static/'+name,fs.readFileSync(path.join(root,'web',name))]));
const manifestURL=JSON.parse(buffers['/static/visual_quality_v018.json']).regional_detail.manifest_url;
buffers[manifestURL]=fs.readFileSync(path.join(root,'web/earth-detail/v018/manifest.json'));
const profile=effects.validateReferenceEffectsProfile(JSON.parse(buffers['/static/reference_effects_v020.json']));
const oldFetch=globalThis.fetch,requests=[];
globalThis.fetch=async url=>{requests.push(url);const bytes=buffers[url]||assets[url];assert(bytes,'Only deployed verified resources may be fetched');return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};};
let checks=0;const check=operation=>{operation();checks++;};
try{
 const baselineScene=structuredClone(inputScene);delete baselineScene.reference_effects;
 const baseline=new eventQuality.SceneEventQualityRenderer(baselineScene,plan);await baseline.init();const baseRequests=requests.splice(0);
 const off=effects.createReferenceEffectsRenderer(baselineScene,plan);await off.init();const offRequests=requests.splice(0);
 const on=effects.createReferenceEffectsRenderer(inputScene,plan);await on.init();const onRequests=requests.splice(0);
 check(()=>assert.equal(off.constructor,eventQuality.SceneEventQualityRenderer));
 check(()=>assert.deepEqual(offRequests,baseRequests));
 check(()=>assert.deepEqual(onRequests.filter(url=>url!=='/static/reference_effects_v020.json'),baseRequests));
 check(()=>assert.deepEqual(onRequests.filter(url=>url==='/static/reference_effects_v020.json'),['/static/reference_effects_v020.json']));
 const receipts=new Map(),textCounts=new Map(),markerScales=new Map();let changedFrames=0;
 for(let frame=0;frame<720;frame++){
  const t=frame/30;for(const renderer of [baseline,off,on]){renderer.ctx.reset();renderer.actx.reset();renderer.frame(t);}
  const before=baseline.audit(t),inactive=off.audit(t),after=on.audit(t);
  assert.deepEqual(off.ctx.commands,baseline.ctx.commands);assert.deepEqual(off.actx.commands,baseline.actx.commands);assert.deepEqual(inactive,before);
  for(const renderer of [off,on]){
   assert.deepEqual(renderer.camera.position.toArray(),baseline.camera.position.toArray());assert.deepEqual(renderer.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(renderer.camera.fov,baseline.camera.fov);assert.deepEqual(renderer.cam.values(t),baseline.cam.values(t));assert.equal(renderer.map.surface.fragmentShader,baseline.map.surface.fragmentShader);assert.equal(renderer.shaderTime,baseline.shaderTime);
   assert.deepEqual(Object.keys(renderer.map.surface.uniforms),Object.keys(baseline.map.surface.uniforms));
   for(const [name,uniform] of Object.entries(renderer.map.surface.uniforms)){const expected=baseline.map.surface.uniforms[name].value;if(uniform.value?.isTexture){assert.deepEqual(uniform.value.image,expected.image);for(const property of ['colorSpace','wrapS','wrapT','minFilter','magFilter','anisotropy','generateMipmaps'])assert.deepEqual(uniform.value[property],expected[property]);}else assert.deepEqual(uniform.value?.toArray?uniform.value.toArray():uniform.value,expected?.toArray?expected.toArray():expected);}
  }
  assert.deepEqual(on.actx.commands,baseline.actx.commands);
  assert.equal(after.effectLayer.events.filter(receipt=>receipt.primary).length<=1,true);
  assert.deepEqual(after.textClipped,[]);
  assert.equal(after.effectLayer.additional_texture_uploads,0);
  const reveal=inputScene.reference_effects.events.some(e=>e.pattern==='TEXT_CHARACTER_REVEAL'&&frame>=e.start_frame&&frame<e.peak_frame);
  const marker=inputScene.reference_effects.events.some(e=>e.pattern==='MARKER_POP'&&frame>=e.start_frame&&frame<e.end_frame);
  if(!reveal&&!marker){assert.deepEqual(on.ctx.commands,baseline.ctx.commands);assert.deepEqual(after.labels,before.labels);assert.deepEqual(after.meaningfulEventsRendered,before.meaningfulEventsRendered);}
  if(JSON.stringify(on.ctx.commands)!==JSON.stringify(baseline.ctx.commands))changedFrames++;
  for(const receipt of after.effectLayer.events){
   const authored=inputScene.reference_effects.events.find(e=>e.id===receipt.id);assert(authored);assert(frame>=authored.start_frame&&frame<authored.end_frame);assert.equal(receipt.story_event_id,authored.story_event_id);
   if(receipt.visible){assert(receipt.pixel_bounds);for(const value of Object.values(receipt.pixel_bounds))assert(Number.isFinite(value));assert(receipt.pixel_bounds.width>0&&receipt.pixel_bounds.height>0);receipts.set(receipt.id,(receipts.get(receipt.id)||0)+1);}
   if(receipt.pattern==='TEXT_CHARACTER_REVEAL'){
    assert.equal(receipt.displayed_text,[...authored.text].slice(0,receipt.visible_chars).join(''));assert(receipt.visible_chars<=receipt.total_chars);assert(receipt.character_scales.every(scale=>scale>=.12&&scale<=1));
    const prior=textCounts.get(receipt.id)||0;assert(receipt.visible_chars>=prior);textCounts.set(receipt.id,receipt.visible_chars);
    const label=after.labels.find(l=>l.event_id===authored.story_event_id),original=before.labels.find(l=>l.event_id===authored.story_event_id);
    assert(label&&original);for(const field of ['text','x','y','width','height','font'])assert.deepEqual(label[field],original[field]);
   }
   if(receipt.pattern==='MARKER_POP'){assert(receipt.scale>=.12&&receipt.scale<=1);if(frame>=authored.start_frame+9)assert.equal(receipt.scale,1);const list=markerScales.get(receipt.id)||[];list.push({frame,scale:receipt.scale});markerScales.set(receipt.id,list);}
  }
 }
 check(()=>assert(changedFrames>0&&changedFrames<=109));
 check(()=>{for(const authored of inputScene.reference_effects.events.filter(e=>e.pattern!=='NONE'))assert((receipts.get(authored.id)||0)>0,authored.id+' must produce measured visible receipts');});
 check(()=>assert.equal(JSON.stringify(inputScene),originalInput));
 check(()=>assert.deepEqual(on.sceneSpec.sound_events,baseline.sceneSpec.sound_events));
 check(()=>{const plain=structuredClone(on.sceneSpec);delete plain.reference_effects;assert.deepEqual(plain,baseline.sceneSpec);});
 check(()=>{for(let i=0;i<2;i++)for(const key of ['day','mask']){const actual=on.qualityTiles[i][key],expected=baseline.qualityTiles[i][key];for(const property of ['image','minFilter','magFilter','colorSpace','anisotropy','generateMipmaps'])assert.deepEqual(actual[property],expected[property]);}});
 check(()=>{const source=read('web/reference_effects_adapter.js');for(const term of ['mapAt(t)','camera.position','camera.fov=','fragmentShader=','ShaderMaterial','TextureLoader','Math.random','drawImage('])assert(!source.includes(term),term);});
 check(()=>assert.throws(()=>effects.createReferenceEffectsRenderer({...baselineScene,reference_effects:{version:'v999'}},plan),/EXPLICIT_V020/));
 check(()=>assert.throws(()=>effects.validateReferenceEffectsEvents([...inputScene.reference_effects.events,inputScene.reference_effects.events[0]]),/EVENT_INVALID/));
 check(()=>assert.throws(()=>effects.validateReferenceEffectsEvents(inputScene.reference_effects.events.map((e,i)=>i===0?{...e,pattern:'PULSE'}:e)),/EVENT_INVALID/));
 check(()=>assert.throws(()=>effects.validateReferenceEffectsProfile({...profile,limits:{...profile.limits,max_primary:2}}),/LIMITS_INVALID/));
 check(()=>{
  const marker=inputScene.reference_effects.events.find(e=>e.pattern==='MARKER_POP');
  const other={...marker,id:'FX_DENSITY_TEST'};
  assert.throws(()=>effects.validateReferenceEffectsEvents([...inputScene.reference_effects.events,other]),/PRIMARY_DENSITY_INVALID/);
  assert.equal(effects.markerPopState(marker,marker.start_frame+4,profile).scale,.95);
  assert.equal(effects.markerPopState(marker,marker.start_frame+6,profile).scale,.85);
  assert.equal(effects.markerPopState(marker,marker.start_frame+9,profile).scale,1);
 });
 const {frameEvidence}=await import('./scene_diagnostic_journal.mjs');
 check(()=>{on.frame(181/30);const audit=on.audit(181/30),captured=frameEvidence({sceneId:'S001',frameIndex:181,t:181/30,audit,errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});assert.deepEqual(captured.effectLayer,audit.effectLayer);assert.equal(captured.effectLayer.version,'v020');});
 const tampered=effects.createReferenceEffectsRenderer({...inputScene,reference_effects:{...inputScene.reference_effects,profile_sha256:'0'.repeat(64)}},plan);await assert.rejects(()=>tampered.init(),/SOURCE_HASH_MISMATCH/);checks++;
 const external=effects.createReferenceEffectsRenderer({...inputScene,reference_effects:{...inputScene.reference_effects,profile_url:'https://untrusted.example/profile.json'}},plan);await assert.rejects(()=>external.init(),/SOURCE_URL_INVALID/);checks++;
 console.log(JSON.stringify({passed:true,checks,frames:720,camera_trajectory:'UNCHANGED',material:'UNCHANGED',wide:'UNCHANGED',overlay_off:'UNCHANGED',sfx:'UNCHANGED',additional_texture_uploads:0,changed_overlay_frames:changedFrames,receipt_coverage:Object.fromEntries(receipts),marker_scales:Object.fromEntries(markerScales),GPU:'NOT_RUN',shader_compile:'NVIDIA_NOT_RUN',pixel_quality:'NOT_RUN',scope:'Actual inherited frame/overlay/audit methods with native camera and real shader assembly; recording Canvas2D uses fixture font metrics, not GPU raster pixels.'}));
}finally{globalThis.fetch=oldFetch;}
