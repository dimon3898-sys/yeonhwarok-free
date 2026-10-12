/** Independent finite-support Event highlight. No existing boundary shader changes. */
import * as THREE from '/three.js';
import {evaluateGeographicLineReveal} from './event_line_v1.mjs';
import {classifyEventLineProtection,EVENT_MARKER_OCCLUSION_CAPACITY} from './event_occlusion_policy_v1.mjs';

export const EVENT_LINE_PASS_V1_VERSION = 'EVENT_LINE_GPU_PASS_V1';
const CAPACITY = 128;
const vertex = `precision highp float;
uniform mat4 projectionMatrix,modelViewMatrix;in vec3 position;
void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const fragment = `precision highp float;out vec4 frag;
uniform vec4 segments[128];uniform int segmentCount;uniform float screenHeight;
uniform float radius,halo,gain;uniform vec4 coreColor,glowColor;
uniform vec4 markerOcclusions[32];uniform int markerOcclusionCount;
void main(){
 vec2 p=vec2(gl_FragCoord.x,screenHeight-gl_FragCoord.y);float d=1.e20;
 // Occlusion affects raster coverage only, never the supplied path or reveal clock.
 for(int i=0;i<32;i++){if(i>=markerOcclusionCount)break;
  vec4 b=markerOcclusions[i];
  if(p.x>=b.x&&p.y>=b.y&&p.x<=b.z&&p.y<=b.w)discard;
 }
 for(int i=0;i<128;i++){if(i>=segmentCount)break;
  vec2 a=segments[i].xy,b=segments[i].zw,ab=b-a;
  float t=clamp(dot(p-a,ab)/max(dot(ab,ab),1.e-12),0.,1.);
  d=min(d,length(p-a-t*ab));
 }
 float core=(1.-smoothstep(max(0.,radius-.5),radius+.5,d))*coreColor.a;
 float glow=(1.-smoothstep(radius,radius+halo,d))*gain*glowColor.a;
 float alpha=core+glow*(1.-core);if(alpha<=0.)discard;
 frag=vec4(mix(glowColor.rgb,coreColor.rgb,core/max(alpha,1.e-12)),alpha);
}`;
const validBox = b => Array.isArray(b) && b.length===4 && b.every(Number.isFinite) && b[0]<b[2] && b[1]<b[3];
const intersects = (a,b) => a[0]<b[2] && a[2]>b[0] && a[1]<b[3] && a[3]>b[1];
function styleRecord(style) {
 if(!style || !Number.isFinite(style.width) || style.width<=0 || !Number.isFinite(style.glowRadius) || style.glowRadius<=0 ||
  !Number.isFinite(style.glowGain) || style.glowGain<0 || style.glowGain>1)throw Error('EVENT_LINE_STYLE_REQUIRED');
 for(const key of ['coreColor','glowColor'])if(!Array.isArray(style[key]) || style[key].length!==4 ||
  !style[key].every(v=>Number.isFinite(v)&&v>=0&&v<=1))throw Error('EVENT_LINE_COLOR_REQUIRED');
 return structuredClone(style);
}
/** Preserve the full geometric footprint; only typed native Marker coverage may occlude it. */
export function validateEventLineFootprint(primitive,{style,safeArea,protectedBoxes=[],protectedGraphics=[]}) {
 const s=styleRecord(style),padding=s.width/2+Math.max(.5,s.glowRadius)+1;
 const full=evaluateGeographicLineReveal(primitive,1,{paddingPixels:padding});
 if(!validBox(safeArea)||!Array.isArray(protectedBoxes)||!protectedBoxes.every(validBox))throw Error('EVENT_LINE_LAYOUT_RECT_REQUIRED');
 const protection=classifyEventLineProtection({protectedBoxes,protectedGraphics});
 if(primitive.screenCoordinates.length-1>CAPACITY)throw Error('EVENT_LINE_GPU_CAPACITY_DATA_LIMITED');
 if(full.roi[0]<safeArea[0]||full.roi[1]<safeArea[1]||full.roi[2]>safeArea[2]||full.roi[3]>safeArea[3])
  throw Error('EVENT_LINE_HALO_OUTSIDE_SAFE_AREA');
 for(let i=1;i<full.path.length;i++){
  const a=full.path[i-1],b=full.path[i];
  const bounds=[Math.min(a[0],b[0])-padding,Math.min(a[1],b[1])-padding,Math.max(a[0],b[0])+padding,Math.max(a[1],b[1])+padding];
  if(protection.strictBoxes.some(box=>intersects(bounds,box)))throw Error('EVENT_LINE_PROTECTED_GRAPHIC_COLLISION');
 }
 return {paddingPixels:padding,fullRoi:full.roi,capacity:CAPACITY,...protection};
}
export function createEventLinePass({renderer,width=1080,height=1920,style}) {
 if(!renderer?.isWebGLRenderer||width!==1080||height!==1920)throw Error('EVENT_CANONICAL_SHARED_GPU_REQUIRED');
 if(renderer.autoClear!==false)throw Error('EVENT_SHARED_RENDERER_AUTOCLEAR_FORBIDDEN');
 const s=styleRecord(style),scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,width,0,height,.1,10);
 camera.position.z=5;camera.updateMatrixWorld();
 const segments=Array.from({length:CAPACITY},()=>new THREE.Vector4());
 const markerOcclusions=Array.from({length:EVENT_MARKER_OCCLUSION_CAPACITY},()=>new THREE.Vector4());
 const uniforms={segments:{value:segments},segmentCount:{value:0},screenHeight:{value:height},
  markerOcclusions:{value:markerOcclusions},markerOcclusionCount:{value:0},
  radius:{value:s.width/2},halo:{value:s.glowRadius},gain:{value:s.glowGain},
  coreColor:{value:new THREE.Vector4(...s.coreColor)},glowColor:{value:new THREE.Vector4(...s.glowColor)}};
 const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:vertex,fragmentShader:fragment,uniforms,
  transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1),material);scene.add(mesh);
 return {evidence:{version:EVENT_LINE_PASS_V1_VERSION,composition:'Independent screen-space GPU polyline over fresh native map',
  support:'Finite capsule core + compact halo; nearest segment prevents joint overbrightening',capacity:CAPACITY},
  draw({primitive,visibleFraction,safeArea,protectedBoxes=[],protectedGraphics=[]}){
   const footprint=validateEventLineFootprint(primitive,{style:s,safeArea,protectedBoxes,protectedGraphics});
   const reveal=evaluateGeographicLineReveal(primitive,visibleFraction,{paddingPixels:footprint.paddingPixels});
   if(reveal.path.length<2)return {...reveal,drawn:false};
   footprint.markerOcclusions.forEach((box,index)=>markerOcclusions[index].set(...box));
   uniforms.markerOcclusionCount.value=footprint.markerOcclusions.length;
   for(let i=1;i<reveal.path.length;i++)segments[i-1].set(...reveal.path[i-1],...reveal.path[i]);
   uniforms.segmentCount.value=reveal.path.length-1;
   const [left,top,right,bottom]=reveal.roi;
   mesh.position.set((left+right)/2,(top+bottom)/2,0);mesh.scale.set(right-left,bottom-top,1);
   renderer.setRenderTarget(null);renderer.render(scene,camera);
   return {...reveal,drawn:true,occlusionPolicy:footprint.policy,markerOcclusions:footprint.markerOcclusions};
  },dispose(){mesh.geometry.dispose();material.dispose();}};
}
