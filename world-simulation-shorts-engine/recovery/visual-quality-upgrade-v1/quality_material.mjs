/** Opt-in standard-import-map source factory. Old A path is called unchanged. */
import {createReferenceTerrainMaterialPassV4 as createBaseline,validateReferenceTerrainProfileV4}
 from '/modules/reference_terrain_material_v4.mjs?baseline';
import {createReferenceTerrainMaterialPassV4 as createOldAstra,configureAstraMaterialForCanvas as configureOld,
 clearAstraMaterialForCanvas as clearOld} from '/astra/astra_material.mjs?baseline';
import {validateAstraProfile} from '/astra/astra_material_core.mjs';
import {createUploadTextures,describeUploadBundle} from '/astra-upload/gpu_upload.mjs';
import {createQualityCompositionPass,validateBoundaryProfile} from './quality_material_core.mjs';
export {REFERENCE_TERRAIN_MATERIAL_V4_VERSION,DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,validateReferenceTerrainProfileV4}
 from '/modules/reference_terrain_material_v4.mjs?baseline';
const configurations=new WeakMap();
let defaultQualityProfile=null,canvasConfigured=false;
export function setQualityMaterialProfile(profile){
 if(defaultQualityProfile||canvasConfigured)throw Error('QUALITY_PROFILE_ALREADY_SELECTED');
 defaultQualityProfile=validateBoundaryProfile(profile);return defaultQualityProfile;
}
export function configureAstraMaterialForCanvas(canvas,{bundle,profile={},qualityProfile,testOnlyContext=false,testOnlySoftwareProbe=false}={}){
 if(!canvas||typeof canvas.getContext!=='function'||configurations.has(canvas))throw Error('QUALITY_UNCONFIGURED_CANVAS_REQUIRED');
 if(qualityProfile===undefined&&!defaultQualityProfile)throw Error('QUALITY_PROFILE_SELECTION_REQUIRED');
 const manifest=describeUploadBundle(bundle),p=validateAstraProfile(profile),q=validateBoundaryProfile(qualityProfile??defaultQualityProfile);
 if(!manifest.enabled||!Object.values(manifest.sources).some(s=>s.status==='available'&&s.parts.length))throw Error('QUALITY_VERIFIED_SOURCES_REQUIRED');
 if(typeof testOnlyContext!=='boolean'||typeof testOnlySoftwareProbe!=='boolean')throw Error('QUALITY_EXPLICIT_TEST_FLAGS_REQUIRED');
 if(!q.boundary)configureOld(canvas,{bundle,profile:p,testOnlyContext,testOnlySoftwareProbe});
 configurations.set(canvas,{bundle,profile:p,qualityProfile:q,testOnlyContext,testOnlySoftwareProbe});
 canvasConfigured=true;
 return Object.freeze({schema:'QUALITY_MATERIAL_SELECTION_V1',boundary:q.boundary,manifestSha256:bundle.manifestSha256,
  gpuRenderingVerified:false,renderAllowed:false});
}
export function clearAstraMaterialForCanvas(canvas){configurations.delete(canvas);clearOld(canvas);}
export async function createReferenceTerrainMaterialPassV4(options={}){
 const c=configurations.get(options.canvas);if(!c)throw Error('QUALITY_MATERIAL_NOT_CONFIGURED');
 if(!c.qualityProfile.boundary)return createOldAstra(options);
 const baseline=await createBaseline(options),gl=options.canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 let uploads;
 try{
  const {captureFlowNativeGlState:capture,restoreFlowNativeGlState:restore}=await import('/modules/flow_graphic_pass_v2.mjs');
  const allocated=createUploadTextures(gl,c.bundle,{testOnlyContext:c.testOnlyContext});
  uploads=c.testOnlySoftwareProbe?Object.freeze({...allocated,testOnly:true}):allocated;
  const pass=createQualityCompositionPass({gl,baseline,uploads,profile:c.profile,qualityProfile:c.qualityProfile,
   baselineProfile:validateReferenceTerrainProfileV4(options.profile),width:options.width??1080,height:options.height??1920,capture,restore});
  pass.evidence.astra.manifestSha256=c.bundle.manifestSha256;return pass;
 }catch(error){uploads?.dispose();baseline.dispose();throw error;}
}
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
