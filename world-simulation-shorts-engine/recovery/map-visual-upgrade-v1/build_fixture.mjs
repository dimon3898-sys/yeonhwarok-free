/** Additive visual profiles over the immutable saved 65406 scene. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {DEFAULT_REFERENCE_TERRAIN_PROFILE_V3} from '../../web/map_infographic_v1/reference_terrain_material_v3.mjs';
import {validateControlFrontierLightProfile} from '../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
const root=new URL('./',import.meta.url),old=new URL('../reference-quality-rework-v2/',import.meta.url);
const read=async url=>JSON.parse(await readFile(url,'utf8'));
const save=async(name,value)=>{const url=new URL(name,root);await mkdir(new URL('./',url),{recursive:true});
 await writeFile(url,JSON.stringify(value,null,2)+'\n');};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previous=await read(new URL('fixtures/SCENE_PLAN.json',old)),scene=structuredClone(previous);
scene.version=scene.schema='MAP_VISUAL_SCENE_V3';
scene.metadata={...scene.metadata,designTarget:'USER_PROVIDED_INLINE_MAP_OCEAN_DESIGN_CONCEPT',
 conceptUsedAsGeometry:false,conceptUsedAsBackground:false,qualityParityClaimed:false,
 factualBasis:'Unchanged saved country GIS and counterfactual reference control/motion; original WORLD ENGINE infantry artwork.',
 materialDataLimit:'Existing licensed NE1 baked relief, no Korea DEM or invented geographic detail.',
 actualReferenceMotionUnchanged:true,sourcePhoneUIAndCaptionsExcluded:true};
scene.style={profileName:'WORLD_ENGINE_CLEAR_ORANGE_PURPLE_TERRAIN_V3',
 losingColor:[186/255,30/255,11/255,.68],existingWinningColor:[104/255,23/255,229/255,.65],
 gainedWinningColor:[104/255,23/255,229/255,.65],interfaceColor:[1,1,1,0],interfaceWidthPixels:0,
 sharedDomainBoundary:'CONTROL_MATERIAL_REPLACES_INTERNAL_SEPARATOR'};
scene.terrainProfile=structuredClone(DEFAULT_REFERENCE_TERRAIN_PROFILE_V3);
Object.assign(scene.terrainProfile,{landContrast:1.8,bakedShadeLocalContrast:.65,warmHighlightStrength:.10});
Object.assign(scene.terrainProfile.oceanProfile,{nearshoreMix:.30,microStrength:.015,glintStrength:.008});
scene.frontierProfile=structuredClone(validateControlFrontierLightProfile({profileName:'REAL_MOVING_CONTROL_WARM_EDGE_V3'}));
scene.frontierProfile.minimumLightingFactor=.74;
scene.combatProfile=await read(new URL('fixtures/ORIGINAL_UNIT_PROFILE.json',root));
// Executed public Scene carries temporal data, never private repository paths.
if(scene.combatProfile.source_motion)delete scene.combatProfile.source_motion.path;
assert.deepEqual(scene.controlIntent,previous.controlIntent);
assert.deepEqual(scene.cameraKeyframes,previous.cameraKeyframes);
assert.deepEqual(scene.presentationProfile,previous.presentationProfile);
for(const unit of scene.combatProfile.units){const before=previous.combatProfile.units.find(row=>row.id===unit.id);
 assert.ok(before);assert.deepEqual(unit.anchor_frames,before.anchor_frames);assert.deepEqual(unit.rotation_frames,before.rotation_frames);}
await save('fixtures/SCENE_PLAN.json',scene);
const runtime=await read(new URL('fixtures/RUNTIME_FIXTURE.json',old));
runtime.version='MAP_VISUAL_UPGRADE_RUNTIME_V3';runtime.videoFilename='WORLD_ENGINE_MAP_VISUAL_UPGRADE_5S.mp4';
runtime.runtimeModuleFiles=[...new Set([...runtime.runtimeModuleFiles,
 ...['map_visual_gpu_adapter_v3.mjs','reference_terrain_material_v3.mjs','reference_ocean_material_v3.mjs',
 'reference_control_frontier_light_v3.mjs','world_engine_unit_overlay_v3.mjs'].map(name=>'web/map_infographic_v1/'+name)])].sort();
await save('fixtures/RUNTIME_FIXTURE.json',runtime);
await save('evidence/FIXTURE_BUILD.json',{status:'READY_FOR_ACTUAL_STATIC_PROBE',parent:'386b4319c527fe8687b52f5ca2ed24886607e0ed',
 unchanged:['controlIntent','cameraKeyframes','presentationProfile','all8AnchorSequences','all8RotationSequences','nativeFiles','inheritedAdmissionFiles'],
 geometryRegenerated:false,timelineRetimed:false,sourceMovieBackground:false,originalArtwork:true,
 sourceSceneSHA256:sha(await readFile(new URL('fixtures/SCENE_PLAN.json',old))),
 sceneSHA256:sha(await readFile(new URL('fixtures/SCENE_PLAN.json',root))),
 requiredTempOnlyFiles:0,qualityParityClaimed:false,userVideoApproved:false});
console.log(JSON.stringify({status:'FIXTURE_READY',version:scene.version,units:scene.combatProfile.units.length,
 frames:runtime.totalFrames,modules:runtime.runtimeModuleFiles.length}));
