/** Native renderer still inspection; creates no MP4 and overwrites no evidence. */
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {chromium}=createRequire(path.resolve(root,'../cinematic-world-map/package.json'))('playwright');
const args={};for(let i=2;i<process.argv.length;i+=2)args[process.argv[i].slice(2)]=process.argv[i+1];
if(!args.plan||!args.output)throw Error('Required --plan FILE --output NEW_DIR');
const out=path.resolve(args.output);if(existsSync(out))throw Error('Evidence directory already exists');
await mkdir(out,{recursive:true});
const plan=JSON.parse(await readFile(args.plan,'utf8'));
const times=String(args.times||'0.5,1.9,2.4,4.5,7.5,10.8,11.2,11.8,11.9666666667,12,12.1,12.4,12.7,14.9').split(',').map(Number);
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
const records=[];const started=Date.now();
const sourceNames=['flat_polish_renderer.js','earth_polish_adapter.js','geographic_polish_transition.js','flat_renderer.js','flat_semantics.js','earth_adapter.js'];
if(plan.scenes.some(scene=>scene.visual_polish?.entity_separation==='v1'))sourceNames.push('flat_entity_separation_polish.js');
const sourceHashes={};for(const name of sourceNames)sourceHashes[name]=createHash('sha256').update(await readFile(path.join(root,'web',name))).digest('hex');
try {
 for(const scene of plan.scenes){
  const selected=times.filter(t=>t>=scene.start_time&&t<scene.start_time+scene.duration);if(!selected.length)continue;
  const page=await browser.newPage({viewport:{width:1080,height:1920}}),errors=[];
  page.setDefaultTimeout(120000);
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});
  await page.addInitScript(config=>{window.SCENE_CONFIG=config;},{plan,scene});
  const mode=scene.render_mode==='FLAT_MAP_PREMIUM'?(scene.visual_polish?.entity_separation==='v1'?'flat_separation':'flat'):'earth';
  await page.goto(`${args.base||'http://127.0.0.1:8092'}/render_${mode}_polish.html?width=${args.width||2160}`,{timeout:120000});
  await page.waitForFunction(()=>window.ready||window.renderError,null,{timeout:120000});
  const error=await page.evaluate(()=>window.renderError);if(error||errors.length)throw Error(JSON.stringify({error,errors}));
  if(args['layout-scene']===scene.scene_id){
   const layout=await page.evaluate(()=>{
    const records=[];
    for(let i=0;i<Math.round(window.app.duration*30);i++){
     const time=i/30,frame=window.app.prepareFrame(time);
     records.push({time,labels:frame.labels.filter(l=>l.polishCity).map(l=>({text:l.text,x:l.x,y:l.y,width:l.width,height:l.height,anchor:l.anchor,opacity:l.opacity,avoidance:l.aircraftAvoidance})),entitySeparation:window.app.entitySeparationFrame||null});
    }
    return {scope:'Exact native font metrics and actual prepared 3D model bounds, without drawing each frame',records};
   });
   await writeFile(path.join(out,`${scene.scene_id}_LAYOUT_SCAN.json`),JSON.stringify(layout,null,2),{flag:'wx'});
  }
  for(const time of selected){
   const local=time-scene.start_time;
   const record=await page.evaluate(t=>{window.renderFrame(t,1);return {png:window.app.canvas.toDataURL('image/png').split(',')[1],audit:window.app.audit(t)};},local);
   const file=`frame_${String(Math.round(time*30)).padStart(4,'0')}.png`;
   await writeFile(path.join(out,file),Buffer.from(record.png,'base64'),{flag:'wx'});
   const {png,...audit}=record;records.push({global_time:time,scene_id:scene.scene_id,file,...audit});
   console.log(JSON.stringify({scene:scene.scene_id,time,file,webglError:record.audit.webglError,textClipped:record.audit.textClipped,entityClipped:record.audit.entityClipped}));
  }
  await page.close();
 }
 const sourceUnchanged={};for(const name of sourceNames)sourceUnchanged[name]=sourceHashes[name]===createHash('sha256').update(await readFile(path.join(root,'web',name))).digest('hex');
 await writeFile(path.join(out,'STILL_AUDITS.json'),JSON.stringify({elapsedSeconds:(Date.now()-started)/1000,sourceHashes,sourceUnchanged,records},null,2),{flag:'wx'});
 if(Object.values(sourceUnchanged).some(v=>!v))throw Error('Source changed during still inspection; evidence is preserved but needs a fresh capture');
}finally{await browser.close();}
