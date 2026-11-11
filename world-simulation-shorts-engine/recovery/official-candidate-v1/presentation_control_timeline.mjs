/** Pinned, source-authored vector states for the existing AreaOverlayPass. No inferred dates or geometry interpolation. */
import {AREA_FRAME_V3_VERSION,validateAreaGeometry,compileAreaLinePrimitive} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {compileEventIntent,freezeEventData,validateEventAnchor} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {evaluateGeographicLineReveal} from '../../web/map_infographic_v1/event_line_v1.mjs';
import {validateControlTimelineReference,CONTROL_TIMELINE_MAX_BYTES,canonicalControlTimelineState} from '../../web/map_infographic_v1/control_timeline_contract_v1.mjs';
export {validateControlTimelineReference,CONTROL_TIMELINE_MAX_BYTES};
export const SOURCE_CONTROL_TIMELINE_SCHEMA='WORLD_ENGINE_SOURCE_CONTROL_TIMELINE_V1';
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)
 &&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const assert=(condition,code)=>{if(!condition)throw Error(code);};
const id=value=>typeof value==='string'&&/^[A-Za-z0-9_.:-]{1,128}$/u.test(value);
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/u.test(value);
const text=value=>typeof value==='string'&&value.trim().length>0&&!/[\u0000-\u001f\u007f]/u.test(value);
const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
const exact=(value,keys)=>object(value)&&Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));

/** Canonical JSON for pinned admission receipts; object keys sort, array/source order never changes. */
export function canonicalControlTimelineJSON(value){
 if(Array.isArray(value))return'['+value.map(canonicalControlTimelineJSON).join(',')+']';
 if(object(value))return'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonicalControlTimelineJSON(value[key])).join(',')+'}';
 assert(value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value),
  'CONTROL_TIMELINE_JSON_VALUE_REQUIRED');
 return JSON.stringify(value);
}

function admissionRecord(value){
 assert(object(value),'CONTROL_TIMELINE_ADMISSION_REQUIRED');
 assert(value.sourceType==='OFFICIAL_RETROSPECTIVE_STRATEGIC_MAP'
  &&value.georeferencing==='DERIVED_GRATICULE'&&value.originalCRS==='UNKNOWN'
  &&value.dailyObserved===false&&value.transitionKind==='SOURCE_AUTHORED_VISUAL_TRANSITION',
  'CONTROL_TIMELINE_SOURCE_TRUTH_CONTRACT_REQUIRED');
 assert(value.productionReady===true,'CONTROL_TIMELINE_SOURCE_NOT_ADMITTED');
 assert(sha(value.sourceQualificationReceiptSHA256),'CONTROL_TIMELINE_QUALIFICATION_RECEIPT_SHA256_REQUIRED');
 assert(value.capacityProfile===undefined||value.capacityProfile==='SOURCE_NATIVE_8192','CONTROL_TIMELINE_CAPACITY_PROFILE_INVALID');
 canonicalControlTimelineJSON(value);
 return structuredClone(value);
}

function geometryStructure(geometry,kind,maxCoordinates){
 assert(exact(geometry,['type','coordinates']),'CONTROL_TIMELINE_GEOMETRY_FIELDS_REQUIRED');
 const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.type==='MultiPolygon'?geometry.coordinates:null;
 if(kind==='AREA'){
  let count=0;
  assert(Array.isArray(polygons)&&polygons.length>0,'AREA_POLYGON_OR_MULTIPOLYGON_REQUIRED');
  for(const polygon of polygons){
   assert(Array.isArray(polygon)&&polygon.length>0,'AREA_OUTER_RING_REQUIRED');
   for(const ring of polygon){
    assert(Array.isArray(ring)&&ring.length>=4,'AREA_CLOSED_RING_REQUIRED');
    count+=ring.length;assert(count<=maxCoordinates,'AREA_GEOMETRY_CAPACITY_EXCEEDED');
    for(const point of ring)validateEventAnchor(point,'AREA_RING_VERTEX');
    assert(JSON.stringify(ring[0])===JSON.stringify(ring.at(-1)),'AREA_CLOSED_RING_REQUIRED');
   }
  }
  return count;
 }else{
  assert(geometry.type==='LineString'&&Array.isArray(geometry.coordinates)&&geometry.coordinates.length>=2,
   'EVENT_LINESTRING_REQUIRED');
  // This is the existing Area Core limit. Source preparation must split long fronts explicitly.
  assert(geometry.coordinates.length<=129,'AREA_LINE_CAPACITY_EXCEEDED');
  for(const point of geometry.coordinates)validateEventAnchor(point,'LINE_VERTEX');
  return geometry.coordinates.length;
 }
}

/** Full dense-grid/basic-coordinate checks; full existing topology validation is scoped to the selected inclusive range. */
export function validateSourceControlTimeline(input,{firstFrame=0,lastFrame=input?.totalFrames-1}={}){
 assert(object(input)&&input.schema===SOURCE_CONTROL_TIMELINE_SCHEMA,'CONTROL_TIMELINE_DATASET_SCHEMA_REQUIRED');
 assert(integer(input.totalFrames,2,36000)&&input.fps===30,'CONTROL_TIMELINE_FRAME_GRID_REQUIRED');
 assert(input.crs==='EPSG:4326','CONTROL_TIMELINE_OUTPUT_CRS_REQUIRED');
 assert(id(input.sourceId)&&sha(input.sourceSHA256),'CONTROL_TIMELINE_SOURCE_IDENTITY_REQUIRED');
 const admission=admissionRecord(input.admission),maxCoordinates=admission.capacityProfile==='SOURCE_NATIVE_8192'?8192:4096;
 assert(integer(firstFrame,0,input.totalFrames-1)&&integer(lastFrame,firstFrame,input.totalFrames-1),
  'CONTROL_TIMELINE_SELECTED_FRAME_RANGE');
 assert(Array.isArray(input.frames)&&input.frames.length===input.totalFrames,'CONTROL_TIMELINE_DENSE_FRAME_GRID_REQUIRED');
 const source={source_type:admission.sourceType,source_reference:'sha256:'+input.sourceSHA256,verification_status:'VERIFIED'},
  selected=[],owners=new Set(),geometryCache=new Map();
 let previousSourceFrame=-1,geometryValidations=0,geometryCacheHits=0,maxObservedAreaCoordinates=0,
  maxObservedFrameAreaCoordinates=0,maxFrontCoordinates=0;
 for(let index=0;index<input.frames.length;index++){
  const row=input.frames[index];
  assert(exact(row,['frame','sourceFrame','sourceDateLabel','areas','fronts'])&&row.frame===index,
   'CONTROL_TIMELINE_DENSE_FRAME_GRID_REQUIRED');
  assert(Number.isFinite(row.sourceFrame)&&row.sourceFrame>=previousSourceFrame&&row.sourceFrame>=0,
   'CONTROL_TIMELINE_SOURCE_FRAME_ORDER_REQUIRED');
  previousSourceFrame=row.sourceFrame;
  assert(text(row.sourceDateLabel),'CONTROL_TIMELINE_SOURCE_DATE_LABEL_REQUIRED');
  assert(Array.isArray(row.areas)&&Array.isArray(row.fronts)&&row.areas.length>0,'CONTROL_TIMELINE_STATE_ARRAYS_REQUIRED');
  const areaIds=new Set(),frontIds=new Set(),inRange=index>=firstFrame&&index<=lastFrame,areas=[],fronts=[];
  let frameAreaCoordinates=0;
  for(const area of row.areas){
   assert(exact(area,['id','ownerId','geometry'])&&id(area.id)&&id(area.ownerId),'CONTROL_TIMELINE_AREA_RECORD_REQUIRED');
   assert(!areaIds.has(area.id),'CONTROL_TIMELINE_DUPLICATE_AREA_ID');areaIds.add(area.id);owners.add(area.ownerId);
   const coordinates=geometryStructure(area.geometry,'AREA',maxCoordinates);frameAreaCoordinates+=coordinates;
   maxObservedAreaCoordinates=Math.max(maxObservedAreaCoordinates,coordinates);
   if(inRange){
    const key=JSON.stringify(area.geometry);let geometry=geometryCache.get(key);
    if(geometry){geometryCacheHits++;}else{
     geometry=validateAreaGeometry(area.geometry,{maxCoordinates});geometryCache.set(key,geometry);geometryValidations++;
    }
    areas.push({id:area.id,ownerId:area.ownerId,geometry});
   }
  }
  for(const front of row.fronts){
   assert(exact(front,['id','geometry'])&&id(front.id),'CONTROL_TIMELINE_FRONT_RECORD_REQUIRED');
   assert(!frontIds.has(front.id),'CONTROL_TIMELINE_DUPLICATE_FRONT_ID');frontIds.add(front.id);
   maxFrontCoordinates=Math.max(maxFrontCoordinates,geometryStructure(front.geometry,'FRONT',maxCoordinates));
   if(inRange){
    const intent=compileEventIntent({data_mode:'PRODUCTION',line:{geometry:front.geometry,source,direction:'FORWARD',style_role:'PRIMARY'}});
    fronts.push({id:front.id,geometry:intent.line.geometry});
   }
  }
  maxObservedFrameAreaCoordinates=Math.max(maxObservedFrameAreaCoordinates,frameAreaCoordinates);
  if(inRange)selected.push({frame:row.frame,sourceFrame:row.sourceFrame,sourceDateLabel:row.sourceDateLabel,areas,fronts});
 }
 assert(owners.size>=1&&owners.size<=16,'CONTROL_TIMELINE_OWNER_CAPACITY');
 return freezeEventData({schema:input.schema,totalFrames:input.totalFrames,fps:input.fps,crs:input.crs,
  sourceId:input.sourceId,sourceSHA256:input.sourceSHA256,admission,source,ownerIds:[...owners],frames:selected,
  geometryValidatedFirstFrame:firstFrame,geometryValidatedLastFrame:lastFrame,
  validation:{fullDatasetDenseGrid:true,fullDatasetBasicCoordinates:true,geometryValidations,geometryCacheHits,
   geometryCapacityProfile:admission.capacityProfile??'LEGACY_4096',maxCoordinatesPerArea:maxCoordinates,
   maxObservedAreaCoordinates,maxObservedFrameAreaCoordinates,maxFrontCoordinates,triangleCapacity:16384,
   triangleValidation:'EXISTING_AREA_OVERLAY_PASS_AT_DRAW_PENDING'}});
}

async function digest(bytes,crypto){
 assert(typeof crypto?.subtle?.digest==='function','CONTROL_TIMELINE_WEB_CRYPTO_REQUIRED');
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');
}
export async function controlTimelineStateDigest(frame,{crypto=globalThis.crypto}={}){
 return digest(new TextEncoder().encode(canonicalControlTimelineState(frame)),crypto);
}

async function readBounded(response,expectedBytes){
 const declared=response.headers?.get?.('content-length');
 if(declared!==null&&declared!==undefined){
  assert(/^\d+$/u.test(declared),'CONTROL_TIMELINE_CONTENT_LENGTH_INVALID');
  assert(Number(declared)<=CONTROL_TIMELINE_MAX_BYTES&&Number(declared)<=expectedBytes,'CONTROL_TIMELINE_BYTE_LIMIT');
 }
 assert(typeof response.body?.getReader==='function','CONTROL_TIMELINE_STREAM_BODY_REQUIRED');
 const reader=response.body.getReader(),chunks=[];let size=0;
 try{
  for(;;){const {done,value}=await reader.read();if(done)break;
   assert(value instanceof Uint8Array,'CONTROL_TIMELINE_BYTE_STREAM_REQUIRED');size+=value.byteLength;
   assert(size<=CONTROL_TIMELINE_MAX_BYTES&&size<=expectedBytes,'CONTROL_TIMELINE_BYTE_LIMIT');chunks.push(value);
  }
 }catch(error){try{await reader.cancel();}catch{}throw error;}
 finally{reader.releaseLock();}
 assert(size===expectedBytes,'CONTROL_TIMELINE_BYTE_LENGTH_MISMATCH');
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
 return bytes;
}

/** Loads only the registered same-origin content-addressed path; all byte/source/admission/state pins must agree. */
export async function preloadSourceControlTimeline(reference,{fetch=globalThis.fetch,crypto=globalThis.crypto,
 origin=globalThis.location?.origin}={}){
 const ref=validateControlTimelineReference(reference);
 assert(typeof fetch==='function','CONTROL_TIMELINE_FETCH_REQUIRED');
 assert(typeof origin==='string'&&/^https?:\/\//u.test(origin),'CONTROL_TIMELINE_SAME_ORIGIN_REQUIRED');
 const base=new URL(origin),url=new URL(ref.url,base);
 assert(base.origin===origin&&url.origin===base.origin&&url.pathname===ref.url,'CONTROL_TIMELINE_SAME_ORIGIN_REQUIRED');
 const response=await fetch(url.href,{method:'GET',credentials:'same-origin',redirect:'error',cache:'no-store'});
 assert(response?.ok===true,'CONTROL_TIMELINE_FETCH_FAILED');
 assert(response.redirected!==true&&(!response.url||response.url===url.href),'CONTROL_TIMELINE_REDIRECT_FORBIDDEN');
 const bytes=await readBounded(response,ref.bytes);
 assert(await digest(bytes,crypto)===ref.sha256,'CONTROL_TIMELINE_CONTENT_SHA256_MISMATCH');
 let input;try{input=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
 catch{throw Error('CONTROL_TIMELINE_JSON_INVALID');}
 assert(input.totalFrames===ref.totalFrames&&input.sourceId===ref.sourceId&&input.sourceSHA256===ref.sourceSHA256,
  'CONTROL_TIMELINE_SOURCE_REFERENCE_MISMATCH');
 assert(await digest(new TextEncoder().encode(canonicalControlTimelineJSON(input.admission)),crypto)===ref.admissionSHA256,
  'CONTROL_TIMELINE_ADMISSION_SHA256_MISMATCH');
 assert(await controlTimelineStateDigest(input.frames?.[ref.firstFrame],{crypto})===ref.firstStateSHA256
  &&await controlTimelineStateDigest(input.frames?.[ref.lastFrame],{crypto})===ref.lastStateSHA256,
  'CONTROL_TIMELINE_ENDPOINT_STATE_SHA256_MISMATCH');
 const validated=validateSourceControlTimeline(input,{firstFrame:ref.firstFrame,lastFrame:ref.lastFrame});
 assert([...validated.ownerIds].sort().join('\n')===[...ref.ownerIds].sort().join('\n'),'CONTROL_TIMELINE_OWNER_REFERENCE_MISMATCH');
 // Hash the immutable geographic vertices once per distinct geometry, before any paid renderer can use them.
 // Identity hits avoid re-serializing area geometry already shared by the topology-validation cache.
 const geometryHashes=new Map(),geometryRecords=new WeakMap();
 for(const row of validated.frames)for(const item of [...row.areas,...row.fronts]){
  const geometry=item.geometry;if(geometryRecords.has(geometry))continue;
  const canonical=canonicalControlTimelineJSON(geometry);let geometrySHA256=geometryHashes.get(canonical);
  if(!geometrySHA256){geometrySHA256=await digest(new TextEncoder().encode(canonical),crypto);geometryHashes.set(canonical,geometrySHA256);}
  const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.type==='MultiPolygon'?geometry.coordinates:null,
   geometryCoordinateCount=polygons?polygons.reduce((total,polygon)=>total+polygon.reduce((sum,ring)=>sum+ring.length,0),0):geometry.coordinates.length;
  geometryRecords.set(geometry,{geometrySHA256,geometryCoordinateCount});
 }
 const totalFrames=ref.lastFrame-ref.firstFrame+1;
 function evaluate(frame,{project}={}){
  assert(integer(frame,0,totalFrames-1),'CONTROL_TIMELINE_FRAME_OUT_OF_RANGE');
  assert(project===undefined||typeof project==='function','AREA_EXISTING_PROJECTION_REQUIRED');
  const row=validated.frames[frame],stateId='SOURCE_FRAME_'+row.frame;
  const areas=row.areas.map(area=>({...area,...geometryRecords.get(area.geometry),sourceGeometry:area.geometry,source:validated.source,role:'CONTROL_AREA',
   style_role:'PRIMARY',state_id:stateId,alpha:1,coverage:1,coverageMode:'SUPPLIED_SOURCE_GEOMETRY',
   transform:{translation:[0,0],heading:0},motion:null}));
  const fronts=row.fronts.map(front=>{
   const item={...front,...geometryRecords.get(front.geometry),source:validated.source,direction:'FORWARD',style_role:'PRIMARY',role:'FRONT_LINE'},
    linePrimitive=project?compileAreaLinePrimitive({...item,data_mode:'PRODUCTION'},{project}):null;
   return {...item,state_id:stateId,alpha:1,revealFraction:1,linePrimitive,
    lineReveal:linePrimitive?evaluateGeographicLineReveal(linePrimitive,1):null};
  });
  return freezeEventData({version:AREA_FRAME_V3_VERSION,frame,localFrame:frame,absoluteFrame:row.frame,
   sourceFrame:row.sourceFrame,sourceDateLabel:row.sourceDateLabel,timeSeconds:frame/validated.fps,
   absoluteTimeSeconds:row.frame/validated.fps,state:'STATE_TRANSITION',stateId,timeLabel:row.sourceDateLabel,
   timeLabelVisible:true,areas,fronts,impacts:[],propagations:[],metric:null,hold:false,
   activeFeatures:['STATE_TRANSITION','TIME_STEP',...(fronts.length?['FRONT_LINE']:[])],
   geometryBinding:'SOURCE_AUTHORED_DENSE_VECTOR_STATES',dataMode:'PRODUCTION',productionEligible:true,
   physicalSimulation:false,dailyObserved:false,interpolation:'NONE_RUNTIME_SOURCE_AUTHORED_STATES',
   sourceSHA256:validated.sourceSHA256,sourceQualificationReceiptSHA256:validated.admission.sourceQualificationReceiptSHA256,
   projectionOwnership:'EXISTING_NATIVE',cameraOwnership:'READ_ONLY'});
 }
 return Object.freeze({schema:SOURCE_CONTROL_TIMELINE_SCHEMA,reference:freezeEventData(ref),fps:validated.fps,totalFrames,
  absoluteFirstFrame:ref.firstFrame,absoluteLastFrame:ref.lastFrame,source:validated.source,admission:validated.admission,
  validation:freezeEventData({...validated.validation,geometryValidatedFirstFrame:ref.firstFrame,geometryValidatedLastFrame:ref.lastFrame,
   bytesSHA256Verified:true,sourceIdentityVerified:true,admissionSHA256Verified:true,endpointStateSHA256Verified:true,
   distinctGeometrySHA256Count:geometryHashes.size}),evaluate});
}
