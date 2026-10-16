/** Actual SOFTWARE WebGL2 coverage probes. Synthetic masks only; never a
 * physical NVIDIA admission, geographic coast certificate or public proof.
 */
import {createCoverageOuterGlowPass} from './coverage_outer_glow.mjs';
import {assertOuterDomainContext} from './frontier_profile_core.mjs';
import {createNativeDomainBinding,describeNativeDomainBinding,publishNativeDomainCoverage,
 getNativeDomainCoverage,clearNativeDomainCoverage} from './native_domain_coverage.mjs';
import {captureFlowNativeGlState as capture,restoreFlowNativeGlState as restore}
 from '/modules/flow_graphic_pass_v2.mjs';
import {qualityProgram as programFactory,resetQualityPixels as resetPixels,setupQualityTexture as setupTexture}
 from '/quality/support_gpu.mjs';

const WIDTH=1080,HEIGHT=1920,BOUNDS=[0,0,2,1];
const check=(ok,code)=>{if(!ok)throw Error(code);};
function changedPixels(before,after,box=[0,0,WIDTH,HEIGHT]){
 let changed=0;
 for(let y=box[1];y<box[3];y++)for(let x=box[0];x<box[2];x++){
  const at=(y*WIDTH+x)*4;
  if(before[at]!==after[at]||before[at+1]!==after[at+1]||before[at+2]!==after[at+2]||before[at+3]!==after[at+3])changed++;
 }
 return changed;
}
const pixel=(bytes,x,y)=>[...bytes.subarray((y*WIDTH+x)*4,(y*WIDTH+x)*4+4)];
function sameState(a,b){
 if(a===b)return true;
 if(ArrayBuffer.isView(a)&&ArrayBuffer.isView(b))return a.constructor===b.constructor&&a.length===b.length&&a.every((x,i)=>x===b[i]);
 if(Array.isArray(a)||Array.isArray(b))return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((x,i)=>sameState(x,b[i]));
 if(a&&b&&Object.getPrototypeOf(a)===Object.prototype&&Object.getPrototypeOf(b)===Object.prototype){
  const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(key=>Object.hasOwn(b,key)&&sameState(a[key],b[key]));
 }
 return false;
}
async function syntheticContext(canvas,rectangle,{allLand=false,frame=9}={}){
 const [left,bottom,right,top]=rectangle,middle=Math.floor((left+right)/2),
  geo=(x,y)=>[x/WIDTH*2,y/HEIGHT],
  region=(id,a,b)=>({id,geometry:{type:'Polygon',coordinates:[[geo(a,bottom),geo(b,bottom),geo(b,top),geo(a,top),geo(a,bottom)]]}}),
  domain=[region('SYNTHETIC_PRIMARY',left,middle),region('SYNTHETIC_SECONDARY',middle,right)],
  binding=await createNativeDomainBinding({primary:domain[0].id,secondary:[domain[1].id],domain,
   geometries:domain.map(item=>({id:item.id,geometry_type:item.geometry.type,coordinates:structuredClone(item.geometry.coordinates)}))}),
  bytes=new Uint8Array(WIDTH*HEIGHT*4);
 for(let y=0;y<HEIGHT;y++)for(let x=0;x<WIDTH;x++){
  const at=(y*WIDTH+x)*4,inside=x>=left&&x<right&&y>=bottom&&y<top;
  bytes[at+3]=255;
  // Separate unselected R-only land patch is deliberately far from the
  // source-bound role union. It is not eligible for gold illumination.
  if(allLand||inside||(x>=20&&x<200&&y>=20&&y<200))bytes[at]=255;
  if(inside){
   if(x===middle-1||x===middle){bytes[at+1]=128;bytes[at+2]=127;}
   else bytes[at+(x<middle?2:1)]=255;
  }
 }
 publishNativeDomainCoverage(canvas,binding,{coverage:bytes,bounds:BOUNDS,frame,width:WIDTH,height:HEIGHT});
 const context=getNativeDomainCoverage(canvas,{frame,domainSHA256:binding.domainSHA256}),
  metadata=describeNativeDomainBinding(binding),controls={frame,localFrame:frame},
  project=point=>[point[0]/2*WIDTH,(1-point[1])*HEIGHT];
 assertOuterDomainContext(context,{controls,project,domainMetadata:metadata});
 return {context,rectangle,domainMetadata:metadata,controls,project};
}

export async function runOuterGlowABProbe(){
 const canvas=document.createElement('canvas');canvas.width=WIDTH;canvas.height=HEIGHT;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 check(gl,'REFERENCE_OUTER_PROBE_WEBGL2_REQUIRED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info'),backend=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
 check(typeof backend==='string'&&/SwiftShader/i.test(backend)&&!/NVIDIA/i.test(backend),'REFERENCE_OUTER_PROBE_SOFTWARE_ONLY');
 let pass;
 const read=()=>{
  const bytes=new Uint8Array(WIDTH*HEIGHT*4);gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);
  gl.readPixels(0,0,WIDTH,HEIGHT,gl.RGBA,gl.UNSIGNED_BYTE,bytes);gl.finish();check(gl.getError()===gl.NO_ERROR,'REFERENCE_OUTER_PROBE_READ_GL_ERROR');
  return bytes;
 };
 const clear=(whiteBox=null)=>{
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,WIDTH,HEIGHT);
  gl.disable(gl.SCISSOR_TEST);gl.disable(gl.DITHER);gl.colorMask(true,true,true,true);
  gl.clearColor(38/255,55/255,77/255,1);gl.clear(gl.COLOR_BUFFER_BIT);
  if(whiteBox){gl.enable(gl.SCISSOR_TEST);gl.scissor(whiteBox[0],whiteBox[1],whiteBox[2]-whiteBox[0],whiteBox[3]-whiteBox[1]);
   gl.clearColor(1,1,1,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.disable(gl.SCISSOR_TEST);}
 };
 const draw=(context,extra={})=>{
  const beforeState=capture(gl),diagnostic=pass.draw({context,presentationScale:1,...extra}),afterState=capture(gl);
  check(sameState(beforeState,afterState),'REFERENCE_OUTER_PROBE_STATE_CHANGED');
  check(diagnostic.glError===0&&diagnostic.sourceCoverageNeighborTaps===16&&diagnostic.singlePass===true,'REFERENCE_OUTER_PROBE_PRODUCTION_PASS_REQUIRED');
  return diagnostic;
 };
 try{
  pass=createCoverageOuterGlowPass({gl,profile:{enabled:true},capture,restore,programFactory,resetPixels,setupTexture});
  const cases=[];
  // A viewport cut through solid land must not become a fabricated coast.
  const full=await syntheticContext(canvas,[0,0,WIDTH,HEIGHT],{allLand:true});clear();let before=read();draw(full.context);let after=read();
  const fullChanged=changedPixels(before,after);check(fullChanged===0,'REFERENCE_OUTER_PROBE_VIEWPORT_EDGE_NOT_ZERO');
  cases.push({name:'SOLID_ROLE_UNION_VIEWPORT_CLIP',changedPixels:fullChanged,totalPixels:WIDTH*HEIGHT,pass:true});

  const adjacent=await syntheticContext(canvas,[240,360,840,1560]);clear();before=read();draw(adjacent.context);after=read();
  const seam=[529,600,551,1300],seamChanged=changedPixels(before,after,seam),unrelated=[20,20,200,200],
   unrelatedChanged=changedPixels(before,after,unrelated),deepInteriorChanged=changedPixels(before,after,[250,370,830,1550]);
  let farOutsideChanged=0;
  for(let y=0;y<HEIGHT;y++)for(let x=0;x<WIDTH;x++)if(x<233||x>846||y<353||y>1566){
   const at=(y*WIDTH+x)*4;if(before[at]!==after[at]||before[at+1]!==after[at+1]||before[at+2]!==after[at+2]||before[at+3]!==after[at+3])farOutsideChanged++;
  }
  check(seamChanged===0,'REFERENCE_OUTER_PROBE_SHARED_INTERNAL_OUTLINE');
  check(unrelatedChanged===0,'REFERENCE_OUTER_PROBE_R_ONLY_LAND_OUTLINE');
  check(deepInteriorChanged===0,'REFERENCE_OUTER_PROBE_INTERIOR_COLOR_CHANGED');
  check(farOutsideChanged===0,'REFERENCE_OUTER_PROBE_NONFINITE_HALO');
  const edgeBefore=pixel(before,240,800),edgeAfter=pixel(after,240,800),outside7Before=pixel(before,233,800),outside7After=pixel(after,233,800);
  check(edgeAfter[0]>edgeBefore[0]&&edgeAfter[1]>edgeBefore[1],'REFERENCE_OUTER_PROBE_OUTER_EDGE_NOT_VISIBLE');
  check(outside7Before.every((v,i)=>v===outside7After[i]),'REFERENCE_OUTER_PROBE_SUPPORT_EXCEEDED');
  cases.push({name:'ADJACENT_G_B_SOURCE_UNION',sharedSeamChangedPixels:seamChanged,unselectedRLandChangedPixels:unrelatedChanged,
   deepInteriorChangedPixels:deepInteriorChanged,farOutsideSupportChangedPixels:farOutsideChanged,
   outerEdgeBeforeRGBA:edgeBefore,outerEdgeAfterRGBA:edgeAfter,outside7PixelsUnchanged:true,pass:true});

  const asym=await syntheticContext(canvas,[120,100,420,460]);clear();before=read();draw(asym.context);after=read();
  const southChanged=changedPixels(before,after,[120,100,420,103]),northMirrorChanged=changedPixels(before,after,[120,HEIGHT-103,420,HEIGHT-100]);
  check(southChanged>0&&northMirrorChanged===0,'REFERENCE_OUTER_PROBE_SOURCE_ROW_ORIENTATION');
  cases.push({name:'ASYMMETRIC_SOUTH_ROW_ZERO',southEdgeChangedPixels:southChanged,northMirrorChangedPixels:northMirrorChanged,pass:true});

  const whiteBox=[230,780,250,820];clear(whiteBox);before=read();draw(adjacent.context);after=read();
  const whiteChanged=changedPixels(before,after,whiteBox);
  check(whiteChanged===0&&pixel(after,240,800).slice(0,3).every(v=>v===255),'REFERENCE_OUTER_PROBE_WHITE_DESTINATION_CHANGED');
  cases.push({name:'SYNTHETIC_PURE_WHITE_PATCH_AT_EDGE',changedPixels:whiteChanged,originalFrontPixelsClaimed:false,pass:true});

  clear();before=read();draw(adjacent.context,{safeArea:[260,380,820,1540]});after=read();
  const safeChanged=changedPixels(before,after);check(safeChanged===0,'REFERENCE_OUTER_PROBE_SAFE_AREA_CHANGED');
  cases.push({name:'SAFE_AREA_CLIPS_ALL_OUTER_SUPPORT',changedPixels:safeChanged,pass:true});

  const reservation=[230,HEIGHT-850,250,HEIGHT-750];clear();before=read();draw(adjacent.context,{protectedGraphics:[{box:reservation}]});after=read();
  const reservedChanged=changedPixels(before,after,[230,750,250,850]);
  check(reservedChanged===0,'REFERENCE_OUTER_PROBE_PROTECTED_RESERVATION_CHANGED');
  check(pixel(after,240,700)[0]>pixel(before,240,700)[0],'REFERENCE_OUTER_PROBE_OUTSIDE_RESERVATION_NOT_DRAWN');
  cases.push({name:'ORIGINAL_PROTECTED_GRAPHIC_RESERVATION',protectedBoxTopLeft:reservation,changedPixels:reservedChanged,
   outerEdgeOutsideReservationVisible:true,pass:true});

  return {schema:'REFERENCE_OUTER_GLOW_ACTUAL_SOFTWARE_AB_V2',status:'PASS',testOnly:true,softwareBackend:backend,
   softwareWebGLDrawExecuted:true,actualReadPixelsCompared:true,actualShaderCompile:true,physicalNvidiaExecuted:false,
   gpuRenderingVerified:false,productionRenderAllowed:false,fixtureSource:'SYNTHETIC_SOURCE_ROLE_COVERAGE_ONLY',
   realCoastAlignmentVerified:false,publicProofGenerated:false,output:[WIDTH,HEIGHT],
   caseCount:cases.length,cases,originalHelperSourcesReused:true,productionCoveragePassUsed:true,
   originalDisabledPipelineComparisonScope:'SEPARATE_FULL_PIPELINE_SOFTWARE_PROBE',visualQualityApproved:false};
 }finally{
  pass?.dispose();clearNativeDomainCoverage(canvas);gl.getExtension('WEBGL_lose_context')?.loseContext();
 }
}
