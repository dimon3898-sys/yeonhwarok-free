import assert from 'node:assert/strict';import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';import {pathToFileURL} from 'node:url';
const {serveNativeCandidateSession}=await import(pathToFileURL(path.resolve(process.argv[2],'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/candidate_native_page.mjs')));
let closed=0;const calls=[];
const service=await serveNativeCandidateSession({close(){closed++},async response(request){calls.push(request);return{status:request.url==='/known'?200:400,headers:{'content-type':'application/json'},body:Buffer.from('{"ok":true}')}}});
const checks=[];
try{
 assert.equal(new URL(service.origin).hostname,'127.0.0.1');checks.push('LOOPBACK_ONLY_BIND');
 const response=await fetch(service.origin+'/known');assert.equal(response.status,200);checks.push('EXISTING_SESSION_RESPONSE_FORWARDED');
 await fetch(service.origin+'/candidate-window',{method:'POST',headers:{'content-type':'application/json','x-world-engine-capability':'test-capability'},body:'{"sceneKey":"test","windowId":"a"}'});
 assert.equal(calls[1].headers['x-world-engine-capability'],'test-capability');assert.equal(calls[1].body.toString(),'{"sceneKey":"test","windowId":"a"}');checks.push('WINDOW_HEADERS_AND_BODY_FORWARDED');
 const count=calls.length;assert.equal((await fetch(service.origin+'/candidate-window',{method:'POST',body:'x'.repeat(2049)})).status,400);assert.equal(calls.length,count);checks.push('OVERSIZED_BODY_REJECTED_BEFORE_SESSION');
 assert.equal(service.trace.length,2);assert.ok(service.trace.every(x=>Object.keys(x).sort().join(',')==='bytes,path,sha256,status'));checks.push('TRACE_HAS_NO_CAPABILITY_HEADERS_OR_BODY');
}finally{await service.close();await service.close();}
assert.equal(closed,1);checks.push('IDEMPOTENT_CLOSE_REVOKES_SESSION');
await assert.rejects(fetch(service.origin+'/known'));checks.push('CLOSED_ORIGIN_UNREACHABLE');
const result={schema:'WORLD_ENGINE_NATIVE_HTTP_BRIDGE_TEST_V1',status:'PASS',newChecks:checks.length,checks,rendererExecuted:false,gpuExecuted:false};await writeFile(path.resolve(process.argv[3],'NATIVE_HTTP_BRIDGE_RESULT.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
