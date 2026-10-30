/** Explicit geographic label contract. No font, renderer, GPU or network work. */
export const LABEL_ROLES=Object.freeze(['COUNTRY','EVENT','NUMERIC']);
export const MAX_LABELS=16;
export const MAX_LABEL_GRAPHEMES=24;
const own=(value,key)=>Object.prototype.hasOwnProperty.call(value,key);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const check=(value,code)=>{if(!value)throw Error(code);};
const id=value=>typeof value==='string'&&/^[A-Za-z0-9_.:-]{1,64}$/.test(value);
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&Math.abs(value[0])<=180&&Math.abs(value[1])<=90;
function keys(value,allowed,code){check(object(value),code+'_OBJECT_REQUIRED');check(Object.keys(value).every(key=>allowed.includes(key)),code+'_UNKNOWN_FIELD');}
export function validateLabelText(value){
 check(typeof value==='string'&&value===value.trim()&&value.length>0&&value.normalize('NFC')===value,'PRESENTATION_LABEL_TEXT_REQUIRED');
 check(!/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f<>]/u.test(value)&&!/[\ud800-\udfff]/u.test(value),'PRESENTATION_LABEL_TEXT_UNSAFE');
 // This opt-in layer promises the pinned Korean font's finite supported scope,
 // not an unverified system-font/emoji fallback for arbitrary Unicode strings.
 const punctuation=' .,:;!?%+-/()[]{}=_\'"#&@$';
 check([...value].every(character=>/^[\uac00-\ud7a3A-Za-z0-9]$/u.test(character)||punctuation.includes(character)),'PRESENTATION_LABEL_FONT_GLYPH_UNSUPPORTED');
 check(typeof Intl?.Segmenter==='function','PRESENTATION_LABEL_SEGMENTER_REQUIRED');
 const length=[...new Intl.Segmenter('ko',{granularity:'grapheme'}).segment(value)].length;
 check(length<=MAX_LABEL_GRAPHEMES&&new TextEncoder().encode(value).length<=160,'PRESENTATION_LABEL_TEXT_TOO_LONG');
 return value;
}

/** Locations own the geographic anchor; highlights own event association/clock.
 * Optional anchor input is accepted only as an exact repeated compiled binding.
 * With no explicit label spec, callers must leave their legacy output unchanged.
 */
export function validateLabelSpec(spec,{scene,highlights=[]}={}){
 keys(spec,['enabled','items'],'PRESENTATION_LABELS');
 check(spec.enabled===true,'PRESENTATION_LABELS_EXPLICIT_OPT_IN_REQUIRED');
 check(scene?.timing?.fps===30&&Number.isSafeInteger(scene.timing.total_frames)&&scene.timing.total_frames>=2&&scene.timing.total_frames<=300,'PRESENTATION_LABEL_SCENE_TIMING_REQUIRED');
 check(Array.isArray(scene.locations)&&Array.isArray(highlights),'PRESENTATION_LABEL_BINDING_COLLECTION_REQUIRED');
 check(Array.isArray(spec.items)&&spec.items.length>=1&&spec.items.length<=MAX_LABELS,'PRESENTATION_LABEL_CAPACITY');
 const frames=scene.timing.total_frames,seen=new Set();
 const items=spec.items.map(item=>{
  keys(item,['id','role','text','locationId','anchor','eventId','startFrame','endFrame','revealFrames','exitFrames','priority'],'PRESENTATION_LABEL');
  check(id(item.id)&&!seen.has(item.id),'PRESENTATION_LABEL_ID_INVALID');seen.add(item.id);
  check(LABEL_ROLES.includes(item.role),'PRESENTATION_LABEL_ROLE_INVALID');
  const text=validateLabelText(item.text);
  check(item.role!=='NUMERIC'||/\p{N}/u.test(text),'PRESENTATION_NUMERIC_LABEL_VALUE_REQUIRED');
  check(id(item.locationId),'PRESENTATION_LABEL_LOCATION_REQUIRED');
  const locations=scene.locations.filter(location=>location.id===item.locationId);
  check(locations.length===1&&point(locations[0].anchor),'PRESENTATION_LABEL_LOCATION_BINDING_REQUIRED');
  const anchor=locations[0].anchor;
  check(!own(item,'anchor')||point(item.anchor)&&item.anchor.every((value,index)=>value===anchor[index]),'PRESENTATION_LABEL_ANCHOR_BINDING_CHANGED');
  check(Number.isSafeInteger(item.startFrame)&&Number.isSafeInteger(item.endFrame)&&item.startFrame>=0&&item.endFrame<=frames&&item.endFrame-item.startFrame>=4,'PRESENTATION_LABEL_TIMING_INVALID');
  const duration=item.endFrame-item.startFrame,defaultFade=Math.max(1,Math.min(8,Math.floor(duration/4))),reveal=item.revealFrames??defaultFade,exit=item.exitFrames??defaultFade;
  check(Number.isSafeInteger(reveal)&&Number.isSafeInteger(exit)&&reveal>=1&&reveal<=30&&exit>=1&&exit<=30&&reveal+exit<duration,'PRESENTATION_LABEL_REVEAL_HOLD_EXIT_INVALID');
  const priority=item.priority??({COUNTRY:30,EVENT:100,NUMERIC:80}[item.role]);
  check(Number.isSafeInteger(priority)&&priority>=0&&priority<=100,'PRESENTATION_LABEL_PRIORITY_INVALID');
  if(item.role==='COUNTRY')check(!own(item,'eventId'),'PRESENTATION_COUNTRY_LABEL_EVENT_FORBIDDEN');
  else{
   check(id(item.eventId),'PRESENTATION_LABEL_EVENT_REQUIRED');
   const events=highlights.filter(event=>event.id===item.eventId);
   check(events.length===1&&events[0].locationId===item.locationId&&Number.isSafeInteger(events[0].startFrame)&&Number.isSafeInteger(events[0].endFrame)&&item.startFrame>=events[0].startFrame&&item.endFrame<=events[0].endFrame,'PRESENTATION_LABEL_EVENT_LOCATION_OR_TIMING_MISMATCH');
  }
  return{id:item.id,role:item.role,text,locationId:item.locationId,anchor:[...anchor],...(item.role==='COUNTRY'?{}:{eventId:item.eventId}),startFrame:item.startFrame,endFrame:item.endFrame,revealFrames:reveal,exitFrames:exit,priority};
 });
 return{enabled:true,items};
}
