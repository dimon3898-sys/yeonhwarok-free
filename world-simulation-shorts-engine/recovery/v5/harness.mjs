// Thin V5 input/capture adapter. Rendering, Camera and Reveal stay in their modules.
import {createV5CameraGpuPipeline} from '/modules/camera_gpu_pipeline_v5.mjs';
const WIDTH=1080,HEIGHT=1920,canvas=document.getElementById('output');
let pipeline=null;
window.v5Runtime={state:'LOADING',error:null};
async function json(url){
 const response=await fetch(url,{cache:'no-store'});
 if(!response.ok)throw Error('INPUT_HTTP_'+response.status);
 return response.json();
}
async function digest(bytes){
 return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
  .map(value=>value.toString(16).padStart(2,'0')).join('');
}
function backend(){
 const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info');
 return {context:gl.getParameter(gl.VERSION),
  renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
  dimensions:[canvas.width,canvas.height],preserveDrawingBuffer:gl.getContextAttributes().preserveDrawingBuffer,
  devicePixelRatio:devicePixelRatio};
}
async function init(){
 const [REGIONAL,CONTINENT,scene,cameraPlan,metadata]=await Promise.all([
  json('/inputs/regional.json'),json('/inputs/continent.json'),json('/inputs/scene.json'),
  json('/inputs/camera-plan.json'),json('/inputs/input-manifest.json')
 ]);
 if(cameraPlan.directorVersion!=='CAMERA_DIRECTOR_V5'||cameraPlan.implementationStage!=='NATURAL_TURNAROUND')
  throw Error('COMPILED_V5_CAMERA_REQUIRED');
 pipeline=await createV5CameraGpuPipeline({canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,
  heightSource:metadata.heightSource,contextTerrain:metadata.contextTerrain,width:WIDTH,height:HEIGHT});
 await document.fonts.ready;
 if(!document.fonts.check('36px Gate1Bold'))throw Error('PINNED_FONT_NOT_READY');
 window.v5Runtime={state:'READY',error:null,
  info:{cameraPlan,pipelineVersion:pipeline.evidence.version,revealPlan:pipeline.revealPlan,evidence:pipeline.evidence},
  async captureFrame(frame){
   if(!Number.isInteger(frame)||frame<0||frame>=cameraPlan.totalFrames)throw Error('INTEGER_V5_FRAME_REQUIRED');
   const diagnostic=pipeline.drawFrame(frame),gl=canvas.getContext('webgl2');gl.finish();
   const pixels=pipeline.readPixels();
   if(pixels.byteLength!==WIDTH*HEIGHT*4||gl.getError()!==gl.NO_ERROR)throw Error('CANONICAL_READBACK_FAILED');
   return {png:pipeline.png(),raw_rgba_sha256:await digest(pixels),backend:backend(),diagnostic};
  },
  dispose(){pipeline?.dispose();pipeline=null;this.state='DISPOSED';}
 };
}
init().catch(error=>{window.v5Runtime={state:'ERROR',error:String(error.message??error)};});
