/** New-input actual Chromium font/layout check; no map draw, capture or encoding. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const [root,privateRoot,out,deps]=process.argv.slice(2);
const require=createRequire(path.join(deps,'package.json')),{chromium}=require('playwright');
let browser;
const server=createServer(async(req,res)=>{try{
 const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 assert(req.method==='GET'&&!pathname.includes('..')&&!pathname.includes('\\'));
 if(pathname==='/'){res.setHeader('content-type','text/html');res.end('<!doctype html><meta charset="utf-8">');return;}
 let file;
 if(/^\/prepared-[12]\.json$/.test(pathname))file=path.join(privateRoot,'PREPARED_'+pathname.match(/[12]/)[0]+'.json');
 else{assert(pathname.startsWith('/world-simulation-shorts-engine/')&&/\.(mjs|otf)$/.test(pathname));file=path.join(root,pathname.slice(1));}
 const raw=await fs.readFile(file);res.setHeader('content-type',file.endsWith('.mjs')?'text/javascript':file.endsWith('.otf')?'font/otf':'application/json');res.end(raw);
 }catch{res.writeHead(404);res.end();}});
try{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());await page.goto(origin);
 const result=await page.evaluate(async()=>{
  const prefix='/world-simulation-shorts-engine/recovery/universal-presentation-v2/';
  const {layoutLabels}=await import(prefix+'presentation_label_layer.mjs');
  const {projectBounds,presentationReplacesHighlightMarker,resolvePresentationMarkerLayout}=await import(prefix+'presentation_plan.mjs');
  const font=new FontFace('Gate1Bold','url(/world-simulation-shorts-engine/web/fonts/NotoSansCJKkr-Bold.otf)');await font.load();document.fonts.add(font);await document.fonts.ready;
  const context=document.createElement('canvas').getContext('2d'),clips=[],failures=[];
  for(const part of [1,2]){
   const payload=await(await fetch('/prepared-'+part+'.json')).json(),frames=[];
   for(const segment of payload.segments){
    let previous=null;const p=segment.presentationPlan.presentation,safe=segment.nativePlan.layout.safe,base=segment.nativePlan.layout.measured?.markerSize??segment.nativePlan.layout.markerSize;
    for(let frame=0;frame<segment.scene.timing.total_frames;frame++){
     const bounds=segment.presentationPlan.cpuFrameBounds[frame],project=point=>projectBounds(bounds,point),markers=[];
     if(segment.scene.markers?.length)throw Error('UNHANDLED_NATIVE_MARKERS');
     for(const h of p.highlights)if(frame>=h.startFrame&&frame<h.endFrame){
      const loc=segment.scene.locations.find(x=>x.id===h.locationId),scale=1+.4*Math.sin(Math.PI*(frame-h.startFrame)/(h.endFrame-h.startFrame-1)),at=project(loc.anchor),r=base*scale/2+2;
      markers.push({id:h.id,locationId:h.locationId,anchor:loc.anchor,scale,box:[at[0]-r,at[1]-r,at[0]+r,at[1]+r],...(presentationReplacesHighlightMarker(p,h,frame)?{qualityPinCandidate:true}:{})});
     }
     const prepare=protectedBoxes=>layoutLabels({items:p.labels.items,frame,project,width:1080,height:1920,safeArea:safe,protectedBoxes,previousLayout:previous,measureText:(t,f)=>{context.font=f;return context.measureText(t);}});
     const resolved=resolvePresentationMarkerLayout(markers,prepare),layout=resolved.layout??prepare(resolved.markerRows),active=p.labels.items.filter(x=>frame>=x.startFrame&&frame<x.endFrame);
     const suppressed=layout.suppressed.filter(x=>x.reason!=='OUTSIDE_EVENT_TIMING'),missing=active.filter(x=>x.pin==='HERO'&&!layout.drawn.find(d=>d.id===x.id)?.pinDrawn).map(x=>x.id);
     if(suppressed.length||missing.length||!active.length||layout.visibleCount!==active.length)failures.push({part,frame:segment.startFrame+frame,suppressed,missing});
     frames.push({frame:segment.startFrame+frame,bounds,drawn:layout.drawn});previous=layout;
    }
   }
   clips.push({part,frames});
  }
  function same(a,b){if(typeof a==='number'&&typeof b==='number')return Math.abs(a-b)<1e-6;if(Array.isArray(a)&&Array.isArray(b))return a.length===b.length&&a.every((x,i)=>same(x,b[i]));return a===b;}
  const a=clips[0].frames,b=clips[1].frames,seams=[];
  for(const [name,l,r] of [['part1-scene',a[149],a[150]],['part2-scene',b[149],b[150]],['clip-boundary',a[299],b[0]]]){
   const errors=[];if(!same(l.bounds,r.bounds))errors.push('CAMERA_BOUNDS');
   for(const item of l.drawn){const next=r.drawn.find(x=>x.id===item.id);if(!next)continue;for(const k of ['text','box','pinBox','connector','fontSize','alpha','pinScale'])if(!same(item[k],next[k]))errors.push(item.id+':'+k);}
   seams.push({name,errors,status:errors.length?'FAIL':'PASS'});
  }
  return{status:failures.length||seams.some(x=>x.errors.length)?'FAIL':'PASS_NEW_INPUT_CHROMIUM_LAYOUT_AND_SEAMS',layoutFrames:clips.reduce((n,c)=>n+c.frames.length,0),failures,seams,clips};
 });
 await fs.writeFile(path.join(out,'CHROMIUM_LAYOUT_600.json'),JSON.stringify(result)+'\n',{flag:'wx'});
 const {clips,...summary}=result;await fs.writeFile(path.join(out,'CHROMIUM_LAYOUT_RESULT.json'),JSON.stringify({...summary,mapFramesDrawn:0,gpuStarts:0,oldPASSReruns:0,referenceQualityApproved:false},null,2)+'\n',{flag:'wx'});
 assert(result.status==='PASS_NEW_INPUT_CHROMIUM_LAYOUT_AND_SEAMS',JSON.stringify({failures:result.failures,seams:result.seams}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
