/** V3 composition orchestration. All geometry/GPU/source/layout engines are reused unchanged. */
import {createAreaNativeBridge} from '/modules/area_native_bridge_v3.mjs';
import {createMovingGraphicPass} from '/modules/graphic_motion_pass_v4.mjs';
import {createAreaAnnotation} from '/modules/area_annotation_v3.mjs';
import {loadUploadBundle} from '/astra-upload/gpu_upload.mjs';
import {setReferenceSourceProfile,setQualityMaterialProfile,configureAstraMaterialForCanvas,
 clearAstraMaterialForCanvas,createReferenceTerrainMaterialPassV4} from '/reference/reference_source_material.mjs';
import {compileLongAreaRequest,evaluateLongAreaFrame} from '/universal/long_area_timeline.mjs';
import {normalizePlannerGeometryKeys} from '/universal/planner_geometry_serialization.mjs';
import {createNativeBoundaryRestore} from '/universal/native_boundary_restore.mjs';
import {normalizeProductionVisualProfile,validateAreaColorBindings,evaluateProductionGeometryClock,productionEventAnnotationLabels,productionAnnotationAnchors} from '/production-v3/production_visual_profile.mjs';
import {createProductionNativeCamera} from '/production-v3/production_native_camera.mjs';
import {createProductionAreaPass} from '/production-v3/production_area_pass.mjs';

const clone=value=>structuredClone(value),hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),
 digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join(''),
 hash=value=>digest(new TextEncoder().encode(JSON.stringify(value))),
 load=async url=>{const r=await fetch(url,{cache:'no-store',redirect:'error'});if(!r.ok)throw Error('PRODUCTION_RUNTIME_HTTP_'+r.status);return r.json();};

export async function bootLongRuntime({testOnlySoftwareProbe=false}={}){
 const config=await load('/runtime-config.json'),uv=config.universalVideo,production=uv?.plan?.productionV3,
  probeVariant=config.productionV3ProbeVariant??'AFTER';
 if(uv?.schema!=='WORLD_ENGINE_UNIVERSAL_RUNTIME_V2'||uv.frameConvention!=='GLOBAL_HALF_OPEN'
  ||production?.runtimeProfile!=='UNIVERSAL_PRODUCTION_V3'||production.visualBindings?.opponentComplementAllowed!==false
  ||!Array.isArray(production.eventChapters)||!production.eventChapters.length
  ||testOnlySoftwareProbe!==(config.testOnlySoftwareProbe===true)||!['BEFORE','AFTER'].includes(probeVariant)
  ||!testOnlySoftwareProbe&&probeVariant!=='AFTER'||!hex(uv.planSha256)||!hex(uv.legacySceneSha256)||!hex(uv.sceneRangeSha256)
  ||uv.productionV3?.runtimeProfile!=='UNIVERSAL_PRODUCTION_V3'||!hex(uv.productionV3.sourceManifestSha256)||!hex(uv.productionV3.browserSourceSignature))
  throw Error('PRODUCTION_EXPLICIT_RUNTIME_PROFILE_REQUIRED');
 const raw=uv.plan.legacyScenePlan,rawBinding=JSON.stringify(raw);
 if(await hash(raw)!==uv.legacySceneSha256||await hash(uv.scene)!==uv.sceneRangeSha256
  ||raw.timing.total_frames!==uv.totalFrames||raw.timing.fps!==uv.fps)throw Error('PRODUCTION_BOUND_SOURCE_HASH_MISMATCH');
 const request=compileLongAreaRequest(normalizePlannerGeometryKeys(raw)),profile=normalizeProductionVisualProfile(production.visualProfile),
  bindings=validateAreaColorBindings(production.visualBindings.areaStyles,raw,production.visualProfile?.palette),
  [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),
   load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
 if(scene.primary_region_id!==raw.camera_intent.native_context.primary_country_id||JSON.stringify(scene.event_anchor)!==JSON.stringify(raw.camera_intent.anchor))
  throw Error('PRODUCTION_ACTUAL_NATIVE_ANCHOR_BINDING_REQUIRED');
 const bundle=await loadUploadBundle({manifestURL:'/astra-data/UPLOAD_MANIFEST.json',expectedManifestSha256:config.astra.bundleManifestSha256,maxBytes:128*1024*1024});
 if(!bundle.enabled||bundle.partCount===0)throw Error('PRODUCTION_AUTHENTIC_ASTRA_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);
 const native=await createAreaNativeBridge({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null}),
  gl=canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info'),backend=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
 if(typeof backend!=='string'||(testOnlySoftwareProbe?!/SwiftShader/i.test(backend):/swiftshader|llvmpipe|lavapipe|software/i.test(backend)||!/\bNVIDIA\b/i.test(backend))){native.dispose();throw Error('PRODUCTION_NVIDIA_REQUIRED');}
 let source,area,foreground,boundary,annotation,snapshotAnnotation,nativeCamera,disposed=false,last=null,currentNative=null,coverageKey=null,coverage=null,coverageHits=0,coverageMisses=0;
 const labels=productionEventAnnotationLabels({chapters:production.eventChapters,source:request.annotations[0].source,anchor:request.origin}),
  snapshotLabels=production.geometrySchedule.filter(row=>row.mode!=='ARRIVAL_NO_EVENT').map(row=>({id:row.scheduleId,
   display_value:row.snapshotLabel.replace(/ 도식$/,''),unit:'도식',source:request.annotations[0].source,anchor:request.origin}));
 try{
  setReferenceSourceProfile({...config.referenceV2.source,registerDomainCoverage:false});
  setQualityMaterialProfile({boundary:config.quality.boundary,screenFeatherPixels:config.quality.screenFeatherPixels});
  configureAstraMaterialForCanvas(canvas,{bundle,profile:config.astra.materialProfile,testOnlySoftwareProbe});
  try{source=await createReferenceTerrainMaterialPassV4({canvas,source:REGIONAL.assets.terrain});}finally{clearAstraMaterialForCanvas(canvas);}
  foreground=await createMovingGraphicPass({renderer:native.renderer,factory:native.factory,width:1080,height:1920});
  nativeCamera=createProductionNativeCamera({native,plans:{REGIONAL,CONTINENT},plan:uv.plan,request,cameraStartFrame:uv.cameraStartFrame,
   heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null,profile});
  boundary=await createNativeBoundaryRestore({gl,width:1080,height:1920});
  area=createProductionAreaPass({canvas,profile,bindings,probeVariant});
  const createAnnotationSet=items=>{
   const entries=new Map();try{for(const label of items)entries.set(label.id,createAreaAnnotation({renderer:native.renderer,
    labels:[label],dataMode:request.dataMode,geographicAnchor:request.origin,safeArea:REGIONAL.layout.safe,width:1080,height:1920}));}
   catch(error){for(const entry of entries.values())entry.dispose();throw error;}
   return{get(id){const owner=entries.get(id);if(!owner)throw Error('PRODUCTION_CURRENT_ANNOTATION_REQUIRED');return owner;},
    dispose(){for(const owner of entries.values())owner.dispose();}};
  };
  // The old pass already creates one glyph/pass per label. Keeping independent
  // owners reserves the current full atlas instead of an unrelated widest label.
  annotation=createAnnotationSet(labels);snapshotAnnotation=createAnnotationSet(snapshotLabels);
 }catch(error){snapshotAnnotation?.dispose();annotation?.dispose();area?.dispose();boundary?.dispose();foreground?.dispose();source?.dispose();native.dispose();throw error;}
 const binding={schema:'WORLD_ENGINE_UNIVERSAL_ACTUAL_FRAME_V2',planSha256:uv.planSha256,legacySceneSha256:uv.legacySceneSha256,
  sceneRangeSha256:uv.sceneRangeSha256,nativePayloadSha256:uv.nativePayloadSha256,testOnly:testOnlySoftwareProbe,productionV3:clone(uv.productionV3)};
 function drawNative(globalFrame){const n=nativeCamera.drawNative(globalFrame);foreground.draw({items:n.layoutItems,reveal:n.reveal});currentNative=n;return n;}
 function placeAnnotation(owner,{kind,globalFrame,chapter,clock,preferredAnchor,protectedGraphics,n}){
  const safe=REGIONAL.layout.safe,m=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],
   originalCandidates=kind==='EVENT_DATE_AND_TITLE'?[m,[m[0],safe[1]+180],[m[0],safe[3]-240],[safe[2]-260,m[1]],[safe[0]+260,m[1]]]
    :[m,[m[0],safe[1]+260],[m[0],safe[3]-160],[safe[2]-260,m[1]],[safe[0]+260,m[1]]];
  const anchors=productionAnnotationAnchors({atlasEnvelope:owner.evidence.atlasEnvelope,safeArea:REGIONAL.layout.safe,
   preferredAnchor,protectedGraphics,boundarySegments:n.boundarySegments});
  try{return owner.place({anchor:preferredAnchor,anchorCandidates:[...originalCandidates,...anchors],safeArea:REGIONAL.layout.safe,protectedGraphics,boundarySegments:n.boundarySegments});}
  catch(error){if(error.message!=='AREA_ANNOTATION_LAYOUT_BLOCKED')throw error;
   throw Error('AREA_ANNOTATION_LAYOUT_BLOCKED '+JSON.stringify({kind,globalFrame,chapterId:chapter.chapterId,scheduleId:clock.scheduleId,
    atlasEnvelope:owner.evidence.atlasEnvelope,safeArea:REGIONAL.layout.safe,candidateCount:anchors.length,
    nativeReservationCount:protectedGraphics.length,nativeBoundarySegments:n.boundarySegments.length,attempts:error.attempts}));}
 }
 async function drawFrame(globalFrame){
  if(disposed||!Number.isSafeInteger(globalFrame)||globalFrame<uv.scene.startFrame||globalFrame>=uv.scene.endFrame)throw Error('PRODUCTION_FRAME_OUTSIDE_SELECTED_SCENE');
  const at=performance.now(),n=drawNative(globalFrame),nativeCpuDispatchMs=performance.now()-at,
   key=await hash({camera:n.camera.flatBounds,reveal:n.reveal,geometry:uv.nativePayloadSha256});
  boundary.capture({key});if(key===coverageKey)coverageHits++;else{coverage=native.factory.coverage();coverageKey=key;coverageMisses++;}
  const sourceAt=performance.now(),terrain=source.draw({coverage,bounds:n.camera.flatBounds,frame:globalFrame,fps:uv.fps}),sourceCpuDispatchMs=performance.now()-sourceAt;
  boundary.restore({key,segments:n.boundarySegments});
  const clock=evaluateProductionGeometryClock(uv.plan,globalFrame),chapter=production.eventChapters.find(row=>globalFrame>=row.startFrame&&globalFrame<row.endFrame);
  if(!chapter)throw Error('PRODUCTION_NARRATIVE_CHAPTER_REQUIRED');
  let controls=null,graphics=null,date=null;
  if(clock.eventEnabled){
   controls=evaluateLongAreaFrame(request.timelinePlan,clock.sourceGeometryFrame,{project:native.project,projectionKey:key});
   const safe=REGIONAL.layout.safe,m=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],eventOwner=annotation.get(chapter.chapterId),snapshotOwner=snapshotAnnotation.get(clock.scheduleId),
    placement=placeAnnotation(eventOwner,{kind:'EVENT_DATE_AND_TITLE',globalFrame,chapter,clock,preferredAnchor:native.project(controls.origin),
     protectedGraphics:n.protectedGraphics,n}),
    snapshotPlacement=placeAnnotation(snapshotOwner,{kind:'SOURCE_GEOMETRY_DATE',globalFrame,chapter,clock,preferredAnchor:[m[0],safe[3]-160],
     protectedGraphics:[...n.protectedGraphics,placement.reservation],n});
   graphics=area.draw({controls,project:native.project,safeArea:safe,protectedGraphics:[...n.protectedGraphics,placement.reservation,snapshotPlacement.reservation],
    primaryMaterialColor:REGIONAL.theme.primary,boundarySegments:n.boundarySegments});
   const eventDate=eventOwner.draw({id:chapter.chapterId,placement});
   if(eventDate.text!==labels.find(label=>label.id===chapter.chapterId).expectedText)throw Error('PRODUCTION_EVENT_TITLE_NOT_RENDERED');
   date={event:eventDate,geometry:snapshotOwner.draw({id:clock.scheduleId,placement:snapshotPlacement}),
    eventLabel:eventDate.text,eventDate:chapter.displayLabel,eventTitle:chapter.title,
    snapshotLabel:clock.snapshotLabel,sourceClockNotNarrativeDate:true,
    reservationPolicy:'CURRENT_LABEL_FULL_MEASURED_ATLAS_NOT_MAX_OTHER_CHAPTER'};
  }
  const markers=foreground.draw({items:n.layoutItems,reveal:n.reveal});gl.finish();const glError=gl.getError();if(glError)throw Error('PRODUCTION_COMPOSITION_GL_ERROR_'+glError);
  if(JSON.stringify(raw)!==rawBinding)throw Error('PRODUCTION_ORIGINAL_SCENE_MUTATED');
  last={frame:globalFrame,width:1080,height:1920,glError:0,universalVideo:{...binding,globalFrame},
   camera:{...n,boundarySegments:undefined},area:{controls,graphics,date,geometryUnchanged:true},terrain,foreground:markers,
   boundaryPreservation:clone(boundary.evidence),coverageCache:{hits:coverageHits,misses:coverageMisses,entryLimit:1,bytes:coverage?.byteLength??0},
   productionV3:{runtimeProfile:production.runtimeProfile,probeVariant,chapter:clone(chapter),geometryClock:clock,
    visual:graphics?.productionVisual??null,cameraAdmission:n.productionCamera,integrity:clone(uv.productionV3),
    layerOrder:['NATIVE_GIS_COVERAGE','ASTRA_SUPPORTED_SOURCE','ACTUAL_SUPPLIED_AREA_OWNERSHIP','ACTUAL_SUPPLIED_FRONT_WHITE_GOLD','CHAPTER_AND_SNAPSHOT_DATE','ORIGINAL_NATIVE_MARKERS_LABELS'],
    noInferredEnemyComplement:true,noInferredHistoricalUnits:true,nationalUnitPositions:0,
    originalNativeMarkerStyleAndAnchor:true,originalProjectionUsed:true},
   timings:{nativeCpuDispatchMs,sourceCpuDispatchMs,completedFrameMs:performance.now()-at,completedAfterGlFinish:true,perStageGpuTimers:false},
   sourceIntegrity:{originalGeometrySHA:uv.legacySceneSha256,actualAstraSelected:true,sourceBeforeAreaAndFront:true,originalV2FilesChanged:false,fictional65422SceneUsed:false},
   visualQualityApproved:false};return last;
 }
 const pipeline={drawFrame,project:native.project,readPixels:native.readPixels,png:()=>canvas.toDataURL('image/png'),get diagnostic(){return last;},
  evidence:{version:'UNIVERSAL_PRODUCTION_COMPOSITOR_V3',native:native.evidence,source:source.evidence,area:area.evidence,camera:nativeCamera.evidence,
   areaClock:request.timelinePlan.ownership,composition:'ASTRA_THEN_SUPPLIED_OCCUPATION_THEN_SUPPLIED_WHITE_GOLD_FRONT_THEN_ORIGINAL_NATIVE_FOREGROUND',
   originalCodeCopied:false,legacyScalarFrontierReused:false,frontOwner:'UNCHANGED_AREA_V3_FRONT_LINE_WITH_EXPLICIT_V3_STYLE',
   sourceUploadOwner:'PRESERVED_REFERENCE_V2_FACTORY_AND_OPTIONAL_SUPPORT_PACK_ONCE_PER_SCENE',totalNvidiaVramMeasured:false},
  dispose(){if(disposed)return;disposed=true;snapshotAnnotation.dispose();annotation.dispose();area.dispose();boundary.dispose();foreground.dispose();source.dispose();native.dispose();coverage=null;}};
 window.longVideoProof={pipeline,...(testOnlySoftwareProbe?{testOnlyNative:Object.freeze({drawFrame:drawNative,readPixels:native.readPixels,
  get boundarySegments(){return clone(currentNative?.boundarySegments??[]);},
  get protectedGraphics(){return clone(currentNative?.protectedGraphics??[]);}})}:{}),async capture(globalFrame,{png=true}={}){
  const diagnostic=await pipeline.drawFrame(globalFrame),readAt=performance.now(),raw=pipeline.readPixels(),result={diagnostic,raw_rgba_sha256:await digest(raw)};
  diagnostic.timings.readbackAndSHA256Ms=performance.now()-readAt;
  if(png){const at=performance.now();result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),c=>c.charCodeAt(0)));diagnostic.timings.pngAndSHA256Ms=performance.now()-at;}return result;},dispose:pipeline.dispose};
 return{backend,testOnly:testOnlySoftwareProbe,universalVideo:{...binding,testOnly:testOnlySoftwareProbe,productionV3:clone(uv.productionV3)},productionV3:{runtimeProfile:production.runtimeProfile,probeVariant},
  evidence:pipeline.evidence,gpuRenderingVerified:false,videoQualityApproved:false,productionEligible:!testOnlySoftwareProbe,fullVideoRendered:false};
}
