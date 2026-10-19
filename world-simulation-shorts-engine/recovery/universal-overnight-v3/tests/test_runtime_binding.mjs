import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {extendOvernightServerPlan,existingVisualSourceRecords} from '../runtime_binding.mjs';
const hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
function fixture(){
 const sourceCatalog={trustedSources:[]},completion={profile:'VISUAL_UNIFIED_COMPLETION_V2'},request={schema:'WORLD_ENGINE_OVERNIGHT_CAPTURE_REQUEST_V3',
  profile:'OVERNIGHT_SAFE_V3',sourceManifestSHA256:'a'.repeat(64),parentCaptureRequest:{completionV2:completion},
  overnightV3:{schema:'WORLD_ENGINE_OVERNIGHT_SAFE_V3',profile:'OVERNIGHT_SAFE_V3',operation:'PREVIEW_5S',
   visualExtensions:{schema:'WORLD_ENGINE_OVERNIGHT_VISUAL_V1',scalarTerritory:null,nationalUnits:null}},
  preview:{range:{startFrame:1400,endFrame:1550,frameCount:150},bindings:{sourceCatalogSHA256:hash(sourceCatalog)}}},
  inherited={completionIntegrity:{profileSHA256:hash(completion)},sourceSignature:'b'.repeat(64),sourceBindings:[],
   serverConfig:{bindings:[{url:'/universal/long_adapter.mjs',path:'/exact/old.mjs',sha256:'c'.repeat(64),bytes:10}],
    runtimeConfig:{old:true,completionIntegrity:{profileSHA256:hash(completion),catalogSHA256:'e'.repeat(64)}}}},
  records=['browser_adapter.mjs','visual_extensions.mjs'].map(name=>({name,file:'/exact/'+name,sha256:'d'.repeat(64),bytes:20}));
 return{inherited,options:{request,records,manifestSHA256:'a'.repeat(64),sourceCatalog}};
}
test('new aliases preserve actual parent and metadata without parent mutation',()=>{
 const {inherited,options}=fixture(),before=structuredClone(inherited),value=extendOvernightServerPlan(inherited,options);
 assert.deepEqual(inherited,before);assert.equal(value.serverConfig.runtimeConfig.old,true);
 const aliases=new Map(value.serverConfig.bindings.map(row=>[row.url,row]));
 assert.equal(aliases.get('/overnight-v3/parent_adapter.mjs').path,'/exact/old.mjs');
 assert.equal(aliases.get('/universal/long_adapter.mjs').path,'/exact/browser_adapter.mjs');
 assert.deepEqual(value.serverConfig.runtimeConfig.overnightPreview.range,options.request.preview.range);
 assert.equal(value.full80sRenderAllowed,false);assert.equal(value.overnightIntegrity.actualGPUOutputVerified,false);
 assert.equal(value.completionIntegrity.profileSHA256,inherited.completionIntegrity.profileSHA256);
});
test('package-sealed additive catalog reaches both original subevent and optional visual consumers',()=>{
 const {inherited,options}=fixture(),row={sourceId:'test-only-contract',role:'FLOW_PLAN',payload:{}};
 options.sourceCatalog.trustedSources.push(row);options.request.preview.bindings.sourceCatalogSHA256=hash(options.sourceCatalog);
 const value=extendOvernightServerPlan(inherited,options),config=value.serverConfig.runtimeConfig;
 assert.deepEqual(config.completionSourceCatalog,options.sourceCatalog);
 assert.deepEqual(config.overnightSourceCatalog,options.sourceCatalog);
 assert.equal(config.completionIntegrity.catalogSHA256,hash(options.sourceCatalog));
 assert.deepEqual(value.completionIntegrity,config.completionIntegrity);
 assert.equal(inherited.serverConfig.runtimeConfig.completionIntegrity.catalogSHA256,'e'.repeat(64));
 options.request.preview.bindings.sourceCatalogSHA256='f'.repeat(64);
 assert.throws(()=>extendOvernightServerPlan(inherited,options),/PACKAGE_SOURCE_CATALOG_BINDING/);
});
test('wrong operation, range, manifest, duplicate source and missing source are rejected',()=>{
 for(const mutate of [x=>x.options.request.overnightV3.operation='FULL_VIDEO',x=>x.options.request.preview.range.frameCount=2400,
  x=>x.options.request.sourceManifestSHA256='e'.repeat(64),x=>x.options.records.push(x.options.records[0]),
  x=>x.options.records.pop(),x=>x.inherited.completionIntegrity.profileSHA256='f'.repeat(64)]){
  const x=fixture();mutate(x);assert.throws(()=>extendOvernightServerPlan(x.inherited,x.options));
 }
});
test('existing alias conflicts reject rather than overwrite source',()=>{
 const x=fixture();x.options.existingRecords=[{url:'/universal/forbidden.mjs',file:'/x',sha256:'a'.repeat(64),bytes:1}];
 assert.throws(()=>extendOvernightServerPlan(x.inherited,x.options),/EXISTING_OWNER_ALIAS/);
 const y=fixture();y.inherited.serverConfig.bindings.push({url:'/ref2/gain_style_core.mjs',sha256:'a'.repeat(64)});
 y.options.existingRecords=[{url:'/ref2/gain_style_core.mjs',file:'/x',sha256:'b'.repeat(64),bytes:1}];
 assert.throws(()=>extendOvernightServerPlan(y.inherited,y.options),/SOURCE_CONFLICT/);
});
test('17 original transitive sources have actual bytes and exact SHA, no rewrite',async()=>{
 const records=await existingVisualSourceRecords();assert.equal(records.length,17);assert.equal(new Set(records.map(row=>row.url)).size,17);
 for(const row of records){const bytes=await readFile(row.file);assert.equal(row.bytes,bytes.length);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),row.sha256);}
});
test('browser entry is before capture and exposes no NVIDIA success or arbitrary draw outside range',async()=>{
 const source=await readFile(new URL('../browser_adapter.mjs',import.meta.url),'utf8');
 for(const value of ['pipeline.drawFrame=async frame','OVERNIGHT_PREVIEW_FRAME_OUTSIDE_APPROVED_RANGE',
  'compileVisualExtensions','readFrameContext','actualGPUOutputVerified:false','parentGeographicFrontPresent'])assert.ok(source.includes(value));
 assert.doesNotMatch(source,/createShader|shaderSource|requestAnimationFrame|hardwareVerified:true/);
});
