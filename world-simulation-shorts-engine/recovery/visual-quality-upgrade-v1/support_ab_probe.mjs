/** TEST TOOL ONLY. Tiny actual SwiftShader draws isolate the source-support
 * discontinuity; they are not a video, NVIDIA test, or visual-quality approval.
 * This module is absent from the production runtime closure. */
import {createAstraCompositionPass,DEFAULT_ASTRA_PROFILE} from '/astra/astra_material_core.mjs';
import {DEFAULT_REFERENCE_TERRAIN_PROFILE_V4} from '/modules/reference_terrain_material_v4.mjs?baseline';
import {captureFlowNativeGlState as capture,restoreFlowNativeGlState as restore} from '/modules/flow_graphic_pass_v2.mjs';
import {createQualityCompositionPass} from './quality_material_core.mjs';
const hash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
function texture(gl,width,height,format,data){
 const value=gl.createTexture();if(!value)throw Error('TEST_SUPPORT_TEXTURE_ALLOCATION');
 gl.bindTexture(gl.TEXTURE_2D,value);
 for(const key of ['TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.NEAREST);
 for(const key of ['TEXTURE_WRAP_S','TEXTURE_WRAP_T'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.CLAMP_TO_EDGE);
 gl.texImage2D(gl.TEXTURE_2D,0,gl[format[0]],width,height,0,gl[format[1]],gl[format[2]],data);
 if(gl.getError()!==gl.NO_ERROR){gl.deleteTexture(value);throw Error('TEST_SUPPORT_TEXTURE_UPLOAD');}return value;
}
const distance=(a,b)=>Math.hypot(...a.slice(0,3).map((v,i)=>v-b[i]));
export async function runSupportABProbe(){
 const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('TEST_SUPPORT_WEBGL2_REQUIRED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info'),renderer=debug&&gl.getParameter(debug.UNMASKED_RENDERER_WEBGL);
 if(typeof renderer!=='string'||!/SwiftShader/i.test(renderer))throw Error('TEST_SUPPORT_SWIFTSHADER_ONLY');
 const results=[],width=256,height=256,n=64,step=.0001,bounds=[0,0,n*step,n*step];
 try{
  for(const role of ['terrain','bathymetry','surfaceTexture']){
   const valid=new Uint8Array(n*n).fill(1),values=role==='terrain'?new Float32Array(n*n):
    role==='bathymetry'?new Int16Array(n*n):new Uint8Array(n*n*4),owned=[];
   for(let j=0;j<n;j++)for(let i=0;i<n;i++){
    const k=j*n+i;if(i===32||i===33)valid[k]=0;
    if(role==='terrain')values[k]=10000-i*30;
    else if(role==='bathymetry')values[k]=-300;
    else{values[k*4]=220;values[k*4+1]=205;values[k*4+2]=180;values[k*4+3]=255;}
   }
   const sourceSHA=await hash(values),validSHA=await hash(valid),before=capture(gl);
   let entry;
   try{
    gl.activeTexture(gl.TEXTURE0);gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_ROW_LENGTH,0);gl.pixelStorei(gl.UNPACK_IMAGE_HEIGHT,0);
    gl.pixelStorei(gl.UNPACK_SKIP_PIXELS,0);gl.pixelStorei(gl.UNPACK_SKIP_ROWS,0);gl.pixelStorei(gl.UNPACK_SKIP_IMAGES,0);
    const fmt=role==='terrain'?['R32F','RED','FLOAT']:role==='bathymetry'?['R16I','RED_INTEGER','SHORT']:['RGBA8','RGBA','UNSIGNED_BYTE'];
    const sourceTexture=texture(gl,n,n,fmt,values);owned.push(sourceTexture);
    const validTexture=texture(gl,n,n,['R8UI','RED_INTEGER','UNSIGNED_BYTE'],valid);owned.push(validTexture);
    entry={role,id:'synthetic_'+role,values:sourceTexture,valid:validTexture,
     metadata:{dimensions:[n,n],bbox:bounds,transform:[0,step,0,0,0,step],sourceValueBytesSHA256:sourceSHA}};
   }finally{restore(gl,before);}
   const coverage=new Uint8Array(width*height*4);
   for(let i=0;i<width*height;i++){coverage[i*4]=role==='bathymetry'?0:255;coverage[i*4+3]=255;}
   const args={bounds,coverage,frame:0,fps:30};
   const baseline=()=>({evidence:{version:'TEST_ONLY_CONSTANT_BASELINE'},
    draw(){const state=capture(gl);try{
     gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,width,height);
     gl.disable(gl.SCISSOR_TEST);gl.colorMask(true,true,true,true);gl.clearColor(.12,.14,.16,1.);gl.clear(gl.COLOR_BUFFER_BIT);
    }finally{restore(gl,state);}return {version:'TEST_ONLY_CONSTANT_BASELINE',frame:0,bounds};},dispose(){}});
   const options=()=>({gl,baseline:baseline(),uploads:{resources:[entry],testOnly:true,gpuUploadExecuted:true,dispose(){}},
    profile:DEFAULT_ASTRA_PROFILE,baselineProfile:DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,width,height,capture,restore});
   const pixel=(x,y)=>{const state=capture(gl),out=new Uint8Array(4);try{
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
    gl.pixelStorei(gl.PACK_ALIGNMENT,1);gl.pixelStorei(gl.PACK_ROW_LENGTH,0);gl.pixelStorei(gl.PACK_SKIP_PIXELS,0);gl.pixelStorei(gl.PACK_SKIP_ROWS,0);
    gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,out);
    if(gl.getError()!==gl.NO_ERROR)throw Error('TEST_SUPPORT_READPIXELS_FAILED');
   }finally{restore(gl,state);}return [...out];};
   const boundaryCell=role==='terrain'?31:32,boundaryPixel=boundaryCell/n*width,left=Math.ceil(boundaryPixel-.5)-1,right=left+1;
   let oldPass,newPass;
   try{
    oldPass=createAstraCompositionPass(options());oldPass.draw(args);
    const oldInside=pixel(left,128),oldOutside=pixel(right,128);oldPass.dispose();oldPass=null;
    newPass=createQualityCompositionPass({...options(),qualityProfile:{boundary:true,screenFeatherPixels:32}});newPass.draw(args);
    const newInside=pixel(left,128),newOutside=pixel(right,128),oldRGBJump=distance(oldInside,oldOutside),newRGBJump=distance(newInside,newOutside);
    if(!(oldRGBJump>0&&newRGBJump<oldRGBJump))throw Error('TEST_SUPPORT_EDGE_NOT_REDUCED_'+role);
    if(sourceSHA!==await hash(values)||validSHA!==await hash(valid))throw Error('TEST_SUPPORT_SOURCE_MUTATED');
    results.push({role,oldInside,oldOutside,newInside,newOutside,oldRGBJump,newRGBJump,
     relativeReduction:1-newRGBJump/oldRGBJump,boundarySourceCell:boundaryCell,sampledOutputPixels:[left,right],
     derivedMask:newPass.evidence.astra.boundary.sourceMasks[0],nativeGIS:role==='bathymetry'?'ALL_OCEAN':'ALL_LAND',
     sourceValuesSHA256:sourceSHA,validSHA256:validSHA,sourceValuesChanged:false,
     actualDrawExecuted:true,actualReadPixelsExecuted:true,testOnly:true,nvidiaHardwareVerified:false});
   }finally{oldPass?.dispose();newPass?.dispose();for(const value of owned)gl.deleteTexture(value);}
  }
 }finally{gl.getExtension('WEBGL_lose_context')?.loseContext();}
 return {schema:'QUALITY_SYNTHETIC_SUPPORT_AB_SOFTWARE_V1',renderer,testOnly:true,
  fixture:'SYNTHETIC_CONSTANT_SOURCE_WITH_INTERNAL_NODATA_BAND',outputDimensions:[width,height],
  videoQualityApproved:false,nvidiaHardwareVerified:false,actualReadPixelsExecuted:true,roles:results};
}
