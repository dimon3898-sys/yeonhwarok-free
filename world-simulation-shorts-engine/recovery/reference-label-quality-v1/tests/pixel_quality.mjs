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
for(const arg of process.argv.slice(2)){const m=/^--(prepared|output|deps-root|chromium)=(.+)$/.exec(arg);assert(m&&!args[m[1]],'QUALITY_PIXEL_ARGUMENT');args[m[1]]=m[2];}
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
 layouts=await page.evaluate(async()=>{
  window.payload=await(await fetch('/runtime.json')).json();
  const {layoutLabels}=await import('/recovery/universal-presentation-v2/presentation_label_layer.mjs'),
   {projectBounds,presentationReplacesHighlightMarker,presentationBoundarySegments,resolvePresentationMarkerLayout}=await import('/recovery/universal-presentation-v2/presentation_plan.mjs');
  const font=new FontFace('Gate1Bold',`url(${window.payload.segments[0].nativePlan.assets.font.url})`);await font.load();document.fonts.add(font);await document.fonts.ready;
  const c=document.createElement('canvas').getContext('2d'),results=[];
  for(const segment of window.payload.segments){
   let previous=null;const p=segment.presentationPlan.presentation,safe=segment.nativePlan.layout.safe,baseSize=segment.nativePlan.layout.measured?.markerSize??segment.nativePlan.layout.markerSize;
   if(!Number.isFinite(baseSize))throw Error('QUALITY_NATIVE_MARKER_SIZE_REQUIRED');
   for(let frame=0;frame<segment.scene.timing.total_frames;frame++){
    const bounds=segment.presentationPlan.cpuFrameBounds[frame],project=point=>projectBounds(bounds,point),markers=(segment.scene.markers??[]).map(row=>({id:row.id,anchor:row.anchor,scale:1}));
    for(const h of p.highlights)if(frame>=h.startFrame&&frame<h.endFrame){
     const loc=segment.scene.locations.find(x=>x.id===h.locationId),progress=(frame-h.startFrame)/(h.endFrame-h.startFrame-1);markers.push({id:h.id,locationId:h.locationId,anchor:loc.anchor,scale:1+.4*Math.sin(Math.PI*progress),...(presentationReplacesHighlightMarker(p,h,frame)?{qualityPinCandidate:true}:{})});
    }
    const markerRows=markers.map(row=>{const at=project(row.anchor),r=baseSize*row.scale/2+2;return{...row,box:[at[0]-r,at[1]-r,at[0]+r,at[1]+r]};}),
     prepare=protectedBoxes=>layoutLabels({items:p.labels.items,frame,project,width:1080,height:1920,safeArea:safe,protectedBoxes,previousLayout:previous,measureText:(text,font)=>{c.font=font;return c.measureText(text);}}),resolved=resolvePresentationMarkerLayout(markerRows,prepare),layout=resolved.layout??prepare(resolved.markerRows);
    const active=p.labels.items.filter(item=>frame>=item.startFrame&&frame<item.endFrame),unexpected=layout.suppressed.filter(row=>row.reason!=='OUTSIDE_EVENT_TIMING');
    if(unexpected.length||layout.visibleCount!==active.length)throw Error('QUALITY_LABEL_LAYOUT_BLOCKED_'+JSON.stringify({frame:segment.startFrame+frame,unexpected}));
    for(const item of active.filter(item=>item.style==='REFERENCE_V1'&&item.pin==='HERO'))if(!layout.drawn.find(row=>row.id===item.id)?.pinDrawn)throw Error('QUALITY_HERO_PIN_SUPPRESSED_'+item.id);
    const boundaries=presentationBoundarySegments({presentation:p,nativePlan:segment.nativePlan,project});
    results.push({frame:segment.startFrame+frame,segment:segment.sceneId,visibleCount:layout.visibleCount,drawn:layout.drawn,suppressed:unexpected,boundarySegments:boundaries.length});previous=layout;
   }
  }
  window.createRuntime=(await import('/recovery/universal-presentation-v2/presentation_runtime.mjs')).createPresentationRuntime;window.currentSegment=-1;
  return results;
 });
 await writeJSON('LAYOUT_300.json',{status:'PASS',scope:'ACTUAL_FONT_CPU_LAYOUT_WITH_COMPILED_CAMERA_NOT_300_DRAW',frames:layouts});
 const requested=new Set([0,15,60,90,149,150,185,210,270,299]);
 for(const segment of payload.segments)for(const item of segment.presentation.labels.items)for(const delta of [0,4,8,12])if(item.startFrame+delta<item.endFrame)requested.add(segment.startFrame+item.startFrame+delta);
 for(const frame of [...requested].sort((a,b)=>a-b)){
  const result=await page.evaluate(async frame=>{
   const index=window.payload.segments.findIndex(s=>frame>=s.startFrame&&frame<s.endFrame),segment=window.payload.segments[index];
   if(window.currentSegment!==index){window.runtime?.dispose();const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);window.runtime=await window.createRuntime({canvas,...segment});window.currentSegment=index;}
   const diagnostic=window.runtime.drawFrame(frame-segment.startFrame),pixels=window.runtime.readPixels();let nonBlackPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlackPixels++;
   if(frame===90)window.nativeMapOnPixels=window.runtime.readBasePixels().slice();
   return{frame,diagnostic,nonBlackPixels,png:window.runtime.png().split(',')[1]};
  },frame);
  assert(result.nonBlackPixels>1080*1920*.2,'QUALITY_BLACK_FRAME');assert.equal(result.diagnostic.glError,0);
  assert(result.diagnostic.presentationMap?.boundariesEnabled&&result.diagnostic.presentationMap?.glowEnabled,'QUALITY_MAP_OUTPUT_NOT_CONNECTED');
  const bad=result.diagnostic.presentationLabels?.suppressed?.filter(row=>row.reason!=='OUTSIDE_EVENT_TIMING')??[];assert.deepEqual(bad,[],'QUALITY_SAMPLED_LABEL_SUPPRESSION');
  const segment=payload.segments.find(s=>frame>=s.startFrame&&frame<s.endFrame),localFrame=frame-segment.startFrame,
   heroes=segment.presentation.labels.items.filter(item=>item.style==='REFERENCE_V1'&&item.pin==='HERO'&&localFrame>=item.startFrame&&localFrame<item.endFrame);
  for(const item of heroes)assert(result.diagnostic.presentationLabels.drawn.find(row=>row.id===item.id)?.pinDrawn,'QUALITY_SAMPLED_HERO_PIN_SUPPRESSED_'+item.id);
  const bytes=Buffer.from(result.png,'base64');await writeFile(path.join(output,`FRAME_${String(frame).padStart(3,'0')}.png`),bytes,{flag:'wx'});delete result.png;frames.push({...result,pngSHA256:hash(bytes)});
  console.log(JSON.stringify({stage:'QUALITY_CPU_SAMPLE',frame}));
 }
 const countryGeometry=rows=>rows.filter(row=>row.role==='COUNTRY').map(row=>({id:row.id,box:row.box,connector:row.connector,pinDrawn:row.pinDrawn,pinBox:row.pinBox,alpha:row.alpha,fontSize:row.fontSize}));
 assert.deepEqual(countryGeometry(layouts[149].drawn),countryGeometry(layouts[150].drawn),'QUALITY_CPU_LAYOUT_COUNTRY_SEAM_CHANGED');
 assert.deepEqual(countryGeometry(frames.find(row=>row.frame===149).diagnostic.presentationLabels.drawn),countryGeometry(frames.find(row=>row.frame===150).diagnostic.presentationLabels.drawn),'QUALITY_ACTUAL_DRAW_COUNTRY_SEAM_CHANGED');
 baseline=await page.evaluate(async()=>{
  window.runtime?.dispose();const segment=structuredClone(window.payload.segments[0]);delete segment.presentationPlan.presentation.mapStyle;
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);window.runtime=await window.createRuntime({canvas,...segment});
  window.runtime.drawFrame(90);const off=window.runtime.readBasePixels(),on=window.nativeMapOnPixels;let changed=0;
  for(let i=0;i<off.length;i+=4)if(off[i]!==on[i]||off[i+1]!==on[i+1]||off[i+2]!==on[i+2])changed++;
  return{frame:90,changedNativeMapPixels:changed,comparison:'SAME_FRAME_CURRENT_CAMERA_MAP_STYLE_ON_VS_OFF_BEFORE_AREA_AND_LABEL',countryFill:false};
 });
 assert(baseline.changedNativeMapPixels>100,'QUALITY_NATIVE_BOUNDARY_GLOW_PIXELS_MISSING');assert.deepEqual(pageErrors,[],'QUALITY_BROWSER_ERROR');
 assert(http.some(row=>row.path==='/recovery/reference-director-v1/director_events.mjs'&&row.status===200),'QUALITY_DIRECTOR_HTTP_NOT_LOADED');
 assert.equal(layouts.length,300);status='PASS';
}catch(error){failure=String(error.stack??error).slice(0,8000);throw error;}
finally{
 await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));
 await writeJSON('PIXEL_RESULT.json',{status,failure,scope:'FOCUSED_CPU_COMPOSITE_PIXELS_AND_LABEL_LAYOUT',layoutFrames:layouts.length,sampledDrawFrames:frames.length,sampledFrameNumbers:frames.map(x=>x.frame),nativeMapPixelComparison:baseline,softwareOnly:true,gpuExecuted:false,videoRendered:false,referenceQualityApproved:false,limitations:['Sparse frames do not prove temporal video quality','Software rasterization does not verify NVIDIA output','Actual 10-second MP4 quality remains NOT_RUN']});
 await writeJSON('FRAME_EVIDENCE.json',{frames});await writeJSON('HTTP_ASSET_BINDINGS.json',http);
}
