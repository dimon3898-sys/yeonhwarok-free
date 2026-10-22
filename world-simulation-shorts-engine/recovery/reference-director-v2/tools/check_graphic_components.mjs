/** Software GPU graphics COMPONENT test on a solid clear color, never a map/video. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {fixture} from '../fixtures/component_program.mjs';
const HERE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),ENGINE=path.resolve(HERE,'../..');
const hash=b=>createHash('sha256').update(b).digest('hex'),attempt=process.argv[2]??'attempt-01';
if(!/^[a-z0-9-]+$/.test(attempt))throw Error('GRAPHIC_COMPONENT_ATTEMPT');
const output=path.join('/workspace/reference-director-v2-private-20261022','graphic-components-'+attempt);
await fs.mkdir(output,{recursive:true,mode:0o700});
const fontPath=path.join(ENGINE,'web/fonts/NotoSansCJKkr-Bold.otf'),font=await fs.readFile(fontPath);
const aliases=new Map([['/three.js',path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js')],['/web/map_infographic_v1/graphic_layout.mjs',path.join(ENGINE,'recovery/g2-final-recovery-v1/layout_extension.mjs')],['/web/map_infographic_v1/graphic_layout_legacy.mjs',path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs')]]);
const requests=[];
const service=createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://127.0.0.1');if(req.method!=='GET'||u.search||u.pathname.includes('..')||u.pathname.includes('\\'))throw Error('LOCAL_READ_ONLY');
 if(u.pathname==='/'){res.writeHead(200,{'content-type':'text/html'});return res.end('<!doctype html><style>body{margin:0;font-family:sans-serif}h3{margin:0;padding:12px;background:white}</style><h3>UNIT GPU GRAPHIC DRAW — SOLID BACKGROUND, NOT MAP / STUDIO OUTPUT</h3><canvas id="unit" width="1080" height="1920"></canvas>');}
 let file=aliases.get(u.pathname);
 if(!file&&['/web/','/recovery/'].some(prefix=>u.pathname.startsWith(prefix)))file=path.join(ENGINE,u.pathname.slice(1));
 if(!file)throw Error('NOT_FOUND');const raw=await fs.readFile(file),type=/\.(mjs|js)$/.test(file)?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.otf')?'font/otf':'application/octet-stream';
 requests.push({path:u.pathname,sha256:hash(raw),bytes:raw.length});res.writeHead(200,{'content-type':type,'cache-control':'no-store'});res.end(raw);
 }catch(error){res.writeHead(404);res.end();}});
const require=createRequire('/workspace/universal-data-pipeline-v1-private-20261022/node-deps/package.json'),{chromium}=require('playwright');
let browser;try{
 await new Promise((ok,bad)=>{service.once('error',bad);service.listen(0,'127.0.0.1',ok);});const origin='http://127.0.0.1:'+service.address().port;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:2000},deviceScaleFactor:1}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());await page.goto(origin);
 const result=await page.evaluate(async({input,fontBase64})=>{
  const face=new FontFace('Gate1Bold',`url(data:font/otf;base64,${fontBase64})`);await face.load();document.fonts.add(face);await document.fonts.ready;
  const THREE=await import('/three.js'),{compileDirectorProgram}=await import('/recovery/reference-director-v2/director_program.mjs'),{createDirectorGraphicPass,prepareMetricPlacements}=await import('/recovery/reference-director-v2/director_graphic_pass.mjs');
  const canvas=document.getElementById('unit'),gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true}),ext=gl.getExtension('WEBGL_debug_renderer_info'),backend=gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER);
  if(!String(backend).includes('SwiftShader'))throw Error('FREE_SOFTWARE_BACKEND_REQUIRED');
  const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);renderer.autoClear=false;renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
  const clear=()=>{renderer.setRenderTarget(null);renderer.setClearColor(new THREE.Color(.02,.035,.05),1);renderer.clear(true,true,true);};
  const read=()=>{const b=new Uint8Array(1080*1920*4);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,b);return b;};
  const pixel=(b,x,y)=>Array.from(b.slice(((1919-Math.floor(y))*1080+Math.floor(x))*4,((1919-Math.floor(y))*1080+Math.floor(x))*4+4));
  const project=p=>[540+(p[0]-9)*180,850-(p[1]-10)*250];
  const factory={screen:project}; // Explicit projection stub for graphics unit testing; no native map is represented.
  const checks=[],images=[];
  const assert=(v,c)=>{if(!v)throw Error(c);};
  function masks(bytes,baseline,predicate){let count=0,x0=1080,y0=1920,x1=-1,y1=-1;const points=[];
   for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){const i=((1919-y)*1080+x)*4,c=bytes.subarray(i,i+4),b=baseline.subarray(i,i+4);if(predicate(c,b)){count++;x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);points.push([x,y]);}}
   return {count,bbox:count?[x0,y0,x1+1,y1+1]:null,points};
  }
  for(const kind of ['PIN','LABEL','AREA','LINE','METRIC']){
   const p=structuredClone(input);p.events=p.events.filter(e=>e.type===kind||kind==='LABEL'&&e.id==='pin');
   if(kind==='PIN')p.events=p.events.filter(e=>e.id==='heroPin');
   const program=compileDirectorProgram(p);clear();gl.finish();const baseline=read();
   const pass=await createDirectorGraphicPass({renderer,canvas,factory,program}),prepared=prepareMetricPlacements(program,{projectAt:(_,point)=>project(point)}),metricPlacements=Object.fromEntries(Object.entries(prepared).map(([id,rows])=>[id,rows[795]]));
   const draw=pass.draw({globalFrame:795,metricPlacements}),pixels=read(),changed=masks(pixels,baseline,(a,b)=>a.some((v,i)=>v!==b[i]));
   assert(changed.count>20,'COMPONENT_NO_CHANGED_PIXELS_'+kind);
   const row={kind,changedPixels:changed.count,changedBBox:changed.bbox,glError:gl.getError(),drawRecords:draw.records};
   if(kind==='PIN'){
    const tip=project(p.locations.find(l=>l.id==='hero').anchor),hole=[tip[0],tip[1]-151+56],body=[tip[0],tip[1]-151+112];
    row.holePixel=pixel(pixels,...hole);row.baselineHolePixel=pixel(baseline,...hole);row.bodyPixel=pixel(pixels,...body);row.tip=tip;
    assert(JSON.stringify(row.holePixel)===JSON.stringify(row.baselineHolePixel),'PIN_HOLE_NOT_TRANSPARENT');assert(row.bodyPixel[0]>200&&row.bodyPixel[1]>180,'PIN_BODY_COLOR');
   }
   if(kind==='LABEL'){
    const white=masks(pixels,baseline,a=>a[0]>220&&a[1]>220&&a[2]>220),blue=masks(pixels,baseline,a=>a[2]>a[0]*1.3&&a[2]>a[1]*1.3&&a[2]>40);
    row.whitePixels=white.count;row.blueHaloPixels=blue.count;row.whiteBBox=white.bbox;row.whiteCenterX=white.bbox?(white.bbox[0]+white.bbox[2])/2:null;
    assert(white.count>50&&blue.count>20,'LABEL_CORE_OR_BLUE_HALO_MISSING');assert(Math.abs(row.whiteCenterX-540)<=2,'LABEL_FULL_WORD_NOT_CENTERED');
   }
   if(kind==='LINE'){
    const core=masks(pixels,baseline,a=>a[0]>200&&a[1]>180&&a[2]<80);row.corePixels=core.count;assert(core.count>100,'LINE_CORE_MISSING');
   }
   if(kind==='METRIC'){
    const white=masks(pixels,baseline,a=>a[0]>220&&a[1]>220&&a[2]>220),pts=white.points,n=pts.length,mx=pts.reduce((s,p)=>s+p[0],0)/n,my=pts.reduce((s,p)=>s+p[1],0)/n;
    const xx=pts.reduce((s,p)=>s+(p[0]-mx)**2,0),yy=pts.reduce((s,p)=>s+(p[1]-my)**2,0),xy=pts.reduce((s,p)=>s+(p[0]-mx)*(p[1]-my),0);
    row.whitePixels=white.count;row.pixelPrincipalAxisDegrees=Math.atan2(2*xy,xx-yy)*90/Math.PI;row.requestedAngleDegrees=metricPlacements.metric.angleRadians*180/Math.PI;
    row.unitPixelAngleErrorDegrees=Math.abs(row.pixelPrincipalAxisDegrees-row.requestedAngleDegrees);assert(white.count>50&&row.unitPixelAngleErrorDegrees<10,'METRIC_PIXEL_ORIENTATION');
   }
   assert(row.glError===0,'GPU_COMPONENT_GL_ERROR');checks.push(row);images.push({kind,png:canvas.toDataURL('image/png').split(',')[1]});pass.dispose();
  }
  renderer.dispose();return {schema:'WORLD_ENGINE_GPU_GRAPHIC_COMPONENT_UNIT_V1',backend,checks,images,nativeMapRendered:false,actualStudioRender:false,referenceProduction:false,nvidiaVerified:false,paidGpuOrApiUsed:false};
 },{input:fixture(),fontBase64:font.toString('base64')});
 const images=result.images;delete result.images;for(const {kind,png}of images)await fs.writeFile(path.join(output,'COMPONENT_'+kind+'.png'),Buffer.from(png,'base64'),{flag:'wx',mode:0o600});
 result.pageErrors=errors;result.fontSHA256=hash(font);result.httpResources=requests;result.status=errors.length?'FAIL':'PASS';
 await fs.writeFile(path.join(output,'GPU_GRAPHIC_COMPONENT_RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
 console.log(JSON.stringify({status:result.status,backend:result.backend,checks:result.checks.map(c=>({kind:c.kind,changedPixels:c.changedPixels,glError:c.glError})),nativeMapRendered:false,output}));
 if(result.status!=='PASS')process.exitCode=1;
}finally{if(browser)await browser.close();await new Promise(ok=>service.close(ok));}
