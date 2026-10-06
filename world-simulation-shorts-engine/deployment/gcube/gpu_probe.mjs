/** One real WebGL2 draw. This does not render an engine video or benchmark it. */
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const appRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const require=createRequire(path.join(appRoot,'../cinematic-world-map/package.json'));
const {chromium}=require('playwright');
const executable=process.argv[2];
if(!executable||process.argv.length!==3)throw Error('GPU_PROBE_ARGUMENTS_INVALID');
let browser, browser_started=false;
let result={schema_version:2,browser_started:false,browser_version:null,
 webgl:{context_available:false,context_version:null,webgl2:false,draw_passed:false},
 system_info_available:false,system_info:null,error_code:null};
try{
 browser=await chromium.launch({executablePath:executable,headless:true,timeout:30000,
  args:['--no-sandbox','--disable-dev-shm-usage']});
 browser_started=true;result.browser_started=true;result.browser_version=browser.version();
 const page=await browser.newPage();
 const webgl=await page.evaluate(()=>{
  const canvas=new OffscreenCanvas(32,32),gl=canvas.getContext('webgl2',{
   alpha:false,antialias:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
  if(!gl)return {context_available:false,context_version:null,webgl2:false,draw_passed:false,
   reason_code:'WEBGL2_CONTEXT_UNAVAILABLE'};
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  const renderer=debug?String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)):null;
  const vendor=debug?String(gl.getParameter(debug.UNMASKED_VENDOR_WEBGL)):null;
  const identity={context_available:true,context_version:2,webgl2:true,renderer,vendor,
   gl_vendor:String(gl.getParameter(gl.VENDOR)),gl_renderer:String(gl.getParameter(gl.RENDERER)),
   unmasked_renderer:renderer,unmasked_vendor:vendor,debug_renderer_available:Boolean(debug)};
  try{
  const compile=(kind,source)=>{const shader=gl.createShader(kind);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('GPU_PROBE_SHADER_FAILED');return shader;};
  const vertex=compile(gl.VERTEX_SHADER,'#version 300 es\nin vec2 p;void main(){gl_Position=vec4(p,0.,1.);}');
  const fragment=compile(gl.FRAGMENT_SHADER,'#version 300 es\nprecision highp float;out vec4 color;void main(){color=vec4(1.,0.,0.,1.);}');
  const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('GPU_PROBE_PROGRAM_FAILED');
  gl.useProgram(program);const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
  const location=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(location);
  gl.vertexAttribPointer(location,2,gl.FLOAT,false,0,0);gl.viewport(0,0,32,32);gl.drawArrays(gl.TRIANGLES,0,3);gl.finish();
  const pixel=new Uint8Array(4);gl.readPixels(16,16,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
  const error=gl.getError();return {...identity,webgl_error:error,pixel:Array.from(pixel),
   draw_passed:error===0&&pixel[0]>=250&&pixel[1]<=5&&pixel[2]<=5&&pixel[3]>=250,
   max_texture_size:gl.getParameter(gl.MAX_TEXTURE_SIZE),max_renderbuffer_size:gl.getParameter(gl.MAX_RENDERBUFFER_SIZE)};
  }catch(error){return {...identity,draw_passed:false,webgl_error:gl.getError(),
    reason_code:['GPU_PROBE_SHADER_FAILED','GPU_PROBE_PROGRAM_FAILED'].includes(error?.message)?error.message:'WEBGL_DRAW_FAILED'};}
 });
 result.webgl=webgl;
 let system_info=null,system_info_available=false;
 try{
  const session=await browser.newBrowserCDPSession();const info=await session.send('SystemInfo.getInfo');
  system_info={devices:(info.gpu?.devices||[]).map(item=>Object.fromEntries(
   ['vendorId','deviceId','vendorString','deviceString','driverVendor','driverVersion']
    .filter(key=>item[key]!==undefined).map(key=>[key,item[key]]))),
   feature_status:info.gpu?.featureStatus||{},
   auxiliary:Object.fromEntries(['glRenderer','glVendor','glVersion','skiaBackendType']
    .filter(key=>info.gpu?.auxAttributes?.[key]!==undefined).map(key=>[key,info.gpu.auxAttributes[key]]))};
  system_info_available=true;await session.detach();
 }catch{}
 result.system_info_available=system_info_available;result.system_info=system_info;
}catch(error){
 const message=String(error?.message||'');
 // Convert launch/page errors into fixed categories; never emit raw stderr,
 // browser command lines, filesystem paths, environment values or owner codes.
 result.error_code=!browser_started?'CHROMIUM_START_FAILED':'CHROMIUM_EVALUATION_FAILED';
 if(/timeout/i.test(message))result.error_code='CHROMIUM_TIMEOUT';
 else if(/error while loading shared libraries|libEGL|libGLES|libvulkan|libGLX/i.test(message))
  result.error_code='DRIVER_GRAPHICS_MISSING';
}finally{
 if(browser){let timer;await Promise.race([browser.close().catch(()=>{}),
  new Promise(resolve=>{timer=setTimeout(resolve,5000);})]);clearTimeout(timer);}
 console.log(JSON.stringify(result));
 if(result.error_code)process.exitCode=2;
}
