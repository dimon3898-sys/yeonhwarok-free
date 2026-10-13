/** Fixture data assembly only. No event/country branches live in the reusable Area engine. */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileAreaIntent,compileAreaPlan} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {compileMinimumContextPlan} from '../../web/map_infographic_v1/camera_director_v5.mjs';
import {compileScalePlan,fitGeographicExtent,geometryBounds} from '../../web/map_infographic_v1/scale_contract.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..');
const load=async p=>JSON.parse(await readFile(path.join(engine,p),'utf8'));
const write=async(p,v)=>writeFile(path.join(root,p),JSON.stringify(v,null,2)+'\n');
const sha=b=>createHash('sha256').update(b).digest('hex');
const regionalTemplate=await load('recovery/event-feature-bundle-v2-polish/fixtures/REGIONAL-plan.json');
const contextTemplate=await load('recovery/event-feature-bundle-v2-polish/fixtures/CONTINENT-plan.json');
const countries=contextTemplate.geometries,primary=countries.find(g=>g.id==='COUNTRY_JPN');
if(!primary)throw Error('PUBLIC_JAPAN_GEOMETRY_REQUIRED');
const origin=[142.373,38.297],source={source_type:'PUBLIC_EVENT_REFERENCE',
 source_reference:'USGS official20110311054624120_30 and NOAA Tohoku 2011 public event references; illustrative coastal relationship',verification_status:'VERIFIED'};
const area=(id,coordinates,role='EVENT_AREA')=>({id,geometry:{type:'Polygon',coordinates:[coordinates]},role,style_role:'PRIMARY'});
// Supplied schematic coast focus, explicitly not an inundation map or measured footprint.
const coastFocus=[[141.0,37.3],[141.4,37.3],[142.0,39.8],[141.6,40.0],[141.2,39.0],[141.0,37.3]];
const originFocus=Array.from({length:33},(_,i)=>{const a=(i%32)/32*Math.PI*2;return[origin[0]+Math.cos(a)*.18,origin[1]+Math.sin(a)*.14];});
const intent=compileAreaIntent({data_mode:'PRODUCTION',source,origin,semantic_mode:'ILLUSTRATIVE_FACT_BASED_VISUAL',
 areas:[area('origin-focus',originFocus,'ORIGIN_REGION')],impacts:[area('coast-focus',coastFocus,'COASTAL_RELATION_NOT_INUNDATION')],
 propagations:[{id:'outward-wave',origin,radius_start_degrees:.08,radius_end_degrees:1.3,
  angular_range_degrees:[0,360]}],
 states:[{state_id:'ORIGIN',time_label:'2011.03.11',areas:[area('stage-footprint',originFocus)]},
  {state_id:'COAST',time_label:'태평양 연안',areas:[area('stage-footprint',originFocus)]},
  {state_id:'HOLD',time_label:'해안 도달',areas:[area('stage-footprint',originFocus)]}]
});
const operations=[{type:'AREA_REVEAL',target_id:'origin-focus',start_frame:0,duration_frames:15},
 {type:'AREA_GROW',target_id:'origin-focus',start_frame:0,duration_frames:24},
 {type:'AREA_REVEAL',target_id:'stage-footprint',start_frame:0,duration_frames:15},
 {type:'PROPAGATION_WAVE',target_id:'outward-wave',start_frame:15,duration_frames:135},
 {type:'IMPACT_ZONE',target_id:'coast-focus',start_frame:130,duration_frames:28},
 {type:'AREA_CONTRACT',target_id:'origin-focus',start_frame:135,duration_frames:30},
 {type:'STATE_TRANSITION',state_ids:['ORIGIN','COAST'],start_frame:145,duration_frames:30},
 {type:'TIME_STEP',state_ids:['COAST','HOLD'],start_frame:175,duration_frames:2},
 {type:'AREA_HOLD',start_frame:177,duration_frames:63}];
const areaPlan=compileAreaPlan(intent,{operations});
const finalBounds=fitGeographicExtent([138.2,34.8,146.0,42.2],{output:[1080,1920],padding:1.05});
const terrainRecord=await load('library/flat/terrain/ORIGINAL_SOURCE_RECORD.json');
const terrain={url:'/static/flat_assets/natural_earth_1_east_asia.png',file:'world-simulation-shorts-engine/web/flat_assets/natural_earth_1_east_asia.png',
 bounds:[104,7,152,63],dimensions:[2880,3360],pixelSpacing:[1/60,1/60],sha256:terrainRecord.sha256,
 classification:'BAKED HILLSHADE',license:terrainRecord.license,
 source:{name:terrainRecord.source_name,sha256:terrainRecord.source_original_sha256,url:terrainRecord.url,
  license:terrainRecord.license,crs:'EPSG:4326',version:terrainRecord.source_pinned_commit},
 lodPreparation:{method:'EXISTING_LOSSLESS_NATIVE_PIXEL_CROP_NO_UPSCALE_NO_NEW_TERRAIN'}};
const base=structuredClone(regionalTemplate);base.primary=primary.id;base.secondary=[];base.anchor.coordinates=origin;
base.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:finalBounds};base.geometries=countries;
base.assets.terrain=terrain;base.text={locationLabel:'',eventTitle:'동일본 쓰나미',watermark:''};
// This new fixture's origin annotation already names the occurrence. Avoid a
// duplicate location label; use the unchanged optional-information contract.
base.scale.information.location=false;
base.layout.countryLabels=[{text:'일본',coordinates:[139.8,36.6],geometry_ref:primary.id}];
base.layout.measured.event.maxWidth=390;base.layout.measured.event.maxWidthFraction=390/1080;
const REGIONAL=compileScalePlan(base,'REGIONAL',{allCountries:countries,eventGeometry:areaPlan.sweepGeometries});
REGIONAL.scale.information.location=false;
const CONTINENT=structuredClone(contextTemplate);CONTINENT.primary=primary.id;CONTINENT.secondary=[];CONTINENT.anchor.coordinates=origin;
CONTINENT.assets.terrain=terrain;CONTINENT.text=structuredClone(base.text);CONTINENT.layout=structuredClone(base.layout);
CONTINENT.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:fitGeographicExtent(geometryBounds(primary),{padding:1.08})};
const scene={primary_region_id:primary.id,primary_geometry:primary,event_anchor:origin,
 event_geometry:areaPlan.sweepGeometries,context_geometry:[],primary_label:'일본',location_label:base.text.locationLabel,event_title:base.text.eventTitle,
 canonical_output:[1080,1920],safe_area:base.layout.safe,
 approved_final_extent:finalBounds,desired_detail_level:'REGIONAL',
 scale_admission:{localDetail:{admission:{status:'LOCAL_NOT_ADMITTED',renderLocal:false},
  safeClosest:{bounds:finalBounds,status:'FACT_BASED_REGIONAL_VIEW_PENDING_NATIVE_AREA_AUDIT'}}}};
const cameraPlan=compileMinimumContextPlan({scene,seed:0});
const lock=cameraPlan.timeline.find(s=>s.state==='CAMERA_LOCK'||s.state==='DETAIL_LOCK'||s.state==='LOCK');
const firstLocked=cameraPlan.timeline.find(s=>s.state.includes('LOCK'))?.startFrame;
if(!Number.isSafeInteger(firstLocked))throw Error('CAMERA_NATIVE_LOCK_REQUIRED');
// Proof starts at the V5 arrival/settle segment, without changing the Director or its timing.
const cameraStartFrame=Math.max(0,firstLocked-30),eventStartFrame=firstLocked-cameraStartFrame;
const presentation={totalFrames:eventStartFrame+areaPlan.totalFrames,eventStartFrame,cameraStartFrame,
 videoFilename:'AREA_PROPAGATION_V3_TSUNAMI_CANDIDATE.mp4',propagationMedium:'WATER',impactMedium:'WATER',
 annotations:[{id:'ORIGIN',display_value:'2011.03.11',unit:'발생',source,anchor:origin},
  {id:'COAST',display_value:'해안 도달',unit:'확산 개념도',source,anchor:origin},
  {id:'HOLD',display_value:'해안 도달',unit:'확산 개념도',source,anchor:origin}],
 checkpoints:[{frame:0,file:'01_EVENT_ARRIVAL.png'},{frame:eventStartFrame+12,file:'02_ORIGIN.png'},
 {frame:eventStartFrame+35,file:'03_PROPAGATION_START.png'},{frame:eventStartFrame+80,file:'04_PROPAGATION_MID.png'},
 {frame:eventStartFrame+128,file:'05_COAST_APPROACH.png'},{frame:eventStartFrame+157,file:'06_IMPACT.png'},
 {frame:eventStartFrame+178,file:'07_STATE_TIME.png'},{frame:eventStartFrame+239,file:'08_FINAL_HOLD.png'}]};
await mkdir(path.join(root,'fixtures'),{recursive:true});await mkdir(path.join(root,'data'),{recursive:true});
for(const [p,v]of Object.entries({'REGIONAL-plan.json':REGIONAL,'CONTINENT-plan.json':CONTINENT,'scene.json':scene,'camera-plan.json':cameraPlan,
 'input-manifest.json':{heightSource:null,contextTerrain:terrain,output:[1080,1920],fps:30,
  demStatus:'EXISTING_DEM_NOT_APPLICABLE_TO_THIS_GEOGRAPHY_USING_EXISTING_BAKED_RELIEF_PATH',runtimeAsset:terrain},
 'REAL_FIXTURE.json':{schema:1,subject:'2011 Tohoku earthquake and tsunami',nativeFiles:Object.fromEntries([
 ['regionalPlan','REGIONAL-plan.json'],['continentPlan','CONTINENT-plan.json'],['scene','scene.json'],
 ['cameraPlan','camera-plan.json'],['inputManifest','input-manifest.json']].map(([k,f])=>[k,'recovery/event-area-propagation-v3/fixtures/'+f])),
 areaPlan,presentation,sourcePolicy:'PUBLIC_EVENT_FACTS_AND_AUTHORED_SCHEMATIC_PROPAGATION_NOT_PHYSICAL_SIMULATION',
 factIntegrity:{eventDate:'2011-03-11',origin:'Offshore east coast of Honshu',relation:'Pacific coast of Japan affected',
  displayedHeight:null,displayedSpeed:null,displayedArrivalTime:null,inundationExtentClaim:false},warnings:['OFFICIAL_SITE_RETRIEVAL_HTTP_403','SCHEMATIC_PROPAGATION_AND_COAST_FOCUS','NO_REGIONAL_DEM_USED']}}))await write('fixtures/'+p,v);
await write('data/PUBLIC_EVENT_REFERENCES.json',{schema:1,recordedAt:new Date().toISOString(),
 facts:{date:'2011-03-11',event:'Tohoku earthquake and tsunami',origin:[142.373,38.297],originPrecisionClaim:'REGIONAL_REFERENCE_POINT_NOT_SURVEY_GRADE',
  relationship:'Offshore Honshu source to Japanese Pacific coast'},
 references:[{agency:'USGS',url:'https://earthquake.usgs.gov/earthquakes/eventpage/official20110311054624120_30/executive',
  license:'US government public event facts',retrievalStatus:'HTTP_403_ENVIRONMENT_NETWORK_POLICY',downloadedDocumentSha256:null},
 {agency:'NOAA',url:'https://www.noaa.gov/news/march-11-2011-tohoku-earthquake-and-tsunami',license:'US government public event facts',
  retrievalStatus:'HTTP_403_ENVIRONMENT_NETWORK_POLICY',downloadedDocumentSha256:null}],
 provenance:'Previously published well-established event facts; live official documents were not retrieved in this restricted environment',
 visualDerivatives:'Authored concept contours and coastal focus, not measured inundation or wave solver',
 terrainOriginal:terrainRecord,geometrySource:primary.source??primary.provenance??null,
 geometrySha256:sha(Buffer.from(JSON.stringify(primary))),crs:'EPSG:4326',physicalSimulation:false});
await write('fixtures/RUNTIME_ROUTES.json',{runtime_routes:[...Object.entries({
 '/inputs/camera-plan.json':'fixtures/camera-plan.json','/inputs/input-manifest.json':'fixtures/input-manifest.json'}).map(([url,file])=>({url,file:'world-simulation-shorts-engine/recovery/event-area-propagation-v3/'+file})),
 {url:terrain.url,file:terrain.file}]});
console.log(JSON.stringify({finalBounds,totalFrames:presentation.totalFrames,duration:presentation.totalFrames/30,
 cameraFrames:cameraPlan.totalFrames,cameraStartFrame,eventStartFrame,lock:firstLocked,features:operations.map(o=>o.type)}));
