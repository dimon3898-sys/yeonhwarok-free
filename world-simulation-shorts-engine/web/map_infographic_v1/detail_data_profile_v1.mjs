/** Data-only detail proposals and strict quality audits. No Camera or pixels. */
import {LOCAL_QUALITY_POLICY, LocalDetailAdmission, SafeClosestExtent,
 groundSpacingMeters, projectedTexelDensity, coverageFraction, heightSourceContract} from './local_detail_admission.mjs';
import {chooseRelatedMetricPlacement} from './event_layout_adapter_v1.mjs';

export const DETAIL_DATA_PROFILE_V1_VERSION = 'DETAIL_DATA_PROFILE_V1';
export const DETAIL_QUALITY_AUDIT_V1_VERSION = 'DETAIL_QUALITY_AUDIT_V1';
export const SAFE_DETAIL_EXTENT_V1_VERSION = 'SAFE_DETAIL_EXTENT_V1';
export const DETAIL_DATA_QUALITY_POLICY = LOCAL_QUALITY_POLICY;
const digest = value => /^[a-f0-9]{64}$/i.test(value ?? '');
const positivePair = value => Array.isArray(value) && value.length === 2 && value.every(v => Number.isFinite(v) && v > 0);
const finitePoint = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const validBounds = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const geographicBounds = value => validBounds(value) && value[0] >= -180 && value[2] <= 180 && value[1] >= -90 && value[3] <= 90;
const contains = (outer, inner) => validBounds(outer) && Array.isArray(inner) && inner.length===4 && inner.every(Number.isFinite)
 && inner[0]<=inner[2] && inner[1]<=inner[3] && inner[0] >= outer[0]
 && inner[1] >= outer[1] && inner[2] <= outer[2] && inner[3] <= outer[3];
const inside = (point, box) => finitePoint(point) && point[0] >= box[0] && point[0] <= box[2] && point[1] >= box[1] && point[1] <= box[3];
const overlaps = (a,b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const canonical = value => JSON.stringify(value, (_key,v) => v && typeof v === 'object' && !Array.isArray(v)
 ? Object.fromEntries(Object.keys(v).sort().map(key => [key,v[key]])) : v);
const same = (a,b) => canonical(a) === canonical(b);
const freeze = value => {
 if (value && typeof value === 'object' && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); }
 return value;
};
const clone = value => structuredClone(value);
const geometry = record => record?.geometry ?? record;
function lineGeometry(record) {
 const g = geometry(record);
 if (g?.type !== 'LineString' || !Array.isArray(g.coordinates) || g.coordinates.length < 2
  || !g.coordinates.every(p => finitePoint(p) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90))
  throw Error('DETAIL_FULL_SOURCE_LINESTRING_REQUIRED');
 const total = g.coordinates.slice(1).reduce((sum,p,index) => sum + Math.hypot(p[0]-g.coordinates[index][0],p[1]-g.coordinates[index][1]),0);
 if (!(total > 0)) throw Error('DETAIL_NONZERO_SOURCE_GEOMETRY_REQUIRED');
 return g;
}
function pointBounds(points) {
 return [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])),
  Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
}
const project = (point,bounds,output) => [(point[0]-bounds[0])/(bounds[2]-bounds[0])*output[0],
 (bounds[3]-point[1])/(bounds[3]-bounds[1])*output[1]];

/** Proposal only: every projected point comes from an unchanged source vertex. */
export function generateDetailExtentCandidates({eventGeometry,eventAnchor,currentBounds,output=[1080,1920],
 safeArea,desiredScreenCoverageRange=[.2,.35,.5],linePaddingPixels=5.75} = {}) {
 const source = lineGeometry(eventGeometry);
 if (!geographicBounds(currentBounds) || !positivePair(output) || !validBounds(safeArea)
  || !contains([0,0,...output],safeArea) || !finitePoint(eventAnchor)
  || Math.abs(eventAnchor[0]) > 180 || Math.abs(eventAnchor[1]) > 90) throw Error('DETAIL_GEOGRAPHIC_SCREEN_CONTRACT_REQUIRED');
 if (!Array.isArray(desiredScreenCoverageRange) || !desiredScreenCoverageRange.length
  || !desiredScreenCoverageRange.every(v => Number.isFinite(v) && v > 0 && v < 1)
  || !Number.isFinite(linePaddingPixels) || linePaddingPixels <= 0) throw Error('DETAIL_READABILITY_REQUEST_REQUIRED');
 const safeWidth=safeArea[2]-safeArea[0], safeHeight=safeArea[3]-safeArea[1];
 const inner=[safeArea[0]+linePaddingPixels,safeArea[1]+linePaddingPixels,
  safeArea[2]-linePaddingPixels,safeArea[3]-linePaddingPixels];
 if (!validBounds(inner)) throw Error('DETAIL_LINE_HALO_EXCEEDS_SAFE_AREA');
 const requests=[...new Set(desiredScreenCoverageRange)].sort((a,b)=>a-b), raw=pointBounds(source.coordinates);
 const fit=pointBounds([...source.coordinates,eventAnchor]), originalWidth=currentBounds[2]-currentBounds[0],
  originalHeight=currentBounds[3]-currentBounds[1], aspect=originalWidth/originalHeight;
 const fitHeight=Math.max((fit[2]-fit[0])*output[0]/((inner[2]-inner[0])*aspect),
  (fit[3]-fit[1])*output[1]/(inner[3]-inner[1]));
 const geometryBinding=canonical(source), candidates=[];
 function add(bounds,requestedCoverage,id) {
  const points=source.coordinates.map(p=>project(p,bounds,output)), box=pointBounds(points),
   axisCoverage=[(box[2]-box[0])/safeWidth,(box[3]-box[1])/safeHeight],
   halo=[box[0]-linePaddingPixels,box[1]-linePaddingPixels,box[2]+linePaddingPixels,box[3]+linePaddingPixels];
  const projectedLengthPixels=points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p[0]-points[i][0],p[1]-points[i][1]),0);
  candidates.push({id,bounds:[...bounds],center:[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2],
   widthDegrees:bounds[2]-bounds[0],heightDegrees:bounds[3]-bounds[1],currentBounds:[...currentBounds],output:[...output],
   safeArea:[...safeArea],linePaddingPixels,eventAnchor:[...eventAnchor],geometryBinding,
   sourceCoordinateCount:source.coordinates.length,projectedCoordinates:points,projectedGeometryBounds:box,projectedHaloBounds:halo,
   projectedLengthPixels,axisCoverage,screenCoverage:Math.max(...axisCoverage),
   requestedCoverage,readabilityMinimum:requests[0],desiredScreenCoverageRange:requests,
   zoomFactor:originalHeight/(bounds[3]-bounds[1]),wholeGeometryVisible:contains(safeArea,halo),
   anchorVisible:inside(project(eventAnchor,bounds,output),inner),
   geographicBoundsValid:geographicBounds(bounds),projection:LOCAL_QUALITY_POLICY.projection,
   derivation:id==='D0'?'CURRENT_REGIONAL_EXTENT':'FULL_SOURCE_BOUNDS_SAFE_AREA_AFFINE_FIT'});
 }
 add(currentBounds,null,'D0');
 if (candidates[0].screenCoverage < requests[0] || !candidates[0].wholeGeometryVisible || !candidates[0].anchorVisible) {
  const proposed=[];
  for (const coverage of requests) {
   const height=Math.max(fitHeight,(raw[2]-raw[0])*output[0]/(aspect*safeWidth*coverage),
    (raw[3]-raw[1])*output[1]/(safeHeight*coverage));
   if (height >= originalHeight) continue;
   const width=height*aspect, x=(fit[0]+fit[2])/2, y=(fit[1]+fit[3])/2,
    safeX=(inner[0]+inner[2])/2, safeY=(inner[1]+inner[3])/2,
    west=x-safeX/output[0]*width, north=y+safeY/output[1]*height,
    bounds=[west,north-height,west+width,north];
   if (!proposed.some(row=>same(row.bounds,bounds))) proposed.push({bounds,coverage,height});
  }
  proposed.sort((a,b)=>b.height-a.height).forEach((row,i)=>add(row.bounds,row.coverage,'D'+(i+1)));
 }
 return freeze(candidates);
}

function segmentBoxInterval(a,b,box) {
 let lo=0,hi=1;
 for(let axis=0;axis<2;axis++) {
  const d=b[axis]-a[axis];
  if(d===0) { if(a[axis]<box[axis]||a[axis]>box[axis+2])return null; }
  else { const x=(box[axis]-a[axis])/d,y=(box[axis+2]-a[axis])/d;lo=Math.max(lo,Math.min(x,y));hi=Math.min(hi,Math.max(x,y));if(lo>hi)return null; }
 }
 return [lo,hi];
}
function ringContains(ring,p) {
 let yes=false;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
  const a=ring[i],b=ring[j];
  if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;
 }
 return yes;
}
function relevantRecord(record,bounds,primary) {
 if(record?.id===primary)return true;
 const g=record.geometry??{type:record.geometry_type,coordinates:record.coordinates};
 const polygons=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[];
 if(!Array.isArray(polygons))return true;
 for(const polygon of polygons) {
  if(!Array.isArray(polygon))return true;
  for(const ring of polygon) {
   if(!Array.isArray(ring))return true;
   if(ring.some(p=>!finitePoint(p)))return true;
   if(ring.some(p=>inside(p,bounds))||ring.slice(1).some((p,i)=>segmentBoxInterval(ring[i],p,bounds)))return true;
  }
  const probes=[[bounds[0],bounds[1]],[bounds[2],bounds[3]],[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2]];
  if(probes.some(p=>ringContains(polygon[0],p)&&!polygon.slice(1).some(ring=>ringContains(ring,p))))return true;
 }
 return false;
}
const finiteError = value => Number.isFinite(value) && value >= 0;
const text = value => typeof value==='string' && value.trim().length>0;
const url = value => text(value) && /^https?:\/\//.test(value);
function minimumGroundPixel(candidate) {
 const b=candidate.bounds, spacing=[(b[2]-b[0])/candidate.output[0],(b[3]-b[1])/candidate.output[1]],
  latitudes=[b[1],b[3],candidate.eventAnchor[1],...(b[1]<0&&b[3]>0?[0]:[])];
 return Math.min(...latitudes.flatMap(lat=>groundSpacingMeters(lat,spacing)));
}
function segmentDistanceToBox(a,b,box) {
 if(segmentBoxInterval(a,b,box))return 0;
 let result=Infinity;
 for(const point of [a,b])result=Math.min(result,Math.hypot(point[0]-Math.max(box[0],Math.min(box[2],point[0])),
  point[1]-Math.max(box[1],Math.min(box[3],point[1]))));
 const dx=b[0]-a[0],dy=b[1]-a[1],den=dx*dx+dy*dy;
 for(const p of [[box[0],box[1]],[box[2],box[1]],[box[0],box[3]],[box[2],box[3]]]) {
  const t=den===0?0:Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den));
  result=Math.min(result,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));
 }
 return result;
}

/** Unknown evidence is DATA_LIMITED. A measured violation is NOT_ADMITTED. */
export function auditDetailExtent({candidate,profile} = {}) {
 if(!candidate||!profile||!geographicBounds(candidate.bounds)||!positivePair(candidate.output)||!validBounds(candidate.safeArea))
  throw Error('DETAIL_CANDIDATE_PROFILE_REQUIRED');
 const checks=[], missing=[], violations=[];
 function check(name,state,metrics={}) {
  if(!['PASS','DATA_LIMITED','FAIL'].includes(state))throw Error('DETAIL_AUDIT_STATE_REQUIRED');
  checks.push({name,status:state,...metrics});if(state==='DATA_LIMITED')missing.push(name);if(state==='FAIL')violations.push(name);
 }
 const sources=Array.isArray(profile.sources)?profile.sources:[], sourceById=new Map(sources.map(source=>[source.id,source])),
  verifiedSources=new Set();
 check('PROFILE_VERSION',profile.version===DETAIL_DATA_PROFILE_V1_VERSION?'PASS':'DATA_LIMITED');
 const synthetic=profile.evidenceKind==='SYNTHETIC_TEST_ONLY'||profile.dataMode==='SYNTHETIC_TEST',
  production=profile.dataMode==='VERIFIED_PRODUCTION'&&profile.evidenceKind==='VERIFIED_PRODUCTION';
 check('PROFILE_EVIDENCE_MODE',synthetic||production?'PASS':'DATA_LIMITED',
  {synthetic,explicitVerifiedProduction:production,productionEligible:production&&!synthetic});
 check('STRICT_IMPORTED_POLICY',profile.policy&&!same(profile.policy,LOCAL_QUALITY_POLICY)?'FAIL':'PASS',{policy:clone(LOCAL_QUALITY_POLICY)});
 check('CANONICAL_PROJECTION',candidate.projection===LOCAL_QUALITY_POLICY.projection?'PASS':'FAIL');
 check('CANONICAL_SCREEN',contains([0,0,...candidate.output],candidate.safeArea)&&same(candidate.output,[1080,1920])?'PASS':'FAIL');
 check('FINITE_LINE_HALO',Number.isFinite(candidate.linePaddingPixels)&&candidate.linePaddingPixels>0
  && validBounds(candidate.projectedHaloBounds)?'PASS':'FAIL');
 const anchorInner=[candidate.safeArea[0]+candidate.linePaddingPixels,candidate.safeArea[1]+candidate.linePaddingPixels,
  candidate.safeArea[2]-candidate.linePaddingPixels,candidate.safeArea[3]-candidate.linePaddingPixels];
 check('PROJECTED_ANCHOR_BINDING',finitePoint(candidate.eventAnchor)&&candidate.anchorVisible
  ===inside(project(candidate.eventAnchor,candidate.bounds,candidate.output),anchorInner)?'PASS':'FAIL');
 for(const source of sources) {
  const name='SOURCE_'+String(source.id??'UNIDENTIFIED');
  const metadata=text(source.id)&&text(source.role)&&text(source.source)&&text(source.version)&&text(source.retrievalDate)
   && Number.isFinite(Date.parse(source.retrievalDate))&&text(source.license)&&url(source.originalUrl)
   && digest(source.sha256)&&text(source.CRS)&&geographicBounds(source.extent);
  const verified=source.payloadVerified===true&&source.verification?.verified===true
   && Number.isSafeInteger(source.verification?.byteLength)&&source.verification.byteLength>0;
  if(verified&&source.verification.sha256!==source.sha256)check(name,'FAIL',{reason:'VERIFIED_PAYLOAD_HASH_MISMATCH'});
  else if(!metadata||!verified)check(name,'DATA_LIMITED',{reason:'ORIGINAL_PAYLOAD_AND_PROVENANCE_REQUIRED',role:source.role??null});
  else { verifiedSources.add(source.id);check(name,'PASS',{sha256:source.sha256,role:source.role}); }
 }
 if(!sources.length)check('ORIGINAL_PAYLOADS','DATA_LIMITED',{verifiedPayloadCount:0});
 const terrain=profile.terrain, terrainSource=sourceById.get(terrain?.sourceId), sourceSpacing=terrainSource?.nativePixelSpacing;
 let terrainDensity=null;
 if(!terrain||!terrainSource||!verifiedSources.has(terrain.sourceId)||!positivePair(sourceSpacing)
  || terrainSource.CRS!=='EPSG:4326')check('TERRAIN_NATIVE_DENSITY','DATA_LIMITED',{reason:'VERIFIED_SOURCE_NATIVE_GEOGRAPHIC_GRID_REQUIRED',density:null});
 else {
  const spacing=positivePair(terrain.pixelSpacing)?terrain.pixelSpacing:sourceSpacing;
  terrainDensity=projectedTexelDensity(sourceSpacing,candidate.bounds,candidate.output);
  const identity=digest(terrain.sha256)&&terrain.nativeSourceSha256===terrainSource.sha256&&terrainSource.role==='TERRAIN';
  const upscaled=spacing.some((v,i)=>v<sourceSpacing[i]-Number.EPSILON*Math.max(1,sourceSpacing[i]));
  const derivative=terrain.sha256!==terrainSource.sha256;
  const derivativeOK=!derivative||(terrain.verification?.verified===true&&terrain.verification.sha256===terrain.sha256
   && terrain.buildRecipe?.verified===true&&terrain.buildRecipe?.noUpscale===true
   && Array.isArray(terrain.buildRecipe.inputSha256s)&&terrain.buildRecipe.inputSha256s.includes(terrainSource.sha256)
   && text(terrain.buildRecipe.method));
  const state=!identity||upscaled?'FAIL':!derivativeOK?'DATA_LIMITED':Math.max(...terrainDensity)>LOCAL_QUALITY_POLICY.maxPixelsPerNativeTexel?'FAIL':'PASS';
  check('TERRAIN_NATIVE_DENSITY',state,{density:terrainDensity,nativePixelSpacing:sourceSpacing,
   derivativePixelSpacing:spacing,artificialUpscale:upscaled,reason:!identity?'NATIVE_SOURCE_HASH_BINDING_REQUIRED':upscaled?'ARTIFICIAL_GRID_UPSCALE':!derivativeOK?'VERIFIED_DERIVATIVE_RECIPE_REQUIRED':'STRICT_NATIVE_GRID_DENSITY'});
 }
 const terrainExtent=terrain?.geographicExtent;
 check('TERRAIN_COVERAGE',!geographicBounds(terrainExtent)||!geographicBounds(terrainSource?.extent)?'DATA_LIMITED'
  :contains(terrainExtent,candidate.bounds)&&contains(terrainSource.extent,candidate.bounds)?'PASS':'FAIL',
  {coverageFraction:coverageFraction(terrainExtent,candidate.bounds)});
 const compatibility=profile.rendererCompatibility, baselines=profile.baselines??{};
 const rendererBound=compatibility?.verified===true&&digest(baselines.rendererSha256)&&digest(baselines.linePassSha256)
  && digest(compatibility.rendererSha256)&&digest(compatibility.linePassSha256);
 check('UNCHANGED_RENDERER_COMPATIBILITY',!rendererBound?'DATA_LIMITED':compatibility.rendererSha256!==baselines.rendererSha256
  || compatibility.linePassSha256!==baselines.linePassSha256?'FAIL':compatibility.terrainTreatment!=='BAKED_RELIEF_V1'
  || compatibility.terrainClassification!=='BAKED HILLSHADE'||terrain?.classification!=='BAKED HILLSHADE'
  || (terrain?.sha256===terrainSource?.sha256&&terrainSource?.classification!=='BAKED HILLSHADE')?'FAIL':'PASS');
 const metresPerPixel=minimumGroundPixel(candidate), evidence=profile.qualityEvidence??{},
  records=(profile.geometries??[]).filter(record=>relevantRecord(record,candidate.bounds,profile.primary));
 if(!text(profile.primary)||!records.some(record=>record.id===profile.primary))check('PRIMARY_GIS_REQUIRED','DATA_LIMITED');
 function geometryQuality(record,name,{complete=false}={}) {
  const item=evidence[record?.id], source=sourceById.get(record?.sourceId), g=geometry(record);
  const hash=record?.sha256??record?.source_feature_sha256;
  if(item?.verified===true&&item.geometrySha256!==hash) {check(name,'FAIL',{reason:'STALE_GEOMETRY_HASH_BINDING'});return;}
  if(item?.verified===true&&source&&item.sourceSha256!==source.sha256) {check(name,'FAIL',{reason:'STALE_ORIGINAL_SOURCE_HASH_BINDING'});return;}
  if(source&&source.role!==(complete?'CANAL':'GIS')) {check(name,'FAIL',{reason:'SOURCE_ROLE_MISMATCH'});return;}
  const coordinates=[];const collect=a=>{if(Array.isArray(a)&&typeof a[0]==='number')coordinates.push(a);else if(Array.isArray(a))a.forEach(collect);};
  collect(g?.coordinates??record?.coordinates);
  if(!coordinates.length||!coordinates.every(p=>finitePoint(p)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90)) {
   check(name,'FAIL',{reason:'INVALID_GIS_COORDINATES'});return;
  }
  if(!digest(hash)||!source||!verifiedSources.has(source.id)||item?.verified!==true||!text(item.provenance)
   || !finiteError(item.positionalErrorMeters)||!finiteError(item.simplificationErrorMeters)
   || (complete&&item.complete!==true)) {check(name,'DATA_LIMITED',{reason:'HASH_BOUND_VERIFIED_METRE_ERROR_REQUIRED',geometryErrorPixels:null});return;}
  if(!geographicBounds(item.auditExtent)||!contains(item.auditExtent,candidate.bounds)) {
   check(name,geographicBounds(item.auditExtent)?'FAIL':'DATA_LIMITED',{reason:'QUALITY_EVIDENCE_DOES_NOT_COVER_VIEWPORT'});return;
  }
  const errorMeters=item.positionalErrorMeters+item.simplificationErrorMeters, errorPixels=errorMeters/metresPerPixel;
  check(name,errorPixels<=LOCAL_QUALITY_POLICY.maxGeometryErrorPixels?'PASS':'FAIL',{geometrySha256:hash,
   verifiedErrorMeters:errorMeters,geometryErrorPixels:errorPixels,minimumGroundMetersPerOutputPixel:metresPerPixel});
 }
 for(const record of records) {
  const type=record.geometry?.type??record.geometry_type;
  if(!['Polygon','MultiPolygon'].includes(type))check('GIS_'+record.id,'FAIL',{reason:'COUNTRY_POLYGON_REQUIRED'});
  else geometryQuality(record,'GIS_'+record.id);
 }
 if(!records.length)check('GIS_PAYLOADS','DATA_LIMITED');
 let event=null;
 try {event=lineGeometry(profile.eventGeometry);} catch {check('FULL_EVENT_GEOMETRY','DATA_LIMITED',{reason:'ORIGINAL_LINESTRING_REQUIRED'});}
 if(event) {
  const currentBinding=canonical(event);
  check('FULL_EVENT_GEOMETRY',!text(baselines.eventGeometryBinding)?'DATA_LIMITED'
   :currentBinding!==candidate.geometryBinding||currentBinding!==baselines.eventGeometryBinding?'FAIL':'PASS',
   {sourceCoordinateCount:event.coordinates.length,projectedLengthPixels:candidate.projectedLengthPixels});
  const projected=event.coordinates.map(point=>project(point,candidate.bounds,candidate.output)), box=pointBounds(projected),
   length=projected.slice(1).reduce((sum,p,index)=>sum+Math.hypot(p[0]-projected[index][0],p[1]-projected[index][1]),0),
   coverage=[(box[2]-box[0])/(candidate.safeArea[2]-candidate.safeArea[0]),(box[3]-box[1])/(candidate.safeArea[3]-candidate.safeArea[1])],
   halo=[box[0]-candidate.linePaddingPixels,box[1]-candidate.linePaddingPixels,box[2]+candidate.linePaddingPixels,box[3]+candidate.linePaddingPixels];
  check('PROJECTED_GEOMETRY_BINDING',same(projected,candidate.projectedCoordinates)&&same(box,candidate.projectedGeometryBounds)
   && length===candidate.projectedLengthPixels&&same(coverage,candidate.axisCoverage)&&Math.max(...coverage)===candidate.screenCoverage
   && same(halo,candidate.projectedHaloBounds)&&candidate.wholeGeometryVisible===contains(candidate.safeArea,halo)
   && candidate.sourceCoordinateCount===event.coordinates.length?'PASS':'FAIL');
  geometryQuality(profile.eventGeometry,'CANAL_POSITIONAL_ACCURACY',{complete:true});
  check('VERIFIED_V2_LINE_REPRESENTATION',compatibility?.verified!==true||!Array.isArray(compatibility.eventRepresentations)
   || !Number.isSafeInteger(compatibility.maximumLineSegments)?'DATA_LIMITED'
   :!compatibility.eventRepresentations.includes('LineString')||compatibility.maximumLineSegments>128
    || event.coordinates.length-1>compatibility.maximumLineSegments?'FAIL':'PASS',
   {representation:'LineString',segments:event.coordinates.length-1,legacyLocalPointOnly:true});
 }
 check('WHOLE_EVENT_SAFE_AREA',candidate.wholeGeometryVisible===true&&candidate.anchorVisible===true?'PASS':'FAIL',
  {axisCoverage:candidate.axisCoverage,screenCoverage:candidate.screenCoverage,cropped:candidate.wholeGeometryVisible!==true});
 const coast=profile.coastAlignmentEvidence, relevantHashes=records.map(record=>record.sha256??record.source_feature_sha256).sort(),
  reference=sources.find(source=>source.sha256===coast?.referenceSourceSha256&&verifiedSources.has(source.id));
 if(coast?.verified===true&&(coast.terrainSha256!==terrain?.sha256||!same([...coast.gisGeometrySha256s??[]].sort(),relevantHashes)))
  check('COAST_ALIGNMENT','FAIL',{reason:'STALE_COAST_ALIGNMENT_BINDING'});
 else if(coast?.verified!==true||!reference||!text(coast.provenance)||coast.independentReference!==true
  || !finiteError(coast.maxAlignmentErrorMeters)||!finiteError(coast.measurementErrorMeters)
  || !geographicBounds(coast.auditExtent))check('COAST_ALIGNMENT','DATA_LIMITED',{maxAlignmentErrorPixels:null,reason:'INDEPENDENT_MEASURED_HASH_BOUND_ALIGNMENT_REQUIRED'});
 else {
  const errorPixels=(coast.maxAlignmentErrorMeters+coast.measurementErrorMeters)/metresPerPixel;
  check('COAST_ALIGNMENT',!contains(coast.auditExtent,candidate.bounds)||!contains(reference.extent,candidate.bounds)
   || errorPixels>LOCAL_QUALITY_POLICY.maxGeometryErrorPixels?'FAIL':'PASS',
   {maxAlignmentErrorPixels:errorPixels,maxAlignmentErrorMeters:coast.maxAlignmentErrorMeters,measurementErrorMeters:coast.measurementErrorMeters});
 }
 auditLayout(candidate,profile,check);
 const nativeNames=['TERRAIN_NATIVE_DENSITY','TERRAIN_COVERAGE','CANAL_POSITIONAL_ACCURACY',...records.map(record=>'GIS_'+record.id)],
  nativeReady=nativeNames.every(name=>checks.some(item=>item.name===name&&item.status==='PASS'))
   && checks.some(item=>item.name==='FULL_EVENT_GEOMETRY'&&item.status==='PASS')
   && checks.some(item=>item.name==='VERIFIED_V2_LINE_REPRESENTATION'&&item.status==='PASS')
   && records.length>0&&records.some(record=>record.id===profile.primary);
 const legacyInput=nativeReady?completeLegacyInput(candidate,profile):null;
 const height=profile.heightSource, demRequired=profile.requirements?.requireRealDEM===true;
 if(height) {
  const contract=heightSourceContract(height);
  check('HEIGHT_SOURCE_CONTRACT',contract.valid?'PASS':'FAIL',{assessment:contract,required:demRequired});
 }
 if(demRequired) {
  const input=legacyInput;
  if(!input)check('REQUIRED_DEM','DATA_LIMITED');
  else {
   const dem=LocalDetailAdmission(input).checks.dem;
   check('REQUIRED_DEM',dem.status==='SUFFICIENT'?'PASS':'FAIL',{assessment:dem});
  }
 } else check('DEM_OPTIONAL_SCOPE','PASS',{required:false,availableFootprint:height?.footprint??null,
  fullCoverage:contains(height?.footprint,candidate.bounds),note:'Optional height is not a claim of complete DEM coverage.'});
 let legacyAdmission=null,safeClosest=null;
 if(legacyInput) {
  legacyAdmission=LocalDetailAdmission(legacyInput);
  // Accuracy established only for a smaller audit scope cannot certify the old
  // wide baseline. The preserved solver assumes its evidence applies there.
  const approved=profile.nativeAdmissionInput?.approvedExtent??candidate.currentBounds;
  const scoped=(legacyInput.geometries??[]).filter(record=>relevantRecord(record,approved,legacyInput.primary));
  if(geographicBounds(approved)&&scoped.every(record=>contains(evidence[record.id]?.auditExtent,approved)))
   safeClosest=SafeClosestExtent({...legacyInput,approvedExtent:approved,requestedExtent:candidate.bounds});
 }
 const status=violations.length?'NOT_ADMITTED':missing.length?'DATA_LIMITED':'ADMITTED';
 return freeze({version:DETAIL_QUALITY_AUDIT_V1_VERSION,candidate:clone(candidate),status,
  policy:clone(LOCAL_QUALITY_POLICY),checks,missingData:missing,violations,
  readable:candidate.screenCoverage>=candidate.readabilityMinimum-1e-12,certificateEligible:status==='ADMITTED'&&candidate.screenCoverage>=candidate.readabilityMinimum-1e-12,
  legacyLocalStatus:legacyAdmission?.status??'NOT_EVALUATED_INCOMPLETE_INPUTS',legacyAdmission,safeClosest,
  effectiveScale:'REGIONAL',localUsed:false,
  certificationScope:'DATA_QUALITY_FOR_NEW_STATIC_REGIONAL_INPUT; NO_CAMERA_OR_EVENT_ANIMATION',
  metrics:{terrainDensity,minimumGroundMetersPerOutputPixel:metresPerPixel,
   projectedLengthPixels:candidate.projectedLengthPixels,axisCoverage:candidate.axisCoverage,screenCoverage:candidate.screenCoverage},
  dataBinding:canonical({candidate,profile,policy:LOCAL_QUALITY_POLICY})});
}

function completeLegacyInput(candidate,profile) {
 if(!text(profile.primary)||!Array.isArray(profile.geometries)||!profile.geometries.length||!profile.eventGeometry
  || !profile.terrain||!inside(candidate.eventAnchor,candidate.bounds))return null;
 return {extent:clone(candidate.bounds),output:clone(candidate.output),anchor:clone(candidate.eventAnchor),primary:profile.primary,
  geometries:clone(profile.geometries),eventGeometry:[clone(profile.eventGeometry)],terrain:clone(profile.terrain),
  qualityEvidence:clone(profile.qualityEvidence??{}),heightSource:clone(profile.heightSource??null),requirements:clone(profile.requirements??{})};
}

function auditLayout(candidate,profile,check) {
 // Trust boundary: the producer must have verified these reservations using
 // the actual unchanged native renderer, fresh projection and glyph bounds.
 // This pure audit validates their bindings/collisions; it cannot attest pixels.
 const layout=profile.layoutEvidence?.[candidate.id], expected=profile.protectedStyle;
 if(layout?.verified!==true||!expected||!same(layout.candidateBounds,candidate.bounds)||layout.geometryBinding!==candidate.geometryBinding) {
  check('PROJECTED_LAYOUT',layout?.verified===true?'FAIL':'DATA_LIMITED',{reason:'FRESH_CANDIDATE_BOUND_LAYOUT_REQUIRED'});return;
 }
 const marker=layout.marker, metric=layout.metric, graphic=layout.protectedGraphics;
 if(!marker||!metric||!Array.isArray(graphic)||!expected.marker||!expected.metric) {
  check('MEASURED_LAYOUT','DATA_LIMITED');return;
 }
 const size=expected.marker.size;
 const markerKnown=finitePoint(expected.marker.anchor)&&Number.isFinite(size)&&size>0&&digest(expected.marker.designSha256)
  && digest(marker.designSha256)&&finitePoint(marker.anchor)&&Number.isFinite(marker.size)&&validBounds(marker.roi);
 const p=finitePoint(expected.marker.anchor)?project(expected.marker.anchor,candidate.bounds,candidate.output):null,
  expectedRoi=p&&Number.isFinite(size)?[p[0]-size/2,p[1]-size/2,p[0]+size/2,p[1]+size/2]:null;
 check('PROTECTED_MARKER',!markerKnown?'DATA_LIMITED':!same(marker.anchor,expected.marker.anchor)||marker.size!==size
  || marker.designSha256!==expected.marker.designSha256||!same(marker.roi,expectedRoi)
  || marker.visible!==true||!contains(candidate.safeArea,marker.roi)?'FAIL':'PASS',{projectedAnchor:p,expectedRoi});
 const textKnown=positivePair(metric.atlasDimensions)&&metric.atlasDimensions.every(Number.isSafeInteger)
  && validBounds(metric.roi)&&metric.measurementVerified===true&&text(expected.metric.value)&&text(expected.metric.source)
  && Number.isFinite(expected.metric.fontSize)&&expected.metric.fontSize>0;
 check('PROTECTED_METRIC_STYLE',!textKnown?'DATA_LIMITED':metric.fontSize!==expected.metric.fontSize||metric.value!==expected.metric.value
  || metric.source!==expected.metric.source||metric.reservationSpace!=='FULL_MEASURED_ATLAS'?'FAIL':'PASS');
 if(graphic.some(item=>!['TEXT','MARKER','PANEL'].includes(item.kind)||!validBounds(item.roi))) {
  check('PROTECTED_GRAPHIC_BOUNDS','DATA_LIMITED');return;
 }
 check('PROTECTED_TEXT_SAFE_AREA',typeof layout.textSafe!=='boolean'?'DATA_LIMITED':layout.textSafe
  && graphic.filter(item=>item.kind!=='MARKER').every(item=>contains(candidate.safeArea,item.roi))?'PASS':'FAIL');
 const strict=graphic.filter(item=>item.kind!=='MARKER'), segments=candidate.projectedCoordinates.slice(1).map((b,i)=>[candidate.projectedCoordinates[i],b]);
 const lineCollisions=strict.flatMap((item,i)=>segments.some(([a,b])=>overlaps([Math.min(a[0],b[0])-candidate.linePaddingPixels,
  Math.min(a[1],b[1])-candidate.linePaddingPixels,Math.max(a[0],b[0])+candidate.linePaddingPixels,Math.max(a[1],b[1])+candidate.linePaddingPixels],item.roi))?[i]:[]);
 check('LINE_PROTECTED_GRAPHICS',lineCollisions.length?'FAIL':'PASS',{collisions:lineCollisions,allowedCollision:'EVENT_GEOGRAPHIC_LINE_WITH_PROTECTED_GEOGRAPHIC_MARKER_ONLY'});
 if(!textKnown)return;
 const bounds=metric.roi, atlas=metric.atlasDimensions, ownMarker=validBounds(marker.roi)?[{kind:'MARKER',roi:marker.roi}]:[],
  protectedItems=[...graphic,...ownMarker],markerOcclusions=protectedItems.filter(item=>item.kind==='MARKER').map(item=>item.roi),
  collisions=protectedItems.flatMap((item,i)=>overlaps(bounds,item.roi)?[i]:[]);
 const fullAtlas=Math.abs((bounds[2]-bounds[0])-atlas[0])<1e-9&&Math.abs((bounds[3]-bounds[1])-atlas[1])<1e-9;
 const lineDistance=Math.min(...segments.map(([a,b])=>segmentDistanceToBox(a,b,bounds)));
 let related=null,error=null;
 try {related=chooseRelatedMetricPlacement({visibleGeometry:candidate.projectedCoordinates,measurement:{atlasDimensions:atlas},
  safeArea:candidate.safeArea,protectedBoxes:protectedItems.map(item=>item.roi),markerOcclusions,
  linePaddingPixels:candidate.linePaddingPixels,gap:10,anchor:project(candidate.eventAnchor,candidate.bounds,candidate.output)});}
 catch(failure){error=failure.message;}
 const support=related?.visibleSupportSegments??[], visibleDistance=support.length
  ?Math.min(...support.map(segment=>segmentDistanceToBox(...segment.path,bounds))):null,
  relationshipGapPixels=visibleDistance===null?null:visibleDistance-candidate.linePaddingPixels;
 const relation=relationshipGapPixels!==null&&relationshipGapPixels>=8-1e-9&&relationshipGapPixels<=14+1e-9;
 check('METRIC_PLACEMENT',!fullAtlas||!contains(candidate.safeArea,bounds)||collisions.length
  || lineDistance<candidate.linePaddingPixels-1e-9||!related||!relation?'FAIL':'PASS',
  {collisions,lineDistancePixels:lineDistance,relationshipGapPixels,atlasDimensions:atlas,layoutFailure:error});
}

/** The least enlargement that is admitted AND readable wins. Never maximum zoom. */
export function selectSafeDetailExtent({candidates,profile} = {}) {
 if(!Array.isArray(candidates)||!candidates.length)throw Error('DETAIL_CANDIDATES_REQUIRED');
 const ordered=[...candidates].sort((a,b)=>a.zoomFactor-b.zoomFactor), audits=ordered.map(candidate=>auditDetailExtent({candidate,profile})),
  selected=audits.find(audit=>audit.certificateEligible), candidate=selected?.candidate;
 const synthetic=profile.evidenceKind==='SYNTHETIC_TEST_ONLY'||profile.dataMode==='SYNTHETIC_TEST';
 const production=profile.dataMode==='VERIFIED_PRODUCTION'&&profile.evidenceKind==='VERIFIED_PRODUCTION'&&!synthetic;
 const certificate=selected?{version:SAFE_DETAIL_EXTENT_V1_VERSION,status:'ADMITTED',effectiveScale:'REGIONAL',localUsed:false,
  evidenceKind:synthetic?'SYNTHETIC_TEST_ONLY':'VERIFIED_PRODUCTION',productionEligible:production,
  candidateId:candidate.id,bounds:clone(candidate.bounds),center:clone(candidate.center),widthDegrees:candidate.widthDegrees,
  heightDegrees:candidate.heightDegrees,terrainSource:clone(profile.terrain),gisSources:clone(profile.geometries),
  eventGeometryBinding:candidate.geometryBinding,projectedLengthPixels:candidate.projectedLengthPixels,
  axisCoverage:clone(candidate.axisCoverage),screenCoverage:candidate.screenCoverage,qualityMetrics:clone(selected.metrics),
  legacyLocalStatus:selected.legacyLocalStatus,legacySafeClosestStatus:selected.safeClosest?.status??'NOT_EVALUATED_INCOMPLETE_OR_SCOPED_INPUTS',
  policy:clone(LOCAL_QUALITY_POLICY),dataBinding:selected.dataBinding,
  selection:'MINIMUM_SUFFICIENT_DETAIL_LEAST_ENLARGEMENT',runtimeAnimationAuthorized:false}:null;
 return freeze({version:DETAIL_DATA_PROFILE_V1_VERSION,status:selected?(production?'DETAIL_ADMISSION_READY':'SYNTHETIC_DETAIL_AUDIT_PASS'):'DETAIL_DATA_ADMISSION_BLOCKED',
  safeDetailExtent:certificate,audits,requiredTempOnlyFiles:null,next:selected?(production?'READY_FOR_EVENT_V3_DETAIL_APPROACH':'SYNTHETIC_VALIDATION_ONLY'):'DETAIL_DATA_ACTION_REQUIRED',
  eventAnimationStarted:false,cameraV5Modified:false});
}
