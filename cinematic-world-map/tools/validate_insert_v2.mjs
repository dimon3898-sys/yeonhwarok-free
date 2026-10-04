// Integration check only: test pixels never enter a delivered master.
import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();await page.goto('http://127.0.0.1:8020/index_v2.html');await page.waitForFunction(()=>window.ready,{timeout:90000});
 const result=await page.evaluate(()=>{
  const app=window.app,clip=document.createElement('canvas');clip.width=64;clip.height=64;let c=clip.getContext('2d');c.fillStyle='#205a84';c.fillRect(0,0,64,64);let localTimes=[];
  app.scenes.insert_cinematic_clip({start:2,end:3,source:local=>{localTimes.push(local);return clip}});
  window.renderFrame(2.5,1);let p=Array.from(app.ctx.getImageData(1080,1920,1,1).data),before=app.cam.camera.position.clone();
  window.renderFrame(3,1);let after=Array.from(app.ctx.getImageData(1080,1920,1,1).data);
  return {localTimes,insertPixel:p,mapReturnPixel:after,endExclusive:!app.scenes.active(3),cameraContinues:before.distanceTo(app.cam.camera.position)>1e-7,scope:'Prepared frame callback compositor; no external I2V generation/decoder and no test pixels in master'};
 });
 if(JSON.stringify(result.insertPixel)!==JSON.stringify([32,90,132,255])||!result.endExclusive||!result.cameraContinues||result.localTimes.length!==1||result.localTimes[0]!==.5)throw Error('Cinematic insertion integration failed');
 await writeFile(new URL('../outputs/v2_insertion_validation.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close()}
