/** Thin archival selection/composition adapter. All native, ASTRA, front GPU,
 * projection, camera and measured glyph owners are the unchanged V3 engines. */
import {createAreaNativeBridge} from '/modules/area_native_bridge_v3.mjs';
import {createMovingGraphicPass} from '/modules/graphic_motion_pass_v4.mjs';
import {createAreaAnnotation} from '/modules/area_annotation_v3.mjs';
import {compileAreaIntent,compileAreaPlan,evaluateAreaFrame} from '/modules/area_core_v3.mjs';
import {loadUploadBundle} from '/astra-upload/gpu_upload.mjs';
import {setReferenceSourceProfile,setQualityMaterialProfile,configureAstraMaterialForCanvas,
 clearAstraMaterialForCanvas,createReferenceTerrainMaterialPassV4} from '/reference/reference_source_material.mjs';
import {compileLongAreaRequest,evaluateLongAreaFrame} from '/universal/long_area_timeline.mjs';
import {normalizePlannerGeometryKeys} from '/universal/planner_geometry_serialization.mjs';
import {createNativeBoundaryRestore} from '/universal/native_boundary_restore.mjs';
import {normalizeProductionVisualProfile,validateAreaColorBindings,evaluateProductionGeometryClock,
 productionEventAnnotationLabels,productionAnnotationAnchors} from '/production-v3/production_visual_profile.mjs';
import {createProductionNativeCamera} from '/production-v3/production_native_camera.mjs';
import {createProductionAreaPass} from '/production-v3/production_area_pass.mjs';
import {FRONT_RUNTIME_PROFILE,normalizeFrontProfile,selectFrontSnapshot,sourceLineChunks,selectSourceFrontBoundaryPolicy} from '/front-v4/front_visual.mjs';

const clone=value=>structuredClone(value),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join(''),
 hash=value=>digest(new TextEncoder().encode(JSON.stringify(value))),
 load=async url=>{const r=await fetch(url,{cache:'no-store',redirect:'error'});if(!r.ok)throw Error('FRONT_V4_RUNTIME_HTTP_'+r.status);return r.json();};
function archivalSource(front){return{source_type:'OFFICIAL_ARCHIVAL_MAP_APPROXIMATE_DIGITIZATION',
 source_reference:front.source.reference,verification_status:'VERIFIED'};}
export async function bootLongRuntime({testOnlySoftwareProbe=false}={}){
 const config=await load('/runtime-config.json'),uv=config.universalVideo,production=uv?.plan?.productionV3,integrity=config.frontV4,
  softwareProbeVariant=config.frontV4ProbeVariant??'AFTER';
 if(uv?.schema!=='WORLD_ENGINE_UNIVERSAL_RUNTIME_V2'||uv.frameConvention!=='GLOBAL_HALF_OPEN'
  ||production?.runtimeProfile!=='UNIVERSAL_PRODUCTION_V3'||integrity?.runtimeProfile!==FRONT_RUNTIME_PROFILE
  ||JSON.stringify(uv.frontV4)!==JSON.stringify(integrity)||!hex(integrity.profileSha256)||!hex(integrity.sourceManifestSha256)
  ||!hex(integrity.browserSourceSignature)||testOnlySoftwareProbe!==(config.testOnlySoftwareProbe===true)
  ||config.productionV3ProbeVariant&&config.productionV3ProbeVariant!=='AFTER'
  ||!['AFTER','SUPPRESS_ARCHIVAL_FRONT'].includes(softwareProbeVariant)||!testOnlySoftwareProbe&&softwareProbeVariant!=='AFTER')throw Error('FRONT_V4_EXPLICIT_RUNTIME_PROFILE_REQUIRED');
 const response=await fetch('/front-v4/profile.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('FRONT_V4_PROFILE_HTTP_REQUIRED');const profileBytes=await response.arrayBuffer();
 if(await digest(profileBytes)!==integrity.profileSha256)throw Error('FRONT_V4_PROFILE_BYTE_HASH_MISMATCH');
 const frontProfile=normalizeFrontProfile(JSON.parse(new TextDecoder().decode(profileBytes)),{totalFrames:uv.totalFrames,eventChapters:production.eventChapters}),
  raw=uv.plan.legacyScenePlan,original=JSON.stringify(raw),request=compileLongAreaRequest(normalizePlannerGeometryKeys(raw)),
  profile=normalizeProductionVisualProfile(production.visualProfile),bindings=validateAreaColorBindings(production.visualBindings.areaStyles,raw,production.visualProfile?.palette);
 if(await hash(raw)!==uv.legacySceneSha256||await hash(uv.scene)!==uv.sceneRangeSha256||raw.timing.total_frames!==uv.totalFrames||raw.timing.fps!==uv.fps)
  throw Error('FRONT_V4_ORIGINAL_PLAN_HASH_REQUIRED');
 const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),
  load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
 if(scene.primary_region_id!==raw.camera_intent.native_context.primary_country_id||JSON.stringify(scene.event_anchor)!==JSON.stringify(raw.camera_intent.anchor))
  throw Error('FRONT_V4_ACTUAL_NATIVE_ANCHOR_REQUIRED');
 const bundle=await loadUploadBundle({manifestURL:'/astra-data/UPLOAD_MANIFEST.json',expectedManifestSha256:config.astra.bundleManifestSha256,maxBytes:128*1024*1024});
 if(!bundle.enabled||bundle.partCount===0)throw Error('FRONT_V4_AUTHENTIC_ASTRA_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);
 const native=await createAreaNativeBridge({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null}),
  gl=canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info'),backend=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
 if(typeof backend!=='string'||(testOnlySoftwareProbe?!/SwiftShader/i.test(backend):/swiftshader|llvmpipe|lavapipe|software/i.test(backend)||!/\bNVIDIA\b/i.test(backend))){native.dispose();throw Error('FRONT_V4_NVIDIA_REQUIRED');}
 const plans=new Map(frontProfile.fronts.map(front=>{
  const source=archivalSource(front),fronts=sourceLineChunks(front.geometry).map((chunk,index)=>({id:front.frontId+'-part-'+index,
   geometry:chunk.geometry,source,role:'FRONT_LINE',style_role:'PRIMARY'})),intent=compileAreaIntent({data_mode:'PRODUCTION',
    semantic_mode:'SUPPLIED_OBSERVED_STATES',origin:request.origin,source,fronts});
  return[front.frontId,compileAreaPlan(intent,{fps:uv.fps,total_frames:1,operations:[{type:'AREA_HOLD',start_frame:0,duration_frames:1}]})];
 }));
 let source,area,foreground,boundary,nativeCamera,disposed=false,last=null,currentNative=null,coverageKey=null,coverage=null,coverageHits=0,coverageMisses=0;
 const owners=[],eventOwners=new Map(),snapshotOwners=new Map(),archivalOwners=new Map(),
  labels=productionEventAnnotationLabels({chapters:production.eventChapters,source:request.annotations[0].source,anchor:request.origin});
 const makeOwner=label=>{const owner=createAreaAnnotation({renderer:native.renderer,labels:[label],dataMode:request.dataMode,
  geographicAnchor:request.origin,safeArea:REGIONAL.layout.safe,width:1080,height:1920});owners.push(owner);return owner;};
 try{
  setReferenceSourceProfile({...config.referenceV2.source,registerDomainCoverage:false});
  setQualityMaterialProfile({boundary:config.quality.boundary,screenFeatherPixels:config.quality.screenFeatherPixels});
  configureAstraMaterialForCanvas(canvas,{bundle,profile:config.astra.materialProfile,testOnlySoftwareProbe});
  try{source=await createReferenceTerrainMaterialPassV4({canvas,source:REGIONAL.assets.terrain});}finally{clearAstraMaterialForCanvas(canvas);}
  foreground=await createMovingGraphicPass({renderer:native.renderer,factory:native.factory,width:1080,height:1920});
  nativeCamera=createProductionNativeCamera({native,plans:{REGIONAL,CONTINENT},plan:uv.plan,request,cameraStartFrame:uv.cameraStartFrame,
   heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null,profile});
  boundary=await createNativeBoundaryRestore({gl,width:1080,height:1920});area=createProductionAreaPass({canvas,profile,bindings,probeVariant:'AFTER'});
  for(const label of labels)eventOwners.set(label.id,makeOwner(label));
  for(const row of production.geometrySchedule.filter(row=>row.mode!=='ARRIVAL_NO_EVENT'))snapshotOwners.set(row.scheduleId,makeOwner({id:row.scheduleId,
   display_value:row.snapshotLabel.replace(/ 도식$/,''),unit:'도식',source:request.annotations[0].source,anchor:request.origin}));
  frontProfile.schedule.forEach((row,index)=>{const split=row.sourceLabel.lastIndexOf(' ');if(split<=0||split===row.sourceLabel.length-1)throw Error('FRONT_V4_TWO_PART_SOURCE_LABEL_REQUIRED');
   const front=frontProfile.fronts.find(item=>item.frontId===row.frontId);archivalOwners.set(index,makeOwner({id:'archival-'+index,
    display_value:row.sourceLabel.slice(0,split),unit:row.sourceLabel.slice(split+1),source:archivalSource(front),anchor:request.origin}));});
 }catch(error){for(const owner of owners)owner.dispose();area?.dispose();boundary?.dispose();foreground?.dispose();source?.dispose();native.dispose();throw error;}
 const binding={schema:'WORLD_ENGINE_UNIVERSAL_ACTUAL_FRAME_V2',planSha256:uv.planSha256,legacySceneSha256:uv.legacySceneSha256,
  sceneRangeSha256:uv.sceneRangeSha256,nativePayloadSha256:uv.nativePayloadSha256,testOnly:testOnlySoftwareProbe,
  productionV3:clone(uv.productionV3),frontV4:clone(integrity)};
 function drawNative(globalFrame){const n=nativeCamera.drawNative(globalFrame);foreground.draw({items:n.layoutItems,reveal:n.reveal});currentNative=n;return n;}
 function place(owner,{preferredAnchor,protectedGraphics,n,kind,chapter,clock,globalFrame}){
  const safe=REGIONAL.layout.safe,m=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],anchors=productionAnnotationAnchors({atlasEnvelope:owner.evidence.atlasEnvelope,
   safeArea:safe,preferredAnchor,protectedGraphics,boundarySegments:n.boundarySegments}),originalCandidates=kind==='EVENT_DATE_AND_TITLE'
    ?[m,[m[0],safe[1]+180],[m[0],safe[3]-240],[safe[2]-260,m[1]],[safe[0]+260,m[1]]]
    :[m,[m[0],safe[1]+260],[m[0],safe[3]-160],[safe[2]-260,m[1]],[safe[0]+260,m[1]]];
  try{return owner.place({anchor:preferredAnchor,anchorCandidates:[...originalCandidates,...anchors],safeArea:safe,protectedGraphics,boundarySegments:n.boundarySegments});}
  catch(error){if(error.message!=='AREA_ANNOTATION_LAYOUT_BLOCKED')throw error;throw Error('AREA_ANNOTATION_LAYOUT_BLOCKED '+JSON.stringify({kind,
   globalFrame,chapterId:chapter.chapterId,scheduleId:clock.scheduleId??null,attempts:error.attempts}));}
 }
 async function drawFrame(globalFrame){
  if(disposed||!Number.isSafeInteger(globalFrame)||globalFrame<uv.scene.startFrame||globalFrame>=uv.scene.endFrame)throw Error('FRONT_V4_FRAME_OUTSIDE_SELECTED_SCENE');
  const at=performance.now(),n=drawNative(globalFrame),key=await hash({camera:n.camera.flatBounds,reveal:n.reveal,geometry:uv.nativePayloadSha256});
  boundary.capture({key});if(key===coverageKey)coverageHits++;else{coverage=native.factory.coverage();coverageKey=key;coverageMisses++;}
  const terrain=source.draw({coverage,bounds:n.camera.flatBounds,frame:globalFrame,fps:uv.fps});boundary.restore({key,segments:n.boundarySegments});
  const selected=selectFrontSnapshot(frontProfile,globalFrame),clock=evaluateProductionGeometryClock(uv.plan,globalFrame),
   chapter=production.eventChapters.find(row=>globalFrame>=row.startFrame&&globalFrame<row.endFrame);
  if(!chapter)throw Error('FRONT_V4_NARRATIVE_CHAPTER_REQUIRED');let controls=null,graphics=null,date=null,sourceGeometrySha256=null,
   boundaryPolicy={policy:'PRESERVED_NATIVE_BOUNDARY_OCCLUSION',nativeBoundaryRestoreUnchanged:true,protectedGraphicMasksUnchanged:true};
  if(selected.sourceActiveFrame||clock.eventEnabled){
   if(selected.sourceActiveFrame){
    const front=frontProfile.fronts.find(row=>row.frontId===selected.frontId),base=evaluateAreaFrame(plans.get(front.frontId),0,{project:native.project});
    controls={...clone(base),frame:globalFrame,localFrame:globalFrame,timeSeconds:globalFrame/uv.fps,state:'ARCHIVAL_FRONT_HOLD',
     stateId:front.frontId,timeLabel:front.mapDate,timeLabelVisible:true,areas:[],observedSnapshotOnly:true,coordinatesInterpolated:false};
    sourceGeometrySha256=await hash(front.geometry);
   }else controls=evaluateLongAreaFrame(request.timelinePlan,clock.sourceGeometryFrame,{project:native.project,projectionKey:key});
   const safe=REGIONAL.layout.safe,m=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],eventOwner=eventOwners.get(chapter.chapterId),
    index=frontProfile.schedule.findIndex(row=>globalFrame>=row.startFrame&&globalFrame<row.endFrame),
    snapshotOwner=selected.sourceActiveFrame?archivalOwners.get(index):snapshotOwners.get(clock.scheduleId),
    eventPlacement=place(eventOwner,{kind:'EVENT_DATE_AND_TITLE',preferredAnchor:native.project(controls.origin),protectedGraphics:n.protectedGraphics,n,chapter,clock,globalFrame}),
    snapshotPlacement=place(snapshotOwner,{kind:'SOURCE_GEOMETRY_DATE',preferredAnchor:[m[0],safe[3]-160],
     protectedGraphics:[...n.protectedGraphics,eventPlacement.reservation],n,chapter,clock,globalFrame});
   boundaryPolicy=selectSourceFrontBoundaryPolicy({sourceActiveFrame:selected.sourceActiveFrame,controls,boundarySegments:n.boundarySegments});
   graphics=area.draw({controls:selected.sourceActiveFrame&&softwareProbeVariant==='SUPPRESS_ARCHIVAL_FRONT'?{...controls,fronts:[]}:controls,
    project:native.project,safeArea:safe,protectedGraphics:[...n.protectedGraphics,eventPlacement.reservation,snapshotPlacement.reservation],
    primaryMaterialColor:REGIONAL.theme.primary,boundarySegments:boundaryPolicy.boundarySegments});
   if(selected.sourceActiveFrame)graphics={...graphics,nativeBoundaryGlowPreserved:false,
    nativeBoundaryPreservationPolicy:boundaryPolicy.policy,
    nativeBoundaryPixelChangesPermittedOnlyWithinSourceFrontSupport:true};
   const event=eventOwner.draw({id:chapter.chapterId,placement:eventPlacement}),geometry=snapshotOwner.draw({id:selected.sourceActiveFrame?'archival-'+index:clock.scheduleId,placement:snapshotPlacement});
   if(event.text!==labels.find(label=>label.id===chapter.chapterId).expectedText)throw Error('FRONT_V4_EVENT_TITLE_NOT_RENDERED');
   if(selected.sourceActiveFrame&&geometry.text!==selected.sourceLabel)throw Error('FRONT_V4_SOURCE_QUALIFIER_NOT_RENDERED');
   date={event,geometry,eventLabel:event.text,eventDate:chapter.displayLabel,eventTitle:chapter.title,
    snapshotLabel:selected.sourceActiveFrame?selected.sourceLabel:clock.snapshotLabel,sourceClockNotNarrativeDate:true,
    archivalCoordinatesApproximate:selected.sourceActiveFrame,archivalCoveragePartial:selected.sourceActiveFrame};
  }
  const markers=foreground.draw({items:n.layoutItems,reveal:n.reveal});gl.finish();const glError=gl.getError();if(glError)throw Error('FRONT_V4_COMPOSITION_GL_ERROR_'+glError);
  if(JSON.stringify(raw)!==original)throw Error('FRONT_V4_PARENT_SOURCE_MUTATED');
  last={frame:globalFrame,width:1080,height:1920,glError:0,universalVideo:{...binding,globalFrame},camera:{...n,boundarySegments:undefined},
   area:{controls,graphics,date,geometryUnchanged:true},terrain,foreground:markers,boundaryPreservation:clone(boundary.evidence),
   coverageCache:{hits:coverageHits,misses:coverageMisses,entryLimit:1,bytes:coverage?.byteLength??0},
   productionV3:{runtimeProfile:production.runtimeProfile,probeVariant:'AFTER',chapter:clone(chapter),geometryClock:clock,
    schematicClockUsedForRendering:!selected.sourceActiveFrame,cameraAdmission:n.productionCamera,integrity:clone(uv.productionV3)},
   frontV4:{runtimeProfile:FRONT_RUNTIME_PROFILE,integrity:clone(integrity),selection:selected,sourceGeometrySha256,softwareProbeVariant,
    boundaryPolicy:{...boundaryPolicy,boundarySegments:undefined},
    originalParentPlanUnchanged:true,unverifiedSchematicAreaSuppressed:selected.sourceActiveFrame,
    noInferredEnemyComplement:true,noInferredHistoricalUnits:true,originalProjectionUsed:true,originalNativeMarkerStyleAndAnchor:true,
    layerOrder:['NATIVE_GIS_COVERAGE','ASTRA_SUPPORTED_SOURCE',selected.sourceActiveFrame?'NO_UNVERIFIED_OCCUPATION_FILL':'PRESERVED_QUALIFIED_SCHEMATIC_AREAS',
     selected.sourceActiveFrame?'SOURCE_REVIEWED_PARTIAL_UN_FRONT':'PRESERVED_SCHEMATIC_FRONT','CHAPTER_AND_SOURCE_DATE','ORIGINAL_NATIVE_MARKERS_LABELS']},
   sourceIntegrity:{originalGeometrySHA:uv.legacySceneSha256,actualAstraSelected:true,sourceBeforeAreaAndFront:true,
    originalV2FilesChanged:false,fictional65422SceneUsed:false},timings:{completedFrameMs:performance.now()-at,completedAfterGlFinish:true},visualQualityApproved:false};return last;
 }
 const pipeline={drawFrame,project:native.project,readPixels:native.readPixels,png:()=>canvas.toDataURL('image/png'),get diagnostic(){return last;},
  evidence:{version:'VERIFIED_ARCHIVAL_FRONT_COMPOSITOR_V4',native:native.evidence,source:source.evidence,area:area.evidence,camera:nativeCamera.evidence,
   originalRendererOrShadersCopied:false,originalAreaEngineReused:true,partialObservedFrontsOnly:true,inferredOccupationPolygons:false},
  dispose(){if(disposed)return;disposed=true;for(const owner of owners)owner.dispose();area.dispose();boundary.dispose();foreground.dispose();source.dispose();native.dispose();coverage=null;}};
 window.longVideoProof={pipeline,...(testOnlySoftwareProbe?{testOnlyNative:Object.freeze({drawFrame:drawNative,readPixels:native.readPixels,
  get boundarySegments(){return clone(currentNative?.boundarySegments??[]);},get protectedGraphics(){return clone(currentNative?.protectedGraphics??[]);}})}:{}),
  async capture(globalFrame,{png=true}={}){const diagnostic=await pipeline.drawFrame(globalFrame),raw=pipeline.readPixels(),result={diagnostic,raw_rgba_sha256:await digest(raw)};
   if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),c=>c.charCodeAt(0)));}return result;},dispose:pipeline.dispose};
 return{backend,testOnly:testOnlySoftwareProbe,universalVideo:clone(binding),productionV3:{runtimeProfile:production.runtimeProfile,probeVariant:'AFTER'},
  frontV4:{runtimeProfile:FRONT_RUNTIME_PROFILE,integrity:clone(integrity)},evidence:pipeline.evidence,
  gpuRenderingVerified:false,videoQualityApproved:false,productionEligible:!testOnlySoftwareProbe,fullVideoRendered:false};
}
