/** Camera-only GPU frame graph. All map pixels come from the approved factory. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer,createProofPreview,createProofFinal} from './renderer.mjs';
import {evaluateCameraFrame,cameraEase} from './camera_director.mjs';

export const CAMERA_GPU_PIPELINE_VERSION='CAMERA_GPU_PIPELINE_V1';
const vertex=`varying vec2 cameraUV; void main(){cameraUV=position.xy*.5+.5;gl_Position=vec4(position.xy,0.,1.);}`;
// Source maps already own their final output transfer. Decode only for an
// explicit projection/LOD dissolve; exact endpoints bypass all transfer math.
const fragment=`precision highp float;varying vec2 cameraUV;uniform sampler2D fromMap,toMap;uniform float weight;
vec3 linearRGB(vec3 s){return mix(s/12.92,pow((s+.055)/1.055,vec3(2.4)),step(vec3(.04045),s));}
vec3 displayRGB(vec3 l){return mix(l*12.92,1.055*pow(max(l,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),l));}
void main(){vec4 a=texture2D(fromMap,cameraUV);if(weight<=0.){gl_FragColor=a;return;}
vec4 b=texture2D(toMap,cameraUV);if(weight>=1.){gl_FragColor=b;return;}
gl_FragColor=vec4(displayRGB(mix(linearRGB(a.rgb),linearRGB(b.rgb),weight)),mix(a.a,b.a,weight));}`;

export async function createCameraGpuPipeline({canvas,plans,cameraPlan,heightSource,width=1080,height=1920}){
 if(createProofPreview!==createProofFinal||createProofFinal!==createMapInfographicRenderer)throw Error('PREVIEW_FINAL_FACTORY_MISMATCH');
 if(width!==1080||height!==1920)throw Error('Camera V1 proof requires canonical output');
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WEBGL2_CONTEXT_FAILED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const outputs={},factories={},cache=new Map();
 const target=()=>new THREE.WebGLRenderTarget(width,height,{depthBuffer:false,minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter});
 for(const [key,plan,dem,layoutPlan] of [
  ['WORLD',plans.WORLD,null,null],['CONTINENT',plans.CONTINENT,null,null],
  ['MOTION',plans.CONTINENT,heightSource,plans.REGIONAL],['REGIONAL',plans.REGIONAL,heightSource,null]]){
  console.info(`CAMERA_INIT START ${key}`);outputs[key]=target();
  factories[key]=await createMapInfographicRenderer({canvas,plan,heightSource:dem,outputRenderer:renderer,outputTarget:outputs[key],layoutPlan,width,height});
  console.info(`CAMERA_INIT END ${key}`);
 }
 const material=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,depthTest:false,depthWrite:false,
  uniforms:{fromMap:{value:outputs.WORLD.texture},toMap:{value:outputs.WORLD.texture},weight:{value:0}}});
 const scene=new THREE.Scene(),quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);scene.add(quad);
 const fsCamera=new THREE.Camera();
 const params={verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
 const hidden={primary:0,marker:0,location:0,country:0,title:0,disclosure:Number(cameraPlan.reveal.disclosurePresent)};
 function drawMap(key,reveal=hidden,bounds=null,tokens=null){
  const signature=JSON.stringify([reveal,bounds,tokens]);
  if(cache.get(key)===signature)return;
  const f=factories[key];if(bounds)f.updateCamera(bounds);if(tokens)f.setScaleVisual(tokens);
  f.renderFrame({...params,dem:key==='MOTION'||key==='REGIONAL',reveal});cache.set(key,signature);
 }
 function interpolateTokens(t){
  const a=plans.CONTINENT.theme,b=plans.REGIONAL.theme,result={};
  for(const key of ['primaryWidth','secondaryWidth','primaryEdgeWidth','secondaryEdgeWidth','glowWidth','glowRadius','glowGain'])result[key]=a[key]+(b[key]-a[key])*t;
  result.markerSize=plans.CONTINENT.scale.marker.pixels+(plans.REGIONAL.scale.marker.pixels-plans.CONTINENT.scale.marker.pixels)*t;
  return result;
 }
 const settle=cameraPlan.timeline.find(s=>s.state==='SETTLE');
 let lastOutput=null,lastPixels=null,lastDiagnostic=null;
 function drawFrame(frame){
  const state=evaluateCameraFrame(cameraPlan,frame);let from,to,mix=0,stage;
  if(frame<cameraPlan.projectionTransition.startFrame){drawMap('WORLD');from=to='WORLD';stage='WORLD_CONTEXT';}
  else if(state.transition.active){drawMap('WORLD');drawMap('CONTINENT');from='WORLD';to='CONTINENT';mix=state.transition.mix;stage='PROJECTION_DISSOLVE';}
  else if(frame<cameraPlan.motion.startFrame){drawMap('CONTINENT');from=to='CONTINENT';stage='CONTINENT_CONTEXT';}
  else if(frame<cameraPlan.motion.endFrame){
   drawMap('MOTION',hidden,state.camera.flatBounds,interpolateTokens(state.easingProgress));
   // Broad-scale RGB stays unchanged; this brief transition admits the same
   // validated DEM path without a first-motion-frame data/lighting hard cut.
   const lodFrames=Math.max(2,Math.round((cameraPlan.motion.endFrame-cameraPlan.motion.startFrame)*.12));
   const p=(frame-cameraPlan.motion.startFrame)/(lodFrames-1);
   if(p<1){drawMap('CONTINENT');from='CONTINENT';to='MOTION';mix=cameraEase(p);stage='MOTION_DEM_ADMISSION_DISSOLVE';}
   else {from=to='MOTION';stage='GEOGRAPHIC_CAMERA_MOTION';}
  }else if(frame<settle.endFrame){
   drawMap('MOTION',hidden,plans.REGIONAL.framing.bounds,interpolateTokens(1));drawMap('REGIONAL');
   from='MOTION';to='REGIONAL';mix=cameraEase((frame-settle.startFrame)/(settle.durationFrames-1));stage='FIXED_CAMERA_REGIONAL_LOD_SETTLE';
  }else {drawMap('REGIONAL',state.reveal);from=to='REGIONAL';stage='LOCKED_REGIONAL';}
  const outputSignature=JSON.stringify([from,to,mix,cache.get(from),cache.get(to)]);
  if(lastOutput!==outputSignature){
   material.uniforms.fromMap.value=outputs[from].texture;material.uniforms.toMap.value=outputs[to].texture;material.uniforms.weight.value=mix;
   renderer.setRenderTarget(null);renderer.setClearColor(0,1);renderer.clear();renderer.render(scene,fsCamera);
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('CAMERA_COMPOSITION_GL_ERROR_'+error);
   lastPixels=null;lastOutput=outputSignature;
  }
  const f=factories[from],diagnostic={...state,gpu:{stage,from,to,mix,glError:0,context:'WebGL2',factory:'createMapInfographicRenderer',
   actualCamera:structuredClone(f.evidence.cameraFrame??{bounds:[...f.plan.framing.bounds],anchorCanonical:f.screen(f.plan.anchor.coordinates)}),
   layoutVisible:state.reveal.location>0||state.reveal.title>0,
   actualReveal:structuredClone(factories.REGIONAL.evidence.revealState??hidden),
   regionalLayoutHashInput:factories.REGIONAL.evidence.layout,
   boundaryPixels:interpolateTokens(state.easingProgress)}};
  // Every integer frame has independent state even when fixed GPU pixels are
  // reused. No clock-based animation and no repeatedly reflowing text.
  lastDiagnostic=diagnostic;return diagnostic;
 }
 function readPixels(){
  if(!lastPixels){lastPixels=new Uint8Array(width*height*4);renderer.setRenderTarget(null);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,lastPixels);if(gl.getError()!==gl.NO_ERROR)throw Error('CAMERA_READPIXELS_GL_ERROR');}
  return lastPixels;
 }
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 return {drawFrame,readPixels,png:()=>canvas.toDataURL('image/png'),
  evidence:{version:CAMERA_GPU_PIPELINE_VERSION,context:gl.getParameter(gl.VERSION),gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
   previewFinalSameFactory:true,composition:'Explicit GPU projection/data-LOD cross dissolve; unchanged map factory shaders',
   frozenMaterialParameters:params,layoutLocked:true,softwareOnly:true,nvidia:'NOT_RUN',
   factories:Object.fromEntries(Object.entries(factories).map(([k,f])=>[k,f.evidence]))},
  get diagnostic(){return lastDiagnostic},
  dispose(){Object.values(factories).forEach(f=>f.dispose());Object.values(outputs).forEach(t=>t.dispose());material.dispose();quad.geometry.dispose();renderer.dispose();}};
}
