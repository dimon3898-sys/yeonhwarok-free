/** v021: authored status information inside inherited, immutable camera locks.
 * Only Canvas2D label presentation changes. Parent frame/camera/map/audio paths
 * are inherited; absence is the original v020 factory and class.
 */
import {SceneReferenceEffectsRenderer,createReferenceEffectsRenderer} from './reference_effects_adapter.js';
import {digestBytes,trustedStaticURL} from './visual_quality_adapter.js';

export const STORY_PROGRESSION_VERSION='v021';
const fail=rule=>{throw Error(`STORY_PROGRESSION_${rule}`);};
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const finiteCoordinate=value=>value&&Number.isFinite(value.lon)&&Number.isFinite(value.lat)&&Math.abs(value.lon)<=180&&Math.abs(value.lat)<=90;
const fpsValue=value=>{const parts=String(value).split('/').map(Number);return parts.length===1?parts[0]:parts.length===2?parts[0]/parts[1]:NaN;};
const frameAt=(time,fps)=>Math.floor(time*fps+1e-7);
const phases=new Set(['EVENT_REVEAL','STATE_CHANGE','PERCEPTION','LOCATION_EMPHASIS','EVENT_STATE']);
const patterns=new Set(['NONE','TEXT_REVEAL_HALO','LOCATION_TEXT_HALO']);
const expectedProfile={version:'v021',parent_version:'v020',reference_sha256:'853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc',
 timing:{reference_fps:30,text_reveal_frames:17,recognition_gap_frames:24,location_emphasis_frames:17},
 typography:{event_size_px:64,event_weight:400,event_opacity:.98,location_opacity:.6},
 patterns:{TEXT_REVEAL_HALO:{max_frames:17,primary:false},LOCATION_TEXT_HALO:{max_frames:17,primary:true}},
 limits:{max_primary:1,max_added_sfx:0,max_added_textures:0,max_effect_frames:17,max_location_emphasis_per_event:1},
 geometry:{status:'NOT_AVAILABLE_IN_CURRENT_SCENE',action:'NO_BOUNDARY_DRAW_WITHOUT_AUTHORED_EVENT_BOUND_GIS'},
 evidence:[{id:'REF_LABEL_CHARACTER_ENTRANCE',start_frame:289,end_frame:306,second_start_frame:311,second_end_frame:328},{id:'REF_SHORT_LABEL_HALO',start_frame:289,end_frame:306}],
 audio:{action:'Preserve exact v020 audio; no new SFX or TTS'},
 design:{font:'Existing Noto Cinema; weight preserved',halo:'Brief neutral text-local halo only; no reference colour copied',texture_uploads:0,shader_changes:false}};

export function validateStoryProgressionProfile(profile){
 if(profile?.version!=='v021'||profile.parent_version!=='v020'||!sha(profile.reference_sha256))fail('PROFILE_VERSION_INVALID');
 const timing=profile.timing,style=profile.typography,limits=profile.limits;
 if(!timing||timing.reference_fps!==30||timing.text_reveal_frames!==17||timing.recognition_gap_frames!==24||timing.location_emphasis_frames!==17)fail('TIMING_INVALID');
 if(!style||style.event_size_px!==64||style.event_weight!==400||style.event_opacity!==.98||style.location_opacity!==.60)fail('TEXT_HIERARCHY_INVALID');
 if(!limits||limits.max_primary!==1||limits.max_added_sfx!==0||limits.max_added_textures!==0||limits.max_effect_frames!==17||limits.max_location_emphasis_per_event!==1)fail('LIMITS_INVALID');
 if(!same(profile.patterns,{TEXT_REVEAL_HALO:{max_frames:17,primary:false},LOCATION_TEXT_HALO:{max_frames:17,primary:true}}))fail('PATTERN_INVALID');
 if(profile.geometry?.status!=='NOT_AVAILABLE_IN_CURRENT_SCENE'||profile.geometry.action!=='NO_BOUNDARY_DRAW_WITHOUT_AUTHORED_EVENT_BOUND_GIS')fail('FAKE_GEOMETRY');
 if(!same(profile,expectedProfile))fail('PROFILE_CONTRACT_INVALID');
 return profile;
}

/** Bind only existing status text and a declared lock; no text or GIS invention. */
export function validateStoryProgressionSelection(scene){
 const selected=scene.story_progression;
 if(selected?.version!==STORY_PROGRESSION_VERSION||selected.parent_version!=='v020'||scene.reference_effects?.version!=='v020')fail('EXPLICIT_V021_OPT_IN_REQUIRED');
 const fps=fpsValue(selected.fps),total=scene.frame_count;
 if(!Number.isFinite(fps)||fps<=0||!Number.isInteger(total)||total<=0||Math.abs(scene.duration*fps-total)>1e-7)fail('FRAME_GRID_INVALID');
 if(![selected.profile_sha256,selected.source_sha256,selected.camera_sha256,selected.quality_sha256].every(sha))fail('SOURCE_HASH_REQUIRED');
 if(selected.boundary?.status!=='NOT_AVAILABLE'||selected.boundary.geometry_ref!==null)fail('FAKE_GEOMETRY');
 if(!Array.isArray(selected.microbeats)||selected.microbeats.length>128)fail('MICROBEATS_INVALID');
 const ids=new Set(),emphasisCounts=new Map();
 for(const beat of selected.microbeats){
  if(!beat||typeof beat.id!=='string'||!beat.id||ids.has(beat.id)||!phases.has(beat.phase)||!patterns.has(beat.pattern)||typeof beat.primary!=='boolean')fail('MICROBEAT_INVALID');
  ids.add(beat.id);
  if(![beat.start_frame,beat.end_frame].every(Number.isInteger)||beat.start_frame<0||beat.start_frame>=beat.end_frame||beat.end_frame>total)fail('MICROBEAT_FRAME_INVALID');
  const event=(scene.visual_events||[]).find(value=>value.id===beat.story_event_id),text=(scene.text_events||[]).find(value=>value.id===beat.text_event_id);
  if(!event||!text||text.role!=='status'||typeof text.text!=='string'||!text.text||text.event_id!==event.id||event.text!==text.text||beat.primary_information!==text.text||beat.target_id!==event.target_id||!finiteCoordinate(beat.coordinates)||!same(beat.coordinates,text.coordinates)||!same(beat.coordinates,event.coordinates)||beat.coordinates.location_id!==beat.target_id)fail('UNSUPPORTED_STORY_EVENT');
  const source=beat.source_ref,eventIndex=(scene.visual_events||[]).indexOf(event),textIndex=(scene.text_events||[]).indexOf(text);
  if(source?.event_path!==`visual_events[${eventIndex}]`||source.text_path!==`text_events[${textIndex}]`||!sha(source.event_sha256)||!sha(source.text_sha256)||beat.claim_id!==(event.claim_id??null)||beat.caused_by!==(event.caused_by??null))fail('SOURCE_BINDING_INVALID');
  if(beat.geometry_ref!==null||beat.semantic_segment_ref!==null)fail('FAKE_GEOMETRY');
  const lock=beat.camera_lock_ref;
  if(!lock||!Number.isInteger(lock.start_frame)||!Number.isInteger(lock.end_frame)||lock.start_frame>beat.start_frame||lock.end_frame<beat.end_frame||!Array.isArray(lock.source_paths)||!lock.source_paths.length)fail('CAMERA_CHANGED_DURING_EVENT_VIEW');
  const timeline=scene.second_event_camera?.timeline;
  if(timeline){
   const valid=new Set(['EVENT1_VIEW','EVENT1_HOLD','EVENT1_RESOLVED','EVENT2_VIEW','EVENT2_HOLD','EVENT2_RESOLVED']);
   const entries=lock.source_paths.map(sourcePath=>{const match=/^second_event_camera\.timeline\[(\d+)\]$/.exec(sourcePath);return match?timeline[Number(match[1])]:null;});
   if(entries.some(value=>!value||!valid.has(value.state))||entries[0].start_frame!==lock.start_frame||entries.at(-1).end_frame!==lock.end_frame||!scene.second_event_camera[lock.camera_key])fail('CAMERA_CHANGED_DURING_EVENT_VIEW');
   for(let index=1;index<entries.length;index++)if(entries[index-1].end_frame!==entries[index].start_frame)fail('CAMERA_CHANGED_DURING_EVENT_VIEW');
   const cameraKeys=new Set(entries.map(entry=>entry.state.startsWith('EVENT1_')?'event1_camera':'event2_camera'));
   if(cameraKeys.size!==1||!cameraKeys.has(lock.camera_key))fail('CAMERA_CHANGED_DURING_EVENT_VIEW');
  }else{
   const authored=(scene.direction?.locked_windows||[]).find(value=>value.start_frame===lock.start_frame&&value.end_frame===lock.end_frame&&value.camera_key===lock.camera_key);
   if(!authored||!['camera_start','camera_end'].includes(lock.camera_key)||!scene.camera_start||!scene.camera_end||!same(scene.camera_start,scene.camera_end))fail('CAMERA_CHANGED_DURING_EVENT_VIEW');
  }
  const authoredStart=frameAt(text.start_time,fps),authoredEnd=frameAt(text.end_time,fps);
  if(beat.start_frame<authoredStart||beat.end_frame>authoredEnd||frameAt(event.time,fps)!==authoredStart)fail('SOURCE_TIMING_INVALID');
  const maxFrames=Math.max(1,Math.round(17*fps/30));
  if(beat.pattern!=='NONE'&&beat.end_frame-beat.start_frame>maxFrames)fail('CONTINUOUS_EFFECT');
  if(beat.pattern==='TEXT_REVEAL_HALO'&&(!['EVENT_REVEAL','STATE_CHANGE'].includes(beat.phase)||beat.primary||beat.start_frame!==authoredStart))fail('PATTERN_INVALID');
  if(beat.pattern==='LOCATION_TEXT_HALO'){
   const label=scene.labels?.[beat.location_label_ref];
   if(beat.phase!=='LOCATION_EMPHASIS'||!beat.primary||!Number.isInteger(beat.location_label_ref)||!label?.text||!same(label.coordinates,beat.coordinates)||!['city','country'].includes(label.role))fail('LOCATION_BINDING_INVALID');
   emphasisCounts.set(event.id,(emphasisCounts.get(event.id)||0)+1);if(emphasisCounts.get(event.id)>1)fail('EXCESSIVE_LOCATION_EMPHASIS');
  }else if(beat.location_label_ref!==null||beat.primary)fail('PATTERN_INVALID');
  if(beat.pattern==='NONE'&&!['PERCEPTION','EVENT_STATE'].includes(beat.phase))fail('PATTERN_INVALID');
 }
 const groups=new Map();for(const beat of selected.microbeats){if(!groups.has(beat.story_event_id))groups.set(beat.story_event_id,[]);groups.get(beat.story_event_id).push(beat);}
 for(const beats of groups.values()){
  const ordered=[...beats].sort((a,b)=>a.start_frame-b.start_frame),sequence=ordered.map(beat=>beat.phase);
  if(!['EVENT_REVEAL','STATE_CHANGE'].includes(sequence[0])||sequence[1]!=='PERCEPTION'||!([2,4].includes(sequence.length))||sequence.length===4&&(sequence[2]!=='LOCATION_EMPHASIS'||sequence[3]!=='EVENT_STATE'))fail('MICRO_BEAT_ORDER_INVALID');
  for(let index=1;index<ordered.length;index++)if(ordered[index-1].end_frame!==ordered[index].start_frame)fail('MICRO_BEAT_ORDER_INVALID');
 }
 for(let frame=0;frame<total;frame++){
  const own=selected.microbeats.filter(beat=>beat.primary&&frame>=beat.start_frame&&frame<beat.end_frame).length;
  const parent=scene.reference_effects.events.filter(event=>event.primary&&event.pattern!=='NONE'&&frame>=event.start_frame&&frame<event.end_frame).length;
  if(own+parent>1)fail('TOO_MANY_PRIMARY_EFFECTS');
  const active=selected.microbeats.filter(beat=>frame>=beat.start_frame&&frame<beat.end_frame);
  if(new Set(active.map(beat=>beat.story_event_id)).size>1)fail('TEXT_PRIORITY_CONFLICT');
 }
 return {selected,fps,total};
}

async function fetchProfile(selected){
 const url=trustedStaticURL(selected.profile_url);if(url!=='/static/story_progression_v021.json')fail('SOURCE_URL_INVALID');
 const response=await fetch(url,{credentials:'same-origin',redirect:'error'});if(!response.ok)fail('PROFILE_FETCH_FAILED');
 const bytes=await response.arrayBuffer(),hash=await digestBytes(bytes);if(hash!==selected.profile_sha256)fail('SOURCE_HASH_MISMATCH');
 let value;try{value=JSON.parse(new TextDecoder().decode(bytes));}catch{fail('PROFILE_JSON_INVALID');}
 return {value:validateStoryProgressionProfile(value),hash};
}

export function createStoryProgressionRenderer(scene,plan){
 return scene.story_progression===undefined?createReferenceEffectsRenderer(scene,plan):new SceneStoryProgressionRenderer(scene,plan);
}

export class SceneStoryProgressionRenderer extends SceneReferenceEffectsRenderer{
 constructor(scene,plan){
  const contract=validateStoryProgressionSelection(scene);super(scene,plan);
  this.storyProgressionAuthoredScene=scene;this.storyProgressionFPS=contract.fps;
  this.storyProgressionReady=false;this.storyProgressionReceipts=[];
 }
 async init(){
  await super.init();const loaded=await fetchProfile(this.storyProgressionAuthoredScene.story_progression);
  this.storyProgressionProfile=loaded.value;this.storyProgressionProfileHash=loaded.hash;
  this.storyProgressionReady=true;this.frame(0);return this;
 }
 overlay(t){
  if(!this.storyProgressionReady)return super.overlay(t);
  const frame=frameAt(t,this.storyProgressionFPS),selection=this.storyProgressionAuthoredScene.story_progression;
  const active=selection.microbeats.filter(beat=>frame>=beat.start_frame&&frame<beat.end_frame);
  this.storyProgressionReceipts=[];
  if(!active.length)return super.overlay(t);
  const beat=active[0],status=this.storyProgressionAuthoredScene.text_events.find(value=>value.id===beat.text_event_id);
  const style=this.storyProgressionProfile.typography,original=this.sceneSpec,originalContext=this.ctx;
  const temporary={...original,labels:(original.labels||[]).map(label=>{
   if(label.production_text_event_id===status.id||label.role==='status'&&label.event_id===beat.story_event_id&&label.text===status.text)return {...label,size:style.event_size_px,opacity:style.event_opacity};
   if(['city','country'].includes(label.role)&&same(label.coordinates,beat.coordinates))return {...label,opacity:style.location_opacity};
   return label;
  })};
  const haloLabel=beat.pattern==='TEXT_REVEAL_HALO'?status.text:beat.pattern==='LOCATION_TEXT_HALO'?this.storyProgressionAuthoredScene.labels[beat.location_label_ref].text:null;
  const progress=(frame-beat.start_frame)/(beat.end_frame-beat.start_frame),strength=haloLabel?Math.sin(Math.PI*progress)**2:0;
  let measuredLabel=null,glyphCalls=0;const scale=this.w/1080,fullTexts=new Set(temporary.labels.map(label=>label.text));
  // Proxy native Canvas methods with their original receiver. The context and
  // its methods are never patched; save/restore scopes the brief neutral halo.
  const decorated=new Proxy(originalContext,{
   get(target,key){
    if(key==='measureText')return value=>{if(fullTexts.has(String(value)))measuredLabel=String(value);return target.measureText(value);};
    if(key==='fillText')return (...args)=>{
     if(haloLabel&&measuredLabel===haloLabel&&strength>0){
      target.save();try{target.shadowColor=`rgba(243,241,229,${.34*strength})`;target.shadowBlur=8*scale;target.shadowOffsetX=0;target.shadowOffsetY=0;glyphCalls++;return target.fillText(...args);}
      finally{target.restore();}
     }
     return target.fillText(...args);
    };
    const value=target[key];return typeof value==='function'?value.bind(target):value;
   },
   set(target,key,value){if(key==='font')measuredLabel=null;target[key]=value;return true;}
  });
  try{this.sceneSpec=temporary;this.ctx=decorated;super.overlay(t);}
  finally{this.sceneSpec=original;this.ctx=originalContext;}
  const eventBox=this.labels.find(label=>label.event_id===beat.story_event_id&&label.text===status.text);
  const locationSource=beat.location_label_ref===null?(this.storyProgressionAuthoredScene.labels||[]).find(label=>['city','country'].includes(label.role)&&same(label.coordinates,beat.coordinates)):this.storyProgressionAuthoredScene.labels[beat.location_label_ref];
  const locationBox=locationSource?this.labels.find(label=>label.text===locationSource.text):null;
  this.storyProgressionReceipts.push({id:beat.id,scene_id:original.scene_id,frame,timestamp:t,
   phase:beat.phase,story_event_id:beat.story_event_id,text_event_id:beat.text_event_id,
   primary_information:beat.primary_information,pattern:beat.pattern,primary:beat.primary,
   start_frame:beat.start_frame,end_frame:beat.end_frame,source_ref:{...beat.source_ref},
   camera_state:(this.storyProgressionAuthoredScene.second_event_camera?.timeline||[]).find(item=>frame>=item.start_frame&&frame<item.end_frame)?.state||'CAMERA_LOCK',
   camera_lock_ref:structuredClone(beat.camera_lock_ref),geometry_ref:null,semantic_segment_ref:beat.semantic_segment_ref,
   reference_evidence_ids:[...beat.reference_evidence_ids],halo:{active:glyphCalls>0,strength,glyph_calls:glyphCalls},
   text_hierarchy:{event_font_px:eventBox?.font??null,event_opacity:eventBox?.opacity??null,location_opacity:locationBox?.opacity??null,weight:400},
   visible:Boolean(eventBox&&eventBox.opacity>.1),pixel_bounds:eventBox?{x:eventBox.x,y:eventBox.y,width:eventBox.width,height:eventBox.height}:null});
 }
 audit(t){
  const value=super.audit(t);if(!this.storyProgressionReady)return value;
  const frame=frameAt(t,this.storyProgressionFPS),parentPrimary=(value.effectLayer?.events||[]).filter(event=>event.primary).length;
  const record={version:'v021',parent_version:'v020',profile_sha256:this.storyProgressionProfileHash,frame,
   phase:this.storyProgressionReceipts.length?this.storyProgressionReceipts[0].phase:'NONE',
   microbeats:this.storyProgressionReceipts.map(receipt=>structuredClone(receipt)),
   primary_effect_count:parentPrimary+this.storyProgressionReceipts.filter(beat=>beat.primary).length,
   boundary:structuredClone(this.storyProgressionAuthoredScene.story_progression.boundary),
   additional_textures:0,additional_texture_uploads:0,added_sfx:0,
   preserved:{camera:true,timing:true,material:true,regional_lod:true,text_content:true,audio:true}};
  value.storyProgression=record;if(value.effectLayer)value.effectLayer.storyProgression=structuredClone(record);
  return value;
 }
}
