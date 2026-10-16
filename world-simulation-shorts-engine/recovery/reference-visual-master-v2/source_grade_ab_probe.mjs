/** Explicit TEST TOOL. Authenticated synthetic source upload -> production
 * source-grade pass -> original frontier draw. SwiftShader only; no video,
 * external data acquisition, production job or NVIDIA claim. */
import {loadUploadBundle,describeUploadBundle,createUploadTextures} from '/astra-upload/gpu_upload.mjs';
import {captureFlowNativeGlState as capture,restoreFlowNativeGlState as restore} from '/modules/flow_graphic_pass_v2.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame} from '/modules/territory_control_adapter_v1.mjs';
import {createControlFrontierLightPassV3,controlTerrainLightingFactor} from '/modules/reference_control_frontier_light_v3.mjs?baseline';
import {createReferenceSourceGradePass} from './source_grade_pass.mjs';
import {gradeSourceRgb} from './source_grade_core.mjs';
const check=(ok,code)=>{if(!ok)throw Error(code);};
const sha=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
async function verifiedBytes(url,expected,limit){
 const target=new URL(url,location.origin);check(target.origin===location.origin&&!target.username&&!target.password&&!target.hash,'TEST_SOURCE_SAME_ORIGIN_REQUIRED');
 check(/^[a-f0-9]{64}$/.test(expected),'TEST_SOURCE_SHA_REQUIRED');
 const response=await fetch(target.href,{redirect:'error',cache:'no-store',credentials:'same-origin'});
 check(response.ok&&!response.redirected&&response.body?.getReader,'TEST_SOURCE_BOUNDED_FETCH_REQUIRED');
 const chunks=[],reader=response.body.getReader();let length=0;
 try{for(;;){const {value,done}=await reader.read();if(done)break;length+=value.length;
   if(length>limit){await reader.cancel();throw Error('TEST_SOURCE_RESPONSE_LIMIT');}chunks.push(value);}}
 finally{reader.releaseLock();}
 const bytes=new Uint8Array(length);let offset=0;for(const part of chunks){bytes.set(part,offset);offset+=part.length;}
 check(await sha(bytes)===expected,'TEST_SOURCE_ARTIFACT_SHA_MISMATCH');return bytes;
}
function makeBaseline(gl,width,height,color){
 const before=capture(gl),texture=gl.createTexture();let disposed=false;
 check(texture,'TEST_SOURCE_SNAPSHOT_ALLOCATION');
 try{gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
  for(const key of ['TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.NEAREST);
  for(const key of ['TEXTURE_WRAP_S','TEXTURE_WRAP_T'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.CLAMP_TO_EDGE);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGB8,width,height);
 }finally{restore(gl,before);}
 return {evidence:{version:'SYNTHETIC_CONSTANT_SOURCE_RGB8'},get outputTexture(){return texture;},draw(args){
  const state=capture(gl);try{
   gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,width,height);
   gl.disable(gl.SCISSOR_TEST);gl.disable(gl.DITHER);gl.colorMask(true,true,true,true);gl.clearColor(...color,1.);gl.clear(gl.COLOR_BUFFER_BIT);
   gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
   gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);
  }finally{restore(gl,state);}check(gl.getError()===gl.NO_ERROR,'TEST_SOURCE_BASELINE_GL_ERROR');
  return {version:'SYNTHETIC_CONSTANT_SOURCE_RGB8',frame:args.frame,bounds:[...args.bounds]};
 },dispose(){if(disposed)return;gl.deleteTexture(texture);disposed=true;}};
}
function syntheticPlan(bounds){
 const [w,s,e,n]=bounds,mid=(s+n)/2,ring=[[w,s],[e,s],[e,n],[w,n],[w,s]];
 return compileTerritoryControlPlan({semantic_mode:'REFERENCE_VISUAL_STUDY',
  source:{source_type:'SYNTHETIC_TEST',source_reference:'fixture://source-grade-consumer-v2',verification_status:'SYNTHETIC_TEST'},
  domain:[{id:'SYNTHETIC_DOMAIN',geometry:{type:'Polygon',coordinates:[ring]}}],
  factions:{winner:{id:'SYNTHETIC_A'},loser:{id:'SYNTHETIC_B'}},longitudinal_knots:[w,e],base_boundary_latitudes:[mid-.0001,mid-.0001],
  boundary_keyframes:[{frame:0,latitudes:[mid,mid]},{frame:1,latitudes:[mid+.0001,mid+.0001]}],
  advance_direction:'POSITIVE_LATITUDE',start_frame:0,total_frames:2,fps:30,interpolation:'LINEAR'});
}
export async function runSourceGradeABProbe({manifestURL,expectedManifestSha256,fixtureURL,expectedFixtureSha256}={}){
 const descriptorBytes=await verifiedBytes(fixtureURL,expectedFixtureSha256,65536),fixture=JSON.parse(new TextDecoder().decode(descriptorBytes));
 check(fixture.schema==='REFERENCE_SOURCE_GRADE_SYNTHETIC_FIXTURE_V2'&&fixture.testOnly===true
  &&fixture.sourceClassification==='SYNTHETIC_TEST_NOT_REAL_WORLD_DATA'&&fixture.manifestSha256===expectedManifestSha256,'TEST_SOURCE_EXPLICIT_FIXTURE_REQUIRED');
 const bundle=await loadUploadBundle({manifestURL,expectedManifestSha256,origin:location.origin,maxBytes:1024*1024}),
  manifest=describeUploadBundle(bundle),canvas=document.createElement('canvas'),[width,height]=fixture.dimensions;
 check(width===1080&&height===1920&&bundle.partCount===3,'TEST_SOURCE_CANONICAL_THREE_ROLE_FIXTURE_REQUIRED');
 canvas.width=width;canvas.height=height;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});check(gl,'TEST_SOURCE_WEBGL2_REQUIRED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info'),renderer=debug&&gl.getParameter(debug.UNMASKED_RENDERER_WEBGL);
 check(typeof renderer==='string'&&/SwiftShader/i.test(renderer),'TEST_SOURCE_SWIFTSHADER_ONLY');
 const bounds=fixture.cameraBounds,point=geo=>[
  Math.max(0,Math.min(width-1,Math.floor((geo[0]-bounds[0])/(bounds[2]-bounds[0])*width))),
  Math.max(0,Math.min(height-1,Math.floor((geo[1]-bounds[1])/(bounds[3]-bounds[1])*height)))],
 read=(name)=>{const [x,y]=point(fixture.points[name]),state=capture(gl),out=new Uint8Array(4);
  try{gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
   gl.pixelStorei(gl.PACK_ALIGNMENT,1);gl.pixelStorei(gl.PACK_ROW_LENGTH,0);gl.pixelStorei(gl.PACK_SKIP_PIXELS,0);gl.pixelStorei(gl.PACK_SKIP_ROWS,0);
   gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,out);
  }finally{restore(gl,state);}check(gl.getError()===gl.NO_ERROR,'TEST_SOURCE_READPIXELS_ERROR');return [...out];},
 nativeCoverage=land=>{const bytes=new Uint8Array(width*height*4);for(let i=0;i<width*height;i++){bytes[i*4]=land;bytes[i*4+3]=255;}return bytes;},
 project=geo=>[(geo[0]-bounds[0])/(bounds[2]-bounds[0])*width,(bounds[3]-geo[1])/(bounds[3]-bounds[1])*height],
 baseArgs={bounds,frame:0,fps:30},cases={};
 let allocated,frontier,activePass;
 const profileBase={enabled:true,terrainLocalContrast:1,landExposure:1,oceanExposure:1,oceanTealMix:0,screenFeatherPixels:32};
 try{
  allocated=createUploadTextures(gl,bundle);
  const uploads=()=>Object.freeze({...allocated,testOnly:true,dispose(){}}),
   construct=(color,profile)=>createReferenceSourceGradePass({gl,baseline:makeBaseline(gl,width,height,color),uploads:uploads(),profile,
    width,height,oceanTint:fixture.oceanTint,capture,restore});
  activePass=construct([1,1,1],{...profileBase,oceanExposure:1.2});
  activePass.draw({...baseArgs,coverage:nativeCoverage(255)});
  const outside=read('outside'),noData=read('noData');
  check(same(outside,[255,255,255,255]),'TEST_SOURCE_ZERO_SUPPORT_WHITE_NOT_EXACT');
  check(same(noData,[255,255,255,255]),'TEST_SOURCE_INTERNAL_NODATA_WHITE_NOT_EXACT');
  cases.zeroSupportWhite={result:'PASS',actualRGBA:outside};cases.internalNoDataWhite={result:'PASS',actualRGBA:noData};
  const supportedWhiteLand=read('validLand');check(same(supportedWhiteLand,[255,255,255,255]),'TEST_SOURCE_NEUTRAL_LAND_WHITE_CLIPPED_BY_OCEAN_PROFILE');
  cases.supportedWhiteLandOceanOnly={result:'PASS',actualRGBA:supportedWhiteLand};
  const sourceMasks=activePass.evidence.sourceGrade.supportMasks,memory=activePass.evidence.sourceGrade.memory;
  activePass.dispose();activePass=null;
  activePass=construct([1,1,1],{...profileBase,landExposure:1.2});
  activePass.draw({...baseArgs,coverage:nativeCoverage(0)});
  const supportedWhiteOcean=read('validOcean');check(same(supportedWhiteOcean,[255,255,255,255]),'TEST_SOURCE_NEUTRAL_OCEAN_WHITE_CLIPPED_BY_LAND_PROFILE');
  cases.supportedWhiteOceanLandOnly={result:'PASS',actualRGBA:supportedWhiteOcean};activePass.dispose();activePass=null;
  const oceanProfile={...profileBase,oceanExposure:1.4,oceanTealMix:.12};
  activePass=construct([.2,.25,.3],oceanProfile);
  activePass.draw({...baseArgs,coverage:nativeCoverage(255)});
  const original=read('noData'),negativeLand=read('negativeDemLand');
  check(same(negativeLand,original),'TEST_SOURCE_NEGATIVE_DEM_LAND_MISREAD_AS_OCEAN');
  cases.negativeDemLand={result:'PASS',actualRGBA:negativeLand,baselineRGBA:original,nativeLandCoverage:255,sourceHeightMeters:-30};
  activePass.draw({...baseArgs,coverage:nativeCoverage(0)});
  const positiveOcean=read('positiveGebcoOcean'),validOcean=read('validOcean');
  check(same(positiveOcean,original),'TEST_SOURCE_POSITIVE_GEBCO_OCEAN_NOT_FALLBACK');
  check(!same(validOcean,original),'TEST_SOURCE_VALID_OCEAN_GRADE_NOT_DRAWN');
  cases.positiveGebcoOcean={result:'PASS',actualRGBA:positiveOcean,baselineRGBA:original,sourceSignedElevation:12};
  cases.validOceanGrade={result:'PASS',actualRGBA:validOcean,baselineRGBA:original};
  activePass.draw({...baseArgs,coverage:nativeCoverage(128)});
  const fractional=read('validLand'),fractionOracle=gradeSourceRgb(original.slice(0,3).map(v=>v/255),
   {coverage:128/255,landSupport:1,oceanSupport:1,interiorLand:false,oceanTint:fixture.oceanTint},oceanProfile).map(v=>Math.round(v*255));
  check(fractional.slice(0,3).every((value,i)=>Math.abs(value-fractionOracle[i])<=1),'TEST_SOURCE_FRACTIONAL_COAST_ORACLE_MISMATCH');
  cases.fractionalCoast={result:'PASS',actualRGBA:fractional,oracleRGB:fractionOracle,nativeLandCoverage:128,maximumOracleToleranceLSB:1};
  activePass.dispose();activePass=null;
  const baseline=makeBaseline(gl,width,height,[.2,.25,.3]);
  activePass=createReferenceSourceGradePass({gl,baseline,uploads:uploads(),profile:{...profileBase,landExposure:1.2},
   width,height,oceanTint:fixture.oceanTint,capture,restore});
  activePass.draw({...baseArgs,coverage:nativeCoverage(255)});
  const gradedSource=read('validLand'),ungradedSource=read('noData');
  check(!same(gradedSource,ungradedSource),'TEST_SOURCE_VALID_LAND_GRADE_NOT_DRAWN');
  cases.validLandGrade={result:'PASS',actualRGBA:gradedSource,baselineRGBA:ungradedSource};
  const plan=syntheticPlan(bounds),controls=evaluateTerritoryControlFrame(plan,0),lightProfile={profileName:'TEST_ONLY_SOURCE_TEXTURE_CONSUMER',
   centerAlpha:0,haloAlpha:0,minimumLightingFactor:.5,luminanceAnchor:.8,reliefLightingEnabled:true};
  frontier=await createControlFrontierLightPassV3({canvas,width,height,territoryPlan:plan,landDomain:plan.intent.domain,profile:lightProfile});
  const destination=()=>{const state=capture(gl);try{gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
   gl.disable(gl.SCISSOR_TEST);gl.disable(gl.DITHER);gl.colorMask(true,true,true,true);gl.clearColor(.6,.4,.3,1.);gl.clear(gl.COLOR_BUFFER_BIT);
  }finally{restore(gl,state);}return read('validLand');},
   oldDestination=destination(),oldDiagnostic=frontier.draw({controls,project,actualTerrainTexture:baseline.outputTexture,presentationScale:1}),
   oldPixel=read('validLand'),newDestination=destination(),newDiagnostic=frontier.draw({controls,project,actualTerrainTexture:activePass.outputTexture,presentationScale:1}),
   newPixel=read('validLand'),oldFactor=controlTerrainLightingFactor(ungradedSource.slice(0,3).map(v=>v/255),lightProfile),
   newFactor=controlTerrainLightingFactor(gradedSource.slice(0,3).map(v=>v/255),lightProfile),
   oldOracle=oldDestination.slice(0,3).map(v=>Math.round(v*oldFactor)),newOracle=newDestination.slice(0,3).map(v=>Math.round(v*newFactor));
  check(oldDiagnostic.actualTerrainSnapshotConsumed===true&&newDiagnostic.actualTerrainSnapshotConsumed===true,'TEST_SOURCE_ORIGINAL_FRONTIER_DID_NOT_CONSUME_TEXTURE');
  check(oldPixel.slice(0,3).every((v,i)=>Math.abs(v-oldOracle[i])<=2)&&newPixel.slice(0,3).every((v,i)=>Math.abs(v-newOracle[i])<=2),
   'TEST_SOURCE_FRONTIER_REAL_PIXEL_ORACLE_MISMATCH');
  check(newPixel.some((v,i)=>i<3&&v>oldPixel[i]),'TEST_SOURCE_NEW_COMBINED_TEXTURE_NOT_VISIBLE_TO_FRONTIER');
  cases.originalFrontierConsumesGradedTexture={result:'PASS',oldPixel,newPixel,oldOracle,newOracle,oldFactor,newFactor,
   oldSourceRGBA:ungradedSource,gradedSourceRGBA:gradedSource,maximumOracleToleranceLSB:2,
   originalFrontierFactoryUsed:true,actualTerrainSnapshotConsumed:true,gradedOutputTextureUsed:true};
  const artifacts=[];
  for(const item of manifest.artifacts){const bytes=await verifiedBytes(new URL(item.file,new URL(manifestURL,location.origin)).href,item.sha256,item.bytes);
   check(bytes.length===item.bytes,'TEST_SOURCE_POST_ARTIFACT_SIZE_CHANGED');artifacts.push({file:item.file,sha256:item.sha256,unchanged:true});}
  return {schema:'REFERENCE_SOURCE_GRADE_ACTUAL_SOFTWARE_PROBE_V2',testOnly:true,renderer,
   fixtureClassification:'AUTHENTICATED_SYNTHETIC_CPU_PRODUCER_BUNDLE_NOT_SUPPLIER_DATA',bundleManifestSHA256:expectedManifestSha256,
   artifactHashesAfter:artifacts,rawValuesMaskCoordinatesUnchanged:true,sourceMasks,memory,cases,
   actualUploadExecuted:true,actualDrawExecuted:true,actualReadPixelsExecuted:true,nvidiaHardwareVerified:false,videoQualityApproved:false};
 }finally{frontier?.dispose();activePass?.dispose();allocated?.dispose();gl.getExtension('WEBGL_lose_context')?.loseContext();}
}
