/** New source-review camera edge; preserved native factory remains the owner. */
import {nativeGraphicReservations,nativeBoundarySupport} from '/completion-v2/parent_camera.mjs';
import {geographicScaleVisualTokens} from '/modules/camera_gpu_pipeline_v5.mjs';
import {geographicTerrainLod} from '/modules/camera_gpu_pipeline_v2.mjs';
import {evaluateMovingLayout,validateVisibleMovingLayout} from '/modules/moving_layout_v4.mjs';
import {publishNativeFrame} from '/completion-v2/frame_context.mjs';
import {publishDirectorNativeOwner} from '/astra-director-v2/frame_context.mjs';
import {compileSourceReviewCamera,evaluateSourceReviewCamera,sourceReviewReveal}
 from '/astra-director-v2/camera_plan.mjs';
const clone=x=>structuredClone(x),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const [config,frontProfile]=await Promise.all(['/runtime-config.json','/front-v4/profile.json'].map(async url=>{
 const response=await fetch(url,{cache:'no-store',redirect:'error'});if(!response.ok)throw Error('DIRECTOR_CAMERA_CONFIG_HTTP_'+response.status);return response.json();
}));
const director=config.astraEventDirector;
if(config.testOnlySoftwareProbe!==true||director?.schema!=='WORLD_ENGINE_EVENT_DIRECTOR_RUNTIME_V2'
 ||director.purpose!=='QUALIFIED_SOURCE_REVIEW'||director.productionEligible!==false)
 throw Error('DIRECTOR_CAMERA_EXPLICIT_SOFTWARE_SOURCE_REVIEW_ONLY');

export function createProductionNativeCamera(input){
 const {native,plans,plan,contextTerrain,cameraStartFrame}=input,
  reference=native.drawNative(native.cameraPlan.totalFrames-1),safe=plans.REGIONAL.layout.safe,
  reveal=sourceReviewReveal(reference.reveal,director.cameraProfile),
  validateBounds=bounds=>{
   // Exact unchanged native minimum rule; no fabricated LOCAL certificate.
   const minimum=plans.REGIONAL.framing.bounds;
   if(bounds[2]-bounds[0]<minimum[2]-minimum[0]-1e-9||bounds[3]-bounds[1]<minimum[3]-minimum[1]-1e-9)
    return{valid:false,failures:[{code:'LOCAL_NOT_ADMITTED',category:'DATA_ADMISSION'}]};
   const visual=geographicScaleVisualTokens(bounds,plans),state={...reference,camera:{...reference.camera,flatBounds:bounds}},
    layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual});
   return validateVisibleMovingLayout(layout,reveal);
  },tracking=compileSourceReviewCamera({profile:director.cameraProfile,eventProfile:director.profile,
   plan,frontProfile,admission:director.cameraAdmission,baseCameraPlan:native.cameraPlan,
   currentNativeFrame:Math.min(cameraStartFrame,native.cameraPlan.totalFrames-1),safeArea:safe,
   minimumBounds:plans.REGIONAL.framing.bounds,validateBounds});
 publishDirectorNativeOwner(native.renderer.domElement,native,{cameraPurpose:'REGIONAL_SOURCE_REVIEW',
  sourcePlanSHA256:director.sourcePlanSHA256,derivedSceneSHA256:director.derivedSceneSHA256,
  requestedLocalContractSatisfied:false,minimumBounds:clone(plans.REGIONAL.framing.bounds)});
 return{directorCameraPlan:tracking,evidence:{version:'ASTRA_EVENT_DIRECTOR_SOURCE_REVIEW_CAMERA_V2',
  actualReferenceCameraAdapterConsumed:true,actualV5BaseConsumed:true,nativeFactoryAndProjectionUnchanged:true,
  originalRegionalFloorPreserved:true,requestedCameraStatus:'BLOCKED_REQUESTED_LOCAL',
  cameraPurpose:'REGIONAL_SOURCE_REVIEW',requestedLocalContractSatisfied:false,
  preflight:clone(tracking.preflight),rollSupported:false,productionEligible:false,nvidiaHardwareVerified:false},
  drawNative(globalFrame){
   const base=native.drawNative(cameraStartFrame+globalFrame),selected=evaluateSourceReviewCamera(tracking,globalFrame),
    nextReveal=sourceReviewReveal(base.reveal,director.cameraProfile),bounds=selected.flatBounds,
    visual=geographicScaleVisualTokens(bounds,plans),state={...base,camera:{...base.camera,...clone(selected.camera),flatBounds:clone(bounds)},
     cameraLocked:selected.cameraLocked,settle:clone(selected.settle)},
    layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual}),
    validation=validateVisibleMovingLayout(layout,nextReveal);
   if(!validation.valid)throw Error('DIRECTOR_CAMERA_ACTUAL_NATIVE_LAYOUT_UNSAFE_FRAME_'+globalFrame);
   let lod=base.gpu?.terrainLod;
   if(!same(bounds,base.camera.flatBounds)||director.cameraProfile.hideDuplicateNativeHeadline){
    lod=geographicTerrainLod(bounds,contextTerrain??plans.CONTINENT.assets.terrain,plans.REGIONAL.assets.terrain,1080,1920);
    native.factory.updateCamera(bounds);native.factory.setScaleVisual(visual);native.factory.setTerrainLod(lod.weight);
    const rendered=native.factory.renderFrame({...native.evidence.frozenMaterialParameters,graphics:false,reveal:nextReveal,primaryMaterial:1});
    if(rendered.glError)throw Error('DIRECTOR_CAMERA_NATIVE_GL_ERROR_'+rendered.glError);
   }
   const visible=layout.items.filter(x=>!director.cameraProfile.hideDuplicateNativeHeadline||!['EVENT_TITLE','TITLE_CONTRAST_PANEL'].includes(x.role)),
    boundarySegments=nativeBoundarySupport({regional:plans.REGIONAL,visual,project:native.project}),
    targetLocations=selected.contextLocations.map(x=>({...x,actualTargetPixel:native.project(x.anchor)})),
    actualCamera=clone(native.factory.evidence.cameraFrame),
    [w,s,e,n]=bounds,p00=native.project([w,n]),px=native.project([e,n]),py=native.project([w,s]),
    sx=(px[0]-p00[0])/(e-w),sy=(py[1]-p00[1])/(s-n),
    actualGeographicToPixelMatrix=[sx,0,p00[0]-sx*w,0,sy,p00[1]-sy*n,0,0,1],
    result={...state,reveal:nextReveal,layoutItems:layout.items,protectedGraphics:nativeGraphicReservations(visible),boundarySegments,
     productionCamera:{parentSourceUnchanged:true,astraDirector:{...selected,targetLocations,
      actualNativeCamera:actualCamera,actualGeographicToPixelMatrix,
      matrixOwner:'PRESERVED_NATIVE_FACTORY_PROJECT_SAMPLES; NOT_AN_INTERNAL_3D_CAMERA_MATRIX',
      protectedGraphicsSafe:true,sourcePlanSHA256:director.sourcePlanSHA256,derivedSceneSHA256:director.derivedSceneSHA256,
      sourceGlobalClockPreserved:true,requestedLocalContractSatisfied:false}},
     gpu:{...base.gpu,actualCamera,boundaryPixels:clone(visual),terrainLod:clone(lod),layout:clone(layout.items),layoutValidation:validation}};
   publishNativeFrame({frame:globalFrame,native:result,boundarySegments,
    protectedGraphics:result.protectedGraphics,actualLayoutValidation:validation});return result;
  }};
}
export {nativeGraphicReservations,nativeBoundarySupport};
