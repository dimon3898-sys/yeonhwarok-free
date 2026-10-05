import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdir,writeFile,readFile,rename} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
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
const sourceFiles=[['adapter',path.join(root,'web/earth_adapter.js')],['render_html',path.join(root,'web/render_transition.html')],['render_tool',fileURLToPath(import.meta.url)],['transition_adapter',path.join(root,'web/transition_adapter.js')],['map_transition',path.join(root,'web/map_transition.js')],['korean_font',path.join(root,'web/fonts/NotoSansCJKkr-Regular.otf')],...['src/renderer_v3.js','src/engine_v3.js','src/core_v1_preserved.js','src/aircraft_v3.js','assets/v3/earth/earth-day-8k.jpg','assets/v3/earth/earth-night-8k.jpg','assets/v3/earth/earth-clouds-8k.jpg','assets/v3/fonts/OpenSans-Light.ttf','assets/gis/earth-topology.png','assets/gis/countries_50m.geojson'].map(p=>[p,path.join(legacy,p)])];
if(options['scene-json'])sourceFiles.push(['scene_json',path.resolve(options['scene-json'])]);
const sourceHashes={};for(const [key,file] of sourceFiles)sourceHashes[key]=createHash('sha256').update(await readFile(file)).digest('hex');
const started=Date.now();let browser,ff,watchdog,complete=false,lastProgress=Date.now(),completedFrames=0;const audits=[],errors=[];
const initial={complete:false,status:'INITIALIZING',completedFrames:0,requestedFrames:frames,nextStart:start,output:destination,quality,sourceHashes};await writeFile(checkpointPath,JSON.stringify(initial,null,2),{flag:'wx'});
async function checkpoint(status,extra={}){const value={...initial,status,completedFrames,requestedFrames:frames,nextStart:start+completedFrames/fps,elapsedSeconds:(Date.now()-started)/1000,...extra};const temp=checkpointPath+'.tmp';await writeFile(temp,JSON.stringify(value,null,2));await rename(temp,checkpointPath);}
try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const targetUrl=new URL(url);targetUrl.searchParams.set('width',String(internalWidth));
 await page.goto(targetUrl.href,{timeout:120000});await page.waitForFunction(()=>window.ready||window.renderError,{timeout:120000});
 const initError=await page.evaluate(()=>window.renderError||null);if(initError||errors.length)throw Error(JSON.stringify({initError,errors}));
 const scene=await page.evaluate(()=>({duration:window.app.duration,id:window.app.sceneSpec.scene_id,dimensions:[window.app.w,window.app.h],numeric:window.app.numericPreflight(30)}));
 if(scene.dimensions[0]!==internalWidth||scene.dimensions[1]!==internalHeight)throw Error('Internal render dimensions mismatch');
 if(start+duration>scene.duration+1/fps+1e-8)throw Error('Requested render exceeds Scene duration');
 if(!scene.numeric.finite||scene.numeric.routeWithinEarth||scene.numeric.entityWithinEarth||scene.numeric.cameraWithinEarth||scene.numeric.maxCameraAngleDegreesPerFrame>2.5)throw Error('Numeric Scene preflight failed');
 ff=spawn('ffmpeg',['-hide_banner','-loglevel','warning','-n','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-vf',`scale=${outputWidth}:${outputHeight}:flags=lanczos:in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,setsar=1,format=yuv420p`,'-c:v','libx264','-preset',quality==='FAST'?'medium':'slow','-crf',quality==='FAST'?'18':'15','-threads','4','-pix_fmt','yuv420p','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1','-movflags','+faststart','-an',destination],{stdio:['pipe','inherit','inherit']});
 const exited=once(ff,'exit');ff.stdin.on('error',e=>errors.push('FFmpeg input '+e.message));
 lastProgress=Date.now();watchdog=setInterval(()=>{if(Date.now()-lastProgress>120000){errors.push('WATCHDOG: no completed frame for 120 seconds');void browser.close();ff.kill('SIGTERM');}},15000);
 for(let i=0;i<frames;i++){
  const t=start+i/fps;
  const result=await page.evaluate(({t,samples})=>{window.renderFrame(t,samples);return {jpeg:window.app.canvas.toDataURL('image/jpeg',.99).split(',')[1],audit:window.app.audit(t)};},{t,samples});
  if(errors.length||result.audit.webglError||result.audit.textClipped.length||result.audit.entityClipped.length||result.audit.missingTextures.length||result.audit.routeInsideEarth||result.audit.routeDiscontinuities.length||!result.audit.fontReady)throw Error('Frame audit failed '+JSON.stringify({errors,audit:result.audit}));
  audits.push(result.audit);if(!ff.stdin.write(Buffer.from(result.jpeg,'base64')))await once(ff.stdin,'drain');completedFrames=i+1;lastProgress=Date.now();
  if(i%5===0||i===frames-1)await checkpoint('RENDERING');
  console.log(JSON.stringify({stage:'scene_render',scene_id:scene.id,completed_frames:completedFrames,total_frames:frames,time:t,elapsed_seconds:(lastProgress-started)/1000}));
 }
 ff.stdin.end();const [code]=await exited;clearInterval(watchdog);watchdog=null;if(code!==0)throw Error('FFmpeg exited '+code);
 await writeFile(auditPath,JSON.stringify(audits,null,2),{flag:'wx'});
 const manifest={complete:true,scene_id:scene.id,sourceHashes,sourceAssets:sourceFiles.filter(([k])=>k.startsWith('assets/')).map(([k])=>({path:k,sha256:sourceHashes[k]})),start,duration:frames/fps,frames,fps,quality,preview_only:quality==='FAST',internalResolution:[internalWidth,internalHeight],outputResolution:[outputWidth,outputHeight],motionIntegrationTaps:7,temporalSceneSamples:samples,renderer:'PRESERVED_V3_ATMOSPHERIC_HANDOFF',output:destination,audit:auditPath,numericPreflight:{...scene.numeric,records:undefined},elapsedSeconds:(Date.now()-started)/1000};
 await writeFile(manifestPath,JSON.stringify(manifest,null,2),{flag:'wx'});complete=true;await checkpoint('COMPLETE',{...manifest,complete:true});console.log(JSON.stringify({stage:'scene_complete',...manifest}));
}catch(error){await checkpoint('FAILED',{error:String(error?.stack||error),browserErrors:errors,complete:false});if(audits.length&&!existsSync(auditPath))await writeFile(auditPath,JSON.stringify(audits,null,2),{flag:'wx'});throw error;
}finally{if(watchdog)clearInterval(watchdog);if(ff&&ff.exitCode===null){ff.stdin.destroy();ff.kill('SIGTERM');}if(browser)await browser.close().catch(()=>{});if(!complete)console.error('Completed frames and partial output preserved; retry uses a new output version.');}
