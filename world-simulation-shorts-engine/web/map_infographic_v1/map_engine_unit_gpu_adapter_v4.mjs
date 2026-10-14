/** Isolated map engine and national-unit orchestration over the existing native APIs.
 * Every FINAL source remains read-only. The scene owns its new material, camera
 * presentation and measured combat overlays; this adapter does not infer story.
 */
import * as THREE from '/three.js';
import {createMapInfographicRenderer} from './renderer.mjs';
import {createTerritoryControlPass} from './territory_control_gpu_adapter_v1.mjs';
import {assertTerritoryControlPlan,evaluateTerritoryControlFrame} from './territory_control_adapter_v1.mjs';
import {assertReferenceCameraTrackPlan,evaluateReferenceCameraTrackFrame} from './reference_camera_adapter_v1.mjs';
import {createReferenceTerrainMaterialPassV4} from './reference_terrain_material_v4.mjs';
import {createControlFrontierLightPassV3} from './reference_control_frontier_light_v3.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,
 projectNativePoint,createReferencePresentationPass} from './reference_presentation_adapter_v2.mjs';
import {createNationalUnitBadgeOverlay} from './national_unit_badge_v1.mjs';

export const MAP_ENGINE_UNIT_GPU_ADAPTER_V4_VERSION='MAP_ENGINE_UNIT_GPU_ADAPTER_V4';
const WIDTH=1080,HEIGHT=1920;
const clone=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const box=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)
 &&value[0]<value[2]&&value[1]<value[3];
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))]
 .map(v=>v.toString(16).padStart(2,'0')).join('');

function inputRecord({plans,cameraPlan,scene,cameraTrack,territoryPlan,scenePlan}){
 const regional=plans?.REGIONAL;
 if(!regional||!plans.CONTINENT||!box(regional.layout?.safe)||!scenePlan
  ||scenePlan.version!=='MAP_ENGINE_UNIT_SCENE_V4'||scenePlan.schema!=='MAP_ENGINE_UNIT_SCENE_V4'
  ||!Array.isArray(scenePlan.cameraKeyframes)
  ||scenePlan.cameraKeyframes.length<2||!scenePlan.terrainProfile||!scenePlan.presentationProfile
  ||!scenePlan.combatProfile||!scenePlan.style||!scenePlan.frontierProfile)
  throw Error('MAP_ENGINE_UNIT_EXPLICIT_SCENE_V4_REQUIRED');
 if(!same(cameraTrack.baseCameraPlan,cameraPlan)||scene?.primary_region_id!==regional.primary
  ||cameraTrack.totalFrames!==territoryPlan.totalFrames||cameraTrack.fps!==territoryPlan.fps)
  throw Error('MAP_ENGINE_UNIT_FROZEN_CAMERA_CONTROL_BINDING_REQUIRED');
 if(!same(scenePlan.cameraKeyframes.map(k=>({frame:k.frame,bounds:k.bounds})),cameraTrack.keyframes))
  throw Error('MAP_ENGINE_UNIT_SCENE_CAMERA_KEYFRAME_BINDING_REQUIRED');
 if(!same(scenePlan.style.existingWinningColor,scenePlan.style.gainedWinningColor))
  throw Error('MAP_VISUAL_UNIFIED_WINNING_TERRITORY_MATERIAL_REQUIRED');
 if(scenePlan.style.interfaceWidthPixels!==0||scenePlan.style.interfaceColor?.[3]!==0)
  throw Error('MAP_ENGINE_UNIT_DECORATIVE_FRONT_STROKE_FORBIDDEN');
 if(!Array.isArray(scenePlan.combatProfile.units)||!scenePlan.combatProfile.profiles
  ||typeof scenePlan.combatProfile.profiles!=='object'||Array.isArray(scenePlan.combatProfile.profiles))
  throw Error('MAP_ENGINE_UNIT_MEASURED_COMBAT_PROFILE_REQUIRED');
 return regional;
}

/** Reuse an existing, persisted FACT-based native framing floor. The new
 * presentation must remain WIDER than that floor on every native frame.
 * This accepts neither a new survey certificate nor a newly weakened limit.
 */
function inheritedNativeFloor(input,controlPlan){
 const receipt=input?.visualAdmission;
 if(!input||!box(input.bounds)||!receipt||receipt.status!=='VISUAL_REFERENCE_ADMITTED'
  ||receipt.grade!=='FACT_BASED_VISUAL_GRADE'||receipt.evidenceKind!=='ACTUAL_NATIVE_STATIC_PROBE'
  ||receipt.surveyAdmissionModified!==false||!same(receipt.output,[WIDTH,HEIGHT])
  ||receipt.domainGeometryBinding!==controlPlan.domainGeometryBinding
  ||typeof input.sha256!=='string'||!/^[a-f0-9]{64}$/.test(input.sha256)
  ||!Array.isArray(receipt.samples)||!receipt.samples.length
  ||receipt.samples.some(sample=>sample.visual!=='VISUAL_PASS'||!/^[a-f0-9]{64}$/.test(sample.pngSha256)))
  throw Error('MAP_ENGINE_UNIT_EXISTING_PERSISTED_VISUAL_NATIVE_FLOOR_REQUIRED');
 let keys;
 try{keys=JSON.parse(receipt.cameraKeyframeBinding);}catch{throw Error('MAP_ENGINE_UNIT_ADMITTED_CAMERA_BINDING_REQUIRED');}
 if(!Array.isArray(keys)||keys.length<2||!same(keys.at(-1)?.bounds,input.bounds))
  throw Error('MAP_ENGINE_UNIT_NATIVE_FLOOR_MUST_MATCH_EXISTING_ADMITTED_ENDPOINT');
 return{bounds:clone(input.bounds),sourceSha256:input.sha256,
  grade:receipt.grade,status:receipt.status,source:'EXISTING_PERSISTED_VISUAL_ADMISSION',
  surveyAdmissionModified:false,newThresholdLowered:false};
}

/** One actual native factory draws the source/GIS frame. A new licensed source
 * terrain/ocean material and the unchanged complementary control pass then draw on
 * that same geographic projection. Actual terrain relief survives control fill
 * through a land-clipped destination light multiplier; the exact current scalar
 * boundary owns its restrained highlight. A uniform presentation roll transforms the
 * whole authentic map together; fixture-resolved, map-anchored national tablets draw afterward.
 * No date/country/story inference happens in this GPU pass. Historical admission
 * is a separate private fixture policy; the caller owns this public scenario.
 * Optional native shot labels/title/marker are explicitly omitted, with their
 * underlying source and design unchanged. No native foreground pixel identity
 * is claimed for a shot whose scene deliberately hides those roles.
 */
export async function createMapEngineUnitGpuAdapterV4({canvas,plans,cameraPlan,scene,
 heightSource=null,contextTerrain=null,cameraTrack,territoryPlan,scenePlan,admittedNativeFraming}={}){
 const track=assertReferenceCameraTrackPlan(cameraTrack),control=assertTerritoryControlPlan(territoryPlan),
  regional=inputRecord({plans,cameraPlan,scene,cameraTrack:track,territoryPlan:control,scenePlan}),
  nativeFloor=inheritedNativeFloor(admittedNativeFraming,control),
  sourceBinding=JSON.stringify({plans,cameraPlan,scene,heightSource,contextTerrain,cameraTrack,territoryPlan,scenePlan,admittedNativeFraming}),
  sourceGeometryBinding=JSON.stringify({native:[...regional.geometries,...plans.CONTINENT.geometries],
   event:control.intent.domain}),sourceGeometrySha256=await digest(sourceGeometryBinding),
  safeArea=clone(regional.layout.safe),
  presentationPlan=compileReferencePresentationPlan({
   rollKeyframes:scenePlan.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
   totalFrames:track.totalFrames,fps:track.fps,overscan:scenePlan.presentationProfile.overscan,
   width:WIDTH,height:HEIGHT}),
  finalPresentation=evaluateReferencePresentationFrame(presentationPlan,track.totalFrames-1),
  finalBounds=expandNativeBounds({bounds:track.targetBounds,referenceStartBounds:track.startBounds,
   rollDegrees:finalPresentation.rollDegrees,overscan:finalPresentation.overscan,
   width:WIDTH,height:HEIGHT,correctMeasuredPan:true}),
  endpointPlan=clone(regional),
  floorSpan=[nativeFloor.bounds[2]-nativeFloor.bounds[0],nativeFloor.bounds[3]-nativeFloor.bounds[1]],
  checkedNativeBounds=Array.from({length:track.totalFrames},(_,frame)=>{
   const position=evaluateReferenceCameraTrackFrame(track,frame),state=evaluateReferencePresentationFrame(presentationPlan,frame),
    bounds=expandNativeBounds({bounds:position.flatBounds,referenceStartBounds:track.startBounds,
     rollDegrees:state.rollDegrees,overscan:state.overscan,width:WIDTH,height:HEIGHT,correctMeasuredPan:true});
   if(bounds[2]-bounds[0]<floorSpan[0]-1e-9||bounds[3]-bounds[1]<floorSpan[1]-1e-9)
    throw Error('MAP_ENGINE_UNIT_NEW_NATIVE_VIEW_EXCEEDS_INHERITED_VISUAL_FLOOR');
   return bounds;
  }),minimumNativeSpan=[Math.min(...checkedNativeBounds.map(b=>b[2]-b[0])),
   Math.min(...checkedNativeBounds.map(b=>b[3]-b[1]))];
 if(!canvas||canvas.width!==WIDTH||canvas.height!==HEIGHT||!box(finalBounds))
  throw Error('MAP_ENGINE_UNIT_CANONICAL_OUTPUT_REQUIRED');
 endpointPlan.framing={...endpointPlan.framing,bounds:clone(nativeFloor.bounds),
  center:[(nativeFloor.bounds[0]+nativeFloor.bounds[2])/2,(nativeFloor.bounds[1]+nativeFloor.bounds[3])/2]};
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('MAP_ENGINE_UNIT_WEBGL2_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(WIDTH,HEIGHT,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 let factory,terrain,territory,frontier,presentation,combat,disposed=false,last=null,pixels=null;
 let currentPresentation=null,currentBounds=null;
 const hiddenReveal={primary:1,marker:0,location:0,country:0,title:0,disclosure:0};
 try{
  factory=await createMapInfographicRenderer({canvas,plan:regional,layoutPlan:endpointPlan,
   contextTerrain:contextTerrain??plans.CONTINENT.assets.terrain,
   contextGeometries:plans.CONTINENT.geometries,heightSource,width:WIDTH,height:HEIGHT,
   outputRenderer:renderer,outputTarget:null});
  terrain=await createReferenceTerrainMaterialPassV4({canvas,source:regional.assets.terrain,
   profile:scenePlan.terrainProfile,width:WIDTH,height:HEIGHT});
  territory=createTerritoryControlPass({canvas,landDomain:control.intent.domain,style:scenePlan.style});
  frontier=await createControlFrontierLightPassV3({canvas,width:WIDTH,height:HEIGHT,
   landDomain:control.intent.domain,territoryPlan:control,profile:scenePlan.frontierProfile});
  presentation=await createReferencePresentationPass({canvas,width:WIDTH,height:HEIGHT});
  combat=await createNationalUnitBadgeOverlay({canvas,width:WIDTH,height:HEIGHT,
   units:scenePlan.combatProfile.units,profiles:scenePlan.combatProfile.profiles});
  if(combat.fixture?.frames!==track.totalFrames)
   throw Error('MAP_ENGINE_UNIT_COMBAT_FRAME_COUNT_BINDING_REQUIRED');
  if(combat.evidence?.noRenderedText!==true||combat.evidence?.flagsFromFixture!==true
   ||combat.evidence?.sourceIconArtworkCopied!==false||combat.evidence?.historicalPolicyApplied!==false)
   throw Error('MAP_ENGINE_UNIT_EXPLICIT_ORIGINAL_NO_TEXT_FLAG_ARTWORK_REQUIRED');
  const project=geo=>{
   if(disposed)throw Error('MAP_ENGINE_UNIT_ADAPTER_DISPOSED');
   if(!currentPresentation||!currentBounds)throw Error('MAP_ENGINE_UNIT_PROJECT_REQUIRES_ACTUAL_FRAME');
   return projectNativePoint(factory.screen(geo),currentPresentation);
  };
  function readPixels(){
   if(disposed)throw Error('MAP_ENGINE_UNIT_ADAPTER_DISPOSED');
   if(!last)throw Error('MAP_ENGINE_UNIT_READ_REQUIRES_FRAME');
   if(!pixels){pixels=factory.readPixels();const error=gl.getError();
    if(error!==gl.NO_ERROR)throw Error('MAP_ENGINE_UNIT_READ_PIXELS_GL_ERROR_'+error);}
   return pixels;
  }
  function drawFrame(frame,{territoryEnabled=true,combatEnabled=true,frontierEnabled=true}={}){
   if(disposed)throw Error('MAP_ENGINE_UNIT_ADAPTER_DISPOSED');
   if(typeof territoryEnabled!=='boolean'||typeof combatEnabled!=='boolean'||typeof frontierEnabled!=='boolean')
    throw Error('MAP_ENGINE_UNIT_DRAW_BOOLEAN_REQUIRED');
   const renderStarted=performance.now();
   const schedule=evaluateReferenceCameraTrackFrame(track,frame),
    state=evaluateReferencePresentationFrame(presentationPlan,frame),
    bounds=expandNativeBounds({bounds:schedule.flatBounds,referenceStartBounds:track.startBounds,
     rollDegrees:state.rollDegrees,overscan:state.overscan,width:WIDTH,height:HEIGHT,
     correctMeasuredPan:true});
   currentPresentation=state;currentBounds=bounds;pixels=null;
   factory.updateCamera(bounds);
   // Both available regional/wide inputs are verified actual rasters. This
   // source ablation keeps the native factory alive without its old material.
   factory.setTerrainLod(0);
   const native=factory.renderFrame({mode:5,graphics:false,boundaries:false,glow:false,dem:false,
    reveal:hiddenReveal,primaryMaterial:1});
   if(native.glError!==gl.NO_ERROR)throw Error('MAP_ENGINE_UNIT_NATIVE_GL_ERROR_'+native.glError);
   const coverage=factory.coverage(),terrainDiagnostic=terrain.draw({bounds,coverage,frame,fps:track.fps}),
    controls=evaluateTerritoryControlFrame(control,control.startFrame+frame),
    territoryDiagnostic=territoryEnabled?territory.draw({controls,project:geo=>factory.screen(geo),
     safeArea:[0,0,WIDTH,HEIGHT],protectedGraphics:[],boundarySegments:[],internalBoundarySegments:[]}):null,
    frontierDiagnostic=territoryEnabled&&frontierEnabled?frontier.draw({controls,project:geo=>factory.screen(geo),actualTerrainTexture:terrain.outputTexture,
     presentationScale:state.overscan,safeArea:[0,0,WIDTH,HEIGHT],protectedGraphics:[]}):null,
    presentationDiagnostic=presentation.draw({state}),
    units=combatEnabled?combat.draw({frame,project,protectedGraphics:[],safeArea}):
     {units:[],flags:0,safeAreaViolations:[],criticalCollisions:[],unitOverlaps:[],enabled:false,noRenderedText:true};
   if(units.noRenderedText!==true||units.flags!==units.units.length)
    throw Error('MAP_ENGINE_UNIT_ACTUAL_NATIONAL_FLAG_NO_TEXT_RENDER_REQUIRED');
   const nationalUnits={...units,noText:units.noRenderedText,nationalFlags:true,
    national_flag_ids:units.units.map(item=>scenePlan.combatProfile.profiles[item.profile_id].id),
    national_country_ids:units.units.map(item=>scenePlan.combatProfile.profiles[item.profile_id].country_id),
    resolvedCountries:units.units.map(item=>({id:item.id,profile_id:item.profile_id,
     country_id:scenePlan.combatProfile.profiles[item.profile_id].country_id,
     role:scenePlan.combatProfile.units.find(unit=>unit.id===item.id).role
      ??scenePlan.combatProfile.profiles[item.profile_id].default_role??'GROUND'})),
    actualFlagPanelArt:true,countrySelectionOwner:'EXPLICIT_CALLER_UNIT_FIXTURE',historicalAdmissionInPublicShader:false};
   gl.finish();
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('MAP_ENGINE_UNIT_COMPOSITION_GL_ERROR_'+glError);
   const actualBinding=JSON.stringify({plans,cameraPlan,scene,heightSource,contextTerrain,cameraTrack,territoryPlan,scenePlan,admittedNativeFraming});
   if(actualBinding!==sourceBinding)throw Error('MAP_ENGINE_UNIT_PROTECTED_INPUT_MUTATION');
   if(JSON.stringify({native:[...regional.geometries,...plans.CONTINENT.geometries],event:control.intent.domain})!==sourceGeometryBinding)
    throw Error('MAP_ENGINE_UNIT_SOURCE_GEOMETRY_MUTATED');
   last={version:MAP_ENGINE_UNIT_GPU_ADAPTER_V4_VERSION,frame,state:'MAP_ENGINE_AND_NATIONAL_UNIT_BUNDLE',
    camera:{...clone(schedule),bounds:clone(schedule.flatBounds),nativeExpandedBounds:clone(bounds),rollDegrees:state.rollDegrees,
     rotationDegrees:state.rollDegrees,
     overscan:state.overscan,referenceFraming:clone(schedule.flatBounds),cameraLocked:false,
     nativeProjectionSourceUnchanged:true,coherentPresentationProjection:true},
    cameraLocked:false,settle:{phase:'MEASURED_REFERENCE_MOTION',settled:false,locked:false},
    gpu:{stage:'ISOLATED_SOURCE_MAP_MATERIAL_AND_NATIONAL_UNIT_EXTENSION',factoryCount:1,nativeDrawCount:1,glError,
     actualCamera:clone(factory.evidence.cameraFrame),actualReveal:clone(factory.evidence.revealState),
     completedRenderWallMs:performance.now()-renderStarted,completionMeasuredAfterGlFinish:true,
     rawSourceNativeFrame:true,displayedNativeForeground:false,layoutValidation:{valid:true,failures:[]}},
    terrain:terrainDiagnostic,frontierLight:frontierDiagnostic?{...frontierDiagnostic,
     realControlBoundaryDerived:true,standaloneDecorativeLine:false}:null,presentation:presentationDiagnostic,units:nationalUnits,
    territory:{enabled:territoryEnabled,graphics:territoryDiagnostic,
     domainGeometryBinding:control.domainGeometryBinding,boundaryKeyframeBinding:control.boundaryKeyframeBinding,
     movingBoundaryHighlight:Boolean(frontierDiagnostic),realControlBoundaryDerived:Boolean(frontierDiagnostic),
     standaloneDecorativeLine:false,geometryUnchanged:true,continuousComplementaryOwnership:true,standaloneFrontLine:false,
     routeVisuals:false,arrowVisuals:false,controls,material:clone(scenePlan.style),
     sourceGeometrySha256,layer:'LAND_BACKGROUND_MATERIAL_BEFORE_MAP_ANCHORED_COMBAT'},
    protection:{sourceUnchanged:true,nativeVisualCoreUnchanged:true,sourceGeometryUnchanged:true,
     displayedNativeForeground:false,sourceGeometrySha256,
     verification:'BOUND_IMMUTABLE_INPUT_JSON_AND_EXTERNAL_PERSISTED_SOURCE_SHA',
     nativeForegroundChoice:'NEW_SHOT_EXPLICIT_OPTIONAL_GRAPHICS_FALSE',nativeForegroundPixelIdentityClaimed:false,
     nativeVisualCoreStyleSourceUnchanged:true,oldShotAndFinalOutputModified:false},
    sourceV5Unchanged:true,surveyAdmissionPreserved:true,surveyAdmission:clone(schedule.admission),
    nativeEndpointGuardActive:true,nativeFramingFloor:{...clone(nativeFloor),minimumNativeSpan:clone(minimumNativeSpan),
     framesChecked:track.totalFrames,allNativeFramesWiderThanInheritedFloor:true},qualityParityClaimed:false,
    decorativeLines:0,arrows:0,routeTraces:0,standaloneFrontStrokes:0,controlBoundaryHighlightEnabled:Boolean(frontierDiagnostic),
    renderedWords:0,noRenderedText:true,nationalUnitArtOriginal:true,nationalFlagsFromFixture:true,
    historicalPublicSceneClaimed:false,historicalAdmissionScope:'SEPARATE_PRIVATE_POLICY_VALIDATION'};
   return last;
  }
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  return{drawFrame,draw:drawFrame,readPixels,png:()=>canvas.toDataURL('image/png'),project,
   evidence:{version:MAP_ENGINE_UNIT_GPU_ADAPTER_V4_VERSION,factoryCount:1,rendererSourceUnchanged:true,
    cameraV5SourceUnchanged:true,eventFinalSourceUnchanged:true,sourceGeometrySha256,sourceGeometryMutation:false,
    nativeEndpointGuardActive:true,surveyAdmissionPreserved:true,surveyAdmissionModified:false,
    nativeFramingFloor:{...clone(nativeFloor),minimumNativeSpan:clone(minimumNativeSpan),
     framesChecked:track.totalFrames,allNativeFramesWiderThanInheritedFloor:true},
    nativeForegroundChoice:'NEW_SHOT_PUBLIC_GRAPHICS_FALSE_OPTIONAL_ROLES_OMITTED',
    nativeForegroundPixelIdentityClaimed:false,oldCandidateModified:false,oldFinalModified:false,
    composition:'FRESH_NATIVE_SOURCE_GIS_THEN_LICENSED_SOURCE_TERRAIN_OCEAN_V4_THEN_REUSED_COMPLEMENTARY_TERRITORY_THEN_DOMAIN_CLIPPED_RELIEF_AND_REAL_MOVING_BOUNDARY_LIGHT_THEN_COHERENT_ROLL_THEN_ORIGINAL_NATIONAL_UNIT_TABLETS',
    originalReferenceVideoUsedAsBackground:false,referenceFrameTextureSampling:false,
    mapPresentationCopy:'ONLY_THIS_FRESH_AUTHENTIC_GEOGRAPHIC_GPU_FRAMEBUFFER',
    terrainPass:terrain.evidence,territoryPass:territory.evidence,frontierPass:frontier.evidence,presentationPass:presentation.evidence,
    combatPass:combat.evidence,nationalUnitPass:combat.evidence,finalNativeBounds:clone(finalBounds),
    noRenderedText:true,nationalFlagsFromFixture:true,originalUnitContainerArtwork:true,
    historicalPublicSceneClaimed:false,historicalAdmissionScope:'SEPARATE_PRIVATE_POLICY_VALIDATION',
    gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
    output:[WIDTH,HEIGHT],qualityParityClaimed:false,productionGate:'USER_VIDEO_REVIEW_REQUIRED'},
   get diagnostic(){return last;},dispose(){if(disposed)return;
    combat?.dispose();presentation?.dispose();frontier?.dispose();territory?.dispose();terrain?.dispose();factory?.dispose();renderer.dispose();
    disposed=true;pixels=null;}};
 }catch(error){combat?.dispose();presentation?.dispose();frontier?.dispose();territory?.dispose();terrain?.dispose();factory?.dispose();renderer.dispose();throw error;}
}
