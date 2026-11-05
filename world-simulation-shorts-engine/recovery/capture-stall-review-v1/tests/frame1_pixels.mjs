/** Focused free CPU pixels over the new Scene. No NVIDIA launch or MP4 encode. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';

const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../../..'),REPO=path.dirname(ENGINE),
 hash=bytes=>createHash('sha256').update(bytes).digest('hex'),within=(file,root)=>file===root||file.startsWith(root+path.sep),args={};
for(const arg of process.argv.slice(2)){const m=/^--(prepared|output|deps-root|chromium|baseline)=(.+)$/.exec(arg);assert(m&&!args[m[1]],'QUALITY_PIXEL_ARGUMENT');args[m[1]]=m[2];}
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
aliases.set('/recovery/universal-presentation-v2/incident_baseline_runtime.mjs',args.baseline);
const allowedFiles=new Set(await Promise.all([...aliases.values()].map(file=>realpath(file)))),http=[];
let browser,server,status='FAIL',failure,layouts=[],frames=[],baseline;
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

 const results=[];
 for(const kind of ['baseline','candidate']){
  await page.evaluate(async kind=>{
   window.runtime?.dispose();window.payload=await(await fetch('/runtime.json')).json();window.currentSegment=-1;
   window.createRuntime=(await import('/recovery/universal-presentation-v2/'+(kind==='baseline'?'incident_baseline_runtime.mjs':'presentation_runtime.mjs'))).createPresentationRuntime;
  },kind);
  for(const frame of (kind==='baseline'?[0,1]:[0,1,2,150,151,152])){
   try{
    const row=await page.evaluate(async frame=>{
     const i=window.payload.segments.findIndex(s=>frame>=s.startFrame&&frame<s.endFrame),segment=window.payload.segments[i];
     if(window.currentSegment!==i){window.runtime?.dispose();const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);window.runtime=await window.createRuntime({canvas,...segment});window.currentSegment=i;}
     const diagnostic=window.runtime.drawFrame(frame-segment.startFrame);
     return{frame,featureChangedPixels:diagnostic.featureChangedPixels,glError:diagnostic.glError,
      areaAlpha:diagnostic.features.flatMap(f=>f.sourceAreas??[]).map(a=>a.alpha),png:window.runtime.png().split(',')[1]};
    },frame);
    assert.equal(row.glError,0);const bytes=Buffer.from(row.png,'base64');delete row.png;
    row.pngSHA256=hash(bytes);row.kind=kind;row.status='DRAW_COMPLETE';results.push(row);
    await writeFile(path.join(output,kind+'-'+frame+'.png'),bytes,{flag:'wx'});
   }catch(error){results.push({kind,frame,status:'FAILED',error:String(error.message).slice(0,800)});if(kind==='candidate')throw error;}
  }
 }
 assert(results.some(r=>r.kind==='baseline'&&r.frame===1&&r.status==='FAILED'&&r.error.includes('UP2_ACTUAL_FEATURE_PIXELS_MISSING')),'BASELINE_FRAME1_NOT_REPRODUCED');
 assert(results.some(r=>r.kind==='candidate'&&r.frame===1&&r.status==='DRAW_COMPLETE'&&r.featureChangedPixels===0),'CANDIDATE_FRAME1_EXPECTED_QUANTIZATION_NOT_OBSERVED');
 assert(results.some(r=>r.kind==='candidate'&&r.frame===2&&r.featureChangedPixels>0),'VISIBLE_AREA_GUARD_MUST_STILL_DRAW');
 assert.equal(pageErrors.length,0);status='CPU_FRAME1_REGRESSION_PASS';
 await writeJSON('FRAME1_RESULT.json',{status,results,gpuExecuted:false,fullVideoRendered:false,referenceQuality:'NOT_VALIDATED',scope:'NEW_FRAMES_1_2_151_152_WITH_SEGMENT_INITIALIZATION_ONLY'});
 console.log('FRAME1_RESULT='+JSON.stringify({status,results}));
}catch(error){status='FAIL';console.log('FRAME1_FAILURE='+String(error.stack));throw error;}
finally{await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));}
