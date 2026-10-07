// Additive transport/audit diagnostics. Frozen approved visual tool and pixel path are preserved.
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdir,writeFile,readFile,rename} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import {auditFailures,auditFailureSnapshot,validateJpeg,FrameFailure,FFmpegPipe,encoderArguments} from './scene_frame_contract.mjs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const dir=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(dir,'..'),legacy=path.resolve(root,'../cinematic-world-map');
const require=createRequire(path.join(legacy,'package.json')),{chromium}=require('playwright');
const options={};for(let i=2;i<process.argv.length;i++){const a=process.argv[i];if(!a.startsWith('--'))throw Error('Expected named argument: '+a);const at=a.indexOf('=');if(at!==-1)options[a.slice(2,at)]=a.slice(at+1);else options[a.slice(2)]=process.argv[i+1]&&!process.argv[i+1].startsWith('--')?process.argv[++i]:true;}
const url=options.url,output=options.output||options.out;if(!url||!output)throw Error('Required: --url URL --output MP4 --duration SECONDS');
const destination=path.resolve(output),auditPath=path.resolve(options.audit||destination.replace(/\.mp4$/i,'')+'.audit.json');
const stem=destination.replace(/\.mp4$/i,''),checkpointPath=stem+'.checkpoint.json',manifestPath=stem+'.manifest.json';
for(const file of [destination,auditPath,checkpointPath,manifestPath])if(existsSync(file))throw Error('Refusing to overwrite existing result '+file);
await mkdir(path.dirname(destination),{recursive:true});await mkdir(path.dirname(auditPath),{recursive:true});
const quality=String(options.quality||'HIGH').toUpperCase();if(!['FAST','HIGH','CINEMA'].includes(quality))throw Error('Unknown render quality');
const internalWidth=Number(options.width||(quality==='FAST'?540:2160)),internalHeight=Number(options.height||Math.round(internalWidth*16/9));
const outputWidth=Number(options['output-width']||(quality==='FAST'?540:1080)),outputHeight=Number(options['output-height']||Math.round(outputWidth*16/9));
if(Math.abs(internalHeight/internalWidth-16/9)>1e-5||Math.abs(outputHeight/outputWidth-16/9)>1e-5)throw Error('Render dimensions must be 9:16');
if(quality!=='FAST'&&internalWidth<2160)throw Error('HIGH/CINEMA must preserve MASTER V3 2160-pixel internal width');
const fps=Number(options.fps||30),duration=Number(options.duration),start=Number(options.start||0),samples=Number(options.samples||1);if(!(duration>0&&fps>=30&&samples>=1))throw Error('Positive duration, >=30fps, samples>=1 required');
const frames=Math.round(duration*fps);if(Math.abs(frames/fps-duration)>.5/fps+1e-8)throw Error('Duration is not aligned to frame grid');
const isFlat=new URL(url).pathname.endsWith('render_production_flat.html');
const sourceFiles=[['flat_renderer',path.join(root,'web/flat_renderer.js')],['flat_semantics',path.join(root,'web/flat_semantics.js')],['render_html',path.join(root,isFlat?'web/render_production_flat.html':'web/render_production_earth.html')],['render_tool',fileURLToPath(import.meta.url)],['korean_font',path.join(root,'web/fonts/NotoSansCJKkr-Regular.otf')],...['assets/v3/earth/earth-day-8k.jpg','assets/v3/fonts/OpenSans-Light.ttf','assets/gis/earth-topology.png','assets/gis/countries_50m.geojson','assets/gis/coastlines_50m.geojson'].map(p=>[p,path.join(legacy,p)])];
const flatSourceManifest=path.join(root,'assets/flat/SOURCES.json');
if(existsSync(flatSourceManifest)){
 sourceFiles.push(['flat_source_manifest',flatSourceManifest]);
 const raw=JSON.parse(await readFile(flatSourceManifest,'utf8')),rows=Array.isArray(raw)?raw:(raw.assets||[]);
 for(const item of rows)sourceFiles.push(['flat_asset:'+item.id,path.join(root,item.file)]);
}
for(const name of ['flat_polish_renderer.js','earth_polish_adapter.js','geographic_polish_transition.js'])sourceFiles.push(['visual_polish:'+name,path.join(root,'web',name)]);
sourceFiles.push(['entity_separation',path.join(root,'web/flat_entity_separation_polish.js')]);
sourceFiles.push(['production_visual_adapter',path.join(root,'web/production_visual_adapter.js')]);
sourceFiles.push(['earth_adapter',path.join(root,'web/earth_adapter.js')]);
if(!isFlat)for(const name of ['src/renderer_v3.js','src/engine_v3.js','src/core_v1_preserved.js','assets/v3/earth/earth-night-8k.jpg','assets/v3/earth/earth-clouds-8k.jpg'])sourceFiles.push([name,path.join(legacy,name)]);
if(options['scene-json'])sourceFiles.push(['scene_json',path.resolve(options['scene-json'])]);
sourceFiles.push(['frame_contract',path.join(root,'tools/scene_frame_contract.mjs')]);
const sourceHashes={};for(const [key,file] of sourceFiles){
 try{sourceHashes[key]=createHash('sha256').update(await readFile(file)).digest('hex');}
 catch(error){console.error('WORLD_ENGINE_RENDER_FAILURE '+JSON.stringify({code:'ASSET_MISSING',frame_index:null,failed_invariants:['REQUIRED_SOURCE_UNREADABLE']}));throw error;}
}
const started=Date.now();let browser,ff,watchdog,complete=false,lastProgress=Date.now(),completedFrames=0,sceneId=null,frameIndex=null,pipe=null,failedAudit=null;const audits=[],errors=[];
const initial={complete:false,status:'INITIALIZING',completedFrames:0,requestedFrames:frames,nextStart:start,output:destination,quality,sourceHashes};await writeFile(checkpointPath,JSON.stringify(initial,null,2),{flag:'wx'});
async function checkpoint(status,extra={}){const value={...initial,status,completedFrames,requestedFrames:frames,nextStart:start+completedFrames/fps,elapsedSeconds:(Date.now()-started)/1000,...extra};const temp=checkpointPath+'.tmp';await writeFile(temp,JSON.stringify(value,null,2));await rename(temp,checkpointPath);}
try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const targetUrl=new URL(url);targetUrl.searchParams.set('width',String(internalWidth));
 await page.goto(targetUrl.href,{timeout:120000});await page.waitForFunction(()=>window.ready||window.renderError,null,{timeout:120000});
 const initError=await page.evaluate(()=>window.renderError||null);if(initError||errors.length)throw Error(JSON.stringify({initError,errors}));
 const scene=await page.evaluate(()=>({duration:window.app.duration,id:window.app.sceneSpec.scene_id,dimensions:[window.app.w,window.app.h],numeric:window.app.numericPreflight(30)}));
 sceneId=scene.id;
 if(scene.dimensions[0]!==internalWidth||scene.dimensions[1]!==internalHeight)throw Error('Internal render dimensions mismatch');
 if(start+duration>scene.duration+1/fps+1e-8)throw Error('Requested render exceeds Scene duration');
 if(isFlat&&scene.numeric.render_mode!=='FLAT_MAP_PREMIUM'||!scene.numeric.finite||scene.numeric.routeWithinEarth||scene.numeric.entityWithinEarth||scene.numeric.cameraWithinEarth||scene.numeric.maxCameraAngleDegreesPerFrame>2.5)throw new FrameFailure('FRAME_AUDIT_FAILED',{failed_invariants:['NUMERIC_PREFLIGHT_FAILED']});
 const encoderOptions=encoderArguments({outputWidth,outputHeight,fps,quality,destination});
 lastProgress=Date.now();watchdog=setInterval(()=>{if(Date.now()-lastProgress>120000){errors.push('WATCHDOG: no completed frame for 120 seconds');void browser.close();if(ff)ff.kill('SIGTERM');}},15000);
 for(let i=0;i<frames;i++){
  frameIndex=i;const t=start+i/fps;
  const result=await page.evaluate(async ({t,samples})=>{
   window.renderFrame(t,samples);
   const uri=window.app.canvas.toDataURL('image/jpeg',.99),jpeg=uri.split(',')[1];
   // Keep the approved post-readback audit: readPixels/export may set GL errors.
   const audit=window.app.audit(t);
   let decoded=null,decodeError=false;
   try{const bytes=Uint8Array.from(atob(jpeg),character=>character.charCodeAt(0)),image=await createImageBitmap(new Blob([bytes],{type:'image/jpeg'}));decoded=[image.width,image.height];image.close();}catch{decodeError=true;}
   return {jpeg,audit,decoded,decodeError};
  },{t,samples});
  failedAudit=auditFailureSnapshot(result.audit);
  const separation=result.audit.entitySeparation;
  if(isFlat&&(!separation||separation.version!=='v1'||separation.pairs.some(pair=>pair.minimumAlpha>.015&&pair.actualProjectedBoxesOverlap)))throw new FrameFailure('FRAME_AUDIT_FAILED',{failed_invariants:['ENTITY_SEPARATION_FAILED']});
  if(result.audit.productionDefaults?.version!=='v1')throw new FrameFailure('FRAME_AUDIT_FAILED',{failed_invariants:['PRODUCTION_RENDERER_REQUIRED']});
  const failures=auditFailures(result.audit,errors);
  if(failures.length)throw new FrameFailure('FRAME_AUDIT_FAILED',{scene_id:scene.id,frame_index:i,failed_invariants:failures});
  const buffer=Buffer.from(result.jpeg||'','base64');
  validateJpeg(buffer,{width:internalWidth,height:internalHeight,decoded:result.decoded,decodeError:result.decodeError,frameIndex:i,expectedIndex:completedFrames});
  // No encoder receives an empty/invalid stream after a first-frame audit failure.
  if(!pipe){pipe=new FFmpegPipe(encoderOptions);ff=pipe.child;}
  audits.push(result.audit);await pipe.write(buffer);completedFrames=i+1;lastProgress=Date.now();failedAudit=null;
  if(i%5===0||i===frames-1)await checkpoint('RENDERING');
  console.log(JSON.stringify({stage:'scene_render',scene_id:scene.id,completed_frames:completedFrames,total_frames:frames,time:t,elapsed_seconds:(lastProgress-started)/1000}));
 }
 await pipe.finish();clearInterval(watchdog);watchdog=null;
 await writeFile(auditPath,JSON.stringify(audits,null,2),{flag:'wx'});
 const manifest={complete:true,scene_id:scene.id,sourceHashes,sourceAssets:sourceFiles.filter(([k])=>k.startsWith('assets/')||k.startsWith('flat_asset:')).map(([k])=>({path:k,sha256:sourceHashes[k]})),start,duration:frames/fps,frames,fps,quality,preview_only:quality==='FAST',internalResolution:[internalWidth,internalHeight],outputResolution:[outputWidth,outputHeight],motionIntegrationTaps:isFlat?1:7,temporalSceneSamples:samples,renderer:isFlat?'PRODUCTION_PREMIUM_FLAT_V004':'PRODUCTION_READABLE_MASTER_V3_EARTH',productionDefaults:'v1',projection:scene.numeric.projection||'LOCAL_MERCATOR',output:destination,audit:auditPath,numericPreflight:{...scene.numeric,records:undefined},elapsedSeconds:(Date.now()-started)/1000};
 await writeFile(manifestPath,JSON.stringify(manifest,null,2),{flag:'wx'});complete=true;await checkpoint('COMPLETE',{...manifest,complete:true});console.log(JSON.stringify({stage:'scene_complete',...manifest}));
}catch(error){
 const cause={code:error.code||'SCENE_RENDER_FAILED',scene_id:sceneId,frame_index:frameIndex,failed_invariants:error.details?.failed_invariants||[],encoder_return_code:pipe?.result?.code??null};
 console.error('WORLD_ENGINE_RENDER_FAILURE '+JSON.stringify(cause));
 if(error.code==='FFMPEG_PIPE_FAILED')for(const line of (pipe?.stderr||[]))console.error(line);
 await checkpoint('FAILED',{error:String(error?.stack||error),root_cause:cause,failed_audit:failedAudit,browserErrors:errors,complete:false});if(audits.length&&!existsSync(auditPath))await writeFile(auditPath,JSON.stringify(audits,null,2),{flag:'wx'});throw error;
}finally{if(watchdog)clearInterval(watchdog);if(pipe)await pipe.abort();if(browser)await browser.close().catch(()=>{});if(!complete)console.error('Completed frames and partial output preserved; retry uses a new output version.');}
