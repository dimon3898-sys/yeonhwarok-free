import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import path from 'node:path';

const require=createRequire(import.meta.url), {chromium}=require('playwright');
const opt=Object.fromEntries(process.argv.slice(2).map(x=>{const [k,v]=x.replace(/^--/,'').split('=');return [k,v??true]}));
const root=path.resolve(import.meta.dirname,'..'), output=path.join(root,'outputs');
await mkdir(output,{recursive:true});
const sourceFiles=['src/aircraft_v3.js','src/core_v1_preserved.js','src/engine_v3.js','src/renderer_v3.js','index_v3.html','tools/render_v3.mjs','assets/v3/fonts/OpenSans-Light.ttf','assets/v3/earth/earth-day-8k.jpg','assets/v3/earth/earth-night-8k.jpg','assets/v3/earth/earth-clouds-8k.jpg','assets/gis/earth-topology.png'];
const sourceHashes={};
for(const file of sourceFiles)sourceHashes[file]=createHash('sha256').update(await readFile(path.join(root,file))).digest('hex');
let ff,watchdog;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
try {
  const page=await browser.newPage({viewport:{width:1080,height:1920}}), errors=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE_ERROR',e.message)});
  page.on('response',r=>{if(r.status()>=400)errors.push(r.url()+' '+r.status())});
  page.on('console',m=>{if(m.type()==='error'){errors.push(m.text());console.error('CONSOLE_ERROR',m.text())}});
  await page.goto(`http://127.0.0.1:8030/index_v3.html?width=${opt.width||2160}`);
  await page.waitForFunction(()=>window.ready,{timeout:90000});
  if(errors.length)throw Error(JSON.stringify(errors));
  const samples=Number(opt.samples||1);
  if(opt.still!==undefined) {
    for(const t of String(opt.still).split(',').map(Number)) {
      const name=`${opt.prefix||'v3_gl_probe_'}${t.toFixed(2).replace('.','_')}`, dest=path.join(output,name+'.png');
      if(existsSync(dest))throw Error('Refusing existing '+dest);
      const stamp=Date.now();
      const result=await page.evaluate(({t,s})=>{window.renderFrame(t,s);return {image:window.app.canvas.toDataURL('image/png').split(',')[1],audit:window.app.audit(t)}},{t,s:samples});
      if(errors.length||result.audit.webglError||result.audit.textClipped.length)throw Error('Frame audit '+JSON.stringify({errors,audit:result.audit}));
      await writeFile(dest,Buffer.from(result.image,'base64'),{flag:'wx'});
      await writeFile(path.join(output,name+'.json'),JSON.stringify({...result.audit,samples,sourceHashes,elapsed_seconds:(Date.now()-stamp)/1000},null,2),{flag:'wx'});
      console.log(name+' '+((Date.now()-stamp)/1000).toFixed(2)+'s');
    }
  } else {
    const name=String(opt.name||'master_cinematic_20s_v3_muted'),dest=path.join(output,name+'.mp4');
    if(existsSync(dest))throw Error('Refusing existing '+dest);
    const fps=30,start=Number(opt.start||0),frames=Math.round(Number(opt.seconds||20)*fps),audits=[],stamp=Date.now();
    let lastProgress=stamp;
    ff=spawn('ffmpeg',['-hide_banner','-loglevel','warning','-n','-f','image2pipe','-vcodec','mjpeg','-framerate','30','-i','pipe:0','-vf','scale=1080:1920:flags=lanczos:in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,setsar=1,format=yuv420p','-c:v','libx264','-preset','slow','-crf','15','-threads','4','-pix_fmt','yuv420p','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-bsf:v','h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1','-movflags','+faststart','-an',dest],{stdio:['pipe','inherit','inherit']});
    const done=once(ff,'exit');
    watchdog=setInterval(()=>{if(Date.now()-lastProgress>120000){console.error('WATCHDOG: no completed frame for 120s; checkpoint and partial movie preserved');void browser.close();ff.kill('SIGTERM');clearInterval(watchdog)}},15000);
    for(let i=0;i<frames;i++) {
      const t=start+i/fps;
      const result=await page.evaluate(({t,s})=>{window.renderFrame(t,s);return {image:window.app.canvas.toDataURL('image/jpeg',.99).split(',')[1],audit:window.app.audit(t)}},{t,s:samples});
      if(errors.length||result.audit.webglError||result.audit.textClipped.length)throw Error('Frame audit '+JSON.stringify({errors,audit:result.audit}));
      audits.push({...result.audit,samples});
      if(!ff.stdin.write(Buffer.from(result.image,'base64')))await once(ff.stdin,'drain');
      lastProgress=Date.now();
      if(i%15===0||i===frames-1) {
        const checkpoint={completedFrames:i+1,requestedFrames:frames,nextStart:start+(i+1)/fps,elapsedSeconds:(lastProgress-stamp)/1000,sourceHashes,partialVideo:dest,complete:false};
        await writeFile(path.join(output,name+'_checkpoint.json'),JSON.stringify(checkpoint,null,2));
        console.log(`FRAME ${i+1}/${frames} time=${t.toFixed(2)} elapsed=${checkpoint.elapsedSeconds.toFixed(1)}s`);
      }
    }
    ff.stdin.end();const [code]=await done;clearInterval(watchdog);watchdog=null;
    if(code!==0)throw Error('FFmpeg '+code);
    await writeFile(path.join(output,name+'_scene_audit.json'),JSON.stringify(audits,null,2),{flag:'wx'});
    const manifest={sourceHashes,start,seconds:frames/fps,fps,frames,internalResolution:[Number(opt.width||2160),Math.round(Number(opt.width||2160)*16/9)],outputResolution:[1080,1920],motionIntegrationTaps:7,temporalSceneSamples:samples,complete:true,elapsedSeconds:(Date.now()-stamp)/1000};
    await writeFile(path.join(output,name+'_source_manifest.json'),JSON.stringify(manifest,null,2),{flag:'wx'});
    await writeFile(path.join(output,name+'_checkpoint.json'),JSON.stringify({...manifest,completedFrames:frames,nextStart:start+frames/fps,partialVideo:dest},null,2));
    console.log('SAVED '+dest);
  }
} finally {
  if(watchdog)clearInterval(watchdog);
  if(ff&&ff.exitCode===null){ff.stdin.destroy();ff.kill('SIGTERM')}
  await browser.close();
}
