// Exactly one complete disabled-extension/Event-OFF comparison against saved V5 Final.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {openVisualRuntime,engine,repo,json} from './visual_runtime.mjs';
const out=path.join(engine,'recovery/event-v1-v3-visual-detail/evidence/off250');await mkdir(out);
const {stdout:commit}=await promisify(execFile)('git',['rev-parse','HEAD'],{cwd:repo});
const baseline=await json(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'));
const report={schema:1,status:'STARTED',sourceCommit:commit.trim(),detailExtensionEnabled:false,eventEnabled:false,
 baseline:'29b8ee294360812b55ef577b62411de58159003b',frames:[],fullRegressionRuns:1,startedAtUtc:new Date().toISOString()};
let session;
try{
 session=await openVisualRuntime();
 await session.page.evaluate(()=>window.visualDetail.initialize({detailEnabled:false}));
 for(let frame=0;frame<250;frame++){
  const row=await session.page.evaluate(frame=>window.visualDetail.capture({disabledFrame:frame,png:true,eventEnabled:false}),frame);
  delete row.png;
  assert.equal(row.raw_rgba_sha256,baseline.frames[frame].raw_rgba_sha256,'V5_RAW_FRAME_'+frame);
  assert.equal(row.png_sha256,baseline.frames[frame].png_sha256,'V5_PNG_FRAME_'+frame);
  assert.equal(row.diagnostic.event.enabled,false);assert.equal(row.diagnostic.event.controls,null);
  assert.equal(row.diagnostic.event.line,null);assert.equal(row.diagnostic.event.metric,null);assert.equal(row.diagnostic.gpu.glError,0);
  report.frames.push({frame,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:row.png_sha256,bitExact:true,eventEvaluated:false});
  if(frame%15===0||frame===249)console.log(JSON.stringify({phase:'OFF250',frame,total:250}));
 }
 assert.equal(session.errors.length,0);report.status='BIT_EXACT';report.matchingFrames=250;
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{report.completedAtUtc=new Date().toISOString();await writeFile(path.join(out,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session?.close();}
