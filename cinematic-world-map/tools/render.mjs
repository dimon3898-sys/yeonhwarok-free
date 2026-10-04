import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {once} from 'node:events';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require('playwright');
const opt=Object.fromEntries(process.argv.slice(2).map(x=>{let [k,v]=x.replace(/^--/,'').split('=');return [k,v??true]}));
const root=path.resolve(import.meta.dirname,'..');const output=path.join(root,'outputs');await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 page.on('pageerror',e=>console.error('PAGE ERROR',e.message));page.on('console',msg=>{if(msg.type()==='error')console.error('WEBGL ERROR',msg.text())});
 await page.goto('http://127.0.0.1:8010/index.html');await page.waitForFunction(()=>window.ready,{timeout:90000});
 const renderer=await page.evaluate(()=>({renderer:window.app.gl.getContext().getParameter(window.app.gl.getContext().RENDERER),width:window.app.w,height:window.app.h}));console.log(JSON.stringify(renderer));
 if(opt.still!==undefined){for(const time of String(opt.still).split(',').map(Number)){await page.evaluate(t=>window.renderFrame(t,2),time);let url=await page.evaluate(()=>window.app.canvas.toDataURL('image/png'));let name=`still_${time.toFixed(2).replace('.','_')}.png`;await writeFile(path.join(output,name),Buffer.from(url.split(',')[1],'base64'));console.log(name)} }
 else{
 const seconds=Number(opt.seconds||20),fps=Number(opt.fps||30),start=Number(opt.start||0),samples=Number(opt.samples||2),name=String(opt.name||'master_cinematic_20s_muted');
 const frames=Math.round(seconds*fps),dest=path.join(output,name+'.mp4');
 const ff=spawn('ffmpeg',['-hide_banner','-loglevel','warning','-y','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-vf','scale=1080:1920:flags=lanczos,setsar=1','-c:v','libx264','-preset','slow','-crf','16','-threads','4','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart','-an',dest],{stdio:['pipe','inherit','inherit']});
 const completion=once(ff,'exit');let stamp=Date.now();for(let i=0;i<frames;i++){const data=await page.evaluate(({t,samples})=>{window.renderFrame(t,samples);return window.app.canvas.toDataURL('image/jpeg',.99).split(',')[1]},{t:start+i/fps,samples});if(!ff.stdin.write(Buffer.from(data,'base64')))await once(ff.stdin,'drain');if(i%15===0||i===frames-1)console.log(`FRAME ${i+1}/${frames}  time=${(start+i/fps).toFixed(2)}  elapsed=${((Date.now()-stamp)/1000).toFixed(1)}s`)}ff.stdin.end();let [code]=await completion;if(code!==0)throw Error(`ffmpeg exit ${code}`);console.log('SAVED '+dest)
 }
}finally{await browser.close()}
