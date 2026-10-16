/** Explicit reference expression selection before the unchanged Quality/ASTRA boot. */
import {bootQualityRuntime} from '/quality/quality_adapter.mjs';
import {setReferenceSourceProfile,createNativeDomainBinding} from './reference_source_material.mjs';
import {setReferenceTerritoryProfile} from './gain_territory.mjs';
import {setReferenceFrontierProfile} from './frontier_ref2.mjs';

const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))]
 .map(byte=>byte.toString(16).padStart(2,'0')).join('');
const load=async url=>{const response=await fetch(url,{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('REFERENCE_RUNTIME_INPUT_HTTP_'+response.status);return response.json();};

export async function bootReferenceRuntime({testOnlySoftwareProbe=false}={}){
 const config=await load('/runtime-config.json'),reference=config.referenceV2;
 if(!reference||reference.family!=='REFERENCE_VISUAL_MASTER_V2'||!['A','B','C','D','E','F'].includes(reference.variant)
  ||reference.qualityApproved!==false||reference.hardwareVerified!==false)
  throw Error('REFERENCE_EXPLICIT_BOUND_PROFILE_REQUIRED');
 if(typeof testOnlySoftwareProbe!=='boolean'||testOnlySoftwareProbe!==(config.testOnlySoftwareProbe===true))
  throw Error('REFERENCE_EXPLICIT_SOFTWARE_PROBE_PROVENANCE_REQUIRED');
 const scene=config.bootstrap.scenePlan;
 if(await digest(scene)!==reference.actualSceneSha256||await digest(scene.cameraKeyframes)!==reference.cameraKeyframeSha256)
  throw Error('REFERENCE_ACTUAL_SCENE_HASH_MISMATCH');
 let domainBinding=null;
 if(reference.source.registerDomainCoverage){
  const regional=await load('/inputs/regional.json');
  domainBinding=await createNativeDomainBinding({primary:regional.primary,secondary:regional.secondary,
   geometries:regional.geometries,domain:scene.controlIntent.domain,eventStartFrame:scene.controlIntent.start_frame});
 }
 // Each setter validates its own normalized bounded group. Node-only camera,
 // unit and filesystem profile planners are never imported into the browser.
 setReferenceSourceProfile(reference.source,{domainBinding});
 setReferenceTerritoryProfile(reference.territory);
 setReferenceFrontierProfile(reference.frontier,{domainBinding});
 const info=await bootQualityRuntime({testOnlySoftwareProbe}),proof=window.referenceProof,
  capture=proof.capture.bind(proof),evidence=info.evidence,
  actualFactories={sourceGrade:evidence.terrainPass?.sourceGrade?.enabled===true,
   gainedTerritory:evidence.territoryPass?.gainTerritory?.actualFactorySelected===true,
   frontier:evidence.frontierPass?.referenceFrontier?.originalBoundaryAlgorithm===true,
   outerDomain:evidence.terrainPass?.nativeDomainCoverage?.registered===true};
 proof.capture=async(...args)=>{
  if(await digest(proof.scenePlan)!==reference.actualSceneSha256)throw Error('REFERENCE_CAPTURE_SCENE_CHANGED');
  const result=await capture(...args);
  result.diagnostic.qualityActivation={...result.diagnostic.qualityActivation,
   profileSha256:reference.profileSha256,cameraSceneSha256:reference.actualSceneSha256,
   frontierChanged:reference.frontier.enabled,baseProfile:'F',newReferenceOverrides:true};
  result.diagnostic.referenceV2={family:reference.family,variant:reference.variant,profileId:reference.profileId,
   profileSha256:reference.profileSha256,actualSceneSha256:reference.actualSceneSha256,
   cameraSceneSha256:reference.actualSceneSha256,cameraKeyframeSha256:reference.cameraKeyframeSha256,
   candidateCameraSceneSha256:reference.candidateCameraSceneSha256,
   cameraChanged:reference.cameraChanged,unitSizeChanged:reference.unitSizeChanged,
   actualFactories,compositionOrder:reference.compositionOrder,testOnly:info.testOnly,
   eventTimingChanged:false,objectTimingChanged:false,gpuVisualQualityVerified:false,qualityApproved:false};
  return result;
 };
 return {...info,referenceV2:{...reference,testOnly:info.testOnly,actualFactories,
  unchangedBoot:'QUALITY_F_TO_ASTRA_TO_ORIGINAL_V4',rendererCoreCopied:false,
  gpuVisualQualityVerified:false,qualityApproved:false}};
}
export const bootRef2Runtime=bootReferenceRuntime;
