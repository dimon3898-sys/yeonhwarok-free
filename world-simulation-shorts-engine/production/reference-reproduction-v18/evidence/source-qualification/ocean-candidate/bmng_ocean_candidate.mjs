/** Isolated CPU proposal. No renderer import, texture edits or admission. */
import {validateReferenceOceanProfileV4,buildReferenceOceanGlslV4} from './source/reference_ocean_material_v4.mjs';
export const BMNG_PROFILE=Object.freeze({...validateReferenceOceanProfileV4({
 profileName:'BMNG_SOURCE_TONE_CANDIDATE_QUALIFICATION_REQUIRED',
 sourceLumaRange:[.005,.30],sourceAnchor:.05,sourceContrast:.75,
 nearshoreMix:0,sourceChromaRetention:.35,
}),sourceLumaRange:Object.freeze([.005,.30])});
export const EVIDENCE=Object.freeze({status:'QUALIFICATION_REQUIRED',productionAdmitted:false,
 inputColorSpace:'SRGB_ENCODED_0_1',outputColorSpace:'SRGB_ENCODED_0_1',
 source:'PINNED_REAL_BMNG_BASELINE_ONLY',geographicDepthData:false,
 authoredWaves:false,nearshoreBand:false,frameDependentParameters:false,
 remainingChecks:['shoreline mask qualification','explicit renderer color conversion','visual review after authorization','runtime binding and preserved-default proof']});
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const mix=(a,b,t)=>a*(1-t)+b*t;
const smooth=(a,b,x)=>{const t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
const rgb=c=>Array.isArray(c)&&c.length===3&&c.every(v=>Number.isFinite(v)&&v>=0&&v<=1);
export function evaluateSourceTone(source,profile=BMNG_PROFILE){
 if(!rgb(source))throw Error('ENCODED_SOURCE_RGB_REQUIRED');
 const p=validateReferenceOceanProfileV4(profile),y=clamp(source[0]*.2126+source[1]*.7152+source[2]*.0722,.001,1);
 const tone=smooth(...p.sourceLumaRange,y),gain=clamp((y/p.sourceAnchor)**p.sourceContrast,.70,1.22);
 return p.deepTint.map((v,i)=>clamp(mix(v,p.midTint[i],tone)*gain*mix(1,clamp(source[i]/y,.65,1.35),p.sourceChromaRetention),0,1));
}
/** Requires the entire declared sampling footprint to be valid known water.
 * Class80 means permanent water, not necessarily ocean. Unknown, mixed coasts,
 * inland/ocean identity and runtime footprint truth remain separate gates.
 */
export function evaluateCandidate({enabled=false,source,baselineSea,footprint,landCoverage}){
 if(!rgb(baselineSea))throw Error('BASELINE_SEA_RGB_REQUIRED');
 if(!enabled)return [...baselineSea];
 if(!footprint||!Number.isSafeInteger(footprint.samples)||footprint.samples<1)throw Error('DECLARED_FOOTPRINT_REQUIRED');
 for(const k of ['knownLand','knownWater','unknown','valid'])if(!Number.isSafeInteger(footprint[k])||footprint[k]<0||footprint[k]>footprint.samples)throw Error('FOOTPRINT_COUNTS_INVALID');
 if(footprint.knownLand+footprint.knownWater+footprint.unknown!==footprint.samples)throw Error('TRISTATE_PARTITION_REQUIRED');
 if(!Number.isFinite(landCoverage)||landCoverage<0||landCoverage>1)throw Error('LAND_COVERAGE_REQUIRED');
 if(landCoverage!==0||footprint.knownWater!==footprint.samples||footprint.valid!==footprint.samples)return [...baselineSea];
 return evaluateSourceTone(source);
}
export const CANDIDATE_GLSL=buildReferenceOceanGlslV4(BMNG_PROFILE);
