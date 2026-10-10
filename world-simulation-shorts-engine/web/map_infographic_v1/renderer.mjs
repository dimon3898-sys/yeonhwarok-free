/** MAP_INFOGRAPHIC_RENDERER_V1 — Gate 1 only.
 * Independent WebGL2 frame graph. No parent Earth renderer, DOM overlay,
 * Canvas frame compositing, shader rewriting, animation or production entrypoint.
 * Canvas is used ONLY to prepare a font coverage texture; GPU draws final text.
 */
import * as THREE from '/three.js';

export const VERSION = 'MAP_INFOGRAPHIC_RENDERER_V1_GATE1';
export const SHADER_VERSION = 'explicit-glsl-1';
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
uniform vec3 primaryHue, secondaryHue;
uniform float primaryStrength, secondaryStrength, secondaryLuminance, detailContrast, reliefStrength, exposure;
uniform int mode;
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
void main(){
 vec2 geo=mix(bounds.xy,bounds.zw,vUv);
 vec2 guv=vec2((geo.x+180.)/360.,(geo.y+90.)/180.);
 vec2 tuv=(geo-tileBounds.xy)/(tileBounds.zw-tileBounds.xy);
 float inside=step(0.,tuv.x)*step(0.,tuv.y)*step(tuv.x,1.)*step(tuv.y,1.);
 vec3 source=linearize(mix(texture(globalTerrain,guv).rgb,texture(terrain,tuv).rgb,inside));
 vec3 cov=texture(coverage,vUv).rgb;
 vec2 idBytes=floor(texture(regionID,vUv).rg*255.+.5);
 float id=idBytes.x+256.*idBytes.y;
 float role=texture(roles,vec2((id+.5)/256.,.5)).r*255.;
 if(mode==3){frag=vec4(idBytes/255.,0.,1.);return;}
 if(mode==4){frag=vec4(cov,1.);return;}
 // Discrete IDs are NEAREST sampled. Only separate AA coverage is fractional.
 float p=role>1.5?cov.b:(cov.b>0.&&cov.b<.999?cov.b:0.);
 float s=role>.5&&role<1.5?cov.g:(cov.g>0.&&cov.g<.999?cov.g:0.);
 vec3 land=source;
 if(mode!=1)land=mix(land,grade(source,primaryHue,primaryStrength),p);
 if(mode!=1)land=mix(land,grade(source,secondaryHue,secondaryStrength)*secondaryLuminance,s);
 // Existing 2K topology: RELIEF PROXY, not a new DEM. NE1 already has baked hillshade.
 vec2 dt=vec2(1./2048.,1./1024.);
 float dx=texture(topo,guv+vec2(dt.x,0.)).r-texture(topo,guv-vec2(dt.x,0.)).r;
 float dy=texture(topo,guv+vec2(0.,dt.y)).r-texture(topo,guv-vec2(0.,dt.y)).r;
 vec3 normal=normalize(vec3(-dx*reliefStrength,-dy*reliefStrength,1.));
 float light=.72+.28*max(dot(normal,normalize(vec3(-.55,.65,1.))),0.);
 land*=light*exposure;
 // Sea retains actual raster surface variation; receives NO country chroma.
 vec3 sea=linearize(vec3(.012,.10,.19))*(.65+2.*pow(max(lum(source),.001),.4));
 vec3 color=mix(sea,land,cov.r);
 if(mode==2){frag=vec4(color,1.);return;}
 color=color/(1.+color*.70); // stronger highlight shoulder for colored terrain.
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
  const pts=ring.slice(0,-1),offset=pos.length/3;
  for(let i=0;i<=pts.length;i++){
   const a=pts[(i+pts.length-1)%pts.length],b=pts[i%pts.length],c=pts[(i+1)%pts.length];
   const dx=c[0]-a[0],dy=c[1]-a[1],l=Math.hypot(dx,dy)||1;
   for(const sign of [-1,1]){pos.push(b[0],b[1],0);tan.push(dx/l,dy/l);side.push(sign);}
   if(i<pts.length){const k=offset+i*2;idx.push(k,k+1,k+2,k+2,k+1,k+3);}
  }
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
 g.setAttribute('tangent',new THREE.Float32BufferAttribute(tan,2));g.setAttribute('side',new THREE.Float32BufferAttribute(side,1));
 g.setIndex(idx);return g;
}
export async function createMapInfographicRenderer({canvas,plan,width=1080,height=1920}){
 console.info('GATE1: factory start');
 if(width/height!==1080/1920)throw Error('Canonical 9:16 layout required');
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WebGL2 required; no fake preview fallback');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const scale=width/1080,b=plan.framing.bounds,c=(b[0]+b[2])/2,lat=(b[1]+b[3])/2,cos=Math.cos(lat*Math.PI/180);
 const project=p=>[(p[0]-c)*cos,p[1]-lat];
 const camera=new THREE.OrthographicCamera(-(b[2]-b[0])*cos/2,(b[2]-b[0])*cos/2,(b[3]-b[1])/2,-(b[3]-b[1])/2,.1,10);
 camera.position.z=5;camera.updateMatrixWorld();
 const screen=p=>{const [x,y]=project(p);const v=new THREE.Vector3(x,y,0).project(camera);return [(v.x*.5+.5)*1080,(.5-v.y*.5)*1920];};
 const fsCamera=new THREE.Camera(),idScene=new THREE.Scene(),covScene=new THREE.Scene();
 const roleLUT=new Uint8Array(256*4),primaryRings=[],secondaryRings=[];let gid=0;
 const geometryEvidence=[];
 for(const record of plan.geometries){
  gid++;if(gid>=256)throw Error('Gate1 region LUT capacity exceeded');
  const role=record.id===plan.primary?2:plan.secondary.includes(record.id)?1:0;
  roleLUT[gid*4]=role;
  const g=triangulateRegion(record,project),idColor=new THREE.Vector3(gid/255,0,0);
  idScene.add(new THREE.Mesh(g.mesh,mat(geoVertex,flatFragment,{value:{value:idColor}})));
  covScene.add(new THREE.Mesh(g.mesh,mat(geoVertex,flatFragment,{value:{value:new THREE.Vector3(1,role===1?1:0,role===2?1:0)}})));
  if(role===2)primaryRings.push(...g.rings);if(role===1)secondaryRings.push(...g.rings);
  geometryEvidence.push({id:record.id,gpuID:gid,role,triangles:g.mesh.index.count/3,parts:polygons(record).length,holes:polygons(record).reduce((s,p)=>s+p.length-1,0)});
 }
 const targets=[];
 function target(samples=0,nearest=false){const t=new THREE.WebGLRenderTarget(width,height,{samples,depthBuffer:false,
  minFilter:nearest?THREE.NearestFilter:THREE.LinearFilter,magFilter:nearest?THREE.NearestFilter:THREE.LinearFilter});targets.push(t);return t;}
 const idTarget=target(0,true),covTarget=target(Math.min(4,renderer.capabilities.maxSamples)),baseTarget=target(),glowTarget=target(),blurTarget=target(),glowFinal=target();
 function draw(scene,cam,targetValue,clear=true){renderer.setRenderTarget(targetValue);if(clear){renderer.setClearColor(0,0);renderer.clear();}renderer.render(scene,cam);}
 draw(idScene,camera,idTarget);draw(covScene,camera,covTarget);
 console.info('GATE1: GIS targets drawn');
 const lut=new THREE.DataTexture(roleLUT,256,1,THREE.RGBAFormat);lut.minFilter=lut.magFilter=THREE.NearestFilter;lut.needsUpdate=true;
 const [regional,global,topo]=await Promise.all([texture(plan.assets.terrain.url),texture(plan.assets.global.url),texture(plan.assets.topo.url)]);
 const ownedTextures=[regional,global,topo,lut];
 console.info('GATE1: terrain sources loaded');
 const anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());for(const t of [regional,global,topo])t.anisotropy=anisotropy;
 const theme=plan.theme;
 const uniforms={terrain:{value:regional},globalTerrain:{value:global},topo:{value:topo},regionID:{value:idTarget.texture},coverage:{value:covTarget.texture},roles:{value:lut},
  bounds:{value:new THREE.Vector4(...b)},tileBounds:{value:new THREE.Vector4(...plan.assets.terrain.bounds)},
  primaryHue:{value:new THREE.Vector3(...theme.primary)},secondaryHue:{value:new THREE.Vector3(...theme.secondary)},
  primaryStrength:{value:theme.primaryStrength},secondaryStrength:{value:theme.secondaryStrength},secondaryLuminance:{value:theme.secondaryLuminance??1},detailContrast:{value:theme.detailContrast??1},reliefStrength:{value:theme.relief},exposure:{value:theme.exposure},mode:{value:0}};
 const terrainMaterial=mat(fullscreenVertex,terrainFragment,uniforms),terrainScene=fullScene(terrainMaterial);
 const primaryGeometry=ribbon(primaryRings),secondaryGeometry=ribbon(secondaryRings),boundaryScene=new THREE.Scene(),glowScene=new THREE.Scene();
 function line(scene,g,pixels,color){const material=mat(ribbonVertex,rgbaFragment,{resolution:{value:new THREE.Vector2(width,height)},width:{value:pixels*scale},color:{value:new THREE.Vector4(...color)}},true);scene.add(new THREE.Mesh(g,material));}
 line(boundaryScene,secondaryGeometry,theme.secondaryWidth+2,[.02,.10,.12,.78]);
 line(boundaryScene,secondaryGeometry,theme.secondaryWidth,[.43,.87,.82,.93]);
 line(boundaryScene,primaryGeometry,theme.primaryWidth+2,[.17,.10,.03,.72]);
 line(boundaryScene,primaryGeometry,theme.primaryWidth,[1,.97,.80,1]);
 line(glowScene,primaryGeometry,theme.primaryWidth+3,[.88,.52,.07,1]);
 const blur=mat(fullscreenVertex,blurFragment,{inputTexture:{value:glowTarget.texture},direction:{value:new THREE.Vector2()}}),blurScene=fullScene(blur);
 const composite=mat(fullscreenVertex,compositeFragment,{baseTexture:{value:baseTarget.texture},glowTexture:{value:glowFinal.texture},gain:{value:theme.glowGain}}),compositeScene=fullScene(composite);
 const graphicsCamera=new THREE.OrthographicCamera(0,1080,0,1920,.1,10);graphicsCamera.position.z=5;graphicsCamera.updateMatrixWorld();
 const graphicScene=new THREE.Scene(),layout=[];
 if(plan.layout.titlePanel){
  const box=plan.layout.titlePanel,m=new THREE.Mesh(new THREE.PlaneGeometry(box[2],box[3]),mat(graphicVertex,panelFragment,{},true));
  m.position.set(box[0]+box[2]/2,box[1]+box[3]/2,0);graphicScene.add(m);layout.push({role:'TITLE_CONTRAST_PANEL',box});
 }
 const anchor=screen(plan.anchor.coordinates),markerSize=plan.layout.markerSize;
 const markerMaterial=mat(graphicVertex,markerFragment,{},true);
 const marker=new THREE.Mesh(new THREE.PlaneGeometry(markerSize,markerSize),markerMaterial);marker.position.set(...anchor,0);graphicScene.add(marker);
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
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(atlas.width,atlas.height),m);mesh.position.set(x+atlas.width/2,y+atlas.height/2,0);graphicScene.add(mesh);
  layout.push({role,text:value,box:[x,y,atlas.width,atlas.height]});
 }
 await text(plan.text.eventTitle,'EVENT_TITLE',plan.layout.title[0],plan.layout.title[1],plan.layout.titleSize,[1,.97,.86]);
 await text(plan.text.locationLabel,'LOCATION_LABEL',anchor[0]+plan.layout.locationOffset[0],anchor[1]+plan.layout.locationOffset[1],plan.layout.locationSize,[1,1,1]);
 if(plan.text.watermark)await text(plan.text.watermark,'SCENARIO_DISCLOSURE',60,1785,26,[.9,.94,.96]);
 // Country names are verified registry data, not invented place labels.
 for(const label of plan.layout.countryLabels)await text(label.text,'COUNTRY',...screen(label.coordinates),label.size,[.89,.94,.90]);
 const debugExt=gl.getExtension('WEBGL_debug_renderer_info');
 const evidence={renderer:VERSION,shader:SHADER_VERSION,theme:THEME_VERSION,dimensions:[width,height],
  context:'webgl2',vendor:gl.getParameter(gl.VENDOR),glRenderer:gl.getParameter(gl.RENDERER),
  unmaskedRenderer:debugExt?gl.getParameter(debugExt.UNMASKED_RENDERER_WEBGL):null,
  maxTextureSize:renderer.capabilities.maxTextureSize,anisotropy,coverageSamples:covTarget.samples,
  projection:'Regional equirectangular, standard parallel at framing center',bounds:b,
  geometry:geometryEvidence,layout,sourceRelief:'NE1 BAKED HILLSHADE + original 2K RELIEF PROXY; no new DEM',
  graph:['GPU region ID (NEAREST, no MSAA)','GPU role/land AA coverage (separate MSAA target)','terrain RGB linear decode -> region material -> relief/light -> sea -> output transfer',
   'primary ribbon glow target -> separable blur','GPU base + glow composite','GPU screen-space boundary core/edge','GPU marker','GPU glyph texture quads'],
  canvasUse:'glyph atlas preparation ONLY; no final-frame Canvas 2D compositing',finalApproval:'USER_PENDING',nvidia:'NOT_RUN'};
 function render({mode=0,graphics=true,boundaries=true,glow=true}={}){
  console.info(`GATE1: frame start mode=${mode} graphics=${graphics}`);
  const start=performance.now();uniforms.mode.value=mode;draw(terrainScene,fsCamera,baseTarget);
  draw(glowScene,camera,glowTarget);blur.uniforms.inputTexture.value=glowTarget.texture;blur.uniforms.direction.value.set(theme.glowRadius*scale/width,0);draw(blurScene,fsCamera,blurTarget);
  blur.uniforms.inputTexture.value=blurTarget.texture;blur.uniforms.direction.value.set(0,theme.glowRadius*scale/height);draw(blurScene,fsCamera,glowFinal);
  composite.uniforms.gain.value=glow?theme.glowGain:0;draw(compositeScene,fsCamera,null);
  if(boundaries)draw(boundaryScene,camera,null,false);if(graphics)draw(graphicScene,graphicsCamera,null,false);
  gl.finish();evidence.frameMilliseconds=performance.now()-start;evidence.glError=gl.getError();
  console.info('GATE1: frame GPU completion');
  evidence.programs=renderer.info.programs.map(p=>({runnable:p.diagnostics?.runnable??true}));
  if(evidence.glError!==gl.NO_ERROR||evidence.programs.some(p=>!p.runnable))throw Error('GPU frame validation failed');
  const png=canvas.toDataURL('image/png');evidence.renderAndPngReadbackMilliseconds=performance.now()-start;
  return png;
 }
 function readTarget(t){const bytes=new Uint8Array(width*height*4);renderer.readRenderTargetPixels(t,0,0,width,height,bytes);return bytes;}
 function boundaryProbe(role){
  const s=new THREE.Scene();line(s,role==='PRIMARY'?primaryGeometry:secondaryGeometry,role==='PRIMARY'?theme.primaryWidth:theme.secondaryWidth,[1,1,1,1]);
  draw(s,camera,null);gl.finish();return canvas.toDataURL('image/png');
 }
 return {render,evidence,plan,boundaryProbe,glowPixels:()=>readTarget(glowFinal),coverage:()=>readTarget(covTarget),regionIDs:()=>readTarget(idTarget),screen,
  dispose(){
   const materials=new Set(),geometries=new Set();
   for(const s of [idScene,covScene,terrainScene,boundaryScene,glowScene,blurScene,compositeScene,graphicScene])s.traverse(o=>{if(o.material)materials.add(o.material);if(o.geometry)geometries.add(o.geometry);});
   materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());ownedTextures.forEach(t=>t.dispose());targets.forEach(t=>t.dispose());renderer.dispose();
  }};
}

// Identical factory for preview/final; no alternative rendering algorithm.
export const createProofPreview=createMapInfographicRenderer;
export const createProofFinal=createMapInfographicRenderer;
