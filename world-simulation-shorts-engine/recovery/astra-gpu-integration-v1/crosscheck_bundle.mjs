/** CPU-only file fixture transport for a real Python bundle; never starts GL. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {loadUploadBundle,describeUploadBundle} from './gpu_upload.mjs';
const [directory,expected]=process.argv.slice(2);
assert.ok(directory&&path.isAbsolute(directory));assert.match(expected,/^[0-9a-f]{64}$/);
const origin='https://astra-fixture.invalid';
const fetchImpl=async address=>{
 const url=new URL(address);assert.equal(url.origin,origin);
 assert.match(url.pathname,/^\/bundle\/[A-Za-z0-9_.-]+$/);
 const file=path.join(directory,path.basename(url.pathname));
 const bytes=await readFile(file);return new Response(bytes,{status:200});
};
const bundle=await loadUploadBundle({manifestURL:origin+'/bundle/UPLOAD_BUNDLE.json',
 expectedManifestSha256:expected,origin,fetchImpl});
const info=describeUploadBundle(bundle);
assert.equal(info.gpuUploadExecuted,false);assert.equal(info.gpuRenderingVerified,false);
console.log(JSON.stringify({schema:'ASTRA_PYTHON_JS_CONTRACT_CROSSCHECK_V1',status:'PASS',
 roles:Object.keys(info.sources).sort(),cpuOnly:true,gpuExecuted:false,networkExecuted:false,
 transport:'EXPLICIT_CPU_FILE_FIXTURE_NOT_HTTP_OR_GPU',manifestSha256:expected}));
