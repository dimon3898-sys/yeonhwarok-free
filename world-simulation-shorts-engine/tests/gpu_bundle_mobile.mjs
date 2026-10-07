// Real local HTTPS transport and actual gcube gateway, Android viewport.
// Browser TLS stays on loopback. The test-only bridge supplies the separately
// verified external HTTPS gcube authority; no gcube or GPU operation.
import fs from 'node:fs';import http from 'node:http';import https from 'node:https';import path from 'node:path';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
let input='';for await(const part of process.stdin)input+=part;
const {port,code,pid,filename,folder,cert,key,pending}=JSON.parse(input),require=createRequire(path.resolve('../cinematic-world-map/package.json')),{chromium}=require('playwright');
const hostname='android-bundle.service.gcube.ai';
const proxy=https.createServer({cert:fs.readFileSync(cert),key:fs.readFileSync(key)},(req,res)=>{
 const headers={...req.headers,host:`${hostname}:24999`,'X-Forwarded-Proto':'http','X-Forwarded-For':'8.8.8.8, 10.0.0.2','X-Envoy-External-Address':'10.0.0.2'};
 if(headers.origin===origin)headers.origin=`https://${hostname}:24999`;
 const upstream=http.request({hostname:'127.0.0.1',port,path:req.url,method:req.method,headers},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res);});upstream.on('error',()=>{res.writeHead(502);res.end();});req.pipe(upstream);
});await new Promise(resolve=>proxy.listen(0,'127.0.0.1',resolve));const origin=`https://127.0.0.1:${proxy.address().port}`;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu']});
try{
 const context=await browser.newContext({viewport:{width:393,height:851},isMobile:true,hasTouch:true,ignoreHTTPSErrors:true,userAgent:'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Mobile Safari/537.36',acceptDownloads:true});
 const page=await context.newPage();await page.goto(origin+'/auth/login');
 const status=await page.evaluate(async code=>{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:code})});return r.status;},code);assert.equal(status,200);
 await page.evaluate(pid=>localStorage.setItem('world-simulation.last-project',pid),pid);await page.goto(origin+'/');
 const link=page.getByRole('link',{name:'진단 ZIP 다운로드',exact:true});
 if(pending){await page.waitForFunction(()=>document.getElementById('progress-panel')?.classList.contains('progress-panel-failed'));assert.equal(await link.count(),0);fs.writeFileSync(path.join(folder,'mobile-page-ready'),'ready');}
 await link.waitFor({state:'visible',timeout:15000});
 assert.ok((await page.locator('#progress-recovery').textContent()).includes('gcube Workload를 중지'));
 const wait=page.waitForEvent('download');await link.click();const download=await wait;
 assert.equal(download.suggestedFilename(),filename);const destination=path.join(folder,filename);await download.saveAs(destination);assert.equal(fs.readFileSync(destination).subarray(0,2).toString(),'PK');
 assert.ok(await page.locator('#output-panel').isVisible());await context.close();process.stdout.write(JSON.stringify({passed:true,viewport:[393,851],Android:'EMULATED',transport:'ACTUAL_LOCAL_HTTPS',authenticated_download:'PASS',failed_screen_button:'PASS',gpu_draw:'NOT_RUN'})+'\n');
}finally{await browser.close();proxy.closeAllConnections();await new Promise(resolve=>proxy.close(resolve));http.globalAgent.destroy();}
