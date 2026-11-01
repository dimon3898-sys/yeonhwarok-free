import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,readFile,writeFile,mkdir,copyFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

// Exercise the real unchanged source verifier only. No capture import, browser,
// compiler, process launch, GPU, network, or previous PASS suite is invoked.
const HERE=path.dirname(fileURLToPath(import.meta.url));
const REPO=path.resolve(HERE,'../../../..');
const REC='world-simulation-shorts-engine/recovery/';
const HANDOFF=REC+'codex-to-gcube-handoff-v1/';
const MANIFEST=HANDOFF+'backend/GENERATED_SOURCE_MANIFEST.json';
const RUNTIME=HANDOFF+'RUNTIME_SOURCE_MANIFEST.json';
const CAPTURE=HANDOFF+'capture_vulkan.generated.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const json=async file=>JSON.parse(await readFile(file,'utf8'));
const canonical=value=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':value&&typeof value==='object'?'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}':JSON.stringify(value);
const baseline=await json(path.join(HERE,'generated_manifest_before.json.fixture'));
const corrected=await json(path.join(REPO,MANIFEST));
const approvedCaptureSHA='0161ac4177bb24b282aab28bb6f42b75d82841aedd81f8b574c8b8e90b33bffb';
const oldCaptureSHA='39bdff1d9190ab8102c812209e64001fd6b633c0ac424d9427f1ca409aa9f592';
const runtime=await json(path.join(REPO,RUNTIME));
const paths=[...corrected.variants.flatMap(row=>[row.original,HANDOFF+row.variant]),...['capture_nvidia.mjs','profile_contract.mjs','private_workspace.mjs'].map(name=>HANDOFF+'backend/'+name)];

async function fixture(t,metadata=corrected){
 const directory=await mkdtemp(path.join(tmpdir(),'world-engine-capture-integrity-'));
 t.after(()=>rm(directory,{recursive:true,force:true}));
 for(const relative of paths){
  const target=path.join(directory,relative);
  await mkdir(path.dirname(target),{recursive:true});
  await copyFile(path.join(REPO,relative),target);
 }
 await writeFile(path.join(directory,MANIFEST),JSON.stringify(metadata));
 const {verifyGeneratedSources}=await import(pathToFileURL(path.join(directory,HANDOFF+'backend/capture_nvidia.mjs')).href);
 return{directory,verifyGeneratedSources};
}
const exactSourceError=error=>error instanceof Error&&error.message==='HANDOFF_CAPTURE_SOURCE_CHANGED';

test('previous nested pin rejects the approved diagnostic capture bytes with the reported code',async t=>{
 assert.equal(baseline.variants[0].variantSHA256,oldCaptureSHA);
 assert.equal(sha(await readFile(path.join(REPO,CAPTURE))),approvedCaptureSHA);
 const f=await fixture(t,baseline);
 await assert.rejects(f.verifyGeneratedSources,exactSourceError);
});

test('corrected nested pin accepts the exact existing three original/variant pairs',async t=>{
 const f=await fixture(t);
 assert.deepEqual(await f.verifyGeneratedSources(),corrected.variants.map(row=>({variant:row.variant,sha256:row.variantSHA256})));
});

for(const [name,relative] of [
 ['changed capture adapter',CAPTURE],
 ['changed preserved original',corrected.variants[0].original],
 ['changed other variant',HANDOFF+corrected.variants[1].variant],
]){
 test(`integrity enforcement still rejects ${name}`,async t=>{
  const f=await fixture(t);
  const file=path.join(f.directory,relative);
  await writeFile(file,Buffer.concat([await readFile(file),Buffer.from('\n// focused integrity mutation\n')]));
  await assert.rejects(f.verifyGeneratedSources,exactSourceError);
 });
}

test('only the nested capture pin and its existing outer startup hash links change',async()=>{
 const expected=structuredClone(baseline);
 expected.variants[0].variantSHA256=approvedCaptureSHA;
 assert.deepEqual(corrected,expected);
 assert.equal(runtime.files.length,355);
 assert.equal(new Set(runtime.files.map(row=>row.path)).size,355);
 const unchangedRows=runtime.files.filter(row=>row.path!==MANIFEST);
 assert.equal(sha(canonical(unchangedRows)),'e6a176cf05916df1d50507cfd8bcb1d425d310228b4ba2bf6157c5f489b5df7c');
 // Limit byte comparisons to the affected verifier dependency set and pin row.
 for(const relative of [MANIFEST,...paths]){
  const row=runtime.files.find(item=>item.path===relative);
  assert.ok(row,relative);
  const raw=await readFile(path.join(REPO,relative));
  assert.equal(row.sha256,sha(raw),relative);
  assert.equal(row.bytes,raw.length,relative);
 }
 const runtimeSHA=sha(await readFile(path.join(REPO,RUNTIME)));
 const bootstrap=await readFile(path.join(REPO,REC+'studio-cold-start-v2/bootstrap.py'));
 const startup=await json(path.join(REPO,REC+'studio-cold-start-v2/STARTUP_MANIFEST.json'));
 assert.equal(bootstrap.toString().match(/^SOURCE_SHA = '([a-f0-9]{64})'$/m)?.[1],runtimeSHA);
 assert.equal(startup.runtimeManifestSHA256,runtimeSHA);
 assert.deepEqual(startup.files['bootstrap.py'],{bytes:bootstrap.length,sha256:sha(bootstrap)});
 assert.deepEqual(startup.files['worker.py'],{bytes:10317,sha256:'75edd4919e545b06f0bab139a3ad106f11a26f072896a8cf4f1983165b0157b0'});
 assert.equal(startup.baseImageDigest,'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da');
});
