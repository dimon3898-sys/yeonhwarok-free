import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

// Focus only on this option restoration and its four-file integrity chain.
// Imports are pure option builders; no browser, renderer, process or GPU runs.
const HERE=path.dirname(fileURLToPath(import.meta.url));
const REPO=path.resolve(HERE,'../../../..');
const REC='world-simulation-shorts-engine/recovery/';
const HANDOFF=REC+'codex-to-gcube-handoff-v1/';
const PROFILE=HANDOFF+'backend/profile_contract.mjs';
const RUNTIME=HANDOFF+'RUNTIME_SOURCE_MANIFEST.json';
const BOOTSTRAP=REC+'studio-cold-start-v2/bootstrap.py';
const STARTUP=REC+'studio-cold-start-v2/STARTUP_MANIFEST.json';
const FLAG='--disable-vulkan-surface';
const ADDED_LINE="  '--disable-vulkan-surface',\n";
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const read=relative=>readFile(path.join(REPO,relative));
const before=await import(pathToFileURL(path.join(HERE,'profile_contract.before.mjs')).href);
const after=await import(pathToFileURL(path.join(REPO,PROFILE)).href);
const baseline=JSON.parse(await readFile(path.join(HERE,'../evidence/BASELINE_FILES.json'),'utf8'));
const actualInput={executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']};

test('runtime source delta is exactly the one restored success option line',async()=>{
 const old=await readFile(path.join(HERE,'profile_contract.before.mjs'),'utf8');
 const current=(await read(PROFILE)).toString();
 assert.equal(current.split(ADDED_LINE).length-1,1);
 assert.equal(current.replace(ADDED_LINE,''),old);
 assert.equal(sha(old),baseline[PROFILE].sha256);
});

for(const [name,input] of [
 ['actual UID1000 capture call',actualInput],
 ['duplicate caller option and retained feature options',{...actualInput,args:[...actualInput.args,FLAG,FLAG,'--enable-features=Example,Vulkan','--disable-features=Other','--mute-audio']}],
]){
 test(`restored option appears once and all other launch fields remain identical: ${name}`,()=>{
  const identity={uid:1000,rootTestOptIn:false};
  const old=before.buildVulkanLaunchOptions(structuredClone(input),identity);
  const current=after.buildVulkanLaunchOptions(structuredClone(input),identity);
  assert.equal(current.options.args.filter(arg=>arg===FLAG).length,1);
  assert.equal(current.evidence.selectedArgs.filter(arg=>arg===FLAG).length,1);
  assert.equal(current.options.chromiumSandbox,true);
  assert.equal(current.evidence.rootTestOnly,false);
  assert.equal(current.options.args.includes('--no-sandbox'),false);
  const normalized=structuredClone(current);
  normalized.options.args=normalized.options.args.filter(arg=>arg!==FLAG);
  normalized.evidence.selectedArgs=normalized.evidence.selectedArgs.filter(arg=>arg!==FLAG);
  assert.deepEqual(normalized,old);
 });
}

test('capture entry, WebGL2 call and generated-source pins remain byte-identical',async()=>{
 for(const file of ['capture_vulkan.generated.mjs','presentation_runtime_vulkan.generated.mjs','backend/GENERATED_SOURCE_MANIFEST.json']){
  const relative=HANDOFF+file,raw=await read(relative);
  assert.equal(sha(raw),baseline[relative].sha256,relative);
  assert.equal(raw.length,baseline[relative].bytes,relative);
 }
 const generated=JSON.parse(await read(HANDOFF+'backend/GENERATED_SOURCE_MANIFEST.json'));
 for(const variant of generated.variants.filter(row=>['capture_vulkan.generated.mjs','presentation_runtime_vulkan.generated.mjs'].includes(row.variant))){
  assert.equal(sha(await read(HANDOFF+variant.variant)),variant.variantSHA256);
 }
});

test('only the affected runtime row and startup hash links change; source policies remain intact',async()=>{
 const oldRuntime=JSON.parse(await readFile(path.join(HERE,'runtime_manifest.before.json')));
 const newRuntime=JSON.parse(await read(RUNTIME));
 const profile=await read(PROFILE);
 const expected=structuredClone(oldRuntime);
 const row=expected.files.find(row=>row.path===PROFILE);
 assert.ok(row);
 row.bytes=profile.length;row.sha256=sha(profile);
 assert.deepEqual(newRuntime,expected);
 assert.equal(newRuntime.files.length,355);
 assert.equal(newRuntime.files.filter(row=>row.path!==PROFILE).length,354);
 const oldBootstrap=await readFile(path.join(HERE,'bootstrap.before.py.fixture'),'utf8');
 const bootstrap=await read(BOOTSTRAP);
 const runtimeSHA=sha(await read(RUNTIME));
 assert.equal(bootstrap.toString(),oldBootstrap.replace(/^SOURCE_SHA = '[a-f0-9]{64}'$/m,"SOURCE_SHA = '"+runtimeSHA+"'"));
 const oldStartup=JSON.parse(await readFile(path.join(HERE,'startup_manifest.before.json')));
 const expectedStartup=structuredClone(oldStartup);
 expectedStartup.runtimeManifestSHA256=runtimeSHA;
 expectedStartup.files['bootstrap.py']={bytes:bootstrap.length,sha256:sha(bootstrap)};
 assert.deepEqual(JSON.parse(await read(STARTUP)),expectedStartup);
});
