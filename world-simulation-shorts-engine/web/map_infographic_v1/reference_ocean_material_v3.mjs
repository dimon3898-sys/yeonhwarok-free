/** Original WORLD ENGINE ocean appearance for the isolated visual-upgrade shot.
 *
 * Actual source RGB and the unchanged Native GIS coverage own all geographic
 * facts. Source brightness supplies bathymetry-inspired tonal variation, never
 * a depth measurement. The low-amplitude analytical surface pattern is authored
 * appearance, never a tsunami/water simulation or an acquired ocean dataset.
 * This helper owns no texture, framebuffer, projection, or moving geometry.
 */
export const REFERENCE_OCEAN_MATERIAL_V3_VERSION='REFERENCE_OCEAN_MATERIAL_V3';
export const DEFAULT_REFERENCE_OCEAN_PROFILE_V3=Object.freeze({
 profileName:'WORLD_ENGINE_REGISTERED_BLUE_OCEAN_V3',
 deepTint:Object.freeze([10/255,30/255,53/255]),
 midTint:Object.freeze([21/255,63/255,86/255]),
 nearshoreTint:Object.freeze([28/255,88/255,104/255]),
 sourceLumaRange:Object.freeze([.54,.77]),
 sourceAnchor:.68,sourceContrast:1.35,nearshoreMix:.58,
 microStrength:.028,glintStrength:.012,driftRadiansPerSecond:.16,
 microCyclesPerDegree:19,
});

const clone=value=>structuredClone(value);
const colors=['deepTint','midTint','nearshoreTint'];
const ranges={sourceAnchor:[.001,1],sourceContrast:[.5,2.5],nearshoreMix:[0,.75],
 microStrength:[0,.04],glintStrength:[0,.02],driftRadiansPerSecond:[0,.35],
 microCyclesPerDegree:[4,40]};

export function validateReferenceOceanProfileV3(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('OCEAN_PROFILE_OBJECT_REQUIRED');
 const allowed=new Set(Object.keys(DEFAULT_REFERENCE_OCEAN_PROFILE_V3));
 for(const key of Object.keys(input))if(!allowed.has(key))throw Error('OCEAN_PROFILE_UNKNOWN_FIELD_'+key);
 const p={...clone(DEFAULT_REFERENCE_OCEAN_PROFILE_V3),...clone(input)};
 if(typeof p.profileName!=='string'||!p.profileName.length)throw Error('OCEAN_PROFILE_NAME_REQUIRED');
 for(const key of colors)if(!Array.isArray(p[key])||p[key].length!==3||
  !p[key].every(value=>Number.isFinite(value)&&value>=0&&value<=1))throw Error('OCEAN_PROFILE_RGB_INVALID_'+key);
 if(!Array.isArray(p.sourceLumaRange)||p.sourceLumaRange.length!==2||
  !p.sourceLumaRange.every(value=>Number.isFinite(value)&&value>=0&&value<=1)||
  p.sourceLumaRange[1]-p.sourceLumaRange[0]<.01)throw Error('OCEAN_PROFILE_SOURCE_RANGE_INVALID');
 for(const [key,[low,high]] of Object.entries(ranges))if(!Number.isFinite(p[key])||p[key]<low||p[key]>high)
  throw Error('OCEAN_PROFILE_RESTRAINED_RANGE_INVALID_'+key);
 return p;
}

const float=value=>Number(value).toFixed(9);
const vec3=value=>'vec3('+value.map(float).join(',')+')';

/** No extra sampler reads. Call for every fragment before land/sea mixing so
 * implicit derivatives remain defined. Coast proximity comes from real GIS
 * neighbours sampled by the one material pass, not inferred coast geometry.
 */
export function buildReferenceOceanGlslV3(input={}){
 const p=validateReferenceOceanProfileV3(input);
 return `
// WORLD ENGINE original analytical surface appearance. Not measured water.
float worldEngineFilteredRipple(float phase){
 // Suppress under-resolved harmonics rather than letting fine waves flicker.
 float footprint=fwidth(phase);
 float resolved=1.-smoothstep(1.2,3.0,footprint);
 return sin(phase)*resolved;
}
vec3 worldEngineOceanMaterial(vec2 geo,vec3 actualSource,float coastalProximity,float frameTimeSec){
 float sourceY=clamp(dot(actualSource,vec3(.2126,.7152,.0722)),.001,1.);
 float sourceTone=smoothstep(${float(p.sourceLumaRange[0])},${float(p.sourceLumaRange[1])},sourceY);
 vec3 sea=mix(${vec3(p.deepTint)},${vec3(p.midTint)},sourceTone);
 sea*=clamp(pow(sourceY/${float(p.sourceAnchor)},${float(p.sourceContrast)}),.70,1.22);
 // The nearshore transition changes material only. The Native coast is intact.
 float coast=clamp(coastalProximity,0.,1.);
 sea=mix(sea,${vec3(p.nearshoreTint)},coast*${float(p.nearshoreMix)});

 // Geographic anchoring prevents texture swimming during camera pan/zoom/roll.
 // Latitude correction describes a local tangent-plane appearance, not depth.
 vec2 p=geo*vec2(max(cos(radians(geo.y)),.2),1.);
 float drift=frameTimeSec*${float(p.driftRadiansPerSecond)};
 float frequency=6.28318530718*${float(p.microCyclesPerDegree)};
 float bend=sin(dot(p,vec2(.43,.71))*1.7)*.65;
 float phaseA=dot(p,vec2(.91,.31))*frequency+bend+drift;
 float phaseB=dot(p,vec2(-.24,.97))*frequency*.47-bend-drift*.63;
 float phaseC=dot(p,vec2(.66,-.75))*frequency*1.71+drift*.37;
 float a=worldEngineFilteredRipple(phaseA);
 float b=worldEngineFilteredRipple(phaseB);
 float c=worldEngineFilteredRipple(phaseC);
 float ripple=.52*a+.32*b+.16*c;
 sea*=1.+${float(p.microStrength)}*ripple;

 // Sparse low-energy highlights; no animated foam, flash, or repetitive blink.
 float glint=smoothstep(.91,1.,a)*smoothstep(.55,1.,b);
 float sourceModulation=.55+.45*sourceTone;
 sea+=vec3(.46,.70,.83)*glint*${float(p.glintStrength)}*sourceModulation*(1.-coast*.65);
 return clamp(sea,vec3(0.),vec3(1.));
}
`;
}

export const REFERENCE_OCEAN_GLSL_V3=buildReferenceOceanGlslV3();
export const REFERENCE_OCEAN_EVIDENCE_V3=Object.freeze({
 version:REFERENCE_OCEAN_MATERIAL_V3_VERSION,
 source:'SHA_VERIFIED_ORIGINAL_REGISTERED_NE1_RGB_FROM_OWNER_MATERIAL_PASS',
 geography:'UNCHANGED_NATIVE_GIS_COVERAGE_AND_SOURCE_GEOREGISTRATION',
 bathymetry:'SOURCE_COLOR_INSPIRED_NO_MEASURED_DEPTH_CLAIM',
 waves:'ORIGINAL_ANALYTICAL_VISUAL_MICROTEXTURE_NO_PHYSICS_OR_HAZARD_CLAIM',
 originality:'AUTHORED_WORLD_ENGINE_GLSL_NO_REFERENCE_ART_TEXTURE_SAMPLING',
 ownership:'NEW_ISOLATED_STUDY_PROFILE_ONLY',
 extraTextureReads:0,extraTextures:0,extraDrawCalls:0,
 phaseAnchor:'GEOGRAPHIC_COORDINATES',deterministic:true,
 derivativeFiltered:true,coastlineChanged:false,
 exactOceanReferenceParityClaimed:false,
});
