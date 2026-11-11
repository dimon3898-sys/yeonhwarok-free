/** Portable references to separately pinned source-control data. No source admission is granted here. */
export const CONTROL_TIMELINE_REF_SCHEMA='WORLD_ENGINE_SOURCE_CONTROL_TIMELINE_REF_V1';
export const CONTROL_TIMELINE_MAX_BYTES=32*1024*1024;
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)
 &&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/u.test(value);
const id=value=>typeof value==='string'&&/^[A-Za-z0-9_.:-]{1,128}$/u.test(value);
const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
const assert=(condition,code)=>{if(!condition)throw Error(code);};
const fields=['schema','url','sha256','bytes','firstFrame','lastFrame','totalFrames','ownerIds',
 'sourceId','sourceSHA256','admissionSHA256','firstStateSHA256','lastStateSHA256'];

/** Structure and identity only. The existing registry and fetched bytes remain independent gates. */
export function validateControlTimelineReference(ref){
 assert(object(ref)&&Object.keys(ref).length===fields.length&&fields.every(key=>Object.hasOwn(ref,key)),
  'CONTROL_TIMELINE_REFERENCE_FIELDS_REQUIRED');
 assert(ref.schema===CONTROL_TIMELINE_REF_SCHEMA,'CONTROL_TIMELINE_REFERENCE_SCHEMA_REQUIRED');
 for(const key of ['sha256','sourceSHA256','admissionSHA256','firstStateSHA256','lastStateSHA256'])
  assert(sha(ref[key]),'CONTROL_TIMELINE_REFERENCE_SHA256_REQUIRED');
 assert(ref.url==='/qualified-control/'+ref.sha256+'.json','CONTROL_TIMELINE_REGISTERED_RELATIVE_URL_REQUIRED');
 assert(integer(ref.bytes,1,CONTROL_TIMELINE_MAX_BYTES),'CONTROL_TIMELINE_REFERENCE_BYTE_LIMIT');
 assert(integer(ref.totalFrames,2,36000)&&integer(ref.firstFrame,0,ref.totalFrames-1)
  &&integer(ref.lastFrame,ref.firstFrame,ref.totalFrames-1),'CONTROL_TIMELINE_REFERENCE_FRAME_RANGE');
 assert(id(ref.sourceId),'CONTROL_TIMELINE_REFERENCE_SOURCE_ID_REQUIRED');
 assert(Array.isArray(ref.ownerIds)&&ref.ownerIds.length>=1&&ref.ownerIds.length<=16
  &&ref.ownerIds.every(id)&&new Set(ref.ownerIds).size===ref.ownerIds.length,'CONTROL_TIMELINE_REFERENCE_OWNER_IDS_REQUIRED');
 return structuredClone(ref);
}

/** Sorted object keys, original array/paint order and JSON numeric spelling; frame/date are not state geometry. */
export function canonicalControlTimelineState(frame){
 assert(object(frame)&&Array.isArray(frame.areas)&&Array.isArray(frame.fronts),'CONTROL_TIMELINE_STATE_ARRAYS_REQUIRED');
 function canonical(value){
  if(Array.isArray(value))return'['+value.map(canonical).join(',')+']';
  if(object(value))return'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
  assert(value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value),
   'CONTROL_TIMELINE_STATE_JSON_VALUE_REQUIRED');
  return JSON.stringify(value);
 }
 return canonical({areas:frame.areas,fronts:frame.fronts});
}
