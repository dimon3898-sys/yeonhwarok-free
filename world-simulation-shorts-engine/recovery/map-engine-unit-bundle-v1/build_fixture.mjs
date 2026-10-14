/** New scene authoring only. Frozen control/camera and source actor data survive. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {DEFAULT_REFERENCE_TERRAIN_PROFILE_V4} from '../../web/map_infographic_v1/reference_terrain_material_v4.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame} from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,geoToPresentationScreen,presentationScreenToGeo}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,sampleControlBoundary} from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {nativeLandPoint} from '../planner-night-run-v1/build_fixture.mjs';
import {evaluateNationalUnitBadgeLayout,measureNationalUnitBadge} from '../../web/map_infographic_v1/national_unit_badge_v1.mjs';
const root=new URL('./',import.meta.url),old=new URL('../map-visual-upgrade-v1/',import.meta.url);
const read=async url=>JSON.parse(await readFile(url,'utf8'));
const save=async(name,value)=>{const url=new URL(name,root);await mkdir(new URL('./',url),{recursive:true});await writeFile(url,JSON.stringify(value,null,2)+'\n');};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const source=await read(new URL('fixtures/SCENE_PLAN.json',old)),runtime=await read(new URL('fixtures/RUNTIME_FIXTURE.json',old));
const cameraPlan=await read(new URL('../../'+runtime.nativeFiles.cameraPlan,root));
const native=await read(new URL('../planner-scene-json-v1/data/NATIVE_PENINSULA.json',root));
const flags=(await read(new URL('fixtures/NATIONAL_FLAG_PROFILES.json',root))).profiles;
const mapping={north_01:'PRC_1949',north_02:'DPRK_1948',north_03:'RUS_MODERN_TRICOLOR',south_01:'ROK_1949_TAEGEUK',
 south_02:'ROK_1949_TAEGEUK',south_03:'US_MODERN_50_STAR',south_04:'US_MODERN_50_STAR',south_05:'US_MODERN_50_STAR'};
const modernProfiles=Object.fromEntries([...new Set(Object.values(mapping))].map(id=>[id,structuredClone(flags[id])]));
assert.ok(Object.values(modernProfiles).every(p=>!p.private_only));
const track=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:runtime.currentNativeFrame,keyframes:source.cameraKeyframes,totalFrames:150,fps:30});
const presentation=compileReferencePresentationPlan({rollKeyframes:source.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),totalFrames:150,fps:30,overscan:source.presentationProfile.overscan,width:1080,height:1920});
const control=compileTerritoryControlPlan(source.controlIntent),safe=[48,72,1032,1848],size=104,margin=12;
const contexts=Array.from({length:150},(_,frame)=>{
 const camera=evaluateReferenceCameraTrackFrame(track,frame),state=evaluateReferencePresentationFrame(presentation,frame);
 const bounds=expandNativeBounds({bounds:camera.flatBounds,referenceStartBounds:track.startBounds,rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true});
 const controls=evaluateTerritoryControlFrame(control,frame),project=p=>geoToPresentationScreen(p,bounds,state),unproject=p=>presentationScreenToGeo(p,bounds,state);
 const segments=[];
 for(let i=1;i<controls.longitudinalKnots.length;i++){
  const a=[controls.longitudinalKnots[i-1],controls.boundaryLatitudes[i-1]],b=[controls.longitudinalKnots[i],controls.boundaryLatitudes[i]];
  // Sampling clips safety reservations only; rendered geography/front remain exact.
  for(let j=0;j<8;j++){const t=j/8,u=(j+1)/8,p=a.map((v,k)=>v+(b[k]-v)*t),q=a.map((v,k)=>v+(b[k]-v)*u),mid=p.map((v,k)=>(v+q[k])/2);
   if(nativeLandPoint(mid,{nativePeninsula:native}).mainland)segments.push([project(p),project(q)]);}
 }
 return {frame,state,bounds,controls,project,unproject,segments};
});
const distance=(p,a,b)=>{const dx=b[0]-a[0],dy=b[1]-a[1],l=dx*dx+dy*dy,t=l?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)):0;return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);};
const offsets=[];for(let y=-192;y<=192;y+=12)for(let x=-192;x<=192;x+=12)if(Math.hypot(x,y)<=192)offsets.push([x,y]);
offsets.sort((a,b)=>Math.hypot(...a)-Math.hypot(...b)||Math.abs(a[0])-Math.abs(b[0])||a[1]-b[1]||a[0]-b[0]);
const resolved=[],records=[];
for(const original of source.combatProfile.units){
 const profileId=mapping[original.id],isWinner=original.id.startsWith('south_'),frameCenters=contexts.map(c=>c.project(original.anchor_frames[c.frame]));
 const radii=original.rotation_frames.map(angle=>{const m=measureNationalUnitBadge({sizePx:size,rotationDegrees:angle});return Math.max(...m.normalizedSupport.map(p=>Math.hypot(...p)))*size;});
 const valid=(offset,frame)=>{
  const c=contexts[frame],center=frameCenters[frame].map((v,k)=>v+offset[k]),geo=c.unproject(center),radius=radii[frame];
  if(center[0]-radius<safe[0]||center[1]-radius<safe[1]||center[0]+radius>safe[2]||center[1]+radius>safe[3])return false;
  if(!nativeLandPoint(geo,{nativePeninsula:native}).mainland)return false;
  const winner=geo[1]<=sampleControlBoundary(c.controls,geo[0]);if(winner!==isWinner)return false;
  if(c.segments.some(([a,b])=>distance(center,a,b)<radius+margin))return false;
  if(resolved.some(other=>Math.hypot(...center.map((v,k)=>v-c.project(other.anchor_frames[frame])[k]))<size+8))return false;
  return true;
 };
 const coarse=[0,38,75,112,149],offset=offsets.find(o=>coarse.every(f=>valid(o,f))&&contexts.every(c=>valid(o,c.frame)));
 assert.ok(offset,'NO_SAFE_CONSTANT_SYMBOL_OFFSET '+original.id);
 const anchors=contexts.map(c=>c.unproject(frameCenters[c.frame].map((v,k)=>v+offset[k])));
 const unit={id:original.id,profile_id:profileId,role:'GROUND',anchor_frames:anchors,source_anchor_frames:structuredClone(original.anchor_frames),
  size_frames:Array(150).fill(size),rotation_frames:structuredClone(original.rotation_frames),screen_offset_pixels:offset,
  placement_semantics:'MAP_BADGE_LAYOUT_OFFSET_NOT_A_REAL_OR_HISTORICAL_UNIT_POSITION'};
 resolved.push(unit);
 const clearance=Math.min(...contexts.map(c=>Math.min(...c.segments.map(([a,b])=>distance(c.project(anchors[c.frame]),a,b)))-radii[c.frame]));
 records.push({id:unit.id,profileId,offsetPixels:offset,offsetLengthPixels:Math.hypot(...offset),minimumConservativeFrontierClearancePixels:clearance,allCentersOnNativeMainland:true,
  sourceAnchorsPreserved:true,frameMotionPolicy:'UNCHANGED_SOURCE_SCREEN_TRAJECTORY_PLUS_ONE_CONSTANT_OFFSET'});
}
let maximumStep=0;for(let f=0;f<150;f++){
 const c=contexts[f],layout=evaluateNationalUnitBadgeLayout(resolved,f,{project:c.project,safeArea:safe,protectedGraphics:[]});
 assert.equal(layout.safeAreaViolations.length,0);assert.equal(layout.criticalCollisions.length,0);assert.equal(layout.unitOverlaps.length,0);
 if(f)for(const u of resolved)maximumStep=Math.max(maximumStep,Math.hypot(...c.project(u.anchor_frames[f]).map((v,k)=>v-contexts[f-1].project(u.anchor_frames[f-1])[k])));
}
const scene=structuredClone(source);scene.schema=scene.version='MAP_ENGINE_UNIT_SCENE_V4';
scene.terrainProfile=structuredClone(DEFAULT_REFERENCE_TERRAIN_PROFILE_V4);
scene.frontierProfile={...scene.frontierProfile,profileName:'REAL_CONTROL_WARM_FRONTIER_V4',centerWidthPixels:1.8,centerColor:[1,.86,.56],haloColor:[1,.52,.14],
 centerAlpha:.94,haloAlpha:.22,haloSigmaPixels:2.1,haloSupportPixels:6.5,minimumLightingFactor:.83,luminanceAnchor:.36};
scene.style={...scene.style,profileName:'TERRAIN_READABLE_ORANGE_PURPLE_V4',losingColor:[186/255,30/255,11/255,.62],existingWinningColor:[104/255,23/255,229/255,.61],gainedWinningColor:[104/255,23/255,229/255,.61]};
scene.combatProfile={version:'ORIGINAL_NATIONAL_UNIT_BADGES_V1',units:resolved,profiles:modernProfiles,semantic_mode:'COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY',
 source_motion_sha256:sha(await readFile(new URL('fixtures/SCENE_PLAN.json',old))),sourceIconArtworkCopied:false,historicalPolicyApplied:false};
scene.metadata={...scene.metadata,factualBasis:'Existing modern counterfactual reference; control/camera unchanged. National flag badges are original representative map symbols, not surveyed military units.',
 publicHistoricalFixture:false,historicalPolicyScope:'PRIVATE_TEST_ONLY_PER_EXPLICIT_USER_SELECTION',allRenderedWords:false,unitPlacement:'CONSTANT_SCREEN_LAYOUT_OFFSET_WITH_PRESERVED_SOURCE_GEOGRAPHIC_ANCHORS',
 physicalElevationLightingClaimed:false,newMapEngineCreated:false,qualityParityClaimed:false};
assert.deepEqual(scene.controlIntent,source.controlIntent);assert.deepEqual(scene.cameraKeyframes,source.cameraKeyframes);assert.deepEqual(scene.presentationProfile,source.presentationProfile);
await save('fixtures/SCENE_PLAN.json',scene);
runtime.version='MAP_ENGINE_UNIT_RUNTIME_V4';runtime.videoFilename='WORLD_ENGINE_MAP_ENGINE_UNIT_BUNDLE_5S.mp4';
runtime.runtimeModuleFiles=[...new Set([...runtime.runtimeModuleFiles,...['map_engine_unit_gpu_adapter_v4.mjs','reference_terrain_material_v4.mjs','reference_ocean_material_v4.mjs','national_unit_badge_v1.mjs','unit_participation_policy_v1.mjs'].map(p=>'web/map_infographic_v1/'+p)])].sort();
await save('fixtures/RUNTIME_FIXTURE.json',runtime);
await save('fixtures/SOURCE_UNIT_BINDINGS.json',{parent:'882bd8e939010962b40a81c268937e7f7e88bb62',sourceUnits:source.combatProfile.units,modernCountryProfileMapping:mapping});
await save('evidence/FIXTURE_BUILD.json',{status:'PASS_READY_FOR_ACTUAL_STATIC',publicScenario:'UNCHANGED_MODERN_COUNTERFACTUAL',explicitUserSelection:true,historicalChecks:'PRIVATE_ONLY',
 geometryUnchanged:true,cameraUnchanged:true,originalDataUnchanged:true,newMapEngineCreated:false,newHistoricalSourceClaims:false,allRenderedWords:0,arrows:0,routes:0,
 symbolPlacement:{records,maximumConsecutiveCenterStepPixels:maximumStep,frontierReservationMarginPixels:margin,algorithm:'Generic nearest feasible CONSTANT_SCREEN_OFFSET over all150 unchanged projected frames',
  newSymbolGeographicAnchorsAreLayoutDerivatives:true,originalGeographicSourceAnchorsPersisted:true,realMilitaryPositionClaimed:false},requiredTempOnlyFiles:0,qualityPassClaimed:false});
console.log(JSON.stringify({status:'FIXTURE_BUILT',units:resolved.length,maximumStep,placements:records.map(r=>({id:r.id,offset:r.offsetPixels,clearance:r.minimumConservativeFrontierClearancePixels}))}));
