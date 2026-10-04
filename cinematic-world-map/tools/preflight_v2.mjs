// All 600 scene poses: actual 3D aircraft bounds against real font metrics.
// GPU frames are validated separately; no mock output is used in the film.
import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 await page.goto('http://127.0.0.1:8020/index_v2.html');await page.waitForFunction(()=>window.ready,{timeout:90000});
 const report=await page.evaluate(()=>{
  const app=window.app,real=app.ctx,noop=()=>{},fakeGradient={addColorStop:noop};
  const drawing=new Set(['fillText','stroke','fillRect','beginPath','moveTo','lineTo','drawImage','clearRect']);
  app.ctx=new Proxy(real,{get(o,k){if(drawing.has(k))return noop;if(k==='createLinearGradient'||k==='createRadialGradient')return ()=>fakeGradient;const v=Reflect.get(o,k,o);return typeof v==='function'?v.bind(o):v},set(o,k,v){if(k==='fillStyle'&&v===fakeGradient)return true;return Reflect.set(o,k,v,o)}});
  let overlaps=[],clipped=[],offscreen=[],finite=true;
  for(let i=0;i<600;i++){const t=i/30;app.cam.update(t);app.map.update(app.camera,t);app.highlight.update(t);app.routes.update(t);app.entities.update(t,app.camera);app.effects.update(t);app.network.update(t);app.scene.updateMatrixWorld(true);app.ctx.globalAlpha=1;app.overlay(t);const a=app.audit(t);
   if(a.aircraftLabelOverlaps.length)overlaps.push({t,texts:a.aircraftLabelOverlaps});if(a.textClipped.length)clipped.push({t,texts:a.textClipped});
   if(a.planeVisible&&(a.aircraftBounds.left<100||a.aircraftBounds.right>2060||a.aircraftBounds.top<250||a.aircraftBounds.bottom>2820))offscreen.push({t,bounds:a.aircraftBounds});
   finite=finite&&[...a.camera,...a.cameraQuaternion,...a.planePosition].every(Number.isFinite);
  }
  app.ctx=real;return {poses:600,finite,aircraftLabelOverlaps:overlaps,textClipping:clipped,aircraftOutsideSafeArea:offscreen,scope:'Scene geometry and font preflight; actual encoded video and GPU frames require separate checks'};
 });
 await writeFile(path.join(root,'outputs','v2_preflight.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 if(!report.finite||report.aircraftLabelOverlaps.length||report.textClipping.length||report.aircraftOutsideSafeArea.length)throw Error('Scene clearance preflight failed');
}finally{await browser.close()}
