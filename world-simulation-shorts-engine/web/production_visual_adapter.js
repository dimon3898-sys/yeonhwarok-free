/** Production Default v1: approved v004 visuals, authored motion timing and
 * restrained geographic labels. Frozen MASTER/v004 renderers are not edited.
 * Scene timestamps, route progress, narration and shader clocks stay independent.
 */
import * as THREE from 'three';
import {SceneFlatEntitySeparationPolishRenderer} from './flat_entity_separation_polish.js';
import {SceneEarthPolishRenderer} from './earth_polish_adapter.js';
import {flatClamp,flatNumber,flatSmooth,flatCameraEase,flatWindow,flatCoordinate} from './flat_semantics.js';

export const PRODUCTION_VISUAL_VERSION='v1';
export const PRODUCTION_ROUTE_POLICY=Object.freeze({
 coreWidth1080:6.25,lightLandCoreWidth1080:6.75,primaryHead1080:6.9,
 secondaryOpacity:.30,secondaryGlowOpacity:.028,directionCuePixels1080:14,
 geographyUnchanged:true,backgroundSampling:'verified geographic UV, local native source luminance',
});
const sameCountry=(feature,id)=>['ISO_A3','ISO_A3_EH','ADM0_A3','ISO_A2','ADMIN','NAME','NAME_EN'].some(key=>String(feature.properties[key]).toUpperCase()===String(id).toUpperCase());
const isProduction=scene=>scene.production_defaults?.version===PRODUCTION_VISUAL_VERSION;
const largeTitlesApproved=scene=>scene.production_defaults?.large_titles===true;
const cloneScene=scene=>JSON.parse(JSON.stringify(scene));

/** Adapt only approved, short, georeferenced text. No invented fact or position. */
export function productionLabelScene(scene){
 const result=cloneScene(scene);
 const extra=(scene.text_events||[]).filter(event=>scene.text_density!=='NONE'&&event.text&&event.coordinates&&
  (event.role!=='title'||event.large_title_approved===true&&largeTitlesApproved(scene)))
  .map(event=>({text:String(event.text),event_id:event.event_id||null,coordinates:event.coordinates,
   start_time:event.start_time,end_time:event.end_time,role:event.role||'status',
   kind:event.role==='question'?'hook_reveal':'world_label',size:event.role==='country'?54:48,opacity:.98,
   offset_x:event.role==='distance'?0:event.role==='question'?-70:60,
   offset_y:event.role==='distance'?-55:event.role==='question'?100:-35,
   production_text_event_id:event.id,route_id:event.route_id||null,display_anchor:event.display_anchor,
   priority:flatNumber(event.priority,1),persistent:Boolean(event.persistent)}));
 result.labels=scene.text_density==='NONE'?[]:[...(result.labels||[]),...extra];
 // Country/city events already create a geographic label in the base core.
 // An explicit text event is authoritative when both bind the same event.
 const bound=new Set(extra.map(event=>event.event_id).filter(Boolean));
 result.visual_events=(result.visual_events||[]).map(event=>bound.has(event.id)&&['country_reveal','city_reveal','region_reveal','destination_preview'].includes(event.kind)?{...event,text:''}:event);
 return result;
}

/** Real, independent camera travel and zoom intervals. Tracking/anticipation and
 * geometric handoff continue to consume unmodified scene time. No global speed. */
export function productionCameraIntervals(scene,maximumSpeed=3){
 const timing=scene.motion_timing||{},duration=flatNumber(scene.duration);
 const speed=flatClamp(flatNumber(scene.camera_speed,1),.6,maximumSpeed);
 // Older production JSON without a reference retains its authored interval.
 // New plans freeze the speed at authoring so later natural-language camera
 // edits can actually shorten/lengthen travel instead of only changing ease.
 const reference=flatClamp(flatNumber(timing.camera_speed_reference,speed),.6,maximumSpeed);
 const ratio=reference/speed,authoredTravel=Math.max(.15,flatNumber(timing.camera_travel_duration,duration));
 const authoredZoom=Math.max(.15,flatNumber(timing.zoom_duration,authoredTravel));
 return {travel:Math.max(.15,authoredTravel*ratio),zoom:Math.max(.15,authoredZoom*ratio),
  speed,reference,speedFactor:speed/reference,sourceDuration:duration};
}

export function productionFlatCameraValues(rig,t){
 const scene=rig.scene,duration=rig.duration,timing=scene.motion_timing||{};
 const {travel,zoom,speed,reference,speedFactor}=productionCameraIntervals(scene,2.5);
 const p=flatClamp(t/duration);
 const easing=scene.camera_easing||scene.flat_map?.camera_easing||'smootherstep';
 const e=flatCameraEase(Math.pow(flatClamp(t/travel),1/speed),easing);
 const ze=flatCameraEase(Math.pow(flatClamp(t/zoom),1/speed),easing);
 const center=rig.projection.point(rig.start).lerp(rig.projection.point(rig.end),e);
 let span=rig.start.span_degrees+(rig.end.span_degrees-rig.start.span_degrees)*ze;
 const envelope=p<=0||p>=1?0:Math.sin(Math.PI*p)**2;
 const primary=rig.routes.find(route=>!route.faint&&t>=route.start&&t<=route.end)||rig.routes.find(route=>!route.faint);
 if(['FLAT_ROUTE_FOLLOW','FLAT_ENTITY_FOLLOW'].includes(scene.camera_preset)&&primary)
  center.lerp(primary.point(primary.progress(t),0),flatNumber(scene.flat_map?.tracking,.38)*envelope);
 const preview=scene.flat_map?.next_event;let previewWeight=0;
 if(preview&&scene.camera_preset==='FLAT_NEXT_EVENT_PREVIEW'){
  const at=flatNumber(preview.event_time),lead=Math.max(.12,flatNumber(timing.next_event_lead_time,flatNumber(preview.lead_time,.7)));
  previewWeight=flatSmooth((t-at+lead)/lead)*flatNumber(preview.strength,.4)*envelope;
  center.lerp(rig.projection.point(preview.coordinates),previewWeight);
 }
 let tilt=rig.start.tilt+(rig.end.tilt-rig.start.tilt)*e;
 const handoffDuration=Math.max(.15,Math.min(1.5,flatNumber(scene.map_transition?.duration??scene.flat_map?.transition_duration,.42)));
 let handoff=0;if(['FLAT_TO_EARTH','EARTH_TO_FLAT'].includes(scene.transition_out))handoff=flatSmooth((t-duration+handoffDuration)/handoffDuration);
 if(scene.transition_in==='EARTH_TO_FLAT')handoff=Math.max(handoff,1-flatSmooth(t/handoffDuration));
 span*=1+.28*handoff;tilt+=(.15-tilt)*handoff;
 return {p,e,zoomEasing:ze,center,span,previewWeight,projectionHandoff:handoff,tilt,
  rotation:rig.start.rotation+(rig.end.rotation-rig.start.rotation)*e,
  bank:rig.start.bank+(rig.end.bank-rig.start.bank)*e,
  cameraTravelDuration:travel,zoomDuration:zoom,cameraSpeedReference:reference,cameraSpeedFactor:speedFactor,sourceTime:t,globalTimewarp:false};
}

export function productionRouteEmphasis(spec,focusTarget){
 const id=spec.route_id||spec.id;
 const explicit=spec.visibility_role==='primary'||spec.role==='primary';
 const secondary=spec.faint||spec.visibility_role==='context'||spec.visibility_role==='secondary'||spec.role==='secondary';
 return !secondary&&(explicit||!focusTarget||id===focusTarget||typeof focusTarget==='object'&&id===focusTarget.target_id);
}

/** Only distance/route information belongs on a moving path. Status labels keep
 * their explicit event location, even when a route ID supplies context. */
export function productionUsesRouteHeadAnchor(label){
 return Boolean(label.route_id&&(['distance','route'].includes(label.role)||label.display_anchor==='route_head'));
}

function makeDirectionCue(item){
 // Small, slender route chevron; it belongs to the path, not a screen HUD.
 const vertices=[-.58,-.40,0, -.42,-.55,0, .42,.13,0, -.42,-.55,0, .58,0,0, .42,.13,0,
  .58,0,0, .42,-.13,0, -.42,.55,0, .42,-.13,0, -.58,.40,0, -.42,.55,0];
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
 const material=item.head.material.clone();material.transparent=true;material.opacity=.72;material.depthWrite=false;material.side=THREE.DoubleSide;
 // The registered v004 handoff has already patched this material contract.
 material.onBeforeCompile=item.head.material.onBeforeCompile;
 material.customProgramCacheKey=item.head.material.customProgramCacheKey.bind(item.head.material);
 const cue=new THREE.Mesh(geometry,material);cue.renderOrder=5;cue.frustumCulled=false;return cue;
}

export class SceneProductionFlatRenderer extends SceneFlatEntitySeparationPolishRenderer {
 constructor(scene,plan){
  if(!isProduction(scene))throw Error('PRODUCTION_DEFAULT_V1_REQUIRED');
  super(productionLabelScene(scene),plan);this.authoredScene=scene;this.productionReady=false;
 }
 async init(){
  await super.init();
  this.cam.values=t=>productionFlatCameraValues(this.cam,t);
  const originalLabels=this.core.overlayLabels.bind(this.core);
  this.core.overlayLabels=t=>{
   if(this.sceneSpec.text_density==='NONE')return [];
   const labels=originalLabels(t);
   return largeTitlesApproved(this.sceneSpec)?labels:labels.filter(label=>!label.information);
  };
  const sample=document.createElement('canvas');sample.width=sample.height=1;this.backgroundContext=sample.getContext('2d',{willReadFrequently:true});
  for(const item of this.graphics.items){item.productionDirectionCue=makeDirectionCue(item);this.world.add(item.productionDirectionCue);}
  this.productionReady=true;this.frame(0);return this;
 }
 backgroundLuminance(route,progress){
  const coordinates=route.coordinate(progress),source=this.sceneSpec.flat_map?.terrain_texture;
  let image=this.day.image,u=(coordinates.lon+180)/360,v=(90-coordinates.lat)/180;
  if(this.terrain&&source&&coordinates.lon>=source.bounds[0]&&coordinates.lon<=source.bounds[2]&&coordinates.lat>=source.bounds[1]&&coordinates.lat<=source.bounds[3]){
   image=this.terrain.image;u=(coordinates.lon-source.bounds[0])/(source.bounds[2]-source.bounds[0]);v=(source.bounds[3]-coordinates.lat)/(source.bounds[3]-source.bounds[1]);
  }
  const c=this.backgroundContext;c.drawImage(image,Math.min(image.width-1,Math.max(0,u*image.width)),Math.min(image.height-1,Math.max(0,v*image.height)),1,1,0,0,1,1);
  const pixel=c.getImageData(0,0,1,1).data;return (pixel[0]*.2126+pixel[1]*.7152+pixel[2]*.0722)/255;
 }
 updateMap(t){
  super.updateMap(t);if(!this.productionReady)return;
  const fade=Math.max(.10,flatNumber(this.sceneSpec.motion_timing?.focus_transition_duration,.18)),pixel=this.core.cam.current.span/this.w;
  const focus=(this.sceneSpec.flat_map?.focus||[]).filter(value=>t>=flatNumber(value.start_time)&&t<=flatNumber(value.end_time,this.duration)).at(-1);
  if(focus){const strength=Math.min(.25,flatNumber(focus.strength,.16)*1.12*flatWindow(t,flatNumber(focus.start_time),flatNumber(focus.end_time,this.duration),fade,Boolean(focus.persistent||focus.end_time>=this.duration)));
   for(const material of this.materials)material.uniforms.uFocusStrength.value=strength;
  }
  for(const item of this.countryItems){
   const highlight=this.core.countryTargets.filter(value=>sameCountry(item.feature,value.country)&&t>=flatNumber(value.start_time)&&t<=flatNumber(value.end_time,this.duration)).at(-1);
   if(!highlight)continue;
   const weight=flatWindow(t,flatNumber(highlight.start_time),flatNumber(highlight.end_time,this.duration),fade,Boolean(highlight.persistent))*flatNumber(highlight.opacity,.20);
   item.material.uniforms.uTintOpacity.value=weight;
   item.material.uniforms.uSelectedWeight.value=Math.min(1,weight/Math.max(.001,flatNumber(highlight.opacity,.20)));
   item.borderMaterial.uniforms.uWidth.value=pixel*3.6;
   item.borderMaterial.uniforms.uOpacity.value=Math.min(.94,.53+weight*1.6);
   item.borderMaterial.uniforms.uColor.value.set(highlight.color||'#d0ab6b');
  }
  const active=Math.max(0,...this.countryItems.map(item=>item.material.uniforms.uSelectedWeight.value));
  for(const material of this.materials)material.uniforms.uSelectionActive.value=active;
 }
 polishRoutes(t){
  super.polishRoutes(t);if(!this.productionReady)return;
  const units=this.core.cam.current.span/this.w,scale1080=this.w/1080,presentationScale=this.w/2160;
  for(const item of this.graphics.items){
   const route=item.route,progress=this.core.routeProgress(route,t),focus=this.sceneSpec.focus_target;
   const routeFocus=typeof focus==='string'&&this.core.routes.some(value=>value.id===focus)?focus:focus&&typeof focus==='object'&&['route'].includes(focus.type||focus.kind||focus.target_type)?focus:null;
   const primary=productionRouteEmphasis(route.spec,routeFocus);
   const active=route.shown(t)&&t<route.end&&progress<.999999;
   let background=0;try{background=this.backgroundLuminance(route,progress);}catch(error){throw Error('PRODUCTION_ROUTE_BACKGROUND_SOURCE_FAILED: '+error);}
   const width=primary?(background>.55?6.75:6.25):3.25;
   // Ribbon width is a half-width in internal pixels; the 2× HIGH
   // downsample cancels that factor. Preserve the approved mobile line scale.
   item.mat.uniforms.uWidth.value=units*width*presentationScale;
   item.mat.uniforms.uOpacity.value=primary?1:.30;item.glowMat.uniforms.uOpacity.value=primary?.145:.028;
   if(primary)item.mat.uniforms.uColor.value.set(background>.55?'#d6f6ff':'#efffff');
   item.head.scale.setScalar(units*presentationScale*(primary?6.9:3.4)/.035);
   item.head.material.transparent=true;item.head.material.opacity=primary?1:.38;
   for(const [index,ghost] of item.headTrail.entries())ghost.ghost.material.opacity=(index===0?.12:.05)*(primary?1:.25);
   const cue=item.productionDirectionCue;cue.visible=primary&&active&&item.head.visible;
   if(cue.visible){const behind=flatClamp(progress-.013),point=route.point(behind,.064),tangent=route.tangent(progress);cue.position.copy(point);cue.rotation.z=Math.atan2(tangent.y,tangent.x);cue.scale.setScalar(units*scale1080*14);}
   item.productionRouteAudit={id:route.id,role:primary?'primary':'secondary',corePixels1080:width,opacity:item.mat.uniforms.uOpacity.value,headPixels1080:primary?6.9:3.4,directionCueVisible:cue.visible,backgroundSourceLuminance:background,backgroundAware:true};
  }
 }
 prepareFrame(t){
  if(!this.productionReady)return super.prepareFrame(t);
  const original=this.sceneSpec,originalCore=this.core.sceneSpec;
  // A distance or route-status label follows the verified great-circle head,
  // rather than an off-screen endpoint. Source coordinates remain immutable;
  // the actual display anchor is deterministically derived from that route.
  const temporary={...original,labels:(original.labels||[]).map(label=>{
   const route=productionUsesRouteHeadAnchor(label)?this.core.route(label.route_id):null;
   return route?{...label,coordinates:{...label.coordinates,...route.coordinate(this.core.routeProgress(route,t))},display_anchor_source:'verified_great_circle_route_head'}:label;
  })};
  let value;
  try{this.sceneSpec=temporary;this.core.sceneSpec=temporary;value=super.prepareFrame(t);}
  finally{this.sceneSpec=original;this.core.sceneSpec=originalCore;}
  // Keep any new label attached to its event source through the morph and
  // eliminate duplicate identical names at the same geographic anchor.
  const seen=new Set();value.labels=value.labels.filter(label=>{
   const key=`${label.text}|${Math.round(label.anchor?.x||0)}|${Math.round(label.anchor?.y||0)}`;
   if(seen.has(key)&&!label.event_id)return false;seen.add(key);return true;
  });return value;
 }
 audit(t){
  const value=super.audit(t);value.productionDefaults={version:'v1',pace:this.sceneSpec.pace||'FAST',textDensity:this.sceneSpec.text_density||'MINIMAL',largeTitlesApproved:largeTitlesApproved(this.sceneSpec),globalTimewarp:false,
   motionTiming:this.sceneSpec.motion_timing||{},cameraTravelDuration:this.core.cam.current.cameraTravelDuration,zoomDuration:this.core.cam.current.zoomDuration,cameraSpeedReference:this.core.cam.current.cameraSpeedReference,cameraSpeedFactor:this.core.cam.current.cameraSpeedFactor,sourceSceneTime:t,
   countryPalette:this.core.countryTargets.map(highlight=>({country:highlight.country,color:highlight.color,terrainPreserved:true})),
   routes:this.graphics.items.map(item=>item.productionRouteAudit).filter(Boolean),
   directLabels:this.labels.map(label=>({text:label.text,event_id:label.event_id,anchor:label.anchor,opacity:label.opacity,informationBanner:Boolean(label.information),box:{x:label.x,y:label.y,width:label.width,height:label.height}})),
   surfaceCoverage:this.sceneSpec.flat_map?.terrain_texture?.bounds||[-180,-90,180,90],outsideRegionalAtlas:'Verified global 8K Earth raster at geographic UV; no synthetic locations',
   preservedEntitySeparation:'v1',preservedProjectionHandoff:'v004_registered_geometric'};
  return value;
 }
}

/** Production Earth changes label policy, not the approved physical renderer.
 * A scene that adopts this policy receives a new truthful renderer/cache key.
 */
export class SceneProductionEarthRenderer extends SceneEarthPolishRenderer {
 constructor(scene,plan){
  if(!isProduction(scene))throw Error('PRODUCTION_DEFAULT_V1_REQUIRED');
  super(productionLabelScene(scene),plan);this.authoredScene=scene;this.productionReady=false;
 }
 async init(){
  await super.init();
  const original=this.cam.values.bind(this.cam);
  this.cam.values=t=>{
   const {travel,zoom}=productionCameraIntervals(this.sceneSpec,3);
   const mapped=Math.min(this.duration,t/travel*this.duration),value=original(mapped),zoomValue=original(Math.min(this.duration,t/zoom*this.duration));
   value.height=zoomValue.height;value.fov=zoomValue.fov;
   // Envelope for orbit/follow remains real scene time, not shifted shader time.
   value.p=flatClamp(t/this.duration);return value;
  };
  this.productionReady=true;this.frame(0);return this;
 }
 drawStoryInformation(t){
  this.eventVisibility=[];
  if(largeTitlesApproved(this.sceneSpec))return super.drawStoryInformation(t);
  // Explicit short text events have already become geographically anchored
  // labels in SceneEarthPolishRenderer.overlay. No generated story banner.
 }
 overlay(t){
  if(this.sceneSpec.text_density==='NONE'){this.labels=[];this.eventVisibility=[];return;}
  const original=this.sceneSpec;
  const temporary={...original,labels:(original.labels||[]).map(label=>{
   const route=productionUsesRouteHeadAnchor(label)?this.routes.byId(label.route_id):null;
   if(!route)return label;
   const point=route.curve.getPoint(this.routes.progress(t,route)).normalize();
   return {...label,coordinates:{...label.coordinates,lon:Math.atan2(-point.z,point.x)*180/Math.PI,lat:Math.asin(flatClamp(point.y,-1,1))*180/Math.PI},display_anchor_source:'verified_great_circle_route_head'};
  })};
  try{this.sceneSpec=temporary;super.overlay(t);}finally{this.sceneSpec=original;}
 }
 dispatchEventAudit(t){
  super.dispatchEventAudit(t);
  // The frozen base can attribute an existing network to a later peak. New
  // production peaks must instead prove a fresh bound path or a newly drawn
  // event label; an inherited old-edge receipt cannot bypass that condition.
  this.eventAudit=this.eventAudit.filter(receipt=>{
   const event=this.sceneSpec.visual_events.find(value=>value.id===receipt.event_id);
   return !event||!['final_reveal','peak_reveal','peak_moment'].includes(event.kind);
  });
  for(const event of this.sceneSpec.visual_events||[]){
   if(event.meaningful===false||this.eventAudit.some(receipt=>receipt.event_id===event.id))continue;
   const start=flatNumber(event.time),end=Math.min(this.duration,start+Math.max(.7,flatNumber(event.duration,1.35)));
   if(t<start||t>=end)continue;
   const label=this.labels.find(value=>value.event_id===event.id&&value.opacity>.1);
   const visibleRoutes=this.routes.routes.filter((route,index)=>this.graphics.items[index].mesh.visible&&this.routes.progress(t,route)>0&&Array.from({length:25},(_,i)=>this.project(route.curve.getPoint(this.routes.progress(t,route)*i/24))).some(point=>point.visible&&point.x>=this.w*.06&&point.x<=this.w*.91&&point.y>=this.h*.08&&point.y<=this.h*.85));
   const boundRoute=event.target_id?this.routes.byId(event.target_id):null;
   const freshNetwork=boundRoute&&boundRoute.start>=start-1e-6&&boundRoute.start<=t&&t<boundRoute.end&&this.routes.progress(t,boundRoute)>1e-6&&visibleRoutes.some(route=>route.id===boundRoute.id);
   if(['final_reveal','peak_reveal','peak_moment'].includes(event.kind)&&visibleRoutes.length>=2&&freshNetwork){
    this.eventAudit.push({event_id:event.id,kind:event.kind,rendered_primitive:'network',actual_time:t,scheduled_time:start,visible:true,route_ids:visibleRoutes.map(route=>route.id),progress:visibleRoutes.map(route=>this.routes.progress(t,route)),fresh_route_id:boundRoute.id,fresh_route_start:boundRoute.start});
   }else if(label){this.eventAudit.push({event_id:event.id,kind:event.kind,rendered_primitive:'world_label',actual_time:t,scheduled_time:start,visible:true,text:label.text,opacity:label.opacity,box:{x:label.x,y:label.y,width:label.width,height:label.height}});}
  }
 }
 audit(t){const value=super.audit(t);value.productionDefaults={version:'v1',pace:this.sceneSpec.pace||'FAST',textDensity:this.sceneSpec.text_density||'MINIMAL',largeTitlesApproved:largeTitlesApproved(this.sceneSpec),globalTimewarp:false,motionTiming:this.sceneSpec.motion_timing||{},sourceSceneTime:t,directLabels:this.labels.map(label=>({text:label.text,event_id:label.event_id,anchor:label.anchor,opacity:label.opacity,box:{x:label.x,y:label.y,width:label.width,height:label.height}})),earth:'preserved_v004_physical_renderer_readable_geography',earthUsage:'peak_or_global_reveal'};return value;}
}
