/** Versioned source decorator. Default disabled returns the preserved F pass.
 * The query edge must be served as the immutable original Quality module. */
import {createReferenceTerrainMaterialPassV4 as createQualityMaterial,
 configureAstraMaterialForCanvas as configureQuality,clearAstraMaterialForCanvas as clearQuality,
 setQualityMaterialProfile as setQualityProfile} from '/quality/quality_material.mjs?baseline';
export {REFERENCE_TERRAIN_MATERIAL_V4_VERSION,DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,validateReferenceTerrainProfileV4}
 from '/quality/quality_material.mjs?baseline';
import {createUploadTextures} from '/astra-upload/gpu_upload.mjs';
import {validateReferenceSourceProfile,sourceGradeIsNeutral} from './source_grade_core.mjs';
import {describeNativeDomainBinding,publishNativeDomainCoverage,clearNativeDomainCoverage} from './native_domain_coverage.mjs';
import {createReferenceSourceGradePass} from './source_grade_pass.mjs';
export {createNativeDomainBinding,describeNativeDomainBinding,getNativeDomainCoverage} from './native_domain_coverage.mjs';
const configurations=new WeakMap();let selected=validateReferenceSourceProfile(),binding=null,configured=false,factoryCreated=false;
export function setReferenceSourceProfile(profile={},options={}){
 if(configured||factoryCreated)throw Error('REFERENCE_SOURCE_PROFILE_ALREADY_BOUND');
 selected=validateReferenceSourceProfile(profile);binding=options.domainBinding??null;
 if(selected.registerDomainCoverage)describeNativeDomainBinding(binding);
 configured=true;return Object.freeze({...selected});
}
export function setQualityMaterialProfile(profile){
 return setQualityProfile(selected.enabled?{...profile,screenFeatherPixels:selected.screenFeatherPixels}:profile);
}
export function configureAstraMaterialForCanvas(canvas,options={}){
 if(configurations.has(canvas))throw Error('REFERENCE_SOURCE_CANVAS_ALREADY_CONFIGURED');
 const result=configureQuality(canvas,options);configurations.set(canvas,options);return result;
}
export function clearAstraMaterialForCanvas(canvas){configurations.delete(canvas);clearQuality(canvas);clearNativeDomainCoverage(canvas);}
export async function createReferenceTerrainMaterialPassV4(options={}){
 factoryCreated=true;const original=await createQualityMaterial(options),config=configurations.get(options.canvas);
 if(!selected.enabled&&!selected.registerDomainCoverage)return original;
 if(!config){original.dispose();throw Error('REFERENCE_SOURCE_CONFIGURED_CANVAS_REQUIRED');}
 let pass=original,uploads;
 try{
  if(selected.enabled&&!sourceGradeIsNeutral(selected)){
   const gl=options.canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true}),
    {captureFlowNativeGlState:capture,restoreFlowNativeGlState:restore}=await import('/modules/flow_graphic_pass_v2.mjs');
   const allocated=createUploadTextures(gl,config.bundle,{testOnlyContext:config.testOnlyContext??false});
   uploads=config.testOnlySoftwareProbe?Object.freeze({...allocated,testOnly:true}):allocated;
   pass=createReferenceSourceGradePass({gl,baseline:original,uploads,profile:selected,width:options.width??1080,height:options.height??1920,
    oceanTint:options.profile?.oceanProfile?.nearshoreTint??[33/255,90/255,104/255],capture,restore});
  }
 }catch(error){uploads?.dispose();original.dispose();throw error;}
 if(!selected.registerDomainCoverage)return pass;
 const owned=pass,domain=describeNativeDomainBinding(binding);
 return {evidence:{...owned.evidence,nativeDomainCoverage:{registered:true,...domain}},
  get outputTexture(){return owned.outputTexture;},get snapshotFrame(){return owned.snapshotFrame;},
  draw(args){const result=owned.draw(args),record=publishNativeDomainCoverage(options.canvas,binding,
   {...args,width:options.width??1080,height:options.height??1920});
   return {...result,nativeDomainCoverage:record};},
  dispose(){clearNativeDomainCoverage(options.canvas);owned.dispose();}};
}
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
