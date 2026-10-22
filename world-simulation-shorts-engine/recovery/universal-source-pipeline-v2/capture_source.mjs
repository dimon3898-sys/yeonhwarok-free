/** Bounded fresh software capture, selected only by the authenticated source worker. */
import {readFile,writeFile,mkdir,readdir,lstat,realpath,rename} from 'node:fs/promises';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
const execute=promisify(execFile),HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE);
const hash=b=>createHash('sha256').update(b).digest('hex'),within=(p,r)=>p===r||p.startsWith(r+path.sep);
function check(ok,code){if(!ok)throw Error(code);}
async function json(file,value){const tmp=file+'.new';await writeFile(tmp,JSON.stringify(value),{flag:'wx',mode:0o600});await rename(tmp,file);}
async function confined(file,root){const resolved=await realpath(file);check(within(resolved,root)&&resolved===path.resolve(file),'SOURCE_HTTP_PATH_REJECTED');return readFile(file);}

export async function capture({planFile,expectedSHA256,outputRoot,cacheRoot}){
 const raw=await readFile(planFile);check(hash(raw)===expectedSHA256,'SOURCE_CAPTURE_PLAN_HASH_MISMATCH');
 const mode=lstat(planFile);check(((await mode).mode&0o077)===0,'SOURCE_CAPTURE_PRIVATE_PLAN_REQUIRED');
 const packageData=JSON.parse(raw),pipeline=packageData.sourcePipeline,receipt=packageData.executionReceipt;
 check(packageData.schema==='WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2'&&pipeline.ready===true&&receipt.softwareOnly===true,'SOURCE_CAPTURE_SCOPE_INVALID');
 // This version's pixel consumer is explicitly a nonhistorical technical demo.
 check(pipeline.mode==='SYNTHETIC_TEST'&&receipt.historicalRenderAllowed===false,'SOURCE_HISTORICAL_PIXEL_CONSUMER_NOT_ADMITTED');
 const total=pipeline.totalFrames,inputs=pipeline.runtimePayload;
 check(Number.isSafeInteger(total)&&total>=2&&total<=240&&inputs.frames.length===total,'SOURCE_CAPTURE_FRAME_LIMIT');
 check(Date.parse(receipt.expiresAt)>Date.now()+5000,'SOURCE_CAPTURE_RECEIPT_EXPIRED');
 check(within(path.resolve(outputRoot),HERE)&&!within(path.resolve(cacheRoot),REPO),'SOURCE_CAPTURE_FRESH_NAMESPACE_REQUIRED');
 await mkdir(outputRoot,{mode:0o700}).catch(e=>{if(e.code!=='EEXIST')throw e;});
 check((await readdir(outputRoot)).length===0,'SOURCE_CAPTURE_OUTPUT_NOT_EMPTY');
 await mkdir(cacheRoot,{mode:0o700});
 const publicRoot=path.join(outputRoot,'public-review'),proofRoot=path.join(outputRoot,'proof'),pngRoot=path.join(cacheRoot,'frames');
 for(const p of [publicRoot,proofRoot,pngRoot])await mkdir(p,{mode:0o700});
 const ownFiles=['native_runtime.mjs','camera_numeric_contract.mjs','source_geometry_contract.mjs','capture_source.mjs','source_contract.py'];
 const bindings=await Promise.all(ownFiles.map(async name=>({path:name,sha256:hash(await readFile(path.join(HERE,name)))})));
 const assertBindings=async()=>{for(const row of bindings)check(hash(await readFile(path.join(HERE,row.path)))===row.sha256,'SOURCE_CAPTURE_ADAPTER_CHANGED');};
 for(const row of inputs.sourceBindings){
  const file=path.isAbsolute(row.path)?row.path:path.resolve(REPO,row.path);
  check(hash(await readFile(file))===row.sha256,'SOURCE_NATIVE_ASSET_BINDING_CHANGED');
 }
 const runtimeBytes=Buffer.from(JSON.stringify(inputs));
 const server=createServer(async(req,res)=>{
  try{
   const u=new URL(req.url,'http://127.0.0.1'),p=decodeURIComponent(u.pathname);
   check(!u.search&&!p.includes('..')&&!p.includes('\\'),'SOURCE_HTTP_TARGET_REJECTED');
   let body,type='application/octet-stream';
   if(p==='/'){body=Buffer.from('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}canvas{display:block}</style></head><body><canvas id="map" width="1080" height="1920"></canvas></body></html>');type='text/html';}
   else if(p==='/runtime.json'){body=runtimeBytes;type='application/json';}
   else if(['/native_runtime.mjs','/camera_numeric_contract.mjs','/source_geometry_contract.mjs'].includes(p)){body=await readFile(path.join(HERE,p.slice(1)));type='text/javascript';}
   else {
    const mounts=[['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]];
    if(p==='/three.js'){body=await confined(path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js'),ENGINE);type='text/javascript';}
    else {const mount=mounts.find(([prefix])=>p.startsWith(prefix));check(mount,'SOURCE_HTTP_NOT_FOUND');body=await confined(path.join(mount[1],p.slice(mount[0].length)),mount[1]);
     type=/\.(mjs|js)$/.test(p)?'text/javascript':/\.png$/.test(p)?'image/png':/\.jpe?g$/.test(p)?'image/jpeg':/\.otf$/.test(p)?'font/otf':type;}
   }
   res.writeHead(200,{'Content-Type':type,'Content-Length':body.length,'Cache-Control':'no-store'});res.end(body);
  }catch{res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const require=createRequire('/workspace/exact-65422-capsule-20261020/package.json'),{chromium}=require('playwright');
 let browser,stage='BROWSER_START',activeFrame=null;
 const started=performance.now(),report={schema:'WORLD_ENGINE_SOURCE_SCENE_CAPTURE_V2',status:'IN_PROGRESS',jobId:receipt.jobId,
  classification:'SYNTHETIC_DEMO_NOT_HISTORICAL_G3',softwareOnly:true,totalFrames:total,newlyRenderedFrames:0,globalFrameRange:receipt.frameRange,
  sourceIndexSHA256:pipeline.sourceIndexSHA256,sourceBundleSHA256:pipeline.sourceBundleSHA256,requestSHA256:pipeline.requestSHA256,
  executionReceiptSHA256:hash(Buffer.from(JSON.stringify(receipt))),adapterBindings:bindings,inputSHA256:expectedSHA256,
  controllerTraceStages:receipt.traceStages,frames:[],checkpoints:[],gpuRenderingVerified:false,nvidiaVerified:false,userApproved:false,
  originalG1ReRendered:false,historicalFramesRendered:0,full80SecondRendered:false,finishedFrameReuse:false};
 const run=(command,args)=>execute(command,args,{timeout:Math.max(1000,Date.parse(receipt.expiresAt)-Date.now()-2500),maxBuffer:4*1024**2});
 try{
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin);
  stage='NATIVE_FACTORY_INIT';
  report.runtime=await page.evaluate(async()=>{
   const inputs=await(await fetch('/runtime.json')).json(),{createUniversalSourceRuntime}=await import('/native_runtime.mjs');
   const runtime=await createUniversalSourceRuntime({canvas:document.getElementById('map'),...inputs});
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
   let first;
   window.sourceProof={runtime,async capture(frame,options={}){
    const diagnostic=runtime.drawFrame(frame,options),pixels=runtime.readPixels(),png=runtime.png();
    if(frame===0&&!first)first=pixels.slice();
    let difference=null;
    if(frame===inputs.frames.length-1&&first){let changed=0,left=1080,right=-1,top=1920,bottom=-1;
     for(let i=0;i<pixels.length;i+=4)if(pixels[i]!==first[i]||pixels[i+1]!==first[i+1]||pixels[i+2]!==first[i+2]){const x=(i/4)%1080,y=1919-Math.floor(i/4/1080);changed++;left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
     difference={changedPixels:changed,box:changed?[left,top,right+1,bottom+1]:null};}
    return{diagnostic,rawSHA256:await digest(pixels),pngSHA256:await digest(Uint8Array.from(atob(png.split(',')[1]),x=>x.charCodeAt(0))),png,difference};
   }};
   return runtime.evidence;
  });
  check(report.runtime.backend.includes('SwiftShader'),'SOURCE_CAPTURE_SOFTWARE_BACKEND_REQUIRED');
  const checkpoints=new Set([0,30,60,90,120,150,total-1].filter(f=>f<total));
  for(let f=0;f<total;f++){
   activeFrame=f;stage='NATIVE_DRAW_READPIXELS';check(Date.now()<Date.parse(receipt.expiresAt)-2500,'SOURCE_CAPTURE_DEADLINE');
   const value=await page.evaluate(f=>window.sourceProof.capture(f),f),bytes=Buffer.from(value.png.split(',')[1],'base64');
   check(hash(bytes)===value.pngSHA256&&value.diagnostic.glError===0,'SOURCE_CAPTURE_READBACK_INVALID');
   const name=String(f).padStart(3,'0');await writeFile(path.join(pngRoot,name+'.png'),bytes,{flag:'wx',mode:0o600});
   report.frames.push({frame:f,globalFrame:pipeline.startFrame+f,timeSeconds:f/30,rawSHA256:value.rawSHA256,pngSHA256:value.pngSHA256,diagnostic:value.diagnostic});
   report.newlyRenderedFrames++;
   if(value.difference)report.firstToLastPixelDifference=value.difference;
   if(checkpoints.has(f)){const file='DEMO_'+name+'.png';await writeFile(path.join(publicRoot,file),bytes,{flag:'wx',mode:0o600});report.checkpoints.push({file,frame:f,sha256:hash(bytes),bytes:bytes.length});}
   if(f%15===0||f===total-1)await json(path.join(proofRoot,'CAPTURE_STATUS.json'),{jobId:receipt.jobId,capturedFrames:report.newlyRenderedFrames,stage});
  }
  stage='ABLATION_PIXEL_PROOF';const probe=Math.floor(total/2);
  report.ablations=[];
  for(const [id,options]of [['CONTROL_OFF',{controlEnabled:false}],['FRONT_OFF',{frontEnabled:false}],['ALL_ON',{}]]){
   const value=await page.evaluate(({probe,options})=>window.sourceProof.capture(probe,options),{probe,options}),bytes=Buffer.from(value.png.split(',')[1],'base64'),file='DEMO_ABLATION_'+id+'.png';
   await writeFile(path.join(publicRoot,file),bytes,{flag:'wx',mode:0o600});report.ablations.push({id,frame:probe,file,rawSHA256:value.rawSHA256,pngSHA256:hash(bytes),diagnostic:value.diagnostic});
  }
  check(errors.length===0,'SOURCE_CAPTURE_BROWSER_ERROR');
  await page.evaluate(()=>window.sourceProof.runtime.dispose());await browser.close();browser=null;
  stage='ENCODE';const file='WORLD_ENGINE_UNIVERSAL_SOURCE_DEMO_6S.mp4',video=path.join(publicRoot,file);
  await run('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-n','-framerate','30','-i',path.join(pngRoot,'%03d.png'),'-frames:v',String(total),'-an','-c:v','libx264','-preset','fast','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video]);
  report.ffprobe=JSON.parse((await run('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
  const stream=report.ffprobe.streams[0];check(report.ffprobe.streams.length===1&&stream.codec_name==='h264'&&stream.width===1080&&stream.height===1920&&Number(stream.nb_frames)===total&&stream.avg_frame_rate==='30/1','SOURCE_CAPTURE_VIDEO_CONTRACT');
  stage='FULL_DECODE';await run('ffmpeg',['-v','error','-xerror','-i',video,'-f','null','-']);
  report.fullDecode='PASS';const data=await readFile(video);report.video={file,sha256:hash(data),bytes:data.length};
  await assertBindings();report.status='SOFTWARE_PREVIEW_COMPLETE';
 }catch(error){report.status='FAILED';report.failure={stage,frame:activeFrame,code:/^[A-Z][A-Z0-9_]+$/.test(error.message)?error.message:'SOURCE_CAPTURE_FAILED',detail:String(error.message).slice(0,3000)};throw error;}
 finally{
  report.elapsedSeconds=(performance.now()-started)/1000;
  await json(path.join(proofRoot,'CAPTURE_REPORT.json'),report);
  await json(path.join(proofRoot,'CAPTURE_STATUS.json'),{jobId:receipt.jobId,capturedFrames:report.newlyRenderedFrames,stage:report.status});
  if(browser)await browser.close().catch(()=>{});await new Promise(resolve=>server.close(resolve));
 }
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args={};for(const arg of process.argv.slice(2)){const m=/^--(plan|expected-sha256|output-root|cache-root)=(.+)$/.exec(arg);check(m&&!args[m[1]],'SOURCE_CAPTURE_ARGUMENT_INVALID');args[m[1]]=m[2];}
 await capture({planFile:args.plan,expectedSHA256:args['expected-sha256'],outputRoot:args['output-root'],cacheRoot:args['cache-root']});
}
