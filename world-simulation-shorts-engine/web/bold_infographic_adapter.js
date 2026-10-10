/** Additive v023 region visual profile. The v022 camera, material, semantic
 * state, marker, measured text layout and OFF renderer remain their originals.
 * Region rasterization is Canvas2D in output screen space, not WebGL linewidth.
 */
import {SceneInfographicRenderer,SceneProductionInfographicRenderer,createInfographicRenderer,validateInfographicGeometry,prepareInfographicGeometry,projectInfographicGeometry} from './infographic_adapter.js';
import {digestBytes,trustedStaticURL} from './visual_quality_adapter.js';

export {prepareInfographicGeometry,projectInfographicGeometry};
export const BOLD_INFOGRAPHIC_VERSION='v023';
export const BOLD_INFOGRAPHIC_PROFILE='BOLD_INFOGRAPHIC_V023';
const PROFILE_URL='/static/infographic/v023/bold_profile.json';
const REGISTRY_URL='/static/infographic/v022/registry.json';
const fail=rule=>{throw Error(`BOLD_INFOGRAPHIC_${rule}`);};
const finite=(value,min,max)=>typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max;
const color=value=>typeof value==='string'&&/^#[a-f0-9]{6}$/i.test(value);
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const clamp=value=>Math.max(0,Math.min(1,value));
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));

export function validateBoldProfile(profile){
 if(profile?.version!==BOLD_INFOGRAPHIC_VERSION||profile.profile_id!==BOLD_INFOGRAPHIC_PROFILE||profile.parent_version!=='v022'||profile.role!=='bold_map_infographic')fail('PROFILE_INVALID');
 const geometry=profile.geometry,primary=geometry?.PRIMARY,secondary=geometry?.SECONDARY;
 if(!geometry||geometry.preserve_holes!==true||geometry.horizon_occlusion!==true||geometry.boundary_draw!==false||geometry.blend_mode!=='source-over'||geometry.screen_space_reference_width!==1080)fail('GEOMETRY_PROFILE_INVALID');
 for(const style of [primary,secondary])if(!style||!color(style.fill_color)||!color(style.core_color)||!color(style.edge_color)||!finite(style.fill_alpha,.01,.85)||!finite(style.core_width_px,.5,20)||!finite(style.edge_width_px,style.core_width_px,28)||!finite(style.edge_alpha,0,1))fail('STYLE_INVALID');
 if(primary.fill_alpha<=secondary.fill_alpha||primary.core_width_px<=secondary.core_width_px||primary.edge_alpha<=secondary.edge_alpha||geometry.NEUTRAL?.fill_alpha!==0||geometry.NEUTRAL?.core_width_px!==0)fail('HIERARCHY_INVALID');
 if(profile.limits?.primary_regions!==1||!Number.isInteger(profile.limits.context_max_regions)||profile.limits.context_max_regions<1||profile.limits.context_max_regions>12||profile.limits.added_routes!==0||profile.limits.added_entities!==0||profile.limits.added_sfx!==0||profile.marker_and_text!=='EXACT_V022')fail('SCOPE_INVALID');
 return profile;
}

/** Shared by actual production overlay and CPU-only captured-pixel QC. */
export function boldRegionStyle(profile,role){
 if(profile===null||profile===undefined)return null;
 validateBoldProfile(profile);
 if(!['PRIMARY','SECONDARY','NEUTRAL'].includes(role))fail('REGION_ROLE_INVALID');
 return role==='NEUTRAL'?null:{...profile.geometry[role],role,blend_mode:profile.geometry.blend_mode};
}

/** Draw only already-projected native polygon triangles and source edges.
 * A dark edge below the bright core provides contrast on both bright desert
 * and dark geography without changing exposure or generating a glow effect.
 * Configured widths are receipts; captured-pixel measurements are separate.
 */
export function drawBoldRegionLayer(ctx,projected,style,{drawFill=true,drawBoundary=true,width=1080,height=1920}={}){
 if(style===null||style===undefined)return {drawn:false,role:'OFF',fill_alpha:0,core_width_px_1080:0,edge_width_px_1080:0};
 if(!ctx||!projected||!Array.isArray(projected.polygons)||!Array.isArray(projected.segments)||!finite(width,1,16384)||!finite(height,1,16384))fail('DRAW_INPUT_INVALID');
 if(!['PRIMARY','SECONDARY'].includes(style.role)||!color(style.fill_color)||!color(style.core_color)||!color(style.edge_color)||!finite(style.fill_alpha,0,1)||!finite(style.core_width_px,.5,20)||!finite(style.edge_width_px,style.core_width_px,28)||!finite(style.edge_alpha,0,1))fail('DRAW_STYLE_INVALID');
 const scale=width/1080,polygons=projected.polygons,segments=projected.segments;
 const pathEdges=()=>{ctx.beginPath();for(const segment of segments){if(segment.length!==2)fail('SEGMENT_INVALID');ctx.moveTo(segment[0].x,segment[0].y);ctx.lineTo(segment[1].x,segment[1].y);}};
 ctx.save();try{
  ctx.globalCompositeOperation='source-over';ctx.lineJoin='round';ctx.lineCap='round';ctx.shadowBlur=0;ctx.shadowOffsetX=0;ctx.shadowOffsetY=0;
  if(drawFill&&polygons.length){
   ctx.globalAlpha=style.fill_alpha;ctx.fillStyle=style.fill_color;ctx.beginPath();
   for(const polygon of polygons){if(polygon.length<3)fail('POLYGON_INVALID');ctx.moveTo(polygon[0].x,polygon[0].y);for(const point of polygon.slice(1))ctx.lineTo(point.x,point.y);ctx.closePath();}
   ctx.fill();
  }
  if(drawBoundary&&segments.length){
   pathEdges();ctx.globalAlpha=style.edge_alpha;ctx.strokeStyle=style.edge_color;ctx.lineWidth=style.edge_width_px*scale;ctx.stroke();
   pathEdges();ctx.globalAlpha=1;ctx.strokeStyle=style.core_color;ctx.lineWidth=style.core_width_px*scale;ctx.stroke();
  }
 }finally{ctx.restore();}
 return {drawn:projected.visible===true&&(drawFill&&polygons.length>0||drawBoundary&&segments.length>0),role:style.role,
  fill_alpha:drawFill&&polygons.length?style.fill_alpha:0,core_width_px_1080:drawBoundary&&segments.length?style.core_width_px:0,
  edge_width_px_1080:drawBoundary&&segments.length?style.edge_width_px:0,core_width_internal_px:style.core_width_px*scale,
  edge_width_internal_px:style.edge_width_px*scale,edge_alpha:style.edge_alpha,fill_color:style.fill_color,core_color:style.core_color,
  edge_color:style.edge_color,polygon_count:polygons.length,segment_count:segments.length,terrain_uncovered_weight:drawFill?1-style.fill_alpha:1,
  blend_mode:'source-over',holes_preserved:true,boundary_source:'Verified native GIS source edges; not triangle borders',
  metric_scope:'Actual Canvas2D draw operations; widths/alphas are configuration receipts, not captured-pixel or NVIDIA quality PASS'};
}

export function validateBoldSelection(scene){
 const selected=scene.bold_infographic,parent=scene.infographic;
 if(!selected||selected.version!==BOLD_INFOGRAPHIC_VERSION||selected.profile_id!==BOLD_INFOGRAPHIC_PROFILE||parent?.version!=='v022')fail('EXPLICIT_PROFILE_REQUIRED');
 if(selected.profile_url!==PROFILE_URL||!sha(selected.profile_sha256)||selected.registry_sha256!==parent.registry_sha256||!sha(selected.parent_infographic_sha256)||!sha(selected.parent_camera_sha256)||!sha(selected.parent_quality_sha256))fail('SOURCE_INVALID');
 if(selected.total_frames!==scene.frame_count||selected.fps!==parent.fps||!Array.isArray(selected.regions)||!Array.isArray(selected.geometries)||!Array.isArray(selected.geometry_ids))fail('FRAME_OR_SELECTION_INVALID');
 const geometries=new Map();for(const record of selected.geometries){validateInfographicGeometry(record);if(!['Polygon','MultiPolygon'].includes(record.geometry_type)||geometries.has(record.id))fail('NATIVE_POLYGON_REQUIRED');geometries.set(record.id,record);}
 if(!same([...geometries.keys()].sort(),[...selected.geometry_ids].sort())||new Set(selected.geometry_ids).size!==selected.geometry_ids.length)fail('GEOMETRY_SELECTION_INVALID');
 const events=new Map(parent.events.map(event=>[event.id,event])),ids=new Set();
 for(const region of selected.regions){
  if(!region||typeof region.id!=='string'||!region.id||ids.has(region.id)||!['PRIMARY','SECONDARY'].includes(region.role)||!geometries.has(region.geometry_ref)||region.source_sha256!==geometries.get(region.geometry_ref).sha256||![region.start_frame,region.end_frame].every(Number.isInteger)||!(0<=region.start_frame&&region.start_frame<region.end_frame&&region.end_frame<=selected.total_frames))fail('REGION_INVALID');
  const event=events.get(region.source_event_id),primary=geometries.get(region.primary_geometry_ref),owner=selected.regions.find(value=>value.role==='PRIMARY'&&value.geometry_ref===region.primary_geometry_ref&&value.source_event_id===region.source_event_id&&value.start_frame===region.start_frame&&value.end_frame===region.end_frame);
  const authored=owner?.selection_method==='AUTHORED_EVENT_NATIVE_POLYGON'&&event?.target_geometry_refs.includes(region.primary_geometry_ref);
  const point=parent.geometries.find(record=>record.id===event?.location_point_ref);
  const sourcedPoint=owner?.selection_method==='VERIFIED_POINT_IN_NATIVE_COUNTRY'&&primary?.geometry_role==='country'&&point?.geometry_type==='Point'&&containsNativeCountryPoint(primary,point.coordinates);
  if(!event||region.event_id!==event.id||!primary||!owner||!(authored||sourcedPoint)||region.role==='PRIMARY'&&region.geometry_ref!==region.primary_geometry_ref||region.role==='SECONDARY'&&(geometries.get(region.geometry_ref)?.geometry_role!=='country'||!['SHARED_NATIVE_BOUNDARY','VERIFIED_GEOGRAPHIC_PROXIMITY'].includes(region.selection_method)))fail('STORY_TARGET_INVALID');
  ids.add(region.id);
 }
 for(let frame=0;frame<selected.total_frames;frame++)if(selected.regions.filter(region=>region.role==='PRIMARY'&&frame>=region.start_frame&&frame<region.end_frame).length>1)fail('PRIMARY_REGION_CONFLICT');
 return {selected,geometries,events};
}

/** Match the server's dateline-safe native ring membership, including holes.
 * The event point selects an existing sourced country backdrop; no point is
 * enlarged into invented event geometry and no authored state target changes.
 */
export function containsNativeCountryPoint(record,point){
 if(!record||!['Polygon','MultiPolygon'].includes(record.geometry_type)||!Array.isArray(point)||point.length!==2||!point.every(Number.isFinite))return false;
 const [x,y]=point,polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates;
 const ringContains=ring=>{
  const values=ring.map(([lon,lat])=>[x+((lon-x+180)%360+360)%360-180,lat]);let inside=false;
  for(let index=1;index<values.length;index++){
   const [ax,ay]=values[index-1],[bx,by]=values[index],cross=(x-ax)*(by-ay)-(y-ay)*(bx-ax);
   if(Math.abs(cross)<1e-10&&x>=Math.min(ax,bx)-1e-10&&x<=Math.max(ax,bx)+1e-10&&y>=Math.min(ay,by)-1e-10&&y<=Math.max(ay,by)+1e-10)return true;
   if((ay>y)!==(by>y)&&x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;
  }return inside;
 };
 return polygons.some(rings=>ringContains(rings[0])&&!rings.slice(1).some(ringContains));
}

async function verifiedJSON(url,expected,allowed){
 if(trustedStaticURL(url)!==allowed||!sha(expected))fail('RESOURCE_SOURCE_INVALID');
 const response=await fetch(allowed,{credentials:'same-origin',redirect:'error'});if(!response.ok)fail('RESOURCE_FETCH_FAILED');
 const bytes=await response.arrayBuffer();if(await digestBytes(bytes)!==expected)fail('RESOURCE_HASH_MISMATCH');
 try{return JSON.parse(new TextDecoder().decode(bytes));}catch{fail('RESOURCE_JSON_INVALID');}
}

function originalGeometryOrder(selected,frame){
 const targets=new Map();
 if(Array.isArray(selected.geometry_layers))for(const layer of selected.geometry_layers){if(frame>=layer.start_frame&&frame<layer.end_frame)targets.set(layer.geometry_ref,layer);}
 else for(const event of selected.events)if(frame>=event.start_frame&&frame<event.end_frame)for(const id of event.target_geometry_refs)targets.set(id,event);
 return [...targets.keys()];
}

/** Suppress only the old country draw operations, not its source receipts,
 * country obstacles, measured text layout or semantic state computation.
 * The frozen v022 overlay starts each geometry group with one outer save.
 * Native context methods stay bound to their real context. The proxy is local
 * to this overlay call and is always removed, including injected draw failure.
 */
export function withoutLegacyCountryDraw(context,geometryOrder,suppressed){
 let depth=0,outerSave=-1,blocked=false,groups=0;
 const proxy=new Proxy(context,{get(target,key){
  if(key==='save')return ()=>{if(depth===0){outerSave++;blocked=outerSave<geometryOrder.length&&suppressed.has(geometryOrder[outerSave]);if(outerSave<geometryOrder.length)groups++;}depth++;return target.save();};
  if(key==='restore')return ()=>{const result=target.restore();depth--;if(depth<=0){depth=0;blocked=false;}return result;};
  if(key==='fill'||key==='stroke')return (...args)=>blocked?undefined:target[key](...args);
  const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
 },set(target,key,value){return Reflect.set(target,key,value,target);}});
 return {context:proxy,verify(){if(depth!==0||groups!==geometryOrder.length)fail('INHERITED_OVERLAY_GROUP_MISMATCH');},groups:()=>groups};
}

function inheritedState(event,frame){
 const transition=event.transition_end_frame===event.start_frame?1:clamp((frame-event.start_frame)/(event.transition_end_frame-event.start_frame));
 return {state:transition>=1?event.state_after:`${event.state_before}→${event.state_after}`,transition};
}

function BoldOverlay(Parent){return class extends Parent{
 constructor(scene,plan){const child=validateBoldSelection(scene);super(scene,plan);this.boldContract=child;this.boldReady=false;this.boldInfographicReceipt=null;}
 async init(){
  await super.init();const selection=this.boldContract.selected;
  const [profile,registry]=await Promise.all([verifiedJSON(selection.profile_url,selection.profile_sha256,PROFILE_URL),verifiedJSON(REGISTRY_URL,selection.registry_sha256,REGISTRY_URL)]);
  this.boldProfile=validateBoldProfile(profile);if(registry.version!=='v022'||registry.crs!=='EPSG:4326'||!Array.isArray(registry.geometries))fail('REGISTRY_INVALID');
  const records=new Map(registry.geometries.map(record=>[record.id,record]));
  for(const record of selection.geometries)if(!same(record,records.get(record.id)))fail('REGISTRY_RECORD_MISMATCH');
  this.boldPrepared=new Map(selection.geometries.map(record=>[record.id,prepareInfographicGeometry(record)]));
  this.boldReady=true;this.frame(0);return this;
 }
 overlay(t){
  if(!this.boldReady)return super.overlay(t);
  const {selected,events}=this.boldContract,parent=this.infographicContract.selected,fps=Number(selected.fps.includes('/')?selected.fps.split('/').reduce((a,b)=>Number(a)/Number(b)):selected.fps),frame=Math.floor(t*fps+1e-7),ctx=this.ctx;
  const active=selected.regions.filter(region=>frame>=region.start_frame&&frame<region.end_frame).sort((a,b)=>Number(a.role==='PRIMARY')-Number(b.role==='PRIMARY')||a.id.localeCompare(b.id));
  const receipts=[],primaryByGeometry=new Map();
  for(const region of active){
   const prepared=this.boldPrepared.get(region.geometry_ref),projected=projectInfographicGeometry(prepared,this.camera,this.w,this.h),style=boldRegionStyle(this.boldProfile,region.role),draw=drawBoldRegionLayer(ctx,projected,style,{width:this.w,height:this.h});
   const receipt={...draw,id:region.id,geometry_id:region.geometry_ref,source_event_id:region.source_event_id,event_id:region.event_id,primary_geometry_ref:region.primary_geometry_ref,frame,start_frame:region.start_frame,end_frame:region.end_frame,visible:projected.visible,bounds:projected.bounds,source_sha256:prepared.record.sha256,source_id:prepared.record.source_id,source_feature_id:prepared.record.source_feature_id,precision:prepared.record.scale,selection_method:region.selection_method};
   receipts.push(receipt);if(region.role==='PRIMARY')primaryByGeometry.set(region.geometry_ref,receipt);
  }
  const ordered=originalGeometryOrder(parent,frame),suppressed=new Set(ordered.filter(id=>primaryByGeometry.has(id))),scope=withoutLegacyCountryDraw(ctx,ordered,suppressed);
  this.ctx=scope.context;try{super.overlay(t);scope.verify();}finally{this.ctx=ctx;}
  for(const receipt of this.infographicReceipt.geometry){const bold=primaryByGeometry.get(receipt.geometry_id);if(bold){const event=events.get(bold.source_event_id),state=inheritedState(event,frame);Object.assign(receipt,state,{visual_profile:BOLD_INFOGRAPHIC_PROFILE,visual_role:'PRIMARY',line_width_px_1080:bold.core_width_px_1080,fill_alpha:bold.fill_alpha,outer_edge_width_px_1080:bold.edge_width_px_1080,source_sha256:bold.source_sha256,drawn_by:'BOLD_NATIVE_COUNTRY_LAYER',legacy_draw_suppressed:true});}}
  this.boldInfographicReceipt={version:BOLD_INFOGRAPHIC_VERSION,profile_id:BOLD_INFOGRAPHIC_PROFILE,frame,timestamp:t,profile_sha256:selected.profile_sha256,registry_sha256:selected.registry_sha256,regions:receipts,primary_regions:receipts.filter(region=>region.role==='PRIMARY'&&region.visible).length,secondary_regions:receipts.filter(region=>region.role==='SECONDARY'&&region.visible).length,legacy_country_draw_groups_suppressed:suppressed.size,legacy_canals_marker_text:'UNCHANGED_SINGLE_DRAW',camera:'UNCHANGED',material:'UNCHANGED',added_texture_uploads:0,added_routes:0,added_entities:0,added_sfx:0,pixel_quality:'NVIDIA_GPU_NOT_RUN',metric_scope:'Native projected GIS and real Canvas2D draw commands; captured-pixel QC is separate and does not establish physical GPU quality'};
  this.infographicReceipt.bold_visual_profile=structuredClone(this.boldInfographicReceipt);
 }
 audit(t){const value=super.audit(t);if(this.boldReady)value.bold_infographic=structuredClone(this.boldInfographicReceipt);return value;}
};}

export const SceneBoldInfographicRenderer=BoldOverlay(SceneInfographicRenderer);
export const SceneProductionBoldInfographicRenderer=BoldOverlay(SceneProductionInfographicRenderer);
export function createBoldInfographicRenderer(scene,plan){
 if(scene.bold_infographic===undefined)return createInfographicRenderer(scene,plan);
 return scene.infographic?.parent_renderer_family==='production-earth-v1'?new SceneProductionBoldInfographicRenderer(scene,plan):new SceneBoldInfographicRenderer(scene,plan);
}
