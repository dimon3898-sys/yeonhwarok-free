/** Bounded native WebGL still/preflight test. No MP4 or FFmpeg is invoked. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {chromium}=createRequire(path.resolve(root,'../cinematic-world-map/package.json'))('playwright');
const args={};for(let i=2;i<process.argv.length;i+=2)args[process.argv[i].slice(2)]=process.argv[i+1];
if(!args.plan||!args.output)throw Error('Required --plan FILE --output NEW_DIR [--scene S003]');
const out=path.resolve(args.output);if(existsSync(out))throw Error('Refusing existing evidence directory');
await mkdir(out,{recursive:true});
const plan=JSON.parse(await readFile(args.plan,'utf8')),selected=plan.scenes.filter(scene=>scene.rhythm_visual?.version==='v1'&&(!args.scene||scene.scene_id===args.scene));
if(!selected.length)throw Error('No opted-in Flat rhythm Scene');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
const results=[],started=Date.now();
const sourceNames=['rhythm_visual_adapter.js','render_rhythm_flat.html','production_visual_adapter.js','flat_renderer.js','flat_semantics.js','flat_polish_renderer.js','flat_entity_separation_polish.js','geographic_polish_transition.js','earth_polish_adapter.js'];
const sourceHashes={};for(const name of sourceNames)sourceHashes[name]=createHash('sha256').update(await readFile(path.join(root,'web',name))).digest('hex');
try{
 for(const scene of selected){
  const errors=[],page=await browser.newPage({viewport:{width:1080,height:1920}});
  page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.status()>=400)errors.push(`${response.status()} ${response.url()}`);});
  await page.addInitScript(config=>{window.SCENE_CONFIG=config;},{plan,scene});
  await page.goto(`${args.base||'http://127.0.0.1:8094'}/render_rhythm_flat.html?width=${args.width||2160}`,{timeout:120000});
  await page.waitForFunction(()=>window.ready||window.renderError,null,{timeout:120000});
  const initError=await page.evaluate(()=>window.renderError||null);assert.equal(initError,null);assert.deepEqual(errors,[]);
  const numeric=await page.evaluate(()=>window.app.numericPreflight(30));
  assert.equal(numeric.finite,true);assert.ok(numeric.maxCameraAngleDegreesPerFrame<=2.5);
  const at=scene.visual_events.find(event=>event.kind==='route_blocked')?.time||Math.min(scene.duration-.1,.9);
  const times=[Math.max(0,at-.1),at,scene.duration-1/30],audits=[];
  for(const [index,time] of times.entries()){
   const result=await page.evaluate(t=>{window.renderFrame(t,1);return {audit:window.app.audit(t),png:window.app.canvas.toDataURL('image/png').split(',')[1]};},time);
   assert.equal(result.audit.rhythmVisual.version,'v1');assert.equal(result.audit.rhythmVisual.sourceSceneTime,time);assert.equal(result.audit.rhythmVisual.globalTimewarp,false);
   assert.equal(result.audit.webglError,0);assert.deepEqual(result.audit.textClipped,[]);assert.deepEqual(result.audit.entityClipped,[]);assert.deepEqual(result.audit.missingTextures,[]);assert.equal(result.audit.fontReady,true);
   assert.ok(result.audit.entitySeparation.pairs.every(pair=>pair.minimumAlpha<=.015||!pair.actualProjectedBoxesOverlap));
   await writeFile(path.join(out,`${scene.scene_id}_${index}.png`),Buffer.from(result.png,'base64'),{flag:'wx'});audits.push(result.audit);
  }
  assert.deepEqual(errors,[]);results.push({scene_id:scene.scene_id,numeric:{...numeric,records:undefined},audits});await page.close();
 }
 const sourceUnchanged={};for(const name of sourceNames)sourceUnchanged[name]=sourceHashes[name]===createHash('sha256').update(await readFile(path.join(root,'web',name))).digest('hex');
 assert.ok(Object.values(sourceUnchanged).every(Boolean),'Source changed during native test');
 const result={passed:true,scenes:results.length,actualStills:results.reduce((sum,scene)=>sum+scene.audits.length,0),elapsedSeconds:(Date.now()-started)/1000,sourceHashes,sourceUnchanged,
  scope:'Actual native WebGL initialization, shared numeric camera gate, three drawn stills per selected scene; no MP4, full-video playback or audio claim',results};
 await writeFile(path.join(out,'NATIVE_RESULT.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify({...result,results:undefined}));
}finally{await browser.close();}
