// Private GPU fixture: geographic layer occlusion preserves existing static pixels.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(engine);
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{stdio:['ignore','pipe','inherit']});
let browser;
try {
 const url=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('SERVER_TIMEOUT')),10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);resolve(JSON.parse(line).url);});
  server.once('error',reject);server.once('exit',code=>reject(Error('SERVER_EXIT_'+code)));
 });
 browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
 await page.goto(url+'/runtime-config.json');
 const report=await page.evaluate(async()=>{
  const THREE=await import('/three.js');
  const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
  const {compileGeographicLinePrimitive,evaluateGeographicLineReveal}=await import('/modules/event_line_v1.mjs');
  const {createEventLinePass,validateEventLineFootprint}=await import('/modules/event_line_pass_v1.mjs');
  const width=1080,height=1920,canvas=document.createElement('canvas');document.body.appendChild(canvas);
  const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
  if(!gl)throw Error('WEBGL2_REQUIRED');
  const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
  renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
  renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
  renderer.setClearColor(0x102030,1);
  const camera=new THREE.OrthographicCamera(0,width,0,height,.1,10);camera.position.z=5;camera.updateMatrixWorld();
  const nativeScene=new THREE.Scene();
  const staticLine=new THREE.Mesh(new THREE.PlaneGeometry(600,3),new THREE.MeshBasicMaterial({color:0x58a9c1,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));
  staticLine.position.set(540,530,0);nativeScene.add(staticLine);
  const marker=new THREE.Group();marker.position.set(540,700,0);
  const ring=new THREE.Mesh(new THREE.RingGeometry(10,16,64),new THREE.MeshBasicMaterial({color:0xee6889,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));
  const anchor=new THREE.Mesh(new THREE.CircleGeometry(4,48),new THREE.MeshBasicMaterial({color:0xffffff,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));
  marker.add(ring,anchor);nativeScene.add(marker);
  const nativeState=()=>JSON.stringify([staticLine,marker,ring,anchor].map(object=>({
   position:object.position.toArray(),scale:object.scale.toArray(),rotation:object.rotation.toArray(),
   geometry:object.geometry?.toJSON(),material:object.material?.toJSON()
  })));
  const beforeNative=nativeState(),markerBox=[510,670,570,730],staticBox=[235,520,845,540];
  const style={width:5,glowRadius:1.7,glowGain:.1,coreColor:[1,.94,.68,.86],glowColor:[.88,.52,.07,1]};
  const safeArea=[48,72,1032,1848],protectedGraphics=[{kind:'MARKER',box:markerBox}];
  const source={source_type:'SYNTHETIC_TEST',source_reference:'fixture://static-geographic-marker-occlusion',verification_status:'SYNTHETIC_TEST'};
  const compile=direction=>{
   const intent=compileEventIntent({data_mode:'SYNTHETIC_TEST',line:{
    geometry:{type:'LineString',coordinates:[[0,0],[1,0],[4,0]]},direction,style_role:'EVENT_HIGHLIGHT',source}});
   return {intent,primitive:compileGeographicLinePrimitive(intent,{project:([x,y])=>[240+x*150,700-y*150]})};
  };
  const pass=createEventLinePass({renderer,style});
  const read=()=>{gl.finish();const a=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,a);return a;};
  const offset=(x,y)=>((height-1-y)*width+x)*4;
  const changedAt=(a,b,x,y)=>{const i=offset(x,y);return a[i]!==b[i]||a[i+1]!==b[i+1]||a[i+2]!==b[i+2]||a[i+3]!==b[i+3];};
  const inside=(x,y,box)=>x+.5>=box[0]&&y+.5>=box[1]&&x+.5<=box[2]&&y+.5<=box[3];
  const boxDifference=(a,b,box)=>{
   let pixels=0;for(let y=Math.ceil(box[1]);y<box[3];y++)for(let x=Math.ceil(box[0]);x<box[2];x++)
    if(changedAt(a,b,x,y))pixels++;
   return pixels;
  };
  const nativeFrame=()=>{renderer.clear(true,true,true);renderer.render(nativeScene,camera);return read();};
  const baseline=nativeFrame();
  renderer.clear(true,true,true);const empty=read();
  const nativeMarkerPixels=boxDifference(baseline,empty,markerBox),nativeStaticLinePixels=boxDifference(baseline,empty,staticBox);
  const directions=[];
  for(const direction of ['FORWARD','REVERSE']){
   const {intent,primitive}=compile(direction),before=JSON.stringify({intent,primitive});
   const footprint=validateEventLineFootprint(primitive,{style,safeArea,protectedGraphics});
   const expectedFull=evaluateGeographicLineReveal(primitive,1,{paddingPixels:footprint.paddingPixels});
   const frames=[];let fullBytes;
   for(const fraction of [0,.3,.5,.7,1,1]){
    nativeFrame();
    const info=pass.draw({primitive,visibleFraction:fraction,safeArea,protectedGraphics}),actual=read();
    const expected=evaluateGeographicLineReveal(primitive,fraction,{paddingPixels:footprint.paddingPixels});
    let changed=0,outside=0;
    for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(changedAt(actual,baseline,x,y)){
     changed++;if(!info.roi||!inside(x,y,info.roi))outside++;
    }
    let holdDifference=null;
    if(fraction===1){if(fullBytes)holdDifference=boxDifference(fullBytes,actual,[0,0,width,height]);else fullBytes=actual;}
    frames.push({fraction,path:info.path,expectedPath:expected.path,tip:info.path.at(-1)??null,
     visibleLengthPixels:info.visibleLengthPixels,expectedLengthPixels:expected.visibleLengthPixels,
     changed,outside,markerPixelsChanged:boxDifference(actual,baseline,markerBox),
     staticLinePixelsChanged:boxDifference(actual,baseline,staticBox),holdDifference,
     leftVisible:changedAt(actual,baseline,450,700),rightVisible:changedAt(actual,baseline,630,700),
     geometryPathUnchanged:JSON.stringify(info.path)===JSON.stringify(expected.path)});
   }
   // A control without a protected Marker must visibly overwrite its pixels.
   nativeFrame();pass.draw({primitive,visibleFraction:1,safeArea});const unprotected=read();
   const unprotectedMarkerPixelsChanged=boxDifference(unprotected,baseline,markerBox);
   directions.push({direction,totalLengthPixels:primitive.totalLengthPixels,
    expectedFullPath:expectedFull.path,frames,unprotectedMarkerPixelsChanged,
    sourceAndPrimitiveUnchanged:before===JSON.stringify({intent,primitive})});
  }
  const {primitive}=compile('FORWARD');
  const failure=options=>{try{pass.draw({primitive,visibleFraction:1,safeArea,...options});return null;}catch(e){return e.message;}};
  const rejected={
   text:failure({protectedGraphics:[{kind:'TEXT',box:markerBox}]}),
   panel:failure({protectedGraphics:[{kind:'PANEL',box:markerBox}]}),
   legacy:failure({protectedBoxes:[markerBox]}),
   legacyWithMarker:failure({protectedBoxes:[markerBox],protectedGraphics}),
   safeArea:failure({safeArea:[48,72,500,1848],protectedGraphics})
  };
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  const result={status:'PASS',scope:'PRIVATE_SYNTHETIC_STATIC_GEOGRAPHIC_OCCLUSION_GPU',
   renderer:gl.getParameter(debug.UNMASKED_RENDERER_WEBGL),nativeMarkerPixels,nativeStaticLinePixels,
   markerBox,staticBox,directions,rejected,nativeGraphicStateUnchanged:beforeNative===nativeState(),glError:gl.getError()};
  pass.dispose();for(const object of [staticLine,ring,anchor]){object.geometry.dispose();object.material.dispose();}
  renderer.dispose();canvas.remove();return result;
 });
 assert.match(report.renderer,/SwiftShader/);assert.equal(errors.length,0);assert.equal(report.glError,0);
 assert.ok(report.nativeMarkerPixels>0);assert.ok(report.nativeStaticLinePixels>0);assert.equal(report.nativeGraphicStateUnchanged,true);
 for(const row of report.directions){
  assert.equal(row.totalLengthPixels,600);assert.equal(row.sourceAndPrimitiveUnchanged,true);
  assert.ok(row.unprotectedMarkerPixelsChanged>0,'positive control must alter Marker pixels');
  assert.equal(row.frames[0].changed,0);
  for(const frame of row.frames){
   assert.equal(frame.outside,0);assert.equal(frame.markerPixelsChanged,0);assert.equal(frame.staticLinePixelsChanged,0);
   assert.equal(frame.geometryPathUnchanged,true);assert.deepEqual(frame.path,frame.expectedPath);
   assert.equal(frame.visibleLengthPixels,frame.expectedLengthPixels);assert.equal(frame.visibleLengthPixels,frame.fraction*600);
   if(frame.holdDifference!==null)assert.equal(frame.holdDifference,0);
  }
  assert.deepEqual(row.frames[1].tip,row.direction==='FORWARD'?[420,700]:[660,700]);
  assert.deepEqual(row.frames[2].tip,[540,700],'internal progress must continue inside Marker');
  assert.deepEqual(row.frames[3].tip,row.direction==='FORWARD'?[660,700]:[420,700]);
  assert.equal(row.frames[2].leftVisible,row.direction==='FORWARD');
  assert.equal(row.frames[2].rightVisible,row.direction==='REVERSE');
  assert.equal(row.frames[3].leftVisible,true);assert.equal(row.frames[3].rightVisible,true);
  assert.deepEqual(row.frames[4].path,row.expectedFullPath);
 }
 for(const key of ['text','panel','legacy','legacyWithMarker'])assert.equal(report.rejected[key],'EVENT_LINE_PROTECTED_GRAPHIC_COLLISION');
 assert.equal(report.rejected.safeArea,'EVENT_LINE_HALO_OUTSIDE_SAFE_AREA');
 const arg=process.argv.indexOf('--report');
 if(arg>=0){if(!process.argv[arg+1])throw Error('REPORT_PATH_REQUIRED');await writeFile(process.argv[arg+1],JSON.stringify(report,null,2)+'\n');}
 console.log(JSON.stringify(report));
} finally {await browser?.close();server.kill();}
