/** Registered-source ocean appearance for the isolated visual bundle.
 * Original NE1 colour and unchanged Native GIS coverage own geography.
 * Baked water colour supplies depth-inspired tone, never a depth measurement.
 * V4 removes analytical ripples, glints and phase drift: there is no authored
 * wave pattern to repeat or swim through the camera's geographical projection.
 */
export const REFERENCE_OCEAN_MATERIAL_V4_VERSION='REFERENCE_OCEAN_MATERIAL_V4';
export const DEFAULT_REFERENCE_OCEAN_PROFILE_V4=Object.freeze({
 profileName:'WORLD_ENGINE_SOURCE_TONE_BLUE_OCEAN_V4',
 deepTint:Object.freeze([10/255,27/255,45/255]),
 midTint:Object.freeze([18/255,60/255,81/255]),
 nearshoreTint:Object.freeze([33/255,90/255,104/255]),
 sourceLumaRange:Object.freeze([.56,.77]),
 sourceAnchor:.68,sourceContrast:1.20,sourceChromaRetention:.35,nearshoreMix:.42,
 // Kept as explicit zero energy fields for reproducible scene profiles.
 // Validation rejects enabling the previous visible procedural wave pattern.
 microStrength:0,glintStrength:0,driftRadiansPerSecond:0,
});
const clone=value=>structuredClone(value);
const colours=['deepTint','midTint','nearshoreTint'];
const ranges={sourceAnchor:[.001,1],sourceContrast:[.5,2.5],sourceChromaRetention:[0,.6],nearshoreMix:[0,.6]};

export function validateReferenceOceanProfileV4(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('OCEAN_PROFILE_OBJECT_REQUIRED');
 const allowed=new Set(Object.keys(DEFAULT_REFERENCE_OCEAN_PROFILE_V4));
 for(const key of Object.keys(input))if(!allowed.has(key))throw Error('OCEAN_PROFILE_UNKNOWN_FIELD_'+key);
 const p={...clone(DEFAULT_REFERENCE_OCEAN_PROFILE_V4),...clone(input)};
 if(typeof p.profileName!=='string'||!p.profileName)throw Error('OCEAN_PROFILE_NAME_REQUIRED');
 for(const key of colours)if(!Array.isArray(p[key])||p[key].length!==3||
  !p[key].every(value=>Number.isFinite(value)&&value>=0&&value<=1))throw Error('OCEAN_PROFILE_RGB_INVALID_'+key);
 if(!Array.isArray(p.sourceLumaRange)||p.sourceLumaRange.length!==2||
  !p.sourceLumaRange.every(value=>Number.isFinite(value)&&value>=0&&value<=1)||
  p.sourceLumaRange[1]-p.sourceLumaRange[0]<.01)throw Error('OCEAN_PROFILE_SOURCE_RANGE_INVALID');
 for(const [key,[low,high]] of Object.entries(ranges))if(!Number.isFinite(p[key])||p[key]<low||p[key]>high)
  throw Error('OCEAN_PROFILE_RESTRAINED_RANGE_INVALID_'+key);
 for(const key of ['microStrength','glintStrength','driftRadiansPerSecond'])
  if(p[key]!==0)throw Error('OCEAN_V4_PROCEDURAL_PATTERN_REMOVED_'+key);
 return p;
}
const float=value=>Number(value).toFixed(9);
const vec3=value=>'vec3('+value.map(float).join(',')+')';

/** No additional sampler reads, geometry, projected pattern or frame phase.
 * The owner material samples the verified source and actual GIS neighbourhood.
 */
export function buildReferenceOceanGlslV4(input={}){
 const p=validateReferenceOceanProfileV4(input);
 return `
// Source-tone appearance only; never measured bathymetry or water physics.
vec3 worldEngineOceanMaterial(vec2 geo,vec3 actualSource,float coastalProximity,float frameTimeSec){
 float sourceY=clamp(dot(actualSource,vec3(.2126,.7152,.0722)),.001,1.);
 float sourceTone=smoothstep(${float(p.sourceLumaRange[0])},${float(p.sourceLumaRange[1])},sourceY);
 vec3 sea=mix(${vec3(p.deepTint)},${vec3(p.midTint)},sourceTone);
 sea*=clamp(pow(sourceY/${float(p.sourceAnchor)},${float(p.sourceContrast)}),.70,1.22);
 // Low-energy colour residual comes solely from the licensed source sample.
 // It preserves irregular registered source variation without synthetic noise.
 vec3 sourceResidual=clamp(actualSource/sourceY,vec3(.65),vec3(1.35));
 sea*=mix(vec3(1.),sourceResidual,${float(p.sourceChromaRetention)});
 // Proximity changes only sea colour; unchanged Native GIS still owns land.
 float coast=clamp(coastalProximity,0.,1.);
 sea=mix(sea,${vec3(p.nearshoreTint)},coast*${float(p.nearshoreMix)});
 return clamp(sea,vec3(0.),vec3(1.));
}
`;
}

export const REFERENCE_OCEAN_GLSL_V4=buildReferenceOceanGlslV4();
export const REFERENCE_OCEAN_EVIDENCE_V4=Object.freeze({
 version:REFERENCE_OCEAN_MATERIAL_V4_VERSION,
 source:'SHA_VERIFIED_ORIGINAL_REGISTERED_NE1_RGB_FROM_OWNER_MATERIAL_PASS',
 geography:'UNCHANGED_NATIVE_GIS_COVERAGE_AND_SOURCE_GEOREGISTRATION',
 bathymetry:'SOURCE_COLOR_INSPIRED_NO_MEASURED_DEPTH_CLAIM',
 waves:'NO_ANALYTICAL_RIPPLE_GLINT_OR_PHASE_DRIFT',
 originality:'AUTHORED_SOURCE_TONE_RESPONSE_NO_REFERENCE_ART_TEXTURE_SAMPLING',
 ownership:'NEW_ISOLATED_STUDY_PROFILE_ONLY',
 extraTextureReads:0,extraTextures:0,extraDrawCalls:0,
 deterministic:true,proceduralWaveEnergy:0,frameDependentPattern:false,
 coastlineChanged:false,exactOceanReferenceParityClaimed:false,
});
