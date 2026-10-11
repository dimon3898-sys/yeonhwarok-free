/** Explicit GPU graphic pass for geographic Camera/Reveal consumers.
 * The approved factory owns all map pixels and pinned-font atlas preparation.
 * This pass changes graphic quad transforms/visibility only, in its actual
 * framebuffer; no Canvas final-frame compositing or finished-frame blit.
 */
import * as THREE from '/three.js';

export const GRAPHIC_MOTION_PASS_V4_VERSION='GRAPHIC_MOTION_PASS_V4';

// Static shader byte sequences copied from the frozen approved factory.
// Their equality is checked by the source-preservation audit.
const graphicVertex = `precision highp float;
uniform mat4 projectionMatrix,modelViewMatrix;in vec3 position;in vec2 uv;out vec2 vUv;
void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const markerFragment = `precision highp float; in vec2 vUv; out vec4 frag;
void main(){
 float r=length((vUv-.5)*2.);
 float outer=1.-smoothstep(.87,.93,r);
 float ring=smoothstep(.48,.53,r)*(1.-smoothstep(.69,.74,r));
 float core=1.-smoothstep(.32,.37,r);
 vec3 c=mix(vec3(.025,.045,.06),vec3(1.),ring);
 c=mix(c,vec3(.96,.29,.16),core);frag=vec4(c,outer);
}`;
const measuredPanelFragment = `precision highp float;in vec2 vUv;out vec4 frag;
uniform vec2 panelSize;uniform float opacity;
void main(){vec2 q=abs((vUv-.5)*panelSize)-(panelSize*.5-vec2(10.));
 float d=length(max(q,0.))+min(max(q.x,q.y),0.)-10.;
 float a=1.-smoothstep(-.7,.7,d);frag=vec4(.015,.035,.052,a*opacity);}`;
const measuredTextFragment = `precision highp float;in vec2 vUv;out vec4 frag;
uniform sampler2D glyph;uniform vec2 texel;uniform vec3 color;uniform float outlineRadius;
void main(){float a=texture(glyph,vUv).a,edge=a;
 for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++)edge=max(edge,texture(glyph,vUv+vec2(float(x),float(y))*texel*outlineRadius*.5).a);
 frag=vec4(mix(vec3(.015,.032,.045),color,a),edge);}`;

const colors={EVENT_TITLE:[1,.97,.86],LOCATION_LABEL:[1,1,1],COUNTRY:[.89,.94,.90],SCENARIO_DISCLOSURE:[.9,.94,.96]};
const revealRole={MARKER:'marker',LOCATION_LABEL:'location',COUNTRY:'country',EVENT_TITLE:'title',TITLE_CONTRAST_PANEL:'title',SCENARIO_DISCLOSURE:'disclosure'};

function material(fragmentShader,uniforms={}){
 return new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:graphicVertex,fragmentShader,uniforms,
  transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});
}

async function glyphCoverageTexture(dataURL,dimensions){
 if(typeof dataURL!=='string'||!dataURL.startsWith('data:image/png;base64,'))throw Error('FROZEN_GLYPH_COVERAGE_PNG_REQUIRED');
 const image=new Image();image.src=dataURL;await image.decode();
 if(image.naturalWidth!==dimensions[0]||image.naturalHeight!==dimensions[1])throw Error('FROZEN_GLYPH_DIMENSIONS_CHANGED');
 // The canvas prepares only the lossless, already measured font coverage.
 // Its RGB is never a rendered map/frame and does not enter final composition.
 const atlas=document.createElement('canvas');atlas.width=image.naturalWidth;atlas.height=image.naturalHeight;
 const context=atlas.getContext('2d');if(!context)throw Error('GLYPH_COVERAGE_DECODE_FAILED');
 context.drawImage(image,0,0);
 const texture=new THREE.CanvasTexture(atlas);
 texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.generateMipmaps=false;
 texture.minFilter=texture.magFilter=THREE.LinearFilter;
 return texture;
}

/** Reuse the factory's actual measured atlas, metrics and draw order. */
export async function createMovingGraphicPass({renderer,factory,width=1080,height=1920}){
 if(!renderer?.isWebGLRenderer||typeof factory?.glyphAtlases!=='function')throw Error('SHARED_GPU_RENDERER_AND_FROZEN_FACTORY_REQUIRED');
 if(width!==1080||height!==1920)throw Error('CANONICAL_GRAPHIC_LAYOUT_REQUIRED');
 const baseline=structuredClone(factory.evidence.layout);
 if(!factory.evidence.layoutValidation.valid)throw Error('FROZEN_MEASURED_LAYOUT_INVALID');
 const atlasByName=new Map(factory.glyphAtlases().map(atlas=>[atlas.name,atlas.dataURL]));
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,1080,0,1920,.1,10);
 camera.position.z=5;camera.updateMatrixWorld();
 const entries=[],textures=[];
 for(const item of baseline){
  const box=item.box;let mat;
  if(item.kind==='MARKER')mat=material(markerFragment);
  else if(item.kind==='PANEL')mat=material(measuredPanelFragment,{panelSize:{value:new THREE.Vector2(box[2],box[3])},opacity:{value:item.opacity}});
  else if(item.kind==='TEXT'){
   const glyph=await glyphCoverageTexture(atlasByName.get(item.glyphAtlasFile),item.atlasDimensions);textures.push(glyph);
   if(!colors[item.role])throw Error('UNKNOWN_APPROVED_TEXT_ROLE');
   mat=material(measuredTextFragment,{glyph:{value:glyph},texel:{value:new THREE.Vector2(1/item.atlasDimensions[0],1/item.atlasDimensions[1])},
    color:{value:new THREE.Vector3(...colors[item.role])},outlineRadius:{value:item.outlineRadius}});
  }else throw Error('UNKNOWN_APPROVED_GRAPHIC_KIND');
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(box[2],box[3]),mat);
  mesh.position.set(box[0]+box[2]/2,box[1]+box[3]/2,0);
  scene.add(mesh);entries.push({item,mesh});
 }
 let current=null;
 function draw({items,reveal}){
  if(!Array.isArray(items)||items.length!==entries.length)throw Error('MOVING_LAYOUT_GRAPHIC_COUNT_CHANGED');
  if(!reveal||typeof reveal!=='object')throw Error('GUIDED_REVEAL_REQUIRED');
  for(let i=0;i<entries.length;i++){
   const {item,mesh}=entries[i],next=items[i],box=next.box;
   if(next.role!==item.role||next.kind!==item.kind||next.text!==item.text)throw Error('APPROVED_GRAPHIC_IDENTITY_CHANGED');
   if(!Array.isArray(box)||box.length!==4||!box.every(Number.isFinite)||box[2]<=0||box[3]<=0)throw Error('INVALID_MOVING_GRAPHIC_BOX');
   if(item.kind==='TEXT'&&(box[2]!==item.box[2]||box[3]!==item.box[3]))throw Error('APPROVED_TEXT_SIZE_CHANGED');
   const factor=reveal[revealRole[item.role]];
   if(!Number.isFinite(factor)||factor<0||factor>1)throw Error('INVALID_GUIDED_REVEAL_FACTOR');
   mesh.position.set(box[0]+box[2]/2,box[1]+box[3]/2,0);
   mesh.scale.set(box[2]/item.box[2],box[3]/item.box[3],1);
   if(item.kind==='PANEL')mesh.material.uniforms.panelSize.value.set(box[2],box[3]);
   // Exact approved appearance semantics (>0), no new text/marker fade shader.
   mesh.visible=factor>0;
  }
  renderer.setRenderTarget(null);renderer.render(scene,camera);
  current={items:structuredClone(items),reveal:structuredClone(reveal),visibleRoles:entries.filter(entry=>entry.mesh.visible).map(entry=>entry.item.role)};
  return current;
 }
 return {draw,baseline,evidence:{version:GRAPHIC_MOTION_PASS_V4_VERSION,composition:'Direct GPU quad draw into the frozen map factory default framebuffer',
  fontCoverage:'Actual frozen factory glyph atlases; lossless PNG coverage, unchanged metrics/style',shaderPolicy:'Four byte-identical approved static GLSL literals',
  drawOrder:baseline.map(item=>item.role),canvasUse:'Pinned glyph coverage decode only; no rendered frame Canvas compositing',finishedFrameMix:false},
  get diagnostic(){return current;},dispose(){for(const {mesh}of entries){mesh.geometry.dispose();mesh.material.dispose();}for(const texture of textures)texture.dispose();}};
}
