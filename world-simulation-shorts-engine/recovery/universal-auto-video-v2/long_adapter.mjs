/** Additive Area/ASTRA composition. No old renderer, camera or event code is copied. */
import {createAreaNativeBridge} from '/modules/area_native_bridge_v3.mjs';
import {compileSceneEngineRequest} from '/modules/planner_engine_adapter_v1.mjs';
import {evaluateAreaFrame} from '/modules/area_core_v3.mjs';
import {createAreaOverlayPass} from '/modules/area_overlay_pass_v3.mjs';
import {createAreaAnnotation} from '/modules/area_annotation_v3.mjs';
import {createMovingGraphicPass} from '/modules/graphic_motion_pass_v4.mjs';
import {loadUploadBundle} from '/astra-upload/gpu_upload.mjs';
import {setReferenceSourceProfile,setQualityMaterialProfile,configureAstraMaterialForCanvas,
 clearAstraMaterialForCanvas,createReferenceTerrainMaterialPassV4} from '/reference/reference_source_material.mjs';
import {createNativeBoundaryRestore} from './native_boundary_restore.mjs';

const clone=value=>structuredClone(value),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
 .map(byte=>byte.toString(16).padStart(2,'0')).join('');
const hash=async value=>digest(new TextEncoder().encode(JSON.stringify(value)));
const load=async url=>{const r=await fetch(url,{cache:'no-store',redirect:'error'});
 if(!r.ok)throw Error('UNIVERSAL_RUNTIME_INPUT_HTTP_'+r.status);return r.json();};

export async function bootLongRuntime({testOnlySoftwareProbe=false}={}){
 const config=await load('/runtime-config.json'),uv=config.universalVideo;
 if(uv?.schema!=='WORLD_ENGINE_UNIVERSAL_RUNTIME_V2'||uv.frameConvention!=='GLOBAL_HALF_OPEN'
  ||typeof testOnlySoftwareProbe!=='boolean'||testOnlySoftwareProbe!==(config.testOnlySoftwareProbe===true)
  ||!hex(uv.planSha256)||!hex(uv.legacySceneSha256)||!hex(uv.sceneRangeSha256))
  throw Error('UNIVERSAL_EXPLICIT_RUNTIME_BINDING_REQUIRED');
 const scenePlan=uv.plan.legacyScenePlan;
 if(await hash(scenePlan)!==uv.legacySceneSha256||await hash(uv.scene)!==uv.sceneRangeSha256
  ||scenePlan.timing.total_frames!==uv.totalFrames||scenePlan.timing.fps!==uv.fps)
  throw Error('UNIVERSAL_ACTUAL_SCENE_HASH_MISMATCH');
 const request=compileSceneEngineRequest(scenePlan);
 const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
  load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),
  load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
 if(scene.primary_region_id!==scenePlan.camera_intent.native_context.primary_country_id
  ||JSON.stringify(scene.event_anchor)!==JSON.stringify(scenePlan.camera_intent.anchor))
  throw Error('UNIVERSAL_NATIVE_EVENT_BINDING_REQUIRED');
 const bundle=await loadUploadBundle({manifestURL:'/astra-data/UPLOAD_MANIFEST.json',
  expectedManifestSha256:config.astra.bundleManifestSha256,maxBytes:128*1024*1024});
 if(!bundle.enabled||bundle.partCount===0)throw Error('UNIVERSAL_AUTHENTIC_ASTRA_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;
 document.body.replaceChildren(canvas);
 const native=await createAreaNativeBridge({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,
  heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null});
 const gl=canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info'),
  backend=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
 if(typeof backend!=='string'||(testOnlySoftwareProbe?!/SwiftShader/i.test(backend):
  /swiftshader|llvmpipe|lavapipe|softpipe|software/i.test(backend)||!/\bNVIDIA\b/i.test(backend))){
  native.dispose();throw Error('UNIVERSAL_NVIDIA_BACKEND_REQUIRED');
 }
 let material,overlay,foreground,boundary,annotation,disposed=false,last=null;
 let cachedKey=null,cachedCoverage=null,coverageHits=0,coverageMisses=0;
 try{
  setReferenceSourceProfile({...config.referenceV2.source,registerDomainCoverage:false});
  setQualityMaterialProfile({boundary:config.quality.boundary,screenFeatherPixels:config.quality.screenFeatherPixels});
  configureAstraMaterialForCanvas(canvas,{bundle,profile:config.astra.materialProfile,testOnlySoftwareProbe});
  try{material=await createReferenceTerrainMaterialPassV4({canvas,source:REGIONAL.assets.terrain});}
  finally{clearAstraMaterialForCanvas(canvas);}
  boundary=await createNativeBoundaryRestore({gl,width:1080,height:1920});
  overlay=createAreaOverlayPass({canvas});
  foreground=await createMovingGraphicPass({renderer:native.renderer,factory:native.factory,width:1080,height:1920});
  annotation=await createAreaAnnotation({renderer:native.renderer,labels:request.annotations,
   dataMode:request.areaPlan.intent.data_mode,geographicAnchor:request.areaPlan.intent.origin,
   safeArea:REGIONAL.layout.safe,width:1080,height:1920});
 }catch(error){annotation?.dispose();foreground?.dispose();overlay?.dispose();boundary?.dispose();material?.dispose();native.dispose();throw error;}
 const binding={schema:'WORLD_ENGINE_UNIVERSAL_ACTUAL_FRAME_V2',planSha256:uv.planSha256,
  legacySceneSha256:uv.legacySceneSha256,sceneRangeSha256:uv.sceneRangeSha256,
  nativePayloadSha256:uv.nativePayloadSha256,testOnly:testOnlySoftwareProbe};
 async function drawFrame(globalFrame){
  if(disposed||!Number.isSafeInteger(globalFrame)||globalFrame<uv.scene.startFrame||globalFrame>=uv.scene.endFrame)
   throw Error('UNIVERSAL_GLOBAL_FRAME_OUTSIDE_SELECTED_SCENE');
  const started=performance.now(),nativeStarted=started,
   n=native.drawNative(uv.cameraStartFrame+globalFrame),nativeCpuDispatchMs=performance.now()-nativeStarted;
  const key=await hash({camera:n.camera.flatBounds,reveal:n.reveal,geometry:uv.nativePayloadSha256});
  boundary.capture({key});
  if(key===cachedKey)coverageHits++;else{cachedCoverage=native.factory.coverage();cachedKey=key;coverageMisses++;}
  const sourceStarted=performance.now(),source=material.draw({coverage:cachedCoverage,bounds:n.camera.flatBounds,
   frame:globalFrame,fps:uv.fps}),sourceCpuDispatchMs=performance.now()-sourceStarted;
  boundary.restore({key,segments:n.boundarySegments});
  let controls=null,graphics=null,date=null;
  if(globalFrame>=request.timing.eventStartFrame){
   if(n.cameraLocked!==true||n.settle?.locked!==true)throw Error('UNIVERSAL_EVENT_REQUIRES_NATIVE_DETAIL_LOCK');
   controls=evaluateAreaFrame(request.areaPlan,request.areaPlan.startFrame+globalFrame-request.timing.eventStartFrame,
    {project:native.project});
   const safe=REGIONAL.layout.safe,middle=[(safe[0]+safe[2])/2,(safe[1]+safe[3])/2],
    placement=annotation.place({anchor:native.project(controls.origin),anchorCandidates:[middle,
     [middle[0],safe[1]+180],[middle[0],safe[3]-240],[safe[2]-260,middle[1]],[safe[0]+260,middle[1]]],
     safeArea:safe,protectedGraphics:n.protectedGraphics,boundarySegments:n.boundarySegments}),
    selected=request.annotations.find(label=>label.id===controls.stateId);
   if(!selected)throw Error('UNIVERSAL_ACTUAL_DATE_STATE_REQUIRED');
   graphics=overlay.draw({controls,project:native.project,safeArea:safe,
    protectedGraphics:[...n.protectedGraphics,placement.reservation],primaryMaterialColor:REGIONAL.theme.primary,
    boundarySegments:n.boundarySegments});
   date=annotation.draw({id:selected.id,placement});
  }
  const units=foreground.draw({items:n.layoutItems,reveal:n.reveal});
  gl.finish();const glError=gl.getError();if(glError)throw Error('UNIVERSAL_COMPOSITION_GL_ERROR_'+glError);
  last={frame:globalFrame,width:1080,height:1920,glError:0,universalVideo:{...binding,globalFrame},
   camera:{...n,boundarySegments:undefined},area:{controls,graphics,date,geometryUnchanged:true},
   terrain:source,foreground:units,boundaryPreservation:clone(boundary.evidence),
   coverageCache:{hits:coverageHits,misses:coverageMisses,entryLimit:1,bytes:cachedCoverage?.byteLength??0},
   timings:{nativeCpuDispatchMs,sourceCpuDispatchMs,completedFrameMs:performance.now()-started,
    completedAfterGlFinish:true,perStageGpuTimers:false},
   sourceIntegrity:{originalGeometrySHA:uv.legacySceneSha256,actualAstraSelected:true,
    sourceBeforeAreaAndFront:true,originalV2FilesChanged:false,fictional65422SceneUsed:false},
   unitPolicy:'ONLY_EXISTING_NATIVE_GEOGRAPHIC_MARKERS_NO_UNVERIFIED_HISTORICAL_UNIT_POSITIONS',
   visualQualityApproved:false};return last;
 }
 const pipeline={drawFrame,project:native.project,readPixels:native.readPixels,png:()=>canvas.toDataURL('image/png'),
  get diagnostic(){return last;},evidence:{native:native.evidence,source:material.evidence,
   area:overlay.evidence,composition:'NATIVE_GIS_ASTRA_SUPPORTED_MATERIAL_NATIVE_BOUNDARY_RESTORE_EXISTING_AREA_FRONT_DATE_ORIGINAL_FOREGROUND',
   originalCodeCopied:false,legacyScalarFrontierReused:false,frontOwner:'UNCHANGED_AREA_V3_FRONT_LINE',
   sourceUploadOwner:'PRESERVED_REFERENCE_V2_FACTORY_AND_OPTIONAL_SUPPORT_PACK_ALLOCATED_ONCE_PER_SCENE_NOT_PER_FRAME',
   totalNvidiaVramMeasured:false},
  dispose(){if(disposed)return;disposed=true;annotation.dispose();foreground.dispose();overlay.dispose();boundary.dispose();
   material.dispose();native.dispose();cachedCoverage=null;}};
 window.longVideoProof={pipeline,...(testOnlySoftwareProbe?{testOnlyNative:Object.freeze({
  drawFrame:frame=>native.drawNative(uv.cameraStartFrame+frame),readPixels:native.readPixels,
  get boundarySegments(){return native.boundarySegments;},
  get protectedGraphics(){return native.protectedGraphics;}})}:{}),async capture(globalFrame,{png=true}={}){
  const diagnostic=await pipeline.drawFrame(globalFrame),readStarted=performance.now(),pixels=pipeline.readPixels(),
   raw_rgba_sha256=await digest(pixels),result={diagnostic,raw_rgba_sha256};
  diagnostic.timings.readbackAndSHA256Ms=performance.now()-readStarted;
  if(png){const at=performance.now();result.png=pipeline.png();result.png_sha256=await digest(
   Uint8Array.from(atob(result.png.split(',')[1]),c=>c.charCodeAt(0)));diagnostic.timings.pngAndSHA256Ms=performance.now()-at;}
  return result;},dispose:pipeline.dispose};
 return {backend,testOnly:testOnlySoftwareProbe,universalVideo:{...binding,testOnly:testOnlySoftwareProbe},
  evidence:pipeline.evidence,gpuRenderingVerified:false,videoQualityApproved:false,
  productionEligible:!testOnlySoftwareProbe,fullVideoRendered:false};
}
