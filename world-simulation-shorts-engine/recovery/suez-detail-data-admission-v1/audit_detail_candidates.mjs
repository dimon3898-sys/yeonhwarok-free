// Reproducible data-only proposals/audits. No camera motion or static proof before admission.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {DETAIL_DATA_PROFILE_V1_VERSION,DETAIL_DATA_QUALITY_POLICY,generateDetailExtentCandidates,
 selectSafeDetailExtent} from '../../web/map_infographic_v1/detail_data_profile_v1.mjs';
import {projectedTexelDensity,coverageFraction} from '../../web/map_infographic_v1/local_detail_admission.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.dirname(engine);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex'),json=async p=>JSON.parse(await readFile(p,'utf8'));
const fixturePath='world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/fixture.json';
const fixture=await json(path.join(repo,fixturePath)),originalFixture=await readFile(path.join(repo,fixturePath));
const regional=await json(path.join(engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json')),
 camera=await json(path.join(engine,'recovery/v5/inputs/camera-plan.json')),
 inputs=await json(path.join(engine,'recovery/v4/V4-state-records/input-manifest.json')),
 on=await json(path.join(engine,'recovery/event-v1-candidate-v2/evidence/on150/REPORT.json'));
const terrainResearch=await json(path.join(root,'research/terrain/TERRAIN_SOURCE_RESEARCH.json')),
 gisResearch=await json(path.join(root,'research/gis/GIS_SOURCE_INVESTIGATION.json')),
 demResearch=await json(path.join(root,'research/dem/EXISTING_DEM_AUDIT.json'));
const sourceGeometry=structuredClone(fixture.intent.line.geometry),sourceBinding=JSON.stringify(sourceGeometry);
const candidates=generateDetailExtentCandidates({eventGeometry:sourceGeometry,eventAnchor:regional.anchor.coordinates,
 currentBounds:camera.intent.finalExtent,output:[1080,1920],safeArea:on.frames.at(-1).placement.safeArea,
 desiredScreenCoverageRange:[.2,.35,.5],linePaddingPixels:5.75});
const now=new Date().toISOString(),geometrySha=sha(Buffer.from(sourceBinding));
const rendererSha=sha(await readFile(path.join(engine,'web/map_infographic_v1/renderer.mjs'))),
 linePassSha=sha(await readFile(path.join(engine,'web/map_infographic_v1/event_line_pass_v1.mjs'))),
 graphicDesignSha=sha(await readFile(path.join(engine,'web/map_infographic_v1/graphic_motion_pass_v4.mjs')));
const heightPath=path.join(engine,'web/dem/glo30/height.f32'),heightSource={...inputs.heightSource};
const profile={version:DETAIL_DATA_PROFILE_V1_VERSION,profileId:'DETAIL_DATA_PROFILE_PENDING_NATIVE_SOURCE_ACQUISITION',
 dataMode:'PRODUCTION_DATA_RESEARCH_NOT_ADMITTED',createdAtUtc:now,policy:DETAIL_DATA_QUALITY_POLICY,
 availableDataResolution:{documentedCandidates:terrainResearch.sources.map(source=>({id:source.id,
  nativeGridMeters:source.native_grid_resolution_m??null,actualPayloadVerified:false,assetSha256:source.asset_sha256??null})),
  spacingIsNotPositionalAccuracy:true},safeScaleRange:null,
 baselines:{rendererSha256:rendererSha,linePassSha256:linePassSha,eventGeometryBinding:candidates[0].geometryBinding,
  v5:'29b8ee294360812b55ef577b62411de58159003b',eventV2:'8cbbbd6',suezData:'69e6ed8',v3Block:'9cf4661'},
 sources:[{id:'DETAIL_TERRAIN_CANDIDATE',role:'TERRAIN',source:'ESA / Copernicus Sentinel-2 L2A public catalog candidate',
  version:'Collection documentation only; Suez product item not acquired',retrievalDate:now,
  license:'Copernicus Sentinel terms linked by official provider; original legal text pending access',
  originalUrl:'https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a',sha256:null,CRS:null,extent:null,
  payloadVerified:false,verification:{verified:false,sha256:null,byteLength:null},nativePixelSpacing:null,
  documentedNativeGridMeters:10,classification:null},
 {id:'BASELINE_COUNTRY_GIS',role:'GIS',source:'Retained Natural Earth country record selection; positional accuracy unverified',
  version:'5.1.1',retrievalDate:now,license:'Natural Earth Public Domain',
  originalUrl:'https://www.naturalearthdata.com/about/terms-of-use/',
  sha256:sha(await readFile(path.join(engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json'))),CRS:'EPSG:4326',
  extent:[-180,-90,180,90],payloadVerified:true,
  verification:{verified:true,sha256:sha(await readFile(path.join(engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json'))),
   byteLength:(await stat(path.join(engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json'))).size},
  retrievalMethod:'RETAINED_BASELINE_RECORDS_REVERIFIED; no new original GIS download'},
 {id:'VALIDATED_EVENT_AXIS',role:'CANAL',source:'Preserved OpenStreetMap Relation 7719838 v17 navigation axis',
  version:'7719838/v17;5038117 to 925360882',retrievalDate:now,license:'ODbL 1.0 / OpenStreetMap contributors',
  originalUrl:fixture.intent.line.source.source_reference,sha256:sha(originalFixture),CRS:'EPSG:4326',
  extent:[Math.min(...sourceGeometry.coordinates.map(p=>p[0])),Math.min(...sourceGeometry.coordinates.map(p=>p[1])),
   Math.max(...sourceGeometry.coordinates.map(p=>p[0])),Math.max(...sourceGeometry.coordinates.map(p=>p[1]))],
  payloadVerified:true,verification:{verified:true,sha256:sha(originalFixture),byteLength:originalFixture.length},
  retrievalMethod:'RETAINED_VALIDATED_FIXTURE_REVERIFIED; original OSM source bytes preserved at69e6ed8'},
 {id:'EXISTING_HEIGHT',role:'DEM',source:'Registered retained Copernicus GLO-30 Float32 atlas',version:heightSource.version,
  retrievalDate:null,license:null,originalUrl:null,sha256:heightSource.sha256,CRS:heightSource.CRS,extent:heightSource.footprint,
  nativePixelSpacing:heightSource.pixelSpacing,payloadVerified:true,
  verification:{verified:true,sha256:heightSource.sha256,byteLength:(await stat(heightPath)).size},
  provenanceLimitations:demResearch.source_provenance_limitations}],
 terrain:{sourceId:'DETAIL_TERRAIN_CANDIDATE',sha256:null,nativeSourceSha256:null,geographicExtent:null,
  pixelSpacing:null,classification:null,verification:{verified:false},buildRecipe:null},
 primary:regional.primary,geometries:regional.geometries.map(record=>({...record,sourceId:'BASELINE_COUNTRY_GIS'})),
 eventGeometry:{id:fixture.geometry_id,geometry:sourceGeometry,sha256:geometrySha,sourceId:'VALIDATED_EVENT_AXIS'},
 qualityEvidence:Object.fromEntries([...regional.geometries.map(record=>[record.id,{verified:false,
  geometrySha256:record.sha256,positionalErrorMeters:null,simplificationErrorMeters:null,
  provenance:'Retained generalized country geometry; no independently verified metre-error bound'}]),
  [fixture.geometry_id,{verified:false,complete:true,geometrySha256:geometrySha,sourceSha256:sha(originalFixture),
   positionalErrorMeters:null,simplificationErrorMeters:0,provenance:'Validated complete native axis; zero source-relative modification is not absolute position accuracy'}]]),
 coastAlignmentEvidence:{verified:false,terrainSha256:null,gisGeometrySha256s:[],referenceSourceSha256:null,
  maxAlignmentErrorMeters:null,measurementErrorMeters:null,independentReference:false,
  provenance:'No actual higher-detail basemap/independent reference payload acquired'},
 protectedStyle:{marker:{anchor:regional.anchor.coordinates,size:regional.layout.measured.markerSize,designSha256:graphicDesignSha},
  metric:{fontSize:40,value:fixture.intent.metric.display_value+' '+fixture.intent.metric.unit,
   source:fixture.intent.metric.source.source_reference}},layoutEvidence:{},
 rendererCompatibility:{verified:false,rendererSourceVerified:true,rendererSha256:rendererSha,linePassSha256:linePassSha,
  terrainTreatment:'BAKED_RELIEF_V1',terrainClassification:null,eventRepresentations:['LineString'],maximumLineSegments:128,
  reason:'Unchanged renderer requires genuinely compatible baked relief; raw spectral RGB is not relabeled'},
 heightSource,requirements:{requireRealDEM:false},
 staticProofPrecondition:'All required DATA/QUALITY/LAYOUT checks ADMITTED; current profile cannot create proof',
 sourceResearchReferences:{terrain:'research/terrain/TERRAIN_SOURCE_RESEARCH.json',gis:'research/gis/GIS_SOURCE_INVESTIGATION.json',
  dem:'research/dem/EXISTING_DEM_AUDIT.json'},gisDetailVerified:false,terrainDetailVerified:false,
 legacyLocalCapabilitiesNotOverridden:true,geographicInterpolationUsed:false};
const outcome=selectSafeDetailExtent({candidates,profile});
assert.equal(outcome.status,'DETAIL_DATA_ADMISSION_BLOCKED');assert.equal(outcome.safeDetailExtent,null);
assert.equal(JSON.stringify(sourceGeometry),sourceBinding);assert.deepEqual(await readFile(path.join(repo,fixturePath)),originalFixture);
const registeredTerrain={spacing:[360/regional.assets.terrain.source.resolution[0],180/regional.assets.terrain.source.resolution[1]],
 sha256:regional.assets.terrain.sha256,nativeSourceSha256:regional.assets.terrain.source.sha256,
 interpretation:'Measured old source reference only; not substituted for unacquired candidate data'};
const rows=outcome.audits.map(audit=>({candidateId:audit.candidate.id,bounds:audit.candidate.bounds,center:audit.candidate.center,
 projectedCanalLengthPixels:audit.candidate.projectedLengthPixels,axisCoverage:audit.candidate.axisCoverage,
 screenCoverage:audit.candidate.screenCoverage,zoomFactor:audit.candidate.zoomFactor,
 wholeAxisWithHaloVisible:audit.candidate.wholeGeometryVisible,markerAnchorWithinSafeArea:audit.candidate.anchorVisible,
 newTerrainPayloadRatio:null,currentRegisteredTerrainRatio:projectedTexelDensity(registeredTerrain.spacing,audit.candidate.bounds,[1080,1920]),
 existingDemRatio:projectedTexelDensity(heightSource.pixelSpacing,audit.candidate.bounds,[1080,1920]),
 existingDemViewportCoverage:coverageFraction(heightSource.footprint,audit.candidate.bounds),
 gisGeometricErrorPixels:null,coastlineAlignmentPixels:null,metricPlacementSpace:'NOT_MEASURED_UNADMITTED_FRAME',
 decision:audit.status,reasons:{missingData:audit.missingData,violations:audit.violations},
 legacyLocalStatus:audit.legacyLocalStatus}));
const out=path.join(root,'evidence');await mkdir(out,{recursive:true});
const profileBytes=Buffer.from(JSON.stringify(profile,null,2)+'\n');
await writeFile(path.join(root,'DETAIL_DATA_PROFILE.json'),profileBytes,{flag:'wx'});
await writeFile(path.join(out,'DETAIL_QUALITY_AUDIT.json'),JSON.stringify({schema:1,status:outcome.status,
 profileSha256:sha(profileBytes),canonicalProfileSha256:sha(Buffer.from(JSON.stringify(profile))),
 admissionModuleSha256:sha(await readFile(path.join(engine,'web/map_infographic_v1/detail_data_profile_v1.mjs'))),
 policy:DETAIL_DATA_QUALITY_POLICY,readabilityRequest:{axisCoverage:[.2,.35,.5]},
 requestedGeometrySourceHash:sha(originalFixture),coordinateCount:sourceGeometry.coordinates.length,geometryUnchanged:true,
 currentTerrainReference:registeredTerrain,candidates:rows,audits:outcome.audits,safeDetailExtent:null,
 interpretation:'Proposals are not admitted camera bounds. Unknown new-source density/accuracy/alignment remains null.',
 staticProofCreated:false,cameraAnimationStarted:false,eventAnimationStarted:false},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:outcome.status,safeDetailExtent:null,candidates:rows},null,2));
