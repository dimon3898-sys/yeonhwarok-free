/** Five presentation parameters over unchanged production engines. No geometry is generated here. */
export const INTEGRATION_SCHEMA='WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1';
export const INTEGRATION_PROFILE='VISUAL_UNIFIED_V1';
export const VISUAL_FIELDS=Object.freeze({
 territoryOpacity:Object.freeze({default:.62,min:.24,max:.8,units:'alpha'}),
 frontCoreWidthPixels:Object.freeze({default:4.8,min:2.5,max:7,units:'output pixels'}),
 frontGlowRadiusPixels:Object.freeze({default:10,min:3,max:16,units:'output pixels'}),
 frontGlowGain:Object.freeze({default:.42,min:.1,max:.65,units:'linear gain'}),
 cameraApproachFrames:Object.freeze({default:48,min:12,max:120,integer:true,units:'frames'})});
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value),
 hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 fail=code=>{throw Error(code);};
export function normalizeIntegrationVisualProfile(input={}){
 if(!object(input))fail('INTEGRATION_VISUAL_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(VISUAL_FIELDS,key))fail('INTEGRATION_VISUAL_FIELD_UNSUPPORTED');
 const result={};
 for(const [key,rule]of Object.entries(VISUAL_FIELDS)){
  const value=Object.hasOwn(input,key)?input[key]:rule.default;
  if(typeof value!=='number'||!Number.isFinite(value)||value<rule.min||value>rule.max||rule.integer&&!Number.isSafeInteger(value))
   fail('INTEGRATION_VISUAL_VALUE_INVALID_'+key);
  result[key]=value;
 }
 return Object.freeze(result);
}
/** Retain parent's white/gold colors, marker policy and geometry policy exactly. */
export function mergeIntegrationProductionProfile(parent,visualProfile){
 if(!object(parent)||parent.version!=='UNIVERSAL_PRODUCTION_VISUAL_V3')fail('INTEGRATION_PARENT_VISUAL_PROFILE_REQUIRED');
 return Object.freeze({...structuredClone(parent),...normalizeIntegrationVisualProfile(visualProfile)});
}
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))]
 .map(byte=>byte.toString(16).padStart(2,'0')).join('');
/** Server configuration is delivered only through the existing exact-SHA loopback server.
 * The profile's own digest is additionally checked in the browser before any factory call. */
export async function loadIntegrationRuntimeConfig({fetchConfig=globalThis.fetch}={}){
 if(typeof fetchConfig!=='function')fail('INTEGRATION_RUNTIME_FETCH_REQUIRED');
 const response=await fetchConfig('/runtime-config.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)fail('INTEGRATION_RUNTIME_HTTP_FAILED');
 const config=await response.json(),binding=config?.integrationV1;
 if(binding?.schema!==INTEGRATION_SCHEMA||binding.profile!==INTEGRATION_PROFILE
  ||!hex(binding.profileSha256)||!hex(binding.sourceManifestSha256)||!hex(binding.browserSourceSignature))
  fail('INTEGRATION_EXPLICIT_RUNTIME_BINDING_REQUIRED');
 const normalized=normalizeIntegrationVisualProfile(binding.visualProfile);
 if(JSON.stringify(normalized)!==JSON.stringify(binding.visualProfile)||await digest(normalized)!==binding.profileSha256)
  fail('INTEGRATION_RUNTIME_PROFILE_SHA_MISMATCH');
 return Object.freeze({...binding,visualProfile:normalized});
}
/** Dependency injection only makes CPU forwarding tests possible; production supplies the exact imported parent. */
export function bindProductionFactory(originalFactory,binding,kind){
 if(typeof originalFactory!=='function'||!['AREA','CAMERA'].includes(kind)
  ||binding?.schema!==INTEGRATION_SCHEMA||binding.profile!==INTEGRATION_PROFILE||!hex(binding.profileSha256))
  fail('INTEGRATION_PARENT_FACTORY_AND_BINDING_REQUIRED');
 const visualProfile=normalizeIntegrationVisualProfile(binding.visualProfile);
 return input=>{
  if(!object(input))fail('INTEGRATION_FACTORY_INPUT_REQUIRED');
  const profile=mergeIntegrationProductionProfile(input.profile,visualProfile),owner=originalFactory({...input,profile});
  if(!object(owner)||typeof owner[kind==='AREA'?'draw':'drawNative']!=='function')fail('INTEGRATION_PARENT_FACTORY_API_INVALID');
  return {...owner,evidence:{...structuredClone(owner.evidence??{}),integrationV1:{
   schema:INTEGRATION_SCHEMA,profile:INTEGRATION_PROFILE,kind,profileSha256:binding.profileSha256,
   consumedVisualProfile:{...visualProfile},existingEngineCalled:true,originalGeometryAndMasksRetained:true,
   hardwareVerified:false,visualOutputVerified:false}}};
 };
}
