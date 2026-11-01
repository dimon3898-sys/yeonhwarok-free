import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Execute the actual mobile entry point with a tiny DOM and synthetic responses.
// No browser, server, compiler, renderer, or prior PASS suite is started.
const source=readFileSync(new URL('../codex-to-gcube-handoff-v1/mobile/app.js',import.meta.url),'utf8');
const code='UP2_COMPLETE_TIMELINE_DATA_REQUIRED';
const diagnostic={schema:'WORLD_ENGINE_UP2_DIAGNOSTIC_V1',sceneIdEncoding:'ZERO_BASED_INPUT_SCENE_INDEX',limit:16};
const payload=(fields={issues:[{code:'REGION_SOURCE_NOT_ADMITTED',field:'$.presentation.sceneOverrides[0].sourceRegionId'}],blockedSceneIds:['scene[0]','scene[1]']})=>({error:{code,fields,diagnostic},renderAllowed:false});

async function harness(){
 const elements=new Map(),calls=[],redirects=[];
 class Element{
  constructor(tag='div'){this.tagName=tag;this.children=[];this.childNodes=this.children;this.parentNode=null;this.hidden=false;this.disabled=false;this.checked=false;this.value='';this.listeners={};this.nodeType=1;this._text='';}
  set id(value){this._id=value;elements.set(value,this);} get id(){return this._id;}
  set textContent(value){this._text=String(value);this.children=[];this.childNodes=this.children;}
  get textContent(){return this._text+this.children.map(child=>child.textContent||'').join('');}
  set innerHTML(_){throw Error('UNSAFE_HTML_WRITE');}
  append(...children){for(const child of children){child.parentNode=this;this.children.push(child);}}
  replaceChildren(...children){this._text='';for(const child of [...this.children])child.remove?.();this.children=[];this.childNodes=this.children;this.append(...children);}
  remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(child=>child!==this);if(this.id)elements.delete(this.id);this.parentNode=null;}
  addEventListener(name,handler){this.listeners[name]=handler;}
 }
 for(const id of ['error','error-text','load-example','input-file','prompt','preflight','refresh','logout','start','consent','start-section','prepare-form','example-data','checks','budget','job-facts','job-section','result-section','downloads','video','storage']){const el=new Element();el.id=id;}
 elements.get('error').append(elements.get('error-text'));elements.get('error').hidden=true;
 const label=new Element('label');label.append(elements.get('consent'),{nodeType:3,textContent:'consent'});
 const headings=new Map([['header h1',new Element('h1')],['header h1 + p',new Element('p')]]);
 let response={status:200,ok:true,data:{authenticated:true,csrf:'synthetic-test-csrf'}};
 const context=vm.createContext({document:{title:'',getElementById:id=>elements.get(id)||null,createElement:tag=>new Element(tag),querySelector:selector=>headings.get(selector)},localStorage:{getItem:()=>null,setItem(){},removeItem(){}},location:{assign:value=>redirects.push(value)},fetch:async(url,options)=>{calls.push({url,options});return{status:response.status,ok:response.ok,json:async()=>response.data};},TextEncoder,crypto:{randomUUID:()=> 'synthetic-random-id'},setTimeout(){throw Error('UNEXPECTED_TIMER');},clearTimeout(){},console});
 await vm.runInContext(source,context);
 return{elements,calls,redirects,context,respond:(status,data)=>{response={status,ok:status>=200&&status<300,data};},run:expression=>vm.runInContext(expression,context),text:()=>elements.get('error').textContent};
}

test('HTTP 422 keeps its code and displays safe field details and input scene ordinals',async()=>{
 const h=await harness();h.respond(422,payload());
 await h.run("request('/api/preflight',{schema:'TEST'}).catch(showError)");
 assert.match(h.text(),/UP2_COMPLETE_TIMELINE_DATA_REQUIRED/);
 assert.match(h.text(),/REGION_SOURCE_NOT_ADMITTED/);
 assert.match(h.text(),/\$\.presentation\.sceneOverrides\[0\]\.sourceRegionId/);
 assert.match(h.text(),/입력 장면 1 \(scene\[0\]\)/);assert.match(h.text(),/입력 장면 2 \(scene\[1\]\)/);
 assert.match(h.text(),/각 목록 최대 16개/);
 assert.equal(h.calls.at(-1).options.credentials,'same-origin');
 assert.equal(h.calls.at(-1).options.headers['X-Studio-CSRF'],'synthetic-test-csrf');
 assert.equal(h.elements.get('start').disabled,true);
});

test('malformed diagnostic strings are redacted and no HTML or private fields are rendered',async()=>{
 const h=await harness();const data=payload({issues:[{code:'<img src=x onerror=SECRET>',field:'$.data.token',message:'SECRET'},{code:'A'.repeat(1000),field:'/private/OWNER_SECRET'}],blockedSceneIds:['OwnerToken=SECRET','scene[99]']});data.error.headers={Authorization:'SECRET'};
 h.respond(422,data);await h.run("request('/api/preflight',{}).catch(showError)");
 assert.match(h.text(),/UNLISTED_CODE/);assert.match(h.text(),/REDACTED_FIELD/);assert.match(h.text(),/REDACTED_SCENE_ID/);
 assert.doesNotMatch(h.text(),/SECRET|Authorization|<img|private|token/);
});

test('401 still redirects and never retains or displays diagnostic details',async()=>{
 const h=await harness();h.respond(422,payload());await h.run("request('/api/preflight',{}).catch(showError)");
 h.respond(401,payload());await h.run("request('/api/preflight',{}).catch(showError)");
 assert.deepEqual(h.redirects,['/login']);assert.match(h.text(),/AUTH_REQUIRED/);
 assert.equal(h.elements.has('error-details'),false);assert.doesNotMatch(h.text(),/REGION_SOURCE_NOT_ADMITTED/);
});

test('successful requests retain normal data and a new action clears stale details',async()=>{
 const h=await harness();h.respond(422,payload());await h.run("request('/api/preflight',{}).catch(showError)");
 const success={valid:true,ready:true,requiresGpu:true,durationSeconds:10,totalFrames:300};h.respond(200,success);
 const result=await h.run("request('/api/preflight',{})");assert.deepEqual(JSON.parse(JSON.stringify(result)),success);
 await h.run('busy(async()=>{})');assert.equal(h.elements.get('error').hidden,true);assert.equal(h.elements.has('error-details'),false);
 assert.equal(h.calls.filter(call=>call.url==='/api/start').length,0);
});

test('unrelated errors and unsupported metadata expose no UP2 details',async()=>{
 const h=await harness();h.respond(422,payload());await h.run("request('/api/preflight',{}).catch(showError)");
 const other=payload();other.error.code='UNRELATED_FAILURE';h.respond(400,other);await h.run("request('/api/preflight',{}).catch(showError)");
 assert.match(h.text(),/UNRELATED_FAILURE/);assert.equal(h.elements.has('error-details'),false);
 const unsupported=payload();unsupported.error.diagnostic={...diagnostic,schema:'UNTRUSTED_SCHEMA'};h.respond(422,unsupported);await h.run("request('/api/preflight',{}).catch(showError)");
 assert.equal(h.elements.has('error-details'),false);
});

test('diagnostic arrays stay capped and input edits remove old error context',async()=>{
 const h=await harness();h.respond(422,payload({issues:Array.from({length:30},()=>({code:'REQUIRED_FIELD',field:'$.data.scenes[0].facts'})),blockedSceneIds:Array.from({length:30},()=> 'scene[0]')}));
 await h.run("request('/api/preflight',{}).catch(showError)");
 assert.equal((h.text().match(/REQUIRED_FIELD/g)||[]).length,16);assert.equal((h.text().match(/입력 장면 1/g)||[]).length,16);
 h.elements.get('prompt').listeners.input();assert.equal(h.elements.has('error-details'),false);assert.equal(h.elements.get('error').hidden,true);
 assert.equal(h.calls.filter(call=>call.url==='/api/start').length,0);
});
