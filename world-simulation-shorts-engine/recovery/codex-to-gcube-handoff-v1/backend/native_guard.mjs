/** Additional native-map evidence, not a standalone basic-WebGL reprobe. */
const check=(value,code)=>{if(!value)throw Error(code);};
export function assertNvidiaVulkanContext(gl){
 check(gl&&typeof gl.getExtension==='function','GCUBE_NATIVE_CONTEXT_REQUIRED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 check(debug,'GCUBE_ACTUAL_RENDERER_INFO_REQUIRED');
 const backend=String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL));
 check(/\bNVIDIA\b/i.test(backend)&&!/swiftshader|llvmpipe|lavapipe|softpipe|software/i.test(backend),'GCUBE_NVIDIA_RENDERER_REQUIRED');
 check(/Vulkan/i.test(backend),'GCUBE_NVIDIA_VULKAN_REQUIRED');
 return{backend,contextVerified:true};
}
export function validateNativeStability(proof,expectedBackend){
 check(proof?.schema==='WORLD_ENGINE_NATIVE_MAP_STABILITY_V1'&&proof.status==='PASS'&&proof.backend===expectedBackend,'GCUBE_NATIVE_STABILITY_PROOF_REQUIRED');
 check(Array.isArray(proof.draws)&&proof.draws.length===3&&proof.draws.every((draw,index)=>draw.index===index&&draw.glError===0&&draw.frame===0&&/^[a-f0-9]{64}$/.test(draw.rawRGBA256)&&draw.nonBlackPixels>1080*1920*.2&&draw.rgbaBytes===1080*1920*4),'GCUBE_NATIVE_STABILITY_DRAWS_INVALID');
 check(proof.draws.every(draw=>draw.rawRGBA256===proof.draws[0].rawRGBA256),'GCUBE_NATIVE_REPEATED_PIXEL_MISMATCH');
 return true;
}
export async function runThreeNativeDraws({runtime,canvas,frame=0}={}){
 check(frame===0&&canvas?.width===1080&&canvas?.height===1920,'GCUBE_STABILITY_INITIAL_FRAME_REQUIRED');
 check(runtime&&typeof runtime.drawFrame==='function'&&typeof runtime.readPixels==='function'&&typeof runtime.recordNativeStability==='function','GCUBE_ACTUAL_NATIVE_RUNTIME_REQUIRED');
 const gl=canvas.getContext('webgl2'),{backend}=assertNvidiaVulkanContext(gl),draws=[];
 for(let index=0;index<3;index++){
  const diagnostic=runtime.drawFrame(frame),pixels=runtime.readPixels();
  check(diagnostic?.glError===0&&diagnostic.backend===backend,'GCUBE_NATIVE_DRAW_FAILED');
  check(pixels instanceof Uint8Array&&pixels.byteLength===1080*1920*4,'GCUBE_NATIVE_READBACK_INVALID');
  let nonBlackPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlackPixels++;
  const rawRGBA256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',pixels))].map(value=>value.toString(16).padStart(2,'0')).join('');
  draws.push({index,frame,glError:gl.getError(),rawRGBA256,nonBlackPixels,rgbaBytes:pixels.byteLength});
 }
 const proof={schema:'WORLD_ENGINE_NATIVE_MAP_STABILITY_V1',status:'PASS',backend,draws,source:'ACTUAL_EXISTING_MAP_RUNTIME_DRAW_AND_READPIXELS',basicWebGLProbeRepeated:false};
 validateNativeStability(proof,backend);
 runtime.recordNativeStability(proof);
 return proof;
}
