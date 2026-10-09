/** Explicit v020 Canvas2D additions over the unchanged v019 renderer.
 * Only observed character-reveal and single marker-pop rhythms are used.
 * Source text, geographic anchors, camera, shaders and textures stay inherited.
 */
import * as THREE from 'three';
import {SceneEventQualityRenderer} from './event_quality_adapter.js';
import {digestBytes,trustedStaticURL} from './visual_quality_adapter.js';
import {flatCoordinate} from './flat_semantics.js';
import {productionUsesRouteHeadAnchor} from './production_visual_adapter.js';

export const REFERENCE_EFFECTS_VERSION='v020';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)));
const smooth=v=>{const x=clamp(v);return x*x*(3-2*x);};
const fail=rule=>{throw Error(`REFERENCE_EFFECTS_${rule}`);};
const sha=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const frameAt=t=>Math.floor(t*30+1e-7);
const normal=coordinate=>{
 const q=flatCoordinate(coordinate),lat=q.lat*Math.PI/180,lon=q.lon*Math.PI/180;
 return new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));
};

export function validateReferenceEffectsEvents(events,durationFrames=720){
 if(!Array.isArray(events)||events.length>12)fail('EVENTS_INVALID');
 const ids=new Set();
 for(const event of events){
  if(!event||typeof event.id!=='string'||!event.id||ids.has(event.id)||
     typeof event.story_event_id!=='string'||typeof event.type!=='string'||
     !['MARKER_POP','TEXT_CHARACTER_REVEAL','NONE'].includes(event.pattern)||
     typeof event.primary!=='boolean'||!Array.isArray(event.reference_evidence_ids)||
     (event.pattern!=='NONE'&&!event.reference_evidence_ids.length)||!event.reference_evidence_ids.every(v=>typeof v==='string'&&v))fail('EVENT_INVALID');
  ids.add(event.id);
  if(![event.start_frame,event.peak_frame,event.end_frame].every(Number.isInteger)||
     event.start_frame<0||event.start_frame>event.peak_frame||(event.pattern!=='NONE'&&event.start_frame===event.peak_frame)||event.start_frame>=event.end_frame||
     event.peak_frame>event.end_frame||event.end_frame>durationFrames)fail('EVENT_FRAME_INVALID');
  if(!event.coordinates||!Number.isFinite(event.coordinates.lon)||!Number.isFinite(event.coordinates.lat)||
     Math.abs(event.coordinates.lon)>180||Math.abs(event.coordinates.lat)>90||typeof event.text!=='string')fail('EVENT_SOURCE_INVALID');
  if(event.pattern==='TEXT_CHARACTER_REVEAL'&&(!event.text||event.peak_frame-event.start_frame>18))fail('TEXT_REVEAL_INVALID');
  if(event.pattern==='MARKER_POP'&&(event.peak_frame-event.start_frame>12||event.end_frame-event.start_frame>45))fail('MARKER_DURATION_INVALID');
 }
 for(let frame=0;frame<durationFrames;frame++)if(events.filter(e=>e.primary&&e.pattern!=='NONE'&&frame>=e.start_frame&&frame<e.end_frame).length>1)fail('PRIMARY_DENSITY_INVALID');
 return events;
}

export function validateReferenceEffectsProfile(profile){
 if(profile?.version!==REFERENCE_EFFECTS_VERSION||profile.parent_version!=='v019')fail('PROFILE_VERSION_INVALID');
 const marker=profile.patterns?.MARKER_POP,text=profile.patterns?.TEXT_CHARACTER_REVEAL,limits=profile.limits;
 if(!sha(profile.reference_sha256)||profile.reference_fps!==30||!Number.isInteger(profile.reference_content_end_frame))fail('REFERENCE_SOURCE_INVALID');
 if(!marker||marker.pop_frames!==9||marker.peak_offset_frames!==4||marker.dip_offset_frames!==6||marker.start_scale!==.12||marker.peak_scale!==.95||marker.dip_scale!==.85||marker.radius_px!==10||!text||text.reveal_frames!==17)fail('PATTERN_INVALID');
 if(!limits||limits.max_primary!==1||limits.max_marker_frames!==45||limits.max_text_motion_frames!==18||limits.max_pops_per_event!==1||limits.max_added_sfx!==0)fail('LIMITS_INVALID');
 return profile;
}

export function characterRevealState(event,frame){
 const chars=[...event.text],progress=clamp((frame-event.start_frame)/(event.peak_frame-event.start_frame));
 const count=progress>=1?chars.length:Math.ceil(chars.length*progress);
 return {phase:frame<event.start_frame?'BEFORE':frame<event.peak_frame?'REVEAL':frame<event.end_frame?'HOLD':'AFTER',
  displayed_text:chars.slice(0,count).join(''),visible_chars:count,total_chars:chars.length,full_text_visible:count===chars.length&&progress>=1,
  character_scales:chars.slice(0,count).map((_,i)=>.12+.88*smooth(progress*chars.length-i))};
}

export function markerPopState(event,frame,profile){
 const marker=profile.patterns.MARKER_POP,settle=event.start_frame+marker.pop_frames,dip=event.start_frame+marker.dip_offset_frames;
 const scale=frame<event.peak_frame?marker.start_scale+(marker.peak_scale-marker.start_scale)*smooth((frame-event.start_frame)/(event.peak_frame-event.start_frame)):
  frame<dip?marker.peak_scale+(marker.dip_scale-marker.peak_scale)*smooth((frame-event.peak_frame)/(dip-event.peak_frame)):
  marker.dip_scale+(1-marker.dip_scale)*smooth((frame-dip)/(settle-dip));
 return {phase:frame<event.start_frame?'BEFORE':frame<event.peak_frame?'POP':frame<settle?'SETTLE':frame<event.end_frame?'HOLD':'AFTER',
  scale,settle_frame:settle};
}

function matchesLabel(event,label){
 if(event.pattern!=='TEXT_CHARACTER_REVEAL'||event.text!==label.text)return false;
 if(event.label_event_id)return event.label_event_id===label.event_id||event.label_event_id===label.production_text_event_id||event.story_event_id===label.event_id;
 if(label.event_id)return event.story_event_id===label.event_id;
 return event.coordinates?.location_id===label.coordinates?.location_id&&
  event.coordinates.lon===label.coordinates.lon&&event.coordinates.lat===label.coordinates.lat;
}

async function fetchProfile(selection){
 if(!sha(selection.profile_sha256))fail('SOURCE_HASH_REQUIRED');
 const url=trustedStaticURL(selection.profile_url);
 if(url!=='/static/reference_effects_v020.json')fail('SOURCE_URL_INVALID');
 const response=await fetch(url,{credentials:'same-origin',redirect:'error'});
 if(!response.ok)fail('PROFILE_FETCH_FAILED');
 const bytes=await response.arrayBuffer(),hash=await digestBytes(bytes);
 if(hash!==selection.profile_sha256)fail('SOURCE_HASH_MISMATCH');
 let value;try{value=JSON.parse(new TextDecoder().decode(bytes));}catch{fail('PROFILE_JSON_INVALID');}
 return {value:validateReferenceEffectsProfile(value),hash};
}

/** Absence is the original class, with no wrapper, profile fetch or new audit. */
export function createReferenceEffectsRenderer(scene,plan){
 return scene.reference_effects===undefined?new SceneEventQualityRenderer(scene,plan):new SceneReferenceEffectsRenderer(scene,plan);
}

export class SceneReferenceEffectsRenderer extends SceneEventQualityRenderer{
 constructor(scene,plan){
  if(scene.reference_effects?.version!==REFERENCE_EFFECTS_VERSION)fail('EXPLICIT_V020_OPT_IN_REQUIRED');
  validateReferenceEffectsEvents(scene.reference_effects.events,Math.round(scene.duration*30));
  super(scene,plan);this.referenceEffectsReady=false;this.referenceEffectReceipts=[];
 }
 async init(){
  await super.init();
  const loaded=await fetchProfile(this.sceneSpec.reference_effects);
  this.referenceEffectsProfile=loaded.value;this.referenceEffectsProfileHash=loaded.hash;
  this.referenceEffectsReady=true;this.frame(0);return this;
 }
 overlay(t){
  if(!this.referenceEffectsReady)return super.overlay(t);
  const frame=frameAt(t),events=this.sceneSpec.reference_effects.events;
  this.referenceEffectReceipts=[];
  const revealing=events.some(event=>event.pattern==='TEXT_CHARACTER_REVEAL'&&frame>=event.start_frame&&frame<event.peak_frame);
  if(revealing&&this.polishReady&&this.sceneSpec.text_density!=='NONE')this.characterOverlay(t,frame);
  else super.overlay(t);
  // Full-text frames use the exact inherited overlay. Receipts never create a
  // new story event and are derived from the actual measured label boxes.
  for(const event of events){
   if(event.pattern!=='TEXT_CHARACTER_REVEAL'||frame<event.start_frame||frame>=event.end_frame)continue;
   const label=this.labels.find(value=>matchesLabel(event,value));
   if(!label||this.referenceEffectReceipts.some(value=>value.id===event.id))continue;
   const state=characterRevealState(event,frame);
   this.referenceEffectReceipts.push(this.effectReceipt(event,state,label,label.opacity>.1&&state.visible_chars>0));
  }
  for(const event of events)if(event.pattern==='MARKER_POP'&&frame>=event.start_frame&&frame<event.end_frame)this.drawReferenceMarker(event,frame);
 }
 effectReceipt(event,state,box,visible){
  return {id:event.id,story_event_id:event.story_event_id,type:event.type,pattern:event.pattern,
   start_frame:event.start_frame,peak_frame:event.peak_frame,end_frame:event.end_frame,
   primary:event.primary,reference_evidence_ids:[...event.reference_evidence_ids],...state,visible,
   pixel_bounds:box?{x:box.x,y:box.y,width:box.width,height:box.height}:null};
 }
 /** The v004 2D loop is retained here solely for the short reveal interval.
  * Full source strings determine layout and collision bounds; only glyph count
  * changes. Its original font, opacity, shade, anchors and safe placement stay.
  */
 characterOverlay(t,frame){
  this.labels=[];const c=this.ctx,scale=this.w/1080,placed=[];
  const handoff=this.geographicHandoff,blend=handoff?smooth(t/handoff.duration):1,incoming=this.incomingCityBoxes();
  const candidates=[...(this.sceneSpec.labels||[])];
  for(const e of this.sceneSpec.visual_events||[])if(['destination_preview','region_reveal','country_reveal'].includes(String(e.kind).toLowerCase())&&e.coordinates&&e.text)candidates.push({text:e.text,event_id:e.id,kind:'world_label',coordinates:e.coordinates,start_time:e.time,end_time:e.time+1.4,opacity:.96,offset_x:90,offset_y:110});
  for(const source of candidates){
   let label=source;
   const route=productionUsesRouteHeadAnchor(label)?this.routes.byId(label.route_id):null;
   if(route){const point=route.curve.getPoint(this.routes.progress(t,route)).normalize();label={...label,coordinates:{...label.coordinates,lon:Math.atan2(-point.z,point.x)*180/Math.PI,lat:Math.asin(clamp(point.y,-1,1))*180/Math.PI}};}
   if(!label.text||!label.coordinates)continue;const start=Number(label.start_time||0),end=Number(label.end_time??this.duration);
   const hold=this.sceneSpec.scene_type==='FINAL_OVERVIEW'&&end>=this.duration-1e-6,fade=Math.min(.4,Math.max(.01,(end-start)/3));
   let opacity=t<start||t>end?0:smooth((t-start)/fade)*(hold?1:1-smooth((t-end+.4)/.4));
   const previous=incoming.find(b=>b.text===label.text),registered=previous&&handoff&&t<handoff.duration;
   if(registered)opacity=Math.max(opacity,previous.opacity*(1-blend));
   if(opacity<.01)continue;const point=normal(label.coordinates).multiplyScalar(1+.003*blend),p=this.project(point);
   if(!p.visible||p.x<this.w*.04||p.x>this.w*.96||p.y<this.h*.10||p.y>this.h*.78)continue;
   const font=Math.max(54,Number(label.size||46))*scale,spacing=1.8*scale;c.save();c.font=`400 ${font}px 'Noto Cinema'`;
   const width=c.measureText(label.text).width+Math.max(0,[...label.text].length-1)*spacing;
   let x=clamp(p.x+Number(label.offset_x??100)*scale,this.w*.13+width/2,this.w*.83-width/2)-width/2,y=clamp(p.y+Number(label.offset_y??110)*scale,this.h*.15+font,this.h*.78)-font;
   if(registered){x=previous.x+(x-previous.x)*blend;y=previous.y+(y-previous.y)*blend;}
   const box={text:label.text,event_id:label.event_id||null,kind:label.kind||'world_label',opacity:opacity*Number(label.opacity??.96),x,y,width,height:font*1.25,font,fontFamily:'Noto Cinema',anchor:p,incomingAircraftAvoidance:registered?previous.aircraftAvoidance:null};
   let tries=0;while(placed.some(b=>box.x<b.x+b.width+10*scale&&box.x+box.width>b.x-10*scale&&box.y<b.y+b.height+10*scale&&box.y+box.height>b.y-10*scale)&&tries++<4)box.y+=font*1.3;
   if(box.y+box.height>this.h*.82){c.restore();continue;}
   const effect=this.sceneSpec.reference_effects.events.find(event=>matchesLabel(event,label)&&frame>=event.start_frame&&frame<event.peak_frame);
   const state=effect?characterRevealState(effect,frame):null,displayed=state?state.displayed_text:label.text;
   if(displayed){
    c.save();c.translate(box.x+width/2,box.y+font*.65);c.scale((width+30*scale)/(font+20*scale),1);
    const radius=font*.92,shade=c.createRadialGradient(0,0,0,0,0,radius),support=.28*blend;
    shade.addColorStop(0,`rgba(3,12,22,${support})`);shade.addColorStop(.6,`rgba(3,12,22,${support*.7})`);shade.addColorStop(1,'rgba(3,12,22,0)');c.fillStyle=shade;c.fillRect(-radius,-radius,2*radius,2*radius);c.restore();
    c.globalAlpha=box.opacity;c.fillStyle=label.color||'#f3f1e5';c.shadowColor='rgba(6,22,31,.90)';c.shadowBlur=3*scale;c.shadowOffsetY=scale;c.strokeStyle='rgba(7,25,36,.78)';c.lineWidth=1.45*scale;
    let at=box.x,index=0;for(const ch of displayed){
     const glyphWidth=c.measureText(ch).width,glyphScale=state?.character_scales[index]??1;
     if(glyphScale<1){c.save();c.translate(at+glyphWidth/2,box.y+font*.65);c.scale(glyphScale,glyphScale);c.strokeText(ch,-glyphWidth/2,font*.35);c.fillText(ch,-glyphWidth/2,font*.35);c.restore();}
     else{c.strokeText(ch,at,box.y+font);c.fillText(ch,at,box.y+font);}
     at+=glyphWidth+spacing;index++;
    }
   }
   c.restore();
   if(state){Object.assign(box,{displayed_text:displayed,visible_chars:state.visible_chars,total_chars:state.total_chars});if(!displayed)box.opacity=0;this.referenceEffectReceipts.push(this.effectReceipt(effect,state,box,box.opacity>.1&&state.visible_chars>0));}
   this.labels.push(box);placed.push(box);
  }
  this.drawStoryInformation(t);
 }
 drawReferenceMarker(event,frame){
  const state=markerPopState(event,frame,this.referenceEffectsProfile),p=this.project(normal(event.coordinates).multiplyScalar(1.003));
  const scale=this.w/1080,radius=this.referenceEffectsProfile.patterns.MARKER_POP.radius_px*scale*state.scale,padding=2*scale;
  const box={x:p.x-radius-padding,y:p.y-radius-padding,width:(radius+padding)*2,height:(radius+padding)*2};
  const visible=this.sceneSpec.text_density!=='NONE'&&p.visible&&box.x>=this.w*.06&&box.x+box.width<=this.w*.91&&box.y>=this.h*.08&&box.y+box.height<=this.h*.85;
  if(visible){const c=this.ctx;c.save();c.globalAlpha=.75;c.beginPath();c.arc(p.x,p.y,radius,0,Math.PI*2);c.strokeStyle='rgba(7,25,36,.78)';c.lineWidth=4*scale;c.stroke();c.strokeStyle='#f3f1e5';c.lineWidth=2*scale;c.stroke();c.restore();}
  this.referenceEffectReceipts.push(this.effectReceipt(event,{...state,coordinates:{...event.coordinates},opacity:visible?.75:0},box,visible));
 }
 audit(t){
  const value=super.audit(t);if(!this.referenceEffectsReady)return value;
  value.effectLayer={version:REFERENCE_EFFECTS_VERSION,parent_version:'v019',profile_sha256:this.referenceEffectsProfileHash,
   frame:frameAt(t),phase:this.referenceEffectReceipts.length?'ACTIVE':'NONE',events:this.referenceEffectReceipts.map(receipt=>({...receipt})),
   additional_textures:0,additional_texture_uploads:0,render_scope:'Canvas2D overlay only',
   preserved:{camera:true,timing:true,material:true,regional_lod:true,night_source:true,text_content:true,audio:true}};
  return value;
 }
}
