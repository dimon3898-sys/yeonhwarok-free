/** Candidate-only sea response continuity. All raster bytes and land/GIS stay pinned. */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const hash=x=>createHash('sha256').update(x).digest('hex');
const oldShader='a12cbde55d19c0624f71b71d5cb997323104d6daac381fde2f59f9d644a7f09f';
const [registryFile,expectedRegistry,probe]=process.argv.slice(2);
const raw=await readFile(registryFile);if(hash(raw)!==expectedRegistry)throw Error('WATER_EDGE_PARENT_REGISTRY_PIN');
const registry=JSON.parse(raw),root=path.join(probe,'water-edge-candidate');await mkdir(root,{mode:0o700});
const shaderResource=registry.registrations[0].record.resources.find(r=>r.url==='/web/map_infographic_v1/official_material_shader.mjs');
const moduleSource=await readFile(shaderResource.sourcePath,'utf8');if(hash(moduleSource)!==shaderResource.pin.sha256)throw Error('WATER_EDGE_PARENT_MODULE_PIN');
const moduleMatch=/export default ("[\s\S]*");\s*$/.exec(moduleSource);if(!moduleMatch)throw Error('WATER_EDGE_SHADER_EXPORT');
let shader=JSON.parse(moduleMatch[1]);if(hash(shader)!==oldShader)throw Error('WATER_EDGE_PARENT_SHADER_PIN');
function replaceOnce(before,after){
 const start=before.startsWith(' encoded=')?shader.indexOf('bool candidateWater('):0;
 const end=before.startsWith(' encoded=')?shader.indexOf('// Separate candidate samplers'):shader.length;
 const section=shader.slice(start,end);if(section.split(before).length!==2)throw Error('WATER_EDGE_EDIT_ANCHOR');
 shader=shader.slice(0,start)+section.replace(before,after)+shader.slice(end);
}
replaceOnce('bool candidateWater(vec2 geo,vec3 coverageValue,out vec3 encoded){','bool candidateWater(vec2 geo,vec3 coverageValue,out vec3 encoded,out float supportWeight){');
replaceOnce(' encoded=mix(mix(samples[0],samples[1],f.x),mix(samples[2],samples[3],f.x),f.y);\n return true;\n}',` encoded=mix(mix(samples[0],samples[1],f.x),mix(samples[2],samples[3],f.x),f.y);
 // Fade only INSIDE the already admitted four-tap known-water footprint.
 // Outside/unknown/land keeps the exact legacy response. No mask is expanded.
 float supportDistance=2.;
 for(int y=-1;y<=2;y++)for(int x=-1;x<=2;x++){
  ivec2 t=i+ivec2(x,y);bool supported=false;
  if(all(greaterThanEqual(t,ivec2(0)))&&all(lessThan(t,dims))){
   vec3 m=texelFetch(candidateMasks,t,0).rgb;
   supported=m.r==0.&&m.g==0.&&m.b==1.;
  }
  if(!supported){vec2 delta=abs(vec2(t)-q);supportDistance=min(supportDistance,max(delta.x,delta.y));}
 }
 supportWeight=smoothstep(1.,2.,supportDistance);
 return true;
}`);
replaceOnce(' vec3 candidateEncoded;\n if((mode==0||(mode==1&&candidateUnfilledSourceEnabled==1))&&globeProjection==0&&candidateWater(geo,cov,candidateEncoded))\n  sea=linearize(worldEngineOceanMaterial(geo,candidateEncoded,0.,0.));',' vec3 candidateEncoded;float candidateSupport=0.;\n if((mode==0||(mode==1&&candidateUnfilledSourceEnabled==1))&&globeProjection==0&&candidateWater(geo,cov,candidateEncoded,candidateSupport))\n  sea=mix(sea,linearize(worldEngineOceanMaterial(geo,candidateEncoded,0.,0.)),candidateSupport);');
const newShader=hash(shader),newModule='export const SHADER_SHA256='+JSON.stringify(newShader)+';\nexport default '+JSON.stringify(shader)+';\n';
const newShaderFile=path.join(root,'official_material_shader.mjs');await writeFile(newShaderFile,newModule,{flag:'wx',mode:0o600});
const labelUrl='/recovery/universal-presentation-v2/presentation_label_layer.mjs';
const labelResource=registry.registrations[0].record.resources.find(r=>r.url===labelUrl);
const labelBefore=await readFile(labelResource.sourcePath,'utf8');
if(hash(labelBefore)!=='bb0437e12780441458dd38b69cf6472aad09e063cfd0fb678810aa5452423391'||hash(labelBefore)!==labelResource.pin.sha256)throw Error('LABEL_PARENT_PIN');
const labelAnchor='  if(Number.isSafeInteger(prior)&&prior>=0&&prior<indices.length)';
if(labelBefore.split(labelAnchor).length!==2)throw Error('LABEL_EDIT_ANCHOR');
const labelAfter=labelBefore.replace(labelAnchor,`  // A stable left-below default prevents a reference date from moving merely
  // because the following scene begins with an empty hysteresis history.
  // Existing collision checks, geographic anchors, and valid prior slots win.
  if(reference&&pinStyle==='NONE'&&item.role==='NUMERIC')indices.splice(indices.indexOf(5),1),indices.unshift(5);
`+labelAnchor);
const labelFile=path.join(root,'presentation_label_layer.mjs');await writeFile(labelFile,labelAfter,{flag:'wx',mode:0o600});
for(const {record:r} of registry.registrations){
 if(r.shaderSha256!==oldShader)throw Error('WATER_EDGE_RECORD_PIN');r.shaderSha256=newShader;
 for(const resource of r.resources){
  if(resource.url==='/web/map_infographic_v1/official_material_shader.mjs'){
   resource.sourcePath=newShaderFile;resource.pin={bytes:Buffer.byteLength(newModule),sha256:hash(newModule)};
  }else if(resource.url===labelUrl){
   if(resource.pin.sha256!==hash(labelBefore))throw Error('LABEL_RESOURCE_PIN');
   resource.sourcePath=labelFile;resource.pin={bytes:Buffer.byteLength(labelAfter),sha256:hash(labelAfter)};
  }else if(resource.url==='/web/map_infographic_v1/official_candidate_registration.mjs'){
   const before=await readFile(resource.sourcePath,'utf8');if(hash(before)!==resource.pin.sha256||!before.includes(oldShader))throw Error('WATER_EDGE_FIXED_RECORD_PIN');
   const after=before.replaceAll(oldShader,newShader),target=path.join(root,hash(after)+'.mjs');await writeFile(target,after,{flag:'wx',mode:0o600});
   resource.sourcePath=target;resource.pin={bytes:Buffer.byteLength(after),sha256:hash(after)};
  }
 }
}
const newRegistryFile=path.join(root,'OFFICIAL_WATER_EDGE_REGISTRY.json'),registryBytes=JSON.stringify(registry)+'\n';
await writeFile(newRegistryFile,registryBytes,{flag:'wx',mode:0o600});
const envelopeFile=path.join(probe,'sealed_scene2.json'),envelope=JSON.parse(await readFile(envelopeFile));
const activation=envelope.candidateActivation;activation.registrySHA256=hash(registryBytes);
for(const chunk of activation.chunks){if(chunk.shaderSha256!==oldShader)throw Error('WATER_EDGE_ACTIVATION_PIN');chunk.shaderSha256=newShader;}
const canonical=x=>JSON.stringify(x,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
envelope.candidateActivationSHA256=hash(canonical(activation));
const newEnvelope=JSON.stringify(envelope);await writeFile(envelopeFile,newEnvelope);
const configFile=path.join(probe,'PROBE_CONFIG.json'),config=JSON.parse(await readFile(configFile));config.expectedSHA256=hash(newEnvelope);await writeFile(configFile,JSON.stringify(config));
const runnerFile=path.join(probe,'run_probe.mjs'),runner=await readFile(runnerFile,'utf8');
if(!runner.includes(registryFile)||!runner.includes(expectedRegistry))throw Error('WATER_EDGE_RUNNER_ANCHOR');
await writeFile(runnerFile,runner.replace(registryFile,newRegistryFile).replace(expectedRegistry,hash(registryBytes)));
await writeFile(path.join(probe,'WATER_EDGE_CHANGE.json'),JSON.stringify({schema:'WORLD_ENGINE_WATER_EDGE_CHANGE_V1',parentShaderSHA256:oldShader,shaderSHA256:newShader,moduleSHA256:hash(newModule),sourceRasterBytesChanged:false,geometryChanged:false,heightPolicyChanged:false,labelsChanged:true,labelParentSHA256:hash(labelBefore),labelSHA256:hash(labelAfter),labelScope:'REFERENCE_NUMERIC_NO_PIN_DEFAULT_SLOT_ONLY',scope:'SOFTEN_KNOWN_WATER_RESPONSE_WITHIN_EXISTING_ADMITTED_FOOTPRINT',visualApproved:false}),{flag:'wx',mode:0o600});
