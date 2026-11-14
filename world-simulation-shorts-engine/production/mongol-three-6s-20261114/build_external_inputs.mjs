import fs from 'node:fs/promises';import path from 'node:path';
const repo=process.cwd(),e=repo+'/world-simulation-shorts-engine',u=e+'/recovery/universal-presentation-v2';
const {canonicalJSON}=await import(u+'/../universal-data-pipeline-v1/prompt_pipeline.mjs');
const {dataHash}=await import(u+'/external_history_data.mjs');
const read=async p=>JSON.parse(await fs.readFile(p));
const sourceInput=await read(e+'/production/continuous-territory-20261114/SCENE_INPUT.json'),sourceRuntime=await read(e+'/production/continuous-territory-20261114/RUNTIME_REQUEST.json');
const evidenceRegistry=(await read(u+'/../universal-data-pipeline-v1/evidence/REVIEWED_HISTORICAL.json')).records;
const bundle={schema:'WORLD_ENGINE_REVIEWED_HISTORY_DATASET_V1',id:'CLIOPATRIA_MONGOL_FIRST_PAIR',version:'1.0.0',sourceInput,sourceRuntime,evidenceRegistry};
const raw=JSON.stringify(bundle)+'\n',sha=dataHash(raw),row={id:bundle.id,version:bundle.version,sha256:sha,bytes:Buffer.byteLength(raw),reviewStatus:'SOURCE_BOUND_DISPLAY_INTERPOLATION_ONLY',sourceInputSHA256:dataHash(sourceInput),sourceRuntimeSHA256:dataHash(sourceRuntime),evidenceRegistrySHA256:dataHash(evidenceRegistry)};
const catalog={schema:'WORLD_ENGINE_REVIEWED_DATA_CATALOG_V1',version:1,records:[row]},catalogRaw=JSON.stringify(catalog,null,2)+'\n';
const out=e+'/production/mongol-three-6s-20261114',root=process.argv[2];
if(!root||!path.isAbsolute(root))throw Error('EXPLICIT_PRIVATE_EXTERNAL_DATA_DIRECTORY_REQUIRED');
for(const dir of [out+'/data',root]){await fs.mkdir(dir,{recursive:true,mode:0o755});await fs.writeFile(dir+'/'+sha+'.json',raw,{mode:0o644});await fs.writeFile(dir+'/catalog.json',catalogRaw,{mode:0o644});}
const original=await read(e+'/production/reference-reconstruction-20s-20261114/FINAL_20S_INPUT.json');
for(let i=0;i<3;i++){
 const prompt={schema:'WORLD_ENGINE_AUTHORED_HISTORY_INPUT_V2',simulationType:'HISTORICAL',source:{id:row.id,version:row.version,sha256:sha},output:{...original.prompt.output,totalFrames:180,durationSeconds:6},timeline:{totalFrames:600,timing:original.prompt.timing,window:{startFrame:i*180,endFrame:(i+1)*180}},presentation:original.prompt.presentation};
 await fs.writeFile(out+'/MONGOL_6S_PART_0'+(i+1)+'.json',JSON.stringify({schema:original.schema,prompt,sceneId:original.sceneId},null,2)+'\n');
}
await fs.writeFile(root+'/operator-config.json',JSON.stringify({dataRoot:root,catalogSHA256:dataHash(catalogRaw),packageSHA256:sha}));
console.log(JSON.stringify({root,catalogSHA256:dataHash(catalogRaw),packageSHA256:sha,packageBytes:row.bytes,inputs:3}));
