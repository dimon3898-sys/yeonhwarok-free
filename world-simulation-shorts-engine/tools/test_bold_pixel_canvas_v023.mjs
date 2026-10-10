/** Actual CPU Canvas detector tests, not production/GPU visual acceptance. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=path.resolve('.'),require=createRequire(path.resolve('../cinematic-world-map/package.json')),{chromium}=require('playwright');
const server=http.createServer((req,res)=>{if(req.url==='/metrics.mjs'){res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync(path.join(root,'tools/bold_pixel_metrics_v023.mjs')));}else{res.setHeader('Content-Type','text/html');res.end('<meta charset="utf-8"><canvas id="c" width="1080" height="1920"></canvas>');}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
try{
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu','--disable-gpu-compositing']});
 const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}/`);
 const result=await page.evaluate(async()=>{
  const {boundaryPixelMetrics,containmentPixelMetrics,regionPixelMetrics,imageDifference}=await import('/metrics.mjs'),canvas=document.getElementById('c'),ctx=canvas.getContext('2d',{willReadFrequently:true}),w=canvas.width,h=canvas.height,checks=[];
  const check=(id,passed,details={})=>{if(!passed)throw Error(id);checks.push({id,passed,...details});};
  const rgba=()=>ctx.getImageData(0,0,w,h).data;
  for(const width of [2,4,6,8,10]){
   ctx.clearRect(0,0,w,h);ctx.strokeStyle='#f8f8ff';ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(150,700.5);ctx.lineTo(900,700.5);ctx.stroke();
   const measured=boundaryPixelMetrics(rgba(),w,h,[[{x:150,y:700.5},{x:900,y:700.5}]]);
   check('ACTUAL_CANVAS_WIDTH_'+width,Math.abs(measured.width_px_median-width)<.1,{measured});
  }
  // Dark contrast edge must not masquerade as the bright 8px core.
  ctx.clearRect(0,0,w,h);ctx.strokeStyle='#071322';ctx.lineWidth=14;ctx.beginPath();ctx.moveTo(150,900.5);ctx.lineTo(900,900.5);ctx.stroke();ctx.strokeStyle='#f8f8ff';ctx.lineWidth=8;ctx.stroke();
  const core=boundaryPixelMetrics(rgba(),w,h,[[{x:150,y:900.5},{x:900,y:900.5}]],{brightCore:true});
  check('BRIGHT_CORE_EXCLUDES_DARK_EDGE',core.width_px_median>=7.9&&core.width_px_median<8.2,{measured:core});
  // Texture detector uses actual composited pixels with an imageData source.
  const texture=new ImageData(w,h);for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*4,v=70+(x*3+y*2)%110;texture.data.set([v,v+10,v+20,255],i);}ctx.putImageData(texture,0,0);const before=rgba();
  const maskCanvas=document.createElement('canvas');maskCanvas.width=w;maskCanvas.height=h;const maskctx=maskCanvas.getContext('2d');maskctx.fillStyle='#fff';maskctx.fillRect(160,300,760,1100);const mask=maskctx.getImageData(0,0,w,h).data;
  ctx.fillStyle='rgba(190,40,160,.50)';ctx.fillRect(160,300,760,1100);const composite=regionPixelMetrics(before,rgba(),mask,w,h);
  check('ACTUAL_ALPHA_FILL_KEEPS_TERRAIN',composite.changed_fraction>.99&&composite.terrain_edge_retention>.49&&composite.terrain_edge_retention<.52&&composite.terrain_edge_correlation>.99,{measured:composite});
  ctx.putImageData(texture,0,0);ctx.fillStyle='#c826a0';ctx.fillRect(160,300,760,1100);const opaque=regionPixelMetrics(before,rgba(),mask,w,h);
  check('ACTUAL_OPAQUE_FILL_ERASES_TERRAIN',opaque.terrain_edge_retention===0,{measured:opaque});
  const reference=mask.slice();ctx.clearRect(0,0,w,h);ctx.fillStyle='#fff';ctx.fillRect(160,300,760,1100);ctx.fillRect(20,20,4,4);const leaking=containmentPixelMetrics(rgba(),reference,w,h);
  check('ACTUAL_OCEAN_LEAK_DETECTED',leaking.outside_native_fill_pixels===16,{measured:leaking});
  ctx.putImageData(texture,0,0);const copy=rgba();check('OFF_EXACT_CHANNELS',imageDifference(texture.data,copy,w,h).identical);
  return {passed:true,checks,GPU:'NOT_RUN',production_frame_render:'NOT_RUN',visual_quality_acceptance:'NOT_RUN',scope:'Actual Chromium CPU Canvas2D 1080x1920 pixels validating the QC detector; authored geometry/production helper is tested by separate preview harness.'};
 });
 assert(result.passed);console.log(JSON.stringify(result));
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
