// Actual 1080x1920 native review probes, without Camera animation or admission claims.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openVisualRuntime,savedCandidateInputs,engine,json,sha} from './visual_runtime.mjs';
const {root,candidates,sourceFixtureSha256}=await savedCandidateInputs();
const out=path.join(root,'evidence',process.argv[2]??'static-probes');await mkdir(out);
const report={schema:1,status:'STARTED',startedAtUtc:new Date().toISOString(),output:[1080,1920],
 sourceFixtureSha256,candidates:[],animationStarted:false,surveyAdmissionModified:false};
let session;
try{
 session=await openVisualRuntime();
 const original=await json(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'));
 for(const candidate of candidates){
  const row={candidate};
  try{
   await session.page.evaluate(c=>window.visualDetail.initialize({targetFraming:{bounds:c.bounds},mode:'STATIC_VISUAL_PROBE'}),candidate);
   const clean=await session.page.evaluate(bounds=>window.visualDetail.capture({bounds,eventEnabled:false,png:true}),candidate.bounds);
   const nativeBytes=Buffer.from(clean.png.split(',')[1],'base64');delete clean.png;
   const nativeName=candidate.id+'_NATIVE.png';await writeFile(path.join(out,nativeName),nativeBytes,{flag:'wx'});
   row.native={...clean,file:nativeName,sha256:sha(nativeBytes),bytes:nativeBytes.length};
   if(candidate.id==='D0'){
    assert.equal(clean.raw_rgba_sha256,original.frames[249].raw_rgba_sha256,'DETAIL_ADAPTER_V5_ARRIVAL_PIXELS_CHANGED');
    assert.equal(clean.png_sha256,original.frames[249].png_sha256,'DETAIL_ADAPTER_V5_ARRIVAL_PNG_CHANGED');
    row.exactV5Arrival=true;
   }
   try{
    const full=await session.page.evaluate(bounds=>window.visualDetail.capture({bounds,eventFrame:149,eventEnabled:true,protect:true,png:true}),candidate.bounds);
    const bytes=Buffer.from(full.png.split(',')[1],'base64');delete full.png;
    const name=candidate.id+'_EVENT.png';await writeFile(path.join(out,name),bytes,{flag:'wx'});
    row.event={...full,file:name,sha256:sha(bytes),bytes:bytes.length};
   }catch(error){row.eventFailure={message:error.message};}
  }catch(error){row.nativeFailure={message:error.message};}
  report.candidates.push(row);
  console.log(JSON.stringify({candidate:candidate.id,native:!!row.native,event:!!row.event,failure:row.nativeFailure??row.eventFailure??null}));
 }
 assert.equal(session.errors.length,0);report.status='COMPLETE_FOR_VISUAL_REVIEW';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{report.completedAtUtc=new Date().toISOString();await writeFile(path.join(out,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session?.close();}
