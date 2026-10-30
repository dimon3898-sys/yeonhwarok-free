/** New 355-source label packaging connections only; no rendering or server. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire,syncBuiltinESMExports} from 'node:module';

const HERE=path.dirname(fileURLToPath(import.meta.url)),RECOVERY=path.dirname(HERE);
const REPO=path.resolve(RECOVERY,'../..'),HANDOFF=path.join(RECOVERY,'codex-to-gcube-handoff-v1');
const UP2=path.join(RECOVERY,'universal-presentation-v2'),EVIDENCE=path.join(HERE,'evidence');
const require=createRequire(import.meta.url),sha=data=>createHash('sha256').update(data).digest('hex');
const OLD_RUNTIME_PIN='631d69debd02ed24584a72499febc5f541d3adcfc411095906c444c03e90d0a6';
const NEW_RUNTIME_PIN='62461ee8f49265554d3858848ec106586937e62ae4fb3ce90c39a96909266d72';
const BASE='5e4ed42496c45333126c08166571598d9fcf0495';

// A mistaken attempt to launch a renderer, helper process or service fails.
for(const name of ['exec','execFile','spawn','fork','execSync','execFileSync','spawnSync'])
 require('node:child_process')[name]=()=>{throw Error('LABEL_PACKAGE_PROCESS_FORBIDDEN');};
for(const module of ['node:http','node:https'])for(const name of ['request','get','createServer'])
 require(module)[name]=()=>{throw Error('LABEL_PACKAGE_NETWORK_FORBIDDEN');};
require('node:net').Server.prototype.listen=()=>{throw Error('LABEL_PACKAGE_LISTEN_FORBIDDEN');};
syncBuiltinESMExports();
globalThis.fetch=async()=>{throw Error('LABEL_PACKAGE_NETWORK_FORBIDDEN');};

const metadata=JSON.parse(await fs.readFile(path.join(HANDOFF,'backend/GENERATED_SOURCE_MANIFEST.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(HANDOFF,'RUNTIME_SOURCE_MANIFEST.json'),'utf8'));
const sourceRows=new Map(manifest.files.map(row=>[row.path,row]));
const entry=await import(pathToFileURL(path.join(HANDOFF,'backend/capture_nvidia.mjs')).href);
const cases=[];
function check(name,run){cases.push({name,run});}
const relative=file=>path.relative(REPO,file).split(path.sep).join('/');

check('01_pinned_before_fix_validator_rejects_label_manifest',async()=>{
 const receipt=JSON.parse(await fs.readFile(path.join(EVIDENCE,'BASELINE_SOURCE_ADMISSION.json'),'utf8'));
 assert.equal(receipt.baseCommit,BASE);
 assert.match(receipt.captureSourceSHA256,/^[a-f0-9]{64}$/);
 assert.equal(sha(receipt.validatorSource),receipt.validatorSourceSHA256);
 assert.ok(receipt.validatorSource.includes(OLD_RUNTIME_PIN));
 assert.ok(!receipt.validatorSource.includes(NEW_RUNTIME_PIN));
 const validate=vm.runInNewContext('('+receipt.validatorSource.replace(/^export /,'')+')',{
  check:(condition,code)=>{if(!condition)throw Error(code);},
  hex:value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 },{timeout:100});
 assert.throws(()=>validate(metadata),/HANDOFF_EXACT_VARIANT_SET_REQUIRED/);
 return {baselineCommit:BASE,baselineCaptureSHA256:receipt.captureSourceSHA256,error:'HANDOFF_EXACT_VARIANT_SET_REQUIRED',scope:'NEW_LABEL_ORIGINAL_PIN_ADMISSION'};
});

check('02_fixed_entry_accepts_exact_manifest_and_rejects_old_runtime_pin',()=>{
 const rows=entry.validateVariantManifest(metadata);
 assert.equal(rows.length,3);
 const runtime=rows.find(row=>row.variant==='presentation_runtime_vulkan.generated.mjs');
 assert.equal(runtime.originalSHA256,NEW_RUNTIME_PIN);
 const stale=structuredClone(metadata);
 stale.variants.find(row=>row.variant===runtime.variant).originalSHA256=OLD_RUNTIME_PIN;
 assert.throws(()=>entry.validateVariantManifest(stale),/HANDOFF_EXACT_VARIANT_SET_REQUIRED/);
 const duplicate=structuredClone(metadata);duplicate.variants[2]=structuredClone(duplicate.variants[1]);
 assert.throws(()=>entry.validateVariantManifest(duplicate),/HANDOFF_EXACT_VARIANT_SET_REQUIRED/);
 return {variantsAccepted:3,oldPinRejected:true,duplicateRejected:true};
});

check('03_actual_generated_source_admission_for_new_label_snapshot',async()=>{
 const actual=await entry.verifyGeneratedSources();
 assert.deepEqual(actual,metadata.variants.map(row=>({variant:row.variant,sha256:row.variantSHA256})));
 return {function:'verifyGeneratedSources',actualPinnedFilesRead:6,variants:actual,renderExecuted:false,scope:'NEWLY_INVALIDATED_LABEL_SNAPSHOT_ADMISSION_ONLY'};
});

check('04_new_label_modules_load_from_runtime_closure_with_real_exports',async()=>{
 const files=[['presentation_labels.mjs','validateLabelSpec'],['presentation_label_layer.mjs','createPresentationLabelPass']];
 const actual=[];
 for(const [name,symbol]of files){
  const file=path.join(UP2,name),raw=await fs.readFile(file),row=sourceRows.get(relative(file));
  assert.ok(row,'new label module missing from candidate runtime closure');
  assert.equal(sha(raw),row.sha256);assert.equal(raw.length,row.bytes);
  const module=await import(pathToFileURL(file).href);
  assert.equal(typeof module[symbol],'function');
  actual.push({path:relative(file),sha256:sha(raw),bytes:raw.length,export:symbol});
 }
 return {actualNodeModuleLoads:2,modules:actual,canvasOrWebGLCreated:false};
});

check('05_capture_mounts_resolve_new_browser_label_edges_without_http',async()=>{
 const capture=await fs.readFile(path.join(HANDOFF,'capture_vulkan.generated.mjs'),'utf8');
 const mounts=[
  ['/recovery/universal-presentation-v2/',"path.join(ENGINE,'recovery/universal-presentation-v2')",UP2],
  ['/recovery/codex-to-gcube-handoff-v1/','HERE',HANDOFF],
 ];
 for(const [prefix,expression]of mounts)assert.ok(capture.includes("['"+prefix+"',"+expression+"]"),'actual capture mount changed');
 assert.ok(capture.includes("type=/\\.(mjs|js)$/.test(target)?'text/javascript'"),'capture module MIME contract changed');
 const runtimeURL='/recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs';
 assert.ok(capture.includes("import('"+runtimeURL+"')"));
 function resolveURL(url){
  const route=mounts.find(([prefix])=>url.startsWith(prefix));assert.ok(route,'new label URL is not served');
  const result=path.join(route[2],url.slice(route[0].length));
  assert.ok(result.startsWith(route[2]+path.sep));return result;
 }
 const edges=[
  [runtimeURL,'../universal-presentation-v2/presentation_label_layer.mjs'],
  ['/recovery/universal-presentation-v2/presentation_runtime.mjs','./presentation_label_layer.mjs'],
  ['/recovery/universal-presentation-v2/presentation_plan.mjs','./presentation_labels.mjs'],
  ['/recovery/universal-presentation-v2/presentation_label_layer.mjs','./presentation_labels.mjs'],
 ];
 const connected=[];
 for(const [from,specifier]of edges){
  const file=resolveURL(from),source=await fs.readFile(file,'utf8');
  assert.ok(source.includes("from '"+specifier+"';"),'actual import edge missing');
  const url=new URL(specifier,'http://unused.invalid'+from).pathname,target=resolveURL(url);
  const row=sourceRows.get(relative(target));assert.ok(row,'new browser target not in355 runtime closure');
  const stat=await fs.lstat(target);assert.ok(stat.isFile()&&!stat.isSymbolicLink());
  connected.push({from,specifier,resolvesTo:url,manifestPath:row.path});
 }
 return {edges:connected,actualCaptureMountsRead:true,serverStarts:0,httpRequests:0,scope:'NEW_LABEL_EDGES_ONLY_INHERITED_GRAPH_NOT_REQUALIFIED'};
});

const requested=process.argv.find(arg=>arg.startsWith('--cases='))?.slice(8);
const selected=requested?new Set(requested.split(',')):null,results=[];
for(const row of cases){
 if(selected&&!selected.has(row.name.slice(0,2)))continue;
 try{const evidence=await row.run();results.push({name:row.name,status:'PASS',evidence});console.log('LABEL_PACKAGE_RUNTIME_PASS='+row.name);}
 catch(error){results.push({name:row.name,status:'BLOCKED',error:String(error?.message??error).slice(0,1000)});console.log('LABEL_PACKAGE_RUNTIME_BLOCKED='+JSON.stringify(results.at(-1)));}
}
const report={schema:'WORLD_ENGINE_LABEL_PACKAGE_RUNTIME_LINK_TESTS_V1',baseCommit:BASE,status:results.every(row=>row.status==='PASS')?'PASS':'BLOCKED',passed:results.filter(row=>row.status==='PASS').length,failed:results.filter(row=>row.status!=='PASS').length,cases:results,existingPASSSuitesRerun:false,gpuRuns:0,imageBuilds:0,serverStarts:0,networkRequests:0};
console.log('LABEL_PACKAGE_RUNTIME_RESULT='+JSON.stringify(report));
if(report.failed)process.exitCode=1;
