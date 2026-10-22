/** Native WebGL composition only. No map renderer, framebuffer copy or final-frame Canvas. */
import * as THREE from '/three.js';
import {compileEventIntent} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {compileGeographicLinePrimitive} from '../../web/map_infographic_v1/event_line_v1.mjs';
import {createEventLinePass} from '../../web/map_infographic_v1/event_line_pass_v1.mjs';
import {createAreaOverlayPass} from '../../web/map_infographic_v1/area_overlay_pass_v3.mjs';
import {selectAreaStyle} from '../../web/map_infographic_v1/area_style_v3.mjs';
import {createMeasuredGlyph} from '../../web/map_infographic_v1/glyph_atlas.mjs';
import {authoredPinSvg,revealSourceLine,compileMetricScreenTrack,measureDirectorWord,labelPlacement,visibilityDecision} from '../reference-director-v1/director_events.mjs';
import {evaluateDirectorProgram,PROGRAM_SCHEMA} from './director_program.mjs';
import {glyphSquaredDistance} from './glyph_distance.mjs';

const clone=v=>structuredClone(v),finitePoint=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
const vertex=`precision highp float;uniform mat4 projectionMatrix,modelViewMatrix;in vec3 position;in vec2 uv;out vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const rgbaFragment=`precision highp float;in vec2 vUv;out vec4 frag;uniform sampler2D image;uniform float opacity;void main(){vec4 c=texture(image,vUv);frag=vec4(c.rgb,c.a*opacity);}`;
const glyphFragment=`precision highp float;in vec2 vUv;out vec4 frag;uniform sampler2D image;uniform vec4 color,haloColor;uniform float opacity;void main(){vec4 t=texture(image,vUv);float core=t.r*color.a;float halo=t.g*haloColor.a;float a=core+halo*(1.-core);if(a<=0.)discard;frag=vec4(mix(haloColor.rgb,color.rgb,core/max(a,1.e-9)),a*opacity);}`;
function texture(canvas){const t=new THREE.CanvasTexture(canvas);t.flipY=false;t.colorSpace=THREE.NoColorSpace;t.generateMipmaps=false;t.minFilter=t.magFilter=THREE.LinearFilter;return t;}
function material(fragment,uniforms){return new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:vertex,fragmentShader:fragment,uniforms,transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide,toneMapped:false});}
const rgba=v=>new THREE.Vector4(...v);
function bounds(points,pad=0){return [Math.min(...points.map(p=>p[0]))-pad,Math.min(...points.map(p=>p[1]))-pad,Math.max(...points.map(p=>p[0]))+pad,Math.max(...points.map(p=>p[1]))+pad];}
function transformedBox(left,baseline,ink,scale,angle=0,origin=[left,baseline]){
 const [l,t,r,b]=ink;return bounds([[l,t],[r,t],[r,b],[l,b]].map(([x,y])=>{
  const dx=left+x*scale-origin[0],dy=baseline+y*scale-origin[1],c=Math.cos(angle),s=Math.sin(angle);
  return [origin[0]+dx*c-dy*s,origin[1]+dx*s+dy*c];
 }));
}
/** Glyph preparation is alpha-only, using the existing measured native font.
 * A finite distance halo is stored independently; no map pixels enter this atlas.
 */
function measuredGlyphTexture(text,style){
 const glyph=createMeasuredGlyph(text,{fontSize:style.fontPx,fontFamily:'Gate1Bold',outlineRadius:style.haloRadiusPx,maxLines:1});
 if(!glyph.fits||glyph.alphaTouchesEdge)throw Error('DIRECTOR_GPU_GLYPH_MEASUREMENT_FAILED');
 const [w,h]=glyph.atlasDimensions,canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
 const context=canvas.getContext('2d'),source=glyph.canvas.getContext('2d').getImageData(0,0,w,h).data,data=context.createImageData(w,h),radius=style.haloRadiusPx;
 const alpha=new Uint8Array(w*h);for(let i=0;i<alpha.length;i++)alpha[i]=source[i*4+3];
 const distance=glyphSquaredDistance(alpha,w,h);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4,a=source[i+3],d=Math.sqrt(distance[y*w+x]);
  const halo=a?1:radius>0?(1-Math.min(1,d/radius))**2:0;
  data.data[i]=a;data.data[i+1]=Math.round(255*halo);data.data[i+2]=0;data.data[i+3]=255;
 }
 context.putImageData(data,0,0);
 const m=glyph.measuredInk[0],drawX=Math.ceil(style.haloRadiusPx)+6+Math.max(0,m.left),drawBaseline=glyph.baselines[0];
 return {texture:texture(canvas),width:w,height:h,drawX,drawBaseline,ink:[-m.left,-m.ascent,m.right,m.descent]};
}
async function pinTexture(variant){
 const svg=authoredPinSvg(variant),image=new Image();image.src='data:image/svg+xml;base64,'+btoa(svg);await image.decode();
 const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.getContext('2d').drawImage(image,0,0);
 return texture(canvas);
}
function roleOf(e,f){return e.requiredRange&&f>=e.requiredRange[0]&&f<e.requiredRange[1]?'REQUIRED_VISIBLE_SAFE':e.role;}

export async function createDirectorGraphicPass({renderer,canvas,factory,program}){
 if(program?.schema!==PROGRAM_SCHEMA||!renderer?.isWebGLRenderer||renderer.autoClear!==false||canvas?.width!==1080||canvas?.height!==1920||typeof factory?.screen!=='function')throw Error('DIRECTOR_GPU_CANONICAL_SHARED_NATIVE_REQUIRED');
 const gl=renderer.getContext(),viewport=[0,0,1080,1920],safe=program.safeArea,resources=[],scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,1080,0,1920,.1,10);
 const entryError=gl.getError();if(entryError!==gl.NO_ERROR)throw Error('DIRECTOR_GPU_EXISTING_GL_ERROR_'+entryError);
 // Drop shared-renderer bindings to any previous pass's disposed resources
 // before the unchanged raw-GL Area pass captures and restores that state.
 renderer.resetState();
 camera.position.z=5;camera.updateMatrixWorld();
 const group=new THREE.Group();scene.add(group);const textCache=new Map(),pinCache=new Map(),linePasses=new Map(),areaPasses=new Map();
 const find=(kind,id)=>program.data[kind].find(r=>r.id===id),project=p=>factory.screen(p);
 const newQuad=(w,h,mat)=>{const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);resources.push(mesh.geometry,mat);return mesh;};
 let atlasPixels=0;
 try{
  for(const e of program.events){
   if(e.type==='PIN'){
    const t=await pinTexture(e.style.assetVariant);resources.push(t);pinCache.set(e.id,{mesh:newQuad(e.style.widthPx,e.style.heightPx,material(rgbaFragment,{image:{value:t},opacity:{value:1}}))});
   }else if(['LABEL','METRIC'].includes(e.type)){
    const word=e.type==='LABEL'?find('locations',e.locationId).label:find('metrics',e.metricId).text;
    const measured=measureDirectorWord(word,{fontPx:e.style.fontPx,haloRadiusPx:e.style.haloRadiusPx});
    const glyphs=e.graphemes.map(g=>{
     if(/^\s+$/u.test(g))return null;
     const atlas=measuredGlyphTexture(g,e.style);resources.push(atlas.texture);atlasPixels+=atlas.width*atlas.height;if(atlasPixels>8388608)throw Error('DIRECTOR_GPU_GLYPH_ATLAS_BUDGET');
     const mat=material(glyphFragment,{image:{value:atlas.texture},color:{value:rgba(e.style.color)},haloColor:{value:rgba([...e.style.haloColor.slice(0,3),e.style.haloColor[3]*e.style.haloOpacity])},opacity:{value:1}});
     return {...atlas,mesh:newQuad(atlas.width,atlas.height,mat)};
    });textCache.set(e.id,{measured,glyphs});
   }else if(e.type==='LINE')linePasses.set(e.id,createEventLinePass({renderer,style:{width:e.style.widthPx,glowRadius:Math.max(.001,e.style.haloRadiusPx),glowGain:e.style.haloOpacity,coreColor:e.style.coreColor,glowColor:e.style.haloColor}}));
   else if(e.type==='AREA'){
    const style=clone(selectAreaStyle({primaryMaterialColor:[.5,.5,.5]}));
    style.AREA={fillColor:e.style.fillColor,coreColor:e.style.coreColor,width:e.style.widthPx,glowColor:e.style.haloColor,glowRadius:e.style.haloRadiusPx,glowGain:e.style.haloOpacity};
    areaPasses.set(e.id,createAreaOverlayPass({canvas,style}));
   }
  }
  const createError=gl.getError();if(createError!==gl.NO_ERROR)throw Error('DIRECTOR_GPU_CREATE_ERROR_'+createError);
 }catch(error){for(const p of [...linePasses.values(),...areaPasses.values()])p.dispose();resources.forEach(r=>r.dispose());throw error;}
 function meshDraw(mesh,center,scale,angle=0){
  mesh.position.set(...center,0);mesh.scale.set(scale,scale,1);mesh.rotation.z=angle;group.add(mesh);
 }
 function draw({globalFrame,metricPlacements=null}){
  const state=evaluateDirectorProgram(program,globalFrame),audit=[];
  for(const r of state.records.filter(r=>r.type==='AREA')){
   const geometry=find('areas',r.areaId).geometry,controls={areas:[{id:r.id,geometry,alpha:r.fraction,coverage:1}],fronts:[],impacts:[],propagations:[]};
   renderer.resetState();const output=areaPasses.get(r.id).draw({controls,project,safeArea:viewport,protectedGraphics:[],boundarySegments:[]});
   audit.push({id:r.id,type:r.type,sourceGeometryId:r.areaId,sourceGeometryUnchanged:true,draw:output});
  }
  for(const r of state.records.filter(r=>r.type==='LINE')){
   const record=find('lines',r.lineId),cut=revealSourceLine(record.arclength,r.fraction);
   if(cut.length<2){audit.push({id:r.id,type:r.type,drawn:false,fraction:r.fraction});continue;}
   const intent=compileEventIntent({data_mode:program.dataMode==='SYNTHETIC_TEST'?'SYNTHETIC_TEST':'PRODUCTION',line:{geometry:{type:'LineString',coordinates:cut},direction:'FORWARD',style_role:'PRIMARY',source:{source_type:program.dataMode==='SYNTHETIC_TEST'?'SYNTHETIC_TEST':'SUPPLIED_GEOGRAPHIC_LINE',source_reference:record.source.id,verification_status:program.dataMode==='SYNTHETIC_TEST'?'SYNTHETIC_TEST':'VERIFIED'}}});
   const primitive=compileGeographicLinePrimitive(intent,{project});renderer.resetState();
   const output=linePasses.get(r.id).draw({primitive,visibleFraction:1,safeArea:r.role==='REQUIRED_VISIBLE_SAFE'?safe:viewport,protectedBoxes:[]});
   audit.push({id:r.id,type:r.type,drawn:output.drawn,fraction:r.fraction,sourceCoordinates:cut,screenPath:output.path,clock:'SOURCE_GEOGRAPHIC_ARCLENGTH',sourceHash:record.source.sha256});
  }
  while(group.children.length)group.remove(group.children[0]);
  for(const r of state.records.filter(r=>r.type==='PIN')){
   if(r.scale<=0)continue;const tip=project(find('locations',r.locationId).anchor),w=r.style.widthPx*r.scale,h=r.style.heightPx*r.scale,box=[tip[0]-w/2,tip[1]-h,tip[0]+w/2,tip[1]],visibility=visibilityDecision(roleOf(r,globalFrame),box,{safe,viewport});
   if(visibility.draw)meshDraw(pinCache.get(r.id).mesh,[tip[0],tip[1]-h/2],r.scale);
   audit.push({id:r.id,type:r.type,drawn:visibility.draw,box,tip,anchorResidualPixels:0,screenUpright:true});
  }
  for(const r of state.records.filter(r=>['LABEL','METRIC'].includes(r.type))){
   const entry=textCache.get(r.id);let left,baseline,angle=0,origin;
   if(r.type==='LABEL'){
    const pin=program.events.find(p=>p.id===r.pinEventId),pinState=state.records.find(p=>p.id===pin.id);
    if(!pinState)throw Error('DIRECTOR_GPU_LABEL_PIN_NOT_ACTIVE');
    const tip=project(find('locations',r.locationId).anchor),placement=labelPlacement(entry.measured,tip,{pinHeightPx:pin.style.heightPx,pinScale:pinState.scale,gapPx:r.style.gapPx??0});
    left=placement.left;baseline=placement.baseline;origin=[left,baseline];
   }else{
    const placement=metricPlacements?.[r.id];if(!placement||placement.referenceFrame!==globalFrame||!finitePoint(placement.position)||!Number.isFinite(placement.angleRadians))throw Error('DIRECTOR_GPU_GLOBAL_METRIC_PLACEMENT_REQUIRED');
    if(Math.hypot(...project(placement.geographicAnchor).map((v,i)=>v-placement.projectedAnchor[i]))>1e-6)throw Error('DIRECTOR_GPU_METRIC_CURRENT_PROJECTION_MISMATCH');
    angle=placement.angleRadians;origin=placement.position;
    const [inkLeft,top,inkRight,bottom]=entry.measured.fullWordInkBounds;
    left=origin[0]-(inkLeft+inkRight)/2;baseline=origin[1]-(top+bottom)/2;
   }
   const reserved=transformedBox(left,baseline,entry.measured.fullWordInkBounds,1,angle,origin),padding=r.style.haloRadiusPx;
   visibilityDecision(roleOf(r,globalFrame),[reserved[0]-padding,reserved[1]-padding,reserved[2]+padding,reserved[3]+padding],{safe,viewport});
   const drawn=[];
   for(let i=0;i<entry.glyphs.length;i++){
    const atlas=entry.glyphs[i],beat=r.glyphs[i];if(!atlas||beat.opacity<=0||beat.scale<=0)continue;
    const gx=left+entry.measured.advances[i],box=transformedBox(gx,baseline,atlas.ink,beat.scale,angle,r.type==='METRIC'?origin:[gx,baseline]);
    const pad=r.style.haloRadiusPx,full=[box[0]-pad,box[1]-pad,box[2]+pad,box[3]+pad],visibility=visibilityDecision(roleOf(r,globalFrame),full,{safe,viewport});
    if(!visibility.draw)continue;
    const localCenter=[gx+(-atlas.drawX+atlas.width/2)*beat.scale,baseline+(-atlas.drawBaseline+atlas.height/2)*beat.scale],pivot=r.type==='METRIC'?origin:[gx,baseline],dx=localCenter[0]-pivot[0],dy=localCenter[1]-pivot[1],c=Math.cos(angle),s=Math.sin(angle),center=[pivot[0]+dx*c-dy*s,pivot[1]+dx*s+dy*c];
    atlas.mesh.material.uniforms.opacity.value=beat.opacity;meshDraw(atlas.mesh,center,beat.scale,angle);drawn.push({grapheme:beat.grapheme,box:full,scale:beat.scale,opacity:beat.opacity});
   }audit.push({id:r.id,type:r.type,drawnGlyphs:drawn,fullWordCentered:true,screenAngleRadians:angle});
  }
  renderer.resetState();renderer.setRenderTarget(null);renderer.render(scene,camera);gl.finish();if(gl.getError()!==gl.NO_ERROR)throw Error('DIRECTOR_GPU_DRAW_ERROR');
  return {globalFrame,actualGPUConsumerDraw:true,finishedFrameCopy:false,sourceGeometryMutated:false,records:audit};
 }
 return {draw,evidence:{version:'WORLD_ENGINE_DIRECTOR_GRAPHIC_PASS_V1',consumer:'ACTUAL_NATIVE_SHARED_WEBGL2_FRAMEBUFFER',mapRenderer:'EXISTING_NATIVE_FACTORY',sourceLineClock:'GEOGRAPHIC_ARCLENGTH_BEFORE_PROJECTION',textAtlas:'EXISTING_PINNED_NATIVE_GLYPH_MEASUREMENT',finishedFrameCopy:false,canvasFinalFrameComposition:false,nvidiaVerified:false},
  dispose(){for(const p of [...linePasses.values(),...areaPasses.values()])p.dispose();resources.forEach(r=>r.dispose());}};
}

/** Run before rendering windows, across the complete visible metric interval. */
export function prepareMetricPlacements(program,{projectAt}){
 const result={};for(const e of program.events.filter(e=>e.type==='METRIC')){
  const line=program.data.lines.find(r=>r.id===e.lineId),frames=Array.from({length:e.holdUntilFrame-e.startFrame},(_,i)=>e.startFrame+i);
  const track=compileMetricScreenTrack(line.arclength,{projectAt,referenceFrames:frames});
  result[e.id]=Object.fromEntries(track.placements.map(p=>[p.referenceFrame,{...p,position:p.projectedAnchor.map((v,i)=>v+e.style.offsetPx*p.normal[i]),offsetPixels:e.style.offsetPx}]));
 }return result;
}

/** Bounded composition over the actual native factory; source/GPU/Studio
 * admission remains the caller's responsibility and is never set to PASS here.
 */
export async function createDirectorRuntime({factory,renderer,canvas,program,cameraAt,projectAt,nativeFrameOptions={}}){
 if(typeof factory?.updateSimilarity!=='function'||typeof factory?.inverseScreen!=='function'||typeof cameraAt!=='function'||typeof projectAt!=='function')throw Error('DIRECTOR_NATIVE_SIMILARITY_API_REQUIRED');
 const pixels=await createDirectorGraphicPass({renderer,canvas,factory,program}),placements=prepareMetricPlacements(program,{projectAt});
 return {drawFrame(globalFrame){
  evaluateDirectorProgram(program,globalFrame);const currentCamera=cameraAt(globalFrame);factory.updateSimilarity(currentCamera);
  for(const location of program.data.locations){const actual=factory.screen(location.anchor),expected=projectAt(globalFrame,location.anchor);
   if(!finitePoint(actual)||!finitePoint(expected)||Math.hypot(actual[0]-expected[0],actual[1]-expected[1])>1e-6)throw Error('DIRECTOR_CURRENT_NATIVE_PROJECTION_MISMATCH');
  }
  const native=factory.renderFrame({...nativeFrameOptions,graphics:false});
  const metricPlacements=Object.fromEntries(Object.entries(placements).map(([id,frames])=>[id,frames[globalFrame]]));
  const overlay=pixels.draw({globalFrame,metricPlacements});
  return {globalFrame,native,overlay,currentNativeCamera:currentCamera,sourceEnvelope:factory.sourceEnvelope(),nvidiaVerified:false,visualQualityApproved:false};
 },readPixels:factory.readPixels,evidence:{...pixels.evidence,runtime:'NATIVE_FACTORY_THEN_GEOGRAPHIC_AND_SCREEN_GRAPHICS',cameraDriver:'CALLER_SOURCE_BOUND_GLOBAL_TRACK',globalTimeReset:false,sourceDataAdmissionPerformedByThisWrapper:false},dispose(){pixels.dispose();}};
}
