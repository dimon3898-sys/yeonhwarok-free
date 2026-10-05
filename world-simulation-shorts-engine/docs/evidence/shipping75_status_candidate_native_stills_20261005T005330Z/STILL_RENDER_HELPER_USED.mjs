import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root='/workspace/yeonhwarok-free/world-simulation-shorts-engine';
const folder=process.argv[2];if(!folder)throw Error('New proof folder required');
await fs.mkdir(folder,{recursive:false});
const inputPath=path.join(root,'docs/evidence/status_label_readability_20261005T004325040574Z/NATURAL_COMBINED_LABEL_PROPOSAL.json');
const inputBytes=await fs.readFile(inputPath),proposal=JSON.parse(inputBytes),plan=proposal.plan;
if(!plan||!plan.gate.passed)throw Error('Proposal gate must pass');
const require=createRequire('/workspace/yeonhwarok-free/cinematic-world-map/package.json');
const {chromium}=require('playwright');const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
const items=[],errors=[];const started=Date.now();
try{
 for(const [sid,time] of [['S004',6.2],['S005',1.8],['S005',2.9]]){
  const scene=plan.scenes.find(s=>s.scene_id===sid);if(!scene)throw Error('Scene missing');
  const original=JSON.parse(await fs.readFile(path.join(root,'tests/fixtures/shipping75_v002_label_readability_original.json'),'utf8')).scenes.find(s=>s.scene_id===sid);
  const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
  const withoutLabels=v=>{const x=structuredClone(v);delete x.labels;return JSON.stringify(sorted(x));};
  if(withoutLabels(scene)!==withoutLabels(original))throw Error('Unintended non-label Scene difference');
  const page=await browser.newPage({viewport:{width:1080,height:1920}});page.on('pageerror',e=>errors.push(String(e)));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});
  await page.addInitScript(input=>{window.SCENE_CONFIG=input;},{scene,plan});
  await page.goto('http://127.0.0.1:8090/render.html?width=2160',{timeout:120000});
  await page.waitForFunction(()=>window.ready||window.renderError,{timeout:120000});
  const initError=await page.evaluate(()=>window.renderError||null);if(initError||errors.length)throw Error(JSON.stringify({initError,errors}));
  const result=await page.evaluate(t=>{window.renderFrame(t,1);return {image:window.app.canvas.toDataURL('image/png').split(',')[1],audit:window.app.audit(t),width:window.app.w,height:window.app.h};},time);
  if(result.width!==2160||result.height!==3840||result.audit.webglError||result.audit.textClipped.length||result.audit.entityClipped.length||result.audit.missingTextures.length||!result.audit.fontReady)throw Error(JSON.stringify(result.audit));
  const stem=sid+'_'+time.toFixed(2).replace('.','_'),native=path.join(folder,stem+'_2160.png');
  await fs.writeFile(native,Buffer.from(result.image,'base64'),{flag:'wx'});
  for(const width of [1080,375]){const output=path.join(folder,stem+'_'+width+'.png');const r=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-n','-i',native,'-vf',`scale=${width}:${Math.round(width*16/9)}:flags=lanczos`,'-frames:v','1',output],{encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);}
  await fs.writeFile(path.join(folder,stem+'.audit.json'),JSON.stringify(result.audit,null,2),{flag:'wx'});
  items.push({scene_id:sid,local_time:time,global_time:scene.start_time+time,native:[2160,3840],output:[1080,1920],mobile:[375,667],labels:scene.labels,geographic_camera_and_route_unchanged:true,elapsed_seconds:(Date.now()-started)/1000});
  console.log(JSON.stringify({stage:'candidate_native_still_complete',scene_id:sid,local_time:time,folder}));
  await page.close();
 }
 const report={at:new Date().toISOString(),proposal_path:inputPath,proposal_sha256:createHash('sha256').update(inputBytes).digest('hex'),source:'Frozen actual MASTER_V3 Scene renderer with supplied, unapproved internal candidate Scene JSON; isolated still validation only',not_production_render_or_approval:true,existing_project_not_modified:true,temporal_scene_samples:1,elapsed_seconds:(Date.now()-started)/1000,items,errors};
 await fs.writeFile(path.join(folder,'REPORT.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify({stage:'candidate_still_validation_complete',folder,elapsed_seconds:report.elapsed_seconds}));
}finally{await browser.close();}
