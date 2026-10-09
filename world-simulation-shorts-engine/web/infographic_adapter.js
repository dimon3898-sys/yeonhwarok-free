/** Versioned, source-bound map infographic overlay. No camera/map/audio rewrite.
 * The OFF factory is the unchanged v021 renderer. ON uses one shared text
 * layout, existing pop/reveal functions and the inherited spherical projection.
 */
import * as THREE from 'three';
import {SceneStoryProgressionRenderer,createStoryProgressionRenderer} from './story_progression_adapter.js';
import {SceneProductionEarthRenderer} from './production_visual_adapter.js';
import {characterRevealState,markerPopState} from './reference_effects_adapter.js';
import {digestBytes,trustedStaticURL,validateQualityProfile,validateDetailManifest,qualityWeight,configureQualityTexture,SceneVisualQualityRenderer} from './visual_quality_adapter.js';
import {validateEventQualityProfile,SceneEventQualityRenderer} from './event_quality_adapter.js';

export const INFOGRAPHIC_VERSION='v022';
const fail=rule=>{throw Error(`INFOGRAPHIC_${rule}`);};
const clamp=(value,low=0,high=1)=>Math.max(low,Math.min(high,value));
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const fpsValue=value=>{const parts=String(value).split('/').map(Number);return parts.length===1?parts[0]:parts.length===2?parts[0]/parts[1]:NaN;};
const frameAt=(seconds,fps)=>Math.floor(seconds*fps+1e-7);
const coordinate=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&Math.abs(value[0])<=180&&Math.abs(value[1])<=90;
const normal=point=>{const lon=point[0]*Math.PI/180,lat=point[1]*Math.PI/180;return new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));};
const overlap=(a,b,pad=0)=>a.x<b.x+b.width+pad&&a.x+a.width>b.x-pad&&a.y<b.y+b.height+pad&&a.y+a.height>b.y-pad;

function unwrap(ring,anchor=null){
 const result=[];for(const point of ring){let lon=point[0];if(result.length){while(lon-result.at(-1).x>180)lon-=360;while(lon-result.at(-1).x<-180)lon+=360;}result.push(new THREE.Vector2(lon,point[1]));}
 if(anchor!==null){const mean=result.reduce((sum,point)=>sum+point.x,0)/result.length,shift=Math.round((anchor-mean)/360)*360;for(const point of result)point.x+=shift;}
 return result;
}

export function validateInfographicGeometry(record){
 if(!record||typeof record.id!=='string'||!record.id||record.crs!=='EPSG:4326'||!['Point','LineString','MultiLineString','Polygon','MultiPolygon'].includes(record.geometry_type)||!sha(record.sha256)||!sha(record.source_file_sha256)||!sha(record.source_feature_sha256)||typeof record.source_id!=='string'||typeof record.source_feature_id!=='string'||typeof record.source_version!=='string'||!record.license?.spdx||!record.scale||!record.provenance)fail('GEOMETRY_SOURCE_INVALID');
 const line=points=>{if(!Array.isArray(points)||points.length<2||!points.every(coordinate))fail('GEOMETRY_COORDINATE_INVALID');};
 const ring=points=>{line(points);if(points.length<4||!same(points[0],points.at(-1)))fail('POLYGON_RING_INVALID');const flat=unwrap(points);let area=0;for(let i=1;i<flat.length;i++)area+=flat[i-1].x*flat[i].y-flat[i].x*flat[i-1].y;if(Math.abs(area)<1e-10)fail('POLYGON_AREA_INVALID');};
 const polygon=rings=>{if(!Array.isArray(rings)||!rings.length)fail('POLYGON_RING_INVALID');for(const points of rings)ring(points);};
 if(record.geometry_type==='Point'){if(!coordinate(record.coordinates))fail('GEOMETRY_COORDINATE_INVALID');}
 else if(record.geometry_type==='LineString')line(record.coordinates);
 else if(record.geometry_type==='MultiLineString'){if(!Array.isArray(record.coordinates)||!record.coordinates.length)fail('GEOMETRY_COORDINATE_INVALID');for(const points of record.coordinates)line(points);}
 else if(record.geometry_type==='Polygon')polygon(record.coordinates);
 else{if(!Array.isArray(record.coordinates)||!record.coordinates.length)fail('POLYGON_RING_INVALID');for(const rings of record.coordinates)polygon(rings);}
 return record;
}

function denseLine(points,maxDegrees=.75){
 const result=[normal(points[0])];
 for(let index=1;index<points.length;index++){
  const a=normal(points[index-1]),b=normal(points[index]),angle=a.angleTo(b),parts=Math.max(1,Math.ceil(angle/(maxDegrees*Math.PI/180)));
  if(angle>Math.PI-1e-6)fail('AMBIGUOUS_ANTIPODAL_LINE');
  for(let step=1;step<=parts;step++){const t=step/parts;result.push(angle<1e-9?a.clone():a.clone().multiplyScalar(Math.sin((1-t)*angle)/Math.sin(angle)).addScaledVector(b,Math.sin(t*angle)/Math.sin(angle)).normalize());}
 }
 return result;
}

function subdivideTriangle(a,b,c,out,depth=0){
 const maximum=Math.max(a.angleTo(b),b.angleTo(c),c.angleTo(a));
 if(maximum<=6*Math.PI/180||depth>=7){out.push([a,b,c]);return;}
 const ab=a.clone().add(b).normalize(),bc=b.clone().add(c).normalize(),ca=c.clone().add(a).normalize();
 subdivideTriangle(a,ab,ca,out,depth+1);subdivideTriangle(ab,b,bc,out,depth+1);subdivideTriangle(ca,bc,c,out,depth+1);subdivideTriangle(ab,bc,ca,out,depth+1);
}

/** Triangulate actual rings and holes once. No inferred radius or point area. */
export function prepareInfographicGeometry(record){
 validateInfographicGeometry(record);const lines=[],triangles=[];
 if(record.geometry_type==='Point')return {record,lines,triangles,point:normal(record.coordinates)};
 const polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.geometry_type==='MultiPolygon'?record.coordinates:[];
 if(polygons.length)for(const rings of polygons){
  const outer=unwrap(rings[0].slice(0,-1)),anchor=outer.reduce((sum,point)=>sum+point.x,0)/outer.length;
  const holes=rings.slice(1).map(ring=>unwrap(ring.slice(0,-1),anchor)),vertices=[...outer,...holes.flat()];
  const indices=THREE.ShapeUtils.triangulateShape(outer,holes);
  if(!indices.length)fail('POLYGON_TRIANGULATION_FAILED');
  for(const indicesOfTriangle of indices){const vectors=indicesOfTriangle.map(index=>normal([((vertices[index].x+180)%360+360)%360-180,vertices[index].y]));subdivideTriangle(...vectors,triangles);}
  for(const ring of rings)lines.push(denseLine(ring));
 }else{
  const authored=record.geometry_type==='LineString'?[record.coordinates]:record.coordinates;
  for(const line of authored)lines.push(denseLine(line));
 }
 return {record,lines,triangles,point:null};
}

function clipPolygon(points,distance,lerp){
 const output=[];if(!points.length)return output;
 let a=points.at(-1),da=distance(a);
 for(const b of points){const db=distance(b),insideA=da>=0,insideB=db>=0;if(insideA!==insideB)output.push(lerp(a,b,da/(da-db)));if(insideB)output.push(b);a=b;da=db;}
 return output;
}

function clipFront(points,camera){
 return clipPolygon(points,point=>camera.position.dot(point)-1,(a,b,t)=>a.clone().lerp(b,t).normalize());
}

function clipSpace(points,matrix){
 let values=points.map(point=>new THREE.Vector4(point.x*1.00008,point.y*1.00008,point.z*1.00008,1).applyMatrix4(matrix));
 const planes=[p=>p.w-1e-8,p=>p.x+p.w,p=>p.w-p.x,p=>p.y+p.w,p=>p.w-p.y,p=>p.z+p.w,p=>p.w-p.z];
 for(const plane of planes){values=clipPolygon(values,plane,(a,b,t)=>a.clone().lerp(b,t));if(!values.length)break;}
 return values;
}

function screen(points,width,height){return points.map(point=>({x:(point.x/point.w*.5+.5)*width,y:(.5-point.y/point.w*.5)*height}));}

/** Front hemisphere and near/frustum clipping share the original camera. */
export function projectInfographicGeometry(prepared,camera,width,height){
 const polygons=[],segments=[],matrix=new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);
 for(const triangle of prepared.triangles){const front=clipFront(triangle,camera),clipped=clipSpace(front,matrix);if(clipped.length>=3)polygons.push(screen(clipped,width,height));}
 for(const line of prepared.lines)for(let index=1;index<line.length;index++){
  // A segment is clipped as an open line, avoiding polygon-closing chords.
  let a=line[index-1],b=line[index],da=camera.position.dot(a)-1,db=camera.position.dot(b)-1;
  if(da<0&&db<0)continue;
  if(da<0)a=a.clone().lerp(b,da/(da-db)).normalize();else if(db<0)b=a.clone().lerp(b,da/(da-db)).normalize();
  let aa=new THREE.Vector4(a.x*1.00008,a.y*1.00008,a.z*1.00008,1).applyMatrix4(matrix),bb=new THREE.Vector4(b.x*1.00008,b.y*1.00008,b.z*1.00008,1).applyMatrix4(matrix),visible=true;
  for(const plane of [p=>p.w-1e-8,p=>p.x+p.w,p=>p.w-p.x,p=>p.y+p.w,p=>p.w-p.y,p=>p.z+p.w,p=>p.w-p.z]){
   const u=plane(aa),v=plane(bb);if(u<0&&v<0){visible=false;break;}if(u<0)aa=aa.clone().lerp(bb,u/(u-v));else if(v<0)bb=aa.clone().lerp(bb,u/(u-v));
  }
  if(visible)segments.push(screen([aa,bb],width,height));
 }
 const all=[...polygons.flat(),...segments.flat()];
 const extrema=all.reduce((v,p)=>({left:Math.min(v.left,p.x),right:Math.max(v.right,p.x),top:Math.min(v.top,p.y),bottom:Math.max(v.bottom,p.y)}),{left:Infinity,right:-Infinity,top:Infinity,bottom:-Infinity});
 const bounds=all.length?{x:extrema.left,y:extrema.top,width:extrema.right-extrema.left,height:extrema.bottom-extrema.top}:null;
 return {polygons,segments,bounds,visible:all.length>0};
}

export function infographicGraphemes(text){
 if(typeof text!=='string')fail('TEXT_SOURCE_INVALID');
 if(typeof Intl.Segmenter!=='function')fail('GRAPHEME_SEGMENTER_UNAVAILABLE');
 return [...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text)].map(value=>value.segment);
}

/** Reuse the v020 reveal count/scale without splitting combining graphemes. */
export function infographicRevealState(text,startFrame,endFrame,frame,mode='CHARACTER_REVEAL'){
 const graphemes=infographicGraphemes(text),intro=Math.max(1,endFrame-startFrame);
 if(mode==='STATIC')return {graphemes,visible:graphemes,opacity:1,scales:graphemes.map(()=>1),phase:'STEADY'};
 if(mode==='FADE')return {graphemes,visible:graphemes,opacity:clamp((frame-startFrame)/intro),scales:graphemes.map(()=>1),phase:frame<endFrame?'INTRO':'STEADY'};
 const state=characterRevealState({text:'\uE000'.repeat(graphemes.length),start_frame:startFrame,peak_frame:endFrame,end_frame:Infinity},frame);
 return {graphemes,visible:graphemes.slice(0,state.visible_chars),opacity:1,scales:state.character_scales,phase:frame<endFrame?'INTRO':'STEADY'};
}

const roleOrder={EVENT_TITLE:4,LOCATION_LABEL:3,SUPPORT_DATA:2,TTS_SUBTITLE:1};
function wrappedLines(ctx,text,maxWidth,maxLines){
 const graphemes=infographicGraphemes(text),lines=[];let current='';
 for(const grapheme of graphemes){
  if(grapheme==='\n'){lines.push(current);current='';continue;}
  if(current&&ctx.measureText(current+grapheme).width>maxWidth){
   const space=current.lastIndexOf(' ');if(space>0&&space>current.length*.4){lines.push(current.slice(0,space));current=current.slice(space+1)+grapheme;}
   else{lines.push(current);current=grapheme;}
  }else current+=grapheme;
 }
 if(current)lines.push(current);
 return lines.length<=maxLines?lines:null;
}

/** One measured layout owns all four roles, collision and safe placement.
 * Renderers and diagnostics consume the same returned boxes; no second label
 * renderer or unmeasured shadow plate is introduced.
 */
export function layoutInfographicLabels(ctx,candidates,{width,height,obstacles=[]}){
 const scale=width/1080,placed=[],omitted=[],seen=new Set(),safe={left:width*.07,right:width*.91,top:height*.11,bottom:height*.78};
 for(const source of [...candidates].sort((a,b)=>(roleOrder[b.role]||0)-(roleOrder[a.role]||0)||Number(b.primary)-Number(a.primary)||a.start_frame-b.start_frame)){
  if(!roleOrder[source.role]||typeof source.text!=='string'||!source.text)fail('LABEL_ROLE_INVALID');
  const key=`${source.role}|${source.text}|${source.target_id||''}`;if(seen.has(key)){omitted.push({id:source.id,reason:'DUPLICATE_LABEL'});continue;}seen.add(key);
  if(source.anchor&&(source.anchor.visible===false||source.anchor.x<0||source.anchor.x>width||source.anchor.y<0||source.anchor.y>height)){omitted.push({id:source.id,reason:source.anchor.occluded?'HORIZON_OCCLUDED':'OFFSCREEN'});continue;}
  const subtitle=source.role==='TTS_SUBTITLE',maxWidth=width*(subtitle?.80:.74),maxLines=source.max_lines??(source.role==='LOCATION_LABEL'||source.role==='SUPPORT_DATA'?1:2);if(!Number.isInteger(maxLines)||maxLines<1||maxLines>2)fail('TEXT_LINE_LIMIT_INVALID');
  const font=source.font_size*scale,weight=source.font_weight;cValidateFont(weight);
  ctx.save();let lines,metrics;
  try{ctx.font=`${weight} ${font}px 'Noto Cinema'`;lines=wrappedLines(ctx,source.text,maxWidth,maxLines);if(lines)metrics=lines.map(text=>ctx.measureText(text));}
  finally{ctx.restore();}
  if(!lines){omitted.push({id:source.id,reason:'TEXT_TOO_LONG_FOR_SAFE_LAYOUT'});continue;}
  const sourceGraphemes=infographicGraphemes(source.text),lineGlyphIndices=[];let sourceCursor=0;
  for(const line of lines){const glyphs=infographicGraphemes(line);while(sourceCursor<=sourceGraphemes.length&&sourceGraphemes.slice(sourceCursor,sourceCursor+glyphs.length).join('')!==line)sourceCursor++;if(sourceCursor>sourceGraphemes.length)fail('TEXT_WRAPPING_SOURCE_INVALID');lineGlyphIndices.push(glyphs.map((_,index)=>sourceCursor+index));sourceCursor+=glyphs.length;}
  const measuredWidth=Math.max(...metrics.map(value=>value.width)),lineHeight=font*1.25,measuredHeight=lineHeight*lines.length;
  const at=source.anchor||{x:width*.5,y:height*.22},centerX=at.x+Number(source.offset_x||0)*scale,centerY=at.y+Number(source.offset_y||0)*scale;
  const candidatesXY=subtitle?[[width*.5,height*.875]]:[[centerX,centerY],[centerX+110*scale,centerY-80*scale],[centerX-110*scale,centerY-80*scale],[centerX,centerY+110*scale],[width*.5,height*.16],[width*.5,height*.72]];
  let selected=null;
  for(const [x,y] of candidatesXY){
   const box={x:clamp(x-measuredWidth/2,safe.left,safe.right-measuredWidth),y:clamp(y-measuredHeight/2,subtitle?height*.82:safe.top,subtitle?height*.94-measuredHeight:safe.bottom-measuredHeight),width:measuredWidth,height:measuredHeight};
   if(box.width>safe.right-safe.left||box.height>(subtitle?height*.12:safe.bottom-safe.top))continue;
   if(placed.some(other=>overlap(box,other,12*scale))||obstacles.some(other=>overlap(box,other,10*scale)))continue;
   selected=box;break;
  }
  if(!selected){omitted.push({id:source.id,reason:'LABEL_COLLISION'});continue;}
  placed.push({...source,...selected,lines,lineGlyphIndices,font,fontFamily:'Noto Cinema',fontWeight:weight,lineHeight,
   ink_metrics:metrics.map(value=>({width:value.width,left:value.actualBoundingBoxLeft??null,right:value.actualBoundingBoxRight??null,ascent:value.actualBoundingBoxAscent??null,descent:value.actualBoundingBoxDescent??null})),
   glyph_metric_scope:metrics.every(value=>Number.isFinite(value.actualBoundingBoxAscent))?'Canvas2D actual font metrics':'Recording fixture metrics; not captured pixels'});
 }
 return {labels:placed,omitted,passed:!omitted.some(value=>['TEXT_TOO_LONG_FOR_SAFE_LAYOUT','LABEL_COLLISION'].includes(value.reason)),safe_area:{...safe,subtitle_top:height*.82,subtitle_bottom:height*.94}};
}
function cValidateFont(weight){if(![400,700].includes(weight))fail('UNVERIFIED_FONT_WEIGHT');}

export function drawInfographicLabels(ctx,layout,frame){
 const receipts=[];
 for(const box of layout.labels){
  const scale=box.font/box.font_size,state=infographicRevealState(box.text,box.start_frame,box.reveal_end_frame,frame,box.intro_mode);
  ctx.save();try{
   ctx.font=`${box.fontWeight} ${box.font}px 'Noto Cinema'`;ctx.globalAlpha=box.opacity*state.opacity;
   ctx.fillStyle=box.color||'#f3f1e5';ctx.strokeStyle='rgba(6,22,31,.88)';ctx.lineWidth=2.25*scale;
   ctx.shadowColor='rgba(6,22,31,.72)';ctx.shadowBlur=3*scale;ctx.shadowOffsetY=2*scale;ctx.shadowOffsetX=0;
   for(const [index,line] of box.lines.entries()){
    const baseline=box.y+box.font+index*box.lineHeight,graphemes=infographicGraphemes(line),sourceIndices=box.lineGlyphIndices[index],visibleCount=sourceIndices.filter(sourceIndex=>sourceIndex<state.visible.length).length;
    if(state.phase==='STEADY'||box.intro_mode==='FADE'){ctx.strokeText(line,box.x,baseline);ctx.fillText(line,box.x,baseline);}
    else for(let glyph=0;glyph<visibleCount;glyph++){
     const x=box.x+ctx.measureText(graphemes.slice(0,glyph).join('')).width,glyphWidth=ctx.measureText(graphemes[glyph]).width,glyphScale=state.scales[sourceIndices[glyph]]??1;
     ctx.save();try{ctx.translate(x+glyphWidth/2,baseline-box.font*.35);ctx.scale(glyphScale,glyphScale);ctx.strokeText(graphemes[glyph],-glyphWidth/2,box.font*.35);ctx.fillText(graphemes[glyph],-glyphWidth/2,box.font*.35);}finally{ctx.restore();}
    }
   }
  }finally{ctx.restore();}
  receipts.push({id:box.id,event_id:box.event_id,role:box.role,text:box.text,target_id:box.target_id,frame,
   start_frame:box.start_frame,reveal_end_frame:box.reveal_end_frame,end_frame:box.end_frame,phase:state.phase,
   displayed_text:state.visible.join(''),visible_graphemes:state.visible.length,total_graphemes:state.graphemes.length,
   opacity:box.opacity*state.opacity,primary:box.primary,box:{x:box.x,y:box.y,width:box.width,height:box.height},
   font:{family:'Noto Cinema',nominal_px:box.font_size,internal_px:box.font,weight:box.fontWeight,ink_metrics:box.ink_metrics,metric_scope:box.glyph_metric_scope},
   source_ref:box.source_ref,semantic_segment_ref:box.semantic_segment_ref??null,steady_style:'Constant text-local outline and 3px shadow; no oscillation'});
 }
 return receipts;
}

export function validateInfographicSelection(scene){
 const selected=scene.infographic;
 if(selected?.version!=='v022'||selected.parent_version!=='v021'||!['story-progression-v021','production-earth-v1'].includes(selected.parent_renderer_family))fail('EXPLICIT_V022_OPT_IN_REQUIRED');
 if(selected.parent_renderer_family==='story-progression-v021'&&scene.story_progression?.version!=='v021')fail('PARENT_V021_REQUIRED');
 if(selected.parent_renderer_family==='production-earth-v1'&&scene.production_defaults?.version!=='v1')fail('PRODUCTION_PARENT_REQUIRED');
 const fps=fpsValue(selected.fps),total=selected.total_frames;
 if(!Number.isFinite(fps)||fps<=0||!Number.isInteger(total)||total<=0||Math.abs(scene.duration*fps-total)>1e-7||scene.frame_count!==total)fail('FRAME_GRID_INVALID');
 if(!sha(selected.registry_sha256)||!sha(selected.profile_sha256)||!Array.isArray(selected.geometries)||!Array.isArray(selected.geometry_ids)||!Array.isArray(selected.events)||!Array.isArray(selected.labels)||!Array.isArray(selected.markers))fail('SELECTION_INVALID');
 const geometries=new Map();for(const record of selected.geometries){validateInfographicGeometry(record);if(geometries.has(record.id))fail('DUPLICATE_GEOMETRY');geometries.set(record.id,record);}
 if(!same([...geometries.keys()].sort(),[...selected.geometry_ids].sort())||new Set(selected.geometry_ids).size!==selected.geometry_ids.length)fail('GEOMETRY_SELECTION_INVALID');
 const events=new Map();
 for(const event of selected.events){
  if(!event||typeof event.id!=='string'||!event.id||events.has(event.id)||!Array.isArray(event.target_geometry_refs)||typeof event.state_before!=='string'||typeof event.state_after!=='string'||!['sourced_fact','hypothetical_scenario'].includes(event.evidence_type)||!event.claim_id)fail('EVENT_SOURCE_INVALID');
  if(![event.start_frame,event.transition_end_frame,event.end_frame].every(Number.isInteger)||!(0<=event.start_frame&&event.start_frame<=event.transition_end_frame&&event.transition_end_frame<event.end_frame&&event.end_frame<=total))fail('EVENT_FRAME_INVALID');
  for(const id of event.target_geometry_refs)if(!geometries.has(id)||geometries.get(id).geometry_type==='Point')fail('POINT_NOT_AN_AREA_OR_LINE');
  if(event.location_point_ref!==null&&geometries.get(event.location_point_ref)?.geometry_type!=='Point')fail('LOCATION_POINT_INVALID');
  if(!event.target_geometry_refs.length&&!event.location_point_ref)fail('EVENT_TARGET_REQUIRED');
  if(event.evidence_type==='hypothetical_scenario'&&(typeof event.watermark!=='string'||!event.watermark))fail('HYPOTHETICAL_WATERMARK_REQUIRED');
  const visualId=event.story_source_ref?.visual_event_id;
  if(visualId&&!scene.visual_events?.some(value=>value.id===visualId))fail('UNSUPPORTED_STORY_EVENT');
  events.set(event.id,event);
 }
 if(selected.geometry_layers!==undefined){if(!Array.isArray(selected.geometry_layers))fail('GEOMETRY_LAYER_INVALID');const ids=new Set();for(const layer of selected.geometry_layers){const event=events.get(layer.event_id);if(!event||ids.has(layer.id)||!event.target_geometry_refs.includes(layer.geometry_ref)||![layer.start_frame,layer.transition_end_frame,layer.end_frame,layer.source_event_end_frame,layer.primary_until_frame].every(Number.isInteger)||layer.start_frame!==event.start_frame||layer.source_event_end_frame!==event.end_frame||layer.end_frame<event.end_frame||layer.end_frame>total||layer.transition_end_frame<layer.start_frame||layer.transition_end_frame>=layer.end_frame||layer.primary_until_frame<layer.start_frame||layer.primary_until_frame>layer.end_frame||layer.state_before!==event.state_before||layer.state_after!==event.state_after||!layer.source_ref)fail('GEOMETRY_LAYER_INVALID');ids.add(layer.id);}}
 const labels=new Set();for(const label of selected.labels){
  const event=events.get(label.event_id),semantic=event?.semantic_segment_ref&&selected.semantic_segments?.some(segment=>segment.id===event.semantic_segment_ref);
  if(!event||typeof label.id!=='string'||labels.has(label.id)||!roleOrder[label.role]||typeof label.text!=='string'||!label.text||!label.source_ref&&!semantic)fail('LABEL_SOURCE_INVALID');labels.add(label.id);
  if(![label.start_frame,label.reveal_end_frame,label.end_frame].every(Number.isInteger)||!(0<=label.start_frame&&label.start_frame<label.reveal_end_frame&&label.reveal_end_frame<label.end_frame&&label.end_frame<=total))fail('LABEL_FRAME_INVALID');
  if(geometries.get(label.anchor_geometry_ref)?.geometry_type!=='Point')fail('LABEL_POINT_REQUIRED');
  const sourceText=label.role==='EVENT_TITLE'?event.text?.event_title:label.role==='LOCATION_LABEL'?event.text?.location_label:label.role==='SUPPORT_DATA'?event.text?.support_data:null;
  if(label.role!=='TTS_SUBTITLE'&&label.text!==sourceText)fail('TEXT_SOURCE_MISMATCH');
 }
 const markers=new Set();for(const marker of selected.markers){
  const event=events.get(marker.event_id),semantic=event?.semantic_segment_ref&&selected.semantic_segments?.some(segment=>segment.id===event.semantic_segment_ref);
  if(!event||typeof marker.id!=='string'||markers.has(marker.id)||geometries.get(marker.geometry_ref)?.geometry_type!=='Point'||!marker.source_ref&&!semantic)fail('MARKER_SOURCE_INVALID');markers.add(marker.id);
  if(![marker.start_frame,marker.intro_end_frame,marker.fade_start_frame,marker.end_frame].every(Number.isInteger)||!(0<=marker.start_frame&&marker.start_frame<marker.intro_end_frame&&marker.intro_end_frame<=marker.fade_start_frame&&marker.fade_start_frame<marker.end_frame&&marker.end_frame<=total))fail('MARKER_FRAME_INVALID');
 }
 return {selected,fps,total,geometries,events};
}

export function validateInfographicProfile(profile){
 if(profile?.version!=='v022'||profile.parent_version!=='v021'||profile.geometry?.boundary_draw!==false||profile.geometry.preserve_holes!==true||profile.geometry.horizon_occlusion!==true||profile.limits?.primary_motion_effects!==1||profile.limits.added_sfx!==0||profile.limits.added_routes!==0||profile.limits.added_entities!==0)fail('PROFILE_INVALID');
 if(profile.geometry.primary_outline_px<3||profile.geometry.primary_outline_px>5||profile.geometry.secondary_outline_px<1.5||profile.geometry.secondary_outline_px>2.5||profile.geometry.region_fill_alpha<.18||profile.geometry.region_fill_alpha>.35||profile.marker.size_px<44||profile.marker.size_px>64||profile.marker.max_size_px>80||profile.marker.pop_frames!==9||profile.marker.pop_reference_fps!==30)fail('PROFILE_RANGE_INVALID');
 for(const role of Object.keys(roleOrder)){const style=profile.typography?.[role];if(!style||!Number.isFinite(style.size_px)||!Number.isInteger(style.max_lines))fail('TYPOGRAPHY_INVALID');cValidateFont(style.weight);}
 return profile;
}

async function verifiedJSON(url,expected,allowed){
 if(trustedStaticURL(url)!==allowed||!sha(expected))fail('RESOURCE_SOURCE_INVALID');
 const response=await fetch(allowed,{credentials:'same-origin',redirect:'error'});if(!response.ok)fail('RESOURCE_FETCH_FAILED');
 const bytes=await response.arrayBuffer();if(await digestBytes(bytes)!==expected)fail('RESOURCE_HASH_MISMATCH');
 try{return JSON.parse(new TextDecoder().decode(bytes));}catch{fail('RESOURCE_JSON_INVALID');}
}

function stateStyle(event,frame,profile){
 const a=profile.state_styles[event.state_before],b=profile.state_styles[event.state_after];if(!a||!b)fail('EVENT_STATE_INVALID');
 const p=event.transition_end_frame===event.start_frame?1:clamp((frame-event.start_frame)/(event.transition_end_frame-event.start_frame));
 return {color:'#'+new THREE.Color(a.color).lerp(new THREE.Color(b.color),p).getHexString(),opacity:a.opacity+(b.opacity-a.opacity)*p,state:p>=1?event.state_after:`${event.state_before}→${event.state_after}`,transition:p};
}

/** Reuse approved material functions on the real Production camera family.
 * Source selection and coverage are authored upstream; an unknown area keeps
 * the existing global material. No old QA camera selection is fabricated.
 */
export class SceneProductionRegionalRenderer extends SceneProductionEarthRenderer{
 constructor(scene,plan){super(scene,plan);this.regionalMaterialReady=false;this.regionalMaterialReceipt={status:'NO_LOCAL_LOD',texture_uploads:0,covered_regions:[],GPU:'NOT_RUN'};}
 async init(){
  await super.init();const selection=this.sceneSpec.regional_lod;
  if(!selection?.selected_regions?.length){this.regionalMaterialReceipt={status:'NO_LOCAL_LOD',texture_uploads:0,covered_regions:[],warnings:selection?.warnings||['REGIONAL_LOD_UNAVAILABLE'],GPU:'NOT_RUN'};return this;}
  const started=performance.now(),qualitySelection=selection.visual_quality_contract,eventSelection=selection.event_quality_contract;
  if(!qualitySelection||!eventSelection||selection.source_manifest_sha256!==qualitySelection.manifest_sha256)fail('REGIONAL_SELECTION_INVALID');
  this.qualityProfile=validateQualityProfile(await verifiedJSON(qualitySelection.profile_url,qualitySelection.profile_sha256,'/static/visual_quality_v018.json'));
  const rawManifest=await verifiedJSON(this.qualityProfile.regional_detail.manifest_url,selection.source_manifest_sha256,'/static/earth-detail/v018/manifest.json');this.qualityManifest=validateDetailManifest(rawManifest);
  this.eventQualityProfile=validateEventQualityProfile(await verifiedJSON(eventSelection.profile_url,eventSelection.profile_sha256,'/static/event_quality_v019.json'));
  this.qualityProfileHash=qualitySelection.profile_sha256;this.qualityManifestHash=selection.source_manifest_sha256;this.eventQualityProfileHash=eventSelection.profile_sha256;
  for(const region of selection.selected_regions){
   const actual=this.qualityManifest.textures.find(tile=>tile.region_id===region.region_id);
   if(!actual||!same(actual.bounds,region.bounds))fail('REGIONAL_COVERAGE_SOURCE_INVALID');
   for(const texture of region.textures||[]){const key=texture.role==='regional_land_mask'?'mask_':'';if(texture.url!==actual[key+'url']||texture.sha256!==actual[key+'sha256']||texture.width!==actual[key+'width']||texture.height!==actual[key+'height'])fail('REGIONAL_TEXTURE_SOURCE_INVALID');}
  }
  const request=this.qualityProfile.filtering.anisotropy_request;
  const load=async(source,mask)=>{
   const key=mask?'mask_':'',url=trustedStaticURL(source[key+'url'],'/static/earth-detail/v018/');
   const response=await fetch(url,{credentials:'same-origin',redirect:'error'});if(!response.ok)fail('REGIONAL_TEXTURE_FETCH_FAILED');
   const bytes=await response.arrayBuffer();if(await digestBytes(bytes)!==source[key+'sha256'])fail('REGIONAL_TEXTURE_HASH_MISMATCH');
   const array=new Uint8Array(bytes);let binary='';for(let i=0;i<array.length;i+=32768)binary+=String.fromCharCode(...array.subarray(i,i+32768));
   const texture=await new THREE.TextureLoader().loadAsync('data:image/png;base64,'+btoa(binary));
   if(texture.image.width!==source[key+'width']||texture.image.height!==source[key+'height']){texture.dispose();fail('REGIONAL_TEXTURE_DIMENSIONS_INVALID');}
   return configureQualityTexture(texture,this.gl.capabilities,request,!mask);
  };
  // The unchanged v019 mask shader uses both preserved pairs. Loading the full
  // four-image manifest is explicit, bounded and recorded; no new data exists.
  this.qualityTiles=await Promise.all(this.qualityManifest.textures.map(async source=>({source,day:await load(source,false),mask:await load(source,true)})));
  SceneVisualQualityRenderer.prototype.installQualitySurface.call(this);
  SceneEventQualityRenderer.prototype.installEventQualitySurface.call(this);
  this.regionalMaterialReady=true;
  const storage=this.qualityTiles.reduce((sum,tile)=>sum+tile.day.image.width*tile.day.image.height*4+tile.mask.image.width*tile.mask.image.height*4,0);
  this.regionalMaterialReceipt={status:'VERIFIED_EXISTING_REGIONAL_MATERIAL',covered_regions:selection.selected_regions.map(region=>region.region_id),coverage_complete:selection.coverage_complete,texture_uploads:4,source_manifest_sha256:selection.source_manifest_sha256,source_bytes:rawManifest.textures.reduce((sum,tile)=>sum+Number(tile.bytes||0),0),decoded_rgba_bytes:storage,estimated_texture_storage_bytes:Math.ceil(storage*4/3),memory_scope:'Source dimensions and full mip chain estimate; not measured RAM/VRAM',source_semantics:'Existing regional Natural Earth RGB relief plus real land masks; unknown geography uses global source',initialization_seconds:(performance.now()-started)/1000,GPU:'NOT_RUN'};
  this.frame(0);return this;
 }
 mapAt(t){
  super.mapAt(t);if(!this.regionalMaterialReady)return;
  const value=this.cam.values(t),selected=this.sceneSpec.regional_lod.selected_regions;
  const covered=selected.some(region=>value.lon>=region.bounds[0]&&value.lon<=region.bounds[2]&&value.lat>=region.bounds[1]&&value.lat<=region.bounds[3]);
  const weight=covered?qualityWeight(this.camera.position.length()-1,this.qualityProfile):0,surface=this.qualityProfile.surface,u=this.map.surface.uniforms;
  u.uVQWeight.value=weight;u.uVQExposureScale.value=1+(surface.close_exposure_scale-1)*weight;u.uVQSpecularScale.value=1+(surface.ocean_specular_scale-1)*weight;u.uEQWeight.value=weight;
 }
 audit(t){const value=super.audit(t);value.regionalLOD={...structuredClone(this.regionalMaterialReceipt),material_weight:this.regionalMaterialReady?this.map.surface.uniforms.uVQWeight.value:0};return value;}
}

function InfographicOverlay(Parent){return class extends Parent{
 constructor(scene,plan){const contract=validateInfographicSelection(scene);super(scene,plan);this.infographicAuthoredScene=scene;this.infographicContract=contract;this.infographicReady=false;this.infographicReceipt=null;}
 async init(){
  await super.init();const selection=this.infographicContract.selected;
  const [profile,registry]=await Promise.all([verifiedJSON(selection.profile_url,selection.profile_sha256,'/static/infographic/v022/profile.json'),verifiedJSON(selection.registry_url,selection.registry_sha256,'/static/infographic/v022/registry.json')]);
  this.infographicProfile=validateInfographicProfile(profile);
  if(registry.version!=='v022'||registry.crs!=='EPSG:4326'||!Array.isArray(registry.geometries))fail('REGISTRY_INVALID');
  const records=new Map(registry.geometries.map(record=>[record.id,record]));
  for(const record of selection.geometries)if(!same(record,records.get(record.id)))fail('REGISTRY_RECORD_MISMATCH');
  this.infographicPrepared=new Map(selection.geometries.map(record=>[record.id,prepareInfographicGeometry(record)]));
  if(!globalThis.document?.fonts)fail('FONT_API_UNAVAILABLE');
  for(const weight of new Set(Object.values(profile.typography).map(style=>style.weight))){
   await document.fonts.load(`${weight} 72px 'Noto Cinema'`,'수에즈 CANAL CLOSED 123');
   if(!document.fonts.check(`${weight} 72px 'Noto Cinema'`,'수에즈 CANAL CLOSED 123'))fail('FONT_NOT_READY');
   if(weight===700&&![...document.fonts].some(face=>String(face.family).replace(/["']/g,'')==='Noto Cinema'&&face.weight==='700'&&face.status==='loaded'))fail('REAL_BOLD_FACE_NOT_LOADED');
  }
  this.infographicFontsReady=true;this.infographicReady=true;this.frame(0);return this;
 }
 overlay(t){
  if(!this.infographicReady)return super.overlay(t);
  const {selected,fps,events,geometries}=this.infographicContract,frame=frameAt(t,fps),profile=this.infographicProfile,ctx=this.ctx,scale=this.w/1080;
  // A single owner draws labels. Old effects cannot draw the same text or pin
  // underneath this version; OFF never enters this path.
  this.referenceEffectReceipts=[];this.storyProgressionReceipts=[];this.labels=[];this.eventVisibility=[];
  const activeEvents=selected.events.filter(event=>frame>=event.start_frame&&frame<event.end_frame),geometryReceipts=[],markerReceipts=[],obstacles=[],geometryObstacles=[];
  const stateTargets=new Map();
  if(Array.isArray(selected.geometry_layers))for(const layer of selected.geometry_layers){if(frame>=layer.start_frame&&frame<layer.end_frame){const source=events.get(layer.event_id);stateTargets.set(layer.geometry_ref,{...source,start_frame:layer.start_frame,transition_end_frame:layer.transition_end_frame,end_frame:layer.end_frame,state_before:layer.state_before,state_after:layer.state_after,geometry_layer:layer});}}
  else for(const event of activeEvents)for(const id of event.target_geometry_refs)stateTargets.set(id,event);
  for(const [id,event] of stateTargets){
   const prepared=this.infographicPrepared.get(id),projected=projectInfographicGeometry(prepared,this.camera,this.w,this.h),style=stateStyle(event,frame,profile),primary=(event.primary_role==='EVENT_TITLE'||event.primary_role==='LOCATION_LABEL')&&(!event.geometry_layer||frame<event.geometry_layer.primary_until_frame),lineWidth=(primary?profile.geometry.primary_outline_px:profile.geometry.secondary_outline_px)*scale;
   ctx.save();try{
    ctx.globalAlpha=style.opacity;ctx.fillStyle=style.color;ctx.strokeStyle=style.color;ctx.lineWidth=lineWidth;ctx.lineJoin='round';ctx.lineCap='round';
    if(projected.polygons.length){ctx.globalAlpha=profile.geometry.region_fill_alpha*style.opacity;ctx.beginPath();for(const polygon of projected.polygons){ctx.moveTo(polygon[0].x,polygon[0].y);for(const point of polygon.slice(1))ctx.lineTo(point.x,point.y);ctx.closePath();}ctx.fill();ctx.globalAlpha=style.opacity;}
    ctx.beginPath();for(const segment of projected.segments){ctx.moveTo(segment[0].x,segment[0].y);ctx.lineTo(segment[1].x,segment[1].y);}ctx.stroke();
   }finally{ctx.restore();}
   geometryReceipts.push({geometry_id:id,event_id:event.id,layer_id:event.geometry_layer?.id||null,source_event_end_frame:event.geometry_layer?.source_event_end_frame||event.end_frame,semantic_target_ref:event.geometry_layer?.semantic_target_ref||null,frame,state:style.state,state_before:event.state_before,state_after:event.state_after,transition:style.transition,visible:projected.visible,polygon_count:projected.polygons.length,segment_count:projected.segments.length,line_width_px_1080:lineWidth/scale,fill_alpha:projected.polygons.length?profile.geometry.region_fill_alpha*style.opacity:0,bounds:projected.bounds,source_id:prepared.record.source_id,source_feature_id:prepared.record.source_feature_id,source_sha256:prepared.record.sha256,precision:prepared.record.scale,holes_preserved:true,boundary_draw_progress:false});
   if(projected.bounds&&projected.visible){
    const box=projected.bounds,area=box.width*box.height/(this.w*this.h),criticalLine=prepared.record.geometry_role==='canal_centerline',compact=box.width<=this.w*.45&&box.height<=this.h*.45&&area<=.16;
    if(criticalLine||compact){const reserved={x:box.x-4*scale,y:box.y-4*scale,width:box.width+8*scale,height:box.height+8*scale,geometry_id:id,policy:criticalLine?'Verified critical canal line bounds':'Compact verified geometry bounds'};obstacles.push(reserved);geometryObstacles.push(reserved);}
   }
  }
  for(const marker of selected.markers){
   if(frame<marker.start_frame||frame>=marker.end_frame)continue;
   const geometry=geometries.get(marker.geometry_ref),point=this.project(normal(geometry.coordinates).multiplyScalar(1.00008));
   const controlling=activeEvents.filter(event=>event.location_point_ref===marker.geometry_ref).at(-1)||events.get(marker.event_id),style=stateStyle(controlling,frame,profile);
   const popFrames=marker.intro_end_frame-marker.start_frame,referenceFrame=marker.start_frame+(frame-marker.start_frame)*9/popFrames;
   const state=markerPopState({start_frame:marker.start_frame,peak_frame:marker.start_frame+4,end_frame:Infinity},referenceFrame,{patterns:{MARKER_POP:{pop_frames:9,dip_offset_frames:6,start_scale:.12,peak_scale:.95,dip_scale:.85}}});
   const markerScale=frame>=marker.intro_end_frame?1:state.scale,size=profile.marker.size_px*scale*markerScale,radius=size*.30,top=point.y-size*.72,fade=frame>=marker.fade_start_frame?clamp((marker.end_frame-frame)/(marker.end_frame-marker.fade_start_frame)):1;
   const box={x:point.x-size*.36,y:point.y-size,width:size*.72,height:size},visible=point.visible&&box.x>=this.w*.06&&box.x+box.width<=this.w*.94&&box.y>=this.h*.08&&box.y+box.height<=this.h*.82;
   if(visible){ctx.save();try{ctx.globalAlpha=style.opacity*fade;ctx.strokeStyle=style.color;ctx.lineWidth=3*scale;ctx.fillStyle='rgba(6,22,31,.50)';ctx.beginPath();ctx.moveTo(point.x,point.y);ctx.lineTo(point.x,top+radius);ctx.stroke();ctx.beginPath();ctx.arc(point.x,top,radius,0,Math.PI*2);ctx.fill();ctx.stroke();}finally{ctx.restore();}obstacles.push(box);}
   markerReceipts.push({id:marker.id,event_id:marker.event_id,state_event_id:controlling.id,geometry_id:marker.geometry_ref,frame,start_frame:marker.start_frame,intro_end_frame:marker.intro_end_frame,fade_start_frame:marker.fade_start_frame,end_frame:marker.end_frame,phase:frame<marker.intro_end_frame?'INTRO':frame<marker.fade_start_frame?'PERSISTENT':'FADE',scale:markerScale,visible,opacity:visible?style.opacity*fade:0,box,source_ref:marker.source_ref,source_id:geometry.source_id,coordinate_role:geometry.geometry_role});
  }
  const candidates=[];
  for(const label of selected.labels){
   if(frame<label.start_frame||frame>=label.end_frame)continue;
   if(label.role==='TTS_SUBTITLE'&&selected.subtitle_owner!=='renderer')continue;
   const geometry=geometries.get(label.anchor_geometry_ref),anchor=this.project(normal(geometry.coordinates).multiplyScalar(1.00008)),typography=profile.typography[label.role];
   const event=events.get(label.event_id);
   candidates.push({...label,target_id:label.anchor_geometry_ref,anchor,font_size:typography.size_px,font_weight:typography.weight,max_lines:typography.max_lines,opacity:label.role==='EVENT_TITLE'?.98:label.role==='LOCATION_LABEL'?.78:.70,intro_mode:label.intro_mode||(infographicGraphemes(label.text).length>24?'FADE':'CHARACTER_REVEAL'),offset_x:label.role==='LOCATION_LABEL'?80:0,offset_y:label.role==='EVENT_TITLE'?-100:label.role==='LOCATION_LABEL'?70:150,semantic_segment_ref:event.semantic_segment_ref});
  }
  const hypothesis=activeEvents.find(event=>event.evidence_type==='hypothetical_scenario');
  if(hypothesis)candidates.push({id:`WATERMARK_${hypothesis.id}`,event_id:hypothesis.id,role:'SUPPORT_DATA',text:hypothesis.watermark,target_id:hypothesis.location_point_ref,anchor:{x:this.w*.5,y:this.h*.125,visible:true},font_size:44,font_weight:400,primary:false,opacity:.82,start_frame:hypothesis.start_frame,reveal_end_frame:hypothesis.start_frame+1,end_frame:hypothesis.end_frame,intro_mode:'STATIC',source_ref:{field:'event.watermark',event_id:hypothesis.id},semantic_segment_ref:hypothesis.semantic_segment_ref});
  const layout=layoutInfographicLabels(ctx,candidates,{width:this.w,height:this.h,obstacles}),labelReceipts=drawInfographicLabels(ctx,layout,frame);
  this.labels=layout.labels.map(box=>({...box,event_id:events.get(box.event_id)?.story_source_ref?.visual_event_id||box.event_id,opacity:labelReceipts.find(receipt=>receipt.id===box.id)?.opacity??0}));
  const primaryMotion=new Set();for(const marker of markerReceipts)if(marker.visible&&marker.phase==='INTRO')primaryMotion.add('MARKER:'+marker.id);for(const label of labelReceipts)if(label.primary&&label.phase==='INTRO'&&label.opacity>.01)primaryMotion.add('LABEL:'+label.id);
  this.infographicReceipt={version:'v022',frame,timestamp:t,parent_renderer_family:selected.parent_renderer_family,registry_sha256:selected.registry_sha256,profile_sha256:selected.profile_sha256,geometry:geometryReceipts,markers:markerReceipts,labels:labelReceipts,layout:{passed:layout.passed,omitted:layout.omitted,safe_area:layout.safe_area,critical_geometry_obstacles:geometryObstacles,occlusion_policy:'Avoid verified critical canal and compact target bounds plus marker boxes; large-country viewport coverage never reserves the whole map'},primary_motion_effect_count:primaryMotion.size,persistent_geometry_count:geometryReceipts.filter(value=>value.visible).length,persistent_marker_count:markerReceipts.filter(value=>value.visible&&value.phase==='PERSISTENT').length,subtitle:{owner:selected.subtitle_owner||'ffmpeg',native_drawn:labelReceipts.some(value=>value.role==='TTS_SUBTITLE'),reserved_safe_area:profile.text.subtitle_safe_area},added_sfx:0,added_routes:0,added_entities:0,additional_texture_uploads:selected.parent_renderer_family==='production-earth-v1'?(this.regionalMaterialReceipt?.texture_uploads||0):0,regional_lod:this.regionalMaterialReceipt||null,metric_scope:'Actual projected geometry and measured font layout; captured pixel/GPU quality require separate output verification',font_sources:selected.font_sources||null};
 }
 audit(t){const value=super.audit(t);if(!this.infographicReady)return value;value.infographic=structuredClone(this.infographicReceipt);value.fontReady=this.infographicFontsReady&&value.fontReady!==false;if(value.effectLayer)value.effectLayer.infographic=structuredClone(value.infographic);return value;}
};}

export const SceneInfographicRenderer=InfographicOverlay(SceneStoryProgressionRenderer);
export const SceneProductionInfographicRenderer=InfographicOverlay(SceneProductionRegionalRenderer);
export function createInfographicRenderer(scene,plan){
 if(scene.infographic===undefined)return scene.story_progression===undefined?new SceneProductionRegionalRenderer(scene,plan):createStoryProgressionRenderer(scene,plan);
 return scene.infographic.parent_renderer_family==='production-earth-v1'?new SceneProductionInfographicRenderer(scene,plan):new SceneInfographicRenderer(scene,plan);
}
