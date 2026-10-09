/** v019 actual material/camera contracts. CPU arithmetic is never an AFTER GPU frame. */
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
const event=new Function('SceneVisualQualityRenderer','digestBytes','trustedStaticURL',
 strip('web/event_quality_adapter.js')+';return {validateEventQualityProfile,eventQualityResponse,eventQualitySurfaceShader,SceneEventQualityRenderer};')
 (quality.SceneVisualQualityRenderer,quality.digestBytes,quality.trustedStaticURL);
globalThis.location={origin:'http://localhost'};
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const eventProfile=JSON.parse(read('data/event_quality_v019.json'));
const profileBytes=fs.readFileSync(path.join(root,'web/visual_quality_v018.json')),
 manifestBytes=fs.readFileSync(path.join(root,'web/earth-detail/v018/manifest.json')),
 eventBytes=fs.readFileSync(path.join(root,'web/event_quality_v019.json'));
const shaBytes=bytes=>createHash('sha256').update(bytes).digest('hex');
check('data/served profile identical',()=>assert.equal(read('data/event_quality_v019.json'),read('web/event_quality_v019.json')));
check('profile accepted',()=>assert.equal(event.validateEventQualityProfile(eventProfile),eventProfile));
check('legacy profile rejected',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,version:'v018'}),/PROFILE_VERSION_INVALID/));
for(const [field,values] of Object.entries({day_input_scale:[NaN,Infinity,true,0,1.1],ocean_specular_scale:[NaN,0,1.1],city_contribution_scale:[NaN,0,1.1]}))
 for(const value of values)check('invalid response rejected',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,[field]:value}),/RESPONSE_INVALID/));
check('new mask prohibited',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,city_mask:'invented_city_data'}),/MASK_SOURCE_INVALID/));
check('new textures prohibited',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,additional_textures:1}),/MASK_SOURCE_INVALID/));
check('daylight night gate retained',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,daylight_start:-.1}),/DAYLIGHT_GATE_INVALID/));
check('invalid daylight range rejected',()=>assert.throws(()=>event.validateEventQualityProfile({...eventProfile,daylight_full:0}),/DAYLIGHT_GATE_INVALID/));
check('explicit opt in required',()=>{const oldScene=structuredClone(scene);delete oldScene.event_quality;assert.throws(()=>new event.SceneEventQualityRenderer(oldScene,plan),/EXPLICIT_V019_OPT_IN_REQUIRED/);});
const patchedV18=quality.qualitySurfaceShader(surface,2),patched=event.eventQualitySurfaceShader(patchedV18,2);
check('missing output fails closed',()=>assert.throws(()=>event.eventQualitySurfaceShader(patchedV18.replace('gl_FragColor=vec4((diffuse+readable+','gl_FragColor=vec4((diffuse+'),2),/SHADER_CONTRACT_SURFACE_OUTPUT/));
check('duplicate main fails closed',()=>assert.throws(()=>event.eventQualitySurfaceShader(patchedV18+'void main(){}',2),/SHADER_CONTRACT_MAIN/));
check('mask count must match preserved assets',()=>assert.throws(()=>event.eventQualitySurfaceShader(patchedV18,3),/PRESERVED_MASK_COUNT_INVALID/));
check('original sampler set unchanged',()=>assert.deepEqual(patched.match(/uniform sampler2D[^;]+;/g),patchedV18.match(/uniform sampler2D[^;]+;/g)));
check('original regional native source retained',()=>{assert(patched.includes('day=vqRegional.rgb;'));assert(patched.includes('float land=vqRegional.a;'));assert(patched.includes('texture2D(uTopo,uv+vec2(1./2048.,0))'));assert(patched.includes('vec3 night=texture2D(uNight,uv).rgb'));});
check('WIDE bypasses all added surface arithmetic',()=>assert(patched.includes('if(uEQWeight>0.){')));
check('native land masks reuse original bounds and edge feather',()=>{for(let n=0;n<2;n++){assert(patched.includes(`vec4 bounds=uVQBounds${n};`));assert(patched.includes(`texture2D(uVQMask${n},q).r`));}assert(patched.includes('smoothstep(0.,uVQEdgeFeather,edge)'));});
check('surface output remains original v018',()=>assert(patched.endsWith(patchedV18.slice(patchedV18.indexOf('gl_FragColor=vec4((diffuse+readable+')))));
const coefficients={diffuse:[1.111,1.153,1.092],readable:[.126,.129,.101],spec:0,lights:[0,0,0],nd:.927,weight:1,landMask:1};
const film=x=>Math.min(1,Math.max(0,(x*(2.51*x+.03))/(x*(2.43*x+.59)+.14)));
const display=v=>v.map(x=>Math.pow(film(x*1.066*1.23),1/2.2)*255);
const luma=rgb=>rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
const surfaceDisplay=value=>display(value.diffuse.map((v,i)=>v+value.readable[i]));
const before=event.eventQualityResponse({...coefficients,weight:0},eventProfile),after=event.eventQualityResponse(coefficients,eventProfile);
check('Suez real bright surface stays luminous with lower film input',()=>{const oldValue=luma(surfaceDisplay(before)),newValue=luma(surfaceDisplay(after));assert(oldValue>238);assert(newValue>220&&newValue<oldValue);});
const detailDelta=weight=>{
 const sample=mult=>event.eventQualityResponse({...coefficients,weight,diffuse:coefficients.diffuse.map(x=>x*mult),readable:coefficients.readable.map(x=>x*mult)},eventProfile);
 return luma(surfaceDisplay(sample(1.03)))-luma(surfaceDisplay(sample(.97)));
};
check('real source variations survive fixed film curve better',()=>assert(detailDelta(1)>detailDelta(0)*1.5));
check('separate ocean reflection contribution reduced',()=>{const value=event.eventQualityResponse({...coefficients,spec:.1888},eventProfile);assert(Math.abs(value.spec-.1888*.6*.5)<1e-12);});
check('Singapore actual night diffuse and fill exactly retained',()=>{const value=event.eventQualityResponse({...coefficients,nd:-.0297,spec:.1},eventProfile);assert.deepEqual(value.diffuse,coefficients.diffuse);assert.deepEqual(value.readable,coefficients.readable);assert.equal(value.spec,.1);});
check('existing city data becomes auxiliary not fabricated detail',()=>{const value=event.eventQualityResponse({...coefficients,nd:-.0297,lights:[.4197486386,.1930843738,.0629622958],landMask:.41307705},eventProfile);assert(value.lights[0]/.03206624<.66);assert(value.lights[0]>0);});
check('ocean mask prevents spill without blur',()=>{const value=event.eventQualityResponse({...coefficients,lights:[1,1,1],landMask:0},eventProfile);assert.deepEqual(value.lights,[0,0,0]);});
check('WIDE response bit for bit unchanged for all day/night states',()=>{for(const nd of [-1,-.03,0,.1,.9])for(const landMask of [0,.413,1]){const input={...coefficients,nd,landMask,weight:0,spec:.1888,lights:[.7,.3,.1]};assert.deepEqual(event.eventQualityResponse(input,eventProfile),{diffuse:input.diffuse,readable:input.readable,spec:input.spec,lights:input.lights});}});
check('continuous finite bounded response across original LOD weights',()=>{let prior=null;for(let n=0;n<=1000;n++){const value=event.eventQualityResponse({...coefficients,weight:n/1000,spec:.2,lights:[1,.5,.2],landMask:.413},eventProfile);for(const item of [...value.diffuse,...value.readable,...value.lights,value.spec])assert(Number.isFinite(item)&&item>=0);if(prior)assert(Math.abs(value.diffuse[0]-prior.diffuse[0])<.001);prior=value;}});
check('no post/cloud/atmosphere/camera/text overrides',()=>{const src=read('web/event_quality_adapter.js');for(const term of ['postMat.fragmentShader=','cloudMat.fragmentShader=','camera.position','camera.fov=','Math.random','GaussianBlur','sharpen'])assert(!src.includes(term));});
const originalFetch=globalThis.fetch,requests=[];
globalThis.fetch=async url=>{
 requests.push(url);
 const bytes=url==='/static/visual_quality_v018.json'?profileBytes:url==='/static/event_quality_v019.json'?eventBytes:url===profile.regional_detail.manifest_url?manifestBytes:assets[url];
 assert(bytes,'Every source must be a real deployed asset');
 return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};
};
scene.visual_quality={...scene.visual_quality,version:'v018',profile_sha256:shaBytes(profileBytes),manifest_sha256:shaBytes(manifestBytes)};
scene.event_quality={...scene.event_quality,version:'v019',profile_url:'/static/event_quality_v019.json',profile_sha256:shaBytes(eventBytes)};
const baselineScene=structuredClone(scene);delete baselineScene.event_quality;
const baseline=new quality.SceneVisualQualityRenderer(baselineScene,plan);
await baseline.init();const originalRequests=requests.splice(0);
const renderer=new event.SceneEventQualityRenderer(scene,plan);
await renderer.init();const newRequests=requests.splice(0);
check('all inherited actual four PNG fetches identical',()=>assert.deepEqual(newRequests.filter(v=>v.endsWith('.png')).sort(),originalRequests.filter(v=>v.endsWith('.png')).sort()));
check('only new source fetch is tiny scalar JSON',()=>assert.deepEqual(newRequests.filter(v=>!originalRequests.includes(v)),['/static/event_quality_v019.json']));
check('new renderer initialized and real regional textures preserved',()=>{assert.equal(renderer.eventQualityReady,true);assert.equal(renderer.qualityTiles.length,2);assert.equal(renderer.map.surface.uniforms.uDay.value.image.width,8192);assert.equal(renderer.qualityTiles[0].day.image.width,1440);});
check('1080 output HIGH internal dimensions untouched',()=>assert.deepEqual([renderer.w,renderer.h],[2160,3840]));
const poses=[],wideFrames=[];
for(let frame=0;frame<720;frame++){
 const time=frame/30;baseline.frame(time);renderer.frame(time);
 const oldAudit=baseline.audit(time),audit=renderer.audit(time);
 assert.deepEqual(renderer.camera.position.toArray(),baseline.camera.position.toArray());
 assert.deepEqual(renderer.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());
 assert.equal(renderer.camera.fov,baseline.camera.fov);
 assert.equal(audit.cameraState,oldAudit.cameraState);
 assert.equal(renderer.map.surface.uniforms.uEQWeight.value,baseline.map.surface.uniforms.uVQWeight.value);
 if(['EVENT1_WIDE','EVENT1_LOCATION','ADAPTIVE_WIDE','EVENT2_LOCATION'].includes(audit.cameraState)){
  assert.equal(renderer.map.surface.uniforms.uEQWeight.value,0);wideFrames.push(frame);
 }
 poses.push({frame,timestamp:time,camera_state:audit.cameraState,position:renderer.camera.position.toArray(),quaternion:renderer.camera.quaternion.toArray(),fov:renderer.camera.fov,weight:audit.eventQuality.material_weight});
}
check('all 720 actual inherited camera frames match v018',()=>assert.equal(poses.length,720));
check('all 14–16.5 CONTINENT_WIDE frames exact zero response',()=>{for(let frame=420;frame<495;frame++)assert(wideFrames.includes(frame));});
check('all scene content and timing untouched',()=>{const plain=structuredClone(renderer.sceneSpec);delete plain.event_quality;assert.deepEqual(plain,baseline.sceneSpec);});
check('original mask resources exact filtering/colorspace retained',()=>{for(let n=0;n<2;n++){const a=renderer.qualityTiles[n],b=baseline.qualityTiles[n];for(const key of ['day','mask']){assert.deepEqual(a[key].image,b[key].image);assert.equal(a[key].minFilter,b[key].minFilter);assert.equal(a[key].colorSpace,b[key].colorSpace);assert.equal(a[key].anisotropy,b[key].anisotropy);}}});
check('diagnostic response receipt uses only actual allowlisted inputs',()=>{const audit=renderer.audit(21).eventQuality;assert.equal(audit.version,'v019');assert.equal(audit.additional_texture_uploads,0);assert.equal(audit.profile_sha256,shaBytes(eventBytes));for(const term of ['OWNER_CODE','cookie','authorization','password','token','session'])assert(!JSON.stringify(audit).includes(term));});
const tampered=new event.SceneEventQualityRenderer({...scene,event_quality:{...scene.event_quality,profile_sha256:'0'.repeat(64)}},plan);
await assert.rejects(()=>tampered.init(),/EVENT_QUALITY_SOURCE_HASH_MISMATCH/);counters.passed++;
const foreign=new event.SceneEventQualityRenderer({...scene,event_quality:{...scene.event_quality,profile_url:'https://untrusted.example/profile.json'}},plan);
await assert.rejects(()=>foreign.init(),/SOURCE_URL_INVALID/);counters.passed++;
globalThis.fetch=originalFetch;
console.log(JSON.stringify({passed:true,checks:counters.passed,frames:720,camera_trajectory:'UNCHANGED',
 wide_response:'UNCHANGED',additional_texture_uploads:0,GPU:'NOT_RUN',shader_compile:'NVIDIA_NOT_RUN',pixel_quality:'NOT_RUN',
 analytical_only:{suez_before_luma:luma(surfaceDisplay(before)),suez_candidate_luma:luma(surfaceDisplay(after)),source_detail_response_ratio:detailDelta(1)/detailDelta(0)},
 scope:'Actual inherited camera/init and real shader assembly; analytical radiance is not an AFTER GPU frame. No browser/software/GPU draw.'}));
if(process.argv[3])fs.writeFileSync(process.argv[3],'#version 100\n'+patched);
