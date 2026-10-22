/** Execute prepared examples through the opt-in compiler; never render. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {analyzePresentationPrompt} from '../presentation_prompt.mjs';

const here=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const reportName=process.argv[2];
if(!reportName || !/^EXAMPLE_MATRIX_[A-Z0-9_]+\.json$/.test(reportName))throw Error('UNIQUE_REPORT_NAME_REQUIRED');
const digest=raw=>crypto.createHash('sha256').update(raw).digest('hex');
const manifest=JSON.parse(fs.readFileSync(path.join(here,'examples/CASE_MANIFEST.json')));
const evidenceRegistry=JSON.parse(fs.readFileSync(path.join(here,'evidence/RETAINED_HISTORY_REGISTRY.json')));
const report={schema:'WORLD_ENGINE_PRESENTATION_EXAMPLE_EXECUTION_V2',
  scope:'ACTUAL_OPT_IN_NATURAL_LANGUAGE_AND_SOURCE_QUALIFICATION_ONLY_NO_RENDER',
  executedAt:new Date().toISOString(),command:`node tools/run_example_matrix.mjs ${reportName}`,
  sourceHashes:Object.fromEntries(['presentation_prompt.mjs','presentation_plan.mjs','region_source.mjs','REGION_SOURCE_CATALOG.json'].map(file=>[file,digest(fs.readFileSync(path.join(here,file)))])),
  externalLLMUsed:false,paidExecutionUsed:false,actualDrawExecuted:false,cases:[]};
for(const row of [...manifest.cases,...manifest.negativeCases]){
 const raw=fs.readFileSync(path.join(here,row.path));
 const inputSHA256=digest(raw);
 let result,exception=null;
 try{result=await analyzePresentationPrompt(raw.toString(),{evidenceRegistry});}
 catch(error){exception=String(error?.stack??error);result={status:'EXCEPTION'};}
 const test={id:row.id,inputPath:row.path,inputSHA256,manifestSHA256:row.sha256,
  inputIntegrityMatch:inputSHA256===row.sha256,expectedStatus:row.expectedStatus,actualStatus:result.status,
  expectationMatched:result.status===row.expectedStatus,issueCodes:(result.issues??[]).map(x=>x.code),
  result};
 if(exception)test.exception=exception;
 report.cases.push(test);
 process.stdout.write(JSON.stringify({id:row.id,expected:row.expectedStatus,actual:result.status,
  matched:test.expectationMatched,issues:test.issueCodes})+'\n');
}
report.summary={total:report.cases.length,expectationMatched:report.cases.filter(x=>x.expectationMatched).length,
 expectationMismatched:report.cases.filter(x=>!x.expectationMatched).length,
 inputIntegrityMismatch:report.cases.filter(x=>!x.inputIntegrityMatch).length,
 accepted:report.cases.filter(x=>x.actualStatus==='PASS').length,
 correctlyBlocked:report.cases.filter(x=>x.actualStatus!=='PASS'&&x.expectationMatched).length};
const reportPath=path.join(here,'reports',reportName);
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
process.stdout.write(JSON.stringify({report:reportPath,summary:report.summary})+'\n');
process.exitCode=report.summary.expectationMismatched||report.summary.inputIntegrityMismatch?1:0;
