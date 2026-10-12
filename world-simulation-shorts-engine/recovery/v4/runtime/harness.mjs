// Thin binding adapter. Protected factories own rendering, layout and camera logic.
import {createProofFinal} from '/modules/renderer.mjs';

const WIDTH=1080,HEIGHT=1920;
const FINAL_PARAMETERS=Object.freeze({
  mode:0,dem:true,verticalExaggeration:2,bakedSuppression:0.1,
  correctedLight:true,shadingCorrection:'FINAL',graphics:true,boundaries:true,glow:true,
  reveal:Object.freeze({primary:1,marker:1,location:1,country:1,title:1,disclosure:1}),
  primaryMaterial:1
});
const canvas=document.getElementById('output');
let factory=null,pipeline=null,inputs=null,config=null;
window.v4Runtime={state:'LOADING',error:null};

async function json(url){
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok)throw Error('INPUT_HTTP_'+response.status);
  return response.json();
}
function backend(){
  const gl=canvas.getContext('webgl2');
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  return {context:gl.getParameter(gl.VERSION),shadingLanguage:gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
    vendor:debug?gl.getParameter(debug.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR),
    renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
    preserveDrawingBuffer:gl.getContextAttributes().preserveDrawingBuffer,
    dimensions:[canvas.width,canvas.height],devicePixelRatio:devicePixelRatio};
}
async function digest(bytes){
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)))
    .map(value=>value.toString(16).padStart(2,'0')).join('');
}
async function capture(png,readPixels,diagnostic){
  const gl=canvas.getContext('webgl2');gl.finish();
  const pixels=readPixels();
  if(pixels.byteLength!==WIDTH*HEIGHT*4)throw Error('RGBA_LENGTH_MISMATCH');
  if(gl.getError()!==gl.NO_ERROR)throw Error('READBACK_GL_ERROR');
  return {png,raw_rgba_sha256:await digest(pixels),raw_rgba_orientation:'bottom-up WebGL RGBA8',
    backend:backend(),diagnostic:structuredClone(diagnostic)};
}

async function init(){
  config=await json('/runtime-config.json');
  const [REGIONAL,CONTINENT,metadata]=await Promise.all([
    json('/inputs/regional.json'),json('/inputs/continent.json'),json('/inputs/input-manifest.json')
  ]);
  if(!REGIONAL.layout?.measured)throw Error('MEASURED_LAYOUT_REQUIRED');
  if(!metadata.heightSource||!metadata.contextTerrain)throw Error('RESTORED_RUNTIME_METADATA_REQUIRED');
  if(metadata.heightSource.url!=='/height.f32'||metadata.contextTerrain.url!=='/camera-v4-assets/context-native.png')
    throw Error('UNEXPECTED_HISTORICAL_RUNTIME_URL');
  if(REGIONAL.assets.font.sha256!==metadata.scales.REGIONAL.assets.font.sha256)
    throw Error('PINNED_FONT_DESCRIPTOR_CHANGED');
  inputs={plans:{REGIONAL,CONTINENT},metadata};
  // Awaiting the original factory also awaits its textures, DEM and pinned font.
  factory=await createProofFinal({canvas,plan:REGIONAL,layoutPlan:REGIONAL,
    contextTerrain:metadata.contextTerrain,contextGeometries:CONTINENT.geometries,
    heightSource:metadata.heightSource,width:WIDTH,height:HEIGHT});
  await document.fonts.ready;
  if(!document.fonts.check('36px Gate1Bold'))throw Error('PINNED_FONT_NOT_READY');
  window.v4Runtime={state:'READY_STATIC',error:null,config,parameters:FINAL_PARAMETERS,
    async captureStatic(){
      if(pipeline)throw Error('STATIC_FACTORY_ALREADY_DISPOSED');
      return capture(factory.render(FINAL_PARAMETERS),()=>factory.readPixels(),factory.evidence);
    },
    async initV4(){
      if(pipeline)return;
      const [scene,cameraPlan,module]=await Promise.all([
        json('/inputs/scene.json'),json('/inputs/camera-plan.json'),
        import('/modules/camera_gpu_pipeline_v4.mjs')
      ]);
      factory.dispose();factory=null;
      pipeline=await module.createGuidedCameraGpuPipeline({canvas,plans:inputs.plans,scene,cameraPlan,
        heightSource:metadata.heightSource,contextTerrain:metadata.contextTerrain,width:WIDTH,height:HEIGHT});
      this.state='READY_V4';
      this.checkpoints=structuredClone(cameraPlan.checkpoints);
    },
    async captureFrame(frame){
      if(!pipeline)throw Error('V4_NOT_INITIALIZED');
      if(!Number.isInteger(frame)||frame<0||frame>374)throw Error('INTEGER_V4_FRAME_REQUIRED');
      const diagnostic=pipeline.drawFrame(frame);
      return capture(pipeline.png(),()=>pipeline.readPixels(),{frame,evidence:pipeline.evidence,frameDiagnostic:diagnostic});
    },
    dispose(){pipeline?.dispose();if(factory)factory.dispose();this.state='DISPOSED';}
  };
}
init().catch(error=>{window.v4Runtime={state:'ERROR',error:String(error?.message??error)};});
