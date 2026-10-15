/** Explicit new visual profile selection around the unchanged ASTRA/V4 browser boot. */
import {bootAstraRuntime} from '/astra/astra_adapter.mjs';
import {setQualityMaterialProfile} from './quality_material.mjs';
import {setQualityTerritoryProfile} from './quality_territory.mjs';

export async function bootQualityRuntime({testOnlySoftwareProbe=false}={}){
 const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('QUALITY_RUNTIME_CONFIG_UNAVAILABLE');
 const config=await response.json(),quality=config.quality;
 if(!quality||!['A','B','C','D','E','F'].includes(quality.profile)||quality.qualityApproved!==false)
  throw Error('QUALITY_EXPLICIT_BOUND_PROFILE_REQUIRED');
 setQualityMaterialProfile({boundary:quality.boundary,screenFeatherPixels:quality.screenFeatherPixels});
 setQualityTerritoryProfile({enabled:quality.territory,profile:quality.territoryProfile});
 const info=await bootAstraRuntime({testOnlySoftwareProbe}),proof=window.referenceProof,
  originalCapture=proof.capture.bind(proof);
 proof.capture=async(...args)=>{
  const result=await originalCapture(...args);
  result.diagnostic.qualityActivation={profile:quality.profile,profileSha256:quality.profileSha256,
   cameraSceneSha256:quality.cameraSceneSha256,cameraChanged:quality.cameraChanged,
   boundary:quality.boundary,territory:quality.territory,frontierChanged:false,
   compositionOrder:quality.compositionOrder,testOnly:info.testOnly,gpuVisualQualityVerified:false};
  return result;
 };
 return {...info,quality:{...quality,testOnly:info.testOnly,gpuVisualQualityVerified:false,
  unchangedBoot:'ASTRA_GPU_ACTIVATION_V1_BOOT_REUSED',wholeRendererCopied:false,qualityApproved:false}};
}
