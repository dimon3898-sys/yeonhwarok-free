/** Exact import-map extension of the original white/front-motion pass.
 * Disabled means the original object is returned with no allocation or draw.
 */
import {createControlFrontierLightPassV3 as createOriginal}
 from '/modules/reference_control_frontier_light_v3.mjs?baseline';
export * from '/modules/reference_control_frontier_light_v3.mjs?baseline';
import {describeNativeDomainBinding,getNativeDomainCoverage} from './native_domain_coverage.mjs';
import {validateReferenceFrontierProfile,applyReferenceFrontierStyle,assertOuterDomainContext,REFERENCE_FRONTIER_EXPRESSION_VERSION}
 from './frontier_profile_core.mjs';
import {createCoverageOuterGlowPass} from './coverage_outer_glow.mjs';
let selected=validateReferenceFrontierProfile(),binding=null,configured=false,factoryCreated=false;
export function setReferenceFrontierProfile(profile={},options={}){
 if(configured||factoryCreated)throw Error('REFERENCE_FRONTIER_PROFILE_ALREADY_BOUND');
 selected=validateReferenceFrontierProfile(profile);binding=options.domainBinding??null;
 if(selected.enabled&&selected.outerGoldIntensity>0)describeNativeDomainBinding(binding);
 configured=true;return Object.freeze({...selected});
}
export async function createControlFrontierLightPassV3(options={}){
 factoryCreated=true;
 if(!selected.enabled)return createOriginal(options);
 const sourceProfile=structuredClone(options.profile),effectiveProfile=applyReferenceFrontierStyle(options.profile,selected),
  meta=selected.outerGoldIntensity>0?describeNativeDomainBinding(binding):null;
 if(meta&&JSON.stringify(options.landDomain??options.territoryPlan?.intent?.domain)!==options.territoryPlan?.domainGeometryBinding)
  throw Error('REFERENCE_OUTER_ORIGINAL_DOMAIN_REQUIRED');
 if(meta){
  const bytes=new TextEncoder().encode(options.territoryPlan.domainGeometryBinding),
   sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
  if(sha!==meta.domainSHA256)throw Error('REFERENCE_OUTER_ORIGINAL_DOMAIN_SHA_MISMATCH');
 }
 const original=await createOriginal({...options,profile:effectiveProfile});let gold;
 try{
  if(meta){
   const gl=options.canvas.getContext('webgl2'),[{captureFlowNativeGlState:capture,restoreFlowNativeGlState:restore},
    {qualityProgram:programFactory,resetQualityPixels:resetPixels,setupQualityTexture:setupTexture}]=await Promise.all([
     import('/modules/flow_graphic_pass_v2.mjs'),import('/quality/support_gpu.mjs')]);
   gold=createCoverageOuterGlowPass({gl,width:options.width??1080,height:options.height??1920,profile:selected,capture,restore,programFactory,resetPixels,setupTexture});
  }
 }catch(error){original.dispose();throw error;}
 const expression={version:REFERENCE_FRONTIER_EXPRESSION_VERSION,profile:structuredClone(selected),sourceProfile,effectiveProfile,
  originalBoundaryAlgorithm:true,originalMotionAndStopLogic:true,originalGeometry:true,
  destinationLightingChanged:sourceProfile.minimumLightingFactor!==effectiveProfile.minimumLightingFactor,
  outerGoldDomain:meta?{domainSHA256:meta.domainSHA256,sourceGeometrySHA256:meta.sourceGeometrySHA256,roleIds:meta.selectedRoleIds}:null};
 return {evidence:{...original.evidence,referenceFrontier:expression},draw(args){
  let context=null;
  if(gold){
   context=getNativeDomainCoverage(options.canvas,{frame:args.controls.frame,domainSHA256:meta.domainSHA256});
   assertOuterDomainContext(context,{controls:args.controls,project:args.project,domainMetadata:meta,width:options.width??1080,height:options.height??1920});
  }
  const diagnostic=original.draw(args),outerDomainGold=gold?.draw({context,presentationScale:args.presentationScale,
   safeArea:args.safeArea,protectedGraphics:args.protectedGraphics})??null;
  return {...diagnostic,referenceFrontier:structuredClone(expression),outerDomainGold};
 },dispose(){gold?.dispose();original.dispose();}};
}
