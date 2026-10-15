/** Opt-in ASTRA material selection. All map/camera/control/frontier/unit orchestration is V4. */
import {createMapEngineUnitGpuAdapterV4} from '/modules/map_engine_unit_gpu_adapter_v4.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame} from '/modules/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,assessReferenceCameraMotion} from '/modules/reference_camera_adapter_v1.mjs';
import {configureAstraMaterialForCanvas,clearAstraMaterialForCanvas} from './astra_material.mjs';
import {loadUploadBundle} from '/astra-upload/gpu_upload.mjs';

const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
 .map(value=>value.toString(16).padStart(2,'0')).join('');
const load=async url=>{const response=await fetch(url,{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('ASTRA_RUNTIME_INPUT_HTTP_'+response.status);return response.json();};

/** Configuring a per-canvas material is the only new pipeline selection step. */
export async function createAstraGpuAdapter(options,{bundle,profile={},testOnlySoftwareProbe=false}={}){
 if(!options?.canvas)throw Error('ASTRA_CANVAS_REQUIRED');
 configureAstraMaterialForCanvas(options.canvas,{bundle,profile,testOnlySoftwareProbe});
 try{return await createMapEngineUnitGpuAdapterV4(options);}
 finally{clearAstraMaterialForCanvas(options.canvas);}
}

/** Runs only in a new loopback harness with its pinned standard import map installed first. */
export async function bootAstraRuntime({testOnlySoftwareProbe=false}={}){
 const config=await load('/runtime-config.json');
 if(config.schema!=='ASTRA_RUNTIME_HTTP_V1'||config.astra?.enabled!==true)
  throw Error('ASTRA_EXPLICIT_RUNTIME_CONFIGURATION_REQUIRED');
 if(typeof testOnlySoftwareProbe!=='boolean'||testOnlySoftwareProbe!==(config.testOnlySoftwareProbe===true))
  throw Error('ASTRA_EXPLICIT_SOFTWARE_TEST_PROVENANCE_REQUIRED');
 const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
  load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),
  load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
 const {scenePlan,currentNativeFrame,totalFrames,mode,admittedNativeFraming}=config.bootstrap;
 const territoryPlan=compileTerritoryControlPlan(scenePlan.controlIntent),
  cameraTrack=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame,
   keyframes:scenePlan.cameraKeyframes,totalFrames,fps:territoryPlan.fps});
 const bundle=await loadUploadBundle({manifestURL:'/astra-data/UPLOAD_MANIFEST.json',
  expectedManifestSha256:config.astra.bundleManifestSha256,maxBytes:128*1024*1024});
 if(!bundle.enabled||bundle.partCount===0)throw Error('ASTRA_ENABLED_SOURCE_DATA_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;
 document.body.replaceChildren(canvas);
 const pipeline=await createAstraGpuAdapter({canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,
  heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null,cameraTrack,
  territoryPlan,scenePlan,admittedNativeFraming},{bundle,profile:config.astra.materialProfile,testOnlySoftwareProbe});
 const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info'),
  backend=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
 if(typeof backend!=='string'||(testOnlySoftwareProbe?!/SwiftShader/i.test(backend):
  /swiftshader|llvmpipe|lavapipe|softpipe|software/i.test(backend)||!/\bNVIDIA\b/i.test(backend))){
  pipeline.dispose();throw Error('ASTRA_HARDWARE_NVIDIA_RENDERER_REQUIRED');
 }
 window.referenceProof={pipeline,scenePlan,territoryPlan,cameraTrack,
  async capture(frame,{png=true,territoryEnabled=true,combatEnabled=true}={}){
   const diagnostic=await pipeline.drawFrame(frame,{territoryEnabled,combatEnabled}),pixels=pipeline.readPixels();
   diagnostic.territory.controls=evaluateTerritoryControlFrame(territoryPlan,territoryPlan.startFrame+frame);
   diagnostic.astraActivation={activationSha256:config.astra.activationSha256,
    bundleManifestSha256:config.astra.bundleManifestSha256,
    compositionOwner:'UNCHANGED_V4_BEFORE_TERRITORY_AND_FRONTIER',actualMaterialFactorySelected:true,
    testOnly:testOnlySoftwareProbe,gpuRenderingVerified:false};
   const result={diagnostic,raw_rgba_sha256:await digest(pixels)};
   if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),
    value=>value.charCodeAt(0)));}return result;
  },dispose(){pipeline.dispose();}};
 return {evidence:pipeline.evidence,backend,runtimeConfig:config,cameraMotion:assessReferenceCameraMotion(cameraTrack),
  cameraKeyframeBinding:JSON.stringify(scenePlan.cameraKeyframes),domainGeometryBinding:territoryPlan.domainGeometryBinding,
  boundaryKeyframeBinding:territoryPlan.boundaryKeyframeBinding,actualCameraLocked:false,surveyAdmissionModified:false,
  productionEligible:!testOnlySoftwareProbe&&mode==='VISUAL_REFERENCE_STUDY',testOnly:testOnlySoftwareProbe,
  gpuRenderingVerified:false,optionalNativeForegroundExcludedByNewScene:true,
  oldNativeForegroundPixelIdentityClaimed:false,inheritedNativeAdmissionSha256:admittedNativeFraming.sha256,
  inheritedNativeFramingBounds:admittedNativeFraming.bounds,astra:{...config.astra,actualMaterialFactorySelected:true,
   noFinalFrameOverlay:true,oldRendererSourceUnchanged:true,actualGpuQualityApproved:false}};
}
