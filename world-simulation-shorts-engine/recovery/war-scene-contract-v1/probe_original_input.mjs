import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {compileScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(here,'evidence/original');
if(fs.existsSync(path.join(out,'RESULT.json')))throw Error('EXISTING_EXECUTION_EVIDENCE_DO_NOT_RERUN');
fs.mkdirSync(out,{recursive:true});
const raw=fs.readFileSync(path.join(here,'input/WORLD_ENGINE_WAR_SYNTHETIC_6S_DRAFT.json'));
const input=JSON.parse(raw),row=input.data.scenes[0];
const report={schema:'WORLD_ENGINE_WAR_ORIGINAL_ENGINE_PROBE_V1',startedAt:new Date().toISOString(),nodeVersion:process.version,inputSHA256:createHash('sha256').update(raw).digest('hex'),operation:'compileScenePlan',mapping:'Same explicit topic/facts/output mapping as existing presentation_prompt.mjs:328',gpuExecuted:false,staticAuditRerun:false};
try {
 const scene=compileScenePlan({topic:input.data.topic,facts:row.facts,output:{fps:input.data.fps,width:input.data.resolution.width,height:input.data.resolution.height}});
 report.status='PASS';report.compiledSceneSchema=scene.metadata.schema;
 fs.writeFileSync(path.join(out,'COMPILED_SCENE.json'),JSON.stringify(scene,null,2)+'\n');
 console.log(JSON.stringify({operation:report.operation,status:'PASS'}));
}catch(error){
 report.status='FAIL';report.error={name:error.name,code:error.code??error.message,message:error.message,stack:error.stack};
 console.error(error.stack);process.exitCode=1;
}
report.finishedAt=new Date().toISOString();
fs.writeFileSync(path.join(out,'RESULT.json'),JSON.stringify(report,null,2)+'\n');
