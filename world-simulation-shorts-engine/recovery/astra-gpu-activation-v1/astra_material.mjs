/** Exact standard-import-map decorator, selected only by the opt-in ASTRA lane.
 * Query bypass loads the ORIGINAL factory bytes. No protected module rewriting.
 */
import {createReferenceTerrainMaterialPassV4 as createBaseline,validateReferenceTerrainProfileV4}
 from '/modules/reference_terrain_material_v4.mjs?baseline';
import {createUploadTextures,describeUploadBundle} from '/astra-upload/gpu_upload.mjs';
import {createAstraCompositionPass,validateAstraProfile} from './astra_material_core.mjs';
export {REFERENCE_TERRAIN_MATERIAL_V4_VERSION,DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,validateReferenceTerrainProfileV4}
 from '/modules/reference_terrain_material_v4.mjs?baseline';
const configurations=new WeakMap();
export function configureAstraMaterialForCanvas(canvas,{bundle,profile={},testOnlyContext=false,testOnlySoftwareProbe=false}={}){
 if(!canvas||typeof canvas.getContext!=='function')throw Error('ASTRA_CANVAS_REQUIRED');
 if(configurations.has(canvas))throw Error('ASTRA_CANVAS_ALREADY_CONFIGURED');
 const manifest=describeUploadBundle(bundle);
 if(!manifest.enabled||!Object.values(manifest.sources).some(s=>s.status==='available'&&s.parts.length))
  throw Error('ASTRA_ENABLED_VERIFIED_SOURCE_REQUIRED');
 if(typeof testOnlyContext!=='boolean'||typeof testOnlySoftwareProbe!=='boolean')throw Error('ASTRA_EXPLICIT_TEST_PROVENANCE_REQUIRED');
 configurations.set(canvas,{bundle,profile:validateAstraProfile(profile),testOnlyContext,testOnlySoftwareProbe});
 return Object.freeze({schema:'ASTRA_MATERIAL_SELECTION_V1',manifestSha256:bundle.manifestSha256,
  sourcePartCount:bundle.partCount,selected:true,gpuRenderingVerified:false});
}
export function clearAstraMaterialForCanvas(canvas){configurations.delete(canvas);}
export async function createReferenceTerrainMaterialPassV4(options={}){
 const configuration=configurations.get(options.canvas);
 if(!configuration)throw Error('ASTRA_MATERIAL_NOT_CONFIGURED');
 const baseline=await createBaseline(options),gl=options.canvas.getContext('webgl2',
  {alpha:false,antialias:false,preserveDrawingBuffer:true});
 let uploads;
 try{
  const {captureFlowNativeGlState:capture,restoreFlowNativeGlState:restore}=await import('/modules/flow_graphic_pass_v2.mjs');
  const allocated=createUploadTextures(gl,configuration.bundle,{testOnlyContext:configuration.testOnlyContext});
  uploads=configuration.testOnlySoftwareProbe?Object.freeze({...allocated,testOnly:true}):allocated;
  const pass=createAstraCompositionPass({gl,baseline,uploads,profile:configuration.profile,
   baselineProfile:validateReferenceTerrainProfileV4(options.profile),width:options.width??1080,height:options.height??1920,capture,restore});
  pass.evidence.astra.manifestSha256=configuration.bundle.manifestSha256;
  return pass;
 }catch(error){uploads?.dispose();baseline.dispose();throw error;}
}
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
