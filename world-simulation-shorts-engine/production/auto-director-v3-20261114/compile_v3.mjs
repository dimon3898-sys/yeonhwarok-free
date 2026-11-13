import fs from 'node:fs';
import assert from 'node:assert/strict';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
const base=new URL('./',import.meta.url),read=n=>JSON.parse(fs.readFileSync(new URL(n,base))),write=(n,x)=>fs.writeFileSync(new URL(n,base),JSON.stringify(x,null,2)+'\n');
const input=read('SCENE_INPUT.json'),result=await analyzePresentationPrompt(input);
write('evidence/COMPILE_RESULT.json',result);console.log(JSON.stringify({status:result.status,issues:result.issues}));assert.equal(result.status,'PASS');
const request=result.renderRequests[0];write('FORMAL_SCENE.json',request.scene);write('DIRECTION_ANALYSIS.json',request.automaticDirection);
write('RUNTIME_REQUEST.json',{schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:result.totalFrames,sourceInputSHA256:result.inputSHA256,segments:result.renderRequests,transitions:result.transitionPlan});
