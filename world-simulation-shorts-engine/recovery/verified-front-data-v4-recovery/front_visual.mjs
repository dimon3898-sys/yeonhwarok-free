/** Evidence-selected archival snapshots; no historical interpolation or inferred ownership. */
export const FRONT_RUNTIME_PROFILE='VERIFIED_ARCHIVAL_FRONT_V4';
export const FRONT_PROFILE_SCHEMA='WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4';
const clone=value=>structuredClone(value),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 fail=code=>{throw Error(code);},date=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)
 &&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
function geometry(value){
 if(!value||!['LineString','MultiLineString'].includes(value.type))fail('FRONT_V4_OPEN_LINE_GEOMETRY_REQUIRED');
 const parts=value.type==='LineString'?[value.coordinates]:value.coordinates;
 if(!Array.isArray(parts)||parts.length<1||parts.length>64)fail('FRONT_V4_BOUNDED_LINE_PARTS_REQUIRED');
 let vertices=0;
 for(const part of parts){
  if(!Array.isArray(part)||part.length<2)fail('FRONT_V4_SOURCE_LINE_PART_REQUIRED');vertices+=part.length;
  for(let i=0;i<part.length;i++){
   const p=part[i];if(!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)||p[0]<-180||p[0]>180||p[1]<-90||p[1]>90)
    fail('FRONT_V4_FINITE_GEOGRAPHIC_SOURCE_REQUIRED');
   if(i&&JSON.stringify(p)===JSON.stringify(part[i-1]))fail('FRONT_V4_DUPLICATE_SOURCE_VERTEX');
   if(i&&Math.abs(p[0]-part[i-1][0])>180)fail('FRONT_V4_WRAPPED_SOURCE_UNSUPPORTED');
  }
  if(JSON.stringify(part[0])===JSON.stringify(part.at(-1)))fail('FRONT_V4_CLOSED_BOUNDARY_NOT_ADMITTED');
 }
 if(vertices>8192)fail('FRONT_V4_SOURCE_GEOMETRY_CAPACITY');return clone(value);
}
/** Partition only at existing vertices to respect the unchanged Area/V1 129-vertex contract.
 * Parts/gaps and every source edge remain unchanged. No additional geographic point is made. */
export function sourceLineChunks(value){
 const g=geometry(value),parts=g.type==='LineString'?[g.coordinates]:g.coordinates,result=[];
 parts.forEach((part,partIndex)=>{for(let offset=0;offset<part.length-1;offset+=128)
  result.push({partIndex,vertexStart:offset,vertexEnd:Math.min(offset+128,part.length-1),
   geometry:{type:'LineString',coordinates:clone(part.slice(offset,offset+129))}});});return result;
}
export function normalizeFrontProfile(input,{totalFrames,eventChapters}={}){
 if(input?.schema!==FRONT_PROFILE_SCHEMA||input.runtimeProfile!==FRONT_RUNTIME_PROFILE
  ||!Number.isSafeInteger(totalFrames)||totalFrames<1)fail('FRONT_V4_EXPLICIT_PROFILE_REQUIRED');
 const policy=input.semanticPolicy;
 if(policy?.inferOccupiedAreas!==false||policy.interpolateUnobservedDates!==false||policy.exactMilitaryDemarcationLineClaimed!==false)
  fail('FRONT_V4_NO_INFERRED_HISTORY_POLICY_REQUIRED');
 if(!Array.isArray(input.fronts)||input.fronts.length<1||input.fronts.length>64||!Array.isArray(input.schedule)||input.schedule.length<1)
  fail('FRONT_V4_ACTUAL_SOURCE_AND_SCHEDULE_REQUIRED');
 const ids=new Set(),fronts=input.fronts.map(front=>{
  const s=front?.source;
  if(typeof front?.frontId!=='string'||!front.frontId||ids.has(front.frontId)||!date(front.mapDate))fail('FRONT_V4_UNIQUE_DATED_FRONT_REQUIRED');
  ids.add(front.frontId);
  if(s?.classification!=='OBSERVED_UN_FRONT'||!hex(s.documentSha256)||!hex(s.rasterSha256)
   ||!Number.isSafeInteger(s.pageIndex0)||s.pageIndex0<0||s.registrationMode!=='REFERENCE_CONTROL_AFFINE_APPROXIMATION'
   ||!Number.isFinite(s.registrationResidualMeters)||s.registrationResidualMeters<0
   ||s.cartographicAccuracy!=='UNKNOWN_NOT_CERTIFIED'||s.reviewStatus!=='SOURCE_LINE_AND_TRACE_REVIEWED'
   ||typeof s.reference!=='string'||!s.reference.trim())fail('FRONT_V4_REVIEWED_APPROXIMATE_SOURCE_REQUIRED');
  if(front.partialSegments!==true||front.verifiedSourceExtent!=='PARTIAL_CONTROL_HULL')fail('FRONT_V4_PARTIAL_SOURCE_EXTENT_REQUIRED');
  if(!hex(front.geoJsonSha256)||typeof front.sourceFile!=='string'||!front.sourceFile||front.sourceFile.startsWith('/')
   ||/[\\\0]/.test(front.sourceFile)||front.sourceFile.split('/').some(part=>!part||part==='.'||part==='..'))fail('FRONT_V4_HASH_BOUND_GEOJSON_REQUIRED');
  return{...clone(front),geometry:geometry(front.geometry)};
 });
 let next=0;const schedule=input.schedule.map(row=>{
  if(!Number.isSafeInteger(row.startFrame)||!Number.isSafeInteger(row.endFrame)||row.startFrame<next
   ||row.endFrame<=row.startFrame||row.endFrame>totalFrames||row.mode!=='ARCHIVAL_FRONT_ONLY'||!ids.has(row.frontId)
   ||!date(row.eventDate)||typeof row.sourceLabel!=='string'||!row.sourceLabel.trim())fail('FRONT_V4_EXPLICIT_NONOVERLAPPING_SCHEDULE_REQUIRED');
  if(Array.isArray(eventChapters)&&!eventChapters.some(ch=>row.startFrame>=ch.startFrame&&row.endFrame<=ch.endFrame
   &&(!row.chapterId||row.chapterId===ch.chapterId)))fail('FRONT_V4_SCHEDULE_CHAPTER_BINDING_REQUIRED');
  const front=fronts.find(item=>item.frontId===row.frontId);
  if(front.mapDate>row.eventDate)fail('FRONT_V4_FUTURE_MAP_NOT_EVENT_EVIDENCE');next=row.endFrame;return clone(row);
 });
 return Object.freeze({...clone(input),fronts,schedule,totalFrames});
}
export function selectFrontSnapshot(profile,globalFrame){
 if(profile?.runtimeProfile!==FRONT_RUNTIME_PROFILE||!Number.isSafeInteger(globalFrame)||globalFrame<0||globalFrame>=profile.totalFrames)
  fail('FRONT_V4_GLOBAL_FRAME_REQUIRED');
 const row=profile.schedule.find(item=>globalFrame>=item.startFrame&&globalFrame<item.endFrame);
 if(!row)return{mode:'PRESERVED_SCHEMATIC_CONTEXT',sourceActiveFrame:false,globalFrame,originalV3ClockUnchanged:true};
 const front=profile.fronts.find(item=>item.frontId===row.frontId);
 return{mode:'ARCHIVAL_FRONT_ONLY',sourceActiveFrame:true,globalFrame,frontId:front.frontId,mapDate:front.mapDate,eventDate:row.eventDate,
  sourceLabel:row.sourceLabel,chapterId:row.chapterId??null,sourceFile:front.sourceFile,sourceGeoJsonSha256:front.geoJsonSha256,
  documentSha256:front.source.documentSha256,rasterSha256:front.source.rasterSha256,
  pageIndex0:front.source.pageIndex0,registrationMode:front.source.registrationMode,
  registrationResidualMeters:front.source.registrationResidualMeters,cartographicAccuracy:front.source.cartographicAccuracy,
  partialSegments:true,verifiedSourceExtent:'PARTIAL_CONTROL_HULL',observedUNFront:true,exactOccupiedBoundaryClaimed:false,
  exactMilitaryDemarcationLineClaimed:false,unverifiedSchematicAreaSuppressed:true,areas:0,coordinatesInterpolated:false,
  unobservedHistoricalMovementInvented:false};
}
/** A source-observed front must remain visible when it coincides with a modern
 * country border. This changes only the new source-front pass input: original
 * native boundary drawing/restoration and every marker/text mask remain owned
 * by their existing engines. Schematic fallback keeps its original mask. */
export function selectSourceFrontBoundaryPolicy({sourceActiveFrame,controls,boundarySegments}={}){
 if(typeof sourceActiveFrame!=='boolean'||!Array.isArray(boundarySegments))fail('FRONT_V4_EXPLICIT_BOUNDARY_POLICY_INPUT_REQUIRED');
 if(!sourceActiveFrame)return{policy:'PRESERVED_NATIVE_BOUNDARY_OCCLUSION',boundarySegments,
  nativeBoundaryRestoreUnchanged:true,protectedGraphicMasksUnchanged:true};
 if(!controls||!Array.isArray(controls.areas)||controls.areas.length!==0||!Array.isArray(controls.fronts)||controls.fronts.length===0
  ||(controls.impacts??[]).length||(controls.propagations??[]).length)
  fail('FRONT_V4_SOURCE_FRONT_ONLY_BOUNDARY_PRIORITY_REQUIRED');
 return{policy:'ARCHIVAL_SOURCE_FRONT_ABOVE_STATIC_COUNTRY_BOUNDARY',boundarySegments:[],
  nativeBoundaryRestoreUnchanged:true,protectedGraphicMasksUnchanged:true,
  changedNativeBoundaryPixelsAllowedOnlyWithinActualSourceFrontSupport:true};
}
