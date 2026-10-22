/** One-frame CPU/SwiftShader factory contract smoke; not a Studio admission. */
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../../..'),REPO=path.dirname(ENGINE),OWN=path.dirname(HERE);
const require=createRequire(path.join(REPO,'cinematic-world-map/package.json')),{chromium}=require('playwright');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex'),within=(p,r)=>p===r||p.startsWith(r+path.sep);
const args=Object.fromEntries(process.argv.slice(2).map(arg=>{const m=/^--(package|native-inputs|output)=(.+)$/.exec(arg);if(!m)throw Error('SMOKE_ARGUMENT_INVALID');return[m[1],m[2]];}));
if(!args.package||!args['native-inputs']||!args.output)throw Error('SMOKE_EXPLICIT_INPUTS_REQUIRED');
const raw=await fs.readFile(args.package),document=JSON.parse(raw),preparedRaw=await fs.readFile(args['native-inputs']),prepared=JSON.parse(preparedRaw);
if(document.sourcePipeline?.mode!=='SYNTHETIC_TEST'||prepared.evidence?.syntheticOnly!==true)throw Error('SMOKE_NONHISTORICAL_SCOPE_REQUIRED');
// This is an explicitly recorded diagnostic substitution of newly prepared
// data into the failed test's unchanged authored synthetic source fields.
const inputs={...document.sourcePipeline.runtimePayload,nativePlan:prepared.nativePlan,cameraPlan:prepared.cameraPlan,cameraSchedule:prepared.cameraSchedule};
let browser,stage='LOOPBACK_SERVER';
const report={schema:'WORLD_ENGINE_NATIVE_FACTORY_SMOKE_V1',status:'IN_PROGRESS',classification:'SYNTHETIC_TEST_DIAGNOSTIC_NOT_STUDIO_SUCCESS',
 inputPackageSHA256:hash(raw),newNativeInputsSHA256:hash(preparedRaw),nativeProfileVersion:inputs.nativePlan.layout.measured.version,
 noHistoricalRendering:true,g1Rendered:false,fullClipRendered:false,nvidiaVerified:false,renderedFrames:0};
const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost'),p=decodeURIComponent(url.pathname);
  if(url.search||p.includes('..')||p.includes('\\'))throw Error('SMOKE_READ_ONLY_TARGET');
  let body,type='application/octet-stream';
  if(p==='/'){body=Buffer.from('<!doctype html><meta charset="utf-8"><canvas id="map" width="1080" height="1920"></canvas>');type='text/html';}
  else if(p==='/input.json'){body=Buffer.from(JSON.stringify(inputs));type='application/json';}
  else if(['/native_runtime.mjs','/camera_numeric_contract.mjs','/source_geometry_contract.mjs'].includes(p)){body=await fs.readFile(path.join(OWN,p.slice(1)));type='text/javascript';}
  else{
   const mounts=[['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]];
   const file=p==='/three.js'?path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js'):null,
    mount=mounts.find(([prefix])=>p.startsWith(prefix));
   if(!file&&!mount)throw Error('SMOKE_NOT_FOUND');
   const candidate=file??path.join(mount[1],p.slice(mount[0].length)),root=file?ENGINE:mount[1],real=await fs.realpath(candidate);
   if(real!==path.resolve(candidate)||!within(real,root))throw Error('SMOKE_PATH_OUTSIDE_ASSET_ROOT');
   body=await fs.readFile(real);type=/\.(js|mjs)$/.test(p)?'text/javascript':/\.png$/.test(p)?'image/png':/\.jpg$/.test(p)?'image/jpeg':/\.otf$/.test(p)?'font/otf':type;
  }
  res.writeHead(200,{'content-type':type,'cache-control':'no-store'});res.end(body);
 }catch{res.writeHead(404);res.end();}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
try{
 const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
 await page.goto(origin);stage='ACTUAL_NATIVE_FACTORY_INIT';
 const result=await page.evaluate(async()=>{
  const input=await(await fetch('/input.json')).json(),{createUniversalSourceRuntime}=await import('/native_runtime.mjs'),
   runtime=await createUniversalSourceRuntime({canvas:document.getElementById('map'),...input});
  const evidence=runtime.evidence,diagnostic=runtime.drawFrame(0),pixels=runtime.readPixels();
  let nonBlack=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlack++;
  const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',pixels))].map(v=>v.toString(16).padStart(2,'0')).join('');
  runtime.dispose();return{evidence,diagnostic,rawPixelSHA256:sha,nonBlackPixels:nonBlack};
 });
 report.renderedFrames=1;report.result=result;report.browserErrors=errors;report.status=errors.length?'FAILED':'ONE_FRAME_SOFTWARE_SMOKE_PASS';
 if(!result.evidence.backend.includes('SwiftShader'))throw Error('SMOKE_SOFTWARE_BACKEND_REQUIRED');
 if(result.diagnostic.glError!==0||result.nonBlackPixels===0||errors.length)throw Error('SMOKE_FRAME_CONTRACT_FAILURE');
}catch(error){report.status='FAILED';report.failure={stage,message:String(error.message).slice(0,3500)};process.exitCode=1;}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve));await fs.writeFile(args.output,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});}
process.stdout.write(JSON.stringify({status:report.status,renderedFrames:report.renderedFrames,failure:report.failure,output:args.output})+'\n');
