import fs from 'node:fs/promises';import path from 'node:path';import{fileURLToPath}from'node:url';import{createHash}from'node:crypto';
import{analyzePresentationPrompt}from'../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import{validateRuntimeRequest,prepareRuntimeRequest}from'../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=path.dirname(fileURLToPath(import.meta.url)),hash=b=>createHash('sha256').update(b).digest('hex'),raw=await fs.readFile(path.join(p,'JAPAN_6S_INPUT.json')),input=JSON.parse(raw),cp=JSON.parse(await fs.readFile(path.join(p,'CHECKPOINT.json')));
let stage='FORMAL_COMPILE';
try{
 const result=await analyzePresentationPrompt(input);await fs.writeFile(path.join(p,'COMPILE_RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 if(result.status!=='PASS')throw Error('NEW_JAPAN_COMPILE_'+result.status+':'+JSON.stringify(result.issues));
 const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:result.totalFrames,sourceInputSHA256:result.inputSHA256,segments:result.renderRequests.map(({sceneId,startFrame,endFrame,scene,region,presentation})=>({sceneId,startFrame,endFrame,scene,region,presentation})),transitions:result.transitionPlan,inputTrace:{inputFile:'JAPAN_6S_INPUT.json',fileSHA256:hash(raw),compilerInputSHA256:result.inputSHA256,compilerVersion:result.compilerVersion}};
 stage='RUNTIME_REQUEST_VALIDATION';validateRuntimeRequest(request);
 await fs.writeFile(path.join(p,'RUNTIME_REQUEST.json'),JSON.stringify(request,null,2)+'\n',{flag:'wx'});
 stage='CAMERA_AND_FULL_SOURCE_PREPARATION';const prepared=await prepareRuntimeRequest({request,cacheRoot:'/workspace/japan6s-prepare-a1'});
 const camera=prepared.segments[0].presentationPlan,rows=camera.cpuFrameBounds;
 if(!rows.slice(150).every(r=>JSON.stringify(r)===JSON.stringify(rows[149])))throw Error('NEW_JAPAN_CAMERA_FINAL_HOLD_NOT_EQUAL');
 const receipt={status:'PASS_NEW_JAPAN_INPUT_AND_SOURCE_PREPARATION',inputFileSHA256:hash(raw),compilerInputSHA256:result.inputSHA256,runtimePackageSHA256:hash(await fs.readFile(path.join(p,'RUNTIME_REQUEST.json'))),totalFrames:180,schema:'WORLD_ENGINE_PRESENTATION_PROMPT_V2',runtimeValidated:true,issues:result.issues,sceneTiming:result.renderRequests[0].scene.timing,flowTiming:result.renderRequests[0].enginePlan.plans[0].plan.timing,cameraMode:camera.mode,cameraBounds:rows,cameraHold149_179:true,sourceQualification:prepared.sourceQualification,sourceQualificationSHA256:prepared.sourceQualificationSHA256,rendererChanges:0,oldPassReruns:0,GPUExecutions:0};
 await fs.writeFile(path.join(p,'INPUT_ADMISSION.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
 cp.status='PASS_NEW_INPUT_PENDING_ACTUAL_CPU';cp.firstIncomplete='ACTUAL_CPU_180_FRAME_CAPTURE';cp.lastError=null;cp.nextAction='Execute new180frame candidate once through unchanged capturePresentation in free GitHub Actions; no old suite or image build.';
 console.log(JSON.stringify({status:receipt.status,totalFrames:180,flowTiming:receipt.flowTiming,sourceId:prepared.segments[0].regionEvidence.sourceId,coverage:camera.coverageBounds,hold:true}));
}catch(error){cp.status='BLOCKED';cp.firstIncomplete=stage;cp.lastError=String(error.message);await fs.writeFile(path.join(p,'COMPILE_FAILURE.json'),JSON.stringify({status:'FAIL',stage,inputFile:'JAPAN_6S_INPUT.json',inputSHA256:hash(raw),originalMessage:String(error.message),stack:error.stack,GPUExecutions:0},null,2)+'\n',{flag:'wx'});throw error;
}finally{await fs.writeFile(path.join(p,'CHECKPOINT.json'),JSON.stringify(cp,null,2)+'\n');}
