/** Exact production NVIDIA preparation facade; no browser, capture or encoder. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {prepareNvidiaRuntimeRequest,verifyNvidiaPreparedRuntimeRequest} from '../../codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
const [fixture,output]=process.argv.slice(2),privateWorkspaceRoot='/workspace/variant-preflight-private',publicExportRoot='/out';
assert.equal(process.getuid(),1000);
const raw=await fs.readFile(fixture),request=JSON.parse(raw);
assert.equal(request.sourceInputSHA256,'ead4c4f8beb8b541aa221366cdb249f20253eb70a2866f377a784cadfb9bc7c7');
assert.equal(request.durationSeconds,10);assert.equal(request.totalFrames,300);assert.equal(request.segments.length,2);
await fs.mkdir(privateWorkspaceRoot,{mode:0o700});
const started=performance.now();
const prepared=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateWorkspaceRoot,'sources'),privateWorkspaceRoot,publicExportRoot});
const checked=await verifyNvidiaPreparedRuntimeRequest({prepared,privateWorkspaceRoot,publicExportRoot});
assert.equal(checked.status,'PASS');assert.equal(checked.verifiedSegments,2);
assert.equal(prepared.totalFrames,300);assert.equal(prepared.segments.length,2);
const result={schema:'WORLD_ENGINE_VARIANT_PREFLIGHT_FACADE_V1',status:'PASS',uid:process.getuid(),
  entryPoints:['prepareNvidiaRuntimeRequest','verifyNvidiaPreparedRuntimeRequest'],
  requestFixtureSHA256:createHash('sha256').update(raw).digest('hex'),sourceInputSHA256:request.sourceInputSHA256,
  sourceQualificationSHA256:checked.sourceQualificationSHA256,preparedSegments:2,plannedFrames:300,
  elapsedSeconds:(performance.now()-started)/1000,gpuExecutions:0,browserLaunches:0,renderedFrames:0,
  encoderLaunches:0,imageBuilds:0,oldPASSReruns:0,actualGcubeMountVerified:false,fullStudioHttpPreflightVerified:false};
await fs.writeFile(output,JSON.stringify(result,null,2)+'\n');
console.log('VARIANT_PREFLIGHT_FACADE='+JSON.stringify(result));
