/** Independent, opt-in software director. Existing V5, layout, shaders, ASTRA,
 * territory/frontline and global Scene consumers are preserved read-only. */
import {nativeGraphicReservations,nativeBoundarySupport} from '/director-v1/preserved_camera.mjs';
import {geographicScaleVisualTokens} from '/modules/camera_gpu_pipeline_v5.mjs';
import {geographicTerrainLod} from '/modules/camera_gpu_pipeline_v2.mjs';
import {evaluateMovingLayout,validateVisibleMovingLayout} from '/modules/moving_layout_v4.mjs';
import {publishNativeFrame} from '/completion-v2/frame_context.mjs';
import {compileStoryDirectorCamera,evaluateStoryDirectorCamera,directorVisibleReveal} from '/director-v1/camera_plan.mjs';
const clone=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const [config,frontProfile]=await Promise.all(['/runtime-config.json','/front-v4/profile.json'].map(async url=>{
 const r=await fetch(url,{cache:'no-store',redirect:'error'});if(!r.ok)throw Error('DIRECTOR_CAMERA_RUNTIME_HTTP_'+r.status);return r.json();
}));
if(config?.storyDirector?.schema!=='WORLD_ENGINE_80S_DIRECTOR_CAPTURE_V1'||config.storyDirector.mode!=='SOFTWARE_PREVIEW'
 ||config.testOnlySoftwareProbe!==true||config.storyDirector.productionEligible!==false)
 throw Error('DIRECTOR_CAMERA_SOFTWARE_CAPTURE_ONLY');
export function createProductionNativeCamera(input){
 const {native,plans,plan,contextTerrain,cameraStartFrame}=input,
  reference=native.drawNative(native.cameraPlan.totalFrames-1),safeArea=plans.REGIONAL.layout.safe,
  visibleReferenceReveal=directorVisibleReveal(reference.reveal,config.storyDirector.profile),
  validateBounds=bounds=>{
   const visual=geographicScaleVisualTokens(bounds,plans),state={...reference,camera:{...reference.camera,flatBounds:bounds}},
    layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual});
   return validateVisibleMovingLayout(layout,visibleReferenceReveal);
  },tracking=compileStoryDirectorCamera({profile:config.storyDirector.profile,plan,frontProfile,
   baseCameraPlan:native.cameraPlan,currentNativeFrame:Math.min(cameraStartFrame,native.cameraPlan.totalFrames-1),safeArea,validateBounds});
 return{directorCameraPlan:tracking,evidence:{version:'SOURCE_BOUND_SOFTWARE_STORY_DIRECTOR_V1',
  originalV5BaseConsumed:true,originalReferenceCameraAdapterConsumed:true,nativeFactoryAndProjectionUnchanged:true,
  allTimelineCameraFloorModified:false,oldCompletionCameraModified:false,
  directorProfileSHA256:config.storyDirector.profileSHA256,actualNativeLayoutPreflight:tracking.nativeLayoutPreflight,
  nativeHeadlinePolicy:{hideDuplicateNativeHeadline:config.storyDirector.profile.hideDuplicateNativeHeadline===true,
   originalNativeTitle:'PRESERVED_SOURCE_UNUSED_WHEN_REPLACED_BY_CHAPTER_TITLE',
   reason:'ACTUAL_NATIVE_HEADLINE_BOUNDARY_CLEARANCE_FAILURE; EXISTING_CHAPTER_TITLE_AND_SOURCE_DATE_REMAIN_VISIBLE',
   rolesHidden:['EVENT_TITLE','TITLE_CONTRAST_PANEL'],otherNativeRevealRolesChanged:false},
  rollSupported:false,nvidiaHardwareVerified:false,productionEligible:false},
  drawNative(globalFrame){
   const base=native.drawNative(cameraStartFrame+globalFrame),selected=evaluateStoryDirectorCamera(tracking,globalFrame),
    reveal=directorVisibleReveal(base.reveal,config.storyDirector.profile),
    bounds=selected.flatBounds,visual=geographicScaleVisualTokens(bounds,plans),
    state={...base,camera:{...base.camera,flatBounds:[...bounds]},cameraLocked:selected.cameraLocked,settle:clone(selected.settle)},
    layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual}),
    validation=validateVisibleMovingLayout(layout,reveal);
   if(validation.valid!==true)throw Error('DIRECTOR_CAMERA_ACTUAL_LAYOUT_UNSAFE_FRAME_'+globalFrame);
   let lod=base.gpu?.terrainLod;
   if(!same(bounds,base.camera.flatBounds)||config.storyDirector.profile.hideDuplicateNativeHeadline===true){
    lod=geographicTerrainLod(bounds,contextTerrain??plans.CONTINENT.assets.terrain,plans.REGIONAL.assets.terrain,1080,1920);
    native.factory.updateCamera(bounds);native.factory.setScaleVisual(visual);native.factory.setTerrainLod(lod.weight);
    const result=native.factory.renderFrame({...native.evidence.frozenMaterialParameters,graphics:false,reveal,primaryMaterial:1});
    if(result.glError)throw Error('DIRECTOR_CAMERA_NATIVE_REDRAW_GL_ERROR_'+result.glError);
   }
   const boundarySegments=nativeBoundarySupport({regional:plans.REGIONAL,visual,project:native.project}),
    targetLocations=selected.contextLocations.map(row=>({...row,actualTargetPixel:native.project(row.anchor)})),
    visibleReservationItems=config.storyDirector.profile.hideDuplicateNativeHeadline===true?
     layout.items.filter(item=>!['EVENT_TITLE','TITLE_CONTRAST_PANEL'].includes(item.role)):layout.items,
    result={...state,reveal,layoutItems:layout.items,protectedGraphics:nativeGraphicReservations(visibleReservationItems),boundarySegments,
     productionCamera:{parentSourceUnchanged:true,storyDirector:{...selected,targetLocations,
      actualNativeCamera:clone(native.factory.evidence.cameraFrame),actualPixelProjectionOwner:'PRESERVED_NATIVE_FACTORY_SCREEN',
      protectedGraphicsSafe:true,globalSceneClockPreserved:true,originalSourceGeometryUnchanged:true}},
     gpu:{...base.gpu,actualCamera:clone(native.factory.evidence.cameraFrame),boundaryPixels:clone(visual),terrainLod:clone(lod),
      layout:clone(layout.items),layoutValidation:validation}};
   publishNativeFrame({frame:globalFrame,native:result,boundarySegments});return result;
  }};
}
export {nativeGraphicReservations,nativeBoundarySupport};
