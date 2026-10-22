/** Final recovery orchestration; legacy native renderer and safety layout remain immutable. */
import {readFile,writeFile,mkdir,readdir,lstat,realpath,rename} from 'node:fs/promises';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';

const execute=promisify(execFile);
export const HERE=path.dirname(fileURLToPath(import.meta.url));
const PREVIOUS=path.resolve(HERE,'../g2-renderer-recovery-v1'),OLD=path.resolve(HERE,'../universal-source-pipeline-v2'),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE);
const hash=b=>createHash('sha256').update(b).digest('hex');
const within=(p,r)=>p===r||p.startsWith(r+path.sep);
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const check=(ok,code)=>{if(!ok)throw Error(code);};
const aliases=new Map(['native_runtime.mjs','camera_numeric_contract.mjs','source_geometry_contract.mjs'].map(n=>['/'+n,path.join(OLD,n)]));
const layoutModule=path.join(HERE,'layout_extension.mjs'),legacyLayout=path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs');
const mandatory=[...aliases.values(),legacyLayout,path.join(PREVIOUS,'terrain_style.py'),...['capture_recovery.mjs','capture_source.mjs','source_contract.py','layout_extension.mjs','fixtures/LAYOUT_PROFILE.json'].map(n=>path.join(HERE,n))];

async function atomic(file,value){const next=file+'.new';await writeFile(next,JSON.stringify(value),{flag:'wx',mode:0o600});await rename(next,file);}
async function confined(file,root){const actual=await realpath(file);check(actual===path.resolve(file)&&within(actual,root),'RECOVERY_HTTP_PATH_REJECTED');return readFile(actual);}

export async function collectCurrentBindings(){
 return Promise.all(mandatory.map(async file=>{const raw=await readFile(file);return{path:path.relative(REPO,file),sha256:hash(raw),bytes:raw.length};}));
}

export function validateGates(gates,{fullCapture=true}={}){
 check(gates?.historicalG3==='BLOCKED'&&gates?.paidGpuExecuted===false,'RECOVERY_NONHISTORICAL_FREE_GATE_REQUIRED');
 check(gates?.baselineCommit==='3913ad8e90885c769cdccc91f396072d83e356f2','RECOVERY_BASELINE_GATE_REQUIRED');
 for(const name of fullCapture?['phaseA','phaseB','phaseC']:['phaseA','phaseB'])check(gates[name]?.status==='PASS','RECOVERY_'+name.toUpperCase()+'_GATE_REQUIRED');
 return true;
}

/** New opt-in policy is data-bound; the visible-role admission is not disabled. */
export function validateLayoutProfile(pipeline){
 const plan=pipeline?.runtimePayload?.nativePlan,policy=plan?.layout?.locationPlacement;
 const expected={schema:'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1',mode:'BOUNDED_GAP_SEARCH',maxGap:216,step:16};
 check(policy&&Object.keys(policy).length===4&&Object.entries(expected).every(([key,value])=>policy[key]===value),'RECOVERY_EXPLICIT_GENERIC_LAYOUT_PROFILE_REQUIRED');
 check(plan.scale?.information?.location!==false,'RECOVERY_LOCATION_ADMISSION_MUST_REMAIN_ENABLED');
 check(Number.isFinite(plan.layout?.measured?.location?.gap)&&plan.layout.measured.location.gap>=0&&plan.layout.measured.location.gap<=policy.maxGap,'RECOVERY_NATIVE_LOCATION_GAP_REQUIRED');
 return policy;
}

/** Verify actual source support, never camera-dependent hiding or invented pixels. */
export function validateStyle(pipeline){
 const style=pipeline?.sourceStyle,asset=style?.terrainAsset,inputs=pipeline?.runtimePayload;
 check(style?.schema==='WORLD_ENGINE_G2_MAP_STYLE_RECEIPT_V1'&&style.styleId==='NE1_SOURCE_NATIVE_COVERAGE','RECOVERY_SOURCE_STYLE_REQUIRED');
 check(asset&&typeof asset.path==='string'&&!path.isAbsolute(asset.path)&&!asset.path.split(/[\\/]/).includes('..')&&!asset.path.includes('\\'),'RECOVERY_TERRAIN_PATH_REQUIRED');
 const file=path.resolve(REPO,asset.path),assetRoots=[path.join(PREVIOUS,'assets/terrain'),path.join(HERE,'assets/terrain')];
 check(assetRoots.some(root=>within(file,root))&&asset.url==='/recovery-assets/'+path.basename(file)&&path.extname(file)==='.png','RECOVERY_EXPLICIT_ASSET_ROUTE_REQUIRED');
 check(hex(asset.sha256)&&Number.isSafeInteger(asset.bytes)&&asset.bytes>32&&asset.bytes<=128*1024**2,'RECOVERY_TERRAIN_HASH_AND_SIZE_REQUIRED');
 check(asset.CRS==='EPSG:4326'&&asset.classification==='BAKED HILLSHADE'&&hex(asset.sourceOriginalSHA256),'RECOVERY_TRUTHFUL_NE1_SOURCE_REQUIRED');
 const b=asset.bounds,d=asset.dimensions,p=asset.pixelSpacing;
 check(Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3]&&b[0]>=-180&&b[2]<=180&&b[1]>=-90&&b[3]<=90,'RECOVERY_GEOGRAPHIC_SOURCE_BOUNDS_REQUIRED');
 check(Array.isArray(d)&&d.length===2&&d.every(v=>Number.isSafeInteger(v)&&v>=2&&v<=8192)&&Array.isArray(p)&&p.length===2&&p.every(v=>Number.isFinite(v)&&v>0),'RECOVERY_NATIVE_SOURCE_DIMENSIONS_REQUIRED');
 check(Math.abs((b[2]-b[0])/d[0]-p[0])<1e-12&&Math.abs((b[3]-b[1])/d[1]-p[1])<1e-12,'RECOVERY_SOURCE_PIXEL_ALIGNMENT_REQUIRED');
 const terrain=inputs?.nativePlan?.assets?.terrain;
 check(terrain&&terrain.file===asset.path&&terrain.url===asset.url&&terrain.sha256===asset.sha256&&equal(terrain.bounds,b)&&equal(terrain.dimensions,d)&&equal(terrain.pixelSpacing,p)&&terrain.classification===asset.classification,'RECOVERY_PLAN_STYLE_BINDING_REQUIRED');
 check(Array.isArray(inputs.cameraSchedule)&&inputs.cameraSchedule.length===pipeline.totalFrames,'RECOVERY_CAMERA_PACKAGE_REQUIRED');
 let minimumGutter=Infinity;
 for(const row of inputs.cameraSchedule){
  const c=row.flatBounds;check(Array.isArray(c)&&c.length===4&&c.every(Number.isFinite)&&c[0]<c[2]&&c[1]<c[3],'RECOVERY_CAMERA_BOUNDS_REQUIRED');
  const gutter=Math.min((c[0]-b[0])/p[0],(c[1]-b[1])/p[1],(b[2]-c[2])/p[0],(b[3]-c[3])/p[1]);
  check(gutter>=1-1e-9,'RECOVERY_COMPLETE_VIEWPORT_SOURCE_SUPPORT_REQUIRED');minimumGutter=Math.min(minimumGutter,gutter);
  check(p[0]/(c[2]-c[0])*1080<=1+1e-9&&p[1]/(c[3]-c[1])*1920<=1+1e-9,'RECOVERY_NATIVE_PIXEL_BUDGET_REQUIRED');
 }
 return{asset,file,assetRoot:assetRoots.find(root=>within(file,root)),minimumSourceGutterPixels:minimumGutter,allActualCameraViewportsCovered:true};
}

async function prepare({planFile,expectedSHA256,fullCapture}){
 const raw=await readFile(planFile);check(hex(expectedSHA256)&&hash(raw)===expectedSHA256,'RECOVERY_CAPTURE_PLAN_HASH_MISMATCH');
 const info=await lstat(planFile);check(info.isFile()&&!info.isSymbolicLink()&&(info.mode&0o077)===0,'RECOVERY_CAPTURE_PRIVATE_PLAN_REQUIRED');
 const data=JSON.parse(raw),pipeline=data.sourcePipeline,receipt=data.executionReceipt,inputs=pipeline?.runtimePayload;
 check(data.schema==='WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2'&&pipeline?.ready===true&&pipeline.mode==='SYNTHETIC_TEST','RECOVERY_SYNTHETIC_SCOPE_REQUIRED');
 check(Number.isSafeInteger(pipeline.totalFrames)&&pipeline.totalFrames>=2&&pipeline.totalFrames<=240&&pipeline.startFrame===0&&Array.isArray(inputs?.frames)&&inputs.frames.length===pipeline.totalFrames,'RECOVERY_FRAME_PACKAGE_REQUIRED');
 const gateFile=path.join(HERE,'reports/GATES.json'),gateRaw=await readFile(gateFile);validateGates(JSON.parse(gateRaw),{fullCapture});
 if(fullCapture){
  check(pipeline.totalFrames===180&&receipt?.softwareOnly===true&&receipt.historicalRenderAllowed===false&&receipt.maxWallSeconds===900&&equal(receipt.frameRange,[0,180])&&Date.parse(receipt.expiresAt)>Date.now()+5000,'RECOVERY_BOUNDED_SOFTWARE_RECEIPT_REQUIRED');
 }
 const layoutProfile=validateLayoutProfile(pipeline);
 const source=validateStyle(pipeline),assetBytes=await confined(source.file,source.assetRoot);
 check(assetBytes.length===source.asset.bytes&&hash(assetBytes)===source.asset.sha256,'RECOVERY_TERRAIN_FILE_CHANGED');
 check(assetBytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))&&equal([assetBytes.readUInt32BE(16),assetBytes.readUInt32BE(20)],source.asset.dimensions),'RECOVERY_REAL_PNG_DIMENSIONS_REQUIRED');
 const current=await collectCurrentBindings(),approved=pipeline.recoveryBindings;
 check(Array.isArray(approved)&&approved.length>=current.length,'RECOVERY_APPROVED_ADAPTER_BINDINGS_REQUIRED');
 const seen=new Set();
 for(const row of approved){
  check(typeof row.path==='string'&&!path.isAbsolute(row.path)&&!row.path.split(/[\\/]/).includes('..')&&!seen.has(row.path)&&hex(row.sha256),'RECOVERY_APPROVED_BINDING_INVALID');seen.add(row.path);
  const file=path.resolve(REPO,row.path);check(within(file,REPO),'RECOVERY_BINDING_SCOPE_REJECTED');
  const bytes=await confined(file,REPO);check(hash(bytes)===row.sha256&&(row.bytes===undefined||row.bytes===bytes.length),'RECOVERY_APPROVED_BINDING_CHANGED');
 }
 for(const row of current)check(approved.some(v=>v.path===row.path&&v.sha256===row.sha256),'RECOVERY_ACTUAL_MODULE_NOT_APPROVED');
 for(const row of inputs.sourceBindings){const file=path.isAbsolute(row.path)?row.path:path.resolve(REPO,row.path);check(hash(await readFile(file))===row.sha256,'RECOVERY_NATIVE_INPUT_BINDING_CHANGED');}
 const assertBindings=async()=>{for(const row of approved){const bytes=await readFile(path.join(REPO,row.path));check(hash(bytes)===row.sha256,'RECOVERY_ADAPTER_CHANGED_DURING_DRAW');}check(hash(await readFile(source.file))===source.asset.sha256,'RECOVERY_TERRAIN_CHANGED_DURING_DRAW');};
 const receiptBinding=approved.find(row=>[HERE,PREVIOUS].some(root=>row.path===path.relative(REPO,path.join(root,'fixtures/RECOVERY_STYLE_RECEIPT.json'))));
 if(fullCapture)check(receiptBinding&&pipeline.sourceStyleReceiptSHA256===receiptBinding.sha256,'RECOVERY_STYLE_RECEIPT_BINDING_REQUIRED');
 const profileBinding=approved.find(row=>row.path===path.relative(REPO,path.join(HERE,'fixtures/LAYOUT_PROFILE.json')));
 check(profileBinding&&pipeline.layoutProfileSHA256===profileBinding.sha256,'RECOVERY_LAYOUT_PROFILE_BINDING_REQUIRED');
 return{data,pipeline,receipt,inputs,source,assetBytes,layoutProfile,adapterBindings:approved,gateSHA256:hash(gateRaw),assertBindings,
  terrainStyleReceiptSHA256:pipeline.sourceStyleReceiptSHA256??null};
}

async function openSession(prepared){
 const {inputs,source,assetBytes}=prepared,runtimeBytes=Buffer.from(JSON.stringify(inputs)),httpTrace=[];
 const server=createServer(async(req,res)=>{
  let target='INVALID';
  try{
   const u=new URL(req.url,'http://127.0.0.1');target=decodeURIComponent(u.pathname);
   check(['GET','HEAD'].includes(req.method)&&!u.search&&!target.includes('..')&&!target.includes('\\'),'RECOVERY_HTTP_TARGET_REJECTED');
   let body,type='application/octet-stream';
   if(target==='/'){body=Buffer.from('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}canvas{display:block}</style></head><body><canvas id="map" width="1080" height="1920"></canvas></body></html>');type='text/html';}
   else if(target==='/runtime.json'){body=runtimeBytes;type='application/json';}
   else if(aliases.has(target)){body=await confined(aliases.get(target),OLD);type='text/javascript';}
   else if(target===source.asset.url){body=assetBytes;type='image/png';}
   else if(target==='/modules/graphic_layout.mjs'){body=await confined(layoutModule,HERE);type='text/javascript';}
   else if(target==='/modules/graphic_layout_legacy.mjs'){body=await confined(legacyLayout,ENGINE);type='text/javascript';}
   else if(target==='/three.js'){body=await confined(path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js'),ENGINE);type='text/javascript';}
   else{
    const mounts=[['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]],mount=mounts.find(([prefix])=>target.startsWith(prefix));
    check(mount,'RECOVERY_HTTP_NOT_FOUND');body=await confined(path.join(mount[1],target.slice(mount[0].length)),mount[1]);
    type=/\.(mjs|js)$/.test(target)?'text/javascript':/\.png$/.test(target)?'image/png':/\.jpe?g$/.test(target)?'image/jpeg':/\.otf$/.test(target)?'font/otf':type;
   }
   httpTrace.push({path:target,status:200,bytes:body.length,sha256:hash(body),recoveryTerrain:target===source.asset.url});
   res.writeHead(200,{'Content-Type':type,'Content-Length':body.length,'Cache-Control':'no-store'});res.end(req.method==='HEAD'?undefined:body);
  }catch{httpTrace.push({path:target,status:404});res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port,require=createRequire('/workspace/exact-65422-capsule-20261020/package.json'),{chromium}=require('playwright');
 let browser;
 try{
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[],requestsFailed=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('requestfailed',request=>requestsFailed.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText}));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));await page.goto(origin);
  const evidence=await page.evaluate(async()=>{
   const inputs=await(await fetch('/runtime.json')).json(),{createUniversalSourceRuntime}=await import('/native_runtime.mjs');
   const {auditRuntimeLayout,validateLocationPlacementPolicy}=await import('/modules/graphic_layout.mjs');
   if(!validateLocationPlacementPolicy(inputs.nativePlan))throw Error('RECOVERY_ACTUAL_LAYOUT_EXTENSION_POLICY_REQUIRED');
   const runtime=await createUniversalSourceRuntime({canvas:document.getElementById('map'),...inputs});
   if(!runtime.evidence.native.layoutValidation.valid||!runtime.evidence.native.layoutValidation.locationRecovery)throw Error('RECOVERY_ACTUAL_LAYOUT_EXTENSION_NOT_USED');
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');let first;
   window.recoveryProof={runtime,async capture(frame,options={}){
    const diagnostic=runtime.drawFrame(frame,options);
    const measuredLayout=auditRuntimeLayout({plan:inputs.nativePlan,screen:point=>runtime.project(point)}),v=measuredLayout.validation;
    const location=measuredLayout.items.find(item=>item.role==='LOCATION_LABEL');
    diagnostic.layoutAudit={schema:measuredLayout.schema,valid:v.valid,failures:v.failures,collisions:v.collisions,boundaryCollisions:v.boundaryCollisions,safeArea:v.safeArea,anchor:v.anchor,geographicAnchor:v.geographicAnchor,locationRecovery:v.locationRecovery,location,measurement:measuredLayout.measurement,projection:measuredLayout.projection,nativeLocationRendered:false,visibleLabelRenderingClaimed:false,diagnosticOnly:true};
    if(!v.valid)throw Error('RECOVERY_DYNAMIC_LAYOUT_INVALID: '+JSON.stringify(diagnostic.layoutAudit));
    const pixels=runtime.readPixels(),png=runtime.png();if(frame===0&&!first)first=pixels.slice();
    let difference=null;
    if(frame===inputs.frames.length-1&&first){let changed=0,left=1080,right=-1,top=1920,bottom=-1;
     for(let i=0;i<pixels.length;i+=4)if(pixels[i]!==first[i]||pixels[i+1]!==first[i+1]||pixels[i+2]!==first[i+2]){const x=(i/4)%1080,y=1919-Math.floor(i/4/1080);changed++;left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
     difference={changedPixels:changed,box:changed?[left,top,right+1,bottom+1]:null};}
    return{diagnostic,rawSHA256:await digest(pixels),pngSHA256:await digest(Uint8Array.from(atob(png.split(',')[1]),x=>x.charCodeAt(0))),png,difference};
   }};return runtime.evidence;
  });
  check(evidence.backend.includes('SwiftShader'),'RECOVERY_SOFTWARE_BACKEND_REQUIRED');
  check(httpTrace.some(v=>v.path==='/modules/graphic_layout.mjs'&&v.status===200)&&httpTrace.some(v=>v.path==='/modules/graphic_layout_legacy.mjs'&&v.status===200),'RECOVERY_ACTUAL_LAYOUT_EXTENSION_HTTP_REQUIRED');
  check(httpTrace.some(v=>v.recoveryTerrain&&v.status===200&&v.sha256===source.asset.sha256),'RECOVERY_ACTUAL_TERRAIN_UPLOAD_REQUEST_REQUIRED');
  return{page,evidence,httpTrace,errors,requestsFailed,async close(){await page.evaluate(()=>window.recoveryProof?.runtime.dispose()).catch(()=>{});await browser.close();await new Promise(resolve=>server.close(resolve));}};
 }catch(error){error.recoveryHTTPTrace=httpTrace;if(browser)await browser.close().catch(()=>{});await new Promise(resolve=>server.close(resolve));throw error;}
}

async function outputDirectories(outputRoot,cacheRoot){
 outputRoot=path.resolve(outputRoot);check(within(outputRoot,HERE),'RECOVERY_FRESH_OUTPUT_NAMESPACE_REQUIRED');
 let ancestor=HERE;
 for(const part of path.relative(HERE,outputRoot).split(path.sep).filter(Boolean)){
  ancestor=path.join(ancestor,part);
  try{check(!(await lstat(ancestor)).isSymbolicLink(),'RECOVERY_OUTPUT_SYMLINK_REJECTED');}catch(error){if(error.code!=='ENOENT')throw error;}
 }
 await mkdir(path.dirname(outputRoot),{recursive:true,mode:0o700});
 await mkdir(outputRoot,{mode:0o700}).catch(e=>{if(e.code!=='EEXIST')throw e;});check((await readdir(outputRoot)).length===0,'RECOVERY_OUTPUT_NOT_EMPTY');
 const publicRoot=path.join(outputRoot,'public-review'),proofRoot=path.join(outputRoot,'proof');
 await mkdir(publicRoot,{mode:0o700});await mkdir(proofRoot,{mode:0o700});
 let pngRoot;
 if(cacheRoot){check(!within(path.resolve(cacheRoot),REPO),'RECOVERY_PRIVATE_CACHE_REQUIRED');await mkdir(cacheRoot,{mode:0o700});pngRoot=path.join(cacheRoot,'frames');await mkdir(pngRoot,{mode:0o700});}
 return{publicRoot,proofRoot,pngRoot};
}

async function draw(session,frame,options={}){
 const value=await session.page.evaluate(({frame,options})=>window.recoveryProof.capture(frame,options),{frame,options}),bytes=Buffer.from(value.png.split(',')[1],'base64');
 check(hash(bytes)===value.pngSHA256&&value.diagnostic.glError===0,'RECOVERY_DRAW_READBACK_INVALID');
 check(value.diagnostic.layoutAudit?.valid===true&&value.diagnostic.layoutAudit?.nativeLocationRendered===false,'RECOVERY_ACTUAL_DYNAMIC_LAYOUT_PROOF_REQUIRED');return{...value,bytes};
}

export async function probeRecovery({planFile,expectedSHA256,outputRoot,frames=[0,90,179,90]}){
 check(Array.isArray(frames)&&frames.length>0&&frames.length<=12&&frames.every(Number.isSafeInteger),'RECOVERY_BOUNDED_PROBE_REQUIRED');
 const prepared=await prepare({planFile,expectedSHA256,fullCapture:false}),{pipeline}=prepared;
 check(frames.every(v=>v>=0&&v<pipeline.totalFrames),'RECOVERY_PROBE_FRAME_RANGE');
 const {publicRoot,proofRoot}=await outputDirectories(outputRoot),started=performance.now();
 let session,stage='ACTUAL_NATIVE_FACTORY_INIT';
 const report={schema:'WORLD_ENGINE_G2_FINAL_NATIVE_PROBE_V1',status:'IN_PROGRESS',inputSHA256:expectedSHA256,
  classification:'SYNTHETIC_TECHNICAL_PROBE_NOT_STUDIO_VIDEO',fullClipRendered:false,nvidiaVerified:false,userApproved:false,
  sourceStyle:prepared.pipeline.sourceStyle,terrainStyleReceiptSHA256:prepared.terrainStyleReceiptSHA256,
  sourceStyleSHA256:prepared.terrainStyleReceiptSHA256,sourceSupport:prepared.source,
  nativeCoveredBounds:prepared.source.asset.bounds,full180ViewportContainment:pipeline.totalFrames===180?true:null,
  adapterBindings:prepared.adapterBindings,gateSHA256:prepared.gateSHA256,frames:[]};
 try{
  session=await openSession(prepared);report.runtime=session.evidence;stage='ACTUAL_NATIVE_DRAW_READPIXELS_AND_LAYOUT';
  for(let index=0;index<frames.length;index++){
   const frame=frames[index],value=await draw(session,frame),file=`PROBE_${String(index).padStart(2,'0')}_F${String(frame).padStart(3,'0')}.png`;
   await writeFile(path.join(publicRoot,file),value.bytes,{flag:'wx',mode:0o600});report.frames.push({frame,file,rawSHA256:value.rawSHA256,pngSHA256:value.pngSHA256,diagnostic:value.diagnostic});
  }
  check(session.errors.length===0&&session.requestsFailed.length===0,'RECOVERY_PROBE_BROWSER_REQUEST_ERROR');
  report.assetHTTP=session.httpTrace;report.terrainAssetHTTPRequests=session.httpTrace.filter(row=>row.recoveryTerrain).map(row=>({url:row.path,path:row.path,httpStatus:row.status,sha256:row.sha256,bytes:row.bytes}));
  report.browserErrors=session.errors;report.requestsFailed=session.requestsFailed;
  await prepared.assertBindings();report.status='PASS';
 }catch(error){report.status='FAIL';report.assetHTTP=error.recoveryHTTPTrace??session?.httpTrace??[];report.failure={stage,detail:String(error.message).slice(0,3000)};throw error;}
 finally{if(session)await session.close();report.elapsedSeconds=(performance.now()-started)/1000;await atomic(path.join(proofRoot,'PROBE_REPORT.json'),report);}
 return report;
}

export async function capture({planFile,expectedSHA256,outputRoot,cacheRoot}){
 const prepared=await prepare({planFile,expectedSHA256,fullCapture:true}),{pipeline,receipt}=prepared,total=pipeline.totalFrames;
 const {publicRoot,proofRoot,pngRoot}=await outputDirectories(outputRoot,cacheRoot),started=performance.now();
 let session,stage='ACTUAL_NATIVE_FACTORY_INIT',activeFrame=null;
 const report={schema:'WORLD_ENGINE_SOURCE_SCENE_CAPTURE_V2',recoverySchema:'WORLD_ENGINE_G2_FINAL_CAPTURE_V1',status:'IN_PROGRESS',jobId:receipt.jobId,
  classification:'SYNTHETIC_DEMO_NOT_HISTORICAL_G3',softwareOnly:true,totalFrames:total,newlyRenderedFrames:0,globalFrameRange:receipt.frameRange,
  sourceIndexSHA256:pipeline.sourceIndexSHA256,sourceBundleSHA256:pipeline.sourceBundleSHA256,requestSHA256:pipeline.requestSHA256,
  inputSHA256:expectedSHA256,executionReceiptSHA256:hash(Buffer.from(JSON.stringify(receipt))),sourceStyle:pipeline.sourceStyle,
  terrainStyleReceiptSHA256:prepared.terrainStyleReceiptSHA256,sourceStyleSHA256:prepared.terrainStyleReceiptSHA256,
  sourceSupport:prepared.source,nativeCoveredBounds:prepared.source.asset.bounds,full180ViewportContainment:true,
  adapterBindings:prepared.adapterBindings,gateSHA256:prepared.gateSHA256,
  controllerTraceStages:receipt.traceStages,frames:[],checkpoints:[],gpuRenderingVerified:false,nvidiaVerified:false,userApproved:false,
  originalG1ReRendered:false,historicalFramesRendered:0,full80SecondRendered:false,finishedFrameReuse:false,
  rendererReuse:'EXACT_UNCHANGED_universal-source-pipeline-v2/native_runtime.mjs'};
 const run=(command,args)=>execute(command,args,{timeout:Math.max(1000,Date.parse(receipt.expiresAt)-Date.now()-2500),maxBuffer:4*1024**2});
 try{
  session=await openSession(prepared);report.runtime=session.evidence;
  const checkpoints=new Set([0,30,60,90,120,150,179]);
  for(let frame=0;frame<total;frame++){
   stage='NATIVE_DRAW_READPIXELS';activeFrame=frame;check(Date.now()<Date.parse(receipt.expiresAt)-2500,'RECOVERY_CAPTURE_DEADLINE');
   const value=await draw(session,frame),name=String(frame).padStart(3,'0');
   await writeFile(path.join(pngRoot,name+'.png'),value.bytes,{flag:'wx',mode:0o600});
   report.frames.push({frame,globalFrame:frame,timeSeconds:frame/30,rawSHA256:value.rawSHA256,pngSHA256:value.pngSHA256,diagnostic:value.diagnostic});report.newlyRenderedFrames++;
   if(value.difference)report.firstToLastPixelDifference=value.difference;
   if(checkpoints.has(frame)){const file='RECOVERY_'+name+'.png';await writeFile(path.join(publicRoot,file),value.bytes,{flag:'wx',mode:0o600});report.checkpoints.push({file,frame,sha256:hash(value.bytes),bytes:value.bytes.length});}
   if(frame%15===0||frame===179)await atomic(path.join(proofRoot,'CAPTURE_STATUS.json'),{jobId:receipt.jobId,capturedFrames:report.newlyRenderedFrames,stage});
  }
  stage='ABLATION_PIXEL_PROOF';report.ablations=[];
  for(const [id,options]of [['CONTROL_OFF',{controlEnabled:false}],['FRONT_OFF',{frontEnabled:false}],['ALL_ON',{}]]){
   const value=await draw(session,90,options),file='RECOVERY_ABLATION_'+id+'.png';await writeFile(path.join(publicRoot,file),value.bytes,{flag:'wx',mode:0o600});
   report.ablations.push({id,frame:90,file,rawSHA256:value.rawSHA256,pngSHA256:hash(value.bytes),diagnostic:value.diagnostic});
  }
  check(session.errors.length===0&&session.requestsFailed.length===0,'RECOVERY_CAPTURE_BROWSER_REQUEST_ERROR');
  report.assetHTTP=session.httpTrace;report.terrainAssetHTTPRequests=session.httpTrace.filter(row=>row.recoveryTerrain).map(row=>({url:row.path,path:row.path,httpStatus:row.status,sha256:row.sha256,bytes:row.bytes}));
  report.browserErrors=session.errors;report.requestsFailed=session.requestsFailed;
  await session.close();session=null;
  stage='ENCODE';const file='G2_FINAL_DEMO_6S.mp4',video=path.join(publicRoot,file);
  await run('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-n','-framerate','30','-i',path.join(pngRoot,'%03d.png'),'-frames:v','180','-an','-c:v','libx264','-preset','fast','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video]);
  report.ffprobe=JSON.parse((await run('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
  const stream=report.ffprobe.streams[0];check(report.ffprobe.streams.length===1&&stream.codec_name==='h264'&&stream.width===1080&&stream.height===1920&&Number(stream.nb_frames)===180&&stream.avg_frame_rate==='30/1'&&Number(stream.duration)===6,'RECOVERY_VIDEO_CONTRACT');
  stage='FULL_DECODE';await run('ffmpeg',['-v','error','-xerror','-i',video,'-f','null','-']);report.fullDecode='PASS';const bytes=await readFile(video);report.video={file,sha256:hash(bytes),bytes:bytes.length};
  await prepared.assertBindings();validateGates(JSON.parse(await readFile(path.join(HERE,'reports/GATES.json'))));report.status='SOFTWARE_PREVIEW_COMPLETE';
 }catch(error){report.status='FAILED';report.assetHTTP=error.recoveryHTTPTrace??session?.httpTrace??[];report.failure={stage,frame:activeFrame,code:/^[A-Z][A-Z0-9_]+$/.test(error.message)?error.message:'RECOVERY_CAPTURE_FAILED',detail:String(error.message).slice(0,3000)};throw error;}
 finally{
  if(session)await session.close();report.elapsedSeconds=(performance.now()-started)/1000;
  await atomic(path.join(proofRoot,'CAPTURE_REPORT.json'),report);await atomic(path.join(proofRoot,'CAPTURE_STATUS.json'),{jobId:receipt.jobId,capturedFrames:report.newlyRenderedFrames,stage:report.status});
 }
 return report;
}

export function parseCaptureArguments(args){
 const values={};for(const arg of args){const m=/^--(plan|expected-sha256|output-root|cache-root)=(.+)$/.exec(arg);check(m&&!values[m[1]],'RECOVERY_CAPTURE_ARGUMENT_INVALID');values[m[1]]=m[2];}
 check(['plan','expected-sha256','output-root','cache-root'].every(k=>typeof values[k]==='string'),'RECOVERY_CAPTURE_ARGUMENT_MISSING');
 return{planFile:values.plan,expectedSHA256:values['expected-sha256'],outputRoot:values['output-root'],cacheRoot:values['cache-root']};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await capture(parseCaptureArguments(process.argv.slice(2)));
