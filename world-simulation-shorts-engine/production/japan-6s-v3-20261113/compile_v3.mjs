import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=new URL('./',import.meta.url),hash=b=>createHash('sha256').update(b).digest('hex');
const write=(n,v)=>fs.writeFile(new URL(n,p),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const raw=await fs.readFile(new URL('JAPAN_V3_SCENE_INPUT.json',p));
try{
 const result=await analyzePresentationPrompt(JSON.parse(raw));await write('COMPILE_RESULT.json',result);
 assert.equal(result.status,'PASS',JSON.stringify(result.issues));
 const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:result.totalFrames,sourceInputSHA256:result.inputSHA256,segments:result.renderRequests.map(({sceneId,startFrame,endFrame,scene,region,presentation})=>({sceneId,startFrame,endFrame,scene,region,presentation})),transitions:result.transitionPlan,inputTrace:{inputFile:'JAPAN_V3_SCENE_INPUT.json',fileSHA256:hash(raw),compilerInputSHA256:result.inputSHA256,compilerVersion:result.compilerVersion}};
 validateRuntimeRequest(request);assert.equal(request.totalFrames,180);assert.equal(request.segments.length,1);
 await write('RUNTIME_REQUEST.json',request);await write('COMPILED_SCENES.json',request.segments.map(x=>x.scene));
 console.log(JSON.stringify({status:'V3_FORMAL_COMPILE_PASS',inputSHA256:hash(raw),runtimeSHA256:hash(await fs.readFile(new URL('RUNTIME_REQUEST.json',p)))}));
}catch(e){await write('COMPILE_FAILURE.json',{stage:'V3_FORMAL_COMPILE',message:e.message,stack:e.stack,inputSHA256:hash(raw)});throw e;}
