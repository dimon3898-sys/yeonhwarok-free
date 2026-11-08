/** Prepare bounded PNG cases from existing sealed submissions; no renderer. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const probe=process.argv[2], staging=process.argv[3];
const {sealSceneChunks}=await import(pathToFileURL(path.join(probe,'closure/world-simulation-shorts-engine/recovery/universal-presentation-v2/sealed_scene_chunks.mjs')));
const activations=JSON.parse(await readFile(path.join(staging,'DESTINATION_ACTIVATIONS.json')));
const cases=[];
for(let part=1;part<=2;part++){
 const submission=JSON.parse(await readFile(path.join(staging,'inputs',`ORIGIN_SUBMISSION_0${part}.json`)));
 const wire=submission.sourcePipeline.runtimeRequestWireJSON;
 if(typeof wire!=='string'||createHash('sha256').update(wire).digest('hex')!==submission.sourcePipeline.runtimeWireSHA256)throw Error('EXISTING_RUNTIME_WIRE_PIN');
 const plan=sealSceneChunks(JSON.parse(wire));
 const selected=activations.find(a=>a.originalSemanticSHA256===plan.originalSHA256);
 if(!selected)throw Error('EXISTING_ACTIVATION_MISSING');
 for(const [index,chunk] of plan.chunks.entries()){
  const activation=selected.activation, activationSHA256=selected.activationSHA256;
  if(typeof activationSHA256!=='string')throw Error('EXISTING_ACTIVATION_PIN_MISSING');
  const binding=activation.chunks.find(c=>c.chunkRequestSHA256===chunk.requestSHA256);
  if(!binding)throw Error('EXISTING_CHUNK_BINDING_MISSING');
  const envelope={schema:'WORLD_ENGINE_OFFICIAL_SCENE_CHUNK_CAPTURE_V1',plan,chunk,candidateActivation:activation,candidateActivationSHA256:activationSHA256};
  const name=`part${part}_scene${index+1}`, file=path.join(probe,name+'.json'),raw=JSON.stringify(envelope);
  await writeFile(file,raw,{flag:'wx',mode:0o600});
  cases.push({name,part,scene:index+1,globalOffset:(part-1)*300+chunk.globalRange[0],config:{packageFile:file,expectedSHA256:createHash('sha256').update(raw).digest('hex'),expectedOriginalSHA256:plan.originalSHA256,expectedSourceQualificationSHA256:binding.nativeSourceQualificationSHA256,outputRoot:path.join(probe,name+'_output'),depsRoot:process.env.CPU_DEPS_ROOT,probeFrames:[0,75,149]}});
 }
}
if(cases.length!==4)throw Error('EXACT_FOUR_SCENES_REQUIRED');
await writeFile(path.join(probe,'FRAME_CASES.json'),JSON.stringify(cases),{flag:'wx',mode:0o600});
