// Focused software GPU verification, not a production fixture or public Proof.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(engine);
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const {chromium}=require('playwright');
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{stdio:['ignore','pipe','inherit']});
let browser;
try {
 const url=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('SERVER_TIMEOUT')),10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);resolve(JSON.parse(line).url);});
  server.once('error',reject);server.once('exit',code=>reject(Error('SERVER_EXIT_'+code)));
 });
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(url+'/runtime-config.json');
 const report=await page.evaluate(async()=>{
  const THREE=await import('/three.js'),{compileEventIntent}=await import('/modules/event_contract_v1.mjs');
  const {compileGeographicLinePrimitive}=await import('/modules/event_line_v1.mjs');
  const {createEventLinePass}=await import('/modules/event_line_pass_v1.mjs');
  const canvas=document.createElement('canvas');document.body.appendChild(canvas);
  const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
  const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);
  renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
  renderer.setClearColor(0x102030,1);
  const style={width:5,glowRadius:1.7,glowGain:.1,coreColor:[1,.94,.68,.86],glowColor:[.88,.52,.07,1]};
  let autoClear='';try{createEventLinePass({renderer,style});}catch(e){autoClear=e.message;}
  renderer.autoClear=false;
  const pass=createEventLinePass({renderer,style}),safeArea=[48,72,1032,1848];
  const source={source_type:'SYNTHETIC_TEST',source_reference:'focused line pixel fixture',verification_status:'SYNTHETIC_TEST'};
  const project=([x,y])=>[200+x*20,300-y*20];
  const intent=compileEventIntent({data_mode:'SYNTHETIC_TEST',line:{geometry:{type:'LineString',coordinates:[[0,0],[1,0],[1,-9]]},direction:'FORWARD',style_role:'PRIMARY',source}});
  const primitive=compileGeographicLinePrimitive(intent,{project});
  function read(){gl.finish();const a=new Uint8Array(1080*1920*4);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,a);return a;}
  function frame(f){renderer.clear(true,true,true);const base=read();const info=pass.draw({primitive,visibleFraction:f,safeArea,protectedBoxes:[]});const actual=read();
   let changed=0,outside=0;for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
    const index=((1919-y)*1080+x)*4;
    if(actual[index]!==base[index]||actual[index+1]!==base[index+1]||actual[index+2]!==base[index+2]||actual[index+3]!==base[index+3]){
     changed++;if(!info.roi||x+.5<info.roi[0]||y+.5<info.roi[1]||x+.5>info.roi[2]||y+.5>info.roi[3])outside++;
    }
   }return {info,changed,outside,bytes:actual};
  }
  const zero=frame(0),half=frame(.5),full=frame(1),hold=frame(1);
  let holdDiff=0;for(let i=0;i<full.bytes.length;i++)if(full.bytes[i]!==hold.bytes[i])holdDiff++;
  const sequence=[0,.1,.3,.6,1].map(f=>{const a=frame(f);return {fraction:f,changed:a.changed,tip:a.info.path.at(-1),outside:a.outside};});
  let collision='';try{pass.draw({primitive,visibleFraction:1,safeArea,protectedBoxes:[[210,295,230,330]]});}catch(e){collision=e.message;}
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  const report={renderer:gl.getParameter(debug.UNMASKED_RENDERER_WEBGL),zeroChanged:zero.changed,halfChanged:half.changed,
   fullChanged:full.changed,halfTip:half.info.path.at(-1),fullPath:full.info.path,outside:[zero,half,full,hold].reduce((n,a)=>n+a.outside,0),
   holdByteDifference:holdDiff,sequence,collision,autoClear,glError:gl.getError()};pass.dispose();renderer.dispose();return report;
 });
 assert.match(report.renderer,/SwiftShader/);assert.equal(report.zeroChanged,0);assert.ok(report.halfChanged>0);
 assert.ok(report.fullChanged>report.halfChanged);assert.deepEqual(report.halfTip,[220,380]);
 assert.deepEqual(report.fullPath,[[200,300],[220,300],[220,480]]);assert.equal(report.outside,0);
 assert.equal(report.holdByteDifference,0);assert.equal(report.glError,0);assert.equal(report.collision,'EVENT_LINE_PROTECTED_GRAPHIC_COLLISION');
 assert.equal(report.autoClear,'EVENT_SHARED_RENDERER_AUTOCLEAR_FORBIDDEN');
 assert.ok(report.sequence.every(a=>a.outside===0));assert.equal(errors.length,0);
 console.log(JSON.stringify({status:'PASS',scope:'COMMON_CORE_SYNTHETIC_NOT_PRODUCTION_PROOF',...report}));
} finally {await browser?.close();server.kill();}
