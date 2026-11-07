/** New input CPU verification driver; reuses the existing ten-second runtime and encoder. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';

const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE),
 hash=bytes=>createHash('sha256').update(bytes).digest('hex'),within=(file,root)=>file===root||file.startsWith(root+path.sep),args={};
for(const arg of process.argv.slice(2)){const m=/^--(prepared|output|deps-root|chromium|frames)=(.+)$/.exec(arg);assert(m&&!args[m[1]],'QUALITY_PIXEL_ARGUMENT');args[m[1]]=m[2];}
for(const key of ['prepared','output','deps-root'])assert(path.isAbsolute(args[key]??''),'QUALITY_PIXEL_ABSOLUTE_'+key);
const preparedFile=await realpath(args.prepared),payload=JSON.parse(await readFile(preparedFile,'utf8')),output=path.resolve(args.output);
assert(payload.schema==='WORLD_ENGINE_PREPARED_PRESENTATION_V2'&&payload.totalFrames===300&&payload.segments.length===2,'QUALITY_PREPARED_10S_REQUIRED');
await mkdir(output,{mode:0o700});
const writeJSON=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'}),
 require=createRequire(path.join(args['deps-root'],'package.json')),{chromium}=require('playwright');
const directorAlias="['/recovery/reference-director-v1/director_events.mjs',path.join(ENGINE,'recovery/reference-director-v1/director_events.mjs')]";
for(const filename of ['recovery/universal-presentation-v2/capture_presentation.mjs','recovery/codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs'])assert((await readFile(path.join(ENGINE,filename),'utf8')).includes(directorAlias),'QUALITY_PRODUCTION_DIRECTOR_ALIAS_MISSING');
const aliases=new Map([['/recovery/reference-director-v1/director_events.mjs',path.join(ENGINE,'recovery/reference-director-v1/director_events.mjs')],['/three.js',path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js')],
 ['/web/map_infographic_v1/graphic_layout.mjs',path.join(ENGINE,'recovery/g2-final-recovery-v1/layout_extension.mjs')],
 ['/web/map_infographic_v1/graphic_layout_legacy.mjs',path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs')]]);
for(const segment of payload.segments){
 aliases.set(segment.sourceStyle.terrainAsset.url,segment.sourceStyle.terrainAsset.file);
 for(const [role,asset]of Object.entries(segment.nativePlan.assets)){
  const bound=segment.serverBindings.assets.find(row=>row.role===role);
  assert(bound&&bound.sha256===asset.sha256,'QUALITY_ASSET_BINDING_REQUIRED');
 }
}
const allowedFiles=new Set(await Promise.all([...aliases.values()].map(file=>realpath(file)))),http=[];
let browser,server,encoder,encoderExit,status='FAIL',failure,frames=[],video=null;
try{
 server=createServer(async(req,res)=>{let target='';try{
  const url=new URL(req.url,'http://localhost');target=decodeURIComponent(url.pathname);
  assert(['GET','HEAD'].includes(req.method)&&!url.search&&!target.includes('..')&&!target.includes('\\'),'QUALITY_HTTP_READ_ONLY');
  let raw,type='application/octet-stream';
  if(target==='/favicon.ico'){res.writeHead(204);res.end();return;}
  if(target==='/'){raw=Buffer.from('<!doctype html><meta charset="utf-8"><body style="margin:0"><canvas width="1080" height="1920"></canvas>');type='text/html';}
  else if(target==='/runtime.json'){raw=Buffer.from(JSON.stringify(payload));type='application/json';}
  else{
   const mounts=[['/web/',path.join(ENGINE,'web')],['/recovery/universal-presentation-v2/',path.join(ENGINE,'recovery/universal-presentation-v2')],['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]],
    mount=mounts.find(([prefix])=>target.startsWith(prefix)),candidate=aliases.get(target)??(mount?path.join(mount[1],target.slice(mount[0].length)):null);
   assert(candidate,'QUALITY_HTTP_NOT_FOUND');const file=await realpath(candidate);
   assert(file===path.resolve(candidate)&&(within(file,await realpath(REPO))||allowedFiles.has(file)),'QUALITY_HTTP_OUTSIDE_ALLOWED_SOURCE');raw=await readFile(file);
   type=/\.(mjs|js)$/.test(target)?'text/javascript':/\.png$/.test(target)?'image/png':/\.jpe?g$/.test(target)?'image/jpeg':/\.(otf|ttf)$/.test(target)?'font/otf':type;
  }
  http.push({path:target,status:200,sha256:hash(raw),bytes:raw.length});res.writeHead(200,{'content-type':type,'cache-control':'no-store','content-length':raw.length});res.end(req.method==='HEAD'?undefined:raw);
 }catch(error){http.push({path:target,status:404,error:String(error.message).slice(0,200)});res.writeHead(404);res.end();}});
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({executablePath:args.chromium??'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),pageErrors=[];
 page.on('pageerror',error=>pageErrors.push(String(error.message).slice(0,1000)));
 await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
 await page.goto(origin,{waitUntil:'load'});
 await page.evaluate(async()=>{
  window.payload=await(await fetch('/runtime.json')).json();
  window.createRuntime=(await import('/recovery/universal-presentation-v2/presentation_runtime.mjs')).createPresentationRuntime;window.currentSegment=-1;
 });
 const videoFile=path.join(output,'CLIP_10S_CPU_PREVIEW.mp4'),credit='Modern geographic context: NASA Earth Observatory Blue Marble Next Generation,2004; Natural Earth 1:10m vectors,Public Domain. Korean War event chronology: National Archives of Korea and MPVA. Direction diagram is not an observed unit route. No historical control polygons or precise landing beaches. CPU SwiftShader preview, not NVIDIA validation.';
 let stderr='';
 if(!args.frames){encoder=spawn('ffmpeg',['-hide_banner','-loglevel','error','-n','-f','image2pipe','-framerate','30','-vcodec','png','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-metadata','comment='+credit,'-movflags','+faststart',videoFile],{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',data=>{stderr=(stderr+data).slice(-4096);});encoder.stdin.on('error',()=>{});encoderExit=once(encoder,'exit');}
 const probeOnly=!!args.frames,selected=probeOnly?args.frames.split(',').map(Number):null;
 if(probeOnly)assert(selected.length>0&&new Set(selected).size===selected.length&&selected.every(f=>Number.isInteger(f)&&f>=0&&f<300),'PROBE_FRAMES_INVALID');
 const stills=new Set([0,30,75,105,149,150,185,210,240,299]);
 const critical=[96,149,150,240,299],cached=new Map(),saved=new Set(),order=probeOnly?selected:[...critical,...Array.from({length:300},(_,i)=>i)];
 for(let index=0;index<order.length;index++){
  const frame=order[index],probe=!probeOnly&&index<critical.length;
  const result=cached.has(frame)?structuredClone(cached.get(frame)):await page.evaluate(async frame=>{
   const index=window.payload.segments.findIndex(s=>frame>=s.startFrame&&frame<s.endFrame),segment=window.payload.segments[index];
   if(window.currentSegment!==index){window.runtime?.dispose();const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);window.runtime=await window.createRuntime({canvas,...segment});window.currentSegment=index;}
   const diagnostic=window.runtime.drawFrame(frame-segment.startFrame),pixels=window.runtime.readPixels();let nonBlackPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlackPixels++;
   let cyanPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]<130&&pixels[i+1]>180&&pixels[i+2]>210)cyanPixels++;
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',pixels))].map(x=>x.toString(16).padStart(2,'0')).join('');
   return{frame,segmentIndex:index,diagnostic,nonBlackPixels,cyanPixels,rawSHA256:digest,png:window.runtime.png().split(',')[1]};
  },frame);
  assert(result.nonBlackPixels>1080*1920*.2,'PREVIEW_BLACK_FRAME');assert.equal(result.diagnostic.glError,0);assert.equal(result.diagnostic.presentationMap.boundariesEnabled,false,'MODERN_BORDER_VISIBLE');
  assert(result.diagnostic.backend.includes('SwiftShader'),'PREVIEW_CPU_ONLY');
  const bad=result.diagnostic.presentationLabels?.suppressed?.filter(r=>r.reason!=='OUTSIDE_EVENT_TIMING')??[];
  assert.deepEqual(bad,[],'PREVIEW_ACTIVE_LABEL_SUPPRESSION_'+frame);
  const segment=payload.segments[result.segmentIndex],local=frame-segment.startFrame;
  assert.equal(result.diagnostic.presentationLabels.visibleCount,segment.presentation.labels.items.filter(x=>local>=x.startFrame&&local<x.endFrame).length,'PREVIEW_ACTIVE_LABEL_MISSING');
  assert.equal(result.diagnostic.presentationMap.areaViewportPolicy,'NATIVE_VIEWPORT_CLIP_UNCHANGED_GEOMETRY');
  const accent=segment.presentation.mapStyle.lineAccentFrames;if(accent&&local>=accent[0]&&local<accent[1]){assert(result.diagnostic.features.some(x=>x.lineAccent?.fronts?.some(f=>f.drawn)),'PREVIEW_SOURCE_DIRECTION_NOT_DRAWN_'+frame);}
  const png=Buffer.from(result.png,'base64');
  assert.equal(result.diagnostic.layout.nativeAuditScope,'NATIVE_GRAPHICS_NOT_DRAWN');
  assert.equal(result.diagnostic.layout.valid,null,'HIDDEN_NATIVE_LAYOUT_MUST_NOT_CLAIM_PASS');
  if(probe){cached.set(frame,structuredClone(result));await writeFile(path.join(output,`FRAME_${String(frame).padStart(3,'0')}.png`),png,{flag:'wx'});await writeJSON(`FRAME_${String(frame).padStart(3,'0')}.json`,{...result,png:undefined});saved.add(frame);console.log(JSON.stringify({stage:'NEW_CRITICAL_FRAME_DRAW',frame}));continue;}
  delete result.png;
  frames.push({frame,resultSHA256:result.rawSHA256,cameraBounds:result.diagnostic.camera.bounds,
   featureChangedPixels:result.diagnostic.featureChangedPixels,cyanPixels:result.cyanPixels,labels:result.diagnostic.presentationLabels,nonBlackPixels:result.nonBlackPixels});
  if((probeOnly||stills.has(frame))&&!saved.has(frame)){await writeFile(path.join(output,`FRAME_${String(frame).padStart(3,'0')}.png`),png,{flag:'wx'});await writeJSON(`FRAME_${String(frame).padStart(3,'0')}.json`,result);}
  if(probeOnly){console.log(JSON.stringify({stage:'REMAINING_CRITICAL_FRAME_DRAW',frame}));continue;}
  assert.equal(encoder.exitCode,null,'PREVIEW_ENCODER_EARLY_EXIT');
  if(!encoder.stdin.write(png))await Promise.race([once(encoder.stdin,'drain'),encoderExit.then(()=>{throw Error('PREVIEW_ENCODER_CLOSED');})]);
  if(frame%15===0||frame===299)console.log(JSON.stringify({stage:'NEW_SAMPLE_CPU_DRAW',frame,totalFrames:300}));
 }
 if(!probeOnly){encoder.stdin.end();const [code]=await encoderExit;assert.equal(code,0,stderr);encoder=null;
 const execute=promisify(execFile),probe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',videoFile],{maxBuffer:2*1024**2})).stdout),v=probe.streams.find(s=>s.codec_type==='video');
 assert.equal(v.width,1080);assert.equal(v.height,1920);assert.equal(v.nb_frames,'300');assert.equal(v.avg_frame_rate,'30/1');assert.equal(Number(probe.format.duration),10);
 const decoded=await execute('ffmpeg',['-v','error','-i',videoFile,'-f','null','-'],{timeout:120000,maxBuffer:1024**2});assert.equal(decoded.stderr.trim(),'');
 const raw=await readFile(videoFile);video={file:path.basename(videoFile),bytes:raw.length,sha256:hash(raw),durationSeconds:10,frames:300,fps:30,width:1080,height:1920,fullDecode:'PASS',audioStreams:0};
 assert.deepEqual(pageErrors,[]);assert.deepEqual(frames[149].cameraBounds,frames[150].cameraBounds);
 const last=frames.at(-1).labels.drawn;assert(last.some(x=>x.alpha===1),'PREVIEW_FINAL_INFORMATION_HOLD_REQUIRED');
 status='PASS';}else{assert.deepEqual(pageErrors,[]);status='PASS_SELECTED_FRAMES_ONLY';}
}catch(error){failure=String(error.stack??error).slice(0,8000);throw error;}
finally{
 encoder?.kill('SIGTERM');await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));
 await writeJSON('FRAME_EVIDENCE.json',{frames});
 await writeJSON('CPU_PREVIEW_RESULT.json',{schema:'WORLD_ENGINE_REFERENCE_CPU_PREVIEW_V2',status,failure,video,
  framesDrawn:frames.length,softwareOnly:true,gpuExecutions:0,referenceQualityApproved:false,
  seamSamePixels:frames.length>150?frames[149].resultSHA256===frames[150].resultSHA256:null,
  oldPASSReruns:0,scope:args.frames?'SELECTED_FRAMES_ONLY_NO_MP4':'NEW_SAMPLE_300_CONTIGUOUS_CPU_FRAMES_AND_ENCODE',limitations:['Not NVIDIA or gCube validation','Regional raster: no newly resolved local detail','Visual quality requires review']});
 await writeJSON('HTTP_ASSET_BINDINGS.json',http);
}
