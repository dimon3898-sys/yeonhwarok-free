/** Opt-in visual polish for the preserved premium flat renderer.
 * Ground geometry, verified coordinates, route progress and event times remain
 * owned by FlatSceneCore. This adapter changes their presentation only.
 */
import * as THREE from 'three';
import {createAircraftV3} from '/v3-src/aircraft_v3.js';
import {SceneFlatRenderer} from './flat_renderer.js';
import {FlatSceneCore,flatClamp,flatNumber,flatSmooth} from './flat_semantics.js';

export const FLAT_POLISH_VERSION='v004';
export const FLAT_POLISH_POLICY=Object.freeze({
 cityMinimumFont1080:54,primaryAircraftPixels1080:88,
 secondaryAircraftPixels1080:82,activeRouteCorePixels1080:5.5,
 stoppedCollisionSeparationPixels1080:58,legacyOpaqueVeil:false,
});

// Guarded shader adaptation fails loudly if the preserved material contract is
// changed. It never rewrites the shared shader or any GIS/raster source asset.
export function polishSurfaceShader(source){
 const replacements=[
  ['uniform vec3 uTint;','uniform vec3 uTint;\n uniform float uSelectionActive,uSelectedWeight;'],
  ['vec3(.007,.026,.060)*variation','vec3(.0045,.021,.053)*variation'],
  ['source=texture2D(uTerrain,terrainUV).rgb;',
   'vec3 globalSource=texture2D(uDay,uv).rgb;\n   vec3 globalNeighbors=(texture2D(uDay,uv+vec2(texel.x,0.)).rgb+texture2D(uDay,uv-vec2(texel.x,0.)).rgb+texture2D(uDay,uv+vec2(0.,texel.y)).rgb+texture2D(uDay,uv-vec2(0.,texel.y)).rgb)*.25;\n   source=texture2D(uTerrain,terrainUV).rgb;'],
  ['  }else{\n   source=texture2D(uDay,uv).rgb;',
   '   float roiEdge=min(min(vMap.x-uTerrainBounds.x,uTerrainBounds.z-vMap.x),min(latitude-uTerrainBounds.y,uTerrainBounds.w-latitude));\n   float roiFeather=smoothstep(0.,12.,roiEdge);\n   source=mix(globalSource,source,roiFeather);neighbors=mix(globalNeighbors,neighbors,roiFeather);\n  }else{\n   source=texture2D(uDay,uv).rgb;'],
  ['source+(source-neighbors)*.46','source+(source-neighbors)*.56'],
  ['mix(vec3(gray),source,1.32)','mix(vec3(gray),source,1.40)'],
  ['vec3 land=source*.63*hill*vec3(1.025,1.025,.93)+vec3(.002,.004,.001);',
   'source=max(vec3(0.),(source-vec3(.24))*1.10+vec3(.24));\n  vec3 land=source*.60*hill*vec3(1.00,1.04,.92)+vec3(.002,.004,.001);'],
  ['color=mix(color,uTint,uTintOpacity*uLand*.85);',
   'vec3 terrainTint=uTint/max(.25,dot(uTint,vec3(.2126,.7152,.0722)))*dot(color,vec3(.2126,.7152,.0722));\n  color=mix(color,terrainTint,clamp(uTintOpacity*uLand*1.32,0.,.42));\n  float selected=clamp(uSelectedWeight,0.,1.);\n  float surroundings=clamp(uSelectionActive,0.,1.)*(1.-selected);\n  color=mix(vec3(dot(color,vec3(.2126,.7152,.0722))),color,1.-surroundings*.10);\n  color*=1.-surroundings*.08;\n  vec3 selectedDetail=max(vec3(0.),(color-vec3(.20))*1.10+vec3(.20))*1.075;\n  color=mix(color,selectedDetail,selected);'],
 ];
 for(const [from,to] of replacements){
  if(!source.includes(from))throw Error('FLAT_POLISH_SURFACE_CONTRACT_CHANGED: '+from);
  source=source.replace(from,to);
 }
 return source;
}

/** Actual measured text boxes; opacity envelopes and information timing survive. */
export function polishFlatLabels(labels,width,height,context,options={}){
 const scale=width/1080,placed=[];
 return labels.map(original=>{
  const label={...original};if(original.anchor)label.anchor={...original.anchor};
  if(label.information)return label;
  const font=Math.max(flatNumber(label.font),FLAT_POLISH_POLICY.cityMinimumFont1080*scale);
  const city=!label.event_id;
  const family=city?'Noto Cinema':label.fontFamily||'Open Sans',weight=family==='Noto Cinema'?400:300;
  context.font=`${weight} ${font}px '${family}'`;
  const spacing=flatNumber(label.spacing,1.8*scale);
  const measured=context.measureText(label.text).width+Math.max(0,[...label.text].length-1)*spacing;
  const oldCenter=label.x+label.width/2,baseline=label.y+label.font;
  label.font=font;label.width=measured;label.height=font*1.25;
  if(city){label.fontFamily=family;label.fontWeight=400;label.polishCity=true;}
  label.x=flatClamp(oldCenter-measured/2,width*.09,width*.87-measured);
  label.y=flatClamp(baseline-font,height*.13,height*.79-label.height);
  label.color='#f3f1e5';label.opacity=Math.min(1,label.opacity*1.04);
  if(city&&options.scene){
   const scene=options.scene,source=(scene.labels||[]).find(source=>source.text===label.text&&source.coordinates);
   let side='above';
   if(source){
    const target=source.coordinates,incoming=(scene.routes||[]).filter(route=>{
     const end=route.points?.at(-1);return end&&Math.abs(end.lat-target.lat)<.02&&Math.abs(((end.lon-target.lon+540)%360)-180)<.02;
    });
    if(incoming.length){
     const direction=incoming.reduce((sum,route)=>{const origin=route.points[route.points.length-2];sum.x+=(((origin.lon-target.lon+540)%360)-180)*Math.cos(target.lat*Math.PI/180);sum.y+=origin.lat-target.lat;return sum;},{x:0,y:0});
     side=Math.abs(direction.y)>Math.abs(direction.x)*.35?(direction.y>0?'below':'above'):(direction.x<0?'right':'left');
    }
    // Resolve the preferred side once against the authored end framing, not
    // against moving aircraft. Subsequent frames retain this relative slot.
    const camera=scene.flat_map?.camera_end||scene.flat_map?.camera_start||scene.coordinates,span=flatNumber(camera.span_degrees,scene.flat_map?.span_degrees||38);
    const yOf=lat=>scene.flat_map?.projection==='LOCAL_EQUIRECTANGULAR'?lat:Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))*180/Math.PI;
    const anchor={x:width*.5+(((target.lon-camera.lon+540)%360)-180)*width/span,y:height*.5-(yOf(target.lat)-yOf(camera.lat))*width/span};
    const half=110*scale,pad=12*scale,boxFor=side=>side==='right'?{x:anchor.x+half+pad,y:anchor.y-label.height/2}:side==='left'?{x:anchor.x-half-pad-label.width,y:anchor.y-label.height/2}:side==='below'?{x:anchor.x-label.width/2,y:anchor.y+half+pad}:{x:anchor.x-label.width/2,y:anchor.y-half-pad-label.height};
    const choices=[side,...(side==='right'||side==='left'?['above','below','left','right']:['below','above','left','right'])];
    side=choices.find(candidate=>{const box=boxFor(candidate);return box.x>=width*.09&&box.x+label.width<=width*.87&&box.y>=height*.13&&box.y+label.height<=height*.79;})||side;
   }
   label.airportReservation={side,size1080:220,source:'verified_city_anchor_and_scene_route_arrival_direction'};
  }
  // Re-layout only the larger city boxes; no opaque panels obscure the map.
  let attempts=0;
  while(placed.some(b=>label.x<b.x+b.width+10*scale&&label.x+label.width>b.x-10*scale&&label.y<b.y+b.height+10*scale&&label.y+label.height>b.y-10*scale)&&attempts++<4)
   label.y+=font*1.30;
  if(label.y+label.height>height*.80)label.y=Math.max(height*.13,baseline-font-font*1.35);
  placed.push(label);return label;
 });
}

/** Screen-space layout against real projected aircraft bounds.
 * The country/city geographic anchor stays fixed; only the label box moves.
 * Exported so the registered incoming Earth shot can use the same policy.
 */
export function avoidCityLabelObstacles(labels,obstacles,width,height){
 const scale=width/1080,out=labels.map(label=>({...label})),placed=out.filter(label=>!label.polishCity);
 const area=(a,b,pad)=>Math.max(0,Math.min(a.x+a.width,b.x+b.width+pad)-Math.max(a.x,b.x-pad))*Math.max(0,Math.min(a.y+a.height,b.y+b.height+pad)-Math.max(a.y,b.y-pad));
 for(const label of out.filter(label=>label.polishCity)){
  const start={x:label.x,y:label.y};
  if(label.airportReservation&&label.anchor){
   const side=label.airportReservation.side,half=110*scale,pad=12*scale;
   const box=side==='right'?{x:label.anchor.x+half+pad,y:label.anchor.y-label.height/2}:side==='left'?{x:label.anchor.x-half-pad-label.width,y:label.anchor.y-label.height/2}:side==='below'?{x:label.anchor.x-label.width/2,y:label.anchor.y+half+pad}:{x:label.anchor.x-label.width/2,y:label.anchor.y-half-pad-label.height};
   label.x=flatClamp(box.x,width*.09,width*.87-label.width);label.y=flatClamp(box.y,height*.13,height*.79-label.height);
   const overlap=obstacles.reduce((sum,b)=>sum+area(label,b,10*scale),0)+placed.reduce((sum,b)=>sum+area(label,b,6*scale),0);
   label.aircraftAvoidance={x:label.x-start.x,y:label.y-start.y,projectedModelObstacles:obstacles.length,stableAirportSlot:side,unresolvedOverlap:overlap>1e-5};
   placed.push(label);continue;
  }
  const candidates=[[0,0],[0,-label.font*1.45],[0,label.font*1.45],[80*scale,0],[-80*scale,0],[0,-label.font*2.4],[0,label.font*2.4],[128*scale,0],[-128*scale,0],[192*scale,0],[-192*scale,0],[110*scale,-label.font*1.6],[-110*scale,-label.font*1.6]];
  let best=null;
  for(const [dx,dy] of candidates){
   const box={...label,x:flatClamp(start.x+dx,width*.09,width*.87-label.width),y:flatClamp(start.y+dy,height*.13,height*.79-label.height)};
   const overlap=obstacles.reduce((sum,b)=>sum+area(box,b,18*scale),0)+placed.reduce((sum,b)=>sum+area(box,b,10*scale),0);
   const displacement=(box.x-start.x)**2+(box.y-start.y)**2;
   const score=overlap*1000+displacement;
   if(!best||score<best.score)best={box,overlap,score};
  }
  label.x=best.box.x;label.y=best.box.y;
  label.aircraftAvoidance={x:label.x-start.x,y:label.y-start.y,projectedModelObstacles:obstacles.length,unresolvedOverlap:best.overlap>1e-5};
  placed.push(label);
 }
 return out;
}

export class SceneFlatPolishRenderer extends SceneFlatRenderer {
 constructor(scene,plan,options={}){
  if(scene.visual_polish?.version!==FLAT_POLISH_VERSION)throw Error('FLAT_POLISH_OPT_IN_V004_REQUIRED');
  super(scene,plan);
  this.polishHooks=options.hooks||null;this.polishReady=false;
  this.displayOffsets=new Map();this.polishVersion=FLAT_POLISH_VERSION;
 }
 setPolishHooks(hooks){this.polishHooks=hooks;return this;}
 async init(){
  await super.init();
  for(const material of this.materials){material.fragmentShader=polishSurfaceShader(material.fragmentShader);material.uniforms.uSelectionActive={value:0};material.uniforms.uSelectedWeight={value:0};material.needsUpdate=true;}
  this.polishReady=true;
  if(!this.polishHooks&&this.sceneSpec.transition_out==='FLAT_TO_EARTH'){
   const next=(this.plan.scenes||[]).find(scene=>Math.abs(flatNumber(scene.start_time)-flatNumber(this.sceneSpec.start_time)-this.duration)<1e-6);
   if(next?.visual_polish?.version===FLAT_POLISH_VERSION){
    const {createGeographicPolishHooks}=await import('./geographic_polish_transition.js');
    this.polishHooks=createGeographicPolishHooks(this);
   }
  }
  await this.polishHooks?.init?.(this);
  this.frame(0);return this;
 }
 updateMap(t){
  super.updateMap(t);if(!this.polishReady)return;
  const pixel=this.core.cam.current.span/this.w;
  for(const material of this.materials)material.uniforms.uSelectedWeight.value=0;
  for(const item of this.countryItems){
   const weight=item.material.uniforms.uTintOpacity.value;
   const highlight=this.core.countryTargets.filter(h=>['ISO_A3','ISO_A3_EH','ADM0_A3','ISO_A2','ADMIN','NAME','NAME_EN'].some(k=>String(item.feature.properties[k]).toUpperCase()===h.country)&&t>=flatNumber(h.start_time)&&t<=flatNumber(h.end_time,this.duration)).at(-1);
   item.material.uniforms.uSelectedWeight.value=highlight?Math.min(1,weight/Math.max(.001,flatNumber(highlight.opacity,.20))):0;
   if(weight>.005){
    item.borderMaterial.uniforms.uWidth.value=pixel*3.6;
    item.borderMaterial.uniforms.uOpacity.value=Math.min(.98,.61+weight*1.6);
    item.borderMaterial.uniforms.uColor.value.lerp(new THREE.Color('#f0c47d'),.20);
   }
  }
  const selectionActive=Math.max(0,...this.countryItems.map(item=>item.material.uniforms.uSelectedWeight.value));
  for(const material of this.materials)material.uniforms.uSelectionActive.value=selectionActive;
  // A slightly stronger spatial focus, keeping surrounding geography visible.
  for(const material of this.materials)material.uniforms.uFocusStrength.value=Math.min(.25,material.uniforms.uFocusStrength.value*1.12);
 }
 polishRoutes(t){
  const scale=this.core.cam.current.span/this.w;
  for(const item of this.graphics.items){
   const p=this.core.routeProgress(item.route,t);
   const held=flatNumber(item.route.spec.progress_start)>=.999999&&flatNumber(item.route.spec.progress_end,1)>=.999999;
   const complete=held||p>=.999999&&t>=item.route.end;
   if(item.route.faint||complete)continue;
   item.mat.uniforms.uWidth.value=scale*FLAT_POLISH_POLICY.activeRouteCorePixels1080;
   item.mat.uniforms.uOpacity.value=1;
   item.mat.uniforms.uColor.value.set('#d7f6ff');
   item.glowMat.uniforms.uOpacity.value=.16;
   item.head.scale.setScalar(scale*5.8/.035);
   // Existing short past-pose head samples remain; no whole-frame blur is added.
  }
 }
 polishEntities(t,frame){
  const scale1080=this.w/1080;
  this.displayOffsets.clear();
  for(const [index,item] of this.entities.items.entries()){
   if(item.spec.type!=='aircraft'||!item.model.visible)continue;
   const authored=flatNumber(item.spec.screen_size,74),minimum=index===0?88:82;
   const gain=Math.max(1,minimum/authored);
   item.model.scale.multiplyScalar(gain);item.shadow.scale.x*=gain;item.shadow.scale.y*=gain;
   for(const ghost of item.ghosts)ghost.model.scale.multiplyScalar(gain);
   item.model.updateMatrixWorld(true);
  }
  // At a common airport, a stationary cartographic proxy yields visual priority
  // to the departing aircraft. Its verified geographical anchor does not move.
  // Separation fades away as the departing aircraft clears the origin.
  const visible=this.entities.items.map((item,index)=>({item,pose:frame.entities[index]})).filter(v=>v.item.model.visible&&v.pose.alpha>.015);
  for(const stopped of visible.filter(v=>v.pose.mode==='stop')){
   let severity=0;const origin=this.core.project(stopped.item.model.position);
   for(const moving of visible.filter(v=>v!==stopped&&v.pose.mode!=='stop')){
    const other=this.core.project(moving.item.model.position),distance=Math.hypot(origin.x-other.x,origin.y-other.y)/scale1080;
    severity=Math.max(severity,(1-flatSmooth(distance/105))*flatSmooth(moving.pose.alpha/.30));
   }
   if(severity<.001)continue;
   const item=stopped.item,dx=58*scale1080*severity,dy=-32*scale1080*severity;
   const camera=this.core.camera||this.camera,anchor=item.model.position.clone(),ndc=anchor.clone().project(camera);
   const displaced=ndc.clone();displaced.x+=2*dx/this.w;displaced.y-=2*dy/this.h;displaced.unproject(camera);
   const delta=new THREE.Vector3(displaced.x-anchor.x,displaced.y-anchor.y,0);
   item.model.position.add(delta);item.shadow.position.add(delta);
   for(const ghost of item.ghosts)ghost.model.position.add(delta);
   const size=1-.23*severity,alpha=1-.32*severity;item.model.scale.multiplyScalar(size);item.shadow.scale.x*=size;item.shadow.scale.y*=size;
   item.model.traverse(o=>{if(o.isMesh)for(const material of Array.isArray(o.material)?o.material:[o.material])material.opacity*=alpha;});
   item.model.userData.alpha=stopped.pose.alpha*alpha;item.model.updateMatrixWorld(true);
   const display=this.core.project(item.model.position);
   this.displayOffsets.set(item.spec.id,{geographicAnchor:stopped.pose.position.toArray(),projectedGeographicAnchor:{x:origin.x,y:origin.y},displayOffsetPixels:{x:display.x-origin.x,y:display.y-origin.y},separationEnvelope:severity,scalePriority:size});
  }
 }
 prepareFrame(t){
  // Through an outgoing projection morph, city names hold to the exact cut.
  // This is local display policy; the authored IR and event timings are intact.
  const authored=this.core.sceneSpec;let frame;
  try{
   if(this.polishReady&&this.polishHooks&&this.sceneSpec.transition_out==='FLAT_TO_EARTH')
    this.core.sceneSpec={...authored,labels:(authored.labels||[]).map(label=>label.role==='city'&&flatNumber(label.end_time,this.duration)>=this.duration?{...label,persistent:true}:label)};
   frame=this.core.semanticFrame(t);
  }finally{this.core.sceneSpec=authored;}
  this.updateMap(t);this.graphics.update(t);this.entities.update(t,frame.entities);this.effects.update(frame);
  if(this.polishReady){this.polishRoutes(t);this.polishEntities(t,frame);}
  this.polishHooks?.beforeWorldRender?.(this,t,frame);
  frame.labels=polishFlatLabels(frame.labels,this.w,this.h,this.ctx,{scene:this.sceneSpec});
  this.polishHooks?.prepareLabels?.(this,t,frame);
  const obstacles=[];
  for(const item of this.entities.items){
   if(!item.model.visible||flatNumber(item.model.userData.alpha,1)<.08)continue;
   const box=new THREE.Box3().setFromObject(item.model),points=[];
   for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
    const point=new THREE.Vector3(x,y,z);
    points.push(this.polishHooks?.projectDisplayPoint?.(this,point)||this.core.project(point));
   }
   const visible=points.filter(p=>p.visible!==false&&Number.isFinite(p.x)&&Number.isFinite(p.y));
   if(visible.length){const x=Math.min(...visible.map(p=>p.x)),y=Math.min(...visible.map(p=>p.y));obstacles.push({x,y,width:Math.max(...visible.map(p=>p.x))-x,height:Math.max(...visible.map(p=>p.y))-y,entity_id:item.spec.id});}
  }
  frame.labels=avoidCityLabelObstacles(frame.labels,obstacles,this.w,this.h);
  // The receipt uses the boxes that will actually be drawn, not the old font box.
  frame.events=frame.events.map(event=>{
   if(!['world_label','information'].includes(event.rendered_primitive))return event;
   const label=frame.labels.find(label=>label.event_id===event.event_id&&label.opacity>.1);
   return label?{...event,text:label.text,opacity:label.opacity,box:{x:label.x,y:label.y,width:label.width,height:label.height}}:null;
  }).filter(Boolean);
  return frame;
 }
 sceneAt(t){
  const frame=this.prepareFrame(t);this.gl.render(this.world,this.camera);return frame;
 }
 drawOverlay(frame){
  // Existing information/country overlay stays intact; city glyphs receive a
  // slightly stronger real font and a thinner shadow edge, not opaque plates.
  super.drawOverlay({...frame,labels:frame.labels.filter(label=>!label.polishCity)});
  const c=this.ctx,s=this.w/1080;
  for(const label of frame.labels.filter(label=>label.polishCity)){
   c.save();c.globalAlpha=label.opacity;c.font=`400 ${label.font}px 'Noto Cinema'`;
   c.strokeStyle='rgba(9,30,42,.55)';c.lineWidth=1.1*s;
   const edgeX=label.x+label.width*.36,edgeY=label.y+label.height+5*s;
   c.beginPath();c.moveTo(label.anchor.x,label.anchor.y);c.lineTo(label.anchor.x+(edgeX-label.anchor.x)*.35,edgeY);c.lineTo(edgeX,edgeY);c.stroke();
   c.fillStyle='#f2ce91';c.beginPath();c.arc(label.anchor.x,label.anchor.y,3.3*s,0,Math.PI*2);c.fill();
   c.fillStyle=label.color;c.shadowColor='rgba(4,18,27,.94)';c.shadowBlur=2.6*s;c.shadowOffsetY=.8*s;
   c.strokeStyle='rgba(5,21,31,.85)';c.lineWidth=1.45*s;
   let x=label.x;for(const ch of label.text){c.strokeText(ch,x,label.y+label.font);c.fillText(ch,x,label.y+label.font);x+=c.measureText(ch).width+(label.spacing||0);}c.restore();
  }
  this.labels=frame.labels;
 }
 frame(t,samples=1){
  t=flatClamp(t,0,this.duration);this.lastFrameTime=t;samples=Math.max(1,Math.round(samples));
  let frame;
  for(let i=0;i<samples;i++){
   frame=this.sceneAt(flatClamp(t+(samples>1?(i/(samples-1)-.5)/90:0),0,this.duration));
   this.actx.globalAlpha=1/(i+1);this.actx.drawImage(this.gl.domElement,0,0);
  }
  this.ctx.globalAlpha=1;this.ctx.drawImage(this.accum,0,0);
  this.currentFrame=samples===1?frame:this.prepareFrame(t);
  this.drawOverlay(this.currentFrame);
  this.transitionOpacity=0;
  this.polishHooks?.afterCanvasRender?.(this,t,this.currentFrame);
  return this.canvas;
 }
 audit(t){
  // Avoid the legacy opacity-based audit suppression without touching the input
  // IR or the inherited renderer. Geometry morph visibility is audited by hooks.
  const authored=this.sceneSpec;let value;
  try{this.sceneSpec={...authored,transition_in:'camera_continuity',transition_out:'camera_continuity'};value=super.audit(t);}
  finally{this.sceneSpec=authored;}
  value.visualPolish={version:FLAT_POLISH_VERSION,legacyOpaqueVeil:false,surface:'Native terrain contrast + luminance-preserving selected-country tint',selectionActive:this.materials[0].uniforms.uSelectionActive?.value||0,surroundingLandBrightness:.92,surroundingLandSaturation:.90,selectedExposure:1.075,selectedContrast:1.10,minimumCityFont1080:54,primaryAircraftMinimumPixels1080:88,secondaryAircraftMinimumPixels1080:82};
  value.entities=value.entities.map(entity=>({...entity,cartographicDisplaySeparation:this.displayOffsets.get(entity.id)||null}));
  value.countryHighlights=value.countryHighlights.map(highlight=>({...highlight,tintMode:'luminance_preserving_translucent',textureReplaced:false}));
  value.meaningfulEventsRendered=this.currentFrame?.events||value.meaningfulEventsRendered;
  return this.polishHooks?.augmentAudit?.(this,t,value)||value;
 }
}

/** Reconstruct the outgoing aircraft footprint with the same real mesh and
 * presentation transforms. This helps the incoming geographic shot register
 * its first label boxes to the last drawn outgoing frame without another GL
 * context, raster render, texture fetch or change to verified coordinates.
 * `project` maps the original projected-map Vector3 through the registered
 * handoff camera/curvature. It must return screen coordinates in width×height.
 */
export function flatPolishProjectedAircraftObstacles(scene,plan,time,width,height,options={}){
 const local={...scene,transition_in:'camera_continuity',transition_out:'camera_continuity'};
 const core=new FlatSceneCore(local,plan,{width,height}),frame=core.semanticFrame(time),scale=core.cam.current.span/width;
 const items=core.entities.map((spec,index)=>{
  const pose=frame.entities[index],model=spec.type==='aircraft'?createAircraftV3():new THREE.Group();
  model.visible=spec.type==='aircraft'&&pose.visible;model.position.copy(pose.position);
  const worldScale=flatNumber(spec.screen_size,74)*(width/1080)*scale/1.45;
  model.scale.setScalar(worldScale);model.position.z=Math.max(.16,worldScale*.13+.045);
  model.rotation.set(0,spec.type==='aircraft'?.065*Math.sin(time*1.3):0,Math.atan2(-pose.tangent.x,pose.tangent.y));model.userData.alpha=pose.alpha;
  const shadow=new THREE.Object3D();shadow.position.copy(model.position);shadow.scale.set(worldScale*.90,worldScale*.86,1);
  return {spec,model,shadow,ghosts:[]};
 });
 const proxy={w:width,h:height,core,camera:core.camera,entities:{items},displayOffsets:new Map()};
 SceneFlatPolishRenderer.prototype.polishEntities.call(proxy,time,frame);
 const project=options.project||((point)=>core.project(point)),obstacles=[];
 for(const item of items){
  if(!item.model.visible||flatNumber(item.model.userData.alpha,1)<.08)continue;
  const box=new THREE.Box3().setFromObject(item.model),points=[];
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z])points.push(project(new THREE.Vector3(x,y,z)));
  const visible=points.filter(p=>p.visible!==false&&Number.isFinite(p.x)&&Number.isFinite(p.y));
  if(visible.length){const x=Math.min(...visible.map(p=>p.x)),y=Math.min(...visible.map(p=>p.y));obstacles.push({x,y,width:Math.max(...visible.map(p=>p.x))-x,height:Math.max(...visible.map(p=>p.y))-y,entity_id:item.spec.id,source:'reconstructed_v004_actual_aircraft_mesh_pose',pose_time:time});}
 }
 // These temporary models have no GPU allocations. Dispose only their private
 // geometry/materials; the preserved library and active renderer are untouched.
 for(const item of items)item.model.traverse(object=>{if(object.isMesh){object.geometry.dispose();for(const material of Array.isArray(object.material)?object.material:[object.material])material.dispose();}});
 return obstacles;
}
