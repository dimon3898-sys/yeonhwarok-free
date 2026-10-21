/** Opt-in director decoration over the unchanged completion/front/native pipeline.
 * Unknown geometry gets a measured source-availability label, never a prior area.
 */
import {bootLongRuntime as bootParent} from '/astra-director-v2/parent_adapter.mjs';
import {readDirectorNativeOwner} from '/astra-director-v2/frame_context.mjs';
import {readFrameContext} from '/completion-v2/frame_context.mjs';
import {readDirectorMaterialFrame} from '/astra-director-v2/material_context.mjs';
import {createQualifiedControlBridge,assertControlConsumerIdentity} from '/astra-director-v2/control_bridge.mjs';
import {createAreaAnnotation} from '/modules/area_annotation_v3.mjs';
import {createQualifiedPartialFrontPass} from '/astra-director-v2/partial_front_pass.mjs';
import {productionEventAnnotationLabels,productionAnnotationAnchors,normalizeProductionVisualProfile} from '/production-v3/production_visual_profile.mjs';
const load=async url=>{const r=await fetch(url,{cache:'no-store',redirect:'error'});if(!r.ok)throw Error('DIRECTOR_BROWSER_INPUT_REQUIRED');return r.json();};
export async function bootLongRuntime(options={}){
 const config=await load('/runtime-config.json'),d=config.astraEventDirector,uv=config.universalVideo;
 if(d?.schema!=='WORLD_ENGINE_EVENT_DIRECTOR_RUNTIME_V2'||d.purpose!=='QUALIFIED_SOURCE_REVIEW'
  ||d.normalization?.reviewReady!==true||d.productionEligible!==false||!options.testOnlySoftwareProbe)
  throw Error('DIRECTOR_EXPLICIT_QUALIFIED_REVIEW_REQUIRED');
 const parent=await bootParent(options),proof=window.longVideoProof,canvas=document.querySelector('canvas'),pipeline=proof?.pipeline,
  nativeOwner=readDirectorNativeOwner(canvas),regional=await load('/inputs/regional.json');
 if(!pipeline||!nativeOwner?.native)throw Error('DIRECTOR_ACTUAL_NATIVE_OWNER_REQUIRED');
 const native=nativeOwner.native,safe=regional.layout.safe,m=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],
  source={source_type:'SOURCE_AVAILABILITY_AUDIT',source_reference:'ASTRA_MASTER_V2 qualified source catalog '+d.catalogSHA256,verification_status:'VERIFIED'},
  chapters=uv.plan.productionV3.eventChapters,unknownIds=new Set(d.profile.sourceSchedule.filter(x=>x.truthKind==='unknown').map(x=>x.chapterId)),
  extraFronts=uv.plan.productionV3.directorAdditionalFronts??[],extraIds=new Set(extraFronts.map(x=>x.frontId)),
  extraChapterIds=new Set(d.profile.sourceSchedule.filter(x=>extraIds.has(x.stateId)).map(x=>x.chapterId)),
  labels=productionEventAnnotationLabels({chapters:chapters.filter(x=>unknownIds.has(x.chapterId)||extraChapterIds.has(x.chapterId)),source,anchor:uv.plan.legacyScenePlan.camera_intent.anchor}),
  owners=new Map(),qualifierId='DIRECTOR_UNKNOWN_GEOMETRY';
 const [timelineBytes,profileBytes,catalogBytes]=await Promise.all(['control','profile','catalog'].map(async name=>{
  const r=await fetch('/astra-director-v2/'+name+'.json',{cache:'no-store',redirect:'error'});
  if(!r.ok)throw Error('DIRECTOR_CONTROL_BYTES_REQUIRED');return r.arrayBuffer();})),
  control=createQualifiedControlBridge({timelineBytes,profileBytes,catalogBytes,
   expectedTimelineSHA256:d.normalization.normalizedRequest.controlTimelineRef.sha256,
   expectedProfileSHA256:d.profileSHA256,expectedCatalogSHA256:d.catalogSHA256,
   sourcePlanSHA256:d.sourcePlanSHA256,purpose:d.purpose});
 const controlBridge=await control;
 function make(label){return createAreaAnnotation({renderer:native.renderer,labels:[label],dataMode:'PRODUCTION',
  geographicAnchor:label.anchor,safeArea:safe,width:1080,height:1920});}
 // The preserved legacy intent calls the field origin; label anchors are not troop locations.
 for(const label of labels)owners.set(label.id,make(label));
 const origin=labels[0]?.anchor??uv.plan.legacyScenePlan.camera_intent.anchor,
  qualifier=make({id:qualifierId,display_value:'점령선 자료',unit:'미확보',source,anchor:origin}),
  extraPass=createQualifiedPartialFrontPass({canvas,profile:d.profile,fronts:extraFronts,origin,
   productionVisualProfile:normalizeProductionVisualProfile(uv.plan.productionV3.visualProfile)}),
  extraLabels=new Map(extraFronts.map(f=>[f.frontId,make({id:f.frontId,display_value:f.mapDate.replaceAll('-','.'),
   unit:'근사·부분 전선',source:{source_type:'OFFICIAL_ARCHIVAL_MAP_APPROXIMATE_DIGITIZATION',source_reference:f.source.reference,
    verification_status:'VERIFIED'},anchor:origin})])),
  draw=pipeline.drawFrame.bind(pipeline),dispose=pipeline.dispose.bind(pipeline);
 function place(owner,preferred,protectedGraphics,boundarySegments){
  const anchors=productionAnnotationAnchors({atlasEnvelope:owner.evidence.atlasEnvelope,safeArea:safe,
   preferredAnchor:preferred,protectedGraphics,boundarySegments});
  return owner.place({anchor:preferred,anchorCandidates:[m,[m[0],safe[1]+180],[m[0],safe[3]-240],...anchors],
   safeArea:safe,protectedGraphics,boundarySegments});
 }
 pipeline.drawFrame=async frame=>{
  const diagnostic=await draw(frame),chapter=chapters.find(x=>frame>=x.startFrame&&frame<x.endFrame),
   segment=d.profile.sourceSchedule.find(x=>frame>=x.startFrame&&frame<x.endFrame),context=readFrameContext(canvas);
  if(!chapter||!segment||context?.frame!==frame)throw Error('DIRECTOR_ACTUAL_FRAME_CONTEXT_REQUIRED');
  const material=readDirectorMaterialFrame(canvas,{frame,bounds:diagnostic.camera.camera.flatBounds}),
   state=controlBridge.evaluateControlState(frame),absent={field:state,globalFrame:frame,ownerDrawCount:0},
   controlIdentity=assertControlConsumerIdentity({state,area:absent,front:absent,terrain:absent});
  let sourceAvailability=null,additionalFront=null;
  if(segment.truthKind==='unknown'){
   if(diagnostic.area?.controls||diagnostic.frontV4?.selection?.sourceActiveFrame)
    throw Error('DIRECTOR_UNKNOWN_FRAME_HAS_UNSUPPORTED_GEOMETRY');
   const eventOwner=owners.get(chapter.chapterId);if(!eventOwner)throw Error('DIRECTOR_UNKNOWN_EVENT_LABEL_REQUIRED');
   const eventPlacement=place(eventOwner,[m[0],safe[1]+180],context.protectedGraphics??[],context.boundarySegments??[]),
    qualificationPlacement=place(qualifier,[m[0],safe[3]-160],
     [...(context.protectedGraphics??[]),eventPlacement.reservation],context.boundarySegments??[]);
   sourceAvailability={event:eventOwner.draw({id:chapter.chapterId,placement:eventPlacement}),
    qualification:qualifier.draw({id:qualifierId,placement:qualificationPlacement}),truthKind:'unknown',
    historicalControlGeometryDrawn:false,noPreviousStateFallback:true};
  }
  if(extraIds.has(segment.stateId)){
   const eventOwner=owners.get(chapter.chapterId),extraOwner=extraLabels.get(segment.stateId),
    eventPlacement=place(eventOwner,[m[0],safe[1]+180],context.protectedGraphics??[],context.boundarySegments??[]),
    qualificationPlacement=place(extraOwner,[m[0],safe[3]-160],
     [...(context.protectedGraphics??[]),eventPlacement.reservation],context.boundarySegments??[]),
    result=extraPass.draw({stateId:segment.stateId,globalFrame:frame,project:pipeline.project,safeArea:safe,
     protectedGraphics:[...(context.protectedGraphics??[]),eventPlacement.reservation,qualificationPlacement.reservation],
     boundarySegments:context.boundarySegments??[]});
   if(!result||result.controls.areas.length)throw Error('DIRECTOR_PARTIAL_FRONT_CONSUMER_REQUIRED');
   additionalFront={...result,controls:undefined,event:eventOwner.draw({id:chapter.chapterId,placement:eventPlacement}),
    qualification:extraOwner.draw({id:segment.stateId,placement:qualificationPlacement})};
  }
  const gl=canvas.getContext('webgl2');gl.finish();const glError=gl.getError();if(glError)throw Error('DIRECTOR_FINAL_GL_ERROR_'+glError);
  return{...diagnostic,glError:0,eventDirector:{schema:'WORLD_ENGINE_EVENT_DIRECTOR_ACTUAL_FRAME_V2',
   globalFrame:frame,chapterId:chapter.chapterId,eventId:chapter.eventId,truthKind:segment.truthKind,
   sourceAsOfDate:segment.sourceDate,profileSHA256:d.profileSHA256,derivedSceneSHA256:d.derivedSceneSHA256,
   sourceAvailability,additionalFront,controlIdentity:{...controlIdentity,consumerBinding:'ABSENCE_GUARD_ONLY_NO_OWNER_CONSUMER_CALLED'},
   fullControlReady:false,historicalOwnerMorphDrawn:false,
   composedTerrainTexture:{frame:material.frame,bounds:[...material.bounds],actualCombinedTexture:true,
    sourceKind:material.sourceKind,lightV3Connected:material.historicalLightV3Connected,lightV3DrawCount:material.historicalLightV3DrawCount},
   cameraPurpose:d.cameraProfile.cameraPurpose,
   requestedLocalCameraAdmitted:false,newRendererCopied:false,nvidiaHardwareVerified:false,visualQualityApproved:false}};
 };
 pipeline.dispose=()=>{for(const owner of owners.values())owner.dispose();for(const owner of extraLabels.values())owner.dispose();
  qualifier.dispose();extraPass.dispose();controlBridge.dispose();dispose();};
 proof.dispose=pipeline.dispose;
 return{...parent,eventDirector:{purpose:d.purpose,productionEligible:false,visualQualityApproved:false}};
}
