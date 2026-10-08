/** CPU-side contract and native camera tests. Never a substitute GPU renderer. */
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {webcrypto,createHash} from 'node:crypto';
const root=path.resolve('.'),THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const read=file=>fs.readFileSync(path.join(root,file),'utf8');
const strip=file=>read(file).replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const defaultPlan=path.join(root,'../deliverables/WORLD_SIMULATION_ENGINE/SECOND_EVENT_CAMERA_v017/SCENE_PLAN.json');
const plan=JSON.parse(fs.readFileSync(process.argv[2]||defaultPlan)),scene=structuredClone(plan.scenes[0]);
const profile=JSON.parse(read('data/visual_quality_v018.json'));
const counters={passed:0};
function check(name,operation){operation();counters.passed++;}
const baseSource=fs.readFileSync(path.join(root,'../cinematic-world-map/src/renderer_v3.js'),'utf8');
const shaderMatch=baseSource.match(/const surfaceFragment=`([\s\S]*?)`;/);assert(shaderMatch);
let surface=shaderMatch[1];
surface=surface.replace('uniform float uTime;','uniform float uTime,uReadability,uExposure,uCityGain;').replace('vec3 lights=vec3(1.,.46,.15)*city*dark*focus*.80;','vec3 lights=vec3(1.,.46,.15)*city*dark*focus*.80*uCityGain;').replace('gl_FragColor=vec4(diffuse+vec3(1.,.90,.74)*spec+lights,1.);','vec3 readable=day*vec3(.78,.87,.97)*uReadability;gl_FragColor=vec4((diffuse+readable+vec3(1.,.90,.74)*spec+lights)*uExposure,1.);');
// The actual optional v004 surface installer supplies the final shader contract.
const polish=new Function('THREE','SceneEarthRenderer','incomingGeographicTransition','FlatSceneCore','flatCoordinate','polishFlatLabels','avoidCityLabelObstacles','flatPolishProjectedAircraftObstacles',strip('web/earth_polish_adapter.js')+';return {SceneEarthPolishRenderer};')(THREE,class{},()=>null,class{},()=>null,()=>null,()=>null,()=>null);
const contractFixture={map:{surface:{fragmentShader:surface,uniforms:{}}},geographicHandoff:null};
polish.SceneEarthPolishRenderer.prototype.installPolishSurface.call(contractFixture);surface=contractFixture.map.surface.fragmentShader;
const old=new Function('THREE','SceneProductionEarthRenderer',strip('web/single_event_camera.js')+';return {singleCameraValues,installSingleCamera};')(THREE,class{});
const previous=new Function('singleCameraValues','installSingleCamera','SceneSingleEventRenderer',strip('web/return_wide_camera.js')+';return {returnCameraValues,installReturnCamera};')(old.singleCameraValues,old.installSingleCamera,class{});
const manifest=JSON.parse(read('web/earth-detail/v018/manifest.json'));
const assets=Object.fromEntries(manifest.textures.map(source=>[source.url,fs.readFileSync(path.join(root,source.file))]));
class ParentFixture{
 constructor(spec,plan){
  this.scene=new THREE.Scene();this.sceneSpec=structuredClone(spec);this.plan=plan;this.w=2160;this.h=3840;
  this.camera=new THREE.PerspectiveCamera(64,9/16,.02,30);this.cam={scene:this.sceneSpec,camera:this.camera};
  const makeTexture=(width,height)=>{const texture=new THREE.Texture();texture.image={width,height};return texture;};
  this.map={surface:{fragmentShader:surface,uniforms:Object.fromEntries(['uDay','uNight','uCloud','uTopo'].map(name=>[name,{value:makeTexture(name==='uTopo'?2048:8192,name==='uTopo'?1024:4096)}]))}};
  this.gl={capabilities:{maxTextureSize:8192,getMaxAnisotropy:()=>8},properties:{get:()=>({__webglTexture:{}})}};
 }
 async init(){previous.installReturnCamera(this.cam);this.frame(0);return this;}
 mapAt(t){this.shaderTime=t;}
 frame(t){this.cam.update(t);this.mapAt(t);return null;}
 audit(t){return {t,cameraPosition:this.camera.position.toArray(),cameraQuaternion:this.camera.quaternion.toArray(),cameraFov:this.camera.fov};}
}
const cameraModule=new Function('THREE','returnCameraValues','installReturnCamera','SceneReturnWideRenderer',strip('web/second_event_camera.js')+';return {installSecondCamera,SceneSecondEventRenderer};')(THREE,previous.returnCameraValues,previous.installReturnCamera,ParentFixture);
const mockTHREE={...THREE,TextureLoader:class{async loadAsync(url){
 assert(url.startsWith('data:image/png;base64,'),'Unchanged CSP prohibits blob image URLs');
 const bytes=Buffer.from(url.split(',')[1],'base64');
 assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 const texture=new THREE.Texture();texture.image={width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)};return texture;
}}};
const quality=new Function('THREE','SceneSecondEventRenderer',strip('web/visual_quality_adapter.js')+';return {qualityWeight,validateQualityProfile,trustedStaticURL,validateDetailManifest,digestBytes,configureQualityTexture,qualitySurfaceShader,SceneVisualQualityRenderer};')(mockTHREE,cameraModule.SceneSecondEventRenderer);
globalThis.location={origin:'http://localhost'};
if(!globalThis.crypto)globalThis.crypto=webcrypto;
check('profile accepted',()=>assert.equal(quality.validateQualityProfile(profile),profile));
check('legacy not selected',()=>{const legacy=structuredClone(scene);delete legacy.visual_quality;assert.throws(()=>new quality.SceneVisualQualityRenderer(legacy,plan),/EXPLICIT_V018_OPT_IN/);});
check('nonstatic URL rejected',()=>assert.throws(()=>quality.trustedStaticURL('https://example.com/map.png'),/SOURCE_URL_INVALID/));
check('traversal URL rejected',()=>assert.throws(()=>quality.trustedStaticURL('/static/../secret'),/SOURCE_URL_INVALID/));
check('query URL rejected',()=>assert.throws(()=>quality.trustedStaticURL('/static/earth-detail/v018/a.png?token=hidden'),/SOURCE_URL_INVALID/));
check('unsafe profile rejected',()=>assert.throws(()=>quality.validateQualityProfile({...profile,regional_detail:{...profile.regional_detail,max_blend:1}}),/REGIONAL_PROFILE_INVALID/));
check('mask required',()=>{const bad=structuredClone(manifest);bad.textures[1].sha256=undefined;assert.throws(()=>quality.validateDetailManifest(bad),/DETAIL_SOURCE_INVALID/);});
check('geographic bounds required',()=>{const bad=structuredClone(manifest);bad.textures[0].bounds=[44,18,20,42];assert.throws(()=>quality.validateDetailManifest(bad),/DETAIL_SOURCE_INVALID/);});
check('real source resolution required',()=>{const bad=structuredClone(manifest);bad.textures[0].source_resolution=[8192,4096];assert.throws(()=>quality.validateDetailManifest(bad),/DETAIL_SOURCE_INVALID/);});
check('manifest accepted',()=>assert.equal(quality.validateDetailManifest(manifest).textures.length,2));
check('wide exact zero',()=>assert.equal(quality.qualityWeight(2.5,profile),0));
check('adaptive wide exact zero',()=>assert.equal(quality.qualityWeight(scene.second_event_camera.adaptive_camera.height,profile),0));
check('close exact one',()=>assert.equal(quality.qualityWeight(.2,profile),1));
check('blend monotone continuous',()=>{let previous=1;for(let i=0;i<=1000;i++){const weight=quality.qualityWeight(.28+i*.47/1000,profile);assert(weight>=0&&weight<=1);assert(weight<=previous+1e-12);assert(previous-weight<.002);previous=weight;}});
const texture=new THREE.Texture();texture.image={width:1440,height:1440};
check('capability clamp',()=>{quality.configureQualityTexture(texture,{maxTextureSize:8192,getMaxAnisotropy:()=>8},16,true);assert.equal(texture.anisotropy,8);assert.equal(texture.minFilter,THREE.LinearMipmapLinearFilter);assert.equal(texture.magFilter,THREE.LinearFilter);assert.equal(texture.generateMipmaps,true);assert.equal(texture.colorSpace,THREE.SRGBColorSpace);});
check('mask data colorspace',()=>{quality.configureQualityTexture(texture,{maxTextureSize:8192,getMaxAnisotropy:()=>8},16,false);assert.equal(texture.colorSpace,THREE.NoColorSpace);});
check('upload resize prohibited',()=>assert.throws(()=>quality.configureQualityTexture(texture,{maxTextureSize:1024,getMaxAnisotropy:()=>8},16,true),/TEXTURE_UPLOAD_SIZE_INVALID/));
const patched=quality.qualitySurfaceShader(surface,2);
check('all shader contracts patched',()=>{assert(patched.includes('day=vqRegional.rgb;'));assert(patched.includes('float land=vqRegional.a;'));assert(patched.includes('mix(.82,uVQCityPower,uVQWeight)'));assert(patched.includes('*spec*uVQSpecularScale+lights'));assert(patched.includes('*uExposure*mix(1.,uVQExposureScale,smoothstep(-.05,.15,nd))'));});
check('night geography exposure retained',()=>{const nd=-.2,daylight=0,weight=quality.qualityWeight(.2,profile);assert.equal(1+(profile.surface.close_exposure_scale-1)*weight*daylight,1);assert(patched.includes('smoothstep(-.05,.15,nd)'));});
check('wide no regional samples',()=>assert(patched.includes('if(uVQWeight<=0.)return vec4(day,land);')));
check('normal/relief source retained',()=>{assert(patched.includes('texture2D(uTopo,uv+vec2(1./2048.,0))'));assert(!patched.includes('normal=texture2D(uVQDetail'));});
check('night not replaced',()=>{assert(patched.includes('vec3 night=texture2D(uNight,uv).rgb'));assert(!patched.includes('sampler2D uVQNight'));});
check('no fake sharpening',()=>{assert(!patched.includes('atlasNeighbor'));assert(!patched.includes('source-neighbor'));});
check('contract change fails closed',()=>assert.throws(()=>quality.qualitySurfaceShader(surface.replace('city=pow(max(city-.001,0.),.82);','city=0.;'),2),/SHADER_CONTRACT_CITY_POWER/));
check('duplicate shader marker fails closed',()=>assert.throws(()=>quality.qualitySurfaceShader(surface+'void main(){}',2),/SHADER_CONTRACT_MAIN/));
check('sampler array size bounded',()=>assert.throws(()=>quality.qualitySurfaceShader(surface,5),/SHADER_TILE_COUNT_INVALID/));
const profileBytes=fs.readFileSync(path.join(root,'web/visual_quality_v018.json')),
 manifestBytes=fs.readFileSync(path.join(root,'web/earth-detail/v018/manifest.json'));
const originalFetch=globalThis.fetch;
globalThis.fetch=async url=>{
 const bytes=url==='/static/visual_quality_v018.json'?profileBytes:url===profile.regional_detail.manifest_url?manifestBytes:assets[url];
 assert(bytes,'Every requested source must be a real deployed asset');
 return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};
};
scene.visual_quality={version:'v018',profile_sha256:createHash('sha256').update(profileBytes).digest('hex'),manifest_sha256:createHash('sha256').update(manifestBytes).digest('hex')};
const renderer=new quality.SceneVisualQualityRenderer(scene,plan),baseline=new cameraModule.SceneSecondEventRenderer(scene,plan);
await baseline.init();await renderer.init();
check('initialization guarded',()=>assert.equal(renderer.qualityReady,true));
check('original render resolution retained',()=>assert.deepEqual([renderer.w,renderer.h],[2160,3840]));
check('cloud/atmosphere absent from overrides',()=>{const src=read('web/visual_quality_adapter.js');assert(!src.includes('postMat.fragmentShader='));assert(!src.includes('cloudMat.fragmentShader='));assert(!src.includes('camera.position.copy'));assert(!src.includes('camera.fov='));});
check('base textures retained',()=>assert.equal(renderer.map.surface.uniforms.uDay.value.image.width,8192));
check('materials explicit bounds',()=>assert.equal(renderer.map.surface.uniforms.uVQMaxBlend.value,.65));
const frames=[];
for(let frame=0;frame<720;frame++){
 const time=frame/30;baseline.frame(time);renderer.frame(time);
 assert.deepEqual(renderer.camera.position.toArray(),baseline.camera.position.toArray());
 assert.deepEqual(renderer.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(renderer.camera.fov,baseline.camera.fov);
 const audit=renderer.audit(time);assert.equal(audit.cameraState,baseline.audit(time).cameraState);
 assert(Number.isFinite(audit.visualQuality.material_weight));
 frames.push({frame,cameraState:audit.cameraState,weight:audit.visualQuality.material_weight});
}
check('720 exact camera trajectory frames',()=>assert.equal(frames.length,720));
check('scene labels/routes/entities unchanged',()=>{for(const key of ['labels','routes','entities','visual_events','text_events'])assert.deepEqual(renderer.sceneSpec[key],baseline.sceneSpec[key]);});
check('close parameters bounded',()=>{renderer.frame(8);assert.equal(renderer.map.surface.uniforms.uVQWeight.value,1);assert(Math.abs(renderer.map.surface.uniforms.uVQExposureScale.value-.82)<1e-12);assert(Math.abs(renderer.map.surface.uniforms.uVQSpecularScale.value-.45)<1e-12);});
check('wide parameters original',()=>{renderer.frame(14.5);assert.equal(renderer.map.surface.uniforms.uVQWeight.value,0);assert.equal(renderer.map.surface.uniforms.uVQExposureScale.value,1);assert.equal(renderer.map.surface.uniforms.uVQSpecularScale.value,1);});
check('audit physical texture estimates explicitly labeled',()=>{const value=renderer.audit(14.5).visualQuality;assert(value.texture_storage_evidence.includes('not measured'));assert.equal(value.regional_textures[0].day.width,1440);assert.equal(value.regional_textures[0].day.color_space,THREE.SRGBColorSpace);assert.equal(value.regional_textures[0].land_mask.color_space,THREE.NoColorSpace);assert.equal(value.filtering.supported_anisotropy,8);});
check('audit no secret dump',()=>{const serialized=JSON.stringify(renderer.audit(14.5));for(const name of ['OWNER_CODE','cookie','authorization','password','token','session'])assert(!serialized.includes(name));});
const tampered=new quality.SceneVisualQualityRenderer({...scene,visual_quality:{...scene.visual_quality,profile_sha256:'0'.repeat(64)}},plan);
await assert.rejects(()=>tampered.init(),/SOURCE_HASH_MISMATCH/);counters.passed++;
globalThis.fetch=originalFetch;
console.log(JSON.stringify({passed:true,checks:counters.passed,camera_trajectory:'UNCHANGED',frames:720,material_only:true,
 GPU:'NOT_RUN',shader_compile:'NVIDIA_NOT_RUN',pixel_quality:'NOT_RUN_REQUIRES_NVIDIA',
 scope:'Native 720-frame camera math, inherited init with material fixture, source hashing, shader contract, filtering/LOD and safety tests; no GPU pixel or performance claim'}));
if(process.argv[3])fs.writeFileSync(process.argv[3],'#version 100\n'+patched);
