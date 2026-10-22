/** Data-driven presentation grammar; no place, event date or reference frame literals. */
import {validateEventAnchor,freezeEventData} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {graphemes,popScale,compileSourceArclength} from '../reference-director-v1/director_events.mjs';
import {assertPinnedFontText} from './font_coverage.mjs';

export const PROGRAM_SCHEMA='WORLD_ENGINE_DIRECTOR_PROGRAM_V1';
const ROLES=['REQUIRED_VISIBLE_SAFE','CONTEXT_CULL','AREA_VIEWPORT_CLIP'];
const TYPES=['PIN','LABEL','AREA','LINE','METRIC'];
const assert=(v,c)=>{if(!v)throw Error('DIRECTOR_PROGRAM_'+c);};
const object=(v,keys,c)=>{assert(v&&typeof v==='object'&&!Array.isArray(v),'OBJECT_'+c);assert(Object.keys(v).every(k=>keys.includes(k)),'UNKNOWN_FIELD_'+c);return v;};
const str=(v,c)=>{assert(typeof v==='string'&&v.trim()&&!/[\u0000-\u001f\u007f]/u.test(v),'TEXT_'+c);return v;};
const integer=(v,c,min=0)=>{assert(Number.isSafeInteger(v)&&v>=min,'INTEGER_'+c);return v;};
const number=(v,c,min=0,max=Infinity)=>{assert(Number.isFinite(v)&&v>=min&&v<=max,'NUMBER_'+c);return v;};
const clone=v=>structuredClone(v),clamp=x=>Math.max(0,Math.min(1,x));
const box=(v,c)=>{assert(Array.isArray(v)&&v.length===4&&v.every(Number.isFinite)&&v[0]<v[2]&&v[1]<v[3],'BOX_'+c);return clone(v);};
function metadata(value,depth=0){
 assert(depth<=16,'SOURCE_METADATA_DEPTH');
 if(value===null||['string','boolean'].includes(typeof value))return;
 if(typeof value==='number'){assert(Number.isFinite(value),'SOURCE_METADATA_FINITE');return;}
 assert(value&&typeof value==='object'&&(Array.isArray(value)||[Object.prototype,null].includes(Object.getPrototypeOf(value))),'SOURCE_METADATA_JSON');
 Object.values(value).forEach(v=>metadata(v,depth+1));
}
function source(v,mode,observation=false){
 object(v,['id','sha256','verification','sourceURL','license','date','crs','nativeResolution','uncertainty'],'SOURCE');str(v.id,'SOURCE_ID');assert(/^[a-f0-9]{64}$/u.test(v.sha256),'SOURCE_SHA');
 for(const key of ['sourceURL','license','date','crs'])if(v[key]!==undefined)str(v[key],'SOURCE_'+key);
 for(const key of ['nativeResolution','uncertainty'])if(v[key]!==undefined)metadata(v[key]);
 const allowed=mode==='SYNTHETIC_TEST'?['SYNTHETIC_TEST']:observation?['VERIFIED','OBSERVED_REFERENCE_TEXT']:['VERIFIED'];
 assert(allowed.includes(v.verification),'SOURCE_VERIFICATION');return clone(v);
}
function records(rows,kind,mode){
 assert(Array.isArray(rows)&&rows.length<=256,'RECORDS_'+kind);
 return rows.map(r=>{
  object(r,kind==='locations'?['id','label','anchor','source']:kind==='metrics'?['id','text','source']:kind==='lines'?['id','geometry','direction','source']:['id','geometry','source'],kind);
  const value={id:str(r.id,kind+'_ID'),source:source(r.source,mode,kind==='metrics')};
  if(kind==='locations'){value.label=str(r.label,'LOCATION_LABEL');value.anchor=validateEventAnchor(r.anchor);}
  else if(kind==='metrics')value.text=str(r.text,'METRIC_TEXT');
  else {object(r.geometry,['type','coordinates'],'GEOMETRY');
   if(kind==='lines'){
    assert(r.geometry.type==='LineString','LINESTRING');assert(Array.isArray(r.geometry.coordinates)&&r.geometry.coordinates.length<=129,'LINE_VERTEX_GPU_CAPACITY');value.direction=r.direction??'FORWARD';
    value.arclength=compileSourceArclength(r.geometry.coordinates,value.direction);
   }else{
    assert(['Polygon','MultiPolygon'].includes(r.geometry.type),'POLYGON');
    const rings=r.geometry.type==='Polygon'?r.geometry.coordinates:r.geometry.coordinates.flat();
    assert(Array.isArray(rings)&&rings.length>0&&rings.length<=2048,'POLYGON_RINGS');
    for(const ring of rings){assert(Array.isArray(ring)&&ring.length>=4,'RING');ring.forEach(validateEventAnchor);
     assert(JSON.stringify(ring[0])===JSON.stringify(ring.at(-1)),'RING_CLOSURE');
     for(let i=1;i<ring.length;i++)assert(Math.abs(ring[i][0]-ring[i-1][0])<=180,'DATELINE_WRAP_UNSUPPORTED');
    }
   }value.geometry=clone(r.geometry);
  }return value;
 });
}
function color(v,c){assert(Array.isArray(v)&&v.length===4&&v.every(x=>Number.isFinite(x)&&x>=0&&x<=1),'COLOR_'+c);return clone(v);}
function style(v,type){
 const keys=type==='PIN'?['assetVariant','widthPx','heightPx']:type==='AREA'?['fillColor','coreColor','widthPx','haloColor','haloRadiusPx','haloOpacity']:type==='LINE'?['coreColor','widthPx','haloColor','haloRadiusPx','haloOpacity']:['fontPx','color','haloColor','haloRadiusPx','haloOpacity',type==='LABEL'?'gapPx':'offsetPx'];
 object(v,keys,'STYLE_'+type);const out=clone(v);
 if(type==='PIN'){assert(['HERO','CONTEXT'].includes(v.assetVariant),'PIN_ASSET_VARIANT');number(v.widthPx,'PIN_WIDTH',1,512);number(v.heightPx,'PIN_HEIGHT',1,512);
  const ratio=v.assetVariant==='HERO'?116/151:49/64;assert(Math.abs(v.widthPx/v.heightPx-ratio)<1e-9,'PIN_UNIFORM_ART_ASPECT_REQUIRED');}
 else {
  for(const name of ['fillColor','coreColor','haloColor','color'])if(v[name]!==undefined)color(v[name],name);
  if(type==='AREA')assert(v.fillColor&&v.coreColor&&v.haloColor,'AREA_COLORS_REQUIRED');
  if(type==='LINE')assert(v.coreColor&&v.haloColor,'LINE_COLORS_REQUIRED');
  for(const name of ['widthPx','fontPx'])if(v[name]!==undefined)number(v[name],name,1,256);
  for(const name of ['haloRadiusPx','gapPx','offsetPx'])if(v[name]!==undefined)number(v[name],name,0,128);
  if(v.haloOpacity!==undefined)number(v.haloOpacity,'HALO_OPACITY',0,1);
  if(['LABEL','METRIC'].includes(type)){
   assert(v.fontPx&&v.color&&v.haloColor&&v.haloRadiusPx!==undefined&&v.haloOpacity!==undefined,'TEXT_STYLE_REQUIRED');
   if(type==='METRIC')assert(v.offsetPx!==undefined,'METRIC_OFFSET_REQUIRED');
   if(type==='LABEL')assert(v.gapPx!==undefined,'LABEL_GAP_REQUIRED');
  }else assert(v.widthPx&&v.haloRadiusPx!==undefined&&v.haloOpacity!==undefined,'LINE_STYLE_REQUIRED');
 }
 return out;
}
export function compileDirectorProgram(input){
 object(input,['schema','dataMode','frameRange','fps','output','safeArea','locations','areas','lines','metrics','events','windows'],'INPUT');
 assert(input.schema===PROGRAM_SCHEMA,'SCHEMA');assert(['SYNTHETIC_TEST','VERIFIED_GEOGRAPHY'].includes(input.dataMode),'DATA_MODE');
 assert(Array.isArray(input.frameRange)&&input.frameRange.length===2,'FRAME_RANGE');const [start,end]=input.frameRange;
 integer(start,'START');integer(end,'END',start+1);assert(end-start<=18000,'GLOBAL_FRAME_LIMIT');
 assert(input.fps===30&&JSON.stringify(input.output)==='[1080,1920]','CANONICAL_OUTPUT');
 const safeArea=box(input.safeArea,'SAFE');assert(safeArea[0]>=0&&safeArea[1]>=0&&safeArea[2]<=input.output[0]&&safeArea[3]<=input.output[1],'SAFE_OUTSIDE_VIEWPORT');
 const data={};for(const kind of ['locations','areas','lines','metrics'])data[kind]=records(input[kind]??[],kind,input.dataMode);
 const ids=Object.values(data).flat().map(r=>r.id);assert(new Set(ids).size===ids.length,'UNIQUE_RECORD_IDS');
 const find=(kind,id)=>{const r=data[kind].find(r=>r.id===id);assert(r,'MISSING_'+kind.toUpperCase()+'_BINDING');return r;};
 assert(Array.isArray(input.events)&&input.events.length>0&&input.events.length<=256,'EVENTS');
 const eventIds=new Set();
 const events=input.events.map(e=>{
  object(e,['id','type','locationId','pinEventId','areaId','lineId','metricId','startFrame','popFrames','revealFrames','graphemeIntervalFrames','settleFrames','fullyReadableFrame','holdUntilFrame','role','requiredRange','style'],'EVENT');
  str(e.id,'EVENT_ID');assert(!eventIds.has(e.id),'UNIQUE_EVENT_IDS');eventIds.add(e.id);assert(TYPES.includes(e.type),'EVENT_TYPE');
  const baseKeys=['id','type','startFrame','holdUntilFrame','role','requiredRange','style'];
  const typeKeys={PIN:['locationId','popFrames'],LABEL:['locationId','pinEventId','graphemeIntervalFrames','settleFrames','fullyReadableFrame'],AREA:['areaId','revealFrames'],LINE:['lineId','revealFrames'],METRIC:['lineId','metricId','graphemeIntervalFrames','settleFrames','fullyReadableFrame']};
  object(e,[...baseKeys,...typeKeys[e.type]],'EVENT_'+e.type);
  assert(!['AREA','LINE'].includes(e.type)||e.requiredRange===undefined,'UNSUPPORTED_REQUIRED_RANGE_FOR_AREA_LINE');
  integer(e.startFrame,'EVENT_START',start);integer(e.holdUntilFrame,'EVENT_END',e.startFrame+1);assert(e.holdUntilFrame<=end,'EVENT_OUTSIDE_GLOBAL_RANGE');
  assert(ROLES.includes(e.role),'VISIBILITY_ROLE');const out={...clone(e),style:style(e.style,e.type)};
  assert(e.type==='AREA'?e.role==='AREA_VIEWPORT_CLIP':e.role!=='AREA_VIEWPORT_CLIP','ROLE_FOR_EVENT_TYPE');
  assert(e.type!=='LINE'||e.role==='REQUIRED_VISIBLE_SAFE','UNSUPPORTED_LINE_CONTEXT_CULL');
  if(e.requiredRange!==undefined){assert(Array.isArray(e.requiredRange)&&e.requiredRange.length===2&&e.requiredRange.every(Number.isSafeInteger)&&e.requiredRange[0]>=e.startFrame&&e.requiredRange[1]<=e.holdUntilFrame&&e.requiredRange[1]>e.requiredRange[0],'REQUIRED_RANGE');}
  if(['PIN','LABEL'].includes(e.type))find('locations',e.locationId);
  if(e.type==='PIN'){integer(e.popFrames,'PIN_POP',2);assert(e.startFrame+e.popFrames<=e.holdUntilFrame,'PIN_POP_TOO_LONG');}
  if(e.type==='AREA')find('areas',e.areaId);
  if(['AREA','LINE'].includes(e.type)){integer(e.revealFrames,'REVEAL',1);assert(e.startFrame+e.revealFrames<=e.holdUntilFrame,'REVEAL_TOO_LONG');}
  if(['LINE','METRIC'].includes(e.type))find('lines',e.lineId);
  if(['LABEL','METRIC'].includes(e.type)){
   const text=e.type==='LABEL'?find('locations',e.locationId).label:find('metrics',e.metricId).text;
   assertPinnedFontText(text);
   out.graphemes=graphemes(text);assert(out.graphemes.length<=128,'TEXT_LENGTH');integer(e.graphemeIntervalFrames,'GLYPH_INTERVAL',1);integer(e.settleFrames,'GLYPH_SETTLE',1);
   const glyphCount=out.graphemes.filter(g=>!/^[\s]+$/u.test(g)).length;
   out.readableFrame=e.startFrame+(glyphCount-1)*e.graphemeIntervalFrames+e.settleFrames;
   assert(glyphCount>0&&out.readableFrame<e.holdUntilFrame,'READING_HOLD_REQUIRED');
   if(e.fullyReadableFrame!==undefined)assert(Number.isSafeInteger(e.fullyReadableFrame)&&out.readableFrame<=e.fullyReadableFrame&&e.fullyReadableFrame<e.holdUntilFrame,'TEXT_READ_DEADLINE');
  }
  return out;
 });
 for(const e of events.filter(e=>e.type==='LABEL')){
  const pin=events.find(pin=>pin.id===e.pinEventId&&pin.type==='PIN'&&pin.locationId===e.locationId);
  assert(pin,'LABEL_PIN_BINDING');assert(e.startFrame>=pin.startFrame&&e.holdUntilFrame<=pin.holdUntilFrame,'LABEL_PIN_ACTIVE_INTERVAL');
 }
 assert(events.filter(e=>['LABEL','METRIC'].includes(e.type)).reduce((n,e)=>n+e.graphemes.filter(g=>!/^\s+$/u.test(g)).length,0)<=256,'TOTAL_GLYPH_RESOURCE_CAPACITY');
 assert(Array.isArray(input.windows)&&input.windows.length>0,'WINDOWS');let cursor=start;const windowIds=new Set();
 const windows=input.windows.map(w=>{object(w,['id','frameRange'],'WINDOW');str(w.id,'WINDOW_ID');assert(!windowIds.has(w.id),'UNIQUE_WINDOW_IDS');windowIds.add(w.id);
  assert(Array.isArray(w.frameRange)&&w.frameRange.length===2&&w.frameRange.every(Number.isSafeInteger)&&w.frameRange[0]===cursor&&w.frameRange[1]>cursor&&w.frameRange[1]<=end&&w.frameRange[1]-cursor<=240,'BOUNDED_CONTIGUOUS_WINDOW');cursor=w.frameRange[1];return clone(w);});
 assert(cursor===end,'INCOMPLETE_WINDOWS');
 return freezeEventData({schema:PROGRAM_SCHEMA,version:1,dataMode:input.dataMode,frameRange:[start,end],fps:input.fps,output:clone(input.output),safeArea,data,events,windows,
  sourceTruth:'INPUT_PROVENANCE_IS_NOT_INDEPENDENT_FACT_VERIFICATION',nativeDrawVerified:false});
}
export function evaluateDirectorProgram(program,globalFrame){
 assert(program?.schema===PROGRAM_SCHEMA,'COMPILED_PROGRAM');integer(globalFrame,'GLOBAL_FRAME',program.frameRange[0]);assert(globalFrame<program.frameRange[1],'GLOBAL_FRAME_OUTSIDE_RANGE');
 const records=[];for(const e of program.events){
  if(globalFrame<e.startFrame||globalFrame>=e.holdUntilFrame)continue;
  const item={...e,globalFrame,role:e.requiredRange&&globalFrame>=e.requiredRange[0]&&globalFrame<e.requiredRange[1]?'REQUIRED_VISIBLE_SAFE':e.role};
  if(e.type==='PIN')item.scale=popScale(globalFrame,e.startFrame,e.popFrames);
  if(['AREA','LINE'].includes(e.type))item.fraction=clamp((globalFrame-e.startFrame)/e.revealFrames);
  if(['LABEL','METRIC'].includes(e.type)){
   let beat=0;item.glyphs=e.graphemes.map(grapheme=>{
    if(/^[\s]+$/u.test(grapheme))return {grapheme,layoutOnly:true,scale:1,opacity:0};
    const startFrame=e.startFrame+(beat++)*e.graphemeIntervalFrames,t=clamp((globalFrame-startFrame)/e.settleFrames),strength=1-(1-t)**3;
    return {grapheme,startFrame,scale:strength,opacity:strength};
   });item.fullyReadable=globalFrame>=e.readableFrame;
  }records.push(item);
 }
 return freezeEventData({globalFrame,timeSeconds:globalFrame/program.fps,records,windowIndependent:true,sourceTruth:program.sourceTruth});
}
export function programWindowFrame(program,windowId,localFrame){
 const window=program.windows.find(w=>w.id===windowId);assert(window,'WINDOW_ID');integer(localFrame,'LOCAL_FRAME');
 assert(localFrame<window.frameRange[1]-window.frameRange[0],'LOCAL_FRAME_OUTSIDE_RANGE');
 return evaluateDirectorProgram(program,window.frameRange[0]+localFrame);
}
