/** Fixture wiring only: existing geographic Scale and Camera V5 own all framing calculations. */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileSceneEngineRequest} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {compileMinimumContextPlan} from '../../web/map_infographic_v1/camera_director_v5.mjs';
import {compileScalePlan,fitGeographicExtent,geometryBounds} from '../../web/map_infographic_v1/scale_contract.mjs';

export const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..');
const load=async file=>JSON.parse(await readFile(path.join(engine,file),'utf8'));
const write=async(file,value)=>writeFile(path.join(root,file),JSON.stringify(value,null,2)+'\n');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');

export async function prepareNativeInputs({scene,facts,checkpoints,videoFilename}){
 const request=compileSceneEngineRequest(scene),context=request.cameraRequest.nativeContext;
 if(!context.primary_country_id||!Array.isArray(context.secondary_country_ids))
  throw Error('PLANNER_NATIVE_COUNTRY_CONTEXT_REQUIRED');
 const regionalTemplate=await load('recovery/event-area-propagation-v3/fixtures/REGIONAL-plan.json');
 const contextTemplate=await load('recovery/event-area-propagation-v3/fixtures/CONTINENT-plan.json');
 const countries=contextTemplate.geometries,primary=countries.find(record=>record.id===context.primary_country_id);
 const secondary=context.secondary_country_ids.map(id=>countries.find(record=>record.id===id));
 if(!primary||secondary.some(record=>!record))throw Error('PLANNER_REGISTERED_COUNTRY_GEOMETRY_REQUIRED');
 const framingGeometry=[primary,...secondary,...request.areaPlan.sweepGeometries,...request.cameraRequest.targetGeometries];
 const bounding=framingGeometry.map(geometryBounds);
 const fullBounds=[Math.min(...bounding.map(b=>b[0])),Math.min(...bounding.map(b=>b[1])),
  Math.max(...bounding.map(b=>b[2])),Math.max(...bounding.map(b=>b[3]))];
 // Universal geographic aspect fit and padding come from the existing Scale API.
 const finalBounds=fitGeographicExtent(fullBounds,{output:[scene.metadata.output.width,scene.metadata.output.height],padding:1.18});
 const terrain=structuredClone(regionalTemplate.assets.terrain),anchor=request.cameraRequest.anchor;
 const requestedLabels=structuredClone(facts.native_labels??[]);
 // The frozen COUNTRY layout validates interior candidates against its primary
 // geometry. Do not feed unsupported secondary labels into that owner.
 const labels=requestedLabels.filter(label=>label.geometry_ref===context.primary_country_id);
 const skippedLabels=requestedLabels.filter(label=>label.geometry_ref!==context.primary_country_id)
  .map(label=>({geometry_ref:label.geometry_ref,text:label.text,
   reason:'FROZEN_COUNTRY_LAYOUT_OWNS_PRIMARY_INTERIOR_ONLY'}));
 if(!labels.length)throw Error('PLANNER_NATIVE_GEOGRAPHIC_LABEL_DATA_REQUIRED');
 const marker=scene.markers?.[0]??null;
 if(marker&&JSON.stringify(marker.anchor)!==JSON.stringify(anchor))throw Error('PLANNER_NATIVE_MARKER_ANCHOR_BINDING_REQUIRED');
 const locationLabel=marker?.label??'';
 const base=structuredClone(regionalTemplate);
 delete base._recovery;
 base.primary=primary.id;base.secondary=secondary.map(record=>record.id);base.anchor.coordinates=anchor;
 base.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:finalBounds};base.geometries=countries;
 base.assets.terrain=terrain;base.text={locationLabel,eventTitle:scene.subject.label,watermark:''};
 base.scale.information.location=Boolean(locationLabel);base.layout.countryLabels=labels;
 const REGIONAL=compileScalePlan(base,'REGIONAL',{allCountries:countries,eventGeometry:request.areaPlan.sweepGeometries});
 REGIONAL.scale.information.location=Boolean(locationLabel);
 const continentBase=structuredClone(base);
 continentBase.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:fitGeographicExtent(fullBounds,{padding:1.35})};
 const CONTINENT=compileScalePlan(continentBase,'CONTINENT',{allCountries:countries,eventGeometry:request.areaPlan.sweepGeometries,padding:1.35});
 const nativeScene={primary_region_id:primary.id,primary_geometry:primary,event_anchor:anchor,
  event_geometry:request.areaPlan.sweepGeometries,context_geometry:secondary,
  primary_label:labels.find(row=>row.geometry_ref===primary.id)?.text??scene.subject.label,
  location_label:locationLabel,event_title:scene.subject.label,canonical_output:[1080,1920],safe_area:base.layout.safe,
  approved_final_extent:finalBounds,desired_detail_level:request.cameraRequest.scale,
  scale_admission:{localDetail:{admission:{status:'LOCAL_NOT_ADMITTED',renderLocal:false},
   safeClosest:{bounds:finalBounds,status:'FACT_BASED_VISUAL_REGIONAL_CURRENT_VIEW_PENDING_RENDER'}}}};
 const cameraPlan=compileMinimumContextPlan({scene:nativeScene,seed:0});
 const firstLocked=cameraPlan.timeline.find(segment=>segment.state.includes('LOCK'))?.startFrame;
 if(!Number.isSafeInteger(firstLocked)||firstLocked<request.timing.eventStartFrame)
  throw Error('PLANNER_EXISTING_V5_ARRIVAL_LOCK_REQUIRED');
 const cameraStartFrame=firstLocked-request.timing.eventStartFrame;
 const presentation={totalFrames:request.timing.totalFrames,eventStartFrame:request.timing.eventStartFrame,
  cameraStartFrame,videoFilename,propagationMedium:'LAND',impactMedium:'LAND',
  annotations:request.annotations,checkpoints};
 const nativeFiles=Object.fromEntries(Object.entries({regionalPlan:'REGIONAL-plan.json',continentPlan:'CONTINENT-plan.json',
  scene:'scene-native.json',cameraPlan:'camera-plan.json',inputManifest:'input-manifest.json'})
  .map(([key,file])=>[key,'recovery/planner-scene-json-v1/fixtures/'+file]));
 const runtime={schema:1,subject:scene.subject.label,scenePlanPath:'recovery/planner-scene-json-v1/fixtures/SCENE_PLAN.json',
  nativeFiles,presentation,sourceGeometryBinding:request.sourceGeometryBinding,
  sourcePolicy:'FACT_BASED_VISUAL_GRADE_SUPPLIED_SCHEMATIC_STATE_BOUNDARIES_NOT_SURVEY_CONTROL_MAP',
  nativeGraphicsBinding:{primaryCountryLabels:labels,skippedCountryLabels:skippedLabels,
   marker:marker?{id:marker.id,anchor:marker.anchor,label:marker.label}:null,
   locationInformation:REGIONAL.scale.information.location,styles:'UNCHANGED_NATIVE_GLYPH_MARKER_LAYOUT'},
  cameraDecision:{decision:'USE_CURRENT_VIEW',core:'UNCHANGED_CAMERA_DIRECTOR_V5',
   derivedFrom:'Scene geometry + supplied registered context countries + existing geographic aspect fit',
   finalBounds,firstLocked,cameraStartFrame,eventStartFrame:request.timing.eventStartFrame}};
 await mkdir(path.join(root,'fixtures'),{recursive:true});
 for(const [file,value]of Object.entries({'REGIONAL-plan.json':REGIONAL,'CONTINENT-plan.json':CONTINENT,
  'scene-native.json':nativeScene,'camera-plan.json':cameraPlan,
  'input-manifest.json':{heightSource:null,contextTerrain:terrain,output:[1080,1920],fps:scene.timing.fps,
   demStatus:'EXISTING_BAKED_RELIEF_FACTORY_PATH',runtimeAsset:terrain},'RUNTIME_FIXTURE.json':runtime,
  'ENGINE_REQUEST.json':request}))await write('fixtures/'+file,value);
 await write('fixtures/NATIVE_INPUT_BINDING.json',{schema:1,status:'PASS',cameraCoreUnchanged:true,
  nativeRegisteredCountryIds:[primary.id,...secondary.map(record=>record.id)],
  geometrySourceSha256:sha(Buffer.from(JSON.stringify(scene.geometries))),
  nativeContextSource:'Inherited registered Natural Earth country geometry and terrain assets',
  sourceGeometryMutated:false,rendererDuplicated:false,finalBounds,skippedCountryLabels:skippedLabels,
  locationLabel,markerAnchor:anchor,
  cameraStartFrame,eventStartFrame:request.timing.eventStartFrame,firstLocked,totalFrames:presentation.totalFrames});
 await write('fixtures/RUNTIME_ROUTES.json',{runtime_routes:[
  {url:'/inputs/camera-plan.json',file:'world-simulation-shorts-engine/'+nativeFiles.cameraPlan},
  {url:'/inputs/input-manifest.json',file:'world-simulation-shorts-engine/'+nativeFiles.inputManifest},
  {url:terrain.url,file:terrain.file}]});
 return {request,runtime,nativeScene,cameraPlan};
}
