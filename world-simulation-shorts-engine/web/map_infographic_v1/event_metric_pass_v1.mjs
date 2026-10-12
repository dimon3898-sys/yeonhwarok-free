/** Fixed metric's measured alpha atlas rendered by the shared GPU. */
import * as THREE from '/three.js';
import {evaluateMetricAnnotation} from './event_metric_v1.mjs';
export const EVENT_METRIC_PASS_V1_VERSION='EVENT_METRIC_GPU_PASS_V1';
const vertex=`precision highp float;
uniform mat4 projectionMatrix,modelViewMatrix;in vec3 position;in vec2 uv;out vec2 vUv;
void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
// Same measured-text material semantics as the approved graphic pass.
const fragment=`precision highp float;in vec2 vUv;out vec4 frag;
uniform sampler2D glyph;uniform vec2 texel;uniform vec3 color;uniform float outlineRadius;
void main(){float a=texture(glyph,vUv).a,edge=a;
 for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++)edge=max(edge,texture(glyph,vUv+vec2(float(x),float(y))*texel*outlineRadius*.5).a);
 frag=vec4(mix(vec3(.015,.032,.045),color,a),edge);}`;
export function createEventMetricPass({renderer,primitive,width=1080,height=1920,color}){
 if(!renderer?.isWebGLRenderer||renderer.autoClear!==false||width!==1080||height!==1920)
  throw Error('EVENT_METRIC_CANONICAL_SHARED_GPU_REQUIRED');
 if(!Array.isArray(color)||color.length!==3||!color.every(v=>Number.isFinite(v)&&v>=0&&v<=1))throw Error('EVENT_METRIC_EXISTING_TEXT_COLOR_REQUIRED');
 const initial=evaluateMetricAnnotation(primitive,0),texture=new THREE.CanvasTexture(initial.canvas);
 texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.generateMipmaps=false;texture.minFilter=texture.magFilter=THREE.LinearFilter;
 const [w,h]=primitive.atlasDimensions,scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,width,0,height,.1,10);
 camera.position.z=5;camera.updateMatrixWorld();
 const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:vertex,fragmentShader:fragment,
  uniforms:{glyph:{value:texture},texel:{value:new THREE.Vector2(1/w,1/h)},color:{value:new THREE.Vector3(...color)},outlineRadius:{value:primitive.style.outlineRadius}},
  transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),material);scene.add(mesh);
 return {evidence:{version:EVENT_METRIC_PASS_V1_VERSION,font:'Existing native measured glyph coverage',
  material:'Approved measured-text shader semantics; no font/style/layout changes'},
  draw({visibleFraction,placement}){
   if(!placement?.box||placement.box.length!==4||!placement.box.every(Number.isFinite)||placement.box[2]!==w||placement.box[3]!==h)
    throw Error('EVENT_METRIC_FULL_MEASURED_PLACEMENT_REQUIRED');
   const frame=evaluateMetricAnnotation(primitive,visibleFraction);
   if(visibleFraction===0)return {...frame,canvas:undefined,drawn:false,roi:null};
   texture.image=frame.canvas;texture.needsUpdate=true;
   mesh.position.set(placement.box[0]+w/2,placement.box[1]+h/2,0);
   renderer.setRenderTarget(null);renderer.render(scene,camera);
   return {...frame,canvas:undefined,drawn:true,roi:[...placement.roi]};
  },dispose(){mesh.geometry.dispose();material.dispose();texture.dispose();}};
}
