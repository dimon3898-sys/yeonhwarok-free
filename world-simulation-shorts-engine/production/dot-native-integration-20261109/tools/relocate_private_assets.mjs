/** Relocation of server resource paths only; source pixels and source provenance stay immutable. */
import {cp,readFile,writeFile,mkdir,access} from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';import {pathToFileURL} from 'node:url';
const [priorRegistry,expectedPin,sourceRoot,destination,codeRoot]=process.argv.slice(2),hash=b=>createHash('sha256').update(b).digest('hex'),check=(v,c)=>{if(!v)throw Error(c)};
const raw=await readFile(priorRegistry);check(hash(raw)===expectedPin,'RELOCATION_PRIOR_REGISTRY_PIN');const data=JSON.parse(raw);
await mkdir(destination,{mode:0o700,recursive:true});
const exists=async p=>{try{await access(p);return true;}catch{return false;}};if(!await exists(path.join(destination,'files')))await cp(path.join(sourceRoot,'files'),path.join(destination,'files'),{recursive:true,errorOnExist:true,force:false});
if(!await exists(path.join(destination,'repository')))await cp(path.join(sourceRoot,'repository'),path.join(destination,'repository'),{recursive:true,errorOnExist:true,force:false});
if(!await exists(path.join(destination,'prior-metadata')))await cp(path.join(sourceRoot,'repinned-metadata'),path.join(destination,'prior-metadata'),{recursive:true,errorOnExist:true,force:false});
if(!await exists(path.join(destination,'prior-browser-records')))await cp(path.join(sourceRoot,'private-browser-records'),path.join(destination,'prior-browser-records'),{recursive:true,errorOnExist:true,force:false});
const rewrite=x=>typeof x==='string'&&x.startsWith(sourceRoot+'/')?path.join(destination,x.slice(sourceRoot.length+1)).replace('/repinned-metadata','/prior-metadata').replace('/private-browser-records','/prior-browser-records'):Array.isArray(x)?x.map(rewrite):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,rewrite(v)])):x;
const meta=path.join(destination,'native-metadata');await mkdir(meta,{mode:0o700,recursive:true});
async function emit(name,b){const file=path.join(meta,name);await writeFile(file,b,{flag:'wx',mode:0o600});return{sourcePath:file,bytes:Buffer.byteLength(b),sha256:hash(b)};}
const asset=rewrite(data.assetRegistryEntries[0][1]);
const binaryPath=path.join(asset.window.binary.root,asset.window.binary.descriptor.localFile),binaryBytes=await readFile(binaryPath);check(hash(binaryBytes)===asset.window.binary.descriptor.sha256,'RELOCATION_BINARY_PIN');
const binary=await emit('BINARY_LAYER_DESCRIPTORS_V3.json',JSON.stringify(rewrite(JSON.parse(binaryBytes))));asset.window.binary={root:meta,descriptor:{localFile:path.basename(binary.sourcePath),bytes:binary.bytes,sha256:binary.sha256}};
const tex=await readFile(asset.textureDescriptor.sourcePath);check(hash(tex)===asset.textureDescriptor.sha256,'RELOCATION_TEXTURE_PIN');asset.textureDescriptor=await emit('INTEGRATION_DESCRIPTOR.json',JSON.stringify(rewrite(JSON.parse(tex))));
data.assetRegistryEntries=[[data.assetRegistryEntries[0][0],asset]];
const{prepareRegisteredFrameWindow}=await import(pathToFileURL(path.join(codeRoot,'official-candidate-v1/candidate_frame_window.mjs')));
const{buildFixedRegistrationModule}=await import(pathToFileURL(path.join(sourceRoot,'tools/build_fixed_registration.mjs')));
let windows=0;
for(const entry of data.registrations){const r=entry.record;
 // Prepared native source receipts remain the original qualifications. The new
 // private registry serves every browser resource from the safe destination.
 r.resources=r.resources.map(rewrite);
 for(const w of r.windows){const result=await prepareRegisteredFrameWindow({request:w.request,registry:new Map([[data.assetRegistryEntries[0][0],asset.window]])});w.windowQualificationSha256=result.sourceQualificationSHA256;windows++;}
 const generated=buildFixedRegistrationModule([r]),fixed=await emit(entry.id+'-registration.mjs',generated.source);
 const registration=r.resources.find(x=>x.url==='/web/map_infographic_v1/official_candidate_registration.mjs');registration.sourcePath=fixed.sourcePath;registration.pin={bytes:fixed.bytes,sha256:fixed.sha256};
 for(const [file,url]of [
 ['official-candidate-v1/presentation_runtime_nvidia.generated.mjs','/recovery/universal-presentation-v2/presentation_runtime.mjs'],
 ['codex-to-gcube-handoff-v1/backend/native_guard_candidate.mjs','/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs']]){
  const b=await readFile(path.join(codeRoot,file));const pin=await emit(entry.id+'-'+path.basename(file),b);
  r.resources=r.resources.filter(old=>old.url!==url);r.resources.push({url,sourcePath:pin.sourcePath,pin:{bytes:pin.bytes,sha256:pin.sha256},kind:'module',mime:'text/javascript'});
 }
}
const result=Buffer.from(JSON.stringify(data));await writeFile(path.join(destination,'OFFICIAL_NATIVE_REGISTRY.json'),result,{flag:'wx',mode:0o600});
console.log(JSON.stringify({schema:'WORLD_ENGINE_NATIVE_SAFE_ROOT_RELOCATION_V1',status:'PREPARED_INACTIVE',registrySHA256:hash(result),registrations:data.registrations.length,windowsRepinned:windows,sourcePixelsChanged:false,oldFilesChanged:false,systemPermissionsChanged:false,activated:false,gpuExecuted:false}));
