/** TEST TOOL ONLY: production gain/old-F territory constructors on original
 * scalar-field geometry, measured with actual SwiftShader draw/readPixels. */
import {createTerritoryControlPass as createGain} from './gain_territory.mjs';
import {createTerritoryControlPass as createOldF} from '/quality/quality_territory.mjs?baseline';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '/modules/territory_control_adapter_v1.mjs';
import {compositeTerritorySample} from '/quality/territory_style_core.mjs';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),check=(value,code)=>{if(!value)throw Error(code);};
const near=(a,b,tolerance=1)=>a.every((value,index)=>Math.abs(value-b[index])<=tolerance);
const rgba=rgb=>rgb.map(value=>Math.round(value*255));
export async function runGainABProbe(){
 const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 check(gl,'REFERENCE_GAIN_TEST_WEBGL2_REQUIRED');const ext=gl.getExtension('WEBGL_debug_renderer_info'),
  renderer=ext&&gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
 check(typeof renderer==='string'&&/SwiftShader/i.test(renderer),'REFERENCE_GAIN_TEST_SWIFTSHADER_ONLY');
 const intent={version:'TERRITORY_CONTROL_INTENT_V1',semantic_mode:'REFERENCE_VISUAL_STUDY',
  source:{source_type:'SYNTHETIC_TEST',source_reference:'REFERENCE_V2_PRODUCTION_GAIN_CLASSIFIER_PIXEL_TEST',verification_status:'TEST_ONLY'},
  domain:[{id:'ARBITRARY_DOMAIN',geometry:{type:'Polygon',coordinates:[[[-2,-2],[2,-2],[2,2],[-2,2],[-2,-2]]]}}],
  factions:{winner:{id:'WINNER'},loser:{id:'LOSER'}},longitudinal_knots:[-2,2],base_boundary_latitudes:[-1,-1],
  boundary_keyframes:[{frame:0,latitudes:[-1,-1]},{frame:19,latitudes:[1,1]}],advance_direction:'POSITIVE_LATITUDE',
  start_frame:0,total_frames:20,fps:30,interpolation:'LINEAR'},
  sourceStyle={profileName:'TEST_ONLY_GENERIC_GAIN_PALETTE',losingColor:[.7,.2,.1,.65],
   existingWinningColor:[.1,.2,.7,.65],gainedWinningColor:[.1,.2,.7,.65],
   interfaceColor:[0,0,0,0],interfaceWidthPixels:0,sharedDomainBoundary:'PRESERVE_ALL_NATIVE_COUNTRY_BOUNDARIES'},
  originalBinding=JSON.stringify({intent,sourceStyle}),plan=compileTerritoryControlPlan(intent),
  project=point=>[(point[0]+3)/6*1080,(3-point[1])/6*1920],
  points={held:[0,-1.5],gained:[0,.5],loser:[0,1.5],outside:[2.5,0]},
  low=[.1,.12,.08],high=[.4,.42,.38];
 let oldPass,newPass;
 const read=point=>{const [x,y]=project(point),pixels=new Uint8Array(4);gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);
  gl.readBuffer(gl.BACK);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);gl.pixelStorei(gl.PACK_ALIGNMENT,1);
  gl.pixelStorei(gl.PACK_ROW_LENGTH,0);gl.pixelStorei(gl.PACK_SKIP_PIXELS,0);gl.pixelStorei(gl.PACK_SKIP_ROWS,0);
  gl.readPixels(Math.floor(x),1919-Math.floor(y),1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixels);return [...pixels.slice(0,3)];};
 const draw=(pass,frame,background)=>{
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,1080,1920);
  gl.disable(gl.SCISSOR_TEST);gl.disable(gl.BLEND);gl.colorMask(true,true,true,true);
  gl.clearColor(...background,1);gl.clear(gl.COLOR_BUFFER_BIT);
  const controls=evaluateTerritoryControlFrame(plan,frame),diagnostic=pass.draw({controls,project,safeArea:[0,0,1080,1920],
   protectedGraphics:[],boundarySegments:[],internalBoundarySegments:[]});gl.finish();
  check(gl.getError()===gl.NO_ERROR,'REFERENCE_GAIN_TEST_GL_ERROR');
  return {frame,diagnostic,pixels:Object.fromEntries(Object.entries(points).map(([role,point])=>[role,read(point)])),
   regions:Object.fromEntries(Object.entries(points).map(([role,point])=>[role,classifyControlPoint(controls,point).region]))};
 };
 try{
  oldPass=createOldF({canvas,landDomain:intent.domain,style:sourceStyle});
  newPass=createGain({canvas,landDomain:intent.domain,style:sourceStyle});
  check(newPass.evidence.gainTerritory?.actualFactorySelected===true,'REFERENCE_GAIN_TEST_ACTUAL_FACTORY_REQUIRED');
  const old=draw(oldPass,19,low),active=draw(newPass,19,low),raised=draw(newPass,19,high),first=draw(newPass,0,low),
   oldStyle=oldPass.evidence.qualityTerritory.effectiveStyle,
   effective=newPass.evidence.qualityTerritory.effectiveStyle;
  check(active.regions.held==='WINNER_EXISTING'&&active.regions.gained==='WINNER_GAINED'
   &&active.regions.loser==='LOSER'&&active.regions.outside==='OUTSIDE_DOMAIN','REFERENCE_GAIN_TEST_ORIGINAL_CLASSIFIER_REQUIRED');
  check(first.regions.gained==='LOSER','REFERENCE_GAIN_TEST_CUMULATIVE_CHANGE_REQUIRED');
  for(const role of ['held','loser','outside'])check(near(old.pixels[role],active.pixels[role]),'REFERENCE_GAIN_TEST_PROTECTED_ROLE_CHANGED_'+role);
  check(!near(old.pixels.gained,active.pixels.gained,1),'REFERENCE_GAIN_TEST_GAIN_MUST_CHANGE_ACTUAL_PIXELS');
  for(const [role,color]of [['held',effective.existingWinningColor],['gained',effective.gainedWinningColor],['loser',effective.losingColor]])
   check(near(active.pixels[role],rgba(compositeTerritorySample(low,color)),2),'REFERENCE_GAIN_TEST_ACTUAL_BLEND_MISMATCH_'+role);
  check(near(active.pixels.outside,rgba(low),1),'REFERENCE_GAIN_TEST_OUTSIDE_DOMAIN_CHANGED');
  const retained=raised.pixels.gained.map((value,index)=>value-active.pixels.gained[index]),
   expected=(high[0]-low[0])*(1-effective.gainedWinningColor[3])*255;
  check(retained.every(value=>Math.abs(value-expected)<=2),'REFERENCE_GAIN_TEST_TERRAIN_RETENTION_MISMATCH');
  check(near(first.pixels.gained,rgba(compositeTerritorySample(low,effective.losingColor)),2),
   'REFERENCE_GAIN_TEST_FIRST_FRAME_NOT_ORIGINAL_LOSER');
  check(same({intent,sourceStyle},JSON.parse(originalBinding)),'REFERENCE_GAIN_TEST_SOURCE_MUTATED');
  return {schema:'REFERENCE_V2_GAIN_ACTUAL_SOFTWARE_AB_V1',status:'PASS',testOnly:true,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,actualDrawExecuted:true,actualReadPixelsExecuted:true,
   productionGainFactorySelected:true,originalClassifierUsed:true,heldAndLosingPixelsUnchanged:true,outsideDomainUnchanged:true,
   cumulativeGainVerified:true,retainedBackgroundVerified:true,oldFMaterial:oldStyle,effectiveMaterial:effective,
   samplePixels:{old:old.pixels,active:active.pixels,raised:raised.pixels,first:first.pixels},
   regions:active.regions,retainedBackgroundDifference:retained,expectedBackgroundDifference:expected,
   sourceStyleAndGeometryUnchanged:true,noDataPolicy:'NO_SOURCE_DATA_IN_THIS_GIS_MATERIAL_TEST_SEPARATE_SOURCE_GRADE_PROBE_REQUIRED',
   renderedText:false,newLines:false,newArrows:false,videoQualityApproved:false,renderer};
 }finally{oldPass?.dispose();newPass?.dispose();gl.getExtension('WEBGL_lose_context')?.loseContext();}
}
