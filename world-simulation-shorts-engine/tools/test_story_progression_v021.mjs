/** Native camera/material and actual 2D overlay contracts. No GPU pixels. */
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {webcrypto,createHash} from 'node:crypto';

const root=path.resolve('.'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const strip=file=>read(file).replace(/^import .*;$/gm,'').replace(/^export /gm,'');
if(!process.argv[2])throw Error('Provide the explicitly selected v021 plan path');
const plan=JSON.parse(fs.readFileSync(process.argv[2])),inputScene=structuredClone(plan.scenes[0]);
assert.equal(inputScene.reference_effects?.version,'v020');
assert.equal(inputScene.story_progression?.version,'v021');
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
const quality=new Function('THREE','SceneSecondEventRenderer',strip('web/visual_quality_adapter.js')+';return {SceneVisualQualityRenderer,digestBytes,trustedStaticURL};')(mockTHREE,camera.SceneSecondEventRenderer);
const eventQuality=new Function('SceneVisualQualityRenderer','digestBytes','trustedStaticURL',strip('web/event_quality_adapter.js')+';return {SceneEventQualityRenderer};')(quality.SceneVisualQualityRenderer,quality.digestBytes,quality.trustedStaticURL);
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
try{
 const baselineScene=structuredClone(inputScene);delete baselineScene.story_progression;
 delayRegionDecode(0);const baseline=effects.createReferenceEffectsRenderer(baselineScene,plan);await baseline.init();const baseRequests=requests.splice(0);
 delayRegionDecode(1);const off=story.createStoryProgressionRenderer(baselineScene,plan);await off.init();const offRequests=requests.splice(0);
 delayedDecodeHash=null;releaseOnMaskURL=null;
 const on=story.createStoryProgressionRenderer(inputScene,plan);await on.init();const onRequests=requests.splice(0);
 check(()=>assert.equal(off.constructor,effects.SceneReferenceEffectsRenderer));
 check(()=>assertRequestInventory(offRequests,baseRequests));
 check(()=>assertRequestInventory(onRequests.filter(url=>url!=='/static/story_progression_v021.json'),baseRequests));
 check(()=>assert.deepEqual(onRequests.filter(url=>url==='/static/story_progression_v021.json'),['/static/story_progression_v021.json']));
 const maskRequests=urls=>urls.filter(url=>regionalMasks.some(source=>source.url===url));
 const firstMask=regionalMasks.find(source=>source.region_id===regionalDays[0].region_id).url,secondMask=regionalMasks.find(source=>source.region_id===regionalDays[1].region_id).url;
 check(()=>assert.deepEqual(maskRequests(baseRequests),[secondMask,firstMask]));
 check(()=>assert.deepEqual(maskRequests(offRequests),[firstMask,secondMask]));
 check(()=>{assert.notDeepEqual(offRequests,baseRequests);assertRequestInventory(baseRequests,['/static/visual_quality_v018.json',manifestURL,...manifest.textures.map(source=>source.url),'/static/event_quality_v019.json','/static/reference_effects_v020.json']);});
 check(()=>assert.throws(()=>assertRequestInventory([...offRequests,offRequests[0]],baseRequests),assert.AssertionError));
 check(()=>assert.throws(()=>assertRequestInventory(offRequests.slice(1),baseRequests),assert.AssertionError));
 const originalSpec=JSON.stringify(on.sceneSpec),receipts=new Map(),haloFrames=new Map();let changedFrames=0,primaryPeak=0;
 const inputEffects=inputScene.story_progression.microbeats;
 for(let frame=0;frame<720;frame++){
  const t=frame/30;for(const renderer of [baseline,off,on]){renderer.ctx.reset();renderer.actx.reset();renderer.frame(t);}
  const before=baseline.audit(t),inactive=off.audit(t),after=on.audit(t);
  assert.deepEqual(off.ctx.commands,baseline.ctx.commands);assert.deepEqual(off.actx.commands,baseline.actx.commands);assert.deepEqual(inactive,before);
  for(const renderer of [off,on]){
   assert.deepEqual(renderer.camera.position.toArray(),baseline.camera.position.toArray());assert.deepEqual(renderer.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(renderer.camera.fov,baseline.camera.fov);assert.deepEqual(renderer.cam.values(t),baseline.cam.values(t));assert.equal(renderer.map.surface.fragmentShader,baseline.map.surface.fragmentShader);assert.equal(renderer.shaderTime,baseline.shaderTime);
   assert.deepEqual(Object.keys(renderer.map.surface.uniforms),Object.keys(baseline.map.surface.uniforms));
   for(const [name,uniform] of Object.entries(renderer.map.surface.uniforms)){const expected=baseline.map.surface.uniforms[name].value;if(uniform.value?.isTexture){assert.deepEqual(uniform.value.image,expected.image);for(const property of ['colorSpace','wrapS','wrapT','minFilter','magFilter','anisotropy','generateMipmaps'])assert.deepEqual(uniform.value[property],expected[property]);}else assert.deepEqual(uniform.value?.toArray?uniform.value.toArray():uniform.value,expected?.toArray?expected.toArray():expected);}
  }
  assert.deepEqual(on.actx.commands,baseline.actx.commands);assert.deepEqual(after.textClipped,[]);
  assert.equal(after.storyProgression.additional_texture_uploads,0);assert.equal(after.storyProgression.added_sfx,0);assert.equal(after.storyProgression.boundary.status,'NOT_AVAILABLE');
  assert.deepEqual(after.effectLayer.storyProgression,after.storyProgression);assert(after.storyProgression.primary_effect_count<=1);primaryPeak=Math.max(primaryPeak,after.storyProgression.primary_effect_count);
  assert.equal(JSON.stringify(on.sceneSpec),originalSpec);assert.equal(JSON.stringify(inputScene),originalInput);assert.equal(on.ctx.stack.length,0);
  const active=inputEffects.filter(beat=>frame>=beat.start_frame&&frame<beat.end_frame);
  if(!active.length){assert.deepEqual(on.ctx.commands,baseline.ctx.commands);assert.deepEqual(after.labels,before.labels);assert.deepEqual(after.meaningfulEventsRendered,before.meaningfulEventsRendered);assert.equal(after.storyProgression.phase,'NONE');}
  if(JSON.stringify(on.ctx.commands)!==JSON.stringify(baseline.ctx.commands))changedFrames++;
  for(const receipt of after.storyProgression.microbeats){
   const authored=inputEffects.find(beat=>beat.id===receipt.id);assert(authored);assert(frame>=authored.start_frame&&frame<authored.end_frame);
   assert.equal(receipt.story_event_id,authored.story_event_id);assert.equal(receipt.primary_information,authored.primary_information);assert.deepEqual(receipt.source_ref,authored.source_ref);assert.equal(receipt.geometry_ref,null);
   receipts.set(receipt.id,(receipts.get(receipt.id)||0)+1);
   const eventLabel=after.labels.find(label=>label.event_id===receipt.story_event_id);
   if(eventLabel){assert.equal(eventLabel.font,64*on.w/1080);assert.equal(receipt.text_hierarchy.weight,400);}
   const locationLabel=after.labels.find(label=>label.text==='SUEZ CANAL');if(locationLabel&&frame>=180&&frame<360)assert(locationLabel.opacity<=.60+1e-7);
   if(receipt.halo.active){assert(['TEXT_REVEAL_HALO','LOCATION_TEXT_HALO'].includes(receipt.pattern));assert(receipt.halo.glyph_calls>0);assert(receipt.halo.strength>0&&receipt.halo.strength<=1);haloFrames.set(receipt.id,(haloFrames.get(receipt.id)||0)+1);}
   else assert.equal(receipt.halo.glyph_calls,0);
  }
  // Source status replacements and v020 glyph counts remain unchanged. Font
  // and local support are presentation changes, not a text/time rewrite.
  for(const parent of after.effectLayer.events){const expected=before.effectLayer.events.find(value=>value.id===parent.id);assert(expected);for(const field of ['story_event_id','pattern','start_frame','peak_frame','end_frame','displayed_text','visible_chars','total_chars','character_scales'])assert.deepEqual(parent[field],expected[field]);}
 }
 check(()=>assert.equal(JSON.stringify(inputScene),originalInput));
 check(()=>assert.equal(changedFrames,180));
 check(()=>assert.equal(primaryPeak,1));
 check(()=>assert.deepEqual(Object.fromEntries(receipts),Object.fromEntries(inputEffects.map(beat=>[beat.id,beat.end_frame-beat.start_frame]))));
 check(()=>{for(const [id,count] of haloFrames){const beat=inputEffects.find(value=>value.id===id);assert(count<=17);assert(count<beat.end_frame-beat.start_frame);}});
 check(()=>{for(const property of ['background','exposure','cityGain','nightGain','specularGain','regionalBlend']){const actual=on.map.surface.uniforms[property],expected=baseline.map.surface.uniforms[property];assert.deepEqual(actual,expected);}});
 check(()=>{const source=read('web/story_progression_adapter.js');for(const term of ['mapAt(t)','camera.position','camera.fov=','fragmentShader=','ShaderMaterial','TextureLoader','Math.random','drawImage('])assert(!source.includes(term),term);});
 check(()=>assert.throws(()=>story.createStoryProgressionRenderer({...inputScene,story_progression:{...inputScene.story_progression,version:'v999'}},plan),/EXPLICIT_V021/));
 check(()=>assert.throws(()=>story.validateStoryProgressionProfile({...storyProfile,limits:{...storyProfile.limits,max_primary:2}}),/LIMITS_INVALID/));
 check(()=>assert.throws(()=>story.validateStoryProgressionProfile({...storyProfile,added_sfx:'invented'}),/PROFILE_CONTRACT_INVALID/));
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats[0].primary_information='INVENTED EVENT';assert.throws(()=>story.validateStoryProgressionSelection(bad),/UNSUPPORTED_STORY_EVENT/);});
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats[0].geometry_ref={fake_line:[[0,0],[1,1]]};assert.throws(()=>story.validateStoryProgressionSelection(bad),/FAKE_GEOMETRY/);});
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats[0].end_frame+=1;assert.throws(()=>story.validateStoryProgressionSelection(bad),/CONTINUOUS_EFFECT/);});
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats[0].camera_lock_ref.start_frame=181;assert.throws(()=>story.validateStoryProgressionSelection(bad),/CAMERA_CHANGED/);});
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats[1].start_frame++;assert.throws(()=>story.validateStoryProgressionSelection(bad),/MICRO_BEAT_ORDER_INVALID/);});
 check(()=>{const bad=structuredClone(inputScene);bad.story_progression.microbeats.find(value=>value.pattern==='LOCATION_TEXT_HALO').start_frame=180;assert.throws(()=>story.validateStoryProgressionSelection(bad),/CONTINUOUS_EFFECT|TOO_MANY_PRIMARY/);});
 const {frameEvidence}=await import('./scene_diagnostic_journal.mjs');
 check(()=>{on.frame(222/30);const audit=on.audit(222/30),captured=frameEvidence({sceneId:'S001',frameIndex:222,t:222/30,audit,errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});assert.deepEqual(captured.effectLayer.storyProgression,audit.storyProgression);assert.equal(captured.effectLayer.storyProgression.version,'v021');});
 // Presentation and context references are restored even when the inherited
 // Canvas2D draw throws; original methods are never replaced.
 check(()=>{const ctx=on.ctx,spec=on.sceneSpec,fill=ctx.fillText;ctx.fillText=()=>{throw Error('INJECTED_NATIVE_CANVAS_FAILURE');};try{assert.throws(()=>on.overlay(222/30),/INJECTED_NATIVE/);assert.equal(on.ctx,ctx);assert.equal(on.sceneSpec,spec);}finally{ctx.fillText=fill;while(ctx.stack.length)ctx.restore();ctx.reset();}});
 const tampered=story.createStoryProgressionRenderer({...inputScene,story_progression:{...inputScene.story_progression,profile_sha256:'0'.repeat(64)}},plan);await assert.rejects(()=>tampered.init(),/SOURCE_HASH_MISMATCH/);checks++;
 const external=story.createStoryProgressionRenderer({...inputScene,story_progression:{...inputScene.story_progression,profile_url:'https://untrusted.example/profile.json'}},plan);await assert.rejects(()=>external.init(),/SOURCE_URL_INVALID/);checks++;
 // Semantic bindings do not depend on these source event IDs or time 6/11.
 // Shift the status timeline by 3 frames inside the same authored camera lock.
 const generic=structuredClone(inputScene),rename=new Map([['E002','AUTHORED_STATUS_A'],['E003','AUTHORED_STATUS_B']]);
 for(const event of generic.visual_events){if(rename.has(event.id)){event.id=rename.get(event.id);event.time+=.1;}if(rename.has(event.caused_by))event.caused_by=rename.get(event.caused_by);}
 for(const text of generic.text_events){if(rename.has(text.event_id)){text.event_id=rename.get(text.event_id);text.start_time+=.1;}}
 for(const event of generic.reference_effects.events){if(rename.has(event.story_event_id)){event.story_event_id=rename.get(event.story_event_id);if(event.label_event_id&&rename.has(event.label_event_id))event.label_event_id=rename.get(event.label_event_id);event.start_frame+=3;event.peak_frame+=3;event.end_frame+=3;}}
 for(const beat of generic.story_progression.microbeats){beat.story_event_id=rename.get(beat.story_event_id)||beat.story_event_id;beat.caused_by=rename.get(beat.caused_by)||beat.caused_by;beat.start_frame+=3;if(beat.phase!=='EVENT_STATE'&&!(beat.phase==='PERCEPTION'&&beat.end_frame===360))beat.end_frame+=3;}
 check(()=>assert.equal(story.validateStoryProgressionSelection(generic).fps,30));
 // A distinct authored fixture consumes the already verified Singapore source
 // coordinate. These fixture messages never enter the approved Suez project.
 const port=structuredClone(generic),portCoordinate=structuredClone(inputScene.visual_events.find(event=>event.id==='E004').coordinates);
 const fixtureMessages=new Map([['AUTHORED_STATUS_A','PORT CLOSED'],['AUTHORED_STATUS_B','PORT OPEN']]);
 for(const event of port.visual_events)if(fixtureMessages.has(event.id)){event.target_id=portCoordinate.location_id;event.coordinates=structuredClone(portCoordinate);event.text=fixtureMessages.get(event.id);}
 for(const text of port.text_events)if(fixtureMessages.has(text.event_id)){text.coordinates=structuredClone(portCoordinate);text.text=fixtureMessages.get(text.event_id);}
 port.labels[0]={...port.labels[0],text:'SINGAPORE',coordinates:structuredClone(portCoordinate)};
 for(const beat of port.story_progression.microbeats){beat.coordinates=structuredClone(portCoordinate);beat.target_id=portCoordinate.location_id;beat.primary_information=fixtureMessages.get(beat.story_event_id);}
 check(()=>assert.equal(story.validateStoryProgressionSelection(port).total,720));
 const genericLock=structuredClone(port);delete genericLock.second_event_camera;
 genericLock.camera_end=structuredClone(genericLock.camera_start);genericLock.direction={locked_windows:[{start_frame:150,end_frame:360,camera_key:'camera_start'}]};
 for(const beat of genericLock.story_progression.microbeats)beat.camera_lock_ref={start_frame:150,end_frame:360,camera_key:'camera_start',source_paths:['direction.locked_windows[0]']};
 check(()=>assert.equal(story.validateStoryProgressionSelection(genericLock).total,720));
 check(()=>{const bad=structuredClone(genericLock);bad.camera_end.lon+=1;assert.throws(()=>story.validateStoryProgressionSelection(bad),/CAMERA_CHANGED/);});
 console.log(JSON.stringify({passed:true,checks,frames:720,camera_trajectory:'UNCHANGED',material:'UNCHANGED',wide:'UNCHANGED',overlay_off:'UNCHANGED',audio:'UNCHANGED',source_scene_immutable:true,boundary_draw:'NONE',additional_texture_uploads:0,added_sfx:0,primary_effect_peak:primaryPeak,changed_overlay_frames:changedFrames,microbeat_receipt_coverage:Object.fromEntries(receipts),halo_frames:Object.fromEntries(haloFrames),generic_contract_fixtures:{shifted_authored_status:true,non_suez_authored_port:true,identical_pose_lock:true,forged_lock_rejected:true},request_order_regression:{completion_order_reversed:true,request_identity:'SAME_URL_MULTISET_AND_COUNTS',baseline_masks:maskRequests(baseRequests),off_masks:maskRequests(offRequests)},GPU:'NOT_RUN',shader_compile:'NVIDIA_NOT_RUN',pixel_quality:'NOT_RUN',scope:'Actual inherited frame/overlay/audit methods with native camera and real shader assembly; recording Canvas2D uses fixture font metrics, not NVIDIA GPU raster pixels; generic source-binding cases are validator contracts.'}));
}finally{globalThis.fetch=oldFetch;}
