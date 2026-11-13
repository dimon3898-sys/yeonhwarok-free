/** New subject admission only; never renders or reruns previous PASS. */
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {analyzePresentationPrompt,extractNaturalLanguage} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {qualifyRegion} from '../../recovery/universal-presentation-v2/region_source.mjs';
const base=new URL('./',import.meta.url),raw=await fs.readFile(new URL('MONGOL_EMPIRE_INPUT_CANDIDATE.json',base));
const input=JSON.parse(raw),hash=x=>createHash('sha256').update(x).digest('hex');
const write=(name,value)=>fs.writeFile(new URL(name,base),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
const result=await analyzePresentationPrompt(input);
await write('evidence/FORMAL_ADMISSION_RESULT.json',result);
// Isolated read-only source diagnosis; this does not advance to capture or admit a blocked scene.
const region=await qualifyRegion({region:input.region,facts:input.data.scenes[0].facts});
await write('evidence/REGION_DIAGNOSTIC.json',region);
await write('evidence/TOPIC_INTENT_EXTRACTION.json',extractNaturalLanguage(input.prompt,{data:input.data}));
const record={inputSHA256:hash(raw),formalStatus:result.status,renderableScenes:result.renderRequests.length,
    issueCodes:[...new Set(result.issues.map(x=>x.code))],regionStatus:region.status,regionIssues:region.issues,
    cpuRenderStarted:false,paidGPUExecutions:0,previousPassReruns:0,
    stage:'NEW_SUBJECT_ADMISSION',engineCodeChanged:false};
await write('evidence/ADMISSION_SUMMARY.json',record);
console.log(JSON.stringify(record));
