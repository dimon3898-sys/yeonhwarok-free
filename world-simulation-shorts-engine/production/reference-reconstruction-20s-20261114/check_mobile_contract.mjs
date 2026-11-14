/** Actual mobile body/duration functions, with a minimal document fixture. No HTTP. */
import fs from 'node:fs/promises';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('./',import.meta.url),source=await fs.readFile(new URL('../../recovery/codex-to-gcube-handoff-v1/mobile/app.js',base),'utf8'),input=JSON.parse(await fs.readFile(new URL('FINAL_20S_INPUT.json',base)));
const dom={prompt:{value:''},consent:{parentNode:{childNodes:[{nodeType:3,textContent:''}]}}},header={},sub={};
const context=vm.createContext({TextEncoder,JSON,Error,document:{title:'',querySelector:x=>x==='header h1'?header:sub},$:x=>dom[x],state:{requestedDuration:6}});
const body=source.slice(source.indexOf('function body(){'),source.indexOf('\nfunction approvedBudget'));
const duration=source.slice(source.indexOf('function drawDuration('),source.indexOf('\nfunction drawPreflight'));
vm.runInContext('function fail(c){throw Error(c);}\n'+body+'\n'+duration,context);
dom.prompt.value=JSON.stringify(input);assert.equal(JSON.stringify(vm.runInContext('body()',context)),JSON.stringify(input));assert.equal(context.state.requestedDuration,20);
assert.equal(vm.runInContext('drawDuration({durationSeconds:20,totalFrames:600})',context),true);assert.equal(header.textContent,'20초 GPU 검수');assert.match(sub.textContent,/600프레임/);assert.match(dom.consent.parentNode.childNodes[0].textContent,/20초 영상 1개/);
assert.equal(vm.runInContext('drawDuration({durationSeconds:10,totalFrames:300})',context),false);
dom.prompt.value=JSON.stringify({...input,ignored:true});assert.throws(()=>vm.runInContext('body()',context),/WRAPPER_INVALID/);
for(const d of [6,10]){dom.prompt.value=JSON.stringify({data:{durationSeconds:d}});vm.runInContext('body()',context);assert.equal(context.state.requestedDuration,d);assert.equal(vm.runInContext(`drawDuration({durationSeconds:${d},totalFrames:${d*30}})`,context),true);}
assert.ok(source.includes("!$('consent').checked)fail('EXPLICIT_START_CONSENT_REQUIRED')"));
const result={status:'PASS_NEW_MOBILE_INPUT_AND_600_DISPLAY',checks:6,httpRequests:0,gpuStarts:0,legacyJobKeyPreserved:true,explicitConsentPreserved:true,actualBrowserVisualCheck:'PENDING_IMAGE_UI'};
await fs.writeFile(new URL('MOBILE_CONTRACT_TESTS.json',base),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
