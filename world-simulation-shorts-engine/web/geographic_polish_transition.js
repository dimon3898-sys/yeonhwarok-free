/** v004 only: a registered geometric map-to-globe handoff, without a veil.
 * The original Mercator coordinates remain the material sampling coordinates.
 * All draw primitives share the same tangent-plane -> spherical position map.
 * No GIS data, cached legacy geometry, or authored scene input is modified.
 */
import * as THREE from 'three';
import {FlatProjection,FlatCameraRig,flatCoordinate,flatNumber,flatClamp,flatSmooth} from './flat_semantics.js';

export const GEOGRAPHIC_POLISH_VERSION='v004';
const RAD=Math.PI/180;
export const geographicSphere=(c,r=1)=>new THREE.Vector3(Math.cos(c.lat*RAD)*Math.cos(c.lon*RAD),Math.sin(c.lat*RAD),-Math.cos(c.lat*RAD)*Math.sin(c.lon*RAD)).multiplyScalar(r);
const durationOf=s=>Math.max(.15,Math.min(1.5,flatNumber(s.map_transition?.duration??s.flat_map?.transition_duration,.65)));
const withoutVeil=s=>({...s,transition_in:'camera_continuity',transition_out:'camera_continuity'});

export function geographicBasis(value){
 const c=flatCoordinate(value),normal=geographicSphere(c);
 const east=new THREE.Vector3(-Math.sin(c.lon*RAD),0,-Math.cos(c.lon*RAD));
 const north=new THREE.Vector3().crossVectors(normal,east).normalize();
 return {coordinate:c,normal,east,north,scale:RAD*Math.cos(c.lat*RAD)};
}

/** Pure transform used both by GPU vertices and the projected-frame receipts. */
export class GeographicWarp {
 constructor(outgoing){
  this.scene=outgoing;this.projection=new FlatProjection(outgoing.flat_map?.center||outgoing.coordinates,outgoing.flat_map?.projection||'LOCAL_MERCATOR');
  this.anchor=flatCoordinate(outgoing.flat_map?.camera_end||outgoing.camera_end||outgoing.coordinates);
  this.basis=geographicBasis(this.anchor);this.anchorPoint=this.projection.point(this.anchor);
 }
 affine(p){const b=this.basis;return b.normal.clone().addScaledVector(b.east,(p.x-this.anchorPoint.x)*b.scale).addScaledVector(b.north,(p.y-this.anchorPoint.y)*b.scale).addScaledVector(b.normal,p.z*b.scale);}
 vector(p){const b=this.basis;return b.east.clone().multiplyScalar(p.x*b.scale).addScaledVector(b.north,p.y*b.scale).addScaledVector(b.normal,p.z*b.scale);}
 position(p,curvature=1){
  const c=this.projection.inverse(p),r=1+p.z*this.basis.scale;
  return this.affine(p).lerp(geographicSphere(c,r),flatClamp(curvature));
 }
 normal(p,n,curvature=1){
  const c=this.projection.inverse(p),b=geographicBasis(c),a=this.basis;
  const flat=a.east.clone().multiplyScalar(n.x).addScaledVector(a.north,n.y).addScaledVector(a.normal,n.z);
  const globe=b.east.clone().multiplyScalar(n.x).addScaledVector(b.north,n.y).addScaledVector(b.normal,n.z);
  return flat.lerp(globe,flatClamp(curvature)).normalize();
 }
 uniforms(){const b=this.basis;return {uPolishEnabled:{value:0},uPolishCurvature:{value:0},uPolishAnchor:{value:new THREE.Vector2(this.anchorPoint.x,this.anchorPoint.y)},uPolishScale:{value:b.scale},uPolishMercator:{value:this.projection.kind==='LOCAL_MERCATOR'?1:0},uPolishEast:{value:b.east.clone()},uPolishNorth:{value:b.north.clone()},uPolishNormal:{value:b.normal.clone()}};}
}

const warpGLSL=`
uniform float uPolishEnabled,uPolishCurvature,uPolishScale,uPolishMercator,uPolishLayerClearance;
uniform vec2 uPolishAnchor;
uniform vec3 uPolishEast,uPolishNorth,uPolishNormal;
float polishLatitude(float y){return mix(y,(2.*atan(exp(clamp(y,-140.,140.)*.0174532925199433))-1.570796326794897)*57.29577951308232,uPolishMercator);}
vec3 polishSphere(vec3 p){float lon=p.x*.0174532925199433,lat=polishLatitude(p.y)*.0174532925199433;return vec3(cos(lat)*cos(lon),sin(lat),-cos(lat)*sin(lon));}
vec3 polishPosition(vec3 p){
 vec3 a=uPolishNormal+uPolishEast*(p.x-uPolishAnchor.x)*uPolishScale+uPolishNorth*(p.y-uPolishAnchor.y)*uPolishScale+uPolishNormal*p.z*uPolishScale;
 vec3 globe=polishSphere(p)*(1.+p.z*uPolishScale);
 vec3 shaped=mix(a,globe,uPolishCurvature);
 shaped+=normalize(shaped)*uPolishLayerClearance*uPolishCurvature;
 return mix(p,shaped,uPolishEnabled);
}
vec3 polishNormal(vec3 p,vec3 n){
 float lon=p.x*.0174532925199433;vec3 radial=polishSphere(p),east=vec3(-sin(lon),0.,-cos(lon)),north=normalize(cross(radial,east));
 vec3 a=uPolishEast*n.x+uPolishNorth*n.y+uPolishNormal*n.z,b=east*n.x+north*n.y+radial*n.z;
 return normalize(mix(n,mix(a,b,uPolishCurvature),uPolishEnabled));
}
`;

function patchVertex(source){
 if(source.includes('#include <project_vertex>')){
  source=source.replace('#include <project_vertex>',`vec3 polishSource=(modelMatrix*vec4(transformed,1.)).xyz;vec4 mvPosition=viewMatrix*vec4(polishPosition(polishSource),1.);gl_Position=projectionMatrix*mvPosition;`);
  if(source.includes('#include <normal_vertex>'))source=source.replace('#include <normal_vertex>',`#include <normal_vertex>\n#ifndef FLAT_SHADED\n vNormal=normalize(mix(vNormal,mat3(viewMatrix)*polishNormal((modelMatrix*vec4(position,1.)).xyz,mat3(modelMatrix)*objectNormal),uPolishEnabled));\n#endif`);
 }else{
  const expression=/gl_Position\s*=\s*projectionMatrix\s*\*\s*modelViewMatrix\s*\*\s*vec4\(([^,]+),\s*1\.?0?\)\s*;/;
  if(!expression.test(source))throw Error('V004_UNSUPPORTED_VERTEX_MATERIAL');
  source=source.replace(expression,(_,p)=>`gl_Position=projectionMatrix*viewMatrix*vec4(polishPosition((modelMatrix*vec4(${p},1.)).xyz),1.);`);
 }
 return warpGLSL+source;
}

/** Adaptive triangle bisection limits angular faceting of ocean/land surfaces.
 * Only per-scene clones are subdivided. Shared Natural Earth cache is untouched.
 */
function curvedSurfaceGeometry(geometry,maxEdge=1.5){
 const source=geometry.index?geometry.toNonIndexed():geometry.clone(),attrs=source.attributes;
 const names=Object.keys(attrs),out=Object.fromEntries(names.map(n=>[n,[]]));let triangles=0;
 const read=i=>Object.fromEntries(names.map(n=>[n,Array.from({length:attrs[n].itemSize},(_,j)=>attrs[n].array[i*attrs[n].itemSize+j])]));
 const length=(a,b)=>Math.hypot(a.position[0]-b.position[0],a.position[1]-b.position[1]);
 const midpoint=(a,b)=>Object.fromEntries(names.map(n=>[n,a[n].map((v,j)=>(v+b[n][j])/2)]));
 const emit=(a,b,c,depth=0)=>{
  const distances=[length(a,b),length(b,c),length(c,a)],largest=Math.max(...distances);
  if(largest>maxEdge&&depth<16){const edge=distances.indexOf(largest);if(edge===0){const m=midpoint(a,b);emit(a,m,c,depth+1);emit(m,b,c,depth+1);}else if(edge===1){const m=midpoint(b,c);emit(a,b,m,depth+1);emit(a,m,c,depth+1);}else{const m=midpoint(c,a);emit(a,b,m,depth+1);emit(m,b,c,depth+1);}return;}
  if(++triangles>300000)throw Error('V004_CURVATURE_GEOMETRY_LIMIT');
  for(const v of [a,b,c])for(const n of names)out[n].push(...v[n]);
 };
 for(let i=0;i<attrs.position.count;i+=3)emit(read(i),read(i+1),read(i+2));
 const result=new THREE.BufferGeometry();for(const n of names)result.setAttribute(n,new THREE.Float32BufferAttribute(out[n],attrs[n].itemSize));
 result.computeBoundingBox();result.computeBoundingSphere();source.dispose();return result;
}

export function registeredHandoffCamera(outgoing,aspect=9/16){
 const warp=new GeographicWarp(outgoing),projection=warp.projection;
 const sourceCamera=new THREE.OrthographicCamera();sourceCamera.aspect=aspect;
 const rig=new FlatCameraRig(sourceCamera,withoutVeil(outgoing),projection,[]);rig.update(outgoing.duration);
 const center=warp.position(rig.current.center,1),direction=warp.vector(sourceCamera.position.clone().sub(rig.current.center)).normalize();
 const camera=new THREE.PerspectiveCamera(flatNumber(outgoing.camera_end?.fov,44),aspect,.005,100);
 const width=rig.current.span*warp.basis.scale,distance=width/(2*aspect*Math.tan(camera.fov*RAD/2));
 camera.position.copy(center).addScaledVector(direction,distance);camera.up.copy(warp.vector(sourceCamera.up).normalize());camera.lookAt(center);camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
 return {camera,warp,center,width,distance,span:rig.current.span};
}

export function incomingGeographicTransition(scene,plan,aspect=9/16){
 if(scene.visual_polish?.version!==GEOGRAPHIC_POLISH_VERSION||scene.transition_in!=='FLAT_TO_EARTH')return null;
 const index=(plan.scenes||[]).findIndex(s=>s.scene_id===scene.scene_id),outgoing=plan.scenes?.[index-1];
 if(!outgoing||outgoing.visual_polish?.version!==GEOGRAPHIC_POLISH_VERSION||outgoing.transition_out!=='FLAT_TO_EARTH'||!outgoing.flat_map)throw Error('V004_GEOGRAPHIC_HANDOFF_REQUIRES_VERIFIED_FLAT_NEIGHBOR');
 return {...registeredHandoffCamera(outgoing,aspect),outgoing,duration:durationOf(outgoing)};
}

class FlatGeographicController {
 constructor(renderer){this.renderer=renderer;this.active=false;this.curvature=0;this.objects=[];this.lights=[];this.camera=new THREE.Camera();this.camera.aspect=renderer.w/renderer.h;this.camera.fov=44;}
 init(){
  const r=this.renderer,s=r.sceneSpec,index=(r.plan.scenes||[]).findIndex(v=>v.scene_id===s.scene_id),next=r.plan.scenes?.[index+1];
  if(s.visual_polish?.version!=='v004'||s.transition_out!=='FLAT_TO_EARTH')return;
  if(!next||next.visual_polish?.version!=='v004'||next.transition_in!=='FLAT_TO_EARTH')throw Error('V004_GEOGRAPHIC_HANDOFF_REQUIRES_EARTH_NEIGHBOR');
  this.warp=new GeographicWarp(s);this.boundary=registeredHandoffCamera(s,r.w/r.h);this.duration=durationOf(s);this.start=s.duration-this.duration;
  r.core.cam.scene=withoutVeil(r.core.cam.scene);this.baseCamera=r.core.camera;
  this.uniforms=this.warp.uniforms();const materialCopies=new Map();
  r.world.traverse(object=>{
   if(object.isLight){this.lights.push({object,position:object.position.clone()});return;}
   if(!object.isMesh)return;
   const materials=Array.isArray(object.material)?object.material:[object.material];
   object.material=materials.map(original=>{
    if(materialCopies.has(original))return materialCopies.get(original);
    const material=original.clone();
    // UniformsUtils clones Texture objects. Restore their shared identity before
    // binding so country clones do not upload duplicate 8K/terrain samplers.
    if(material.uniforms)for(const [name,u] of Object.entries(original.uniforms||{}))if(u.value?.isTexture)material.uniforms[name].value=u.value;
    const layer={value:original.uniforms?.uLand?.value===0?-.0007:0};
    if(material.isShaderMaterial){Object.assign(material.uniforms,this.uniforms,{uPolishLayerClearance:layer});material.vertexShader=patchVertex(material.vertexShader);original.uniforms=material.uniforms;}
    else {const old=material.onBeforeCompile;material.onBeforeCompile=shader=>{old?.(shader);Object.assign(shader.uniforms,this.uniforms,{uPolishLayerClearance:layer});shader.vertexShader=patchVertex(shader.vertexShader);};material.customProgramCacheKey=()=>`v004-geographic-warp-${original.type}`;}
    material.needsUpdate=true;materialCopies.set(original,material);return material;
   });
   if(!Array.isArray(materials)||materials.length===1)object.material=object.material[0];
   if(materials.some(m=>m.uniforms?.uLand))object.geometry=curvedSurfaceGeometry(object.geometry);
   object.frustumCulled=false;this.objects.push(object);
  });
  // Keep the existing animation controllers writing the same cloned uniforms.
  for(const material of r.materials){const copy=materialCopies.get(material);if(copy){material.uniforms=copy.uniforms;}}
  for(const item of r.countryItems){if(materialCopies.has(item.material))item.material=materialCopies.get(item.material);if(materialCopies.has(item.borderMaterial))item.borderMaterial=materialCopies.get(item.borderMaterial);}
  for(const item of r.graphics.items)for(const key of ['mat','glowMat'])if(materialCopies.has(item[key]))item[key]=materialCopies.get(item[key]);
  this.initialized=true;
 }
 before(t){
  if(!this.initialized)return;
  const r=this.renderer,amount=flatSmooth((t-this.start)/this.duration);this.active=t>=this.start;this.curvature=amount;
  this.uniforms.uPolishEnabled.value=this.active?1:0;this.uniforms.uPolishCurvature.value=amount;
  if(!this.background)this.background=r.world.background.clone();
  r.world.background.copy(this.background).lerp(new THREE.Color('#01050a'),amount);
  if(!this.active){r.camera=this.baseCamera;for(const l of this.lights)l.object.position.copy(l.position);return;}
  const source=this.baseCamera,warp=this.warp,current=r.core.cam.current;
  const flatPosition=warp.affine(source.position),center=warp.position(current.center,amount);
  const end=this.boundary.camera,position=flatPosition.clone().lerp(end.position,amount);
  this.camera.position.copy(position);this.camera.up.copy(warp.vector(source.up).normalize());this.camera.lookAt(center);this.camera.updateMatrixWorld(true);
  const ortho=source.projectionMatrix.clone(),scale=warp.basis.scale;
  // A global unit scale changes the clip matrix as well as the camera rig.
  for(const column of [0,1,2])for(let row=0;row<4;row++)ortho.elements[column*4+row]/=scale;
  const perspective=end.projectionMatrix.clone();for(let i=0;i<16;i++)perspective.elements[i]/=this.boundary.distance;
  for(let i=0;i<16;i++)this.camera.projectionMatrix.elements[i]=ortho.elements[i]*(1-amount)+perspective.elements[i]*amount;
  this.camera.projectionMatrixInverse.copy(this.camera.projectionMatrix).invert();this.camera.fov=end.fov;this.camera.near=.005;this.camera.far=100;
  r.camera=this.camera;
  for(const l of this.lights)l.object.position.copy(warp.affine(l.position));
  r.world.updateMatrixWorld(true);
 }
 project(point){
  const r=this.renderer;if(!this.active)return r.core.project(point);
  const world=this.warp.position(point,this.curvature),p=world.clone().project(this.camera);
  const normal=this.warp.normal(point,new THREE.Vector3(0,0,1),this.curvature),front=normal.dot(this.camera.position.clone().sub(world))>0;
  return {x:(p.x*.5+.5)*r.w,y:(.5-p.y*.5)*r.h,visible:front&&p.z>=-1&&p.z<=1,occluded:!front,worldPosition:world.toArray()};
 }
 labels(frame){
  if(!this.active)return;
  const r=this.renderer,sources=[...(r.sceneSpec.labels||[]),...(r.sceneSpec.visual_events||[])];
  frame.labels=frame.labels.filter(label=>{
   if(label.information)return true;
   const source=sources.find(v=>v.coordinates&&(v.id===label.event_id||v.event_id===label.event_id||v.text===label.text));if(!source)return false;
   const p=this.project(r.core.projection.point(source.coordinates));if(!p.visible||p.x<r.w*.04||p.x>r.w*.96||p.y<r.h*.08||p.y>r.h*.82)return false;
   const dx=p.x-label.anchor.x,dy=p.y-label.anchor.y;label.anchor=p;label.x=flatClamp(label.x+dx,r.w*.09,r.w*.87-label.width);label.y=flatClamp(label.y+dy,r.h*.13,r.h*.79-label.height);return true;
  });
 }
 audit(value){
  if(!this.initialized)return value;const r=this.renderer;
  const equivalent=new THREE.Camera();equivalent.position.copy(this.warp.affine(this.baseCamera.position));equivalent.up.copy(this.warp.vector(this.baseCamera.up).normalize());equivalent.lookAt(this.warp.affine(r.core.cam.current.center));equivalent.updateMatrixWorld(true);
  value.registeredCameraPosition=(this.active?this.camera:equivalent).position.toArray();value.registeredCameraQuaternion=(this.active?this.camera:equivalent).quaternion.toArray();value.registeredCameraUnits='normalized_earth_radius';
  const anchors=(r.sceneSpec.labels||[]).filter(l=>l.coordinates).map(l=>({text:l.text,coordinates:l.coordinates,...this.project(r.core.projection.point(l.coordinates))}));
  value.geographic_anchor_projections=anchors;
  if(this.active){
   value.entities=value.entities.map(e=>{const item=r.entities.items.find(i=>i.spec.id===e.id),position=item.model.position.clone(),p=this.project(position),corners=[];const box=new THREE.Box3().setFromObject(item.model);for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z])corners.push(this.project(new THREE.Vector3(x,y,z)));const radius=Math.max(...corners.map(q=>Math.hypot(q.x-p.x,q.y-p.y)));const clipped=e.visible&&p.visible&&(p.x+radius<0||p.x-radius>r.w||p.y+radius<0||p.y-radius>r.h);return {...e,...p,position:this.warp.position(position,this.curvature).toArray(),sourceProjectedPosition:position.toArray(),screenRadius:radius,screenVisible:p.visible&&p.x+radius>=0&&p.x-radius<=r.w&&p.y+radius>=0&&p.y-radius<=r.h,clipped};});
   value.entityClipped=value.entities.filter(e=>e.clipped).map(e=>e.id);
   const focus=(r.sceneSpec.flat_map?.focus||[]).filter(f=>this.renderer.lastFrameTime>=flatNumber(f.start_time)&&this.renderer.lastFrameTime<=flatNumber(f.end_time,r.duration)).at(-1);
   if(focus){const center=r.core.projection.point(focus.coordinates),radius=flatNumber(focus.radius_degrees,5),corners=[];for(const x of [-radius,radius])for(const y of [-radius,radius])corners.push(this.project(center.clone().add(new THREE.Vector3(x,y,0))));const xs=corners.map(p=>p.x),ys=corners.map(p=>p.y);value.focusTargetBox={x:Math.max(0,Math.min(...xs)),y:Math.max(0,Math.min(...ys)),width:Math.max(0,Math.min(r.w,Math.max(...xs))-Math.max(0,Math.min(...xs))),height:Math.max(0,Math.min(r.h,Math.max(...ys))-Math.max(0,Math.min(...ys)))};}
   value.cameraPosition=this.camera.position.toArray();value.cameraQuaternion=this.camera.quaternion.toArray();value.cameraPositionUnits='normalized_earth_radius';value.cameraCoordinateUnits='registered_geographic_tangent_to_sphere';value.cameraProjectionMatrix=this.camera.projectionMatrix.toArray();
   value.meaningfulEventsRendered=(value.meaningfulEventsRendered||[]).filter(e=>{
    if(e.rendered_primitive==='information')return true;
    if(e.rendered_primitive==='world_label')return r.currentFrame.labels.some(l=>l.event_id===e.event_id&&l.opacity>.1);
    const source=(r.sceneSpec.visual_events||[]).find(v=>v.id===e.event_id);if(source?.coordinates)return this.project(r.core.projection.point(source.coordinates)).visible;
    return true;
   });
  }
  value.projectionTransition={kind:'REGISTERED_GEOMETRIC_TANGENT_TO_SPHERE',curvature:this.curvature,veil_opacity:0,source_projection:this.warp.projection.kind,anchor:this.warp.anchor,scale:this.warp.basis.scale,geography_sampling:'original_verified_projected_coordinates',land_ocean_subdivision_max_edge_degrees:1.5,ocean_cartographic_radial_separation:.0007*this.curvature,ocean_signed_surface_z_preserved:true,ocean_separation_scope:'Visual depth separation of independently tessellated meshes; not surveyed bathymetry or DEM'};
  return value;
 }
}

export function createGeographicPolishHooks(renderer){
 const controller=new FlatGeographicController(renderer);
 return {init:()=>controller.init(),beforeWorldRender:(r,t)=>controller.before(t),projectDisplayPoint:(r,p)=>controller.project(p),prepareLabels:(r,t,f)=>controller.labels(f),augmentAudit:(r,t,a)=>controller.audit(a),controller};
}
