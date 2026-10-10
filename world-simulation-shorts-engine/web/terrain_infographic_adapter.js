/** v024 colorized terrain overlay over unchanged v022 GIS/state and v023
 * native region selection. No camera, shader, source texture or story rewrite.
 * The same native Canvas2D helper runs in production and CPU pixel fixtures.
 */
import {SceneInfographicRenderer,SceneProductionInfographicRenderer,prepareInfographicGeometry,projectInfographicGeometry} from './infographic_adapter.js';
import {validateBoldSelection,withoutLegacyCountryDraw,createBoldInfographicRenderer} from './bold_infographic_adapter.js';
import {digestBytes,trustedStaticURL} from './visual_quality_adapter.js';
import * as THREE from 'three';

export {prepareInfographicGeometry,projectInfographicGeometry};
export const TERRAIN_INFOGRAPHIC_VERSION='v024';
export const TERRAIN_INFOGRAPHIC_PROFILE='VISUAL_TARGET_MAP_V024';
const PROFILE_URL='/static/infographic/v024/terrain_profile.json';
const REGISTRY_URL='/static/infographic/v022/registry.json';
const fail=rule=>{throw Error(`TERRAIN_INFOGRAPHIC_${rule}`);};
const finite=(value,low,high)=>typeof value==='number'&&Number.isFinite(value)&&value>=low&&value<=high;
const color=value=>typeof value==='string'&&/^#[a-f0-9]{6}$/i.test(value);
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));

/** The original adaptive spherical triangle subdivision can leave T-junctions:
 * a midpoint on one face is a spherical point but its neighbour keeps a chord.
 * v024 refines each indexed edge once for both adjacent faces. Source rings,
 * native holes, outline lines and the inherited clipping/projector are intact.
 */
export function prepareTerrainInfographicGeometry(record){
 const native=prepareInfographicGeometry(record);
 if(!native.triangles.length)return native;
 const vertices=[],triangles=[],ids=new Map(),edge=(a,b)=>a<b?`${a}:${b}`:`${b}:${a}`;
 const vertex=point=>{const key=point.toArray().map(value=>value.toFixed(14)).join(':');if(ids.has(key))return ids.get(key);const id=vertices.length;vertices.push(point);ids.set(key,id);return id;};
 const unwrap=(ring,anchor=null)=>{const values=[];for(const [longitude,latitude]of ring){let lon=longitude;if(values.length){while(lon-values.at(-1).x>180)lon-=360;while(lon-values.at(-1).x<-180)lon+=360;}values.push(new THREE.Vector2(lon,latitude));}if(anchor!==null){const mean=values.reduce((sum,p)=>sum+p.x,0)/values.length,shift=Math.round((anchor-mean)/360)*360;for(const p of values)p.x+=shift;}return values;};
 const normal=point=>{const lon=point.x*Math.PI/180,lat=point.y*Math.PI/180;return new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));};
 const polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates;
 for(const rings of polygons){const outer=unwrap(rings[0].slice(0,-1)),anchor=outer.reduce((sum,p)=>sum+p.x,0)/outer.length,holes=rings.slice(1).map(ring=>unwrap(ring.slice(0,-1),anchor)),points=[...outer,...holes.flat()],local=points.map(point=>vertex(normal(point))),indices=THREE.ShapeUtils.triangulateShape(outer,holes);if(!indices.length)fail('NATIVE_TRIANGULATION_FAILED');for(const triangle of indices)triangles.push(triangle.map(id=>local[id]));}
 let mesh=triangles,rounds=0;const maximum=6*Math.PI/180;
 for(;rounds<14;rounds++){
  const marked=new Map();for(const [a,b,c]of mesh)for(const [u,v]of [[a,b],[b,c],[c,a]])if(vertices[u].angleTo(vertices[v])>maximum+1e-12)marked.set(edge(u,v),[u,v]);
  if(!marked.size)break;
  const midpoint=new Map();for(const [key,[a,b]]of marked)midpoint.set(key,vertex(vertices[a].clone().add(vertices[b]).normalize()));
  const next=[];for(const [a,b,c]of mesh){const ab=midpoint.get(edge(a,b)),bc=midpoint.get(edge(b,c)),ca=midpoint.get(edge(c,a)),mask=Number(ab!==undefined)+2*Number(bc!==undefined)+4*Number(ca!==undefined);
   if(mask===0)next.push([a,b,c]);else if(mask===1)next.push([a,ab,c],[ab,b,c]);else if(mask===2)next.push([b,bc,a],[bc,c,a]);else if(mask===4)next.push([c,ca,b],[ca,a,b]);
   else if(mask===3)next.push([b,bc,ab],[a,ab,c],[ab,bc,c]);else if(mask===6)next.push([c,ca,bc],[b,bc,a],[bc,ca,a]);else if(mask===5)next.push([a,ab,ca],[c,ca,b],[ca,ab,b]);else next.push([a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]);
  }mesh=next;
 }
 if(rounds===14)fail('CONFORMING_TESSELLATION_LIMIT');
 return {...native,triangles:mesh.map(triangle=>triangle.map(id=>vertices[id])),fill_tessellation:{method:'SHARED_INDEXED_SPHERICAL_EDGE_REFINEMENT',maximum_degrees:6,rounds,source_triangle_count:triangles.length,triangle_count:mesh.length,vertex_count:vertices.length,source_geometry_sha256:record.sha256}};
}

export function validateTerrainProfile(profile){
 if(profile?.version!==TERRAIN_INFOGRAPHIC_VERSION||profile.profile_id!==TERRAIN_INFOGRAPHIC_PROFILE||profile.parent_version!=='v023'||profile.role!=='colorized_terrain_map_infographic')fail('PROFILE_INVALID');
 const geometry=profile.geometry,primary=geometry?.PRIMARY,secondary=geometry?.SECONDARY;
 if(!geometry||geometry.preserve_holes!==true||geometry.horizon_occlusion!==true||geometry.boundary_draw!==false||geometry.blend_mode!=='color'||geometry.screen_space_reference_width!==1080)fail('GEOMETRY_PROFILE_INVALID');
 for(const style of [primary,secondary]){if(!style||!color(style.fill_color)||!color(style.core_color)||!color(style.edge_color)||!color(style.glow_color)||!finite(style.luminance_scale,.80,1)||!finite(style.fill_alpha,.01,1)||!finite(style.core_width_px,.5,20)||!finite(style.edge_width_px,style.core_width_px,18)||!finite(style.edge_alpha,0,1)||!finite(style.glow_alpha,0,.25)||!finite(style.glow_width_px,0,12)||!finite(style.glow_blur_px,0,6))fail('STYLE_INVALID');const rgb=[1,3,5].map(index=>parseInt(style.fill_color.slice(index,index+2),16));if(Math.max(...rgb)-Math.min(...rgb)<24)fail('ROLE_COLOR_INVALID');}
 if(!finite(primary.fill_alpha,.72,.95)||!finite(secondary.fill_alpha,.40,.80)||!finite(primary.core_width_px,6,12)||!finite(secondary.core_width_px,2,5)||primary.fill_alpha<=secondary.fill_alpha||primary.core_width_px<=secondary.core_width_px||primary.edge_alpha<=secondary.edge_alpha||geometry.NEUTRAL?.fill_alpha!==0||geometry.NEUTRAL?.core_width_px!==0||geometry.NEUTRAL?.luminance_scale!==1||geometry.NEUTRAL?.glow_alpha!==0)fail('HIERARCHY_INVALID');
 if(secondary.glow_alpha!==0||secondary.glow_width_px!==0||secondary.glow_blur_px!==0||primary.glow_alpha>0&&primary.glow_width_px===0)fail('BOUNDED_PRIMARY_GLOW_REQUIRED');
 const contrast=profile.contrast,keys=['scope','text_outline_px','text_outline_color','text_outline_alpha','text_shadow_color','text_shadow_alpha','text_shadow_px','marker_edge_px','marker_edge_color','marker_edge_alpha'];
 if(!contrast||contrast.scope!=='DRAW_ONLY_V022_TIMING_LAYOUT'||Object.keys(contrast).some(key=>!keys.includes(key))||Object.keys(contrast).length!==keys.length||!finite(contrast.text_outline_px,2.5,4)||!color(contrast.text_outline_color)||contrast.text_outline_alpha!==1||!color(contrast.text_shadow_color)||!finite(contrast.text_shadow_alpha,.72,1)||contrast.text_shadow_px!==3||!finite(contrast.marker_edge_px,3,5.5)||!color(contrast.marker_edge_color)||contrast.marker_edge_alpha!==1)fail('CONTRAST_PROFILE_INVALID');
 if(profile.limits?.primary_regions!==1||profile.limits.context_max_regions!==6||profile.limits.added_routes!==0||profile.limits.added_entities!==0||profile.limits.added_sfx!==0||profile.marker_and_text!=='TIMING_LAYOUT_V022_CONTRAST_V024'||profile.glow_policy!=='STATIC_PRIMARY_EDGE_ONLY'||!same(profile.semantic_roles,{PRIMARY:'EVENT_GEOGRAPHY',SECONDARY:'VERIFIED_GEOGRAPHIC_CONTEXT',NEUTRAL:'UNSELECTED_BASE_GEOGRAPHY'}))fail('SCOPE_INVALID');
 return profile;
}

export function terrainRegionStyle(profile,role){
 if(profile===null||profile===undefined)return null;
 validateTerrainProfile(profile);
 if(!['PRIMARY','SECONDARY','NEUTRAL'].includes(role))fail('REGION_ROLE_INVALID');
 return role==='NEUTRAL'?null:{...profile.geometry[role],role,blend_mode:'color'};
}

/** A conforming mesh still has many very narrow faces. Canvas path AA can
 * retain faint internal slivers even when shared face edges are exact. Cancel
 * those paired directed edges before filling, leaving only the actual clipped
 * native outer/hole paths. This is a mesh union, never country expansion.
 * Keys identify equivalent endpoints within 1e-7 pixel; drawn points retain
 * their actual projection coordinates, not snapped grid coordinates.
 */
export function mergeTerrainFillPaths(polygons){
 if(!Array.isArray(polygons))fail('FILL_PATH_INPUT_INVALID');
 const points=new Map(),edges=new Map(),halfedges=[],parents=polygons.map((_,index)=>index);let mergedDelta=0,edgeOccurrences=0,zeroAreaFaces=0;const zeroAreaExamples=[];
 const find=index=>{while(parents[index]!==index){parents[index]=parents[parents[index]];index=parents[index];}return index;},join=(a,b)=>{a=find(a);b=find(b);if(a!==b)parents[b]=a;};
 const pointKey=point=>{if(!point||!Number.isFinite(point.x)||!Number.isFinite(point.y))fail('FILL_PATH_POINT_INVALID');const key=`${point.x.toFixed(7)}:${point.y.toFixed(7)}`,prior=points.get(key);if(prior)mergedDelta=Math.max(mergedDelta,Math.hypot(prior.x-point.x,prior.y-point.y));else points.set(key,point);return key;};
 for(const [face,polygon]of polygons.entries()){
  if(!Array.isArray(polygon)||polygon.length<3)fail('FILL_PATH_POLYGON_INVALID');let keys=polygon.map(pointKey);
  const twiceArea=polygon.reduce((sum,p,i)=>sum+p.x*polygon[(i+1)%polygon.length].y-p.y*polygon[(i+1)%polygon.length].x,0);
  if(twiceArea===0){zeroAreaFaces++;if(zeroAreaExamples.length<3)zeroAreaExamples.push(polygon.map(point=>({x:point.x,y:point.y})));continue;}
  keys=keys.filter((key,index)=>index===0||key!==keys[index-1]);if(keys[0]===keys.at(-1))keys.pop();if(keys.length<3)fail('FILL_PATH_QUANTIZATION_DEGENERATE');
  const first=halfedges.length;for(let i=0;i<keys.length;i++){const a=keys[i],b=keys[(i+1)%keys.length],id=halfedges.length,key=a<b?`${a}|${b}`:`${b}|${a}`;halfedges.push({a,b,face,next:first+(i+1)%keys.length,twin:null});const group=edges.get(key)||[];group.push(id);edges.set(key,group);edgeOccurrences++;}
 }
 const boundary=[];let cancelled=0;
 for(const group of edges.values()){
  if(group.length===1){boundary.push(group[0]);continue;}if(group.length!==2)fail('FILL_PATH_OVERLAP_INVALID');
  const[a,b]=group,u=halfedges[a],v=halfedges[b];if(u.a!==v.b||u.b!==v.a||u.face===v.face)fail('FILL_PATH_OVERLAP_INVALID');u.twin=b;v.twin=a;join(u.face,v.face);cancelled+=2;
 }
 // Follow ordered native FACE successors, crossing only actual reverse-paired
 // edges. A geometric tangent/pole vertex may have several valid boundary
 // occurrences; its original face fan determines the next edge without any
 // angle-based choice or invented connection between MultiPolygon parts.
 const successors=new Map(),predecessors=new Map();let maximumFanSteps=0;
 for(const edge of boundary){let next=halfedges[edge].next,steps=0;const seen=new Set();while(halfedges[next].twin!==null){if(seen.has(next)||steps++>halfedges.length)fail('FILL_PATH_UNRESOLVED');seen.add(next);next=halfedges[halfedges[next].twin].next;}maximumFanSteps=Math.max(maximumFanSteps,steps);if(halfedges[next].a!==halfedges[edge].b)fail('FILL_PATH_UNCLOSED');if(predecessors.has(next))fail('FILL_PATH_BRANCH_INVALID');successors.set(edge,next);predecessors.set(next,edge);}
 for(const edge of boundary)if(!successors.has(edge)||!predecessors.has(edge))fail('FILL_PATH_UNCLOSED');
 const paths=[],visited=new Set();for(const first of boundary){if(visited.has(first))continue;const path=[];let edge=first;do{if(visited.has(edge)||!successors.has(edge)||path.length>boundary.length)fail('FILL_PATH_UNCLOSED');visited.add(edge);path.push(points.get(halfedges[edge].a));edge=successors.get(edge);}while(edge!==first);if(path.length<3)fail('FILL_PATH_DEGENERATE');paths.push(path);}
 const components=new Set(boundary.map(edge=>find(halfedges[edge].face)));
 // Nonzero projected faces cannot form a boundaryless closed 2D component;
 // reverse duplicate faces would otherwise cancel into a false empty success.
 for(const edge of halfedges)if(!components.has(find(edge.face)))fail('FILL_PATH_UNRESOLVED');
 return {paths,receipt:{method:'PAIRED_PROJECTED_MESH_EDGE_UNION',component_rule:'SHARED_FACE_EDGE_NOT_VERTEX',boundary_rule:'ORDERED_NATIVE_HALFEDGE_FACE_SUCCESSOR',boundary_successor_bijective:true,coordinate_vertex_touches_preserved:true,connected_fill_components:components.size,winding:'NONZERO_NATIVE_ORIENTATION',fill_path_count:paths.length,fill_path_vertex_count:paths.reduce((sum,path)=>sum+path.length,0),internal_edge_occurrences_cancelled:cancelled,input_edge_occurrences:edgeOccurrences,maximum_native_fan_steps:maximumFanSteps,zero_area_faces_omitted:zeroAreaFaces,zero_area_projected_coordinates:zeroAreaExamples,zero_area_rule:'Exact computed projected area equals zero; no epsilon area threshold',endpoint_key_precision_px:1e-7,maximum_endpoint_identification_delta_px:mergedDelta,drawn_coordinates:'Original projected coordinates; quantization keys only',closed:true,branched:false}};
}

export function traceTerrainFillPath(ctx,projected){
 if(!ctx||!projected||!Array.isArray(projected.polygons))fail('FILL_PATH_TRACE_INPUT_INVALID');const union=mergeTerrainFillPaths(projected.polygons);ctx.beginPath();for(const path of union.paths){ctx.moveTo(path[0].x,path[0].y);for(const point of path.slice(1))ctx.lineTo(point.x,point.y);ctx.closePath();}return union.receipt;
}

/** Geometry-local neutral multiply controls regional albedo brightness within
 * the bounded profile factor. Native color then transfers hue/chroma while
 * retaining that scaled W3C luminance and existing texture/light variations.
 * No global surface/shader/exposure changes. Captured detail is separate QC.
 */
export function drawTerrainRegionLayer(ctx,projected,style,{drawFill=true,drawBoundary=true,drawGlow=true,width=1080,height=1920}={}){
 if(style===null||style===undefined)return {drawn:false,role:'OFF',fill_alpha:0,luminance_scale:1,core_width_px_1080:0,edge_width_px_1080:0,glow_alpha:0};
 if(!ctx||!projected||!Array.isArray(projected.polygons)||!Array.isArray(projected.segments)||!finite(width,1,16384)||!finite(height,1,16384))fail('DRAW_INPUT_INVALID');
 if(!['PRIMARY','SECONDARY'].includes(style.role)||style.blend_mode!=='color'||!color(style.fill_color)||!color(style.core_color)||!color(style.edge_color)||!color(style.glow_color)||!finite(style.luminance_scale,.80,1)||!finite(style.fill_alpha,0,1)||!finite(style.core_width_px,.5,20)||!finite(style.edge_width_px,style.core_width_px,28)||!finite(style.edge_alpha,0,1)||!finite(style.glow_alpha,0,.25)||!finite(style.glow_width_px,0,20)||!finite(style.glow_blur_px,0,6)||style.role==='SECONDARY'&&(style.glow_alpha!==0||style.glow_width_px!==0||style.glow_blur_px!==0))fail('DRAW_STYLE_INVALID');
 const scale=width/1080,polygons=projected.polygons,segments=projected.segments;
 const pathEdges=()=>{ctx.beginPath();for(const segment of segments){if(segment.length!==2)fail('SEGMENT_INVALID');ctx.moveTo(segment[0].x,segment[0].y);ctx.lineTo(segment[1].x,segment[1].y);}};
 let glowDrawn=false,multiplyColor=null,multiplyGrayFactor=1,fillPathReceipt=null;
 ctx.save();try{
  ctx.lineJoin='round';ctx.lineCap='round';ctx.shadowBlur=0;ctx.shadowOffsetX=0;ctx.shadowOffsetY=0;ctx.shadowColor='rgba(0,0,0,0)';
  if(drawFill&&polygons.length){
   fillPathReceipt=traceTerrainFillPath(ctx,projected);
   // This is the same verified polygon path, not a screen-wide exposure pass.
   // Native Canvas CSS quantization is recorded and pixel-measured separately.
   if(style.luminance_scale<1){
    ctx.globalCompositeOperation='multiply';if(ctx.globalCompositeOperation!=='multiply')fail('NATIVE_MULTIPLY_COMPOSITE_UNSUPPORTED');
    const channel=style.luminance_scale*255;ctx.globalAlpha=1;ctx.fillStyle=`rgb(${channel},${channel},${channel})`;multiplyColor=ctx.fillStyle;
    const hex=typeof multiplyColor==='string'?multiplyColor.match(/^#([a-f0-9]{6})$/i):null,channels=hex?hex[1].match(/../g).map(value=>parseInt(value,16)):null,rgb=typeof multiplyColor==='string'?multiplyColor.match(/^rgb\(\s*([\d.]+)/):null;
    multiplyGrayFactor=channels&&channels.every(value=>value===channels[0])?channels[0]/255:rgb?Number(rgb[1])/255:style.luminance_scale;
    ctx.fill();
   }
   ctx.globalCompositeOperation='color';if(ctx.globalCompositeOperation!=='color')fail('NATIVE_COLOR_COMPOSITE_UNSUPPORTED');
   ctx.globalAlpha=style.fill_alpha;ctx.fillStyle=style.fill_color;ctx.fill();
  }
  ctx.globalCompositeOperation='source-over';
  if(drawBoundary&&segments.length){
   if(drawGlow&&style.role==='PRIMARY'&&style.glow_alpha>0){
    pathEdges();ctx.globalAlpha=style.glow_alpha;ctx.strokeStyle=style.glow_color;ctx.lineWidth=style.glow_width_px*scale;ctx.shadowColor=style.glow_color;ctx.shadowBlur=style.glow_blur_px*scale;ctx.stroke();glowDrawn=true;
    ctx.shadowBlur=0;ctx.shadowColor='rgba(0,0,0,0)';
   }
   pathEdges();ctx.globalAlpha=style.edge_alpha;ctx.strokeStyle=style.edge_color;ctx.lineWidth=style.edge_width_px*scale;ctx.stroke();
   pathEdges();ctx.globalAlpha=1;ctx.strokeStyle=style.core_color;ctx.lineWidth=style.core_width_px*scale;ctx.stroke();
  }
 }finally{ctx.restore();}
 return {drawn:projected.visible===true&&(drawFill&&polygons.length>0||drawBoundary&&segments.length>0),role:style.role,
  fill_alpha:drawFill&&polygons.length?style.fill_alpha:0,fill_color:style.fill_color,fill_mode:'NATIVE_COLORIZED_TERRAIN',blend_mode:'color',
  luminance_scale:drawFill&&polygons.length?style.luminance_scale:1,luminance_operation:drawFill&&polygons.length&&style.luminance_scale<1?'NATIVE_POLYGON_NEUTRAL_MULTIPLY':'NONE',multiply_color:multiplyColor,multiply_gray_factor:multiplyGrayFactor,
  core_width_px_1080:drawBoundary&&segments.length?style.core_width_px:0,edge_width_px_1080:drawBoundary&&segments.length?style.edge_width_px:0,
  core_width_internal_px:style.core_width_px*scale,edge_width_internal_px:style.edge_width_px*scale,core_color:style.core_color,edge_color:style.edge_color,edge_alpha:style.edge_alpha,
  glow_drawn:glowDrawn,glow_alpha:glowDrawn?style.glow_alpha:0,glow_width_px_1080:glowDrawn?style.glow_width_px:0,glow_blur_px_1080:glowDrawn?style.glow_blur_px:0,
  polygon_count:polygons.length,segment_count:segments.length,fill_path:fillPathReceipt,holes_preserved:true,boundary_source:'Verified native GIS source edges; not triangle borders',
  luminance_model:'Bounded local albedo factor then Native Canvas W3C non-separable color; Rec709 and captured detail measured separately',
  metric_scope:'Actual Canvas2D operations; values are draw receipts, not captured-pixel or NVIDIA quality PASS'};
}

export function validateTerrainSelection(scene){
 const inherited=validateBoldSelection(scene),selected=scene.terrain_infographic,parent=inherited.selected;
 if(!selected||selected.version!==TERRAIN_INFOGRAPHIC_VERSION||selected.profile_id!==TERRAIN_INFOGRAPHIC_PROFILE)fail('EXPLICIT_PROFILE_REQUIRED');
 if(selected.profile_url!==PROFILE_URL||!sha(selected.profile_sha256)||selected.registry_sha256!==parent.registry_sha256||!sha(selected.parent_bold_sha256)||selected.parent_infographic_sha256!==parent.parent_infographic_sha256||selected.parent_camera_sha256!==parent.parent_camera_sha256||selected.parent_quality_sha256!==parent.parent_quality_sha256)fail('SOURCE_INVALID');
 if(selected.total_frames!==scene.frame_count||selected.total_frames!==parent.total_frames||selected.fps!==parent.fps||!selected.source_hashes||Object.values(selected.source_hashes).some(value=>!sha(value)))fail('FRAME_OR_SELECTION_INVALID');
 return {...inherited,terrain:selected};
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

/** Draw-only native text/ring contrast. No new labels, font, layout or marker
 * animation. The ring edge is capped to the original measured marker box;
 * small intro rings receive no extra stroke. Native fade/state core stays last.
 */
export function withTerrainContrast(context,profile,width){
 validateTerrainProfile(profile);const c=profile.contrast,scale=width/1080,receipt={text_glyph_strokes:0,text_outline_px_1080:c.text_outline_px,text_shadow_px_1080:c.text_shadow_px,text_shadow_alpha:c.text_shadow_alpha,marker_edges:[],scope:c.scope};let arc=null,textStroke=false,markerFill=false;
 const rgba=(hex,alpha)=>`rgba(${[1,3,5].map(start=>parseInt(hex.slice(start,start+2),16)).join(',')},${alpha})`;
 const proxy=new Proxy(context,{get(target,key){
  if(key==='beginPath')return (...args)=>{arc=null;return target.beginPath(...args);};
  if(key==='arc')return (...args)=>{arc={x:args[0],y:args[1],radius:args[2]};return target.arc(...args);};
  if(key==='stroke')return (...args)=>{
   if(arc&&Math.abs(target.lineWidth-3*scale)<1e-7&&markerFill){
    const requested=c.marker_edge_px*scale,actual=Math.min(requested,arc.radius*.4),base=target.lineWidth;
    if(actual>base+1e-7){const size=arc.radius/.30,box={x:arc.x-size*.36,y:arc.y-size*.28,width:size*.72,height:size},clip=new Path2D();clip.rect(box.x,box.y,box.width,box.height);
     target.save();try{target.clip(clip);target.lineWidth=actual;target.strokeStyle=rgba(c.marker_edge_color,c.marker_edge_alpha);target.stroke(...args);}finally{target.restore();}
     receipt.marker_edges.push({...arc,width_px_1080:actual/scale,requested_width_px_1080:c.marker_edge_px,core_width_px_1080:3,clip_box:box,inside_original_box:true});
    }
   }return target.stroke(...args);
  };
  if(key==='strokeText')return (...args)=>{receipt.text_glyph_strokes++;return target.strokeText(...args);};
  const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
 },set(target,key,value){
  if(key==='fillStyle')markerFill=value==='rgba(6,22,31,.50)';
  if(key==='strokeStyle'){textStroke=value==='rgba(6,22,31,.88)';if(textStroke)value=rgba(c.text_outline_color,c.text_outline_alpha);}
  else if(key==='lineWidth'&&Math.abs(value-2.25*scale)<1e-7&&textStroke)value=c.text_outline_px*scale;
  else if(key==='shadowColor'&&value==='rgba(6,22,31,.72)')value=rgba(c.text_shadow_color,c.text_shadow_alpha);
  return Reflect.set(target,key,value,target);
 }});
 return {context:proxy,receipt};
}

function TerrainOverlay(Parent){return class extends Parent{
 constructor(scene,plan){const child=validateTerrainSelection(scene);super(scene,plan);this.terrainContract=child;this.terrainReady=false;this.terrainInfographicReceipt=null;}
 async init(){
  await super.init();const selected=this.terrainContract.terrain,inherited=this.terrainContract.selected;
  const [profile,registry]=await Promise.all([verifiedJSON(selected.profile_url,selected.profile_sha256,PROFILE_URL),verifiedJSON(REGISTRY_URL,selected.registry_sha256,REGISTRY_URL)]);
  this.terrainProfile=validateTerrainProfile(profile);if(registry.version!=='v022'||registry.crs!=='EPSG:4326'||!Array.isArray(registry.geometries))fail('REGISTRY_INVALID');
  const records=new Map(registry.geometries.map(record=>[record.id,record]));
  for(const record of inherited.geometries)if(!same(record,records.get(record.id)))fail('REGISTRY_RECORD_MISMATCH');
  this.terrainPrepared=new Map(inherited.geometries.map(record=>[record.id,prepareTerrainInfographicGeometry(record)]));
  this.terrainReady=true;this.frame(0);return this;
 }
 overlay(t){
  if(!this.terrainReady)return super.overlay(t);
  const {selected,terrain}=this.terrainContract,parent=this.infographicContract.selected,fps=Number(selected.fps.includes('/')?selected.fps.split('/').reduce((a,b)=>Number(a)/Number(b)):selected.fps),frame=Math.floor(t*fps+1e-7),ctx=this.ctx;
  const active=selected.regions.filter(region=>frame>=region.start_frame&&frame<region.end_frame).sort((a,b)=>Number(a.role==='PRIMARY')-Number(b.role==='PRIMARY')||a.id.localeCompare(b.id));
  const receipts=[],drawnByGeometry=new Map();
  for(const region of active){
   const prepared=this.terrainPrepared.get(region.geometry_ref),projected=projectInfographicGeometry(prepared,this.camera,this.w,this.h),style=terrainRegionStyle(this.terrainProfile,region.role),draw=drawTerrainRegionLayer(ctx,projected,style,{width:this.w,height:this.h});
   const receipt={...draw,id:region.id,geometry_id:region.geometry_ref,source_event_id:region.source_event_id,event_id:region.event_id,primary_geometry_ref:region.primary_geometry_ref,frame,start_frame:region.start_frame,end_frame:region.end_frame,visible:projected.visible,bounds:projected.bounds,source_sha256:prepared.record.sha256,source_id:prepared.record.source_id,source_feature_id:prepared.record.source_feature_id,precision:prepared.record.scale,selection_method:region.selection_method,fill_tessellation:prepared.fill_tessellation||null};
   receipts.push(receipt);drawnByGeometry.set(region.geometry_ref,receipt);
  }
  // An authored multi-country event can also target a context country. Its
  // old solid fill must not redraw after our verified SECONDARY color layer.
  // Keep the original state/obstacle/layout computation for every geometry.
  const ordered=originalGeometryOrder(parent,frame),suppressed=new Set(ordered.filter(id=>drawnByGeometry.has(id))),scope=withoutLegacyCountryDraw(ctx,ordered,suppressed);
  const contrast=withTerrainContrast(scope.context,this.terrainProfile,this.w);
  this.ctx=contrast.context;try{super.overlay(t);scope.verify();}finally{this.ctx=ctx;}
  for(const receipt of this.infographicReceipt.geometry){const drawn=drawnByGeometry.get(receipt.geometry_id);if(drawn)Object.assign(receipt,{visual_profile:TERRAIN_INFOGRAPHIC_PROFILE,visual_role:drawn.role,line_width_px_1080:drawn.core_width_px_1080,fill_alpha:drawn.fill_alpha,fill_mode:drawn.fill_mode,blend_mode:drawn.blend_mode,luminance_scale:drawn.luminance_scale,luminance_operation:drawn.luminance_operation,outer_edge_width_px_1080:drawn.edge_width_px_1080,glow_alpha:drawn.glow_alpha,source_sha256:drawn.source_sha256,drawn_by:'COLORIZED_NATIVE_TERRAIN_LAYER',legacy_draw_suppressed:true});}
  this.terrainInfographicReceipt={version:TERRAIN_INFOGRAPHIC_VERSION,profile_id:TERRAIN_INFOGRAPHIC_PROFILE,frame,timestamp:t,profile_sha256:terrain.profile_sha256,registry_sha256:terrain.registry_sha256,regions:receipts,primary_regions:receipts.filter(region=>region.role==='PRIMARY'&&region.visible).length,secondary_regions:receipts.filter(region=>region.role==='SECONDARY'&&region.visible).length,legacy_country_draw_groups_suppressed:suppressed.size,legacy_canals_marker_text:'ORIGINAL_TIMING_LAYOUT_SINGLE_DRAW_CONTRAST_V024',contrast:contrast.receipt,camera:'UNCHANGED',material:'UNCHANGED',added_texture_uploads:0,added_routes:0,added_entities:0,added_sfx:0,pixel_quality:'NOT_ASSESSED_BY_OVERLAY_AUDIT',metric_scope:'Native Canvas colorized GIS overlay; actual source pixel QC and NVIDIA/human acceptance are separate evidence'};
  this.infographicReceipt.terrain_visual_profile=structuredClone(this.terrainInfographicReceipt);
 }
 audit(t){const value=super.audit(t);if(this.terrainReady)value.terrain_infographic=structuredClone(this.terrainInfographicReceipt);return value;}
};}

export const SceneTerrainInfographicRenderer=TerrainOverlay(SceneInfographicRenderer);
export const SceneProductionTerrainInfographicRenderer=TerrainOverlay(SceneProductionInfographicRenderer);
export function createTerrainInfographicRenderer(scene,plan){
 if(scene.terrain_infographic===undefined)return createBoldInfographicRenderer(scene,plan);
 return scene.infographic?.parent_renderer_family==='production-earth-v1'?new SceneProductionTerrainInfographicRenderer(scene,plan):new SceneTerrainInfographicRenderer(scene,plan);
}
