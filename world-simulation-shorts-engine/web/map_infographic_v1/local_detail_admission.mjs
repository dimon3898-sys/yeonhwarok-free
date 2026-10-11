/** Data admission only. No pixels, fabricated precision, or regional overrides. */
export const LOCAL_DETAIL_VERSION = 'LOCAL_DETAIL_ADMISSION_V1';
export const LOCAL_QUALITY_POLICY = Object.freeze({
 maxPixelsPerNativeTexel: 1, maxGeometryErrorPixels: 1,
 requiredCoverageFraction: 1, projection: 'REGIONAL_EQUIRECTANGULAR',
});
export const LOCAL_RENDER_CAPABILITIES = Object.freeze({ eventRepresentations: Object.freeze(['Point']) });
const hash = value => /^[a-f0-9]{64}$/i.test(value ?? '');
const validBounds = b => Array.isArray(b) && b.length === 4 && b.every(Number.isFinite)
 && b[0] < b[2] && b[1] < b[3] && b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;
const contains = (a,b) => validBounds(a) && validBounds(b) && a[0] <= b[0] && a[1] <= b[1] && a[2] >= b[2] && a[3] >= b[3];
const positivePair = a => Array.isArray(a) && a.length === 2 && a.every(v => Number.isFinite(v) && v > 0);
const type = g => g.geometry_type ?? g.geometry?.type;
const coords = g => g.coordinates ?? g.geometry?.coordinates;
const digest = g => g.sha256 ?? g.source_feature_sha256;
const canonical = x => JSON.stringify(x, (_key, v) => v && typeof v === 'object' && !Array.isArray(v)
 ? Object.fromEntries(Object.keys(v).sort().map(k => [k,v[k]])) : v);

export function groundSpacingMeters(latitude, spacing) {
 const p = latitude*Math.PI/180, a = 6378137, e2 = .00669437999014;
 const r = Math.sqrt(1-e2*Math.sin(p)**2), rad = Math.PI/180;
 return [a/r*Math.cos(p)*rad*spacing[0], a*(1-e2)/r**3*rad*spacing[1]];
}
export function projectedTexelDensity(spacing, extent, output) {
 if (!positivePair(spacing) || !validBounds(extent) || !positivePair(output)) return null;
 return [spacing[0]*output[0]/(extent[2]-extent[0]), spacing[1]*output[1]/(extent[3]-extent[1])];
}
export function coverageFraction(bounds, extent) {
 if (!validBounds(bounds) || !validBounds(extent)) return 0;
 const w = Math.max(0, Math.min(bounds[2],extent[2])-Math.max(bounds[0],extent[0]));
 const h = Math.max(0, Math.min(bounds[3],extent[3])-Math.max(bounds[1],extent[1]));
 return w*h/((extent[2]-extent[0])*(extent[3]-extent[1]));
}
/** Native source spacing takes priority over derived/upscaled image dimensions. */
export function terrainDetailDescriptor(asset, metadata = {}) {
 const nativeResolution = asset?.source?.resolution;
 const nativeExtent=asset?.source?.geographicExtent??asset?.source?.bounds??metadata.nativeGeographicExtent;
 const pixelSpacing = asset?.source?.pixelSpacing ?? (positivePair(nativeResolution)&&validBounds(nativeExtent)
  ? [(nativeExtent[2]-nativeExtent[0])/nativeResolution[0],(nativeExtent[3]-nativeExtent[1])/nativeResolution[1]]
  : positivePair(nativeResolution) ? metadata.pixelSpacing : asset?.pixelSpacing ?? metadata.pixelSpacing);
 return { sha256: asset?.sha256, file: asset?.file, url: asset?.url,
  geographicExtent: asset?.bounds ?? metadata.geographicExtent,
  pixelSpacing: pixelSpacing ?? null, nativeSourceSha256: asset?.source?.sha256 ?? asset?.sha256,
  dimensions: asset?.dimensions ?? metadata.dimensions ?? null,
  classification: asset?.classification ?? metadata.classification ?? 'UNKNOWN' };
}
export function heightSourceContract(h) {
 const dims=h?.dimensions, count=positivePair(dims)?dims[0]*dims[1]:null;
 const checks={CRS:h?.CRS==='EPSG:4326',unit:h?.unit==='m',scale:h?.scale===1,offset:h?.offset===0,
  format:/Float32|R32F/.test(h?.format??''),NoData:h?.NoData===null,
  dimensions:positivePair(dims)&&dims.every(n=>Number.isInteger(n)&&n>=2),
  allSamplesValid:count!==null&&h?.validSamples===count,
  byteLength:count!==null&&h?.byteLength===count*4,
  pixelSpacing:positivePair(h?.pixelSpacing),footprint:validBounds(h?.footprint),
  firstSample:Array.isArray(h?.firstSample)&&h.firstSample.length===2&&h.firstSample.every(Number.isFinite),
  orientation:/north-up row-major/.test(h?.orientation??''),sourceHash:hash(h?.sha256)};
 return {valid:Object.values(checks).every(Boolean),checks,
  scope:'Registered source metadata; actual bytes/hash/finite heights and GPU texture capability also checked by the existing Renderer'};
}
function geometryIntersects(g, extent) {
 // Actual vertices/segments, not a dateline-spanning record bbox.
 let found = false;
 const inside = p => p[0]>=extent[0] && p[0]<=extent[2] && p[1]>=extent[1] && p[1]<=extent[3];
 const segment = (a,b) => {
  let lo=0,hi=1;const dx=b[0]-a[0],dy=b[1]-a[1];
  for (const [p,q] of [[-dx,a[0]-extent[0]],[dx,extent[2]-a[0]],[-dy,a[1]-extent[1]],[dy,extent[3]-a[1]]]) {
   if (p===0) { if(q<0)return false; } else {const t=q/p;if(p<0)lo=Math.max(lo,t);else hi=Math.min(hi,t);if(lo>hi)return false;}
  } return true;
 };
 const visit = a => {
  if (!Array.isArray(a) || found) return;
  if (Array.isArray(a[0]) && typeof a[0][0]==='number') {
   found=a.some(inside)||a.some((p,i)=>i>0&&segment(a[i-1],p));
  } else a.forEach(visit);
 };
 visit(coords(g));
 if (!found && ['Polygon','MultiPolygon'].includes(type(g))) {
  const ringContains=(ring,p)=>{
   let inside=false;
   for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
   }return inside;
  };
  const polygons=type(g)==='Polygon'?[coords(g)]:coords(g);
  const probes=[[extent[0],extent[1]],[extent[2],extent[1]],[extent[0],extent[3]],[extent[2],extent[3]],[(extent[0]+extent[2])/2,(extent[1]+extent[3])/2]];
  found=polygons.some(p=>p?.length&&probes.some(q=>ringContains(p[0],q)&&!p.slice(1).some(h=>ringContains(h,q))));
 }
 return found;
}
function verifiedError(g, evidence) {
 // Scale denominator is never converted to invented metre accuracy.
 if (!evidence || evidence.verified!==true || evidence.geometrySha256!==digest(g)
  || !hash(digest(g)) || !evidence.provenance
  || !Number.isFinite(evidence.positionalErrorMeters) || evidence.positionalErrorMeters<0
  || !Number.isFinite(evidence.simplificationErrorMeters) || evidence.simplificationErrorMeters<0) return null;
 return evidence.positionalErrorMeters+evidence.simplificationErrorMeters;
}
function validCoordinates(g) {
 const points=[];
 const visit=a=>{if(Array.isArray(a)&&typeof a[0]==='number')points.push(a);else if(Array.isArray(a))a.forEach(visit);};
 visit(coords(g));
 return points.length>0&&points.every(p=>p.length>=2&&Number.isFinite(p[0])&&Number.isFinite(p[1])
  &&p[0]>=-180&&p[0]<=180&&p[1]>=-90&&p[1]<=90);
}
function relevantGeometry(input) {
 return (input.geometries??[]).filter(g => g.id===input.primary || geometryIntersects(g,input.extent));
}
function binding(input) {
 // Exact canonical data binding, not an authentication signature or invented hash.
 return canonical({ extent:input.extent, output:input.output, anchor:input.anchor,
  terrain:input.terrain, primary:input.primary, geometries:input.geometries,
  eventGeometry:input.eventGeometry, qualityEvidence:input.qualityEvidence,
  requirements:input.requirements, heightSource:input.heightSource,
  policy:LOCAL_QUALITY_POLICY, capabilities:LOCAL_RENDER_CAPABILITIES });
}

export function LocalDetailAdmission(input) {
 const {extent, output=[1080,1920], anchor, terrain, heightSource=null,
  qualityEvidence={}, requirements={}} = input;
 if (!validBounds(extent) || !positivePair(output) || !Array.isArray(anchor)
  || anchor.length!==2 || !anchor.every(Number.isFinite) || anchor[0]<extent[0] || anchor[0]>extent[2]
  || anchor[1]<extent[1] || anchor[1]>extent[3]) throw Error('LOCAL_INVALID_GEOGRAPHIC_CONTRACT');
 const screenSpacing=[(extent[2]-extent[0])/output[0],(extent[3]-extent[1])/output[1]];
 // Worst differential screen scale across the entire viewport, not just anchor.
 const latitudes=[extent[1],extent[3],anchor[1],...(extent[1]<0&&extent[3]>0?[0]:[])];
 const minimumGroundPixel=Math.min(...latitudes.flatMap(lat=>groundSpacingMeters(lat,screenSpacing)));
 const density=projectedTexelDensity(terrain?.pixelSpacing,extent,output);
 const terrainCoverage=coverageFraction(terrain?.geographicExtent,extent);
 const terrainOK=hash(terrain?.sha256)&&hash(terrain?.nativeSourceSha256)&&density
  && Math.max(...density)<=LOCAL_QUALITY_POLICY.maxPixelsPerNativeTexel && contains(terrain.geographicExtent,extent);
 const geographicRecords=relevantGeometry(input);
 const geometry=geographicRecords.map(g=>{
  const errorMeters=verifiedError(g,qualityEvidence[g.id]);
  const errorPixels=errorMeters===null?null:errorMeters/minimumGroundPixel;
  return { id:g.id, sourceSha256:digest(g), cartographicScale:g.scale?.denominator??null,
   geometryScreenErrorPixels:errorPixels, verifiedErrorMeters:errorMeters,
   status:['Polygon','MultiPolygon'].includes(type(g))&&validCoordinates(g)&&errorPixels!==null&&errorPixels<=LOCAL_QUALITY_POLICY.maxGeometryErrorPixels?'SUFFICIENT':'INSUFFICIENT',
   reason:!['Polygon','MultiPolygon'].includes(type(g))?'COUNTRY_POLYGON_REQUIRED':!validCoordinates(g)?'INVALID_GIS_COORDINATES':errorPixels===null?'UNVERIFIED_SOURCE_POSITIONAL_ACCURACY':errorPixels>1?'VISIBLE_GEOMETRY_ERROR':'VERIFIED_METRE_ERROR_BOUND' };
 });
 const gisOK=geometry.length>0&&geometry.some(g=>g.id===input.primary)&&geometry.every(g=>g.status==='SUFFICIENT');
 const event=(input.eventGeometry??[]).map(g=>{
  const e=qualityEvidence[g.id], errorMeters=verifiedError(g,e), errorPixels=errorMeters===null?null:errorMeters/minimumGroundPixel;
  const representation=type(g), supported=LOCAL_RENDER_CAPABILITIES.eventRepresentations.includes(representation);
  const complete=e?.complete===true&&e?.verified===true&&e?.geometrySha256===digest(g);
  const requiredType=!requirements.eventRepresentations?.length||requirements.eventRepresentations.includes(representation);
  // Current pixel pipeline represents verified Point events via the fixed marker.
  const pointAligned=representation!=='Point'||canonical(coords(g))===canonical(anchor);
  return {id:g.id, representation, complete, supportedByPixelPipeline:supported,
   geometryScreenErrorPixels:errorPixels,
   status:validCoordinates(g)&&complete&&requiredType&&supported&&pointAligned&&errorPixels!==null&&errorPixels<=1?'SUFFICIENT':'INSUFFICIENT',
   reason:!complete?'LOCAL_EVENT_COMPLETENESS_UNVERIFIED':!supported?'LOCAL_EVENT_REPRESENTATION_NOT_IMPLEMENTED'
    :!requiredType?'LOCAL_EVENT_REPRESENTATION_REQUIRED':!pointAligned?'LOCAL_EVENT_ANCHOR_MISMATCH'
    :errorPixels===null?'UNVERIFIED_EVENT_POSITIONAL_ACCURACY':errorPixels>1?'VISIBLE_EVENT_GEOMETRY_ERROR':'VERIFIED_LOCAL_EVENT' };
 });
 const eventOK=event.length>0&&event.every(e=>e.status==='SUFFICIENT');
 const demCoverage=coverageFraction(heightSource?.footprint,extent);
 const demDensity=projectedTexelDensity(heightSource?.pixelSpacing,extent,output);
 const demContract=heightSourceContract(heightSource);
 const demOK=demContract.valid&&contains(heightSource?.footprint,extent)&&demDensity&&Math.max(...demDensity)<=1;
 const checks={ terrain:{status:terrainOK?'SUFFICIENT':'INSUFFICIENT',projectedPixelsPerNativeTexel:density,
   coverageFraction:terrainCoverage,source:terrain,groundMetersPerOutputPixelAtAnchor:groundSpacingMeters(anchor[1],screenSpacing)},
  gis:{status:gisOK?'SUFFICIENT':'INSUFFICIENT',records:geometry},
  event:{status:eventOK?'SUFFICIENT':'INSUFFICIENT',records:event},
  dem:{status:demOK?'SUFFICIENT':'INSUFFICIENT',required:requirements.requireRealDEM===true,
   screenCoverageFraction:demCoverage,projectedPixelsPerSample:demDensity,sourceContract:demContract,
   outsideCoverage:'EXISTING_TERRAIN_FALLBACK; no fabricated elevation'},
  coverage:{status:contains(terrain?.geographicExtent,extent)&&(!requirements.requireRealDEM||demOK)?'SUFFICIENT':'INSUFFICIENT'} };
 const missingData=[];
 if(!terrainOK)missingData.push('HIGH_DETAIL_TERRAIN_REQUIRED');
 if(!gisOK)missingData.push('VERIFIED_LOCAL_GIS_ACCURACY_REQUIRED');
 if(geometry.some(g=>g.geometryScreenErrorPixels===null))missingData.push('DETAILED_COASTLINE_REQUIRED');
 if(!eventOK)missingData.push('DETAILED_EVENT_GEOMETRY_REQUIRED');
 if(requirements.requireRealDEM&&!demOK)missingData.push('LOCAL_DEM_COVERAGE_REQUIRED');
 if(heightSource&&!demContract.valid)missingData.push('INVALID_HEIGHT_SOURCE_CONTRACT');
 const admitted=terrainOK&&gisOK&&eventOK&&(!requirements.requireRealDEM||demOK)&&(!heightSource||demContract.valid);
 return {version:LOCAL_DETAIL_VERSION,status:admitted?'LOCAL_ADMITTED':'LOCAL_NOT_ADMITTED',renderLocal:!!admitted,
  category:'DATA_ADMISSION',policy:LOCAL_QUALITY_POLICY,requestedExtent:[...extent],canonicalOutput:[...output],
  checks,missingData, optionalLimitations:!demOK&&!requirements.requireRealDEM?['PARTIAL_OR_MISSING_REAL_DEM; NOT_A_MANDATORY_LOCAL_REQUIREMENT']:[],
  binding:admitted?binding({...input,output}):null};
}

/** Closest certified extent along an anchor-centered, aspect-preserving zoom path. */
export function SafeClosestExtent({approvedExtent, requestedExtent, ...input}) {
 if (!validBounds(approvedExtent)||!validBounds(requestedExtent)) throw Error('SAFE_EXTENT_BOUNDS_REQUIRED');
 const baseline=LocalDetailAdmission({...input,extent:approvedExtent});
 const fallback=reason=>({bounds:[...approvedExtent],scale:'REGIONAL',status:'APPROVED_REGIONAL_FALLBACK',
  closestExtentCertified:false,additionalZoomPermitted:false,reason,
  baselineDataAssessment:baseline.checks,
  warning:'Existing visual approval is preserved; this is not a newly certified closest zoom or LOCAL approval.'});
 if(baseline.checks.gis.status!=='SUFFICIENT')return fallback('UNVERIFIED_GEOMETRY_SCREEN_ERROR; no closer extent can be certified');
 if(baseline.checks.terrain.status!=='SUFFICIENT')return fallback('APPROVED_BASELINE_EXCEEDS_STRICT_NATIVE_TEXEL_POLICY');
 if(input.heightSource&&!baseline.checks.dem.sourceContract.valid)return fallback('INVALID_HEIGHT_SOURCE_CONTRACT');
 if(input.requirements?.requireRealDEM&&baseline.checks.dem.status!=='SUFFICIENT')return fallback('REQUIRED_DEM_COVERAGE_UNAVAILABLE');
 const {anchor,output=[1080,1920],terrain,qualityEvidence={}}=input;
 const half=[(approvedExtent[2]-approvedExtent[0])/2,(approvedExtent[3]-approvedExtent[1])/2];
 const enlarge=Math.max((anchor[0]-approvedExtent[0])/half[0],(approvedExtent[2]-anchor[0])/half[0],
  (anchor[1]-approvedExtent[1])/half[1],(approvedExtent[3]-anchor[1])/half[1]);
 half[0]*=enlarge;half[1]*=enlarge;
 const desired=Math.max((requestedExtent[2]-requestedExtent[0])/(2*half[0]),(requestedExtent[3]-requestedExtent[1])/(2*half[1]));
 const requiredGeometry=baseline.checks.gis.records;
 let scale=Math.max(desired,terrain.pixelSpacing[0]*output[0]/(2*half[0]),terrain.pixelSpacing[1]*output[1]/(2*half[1]));
 for(const g of requiredGeometry){const error=verifiedError(input.geometries.find(r=>r.id===g.id),qualityEvidence[g.id]);
  scale=Math.max(scale,error/Math.min(...groundSpacingMeters(anchor[1],[2*half[0]/output[0],2*half[1]/output[1]])));}
 if(input.requirements?.requireRealDEM){const p=input.heightSource.pixelSpacing;scale=Math.max(scale,p[0]*output[0]/(2*half[0]),p[1]*output[1]/(2*half[1]));}
 const at=s=>[anchor[0]-half[0]*s,anchor[1]-half[1]*s,anchor[0]+half[0]*s,anchor[1]+half[1]*s];
 // Recheck worst-latitude error and coverage. Unknown inputs never gain accuracy by zoom.
 for(let i=0;i<64&&scale<=1;i++){
  const bounds=at(scale),assessment=LocalDetailAdmission({...input,extent:bounds});
  if(assessment.checks.terrain.status==='SUFFICIENT'&&assessment.checks.gis.status==='SUFFICIENT'
    &&assessment.checks.coverage.status==='SUFFICIENT')return {bounds,scale:'REGIONAL',status:'DATA_CERTIFIED_REGIONAL_EXTENT',
     closestExtentCertified:true,additionalZoomPermitted:scale<1,zoomFactor:1/scale,solverRelativeExtentTolerance:.01,
     reason:'Native raster density, verified metre geometry bounds and source coverage',assessment:assessment.checks};
  scale*=1.01;
 }
 return fallback('NO_CERTIFIABLE_ANCHOR_CENTERED_EXTENT_INSIDE_SOURCE_COVERAGE');
}

export class LocalDetailAdmissionError extends Error {
 constructor(reason){super(reason);this.name='LocalDetailAdmissionError';this.code='LOCAL_NOT_ADMITTED';this.category='DATA_ADMISSION';}
}
/** Fail closed at the real factory, before WebGL creation or asset loading. */
export function assertLocalDetailAdmission(plan, heightSource) {
 if(plan.scale?.name!=='LOCAL')return;
 if(plan.framing?.projection!==LOCAL_QUALITY_POLICY.projection
  ||canonical(plan.scale.canonicalOutput)!==canonical([1080,1920]))throw new LocalDetailAdmissionError('LOCAL projection/canonical output contract mismatch');
 const saved=plan.localDetail?.admission,context=plan.localDetail?.context;
 if(saved?.status!=='LOCAL_ADMITTED'||!saved.renderLocal||!context)throw new LocalDetailAdmissionError('LOCAL admission evidence required');
 const live={...context,extent:plan.framing.bounds,output:plan.scale.canonicalOutput,anchor:plan.anchor.coordinates,
  primary:plan.primary,geometries:plan.geometries,
  terrain:terrainDetailDescriptor(plan.assets.terrain,context.terrainMetadata),heightSource};
 const result=LocalDetailAdmission(live);
 if(!result.renderLocal||result.binding!==saved.binding)throw new LocalDetailAdmissionError('LOCAL data/extent evidence is stale or insufficient');
}
