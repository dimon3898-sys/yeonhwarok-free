import test from 'node:test';
import assert from 'node:assert/strict';
import {DETAIL_DATA_PROFILE_V1_VERSION,DETAIL_DATA_QUALITY_POLICY,generateDetailExtentCandidates,
 auditDetailExtent,selectSafeDetailExtent} from '../web/map_infographic_v1/detail_data_profile_v1.mjs';
import {LOCAL_QUALITY_POLICY} from '../web/map_infographic_v1/local_detail_admission.mjs';
import {chooseRelatedMetricPlacement} from '../web/map_infographic_v1/event_layout_adapter_v1.mjs';

// Synthetic evidence only. These invented hashes/accuracy values cannot certify
// any production dataset. Production acquisition and audit run separately.
const hash=character=>character.repeat(64), broad=[-20,-40,20,40];
const input=()=>({eventGeometry:{type:'LineString',coordinates:[[0,0],[.1,.4],[.2,1]]},
 eventAnchor:[.1,.4],currentBounds:[-5,-10,5,10],output:[1080,1920],safeArea:[48,72,1032,1848]});
function fixture() {
 const given=input(), candidates=generateDetailExtentCandidates(given),
  source=(id,role,sha)=>({id,role,source:'SYNTHETIC_TEST',version:'SYNTHETIC_TEST_V1',retrievalDate:'2026-10-13T00:00:00Z',
   license:'SYNTHETIC_TEST_ONLY',originalUrl:'https://example.test/'+id,sha256:sha,CRS:'EPSG:4326',extent:[...broad],
   payloadVerified:true,verification:{verified:true,sha256:sha,byteLength:100}}),
  sources=[{...source('terrain','TERRAIN',hash('a')),nativePixelSpacing:[.0001,.0001],classification:'BAKED HILLSHADE'},
   source('gis','GIS',hash('b')),source('canal','CANAL',hash('c')),source('reference','REFERENCE',hash('d'))],
  geometries=[{id:'primary',sourceId:'gis',sha256:hash('2'),geometry:{type:'Polygon',coordinates:[[
   [-20,-40],[20,-40],[20,40],[-20,40],[-20,-40]]]}}],
  eventGeometry={id:'axis',sourceId:'canal',sha256:hash('3'),geometry:structuredClone(given.eventGeometry)},
  evidence=(geometrySha256,sourceSha256)=>({verified:true,geometrySha256,sourceSha256,provenance:'SYNTHETIC_TEST_ONLY',
   positionalErrorMeters:1,simplificationErrorMeters:0,auditExtent:[...broad],complete:true});
 const profile={version:DETAIL_DATA_PROFILE_V1_VERSION,evidenceKind:'SYNTHETIC_TEST_ONLY',policy:LOCAL_QUALITY_POLICY,
  sources,primary:'primary',geometries,eventGeometry,qualityEvidence:{primary:evidence(hash('2'),hash('b')),axis:evidence(hash('3'),hash('c'))},
  terrain:{sourceId:'terrain',sha256:hash('a'),nativeSourceSha256:hash('a'),geographicExtent:[...broad],
   pixelSpacing:[.0001,.0001],classification:'BAKED HILLSHADE'},
  baselines:{rendererSha256:hash('e'),linePassSha256:hash('f'),eventGeometryBinding:candidates[0].geometryBinding},
  rendererCompatibility:{verified:true,rendererSha256:hash('e'),linePassSha256:hash('f'),terrainTreatment:'BAKED_RELIEF_V1',
   terrainClassification:'BAKED HILLSHADE',eventRepresentations:['LineString'],maximumLineSegments:128},
  coastAlignmentEvidence:{verified:true,terrainSha256:hash('a'),gisGeometrySha256s:[hash('2')],referenceSourceSha256:hash('d'),
   independentReference:true,maxAlignmentErrorMeters:1,measurementErrorMeters:1,provenance:'SYNTHETIC_TEST_ONLY',auditExtent:[...broad]},
  protectedStyle:{marker:{anchor:[...given.eventAnchor],size:40,designSha256:hash('1')},
   metric:{fontSize:40,value:'123.45 km',source:'SYNTHETIC_TEST_AUTHORITY'}},requirements:{requireRealDEM:false},layoutEvidence:{}};
 for(const candidate of candidates)profile.layoutEvidence[candidate.id]=layout(candidate,profile);
 return {given,candidates,profile};
}
function layout(candidate,profile) {
 const [west,south,east,north]=candidate.bounds,[width,height]=candidate.output, anchor=profile.protectedStyle.marker.anchor,
  projected=[(anchor[0]-west)/(east-west)*width,(north-anchor[1])/(north-south)*height],size=profile.protectedStyle.marker.size,
  roi=[projected[0]-size/2,projected[1]-size/2,projected[0]+size/2,projected[1]+size/2],
  protectedGraphics=[{kind:'MARKER',roi},{kind:'TEXT',roi:[60,80,300,130]}], atlasDimensions=[200,50],
  metric=chooseRelatedMetricPlacement({visibleGeometry:candidate.projectedCoordinates,measurement:{atlasDimensions},
   safeArea:candidate.safeArea,protectedBoxes:protectedGraphics.map(item=>item.roi),markerOcclusions:[roi],
   linePaddingPixels:candidate.linePaddingPixels,gap:10,anchor:projected});
 return {verified:true,candidateBounds:[...candidate.bounds],geometryBinding:candidate.geometryBinding,textSafe:true,protectedGraphics,
  marker:{...profile.protectedStyle.marker,visible:true,roi},
  metric:{...profile.protectedStyle.metric,measurementVerified:true,atlasDimensions,roi:[...metric.roi],reservationSpace:'FULL_MEASURED_ATLAS'}};
}
const audit=(data,index=1)=>auditDetailExtent({candidate:data.candidates[index],profile:data.profile});
const check=(result,name)=>result.checks.find(row=>row.name===name);

test('strict policy is the identical preserved frozen policy object',()=>{
 assert.equal(DETAIL_DATA_QUALITY_POLICY,LOCAL_QUALITY_POLICY);
 assert.equal(DETAIL_DATA_QUALITY_POLICY.maxPixelsPerNativeTexel,1);
 assert.equal(DETAIL_DATA_QUALITY_POLICY.maxGeometryErrorPixels,1);
 assert.equal(Object.isFrozen(DETAIL_DATA_QUALITY_POLICY),true);
});

test('A: already-readable full geometry keeps current view without another enlargement',()=>{
 const given=input();given.eventGeometry.coordinates=[[0,-3],[.3,3]];
 const candidates=generateDetailExtentCandidates(given);
 assert.equal(candidates.length,1);assert.equal(candidates[0].id,'D0');
 assert.deepEqual(candidates[0].bounds,given.currentBounds);assert.ok(candidates[0].screenCoverage>=.2);
 assert.equal(candidates[0].wholeGeometryVisible,true);
});

test('B: small geometry generates three input-derived least-enlargement-first proposals',()=>{
 const given=input(),before=structuredClone(given),candidates=generateDetailExtentCandidates(given);
 assert.deepEqual(given,before);assert.deepEqual(candidates.map(row=>row.id),['D0','D1','D2','D3']);
 assert.ok(candidates[0].screenCoverage<.2);
 candidates.slice(1).forEach((row,i)=>{
  assert.ok(Math.abs(row.screenCoverage-[.2,.35,.5][i])<1e-12);
  assert.equal(row.wholeGeometryVisible,true);assert.equal(row.sourceCoordinateCount,3);
  assert.ok(Math.abs(row.widthDegrees/row.heightDegrees-.5)<1e-12);
  assert.ok(row.zoomFactor>candidates[i].zoomFactor);
 });
 assert.equal(Object.isFrozen(candidates[1].bounds),true);
});

test('C: long narrow geometry retains every endpoint and finite halo instead of cropping',()=>{
 const given=input();given.eventGeometry.coordinates=[[0,-1],[.01,0],[0,1]];
 const candidates=generateDetailExtentCandidates(given);
 for(const candidate of candidates){
  assert.equal(candidate.sourceCoordinateCount,3);assert.equal(candidate.wholeGeometryVisible,true);
  for(const p of candidate.projectedCoordinates)assert.ok(p[0]>=candidate.safeArea[0]+5.75&&p[0]<=candidate.safeArea[2]-5.75
   &&p[1]>=candidate.safeArea[1]+5.75&&p[1]<=candidate.safeArea[3]-5.75);
 }
 assert.ok(candidates.at(-1).projectedLengthPixels>candidates[0].projectedLengthPixels);
});

test('translation changes only geographic bounds, not zoom or screen coverage',()=>{
 const given=input(), original=generateDetailExtentCandidates(given), translated=structuredClone(given), delta=[12,8];
 translated.eventGeometry.coordinates=translated.eventGeometry.coordinates.map(p=>p.map((v,i)=>v+delta[i]));
 translated.eventAnchor=translated.eventAnchor.map((v,i)=>v+delta[i]);
 translated.currentBounds=translated.currentBounds.map((v,i)=>v+delta[i%2]);
 const result=generateDetailExtentCandidates(translated);
 assert.equal(result.length,original.length);
 result.forEach((row,i)=>{
  row.bounds.forEach((v,j)=>assert.ok(Math.abs(v-original[i].bounds[j]-delta[j%2])<1e-12));
  assert.ok(Math.abs(row.screenCoverage-original[i].screenCoverage)<1e-12);
  assert.ok(Math.abs(row.zoomFactor-original[i].zoomFactor)<1e-12);
 });
});

test('a complete synthetic quality audit passes while legacy LOCAL stays denied for LineString',()=>{
 const result=audit(fixture());
 assert.equal(result.status,'ADMITTED',JSON.stringify(result.checks.filter(row=>row.status!=='PASS')));
 assert.equal(result.legacyLocalStatus,'LOCAL_NOT_ADMITTED');assert.equal(result.localUsed,false);
 assert.equal(result.legacyAdmission.checks.event.records[0].representation,'LineString');
 assert.equal(result.legacyAdmission.checks.event.records[0].supportedByPixelPipeline,false);
 assert.equal(result.safeClosest.status,'DATA_CERTIFIED_REGIONAL_EXTENT');
 assert.equal(result.effectiveScale,'REGIONAL');
});

test('selection takes the first readable admitted proposal and binds its exact data',()=>{
 const data=fixture(), before=structuredClone(data), selected=selectSafeDetailExtent(data);
 assert.equal(selected.status,'SYNTHETIC_DETAIL_AUDIT_PASS');assert.equal(selected.safeDetailExtent.candidateId,'D1');
 assert.deepEqual(selected.safeDetailExtent.bounds,data.candidates[1].bounds);
 assert.equal(selected.safeDetailExtent.runtimeAnimationAuthorized,false);
 assert.equal(selected.safeDetailExtent.productionEligible,false);
 assert.equal(selected.eventAnimationStarted,false);assert.deepEqual(data,before);
 assert.ok(selected.safeDetailExtent.dataBinding.includes('SYNTHETIC_TEST_ONLY'));
 // The anchor-centred legacy solver can return a different extent. Its status
 // is evidence about its actual result, never the certificate's bounds.
 assert.notDeepEqual(selected.audits[1].safeClosest.bounds,selected.safeDetailExtent.bounds);
});

test('no original payload means DATA_LIMITED even with documentary ten-metre resolution',()=>{
 const data=fixture(), source=data.profile.sources[0];source.payloadVerified=false;source.verification=null;
 source.nativePixelSpacing=null;source.documentaryResolutionMeters=10;
 const result=audit(data);assert.equal(result.status,'DATA_LIMITED');
 assert.equal(check(result,'TERRAIN_NATIVE_DENSITY').density,null);
 assert.equal(result.legacyLocalStatus,'NOT_EVALUATED_INCOMPLETE_INPUTS');
 assert.equal(selectSafeDetailExtent(data).safeDetailExtent,null);
});

test('missing GIS positional or simplification error remains unknown, never zero or pass',()=>{
 const data=fixture();data.profile.qualityEvidence.primary.positionalErrorMeters=null;
 const result=audit(data);assert.equal(result.status,'DATA_LIMITED');
 assert.equal(check(result,'GIS_primary').geometryErrorPixels,null);
 assert.equal(selectSafeDetailExtent(data).safeDetailExtent,null);
});

test('upscaling a derivative cannot improve native density and is rejected',()=>{
 const data=fixture();data.profile.terrain.dimensions=[200000,200000];data.profile.terrain.pixelSpacing=[.00001,.00001];
 const result=audit(data);assert.equal(result.status,'NOT_ADMITTED');
 assert.equal(check(result,'TERRAIN_NATIVE_DENSITY').artificialUpscale,true);
 const base=audit(fixture());assert.deepEqual(check(result,'TERRAIN_NATIVE_DENSITY').density,check(base,'TERRAIN_NATIVE_DENSITY').density);
});

test('native terrain density at exactly one passes and just above fails',()=>{
 const data=fixture(),candidate=data.candidates[1],spacing=[candidate.widthDegrees/candidate.output[0],candidate.heightDegrees/candidate.output[1]];
 data.profile.sources[0].nativePixelSpacing=spacing;data.profile.terrain.pixelSpacing=[...spacing];
 assert.equal(check(audit(data),'TERRAIN_NATIVE_DENSITY').status,'PASS');
 data.profile.sources[0].nativePixelSpacing=spacing.map(v=>v*(1+1e-6));data.profile.terrain.pixelSpacing=[...data.profile.sources[0].nativePixelSpacing];
 assert.equal(check(audit(data),'TERRAIN_NATIVE_DENSITY').status,'FAIL');
});

test('GIS error uses worst viewport latitude, passes exactly one pixel and fails above',()=>{
 const data=fixture(),base=audit(data),pixel=base.metrics.minimumGroundMetersPerOutputPixel;
 data.profile.qualityEvidence.primary.positionalErrorMeters=pixel;
 assert.equal(check(audit(data),'GIS_primary').status,'PASS');
 data.profile.qualityEvidence.primary.positionalErrorMeters=pixel*(1+1e-6);
 assert.equal(check(audit(data),'GIS_primary').status,'FAIL');
});

test('stale geometry, original payload and coastline bindings fail closed',()=>{
 for(const mutate of [
  data=>{data.profile.qualityEvidence.primary.geometrySha256=hash('4');},
  data=>{data.profile.sources[0].verification.sha256=hash('4');},
  data=>{data.profile.coastAlignmentEvidence.gisGeometrySha256s=[hash('4')];},
  data=>{data.profile.qualityEvidence.axis.sourceSha256=hash('4');},
 ]) {const data=fixture();mutate(data);assert.equal(audit(data).status,'NOT_ADMITTED');}
});

test('independent coastline measurement and uncertainty are required and strict',()=>{
 const data=fixture();data.profile.coastAlignmentEvidence.measurementErrorMeters=null;
 assert.equal(audit(data).status,'DATA_LIMITED');
 const known=fixture(),pixel=audit(known).metrics.minimumGroundMetersPerOutputPixel;
 known.profile.coastAlignmentEvidence.maxAlignmentErrorMeters=pixel;known.profile.coastAlignmentEvidence.measurementErrorMeters=0;
 assert.equal(check(audit(known),'COAST_ALIGNMENT').status,'PASS');
 known.profile.coastAlignmentEvidence.maxAlignmentErrorMeters=pixel+1;
 assert.equal(check(audit(known),'COAST_ALIGNMENT').status,'FAIL');
});

test('raw imagery cannot be relabeled as compatible baked hillshade',()=>{
 const data=fixture();data.profile.sources[0].classification='RAW SATELLITE RGB';
 assert.equal(check(audit(data),'UNCHANGED_RENDERER_COMPATIBILITY').status,'FAIL');
 const other=fixture();other.profile.rendererCompatibility.terrainTreatment='CURRENT';
 assert.equal(check(audit(other),'UNCHANGED_RENDERER_COMPATIBILITY').status,'FAIL');
});

test('partial optional DEM is explicit; mandatory missing DEM fails',()=>{
 const data=fixture();data.profile.heightSource={CRS:'EPSG:4326',unit:'m',scale:1,offset:0,format:'Float32',NoData:null,
  dimensions:[2,2],validSamples:4,byteLength:16,pixelSpacing:[.01,.01],footprint:[0,0,1,.2],firstSample:[0,.2],
  orientation:'north-up row-major',sha256:hash('6')};
 const result=audit(data);assert.equal(check(result,'DEM_OPTIONAL_SCOPE').status,'PASS');
 assert.equal(check(result,'DEM_OPTIONAL_SCOPE').fullCoverage,false);
 data.profile.requirements.requireRealDEM=true;
 assert.equal(check(audit(data),'REQUIRED_DEM').status,'FAIL');
});

test('fresh measured Metric cannot overlap Marker or text and must reserve the full atlas',()=>{
 const data=fixture(),row=data.profile.layoutEvidence.D1;row.metric.roi=[...row.marker.roi];
 assert.equal(check(audit(data),'METRIC_PLACEMENT').status,'FAIL');
 const other=fixture();other.profile.layoutEvidence.D1.metric.measurementVerified=false;
 assert.equal(check(audit(other),'PROTECTED_METRIC_STYLE').status,'DATA_LIMITED');
 const value=fixture();value.profile.layoutEvidence.D1.metric.value='999 km';
 assert.equal(check(audit(value),'PROTECTED_METRIC_STYLE').status,'FAIL');
});

test('Marker anchor/design/size and metric font are preserved independently of projection',()=>{
 for(const mutate of [
  row=>{row.marker.anchor[0]+=.1;},row=>{row.marker.size=41;},row=>{row.marker.designSha256=hash('4');},row=>{row.metric.fontSize=39;},
 ]){const data=fixture();mutate(data.profile.layoutEvidence.D1);assert.equal(audit(data).status,'NOT_ADMITTED');}
});

test('source line replacement, fake projection and crop are rejected',()=>{
 const data=fixture();data.profile.eventGeometry.geometry.coordinates[0][0]+=.01;
 assert.equal(check(audit(data),'FULL_EVENT_GEOMETRY').status,'FAIL');
 const altered=fixture(), candidate=structuredClone(altered.candidates[1]);candidate.projectedLengthPixels*=2;
 assert.equal(check(auditDetailExtent({candidate,profile:altered.profile}),'PROJECTED_GEOMETRY_BINDING').status,'FAIL');
 const cropped=fixture(), narrow=structuredClone(cropped.candidates[1]);narrow.wholeGeometryVisible=false;
 assert.equal(check(auditDetailExtent({candidate:narrow,profile:cropped.profile}),'WHOLE_EVENT_SAFE_AREA').status,'FAIL');
});

test('narrow accuracy scope cannot certify the wider legacy baseline',()=>{
 const data=fixture();for(const evidence of Object.values(data.profile.qualityEvidence))evidence.auditExtent=[...data.candidates[1].bounds];
 data.profile.coastAlignmentEvidence.auditExtent=[...data.candidates[1].bounds];
 const result=audit(data);assert.equal(result.status,'ADMITTED');assert.equal(result.safeClosest,null);
 assert.equal(result.legacyLocalStatus,'LOCAL_NOT_ADMITTED');
 const wider=audit(data,0);assert.equal(check(wider,'GIS_primary').status,'FAIL');
});

test('unknown irrelevant polygon does not gain or block accuracy; primary always required',()=>{
 const data=fixture();data.profile.geometries.push({id:'far',sourceId:'unknown',sha256:hash('4'),geometry:{type:'Polygon',
  coordinates:[[[50,50],[51,50],[51,51],[50,51],[50,50]]]}});
 assert.equal(audit(data).status,'ADMITTED');
 data.profile.primary='missing';assert.equal(check(audit(data),'PRIMARY_GIS_REQUIRED').status,'DATA_LIMITED');
});

test('policy weakening and unsupported representation are not admission',()=>{
 const data=fixture();data.profile.policy={...LOCAL_QUALITY_POLICY,maxGeometryErrorPixels:2};
 assert.equal(check(audit(data),'STRICT_IMPORTED_POLICY').status,'FAIL');
 const other=fixture();other.profile.rendererCompatibility.eventRepresentations=['Point'];
 assert.equal(check(audit(other),'VERIFIED_V2_LINE_REPRESENTATION').status,'FAIL');
});

test('invalid height metadata is rejected even when real DEM coverage is optional',()=>{
 const data=fixture();data.profile.heightSource={footprint:[0,0,1,.2]};
 const result=audit(data);assert.equal(result.status,'NOT_ADMITTED');
 assert.equal(check(result,'HEIGHT_SOURCE_CONTRACT').status,'FAIL');
 assert.equal(check(result,'DEM_OPTIONAL_SCOPE').status,'PASS');
 assert.equal(selectSafeDetailExtent(data).safeDetailExtent,null);
});

test('synthetic or implicit profile modes cannot become production-ready output',()=>{
 const synthetic=fixture();synthetic.profile.dataMode='SYNTHETIC_TEST';
 const result=selectSafeDetailExtent(synthetic);assert.equal(result.status,'SYNTHETIC_DETAIL_AUDIT_PASS');
 assert.equal(result.safeDetailExtent.productionEligible,false);assert.equal(result.next,'SYNTHETIC_VALIDATION_ONLY');
 const implicit=fixture();delete implicit.profile.evidenceKind;
 assert.equal(check(audit(implicit),'PROFILE_EVIDENCE_MODE').status,'DATA_LIMITED');
 assert.equal(selectSafeDetailExtent(implicit).safeDetailExtent,null);
 implicit.profile.dataMode='VERIFIED_PRODUCTION';
 assert.equal(selectSafeDetailExtent(implicit).status,'DETAIL_DATA_ADMISSION_BLOCKED');
});

test('forged crop and anchor visibility are recomputed rather than trusted',()=>{
 const cropped=fixture(),given=input();given.eventGeometry.coordinates=[[-6,0],[6,1]];
 const actual=generateDetailExtentCandidates(given)[0];assert.equal(actual.wholeGeometryVisible,false);
 const candidate=structuredClone(actual);candidate.wholeGeometryVisible=true;
 cropped.profile.eventGeometry.geometry=given.eventGeometry;cropped.profile.baselines.eventGeometryBinding=actual.geometryBinding;
 assert.equal(check(auditDetailExtent({candidate,profile:cropped.profile}),'PROJECTED_GEOMETRY_BINDING').status,'FAIL');
 const anchored=fixture(),outside=input();outside.eventAnchor=[6,.4];
 const anchorCandidate=structuredClone(generateDetailExtentCandidates(outside)[0]);assert.equal(anchorCandidate.anchorVisible,false);
 anchorCandidate.anchorVisible=true;
 assert.equal(check(auditDetailExtent({candidate:anchorCandidate,profile:anchored.profile}),'PROJECTED_ANCHOR_BINDING').status,'FAIL');
});

test('projection and invalid finite halo cannot be forged on a readonly candidate',()=>{
 const data=fixture(),projection=structuredClone(data.candidates[1]);projection.projection='WORLD_GLOBE_ORTHOGRAPHIC';
 assert.equal(check(auditDetailExtent({candidate:projection,profile:data.profile}),'CANONICAL_PROJECTION').status,'FAIL');
 const halo=structuredClone(data.candidates[1]);halo.linePaddingPixels=NaN;
 assert.equal(check(auditDetailExtent({candidate:halo,profile:data.profile}),'FINITE_LINE_HALO').status,'FAIL');
 assert.equal(Object.isFrozen(data.candidates[1].projectedHaloBounds),true);
});
