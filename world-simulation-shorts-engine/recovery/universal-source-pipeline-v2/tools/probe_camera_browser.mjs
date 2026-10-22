/** Read-only bounded Camera V5 numeric probe: imports camera code; never draws. */
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {evaluateMinimumContextCameraFrame} from '../../../web/map_infographic_v1/camera_director_v5.mjs';

const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..'),
 modules=path.resolve(root,'web/map_infographic_v1');
const require=createRequire(path.resolve(root,'../cinematic-world-map/package.json'));
const {chromium}=require('playwright');
const args=Object.fromEntries(process.argv.slice(2).map(arg=>{const index=arg.indexOf('=');if(!arg.startsWith('--')||index<0)throw Error('EXPLICIT_PROBE_ARGUMENT_REQUIRED');return[arg.slice(2,index),arg.slice(index+1)];}));
if(!args.package||!args.output||Object.keys(args).some(key=>!['package','output'].includes(key)))throw Error('PROBE_PACKAGE_AND_OUTPUT_REQUIRED');
const document=JSON.parse(await fs.readFile(args.package,'utf8')),
 payload=document.sourcePipeline?.runtimePayload??document;
if(!payload.cameraPlan||!Array.isArray(payload.cameraSchedule)||payload.cameraSchedule.length<2||payload.cameraSchedule.length>240)throw Error('BOUNDED_CAMERA_PACKAGE_REQUIRED');
const cameraPlan=payload.cameraPlan,cameraSchedule=payload.cameraSchedule;
const node=cameraSchedule.map(clock=>{const value=evaluateMinimumContextCameraFrame(cameraPlan,clock.sourceFrame);return{bounds:value.camera.flatBounds,admission:value.admission};});
const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/'){res.writeHead(200,{'content-type':'text/html','cache-control':'no-store'});res.end('<!doctype html><meta charset="utf-8"><title>Camera numeric probe</title>');return;}
  if(url.pathname==='/camera_numeric_contract.mjs'){
   res.writeHead(200,{'content-type':'text/javascript','cache-control':'no-store'});res.end(await fs.readFile(path.resolve(here,'../camera_numeric_contract.mjs')));return;
  }
  if(!/^\/modules\/[a-zA-Z0-9_.-]+\.mjs$/.test(url.pathname))throw Error('READ_ONLY_CAMERA_MODULE_ROUTE');
  const file=path.resolve(modules,url.pathname.slice('/modules/'.length));
  if(path.dirname(await fs.realpath(file))!==await fs.realpath(modules))throw Error('MODULE_PATH_OUTSIDE_NATIVE_ROOT');
  res.writeHead(200,{'content-type':'text/javascript','cache-control':'no-store'});res.end(await fs.readFile(file));
 }catch{res.writeHead(404);res.end('Not found');}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
let browser;
try{
 const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();
 await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
 await page.goto(origin,{waitUntil:'domcontentloaded'});
 const result=await page.evaluate(async({cameraPlan,cameraSchedule})=>{
  const {evaluateMinimumContextCameraFrame}=await import('/modules/camera_director_v5.mjs');
  const {cameraBoundsNumericallyAgree}=await import('/camera_numeric_contract.mjs');
  return cameraSchedule.map(clock=>{const value=evaluateMinimumContextCameraFrame(cameraPlan,clock.sourceFrame);return{bounds:value.camera.flatBounds,admission:value.admission,
   numericAgreement:cameraBoundsNumericallyAgree(value.camera.flatBounds,clock.flatBounds)};});
 },{cameraPlan,cameraSchedule});
 const ordered=value=>{const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,value,false);const bits=view.getBigUint64(0,false);return(bits>>63n)?-(bits&0x7fffffffffffffffn):bits;};
 const ulps=(a,b)=>{let value=ordered(a)-ordered(b);return value<0n?-value:value;};
 const differences=[];let maxPixelDelta=0,maxAbsoluteDelta=0,maxUlps=0n;
 for(let frame=0;frame<cameraSchedule.length;frame++)for(let axis=0;axis<4;axis++){
  const expected=cameraSchedule[frame].flatBounds[axis],nodeValue=node[frame].bounds[axis],browserValue=result[frame].bounds[axis],
   delta=Math.abs(browserValue-expected),span=result[frame].bounds[axis%2+2]-result[frame].bounds[axis%2],
   pixelDelta=delta/span*(axis%2===0?1080:1920),ulpDistance=ulps(expected,browserValue);
  maxPixelDelta=Math.max(maxPixelDelta,pixelDelta);maxAbsoluteDelta=Math.max(maxAbsoluteDelta,delta);if(ulpDistance>maxUlps)maxUlps=ulpDistance;
  if(expected!==browserValue)differences.push({frame,sourceFrame:cameraSchedule[frame].sourceFrame,axis,expected,node:nodeValue,browser:browserValue,delta,pixelDelta,ulps:ulpDistance.toString()});
 }
 const report={schema:'WORLD_ENGINE_NODE_CHROMIUM_CAMERA_NUMERIC_PROBE_V1',kind:'READ_ONLY_CAMERA_EVALUATION_NO_WEBGL_DRAW',
  nodeVersion:process.version,browserVersion:browser.version(),cameraVersion:cameraPlan.directorVersion,frames:cameraSchedule.length,
  nodeMatchesExpected:node.every((row,index)=>JSON.stringify(row.bounds)===JSON.stringify(cameraSchedule[index].flatBounds)),
  browserExactMatch:differences.length===0,differingCoordinates:differences.length,firstDifference:differences[0]??null,
  maxAbsoluteDeltaDegrees:maxAbsoluteDelta,maxCanonicalPixelDelta:maxPixelDelta,maxUlps:maxUlps.toString(),
  admissionsMatch:node.every((row,index)=>JSON.stringify(row.admission)===JSON.stringify(result[index].admission)),
  anyBrowserLocalUsed:result.some(row=>row.admission.localUsed),firstActualAdmission:result[0].admission,
  boundedNumericsAllAccepted:result.every(row=>row.numericAgreement.matches),
  firstBoundedNumericRejection:result.findIndex(row=>!row.numericAgreement.matches),
  differences,nativeMapRendererCreated:false,webglDraws:0,nvidiaVerified:false};
 await fs.writeFile(args.output,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
 process.stdout.write(JSON.stringify({...report,differences:undefined})+'\n');
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
