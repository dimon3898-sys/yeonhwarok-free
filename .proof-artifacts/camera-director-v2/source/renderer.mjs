/** MAP_INFOGRAPHIC_RENDERER_V1 — Gate 1 only.
 * Independent WebGL2 frame graph. No parent Earth renderer, DOM overlay,
 * Canvas frame compositing, shader rewriting, animation or production entrypoint.
 * Canvas is used ONLY to prepare a font coverage texture; GPU draws final text.
 */
import * as THREE from '/three.js';
import {createMeasuredGlyph} from './glyph_atlas.mjs';
import {buildMeasuredGraphicLayout} from './graphic_layout.mjs';
import {createGlobeProjection, geographicAtlasRecord, globeBoundaryRings, globeBasis} from './scale_projection.mjs';
import {assertLocalDetailAdmission} from './local_detail_admission.mjs';

export const VERSION = 'MAP_INFOGRAPHIC_RENDERER_V1_GATE1';
export const SHADER_VERSION = 'explicit-glsl-1-scale-system-v1';
export const THEME_VERSION = 'terrain-material-1';
const fullscreenVertex = `precision highp float;
in vec3 position; in vec2 uv; out vec2 vUv;
void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}`;
const graphicVertex = `precision highp float;
uniform mat4 projectionMatrix,modelViewMatrix;in vec3 position;in vec2 uv;out vec2 vUv;
void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const geoVertex = `precision highp float;
uniform mat4 projectionMatrix, modelViewMatrix; in vec3 position;
void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const flatFragment = `precision highp float;
uniform vec3 value; out vec4 frag;
void main(){frag=vec4(value,1.);}`;
const terrainFragment = `precision highp float;
in vec2 vUv; out vec4 frag;
uniform sampler2D terrain, globalTerrain, topo, regionID, coverage, roles;
uniform vec4 bounds, tileBounds;
// Optional continuous-map LOD is a geographic SOURCE input, before the frozen
// material/lighting response. It never blends completed frames or GIS masks.
uniform sampler2D contextTerrain;
uniform vec4 contextTileBounds;
uniform int contextTerrainEnabled;
uniform float terrainLodWeight;
// Projection is an explicit input to this same material, not a second renderer.
uniform int globeProjection;
uniform vec4 globeDisc;
uniform vec3 globeEast,globeNorth,globeCenter;
uniform vec3 primaryHue, secondaryHue;
uniform float primaryStrength, secondaryStrength, primaryLuminance, secondaryLuminance, detailContrast, reliefStrength, exposure;
uniform int mode, terrainTreatment;
// Height is a MATERIAL input, not an RGB overlay. IDs/coverage stay unchanged.
uniform sampler2D demHeight;
uniform vec2 demFirstSample, demSpacing, demDimensions, canonicalPixelDegrees;
uniform int demEnabled, demCorrectedLight;
uniform float demExaggeration, demBakedSuppression;
// Explicit controlled ablation: 0=Gate1B, 1=light, 2=material, 3=frozen D,
// 4=final terrain pass. The accepted D response remains reproducible at stage 3.
uniform int shadingStage;
float heightAt(vec2 geo){
 vec2 q=vec2((geo.x-demFirstSample.x)/demSpacing.x,(demFirstSample.y-geo.y)/demSpacing.y);
 ivec2 i=ivec2(floor(q)),hi=ivec2(demDimensions)-1;vec2 f=fract(q);
 float a=texelFetch(demHeight,clamp(i,ivec2(0),hi),0).r;
 float b=texelFetch(demHeight,clamp(i+ivec2(1,0),ivec2(0),hi),0).r;
 float c=texelFetch(demHeight,clamp(i+ivec2(0,1),ivec2(0),hi),0).r;
 float d=texelFetch(demHeight,clamp(i+ivec2(1,1),ivec2(0),hi),0).r;
 return mix(mix(a,b,f.x),mix(c,d,f.x),f.y);
}
float footprintHeight(vec2 geo,vec2 stepDegrees){
 // Nine sparse height taps across the canonical output footprint. Native slopes
 // sampled once per 1.3km output pixel would alias ~44-50 30m samples/pixel.
 float h=0.;for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)
  h+=heightAt(geo+vec2(float(x),float(y))*.45*stepDegrees);
 return h/9.;
}
float demWeight(vec2 geo,vec2 stepDegrees){
 if(demEnabled==0)return 0.;
 vec2 last=demFirstSample+vec2(demSpacing.x,-demSpacing.y)*(demDimensions-1.);
 vec2 edge=min(geo-vec2(demFirstSample.x,last.y),vec2(last.x,demFirstSample.y)-geo);
 // Require a complete real-data neighbourhood: never invent edge heights.
 return smoothstep(1.5,2.5,min(edge.x/stepDegrees.x,edge.y/stepDegrees.y));
}
vec3 demNormal(vec2 geo,vec2 stepDegrees){
 float e=footprintHeight(geo+vec2(stepDegrees.x,0.),stepDegrees)-footprintHeight(geo-vec2(stepDegrees.x,0.),stepDegrees);
 float n=footprintHeight(geo+vec2(0.,stepDegrees.y),stepDegrees)-footprintHeight(geo-vec2(0.,stepDegrees.y),stepDegrees);
 // WGS84 meridian and prime-vertical radii; east/north spacing is not equal.
 float lat=radians(geo.y),sinLat=sin(lat),den=1.-.00669437999014*sinLat*sinLat;
 float eastMetres=6378137./sqrt(den)*cos(lat)*radians(2.*stepDegrees.x);
 float northMetres=6378137.*(1.-.00669437999014)/pow(den,1.5)*radians(2.*stepDegrees.y);
 return normalize(vec3(-e/eastMetres*demExaggeration,-n/northMetres*demExaggeration,1.));
}
vec3 linearize(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
vec3 encode(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
float lum(vec3 c){return dot(c,vec3(.2126,.7152,.0722));}
vec3 grade(vec3 base,vec3 hue,float strength){
 float y=max(lum(base),.002);
 // Region identity changes chroma, not topology or surface variation.
 // Luminance comes from the ACTUAL terrain sample, not a synthetic noise field.
 vec3 tint=linearize(hue); tint/=max(lum(tint),.01);
 vec3 variation=clamp(base/y,vec3(.58),vec3(1.45));
 float detail=.35*pow(y/.35,detailContrast);
 vec3 colored=tint*detail*mix(vec3(1.),variation,.24);
 return mix(base,colored,strength);
}
vec3 terrainMaterial(vec3 base,vec3 hue,float strength,int stage){
 if(stage<2)return grade(base,hue,strength);
 float y=max(lum(base),.002);
 vec3 tint=linearize(hue);tint/=max(lum(tint),.01);
 // Calibrate the role's color identity once at a fixed baseline reference.
 // This keeps the accepted display palette after replacing the old output
 // transfer. It is NOT a per-pixel tone curve: terrain Y stays independent.
 tint=tint/(1.+.70*tint*1.15);tint/=max(lum(tint),.01);
 // Source-only chromatic variation. Renormalize the colorant so chroma
 // never determines surface luminance; do not invent texture or elevation.
 vec3 residual=mix(vec3(1.),clamp(base/y,vec3(.58),vec3(1.45)),.45);
 vec3 colorant=mix(base/y,tint*residual,strength);
 colorant/=max(lum(colorant),.001);
 // More source-derived luminance separation, with display headroom for bright
 // desert midtones. This is a pointwise material response, not sharpening,
 // elevation amplification, or a new source of surface detail.
 float terrainY=stage>=4?.190*pow(y/.35,detailContrast+.20):.26*pow(y/.35,detailContrast);
 return colorant*terrainY;
}
vec3 terrainOutput(vec3 color,int stage){
 float y=max(lum(color),.000001);
 // One scalar tone response: every channel receives the same Y scale.
 // The lower material anchor creates room for a gentler luminance shoulder.
 // Every channel still shares this single response; hue/gamut logic is intact.
 float shoulder=stage>=4?.40:.50;
 float mappedY=y/(1.+shoulder*y);
 vec3 chroma=color/y;
 // Gamut compression at constant mapped luminance. A neutral-axis blend
 // preserves the linear RGB hue direction instead of clipping channels.
 float peak=max(chroma.r,max(chroma.g,chroma.b));
 float allowed=.98/max(mappedY,.000001);
 float amount=peak>1.?min(1.,max(0.,(allowed-1.)/(peak-1.))):1.;
 return mappedY*mix(vec3(1.),chroma,amount);
}
void main(){
 vec2 geo=mix(bounds.xy,bounds.zw,vUv);
 vec2 gisUv=vUv;
 if(globeProjection==1){
  vec2 xy=(vUv-globeDisc.xy)/globeDisc.zw;
  float r2=dot(xy,xy);
  if(r2>1.){frag=vec4(.006,.014,.026,1.);return;}
  vec3 earth=xy.x*globeEast+xy.y*globeNorth+sqrt(max(0.,1.-r2))*globeCenter;
  geo=vec2(degrees(atan(earth.z,earth.x)),degrees(asin(clamp(earth.y,-1.,1.))));
  gisUv=vec2((geo.x+180.)/360.,(geo.y+90.)/180.);
 }
 vec2 guv=vec2((geo.x+180.)/360.,(geo.y+90.)/180.);
 vec2 tuv=(geo-tileBounds.xy)/(tileBounds.zw-tileBounds.xy);
 float inside=step(0.,tuv.x)*step(0.,tuv.y)*step(tuv.x,1.)*step(tuv.y,1.);
 // WORLD admits the global source; regional crops are not world detail.
 if(globeProjection==1)inside=0.;
 vec3 source;
 if(contextTerrainEnabled==0||terrainLodWeight>=1.){
  // Final/default path is the approved source expression, without extra source
  // work or changes to the frozen downstream material/lighting/output response.
  source=linearize(mix(texture(globalTerrain,guv).rgb,texture(terrain,tuv).rgb,inside));
 }
 if(contextTerrainEnabled==1&&terrainLodWeight<1.){
  vec3 sourceRGB=mix(texture(globalTerrain,guv).rgb,texture(terrain,tuv).rgb,inside);
  vec2 contextUv=(geo-contextTileBounds.xy)/(contextTileBounds.zw-contextTileBounds.xy);
  float contextInside=step(0.,contextUv.x)*step(0.,contextUv.y)*step(contextUv.x,1.)*step(contextUv.y,1.);
  vec3 contextRGB=mix(texture(globalTerrain,guv).rgb,texture(contextTerrain,contextUv).rgb,contextInside);
  // Outside the real regional source, retain the real wide source. Both inputs
  // refer to the same geographic coordinates; no synthetic detail is admitted.
  sourceRGB=mix(contextRGB,sourceRGB,terrainLodWeight*inside);
  // Both admitted inputs are baked NE1 sources. This is their actual coverage,
  // not a camera-dependent switch in the existing baked-lighting formula.
  inside=max(inside,contextInside);
  source=linearize(sourceRGB);
 }
 // Gate1A source ablation: diagnostic output only, before material or lighting.
 if(mode==5){frag=vec4(encode(source),1.);return;}
 vec3 cov=texture(coverage,gisUv).rgb;
 // Preserve the baseline sea/AA path below the coverage target's half-LSB.
 // Coverage/geometry targets themselves are unchanged. Tiny interpolation
 // residuals at pure-sea pixel centres must not select a land correction.
 int stage=cov.r<(.5/255.)?0:shadingStage;
 vec2 idBytes=floor(texture(regionID,gisUv).rg*255.+.5);
 float id=idBytes.x+256.*idBytes.y;
 float role=texture(roles,vec2((id+.5)/256.,.5)).r*255.;
 if(mode==3){frag=vec4(idBytes/255.,0.,1.);return;}
 if(mode==4){frag=vec4(cov,1.);return;}
 // Discrete IDs are NEAREST sampled. Only separate AA coverage is fractional.
 float p=role>1.5?cov.b:(cov.b>0.&&cov.b<.999?cov.b:0.);
 float s=role>.5&&role<1.5?cov.g:(cov.g>0.&&cov.g<.999?cov.g:0.);
 // NE1 is already shaded. Recover only its existing luminance variation;
 // do not infer heights/normals from color or synthesize new terrain detail.
 // Applied only inside the admitted baked-hillshade tile. Sea keeps raw source.
 vec3 surface=source;
 vec2 demStep=max(demSpacing,canonicalPixelDegrees*.5);
 float demAmount=demWeight(geo,demStep);
 if(terrainTreatment==1&&inside>.5){
  float y=max(lum(source),.002);
  // Shadow-side only: never lift NE1's already bright desert/highlights.
  surface*=pow(min(y/.80,1.),.50);
  // Limit the Gate1A amplification of baked shadows. This does NOT claim to
  // reconstruct true albedo or remove NE1's original embedded hillshade.
  if(demAmount>0.&&demBakedSuppression>0.)surface/=pow(min(y/.80,1.),.50*demBakedSuppression*demAmount);
 }
 vec3 land=surface;
 if(mode!=1&&mode!=6&&mode!=7)land=mix(land,terrainMaterial(surface,primaryHue,primaryStrength,stage)*primaryLuminance,p);
 if(mode!=1&&mode!=6&&mode!=7)land=mix(land,terrainMaterial(surface,secondaryHue,secondaryStrength,stage)*secondaryLuminance,s);
 // Existing 2K topology: RELIEF PROXY, not a new DEM. NE1 already has baked hillshade.
 vec2 dt=vec2(1./2048.,1./1024.);
 float dx=texture(topo,guv+vec2(dt.x,0.)).r-texture(topo,guv-vec2(dt.x,0.)).r;
 float dy=texture(topo,guv+vec2(0.,dt.y)).r-texture(topo,guv-vec2(0.,dt.y)).r;
 vec3 normal=normalize(vec3(-dx*reliefStrength,-dy*reliefStrength,1.));
 float light=.72+.28*max(dot(normal,normalize(vec3(-.55,.65,1.))),0.);
 // A second unregistered, coarse proxy light would relight baked shading.
 // Retain the original flat-surface irradiance, not a second directional light.
 if(terrainTreatment==1&&inside>.5)light=.72+.28*dot(vec3(0.,0.,1.),normalize(vec3(-.55,.65,1.)));
 if(demAmount>0.){
  vec3 dn=demNormal(geo,demStep),dl=normalize(vec3(-.55,.65,1.));
  float slopeLight=.72+.28*max(dot(dn,dl),0.);
  if(demCorrectedLight==1){
   dl=normalize(vec3(-.65,.70,.60));
   // Change slope readability, retaining the Gate1A flat-surface irradiance.
   // Preserve flat irradiance and the original 2x DEM normals. Reduce the
   // ambient wash so existing gentle/higher slopes retain directional shading.
   if(stage>=4)slopeLight=(.30+.70*max(dot(dn,dl),0.))/(.30+.70*dl.z)*(.72+.28*normalize(vec3(-.55,.65,1.)).z);
   else slopeLight=(.42+.58*max(dot(dn,dl),0.))/(.42+.58*dl.z)*(.72+.28*normalize(vec3(-.55,.65,1.)).z);
   // NE1 desert is already bright: express real slope shadows without lifting
   // baked highlights into gamut clipping. No synthetic emboss/sharpening.
   if(stage==0)slopeLight=min(slopeLight,.72+.28*normalize(vec3(-.55,.65,1.)).z);
  }
  light=mix(light,slopeLight,demAmount);
  if(mode==10){frag=vec4(dn*.5+.5,1.);return;}
 }
 if(mode==9){frag=vec4(vec3(demAmount),1.);return;}
 if(mode==10){frag=vec4(.5,.5,1.,1.);return;}
 if(mode==7){frag=vec4(vec3(shadingStage>0?light/2.:light),1.);return;}
 // Controlled flat-normal ablation retains exposure and the output transfer.
 if(mode==6||mode==8)light=.72+.28*dot(vec3(0.,0.,1.),normalize(vec3(-.55,.65,1.)));
 land*=light*exposure;
 // Sea retains actual raster surface variation; receives NO country chroma.
 vec3 sea=linearize(vec3(.012,.10,.19))*(.65+2.*pow(max(lum(source),.001),.4));
 vec3 color=mix(sea,land,cov.r);
 if(mode==2){frag=vec4(color,1.);return;}
 vec3 originalColor=color/(1.+color*.70);
 if(stage>=3){
  // The correction belongs to land material only; sea remains identical.
  vec3 corrected=terrainOutput(land,stage);
  vec3 originalSea=sea/(1.+sea*.70);
  color=mix(originalSea,corrected,cov.r);
 }else color=originalColor;
 frag=vec4(encode(clamp(color,0.,1.)),1.);
}`;
const ribbonVertex = `precision highp float;
uniform mat4 projectionMatrix,modelViewMatrix;
uniform vec2 resolution; uniform float width;
in vec3 position; in vec2 tangent; in float side;out float edgeCoord;
void main(){
 vec4 clip=projectionMatrix*modelViewMatrix*vec4(position,1.);
 vec4 next=projectionMatrix*modelViewMatrix*vec4(position+vec3(tangent,0.),1.);
 vec2 dir=normalize((next.xy/next.w-clip.xy/clip.w)*resolution);
 vec2 normal=vec2(-dir.y,dir.x);
 clip.xy+=normal*side*width/resolution*clip.w;
 edgeCoord=side;gl_Position=clip;
}`;
const rgbaFragment = `precision highp float; uniform vec4 color;in float edgeCoord; out vec4 frag;
void main(){float aa=1.-smoothstep(1.-fwidth(edgeCoord),1.,abs(edgeCoord));frag=vec4(color.rgb,color.a*aa);}`;
const panelFragment = `precision highp float;in vec2 vUv;out vec4 frag;
void main(){vec2 q=abs(vUv-.5)-vec2(.48,.40);float d=length(max(q,0.))+min(max(q.x,q.y),0.)-.02;
 float a=1.-smoothstep(-.003,.003,d);frag=vec4(.012,.027,.038,a*.86);}`;
const blurFragment = `precision highp float; in vec2 vUv; out vec4 frag;
uniform sampler2D inputTexture; uniform vec2 direction;
void main(){
 vec4 c=texture(inputTexture,vUv)*.227027;
 c+=(texture(inputTexture,vUv+direction*1.384615)+texture(inputTexture,vUv-direction*1.384615))*.316216;
 c+=(texture(inputTexture,vUv+direction*3.230769)+texture(inputTexture,vUv-direction*3.230769))*.070270;
 frag=c;
}`;
const compositeFragment = `precision highp float; in vec2 vUv; out vec4 frag;
uniform sampler2D baseTexture,glowTexture; uniform float gain;
void main(){vec4 b=texture(baseTexture,vUv),g=texture(glowTexture,vUv);frag=vec4(b.rgb+g.rgb*gain,1.);}`;
const markerFragment = `precision highp float; in vec2 vUv; out vec4 frag;
void main(){
 float r=length((vUv-.5)*2.);
 float outer=1.-smoothstep(.87,.93,r);
 float ring=smoothstep(.48,.53,r)*(1.-smoothstep(.69,.74,r));
 float core=1.-smoothstep(.32,.37,r);
 vec3 c=mix(vec3(.025,.045,.06),vec3(1.),ring);
 c=mix(c,vec3(.96,.29,.16),core);frag=vec4(c,outer);
}`;
const textFragment = `precision highp float; in vec2 vUv; out vec4 frag;
uniform sampler2D glyph; uniform vec2 texel; uniform vec3 color;
void main(){
 float a=texture(glyph,vUv).a,edge=a;
 for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++)edge=max(edge,texture(glyph,vUv+vec2(float(x),float(y))*texel).a);
 frag=vec4(mix(vec3(.015,.032,.045),color,a),edge);
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
function mat(vertexShader,fragmentShader,uniforms,transparent=false){
 return new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader,fragmentShader,uniforms,
  transparent,depthTest:false,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});
}
function quad(material){return new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);}
function fullScene(material){const s=new THREE.Scene();s.add(quad(material));return s;}
async function texture(url){
 const t=await new THREE.TextureLoader().loadAsync(url);
 // Shader owns sRGB decode/encode explicitly. No browser/Three double conversion.
 t.colorSpace=THREE.NoColorSpace;t.minFilter=THREE.LinearMipmapLinearFilter;
 t.magFilter=THREE.LinearFilter;t.generateMipmaps=true;return t;
}
export function polygons(record){
 if(record.geometry_type==='Polygon')return [record.coordinates];
 if(record.geometry_type==='MultiPolygon')return record.coordinates;
 throw Error(`No polygon coverage for ${record.geometry_type}`);
}
export function triangulateRegion(record,project){
 const shapes=[],rings=[];
 for(const polygon of polygons(record)){
  const points=polygon[0].slice(0,-1).map(p=>new THREE.Vector2(...project(p)));
  if(points.length<3)throw Error('Degenerate verified polygon');
  const shape=new THREE.Shape(points);rings.push(polygon[0].map(project));
  for(const hole of polygon.slice(1)){
   shape.holes.push(new THREE.Path(hole.slice(0,-1).map(p=>new THREE.Vector2(...project(p)))));
   rings.push(hole.map(project));
  }
  shapes.push(shape);
 }
 return {mesh:new THREE.ShapeGeometry(shapes),rings};
}
function ribbon(rings){
 const pos=[],tan=[],side=[],idx=[];
 for(const ring of rings){
  const closed=ring.closed!==false,pts=closed?ring.slice(0,-1):ring,offset=pos.length/3;
  if(pts.length<2)continue;
  const last=closed?pts.length:pts.length-1;
  for(let i=0;i<=last;i++){
   const a=pts[closed?(i+pts.length-1)%pts.length:Math.max(0,i-1)],b=pts[i%pts.length],c=pts[closed?(i+1)%pts.length:Math.min(pts.length-1,i+1)];
   const dx=c[0]-a[0],dy=c[1]-a[1],l=Math.hypot(dx,dy)||1;
   for(const sign of [-1,1]){pos.push(b[0],b[1],0);tan.push(dx/l,dy/l);side.push(sign);}
   if(i<last){const k=offset+i*2;idx.push(k,k+1,k+2,k+2,k+1,k+3);}
  }
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
 g.setAttribute('tangent',new THREE.Float32BufferAttribute(tan,2));g.setAttribute('side',new THREE.Float32BufferAttribute(side,1));
 g.setIndex(idx);return g;
}
export async function createMapInfographicRenderer({canvas,plan,width=1080,height=1920,terrainTreatment='BAKED_RELIEF_V1',heightSource=null,outputRenderer=null,outputTarget=null,layoutPlan=null,contextTerrain=null,contextGeometries=[]}){
 assertLocalDetailAdmission(plan,heightSource);
 console.info('GATE1: factory start');
 if(width/height!==1080/1920)throw Error('Canonical 9:16 layout required');
 const gl=outputRenderer?outputRenderer.getContext():canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WebGL2 required; no fake preview fallback');
 const renderer=outputRenderer??new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 if(!outputRenderer){renderer.setPixelRatio(1);renderer.setSize(width,height,false);}renderer.autoClear=false;
 if(outputTarget&&(outputTarget.width!==width||outputTarget.height!==height))throw Error('Explicit output target must match canonical output resolution');
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const scale=width/1080,b=plan.framing.bounds,c=(b[0]+b[2])/2,lat=(b[1]+b[3])/2,cos=Math.cos(lat*Math.PI/180);
 const isGlobe=plan.framing.projection==='WORLD_GLOBE_ORTHOGRAPHIC';
 if(contextTerrain){
  const cb=contextTerrain.bounds;
  if(isGlobe)throw Error('Continuous terrain source LOD requires the admitted flat map projection');
  if(!Array.isArray(cb)||cb.length!==4||!cb.every(Number.isFinite)||cb[2]<=cb[0]||cb[3]<=cb[1]||typeof contextTerrain.url!=='string')throw Error('Context terrain requires a real geographic source descriptor');
  if(terrainTreatment==='BAKED_RELIEF_V1'&&contextTerrain.classification!=='BAKED HILLSHADE')throw Error('Context source must retain the admitted baked-hillshade classification');
 }
 if(!Array.isArray(contextGeometries))throw Error('Context geometry must be verified country records');
 const sourceGeometryIds=new Set(plan.geometries.map(record=>record.id));
 const extraContext=[];
 for(const record of contextGeometries){
  if(!record||typeof record.id!=='string')throw Error('Context geometry requires a source GIS ID');
  if(sourceGeometryIds.has(record.id))continue;
  polygons(record);sourceGeometryIds.add(record.id);extraContext.push(record);
 }
 const globeOptions={center:plan.framing.center??plan.anchor.coordinates,canonical:[1080,1920],
  diameter:(plan.framing.globe?.diameterFraction??.88)*1080,screenCenter:plan.framing.globe?.centerCanonical??[1080/2,1920/2]};
 const globeScreen=isGlobe?createGlobeProjection(globeOptions):null;
 const project=isGlobe?p=>p:p=>[(p[0]-c)*cos,p[1]-lat];
 const camera=isGlobe?new THREE.OrthographicCamera(-180,180,90,-90,.1,10):
  new THREE.OrthographicCamera(-(b[2]-b[0])*cos/2,(b[2]-b[0])*cos/2,(b[3]-b[1])/2,-(b[3]-b[1])/2,.1,10);
 camera.position.z=5;camera.updateMatrixWorld();
 const screen=globeScreen??(p=>{const [x,y]=project(p);const v=new THREE.Vector3(x,y,0).project(camera);return [(v.x*.5+.5)*1080,(.5-v.y*.5)*1920];});
 const lineCamera=isGlobe?new THREE.OrthographicCamera(0,1080,0,1920,.1,10):camera;
 if(isGlobe){lineCamera.position.z=5;lineCamera.updateMatrixWorld();}
 const fsCamera=new THREE.Camera(),idScene=new THREE.Scene(),covScene=new THREE.Scene();
 const roleLUT=new Uint8Array(256*4),primaryRings=[],secondaryRings=[],primaryCoverage=[];let gid=0;
 const geometryEvidence=[];
 for(const record of [...plan.geometries,...extraContext]){
  gid++;if(gid>=256)throw Error('Gate1 region LUT capacity exceeded');
  const role=record.id===plan.primary?2:plan.secondary.includes(record.id)?1:0;
  roleLUT[gid*4]=role;
  const isContext=extraContext.includes(record);
  const g=triangulateRegion(isGlobe||plan.scale?.name==='CONTINENT'||isContext?geographicAtlasRecord(record):record,project),idColor=new THREE.Vector3(gid/255,0,0);
  idScene.add(new THREE.Mesh(g.mesh,mat(geoVertex,flatFragment,{value:{value:idColor}})));
  const coverageMaterial=mat(geoVertex,flatFragment,{value:{value:new THREE.Vector3(1,role===1?1:0,role===2?1:0)}});
  covScene.add(new THREE.Mesh(g.mesh,coverageMaterial));if(role===2)primaryCoverage.push(coverageMaterial);
  if(role===2)primaryRings.push(...g.rings);if(role===1)secondaryRings.push(...g.rings);
  geometryEvidence.push({id:record.id,gpuID:gid,role,triangles:g.mesh.index.count/3,parts:polygons(record).length,holes:polygons(record).reduce((s,p)=>s+p.length-1,0)});
 }
 if(isGlobe){
  primaryRings.splice(0,primaryRings.length,...globeBoundaryRings(plan.geometries,r=>r.id===plan.primary,globeScreen));
  secondaryRings.splice(0,secondaryRings.length,...globeBoundaryRings(plan.geometries,r=>plan.secondary.includes(r.id),globeScreen));
 }
 const targets=[];
 function target(samples=0,nearest=false,dimensions=[width,height]){const t=new THREE.WebGLRenderTarget(...dimensions,{samples,depthBuffer:false,
  minFilter:nearest?THREE.NearestFilter:THREE.LinearFilter,magFilter:nearest?THREE.NearestFilter:THREE.LinearFilter});targets.push(t);return t;}
 const gisDimensions=isGlobe?[4096,2048]:[width,height];
 const idTarget=target(0,true,gisDimensions),covTarget=target(Math.min(4,renderer.capabilities.maxSamples),false,gisDimensions),baseTarget=target(),glowTarget=target(),blurTarget=target(),glowFinal=target();
 function draw(scene,cam,targetValue,clear=true){renderer.setRenderTarget(targetValue);if(clear){renderer.setClearColor(0,0);renderer.clear();}renderer.render(scene,cam);}
 draw(idScene,camera,idTarget);draw(covScene,camera,covTarget);
 console.info('GATE1: GIS targets drawn');
 const lut=new THREE.DataTexture(roleLUT,256,1,THREE.RGBAFormat);lut.minFilter=lut.magFilter=THREE.NearestFilter;lut.needsUpdate=true;
 const [regional,global,topo,wide]=await Promise.all([texture(plan.assets.terrain.url),texture(plan.assets.global.url),texture(plan.assets.topo.url),contextTerrain?texture(contextTerrain.url):Promise.resolve(null)]);
 const ownedTextures=[regional,global,topo,lut];if(wide)ownedTextures.push(wide);
 console.info('GATE1: terrain sources loaded');
 const anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());for(const t of [regional,global,topo,...(wide?[wide]:[])])t.anisotropy=anisotropy;
 const theme=plan.theme;
 if(!['CURRENT','BAKED_RELIEF_V1'].includes(terrainTreatment))throw Error('Unknown terrain treatment');
 if(terrainTreatment==='BAKED_RELIEF_V1'&&plan.assets.terrain.classification!=='BAKED HILLSHADE')throw Error('Baked-relief treatment requires admitted baked hillshade');
 let heightTexture=new THREE.DataTexture(new Float32Array([0]),1,1,THREE.RedFormat,THREE.FloatType),heightEvidence=null;
 if(heightSource){
  const h=heightSource;
  if(h.CRS!=='EPSG:4326'||h.unit!=='m'||h.scale!==1||h.offset!==0||h.NoData!==null)throw Error('Height source requires admitted metre Float32 grid with no missing samples');
  if(h.dimensions.some(v=>!Number.isInteger(v)||v<2||v>renderer.capabilities.maxTextureSize))throw Error('Height grid exceeds actual WebGL2 capability');
  const response=await fetch(h.url);if(!response.ok)throw Error('Height source unavailable');
  const bytes=await response.arrayBuffer();
  if(bytes.byteLength!==h.dimensions[0]*h.dimensions[1]*4)throw Error('Height source byte length mismatch');
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
  if(digest!==h.sha256)throw Error('Height source hash mismatch');
  const heights=new Float32Array(bytes);if(!heights.every(Number.isFinite))throw Error('Height source contains unadmitted NoData');
  heightTexture.dispose();heightTexture=new THREE.DataTexture(heights,...h.dimensions,THREE.RedFormat,THREE.FloatType);
  heightEvidence={...h,format:'R32F',precision:'IEEE754 Float32 metres',filter:'NEAREST / explicit manual bilinear',
   sampling:'3x3 sparse footprint-aware height sampling (not exact area integration); geographic central derivatives across shared atlas; WGS84 east/north distances',
   outsideCoverage:'Exact Gate1A terrain path; no invented elevation',gpuBytes:bytes.byteLength};
 }
 heightTexture.internalFormat='R32F';heightTexture.flipY=false;heightTexture.generateMipmaps=false;
 heightTexture.minFilter=heightTexture.magFilter=THREE.NearestFilter;heightTexture.needsUpdate=true;ownedTextures.push(heightTexture);
 const uniforms={terrain:{value:regional},globalTerrain:{value:global},topo:{value:topo},regionID:{value:idTarget.texture},coverage:{value:covTarget.texture},roles:{value:lut},
  contextTerrain:{value:wide??regional},contextTileBounds:{value:new THREE.Vector4(...(contextTerrain?.bounds??plan.assets.terrain.bounds))},contextTerrainEnabled:{value:contextTerrain?1:0},terrainLodWeight:{value:1},
  globeProjection:{value:isGlobe?1:0},globeDisc:{value:new THREE.Vector4(globeOptions.screenCenter[0]/1080,1-globeOptions.screenCenter[1]/1920,globeOptions.diameter/2160,globeOptions.diameter/3840)},
  globeEast:{value:new THREE.Vector3(...globeBasis(globeOptions.center).east)},globeNorth:{value:new THREE.Vector3(...globeBasis(globeOptions.center).north)},globeCenter:{value:new THREE.Vector3(...globeBasis(globeOptions.center).center)},
  demHeight:{value:heightTexture},demFirstSample:{value:new THREE.Vector2(...(heightSource?.firstSample??[0,0]))},demSpacing:{value:new THREE.Vector2(...(heightSource?.pixelSpacing??[1,1]))},
  demDimensions:{value:new THREE.Vector2(...(heightSource?.dimensions??[1,1]))},canonicalPixelDegrees:{value:new THREE.Vector2((b[2]-b[0])/1080,(b[3]-b[1])/1920)},
  demEnabled:{value:heightSource?1:0},demCorrectedLight:{value:0},demExaggeration:{value:1},demBakedSuppression:{value:0},
  shadingStage:{value:0},
  bounds:{value:new THREE.Vector4(...b)},tileBounds:{value:new THREE.Vector4(...plan.assets.terrain.bounds)},
  primaryHue:{value:new THREE.Vector3(...theme.primary)},secondaryHue:{value:new THREE.Vector3(...theme.secondary)},
  primaryStrength:{value:theme.primaryStrength},secondaryStrength:{value:theme.secondaryStrength},primaryLuminance:{value:theme.primaryLuminance??1},secondaryLuminance:{value:theme.secondaryLuminance??1},detailContrast:{value:theme.detailContrast??1},reliefStrength:{value:theme.relief},exposure:{value:theme.exposure},mode:{value:0},terrainTreatment:{value:terrainTreatment==='CURRENT'?0:1}};
 const terrainMaterial=mat(fullscreenVertex,terrainFragment,uniforms),terrainScene=fullScene(terrainMaterial);
 const primaryGeometry=ribbon(primaryRings),secondaryGeometry=ribbon(secondaryRings),boundaryScene=new THREE.Scene(),glowScene=new THREE.Scene();
 function line(scene,g,pixels,color){const material=mat(ribbonVertex,rgbaFragment,{resolution:{value:new THREE.Vector2(width,height)},width:{value:pixels*scale},color:{value:new THREE.Vector4(...color)}},true);const mesh=new THREE.Mesh(g,material);scene.add(mesh);return mesh;}
 // Boundary-only tokens. Absent tokens reproduce the approved previous style.
 // Terrain material, GIS paths and every pixel shader remain independent.
 const boundaryStyle={primaryWidth:theme.primaryWidth,secondaryWidth:theme.secondaryWidth,
  primaryEdgeWidth:theme.primaryEdgeWidth??theme.primaryWidth+2,secondaryEdgeWidth:theme.secondaryEdgeWidth??theme.secondaryWidth+2,
  primaryCoreColor:theme.primaryCoreColor??[1,.97,.80,1],secondaryCoreColor:theme.secondaryCoreColor??[.43,.87,.82,.93],
  primaryEdgeColor:theme.primaryEdgeColor??[.17,.10,.03,.72],secondaryEdgeColor:theme.secondaryEdgeColor??[.02,.10,.12,.78],
  glowWidth:theme.glowWidth??theme.primaryWidth+3,glowColor:theme.glowColor??[.88,.52,.07,1],glowRadius:theme.glowRadius,glowGain:theme.glowGain};
 const boundaryLayers=[
  {mesh:line(boundaryScene,secondaryGeometry,boundaryStyle.secondaryEdgeWidth,boundaryStyle.secondaryEdgeColor),width:'secondaryEdgeWidth',role:'SECONDARY',alpha:boundaryStyle.secondaryEdgeColor[3]},
  {mesh:line(boundaryScene,secondaryGeometry,boundaryStyle.secondaryWidth,boundaryStyle.secondaryCoreColor),width:'secondaryWidth',role:'SECONDARY',alpha:boundaryStyle.secondaryCoreColor[3]},
  {mesh:line(boundaryScene,primaryGeometry,boundaryStyle.primaryEdgeWidth,boundaryStyle.primaryEdgeColor),width:'primaryEdgeWidth',role:'PRIMARY',alpha:boundaryStyle.primaryEdgeColor[3]},
  {mesh:line(boundaryScene,primaryGeometry,boundaryStyle.primaryWidth,boundaryStyle.primaryCoreColor),width:'primaryWidth',role:'PRIMARY',alpha:boundaryStyle.primaryCoreColor[3]},
  {mesh:line(glowScene,primaryGeometry,boundaryStyle.glowWidth,boundaryStyle.glowColor),width:'glowWidth',role:'PRIMARY',alpha:boundaryStyle.glowColor[3]}
 ];
 let activeGlowRadius=theme.glowRadius,activeGlowGain=theme.glowGain,primaryReveal=1;
 const blur=mat(fullscreenVertex,blurFragment,{inputTexture:{value:glowTarget.texture},direction:{value:new THREE.Vector2()}}),blurScene=fullScene(blur);
 const composite=mat(fullscreenVertex,compositeFragment,{baseTexture:{value:baseTarget.texture},glowTexture:{value:glowFinal.texture},gain:{value:theme.glowGain}}),compositeScene=fullScene(composite);
 const graphicsCamera=new THREE.OrthographicCamera(0,1080,0,1920,.1,10);graphicsCamera.position.z=5;graphicsCamera.updateMatrixWorld();
 const graphicScene=new THREE.Scene(),layout=[],glyphExports=[],graphicRoles=[];
 const graphicPlan=layoutPlan??plan;
 // Camera motion freezes one measured final layout. This is the SAME layout
 // algorithm and glyph source; no per-frame label reflow or alternate renderer.
 const layoutBounds=graphicPlan.framing.bounds;
 const layoutScreen=layoutPlan&&!isGlobe?p=>[(p[0]-layoutBounds[0])/(layoutBounds[2]-layoutBounds[0])*1080,(layoutBounds[3]-p[1])/(layoutBounds[3]-layoutBounds[1])*1920]:screen;
 let layoutValidation={version:'LEGACY_FIXED_LAYOUT'};
 if(graphicPlan.layout.measured){
  const font=new FontFace('Gate1Bold',`url(${plan.assets.font.url})`);await font.load();document.fonts.add(font);
  console.info('GATE1: pinned CJK font loaded for measured layout');
  const result=buildMeasuredGraphicLayout({plan:graphicPlan,screen:layoutScreen,measure:createMeasuredGlyph});layoutValidation=result.validation;
  if(!layoutValidation.valid)throw Error('MEASURED_LAYOUT_INVALID: '+JSON.stringify(layoutValidation));
  for(const item of result.items){
   const box=item.box;let material;
   if(item.kind==='MARKER')material=mat(graphicVertex,markerFragment,{},true);
   else if(item.kind==='PANEL')material=mat(graphicVertex,measuredPanelFragment,{panelSize:{value:new THREE.Vector2(box[2],box[3])},opacity:{value:item.opacity}},true);
   else if(item.kind==='TEXT'){
    const m=item.metrics,atlas=m.canvas,tex=new THREE.CanvasTexture(atlas);
    tex.flipY=false;tex.colorSpace=THREE.NoColorSpace;tex.generateMipmaps=false;tex.minFilter=tex.magFilter=THREE.LinearFilter;ownedTextures.push(tex);
    const colors={EVENT_TITLE:[1,.97,.86],LOCATION_LABEL:[1,1,1],COUNTRY:[.89,.94,.90],SCENARIO_DISCLOSURE:[.9,.94,.96]};
    material=mat(graphicVertex,measuredTextFragment,{glyph:{value:tex},texel:{value:new THREE.Vector2(1/atlas.width,1/atlas.height)},color:{value:new THREE.Vector3(...colors[item.role])},outlineRadius:{value:m.outlineRadius}},true);
    const name=`glyph-atlas-${item.role}-${glyphExports.length}.png`;
    glyphExports.push({name,dataURL:atlas.toDataURL('image/png')});
    const {canvas:unused,...metrics}=m;
    layout.push({...item,metrics:undefined,...metrics,glyphAtlasFile:name,fontSha256:plan.assets.font.sha256});
   }else throw Error('Unknown explicit graphic item');
   const mesh=new THREE.Mesh(new THREE.PlaneGeometry(box[2],box[3]),material);mesh.position.set(box[0]+box[2]/2,box[1]+box[3]/2,0);graphicScene.add(mesh);graphicRoles.push({mesh,role:item.role,size:item.kind==='MARKER'?box[2]:null});
   if(item.kind!=='TEXT')layout.push({...item});
  }
 }else{
 if(plan.layout.titlePanel){
  const box=plan.layout.titlePanel,m=new THREE.Mesh(new THREE.PlaneGeometry(box[2],box[3]),mat(graphicVertex,panelFragment,{},true));
  m.position.set(box[0]+box[2]/2,box[1]+box[3]/2,0);graphicScene.add(m);graphicRoles.push({mesh:m,role:'TITLE_CONTRAST_PANEL'});layout.push({role:'TITLE_CONTRAST_PANEL',box});
 }
 const anchor=screen(plan.anchor.coordinates),markerSize=plan.layout.markerSize;
 const markerMaterial=mat(graphicVertex,markerFragment,{},true);
 const marker=new THREE.Mesh(new THREE.PlaneGeometry(markerSize,markerSize),markerMaterial);marker.position.set(...anchor,0);graphicScene.add(marker);graphicRoles.push({mesh:marker,role:'MARKER',size:markerSize});
 layout.push({role:'MARKER',box:[anchor[0]-markerSize/2,anchor[1]-markerSize/2,markerSize,markerSize],anchor});
 const font=new FontFace('Gate1Bold',`url(${plan.assets.font.url})`);await font.load();document.fonts.add(font);
 console.info('GATE1: font loaded');
 async function text(value,role,x,y,size,color){
  const atlas=document.createElement('canvas'),ctx=atlas.getContext('2d');ctx.font=`${size}px Gate1Bold`;
  const tw=Math.ceil(ctx.measureText(value).width),pad=10;atlas.width=tw+pad*2;atlas.height=Math.ceil(size*1.65)+pad*2;
  ctx.font=`${size}px Gate1Bold`;ctx.textBaseline='top';ctx.fillStyle='white';ctx.fillText(value,pad,pad);
  const tex=new THREE.CanvasTexture(atlas);tex.flipY=false;tex.colorSpace=THREE.NoColorSpace;tex.generateMipmaps=false;tex.minFilter=tex.magFilter=THREE.LinearFilter;
  ownedTextures.push(tex);
  const m=mat(graphicVertex,textFragment,{glyph:{value:tex},texel:{value:new THREE.Vector2(1/atlas.width,1/atlas.height)},color:{value:new THREE.Vector3(...color)}},true);
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(atlas.width,atlas.height),m);mesh.position.set(x+atlas.width/2,y+atlas.height/2,0);graphicScene.add(mesh);graphicRoles.push({mesh,role});
  layout.push({role,text:value,box:[x,y,atlas.width,atlas.height]});
 }
 await text(plan.text.eventTitle,'EVENT_TITLE',plan.layout.title[0],plan.layout.title[1],plan.layout.titleSize,[1,.97,.86]);
 await text(plan.text.locationLabel,'LOCATION_LABEL',anchor[0]+plan.layout.locationOffset[0],anchor[1]+plan.layout.locationOffset[1],plan.layout.locationSize,[1,1,1]);
 if(plan.text.watermark)await text(plan.text.watermark,'SCENARIO_DISCLOSURE',60,1785,26,[.9,.94,.96]);
 // Country names are verified registry data, not invented place labels.
 for(const label of plan.layout.countryLabels)await text(label.text,'COUNTRY',...screen(label.coordinates),label.size,[.89,.94,.90]);
 }
 const debugExt=gl.getExtension('WEBGL_debug_renderer_info');
 const evidence={renderer:VERSION,shader:SHADER_VERSION,theme:THEME_VERSION,regionColorProfile:theme.visualColorProfile??'LEGACY_REGION_COLORS',
  boundaryGlowProfile:theme.visualBoundaryProfile??'LEGACY_BOUNDARY_GLOW',boundaryGlowParameters:boundaryStyle,
  regionMaterialParameters:{primaryHue:theme.primary,secondaryHue:theme.secondary,primaryStrength:theme.primaryStrength,secondaryStrength:theme.secondaryStrength,
   primaryLuminance:theme.primaryLuminance??1,secondaryLuminance:theme.secondaryLuminance??1,neutral:'UNCHANGED_SOURCE_TERRAIN'},dimensions:[width,height],
  context:'webgl2',vendor:gl.getParameter(gl.VENDOR),glRenderer:gl.getParameter(gl.RENDERER),
  unmaskedRenderer:debugExt?gl.getParameter(debugExt.UNMASKED_RENDERER_WEBGL):null,
  maxTextureSize:renderer.capabilities.maxTextureSize,anisotropy,coverageSamples:covTarget.samples,
  projection:isGlobe?'Orthographic globe; inverse sphere geographic sampling, same terrain material':'Regional equirectangular, standard parallel at framing center',bounds:b,
  scaleContract:plan.scale??null,gisTargetDimensions:gisDimensions,visibleHemisphere:isGlobe?globeOptions:null,
  geometry:geometryEvidence,layout,layoutValidation,terrainTreatment,heightSource:heightEvidence,sourceRelief:heightSource?'Copernicus GLO-30 real DSM height inside admitted footprint only; NE1 baked hillshade + Gate1A outside':terrainTreatment==='CURRENT'?'NE1 BAKED HILLSHADE + original 2K RELIEF PROXY; no new DEM':'NE1 BAKED HILLSHADE; source luminance curve, single baked illumination; no DEM or invented height; global proxy outside regional tile only',
  graph:['GPU region ID (NEAREST, no MSAA)','GPU role/land AA coverage (separate MSAA target)','terrain RGB linear decode -> region material -> relief/light -> sea -> output transfer',
   'primary ribbon glow target -> separable blur','GPU base + glow composite','GPU screen-space boundary core/edge','GPU marker','GPU glyph texture quads'],
  canvasUse:'glyph atlas preparation ONLY; no final-frame Canvas 2D compositing',finalApproval:'USER_PENDING',nvidia:'NOT_RUN'};
 if(contextTerrain)evidence.terrainLod={weight:1,wideSource:{sha256:contextTerrain.sha256??null,bounds:[...contextTerrain.bounds],dimensions:contextTerrain.dimensions??null},regionalSource:{sha256:plan.assets.terrain.sha256??null,bounds:[...plan.assets.terrain.bounds],dimensions:plan.assets.terrain.dimensions??null},contextGeometryIds:extraContext.map(record=>record.id),method:'Geographic raw terrain RGB source sampling before the unchanged linear decode/material/lighting; real-source coverage only; no completed-frame transition'};
 const revealDefaults={primary:1,marker:1,location:1,country:1,title:1,disclosure:1};
 let currentReveal={...revealDefaults},currentBounds=[...b];
 function setReveal(reveal=null){
  const next={...revealDefaults,...reveal};
  if(reveal&&Object.hasOwn(reveal,'eventTitle'))next.title=reveal.eventTitle;
  for(const key of Object.keys(revealDefaults))if(!Number.isFinite(next[key])||next[key]<0||next[key]>1)throw Error('Reveal factors must be finite values in [0,1]');
  if(next.primary!==primaryReveal){
   primaryReveal=next.primary;
   for(const material of primaryCoverage)material.uniforms.value.value.z=primaryReveal;
   draw(covScene,camera,covTarget);
   for(const layer of boundaryLayers)if(layer.role==='PRIMARY')layer.mesh.material.uniforms.color.value.w=layer.alpha*primaryReveal;
  }
  const roles={MARKER:'marker',LOCATION_LABEL:'location',COUNTRY:'country',EVENT_TITLE:'title',TITLE_CONTRAST_PANEL:'title',SCENARIO_DISCLOSURE:'disclosure'};
  // V1 Marker/Text reveal is an explicit appearance step (>0), not a fade.
  // Primary coverage/ribbons/glow alone accept fractional reveal strength.
  for(const item of graphicRoles)item.mesh.visible=next[roles[item.role]??'title']>0;
  currentReveal=Object.fromEntries(Object.keys(revealDefaults).map(k=>[k,next[k]]));
 }
 function updateCamera(nextBounds){
  if(isGlobe)throw Error('Flat camera updates are not a globe projection transition');
  if(!Array.isArray(nextBounds)||nextBounds.length!==4||!nextBounds.every(Number.isFinite)||nextBounds[2]<=nextBounds[0]||nextBounds[3]<=nextBounds[1]||nextBounds[1]<-90||nextBounds[3]>90)throw Error('Invalid geographic camera extent');
  const closestPlan=layoutPlan??(plan.scale?.name==='REGIONAL'?plan:null);
  if(closestPlan){
   // An explicit locked Regional endpoint is also the closest admitted extent.
   // Camera interpolation may approach it but must never create a denied Local.
   const minimum=closestPlan.framing.bounds;
   if(nextBounds[2]-nextBounds[0]<(minimum[2]-minimum[0])-1e-9||nextBounds[3]-nextBounds[1]<(minimum[3]-minimum[1])-1e-9)throw Object.assign(Error('Camera extent exceeds the admitted locked endpoint'),{code:'LOCAL_NOT_ADMITTED',category:'DATA_ADMISSION'});
  }
  const [west,south,east,north]=nextBounds;
  camera.left=-(east-west)*cos/2;camera.right=(east-west)*cos/2;camera.top=(north-south)/2;camera.bottom=-(north-south)/2;
  camera.position.set(((west+east)/2-c)*cos,(south+north)/2-lat,5);camera.updateProjectionMatrix();camera.updateMatrixWorld();
  uniforms.bounds.value.set(...nextBounds);uniforms.canonicalPixelDegrees.value.set((east-west)/1080,(north-south)/1920);
  currentBounds=[...nextBounds];draw(idScene,camera,idTarget);draw(covScene,camera,covTarget);
  evidence.cameraFrame={projection:plan.framing.projection,bounds:[...currentBounds],center:[(west+east)/2,(south+north)/2],anchorCanonical:screen(plan.anchor.coordinates),layoutFrozen:!!layoutPlan};
  return evidence.cameraFrame;
 }
 function setScaleVisual(tokens={}){
  const keys=['primaryWidth','secondaryWidth','primaryEdgeWidth','secondaryEdgeWidth','glowWidth','glowRadius','glowGain','markerSize'];
  for(const key of Object.keys(tokens))if(!keys.includes(key)||!Number.isFinite(tokens[key])||tokens[key]<0)throw Error('Camera scale adjustment accepts existing width/size tokens only');
  for(const layer of boundaryLayers)if(Object.hasOwn(tokens,layer.width)){
   boundaryStyle[layer.width]=tokens[layer.width];layer.mesh.material.uniforms.width.value=tokens[layer.width]*scale;
  }
  if(Object.hasOwn(tokens,'glowRadius')){activeGlowRadius=tokens.glowRadius;boundaryStyle.glowRadius=activeGlowRadius;}
  if(Object.hasOwn(tokens,'glowGain')){activeGlowGain=tokens.glowGain;boundaryStyle.glowGain=activeGlowGain;}
  if(Object.hasOwn(tokens,'markerSize'))for(const item of graphicRoles)if(item.role==='MARKER')item.mesh.scale.set(tokens.markerSize/item.size,tokens.markerSize/item.size,1);
 }
 function setTerrainLod(weight){
  if(!Number.isFinite(weight)||weight<0||weight>1)throw Error('Terrain LOD weight must be finite in [0,1]');
  if(!contextTerrain&&weight!==1)throw Error('No admitted geographic context terrain source');
  uniforms.terrainLodWeight.value=weight;
  if(evidence.terrainLod)evidence.terrainLod.weight=weight;
 }
 function renderFrame({mode=0,graphics=true,boundaries=true,glow=true,dem=!!heightSource,correctedLight=false,verticalExaggeration=1,bakedSuppression=0,shadingCorrection='BASELINE',reveal=null,finish=false,log=false}={}){
  if(contextTerrain&&uniforms.terrainLodWeight.value===1){
   const tile=plan.assets.terrain.bounds;
   if(currentBounds[0]<tile[0]-1e-9||currentBounds[1]<tile[1]-1e-9||currentBounds[2]>tile[2]+1e-9||currentBounds[3]>tile[3]+1e-9)throw Error('Final regional terrain LOD requires complete real-source viewport coverage');
  }
  if(dem&&!heightSource)throw Error('No admitted DEM source');
  if(!Number.isFinite(verticalExaggeration)||verticalExaggeration<1||verticalExaggeration>3||!Number.isFinite(bakedSuppression)||bakedSuppression<0||bakedSuppression>1)throw Error('Invalid DEM relief parameters');
  uniforms.demEnabled.value=dem?1:0;uniforms.demCorrectedLight.value=correctedLight?1:0;
  uniforms.demExaggeration.value=verticalExaggeration;uniforms.demBakedSuppression.value=bakedSuppression;
  const shadingStages={BASELINE:0,LIGHTING:1,MATERIAL:2,OUTPUT:3,FINAL:4};
  if(!Object.hasOwn(shadingStages,shadingCorrection))throw Error('Unknown terrain shading correction stage');
  const stage=shadingStages[shadingCorrection];uniforms.shadingStage.value=stage;
  evidence.shadingParameters={stage:shadingCorrection,lightingCorrection:stage>=1,materialCorrection:stage>=2,outputCorrection:stage>=3,
   materialLuminanceGamma:theme.detailContrast+(stage>=4?.20:0),materialLuminanceAnchor:stage>=4?.190:.26,sourceChromaResidual:.45,rolePaletteReferenceY:1.15,outputLuminanceShoulder:stage>=4?.40:.50,outputGamutCeiling:.98,
   ambient:stage>=4?.30:.42,diffuse:stage>=4?.70:.58,
   lighting:'Normalized ambient/diffuse with frozen light direction, flat irradiance and DEM normals; no positive slope cap for corrected stages',lightingProbeEncoding:stage>0?'light / 2':'light'};
  evidence.demParameters={enabled:dem,verticalExaggeration,correctedLight,bakedSuppression};
  setReveal(reveal);
  if(log)console.info(`GATE1: frame start mode=${mode} graphics=${graphics}`);
  const start=performance.now();uniforms.mode.value=mode;draw(terrainScene,fsCamera,baseTarget);
  draw(glowScene,lineCamera,glowTarget);blur.uniforms.inputTexture.value=glowTarget.texture;blur.uniforms.direction.value.set(activeGlowRadius*scale/width,0);draw(blurScene,fsCamera,blurTarget);
  blur.uniforms.inputTexture.value=blurTarget.texture;blur.uniforms.direction.value.set(0,activeGlowRadius*scale/height);draw(blurScene,fsCamera,glowFinal);
  composite.uniforms.gain.value=glow?activeGlowGain*primaryReveal:0;draw(compositeScene,fsCamera,outputTarget);
  if(boundaries)draw(boundaryScene,lineCamera,outputTarget,false);if(graphics)draw(graphicScene,graphicsCamera,outputTarget,false);
  if(finish)gl.finish();evidence.frameMilliseconds=performance.now()-start;evidence.glError=gl.getError();
  evidence.revealState={...currentReveal};
  if(log)console.info('GATE1: frame GPU completion');
  evidence.programs=renderer.info.programs.map(p=>({runnable:p.diagnostics?.runnable??true}));
  if(evidence.glError!==gl.NO_ERROR||evidence.programs.some(p=>!p.runnable))throw Error('GPU frame validation failed');
  return {target:outputTarget,texture:outputTarget?.texture??null,frameMilliseconds:evidence.frameMilliseconds,glError:evidence.glError,camera:evidence.cameraFrame??{bounds:[...currentBounds],anchorCanonical:screen(plan.anchor.coordinates)},reveal:{...currentReveal}};
 }
 function render(options={}){
  if(outputTarget)throw Error('Offscreen factory exposes renderFrame/readPixels; final PNG export belongs to the shared GPU composition output');
  const start=performance.now();renderFrame({...options,finish:true,log:true});
  const png=canvas.toDataURL('image/png');evidence.renderAndPngReadbackMilliseconds=performance.now()-start;
  return png;
 }
 function readTarget(t){const bytes=new Uint8Array(t.width*t.height*4);renderer.readRenderTargetPixels(t,0,0,t.width,t.height,bytes);return bytes;}
 function boundaryProbe(role,layer='CORE'){
  const key=(role==='PRIMARY'?'primary':'secondary')+(layer==='EDGE'?'EdgeWidth':'Width');
  const s=new THREE.Scene();line(s,role==='PRIMARY'?primaryGeometry:secondaryGeometry,boundaryStyle[key],[1,1,1,1]);
  draw(s,lineCamera,null);gl.finish();return canvas.toDataURL('image/png');
 }
 function boundaryLayerProbe(){draw(boundaryScene,lineCamera,null);gl.finish();return canvas.toDataURL('image/png');}
 // Focused QC reads the actual GPU ribbon alpha, never a linewidth setting or
 // another final PNG. The temporary target cannot repaint the submitted frame.
 function measureBoundaryWidths(){
  const t=target(),results={};
  const alphaAt=(data,x,y)=>{
   const px=x-.5,py=y-.5,ix=Math.floor(px),iy=Math.floor(py),fx=px-ix,fy=py-iy;
   const at=(xx,yy)=>xx<0||yy<0||xx>=width||yy>=height?0:data[((height-1-yy)*width+xx)*4+3]/255;
   return (at(ix,iy)*(1-fx)+at(ix+1,iy)*fx)*(1-fy)+(at(ix,iy+1)*(1-fx)+at(ix+1,iy+1)*fx)*fy;
  };
  for(const [role,rings,g,key] of [['PRIMARY',primaryRings,primaryGeometry,'primaryWidth'],['SECONDARY',secondaryRings,secondaryGeometry,'secondaryWidth']]){
   const scene=new THREE.Scene();line(scene,g,boundaryStyle[key],[1,1,1,1]);draw(scene,lineCamera,t);gl.finish();const pixels=readTarget(t);
   const toScreen=p=>{if(isGlobe)return [p[0]*scale,p[1]*scale];const v=new THREE.Vector3(p[0],p[1],0).project(camera);return [(v.x*.5+.5)*width,(.5-v.y*.5)*height];};
   const segments=[];
   for(const ring of rings)for(let i=1;i<ring.length;i++){
    const a=toScreen(ring[i-1]),b=toScreen(ring[i]),length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    const mid=[(a[0]+b[0])/2,(a[1]+b[1])/2],guard=boundaryStyle[key]*scale*3+3;
    if(length>2&&mid[0]>guard&&mid[0]<width-guard&&mid[1]>guard&&mid[1]<height-guard)segments.push({a,b,length,mid});
   }
   const samples=segments.sort((a,b)=>b.length-a.length).slice(0,32).map(s=>{
    const n=[-(s.b[1]-s.a[1])/s.length,(s.b[0]-s.a[0])/s.length],radius=boundaryStyle[key]*scale*3+3;
    let integral=0;
    for(let d=-radius;d<=radius;d+=.25)integral+=alphaAt(pixels,s.mid[0]+n[0]*d,s.mid[1]+n[1]*d)*.25;
    // fwidth(edgeCoord) uses the normal's Manhattan length. Integrated AA
    // coverage is narrower than the geometric ribbon; report both honestly.
    const nominal=boundaryStyle[key]*scale,fw=2*(Math.abs(n[0])+Math.abs(n[1]))/nominal;
    let expected=0;
    for(let d=-nominal/2;d<=nominal/2;d+=.01){const q=Math.max(0,Math.min(1,(Math.abs(2*d/nominal)-(1-fw))/fw));expected+=(1-q*q*(3-2*q))*.01;}
    return {point:s.mid,segmentPixels:s.length,normal:n,coverageWidthPixels:integral,analyticAAWidthPixels:expected};
   });
   const sorted=samples.map(s=>s.coverageWidthPixels).sort((a,b)=>a-b);
   results[role]={requestedPixels:boundaryStyle[key]*scale,sampleCount:samples.length,
    measuredMedianPixels:sorted.length?sorted[Math.floor(sorted.length/2)]:null,samples,
    analyticAAMedianPixels:samples.length?samples.map(s=>s.analyticAAWidthPixels).sort((a,b)=>a-b)[Math.floor(samples.length/2)]:null,
    method:'Actual GPU core ribbon alpha integrated along perpendicular pixel profiles; no final image re-render'};
   for(const o of scene.children)o.material.dispose();
  }
  results.glError=gl.getError();renderer.setRenderTarget(null);return results;
 }
 return {render,renderFrame,updateCamera,setScaleVisual,setTerrainLod,outputTexture:outputTarget?.texture??null,readPixels:()=>{if(outputTarget)return readTarget(outputTarget);const bytes=new Uint8Array(width*height*4);renderer.setRenderTarget(null);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,bytes);return bytes;},evidence,plan,boundaryProbe,boundaryLayerProbe,measureBoundaryWidths,glyphAtlases:()=>glyphExports,glowPixels:()=>readTarget(glowFinal),coverage:()=>readTarget(covTarget),regionIDs:()=>readTarget(idTarget),screen,
  dispose(){
   const materials=new Set(),geometries=new Set();
   for(const s of [idScene,covScene,terrainScene,boundaryScene,glowScene,blurScene,compositeScene,graphicScene])s.traverse(o=>{if(o.material)materials.add(o.material);if(o.geometry)geometries.add(o.geometry);});
   materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());ownedTextures.forEach(t=>t.dispose());targets.forEach(t=>t.dispose());if(!outputRenderer)renderer.dispose();
  }};
}

// Identical factory for preview/final; no alternative rendering algorithm.
export const createProofPreview=createMapInfographicRenderer;
export const createProofFinal=createMapInfographicRenderer;
