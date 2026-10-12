#!/usr/bin/env node
/** Native 1080x1920 framebuffer measurement; never edits the map or source data.
 * V1 styling and every generic V2 palette candidate use the unchanged Event
 * raster pass on the production geometry, camera, terrain and Marker masks.
 */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {repo,runtime,WIDTH,HEIGHT,CAMERA_FRAME,productionFixture,V1_ON_REPORT,
 inventory,openRuntime,json,writeJson} from './candidate_runtime.mjs';
const execute=promisify(execFile);

function options(){
 const args=process.argv.slice(2);
 if(args.length!==2||args[0]!=='--output-dir'||!args[1])throw Error('USAGE: --output-dir NEW_EXCLUSIVE_DIRECTORY');
 const out=path.resolve(args[1]);
 if(out===repo||out===runtime)throw Error('NEW_EXCLUSIVE_MEASUREMENT_DIRECTORY_REQUIRED');
 return {out};
}

async function main(){
 const {out}=options();await mkdir(path.dirname(out),{recursive:true});await mkdir(out);
 const inputs=await inventory(),fixture=await json(path.join(repo,productionFixture));
 const v1=await json(path.join(repo,V1_ON_REPORT));
 const {stdout:head}=await execute('git',['rev-parse','HEAD'],{cwd:repo});
 const report={schema:1,phase:'visual-measurement',status:'STARTED',source_commit:head.trim(),
  state:'EVENT_SYSTEM_V1_CANDIDATE_V2',event_final:false,user_video_review:'USER_VIDEO_REVIEW_REQUIRED',
  output:[WIDTH,HEIGHT],cameraFrame:CAMERA_FRAME,eventFrame:74,required_inputs:inputs,
  started_at_utc:new Date().toISOString(),errors:[],frames:[],
  command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()}};
 let session;
 try{
  session=await openRuntime({fixture});
  const clean=await session.page.evaluate(frame=>window.eventCandidate.cleanReference(frame),CAMERA_FRAME);
  const actualRuntime=await session.page.evaluate(({cameraFrame,eventFrame})=>
   window.eventCandidate.capture(cameraFrame,eventFrame),{cameraFrame:CAMERA_FRAME,eventFrame:74});
  report.runtime={backend:session.info.backend,chromium:'154.0.8037.57',node:process.version,
   raw_rgba_sha256:actualRuntime.raw_rgba_sha256,eventStyle:actualRuntime.eventStyle,
   line:actualRuntime.line};
  const measured=await session.page.evaluate(async({fixture,clean,runtimeRow,v1Expected})=>{
   const THREE=await import('/three.js');
   const {createMapInfographicRenderer}=await import('/modules/renderer.mjs');
   const {createMovingGraphicPass}=await import('/modules/graphic_motion_pass_v4.mjs');
   const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
   const {compileGeographicLinePrimitive}=await import('/modules/event_line_v1.mjs');
   const {createEventLinePass}=await import('/modules/event_line_pass_v1.mjs');
   const {selectEventLineStyle,EVENT_LINE_COLOR_CANDIDATES_SRGB,contrastRatioSrgb,
    relativeLuminanceSrgb,oklabSrgb}=await import('/modules/event_style_v1.mjs');
   const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('MEASUREMENT_INPUT_HTTP_'+r.status);return r.json();};
   const [regional,continent,input]=await Promise.all([
    load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/input-manifest.json')]);
   const frozenInputs=JSON.stringify({regional,continent,input,fixture});
   const d=clean.diagnostic,width=1080,height=1920,canvas=document.createElement('canvas');
   document.body.appendChild(canvas);
   const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
   const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
   renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
   renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
   let factory,graphics;
   const fail=(condition,message)=>{if(!condition)throw Error(message);};
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
    .map(x=>x.toString(16).padStart(2,'0')).join('');
   const quantile=(values,f)=>{const sorted=[...values].sort((a,b)=>a-b),at=(sorted.length-1)*f;
    const low=Math.floor(at),t=at-low;return sorted[low]*(1-t)+sorted[Math.min(low+1,sorted.length-1)]*t;};
   const stats=values=>({minimum:Math.min(...values),p10:quantile(values,.1),median:quantile(values,.5),
    mean:values.reduce((a,b)=>a+b,0)/values.length,maximum:Math.max(...values)});
   const rgb=(bytes,x,y)=>{
    const px=Math.max(0,Math.min(width-1,Math.floor(x))),py=Math.max(0,Math.min(height-1,Math.floor(y)));
    const at=((height-1-py)*width+px)*4;return [bytes[at]/255,bytes[at+1]/255,bytes[at+2]/255];
   };
   const bilinear=(bytes,x,y)=>{
    const px=x-.5,py=y-.5,ix=Math.floor(px),iy=Math.floor(py),fx=px-ix,fy=py-iy;
    const a=rgb(bytes,ix,iy),b=rgb(bytes,ix+1,iy),c=rgb(bytes,ix,iy+1),e=rgb(bytes,ix+1,iy+1);
    return a.map((value,i)=>(value*(1-fx)+b[i]*fx)*(1-fy)+(c[i]*(1-fx)+e[i]*fx)*fy);
   };
   const pixelAt=(x,y)=>((height-1-Math.floor(y))*width+Math.floor(x))*4;
   const pixelDistance=(point,a,b)=>{
    const ab=[b[0]-a[0],b[1]-a[1]],length2=ab[0]**2+ab[1]**2;
    const t=Math.max(0,Math.min(1,((point[0]-a[0])*ab[0]+(point[1]-a[1])*ab[1])/Math.max(length2,1e-12)));
    return Math.hypot(point[0]-a[0]-ab[0]*t,point[1]-a[1]-ab[1]*t);
   };
   const inside=(x,y,box,padding=0)=>x>=box[0]-padding&&x<=box[2]+padding&&y>=box[1]-padding&&y<=box[3]+padding;
   const expectedStyle=runtimeRow.eventStyle;
   fail(expectedStyle?.selection,'RUNTIME_AUTOMATIC_STYLE_DIAGNOSTIC_REQUIRED');
   try{
    factory=await createMapInfographicRenderer({canvas,plan:regional,layoutPlan:regional,
     contextTerrain:input.contextTerrain??continent.assets.terrain,contextGeometries:continent.geometries,
     heightSource:input.heightSource,width,height,outputRenderer:renderer,outputTarget:null});
    graphics=await createMovingGraphicPass({renderer,factory,width,height});
    factory.updateCamera(d.gpu.actualCamera.bounds);factory.setScaleVisual(d.gpu.boundaryPixels);
    factory.setTerrainLod(d.gpu.terrainLod.weight);
    const params={dem:true,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL',
     graphics:false,reveal:d.reveal,primaryMaterial:1};
    const native=()=>{factory.renderFrame(params);graphics.draw({items:d.gpu.layout,reveal:d.reveal});gl.finish();
     const bytes=factory.readPixels();fail(gl.getError()===0,'NATIVE_MEASUREMENT_GL_ERROR');return bytes;};
    const base=native(),baseHash=await digest(base);
    fail(baseHash===clean.raw_rgba_sha256,'PRODUCTION_NATIVE_FRAMEBUFFER_IDENTITY_FAILED');
    const coverage=factory.coverage(),nativeGlow=factory.glowPixels();
    // Existing public probe is a separate diagnostic draw. The base is restored
    // immediately and is never modified to improve a candidate's contrast.
    factory.boundaryLayerProbe();gl.finish();const nativeBoundary=factory.readPixels();
    fail(await digest(native())===baseHash,'NATIVE_BASE_RESTORE_FAILED');
    const primitive=compileGeographicLinePrimitive(compileEventIntent(fixture.intent),{project:p=>factory.screen(p)});
    fail(JSON.stringify(primitive.screenCoordinates)===JSON.stringify(runtimeRow.line.path),
     'RUNTIME_LINE_GEOMETRY_DIFFERS_FROM_NATIVE_PROJECTED_GEOMETRY');
    const role=fixture.intent.line.style_role,prefix=role==='PRIMARY'?'primary':'secondary';
    const baselineStyle={width:regional.theme[prefix+'Width'],coreColor:regional.theme[prefix+'CoreColor'],
     glowRadius:regional.theme.glowRadius,glowGain:regional.theme.glowGain,glowColor:regional.theme.glowColor};
    const support=Math.max(baselineStyle.width/2+baselineStyle.glowRadius,
     expectedStyle.width/2+expectedStyle.glowRadius)+3;
    const protectedBoxes=runtimeRow.protectedBoxes;
    // Read the safe area from the unchanged native contract, never geography.
    const {compileMovingLayoutContract}=await import('/modules/moving_layout_v4.mjs');
    const contract=compileMovingLayoutContract({regionalPlan:regional,measuredLayout:factory.evidence.layout});
    const nativeSafeArea=contract.safeArea;
    const protectedGraphics=runtimeRow.protectedGraphics??d.gpu.layout.map((item,index)=>({
     kind:item.role==='MARKER'&&item.kind!=='TEXT'&&item.kind!=='PANEL'?'MARKER':item.kind==='TEXT'?'TEXT':'PANEL',
     box:protectedBoxes[index]}));
    const draw=(style,{coreOnly=false}={})=>{
     factory.renderFrame(params);
     const pass=createEventLinePass({renderer,width,height,style:coreOnly?{...style,glowGain:0}:style});
     const line=pass.draw({primitive,visibleFraction:1,safeArea:nativeSafeArea,protectedGraphics});
     graphics.draw({items:d.gpu.layout,reveal:d.reveal});gl.finish();const bytes=factory.readPixels();pass.dispose();
     fail(gl.getError()===0,'CANDIDATE_MEASUREMENT_GL_ERROR');return {bytes,line};
    };
    const validRaster=(x,y,{boundaryGuard=true}={})=>{
     if(x<support||y<support||x>=width-support||y>=height-support)return false;
     if(!inside(x,y,nativeSafeArea))return false;
     if(protectedBoxes.some(box=>inside(x,y,box,2)))return false;
     const at=pixelAt(x,y);if(coverage[at+2]<254)return false;
     if(boundaryGuard&&(nativeBoundary[at]+nativeBoundary[at+1]+nativeBoundary[at+2]>0||
      nativeGlow[at]+nativeGlow[at+1]+nativeGlow[at+2]>3))return false;
     return true;
    };
    const profilePoints=[];
    for(let segment=0;segment<primitive.segmentLengthsPixels.length;segment++){
     const a=primitive.screenCoordinates[segment],b=primitive.screenCoordinates[segment+1],length=primitive.segmentLengthsPixels[segment];
     if(length<4)continue;
     const normal=[-(b[1]-a[1])/length,(b[0]-a[0])/length];
     for(const fraction of [.3,.5,.7]){
      const point=[a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction];
      if(Math.min(length*fraction,length*(1-fraction))<2)continue;
      if(protectedBoxes.some(box=>inside(...point,box,support+2)))continue;
      if(profilePoints.some(item=>Math.hypot(item.point[0]-point[0],item.point[1]-point[1])<2))continue;
      let valid=true;
      for(let offset=-support;offset<=support;offset+=.5){
       const x=point[0]+normal[0]*offset,y=point[1]+normal[1]*offset;
       if(!validRaster(x,y)){valid=false;break;}
       // Dense supplied polylines can have several collinear vertices inside
       // one core diameter. Reject another segment only when it is closer to
       // the profile pixel than this section's own perpendicular distance.
       // An ordinary collinear neighbor cannot widen the measured profile.
       for(let other=0;other<primitive.segmentLengthsPixels.length;other++)if(Math.abs(other-segment)>1&&
        pixelDistance([x,y],primitive.screenCoordinates[other],primitive.screenCoordinates[other+1])<Math.abs(offset)-.25){valid=false;break;}
       if(!valid)break;
      }
      if(valid)profilePoints.push({segment,point,normal,segmentLengthPixels:length,fraction});
     }
    }
    fail(profilePoints.length>=3,'INSUFFICIENT_UNOCCLUDED_PRIMARY_CROSS_SECTIONS');
    // Raster centers within 0.5px of the true production path are fully in the
    // core of every candidate. Compare identical pixel locations for all colors.
    const centerPixels=[];
    for(let y=Math.floor(runtimeRow.line.roi[1]);y<=Math.ceil(runtimeRow.line.roi[3]);y++)
     for(let x=Math.floor(runtimeRow.line.roi[0]);x<=Math.ceil(runtimeRow.line.roi[2]);x++){
      const p=[x+.5,y+.5];if(!validRaster(...p))continue;
      const distance=Math.min(...primitive.segmentLengthsPixels.map((_,i)=>
       pixelDistance(p,primitive.screenCoordinates[i],primitive.screenCoordinates[i+1])));
      if(distance<=.5)centerPixels.push(p);
     }
    fail(centerPixels.length>=8,'INSUFFICIENT_ACTUAL_PRIMARY_CORE_PIXELS');
    const labs=centerPixels.map(([x,y])=>oklabSrgb(rgb(base,x,y)));
    const materialLab=oklabSrgb(regional.theme.primary);
    const measureContrast=(bytes,style,name,family)=>{
     const backgrounds=centerPixels.map(([x,y])=>rgb(base,x,y));
     const rendered=centerPixels.map(([x,y])=>rgb(bytes,x,y));
     const luminanceContrast=stats(rendered.map((color,index)=>contrastRatioSrgb(color,backgrounds[index])));
     const colorDistance=stats(rendered.map((color,index)=>Math.hypot(...oklabSrgb(color).map((v,i)=>v-labs[index][i]))));
     const chromaticDistance=stats(rendered.map((color,index)=>Math.hypot(...oklabSrgb(color).slice(1).map((v,i)=>v-labs[index][i+1]))));
     const candidateLab=oklabSrgb(style.coreColor.slice(0,3));
     const materialChroma=Math.hypot(candidateLab[1]-materialLab[1],candidateLab[2]-materialLab[2]);
     const score=.30*Math.log2(luminanceContrast.p10)+1.60*chromaticDistance.p10+.75*colorDistance.mean+
      .35*materialChroma+(family==='CYAN_TEAL'?.015:0);
     return {name,family,style,sampleCount:centerPixels.length,luminanceContrast,OKLabDistance:colorDistance,
      OKLabChromaticDistance:chromaticDistance,primaryMaterialChromaticDistance:materialChroma,score,
      backgroundLuminance:stats(backgrounds.map(relativeLuminanceSrgb)),
      samples:centerPixels.map((point,index)=>({point,backgroundRGB8:backgrounds[index].map(v=>Math.round(v*255)),
       renderedCoreRGB8:rendered[index].map(v=>Math.round(v*255)),
       luminanceContrastRatio:contrastRatioSrgb(rendered[index],backgrounds[index])}))};
    };
    const inferAlpha=(actual,background,core)=>{
     const direction=core.map((v,i)=>v-background[i]),difference=actual.map((v,i)=>v-background[i]);
     const denominator=direction.reduce((sum,v)=>sum+v*v,0);
     fail(denominator>1e-5,'INSUFFICIENT_COLOR_DISTANCE_FOR_ALPHA_INVERSION');
     return Math.max(0,Math.min(1,direction.reduce((sum,v,i)=>sum+v*difference[i],0)/denominator));
    };
    const interval=(profile,key,threshold)=>{
     const selected=profile.map((item,index)=>item[key]>=threshold?index:-1).filter(index=>index>=0);
     if(!selected.length)return 0;
     let left=selected[0],right=selected.at(-1),a=profile[left].offset,b=profile[right].offset;
     if(left>0){const p=profile[left-1],q=profile[left];a=p.offset+(threshold-p[key])/(q[key]-p[key])*(q.offset-p.offset);}
     if(right<profile.length-1){const p=profile[right],q=profile[right+1];b=p.offset+(threshold-p[key])/(q[key]-p[key])*(q.offset-p.offset);}
     return b-a;
    };
    const measureWidth=(full,coreOnly,style)=>{
     const samples=profilePoints.map(item=>{
      const profile=[],step=.05;
      for(let offset=-support;offset<=support+.001;offset+=step){
       const point=[item.point[0]+item.normal[0]*offset,item.point[1]+item.normal[1]*offset];
       const background=bilinear(base,...point),actualCore=bilinear(coreOnly,...point),actualFull=bilinear(full,...point);
       const coreAlpha=inferAlpha(actualCore,background,style.coreColor.slice(0,3));
       const totalAlpha=inferAlpha(actualFull,background,style.coreColor.slice(0,3));
       const RGBDifference=Math.max(...actualFull.map((v,i)=>Math.abs(v-background[i])*255));
       profile.push({offset,coreAlpha,totalAlpha,RGBDifference});
      }
      const coreFwhm=interval(profile,'coreAlpha',style.coreColor[3]*.5);
      const integral=profile.reduce((sum,item)=>sum+item.coreAlpha*step,0);
      return {...item,coreFwhmPixels:coreFwhm,coreAlphaIntegralPixels:integral,
       coreEquivalentOpaqueWidthPixels:integral/style.coreColor[3],
       haloAndCoreObservableSupportPixels:interval(profile,'RGBDifference',1),
       haloAndCoreAlpha01SupportPixels:interval(profile,'totalAlpha',.01),
       peakCoreAlpha:Math.max(...profile.map(x=>x.coreAlpha)),
       profile:profile.filter((_,index)=>index%5===0)};
     });
     const statsFor=key=>stats(samples.map(sample=>sample[key]));
     return {configuredCoreWidthPixels:style.width,configuredCoreAlpha:style.coreColor[3],
      configuredTotalFiniteSupportPixels:style.width+2*style.glowRadius,sampleCount:samples.length,
      coreFwhmPixels:statsFor('coreFwhmPixels'),coreAlphaIntegralPixels:statsFor('coreAlphaIntegralPixels'),
      coreEquivalentOpaqueWidthPixels:statsFor('coreEquivalentOpaqueWidthPixels'),
      haloAndCoreObservableSupportPixels:statsFor('haloAndCoreObservableSupportPixels'),
      haloAndCoreAlpha01SupportPixels:statsFor('haloAndCoreAlpha01SupportPixels'),samples};
    };
    const area=(bytes,style)=>{
     let changed=0,changedPrimary=0,primary=0,corePixels=0,protectedChanged=0,outsideROI=0;
     const a32=new Uint32Array(bytes.buffer),b32=new Uint32Array(base.buffer);
     for(let index=0;index<a32.length;index++){
      const at=index*4,isPrimary=coverage[at+2]>=254;if(isPrimary)primary++;
      if(a32[index]===b32[index])continue;
      changed++;if(isPrimary)changedPrimary++;
      const x=index%width+.5,y=height-1-Math.floor(index/width)+.5;
      if(protectedBoxes.some(box=>inside(x,y,box)))protectedChanged++;
      if(!inside(x,y,runtimeRow.line.roi))outsideROI++;
      if(inferAlpha(rgb(bytes,x,y),rgb(base,x,y),style.coreColor.slice(0,3))>=style.coreColor[3]*.5)corePixels++;
     }
     fail(protectedChanged===0,'MEASUREMENT_CHANGED_PROTECTED_PIXELS');
     return {changedPixels:changed,changedPrimaryPixels:changedPrimary,primaryPixels:primary,
      changedPrimaryFraction:changedPrimary/primary,changedViewportFraction:changed/(width*height),
      coreHalfAlphaPixels:corePixels,protectedChangedPixels:protectedChanged,
      outsideRuntimeSelectedRoiPixels:outsideROI};
    };
    const v1Draw=draw(baselineStyle),v1Hash=await digest(v1Draw.bytes);
    fail(v1Hash===v1Expected.raw_rgba_sha256,'SAVED_V1_BASELINE_NATIVE_RENDER_IDENTITY_FAILED');
    const v1Core=draw(baselineStyle,{coreOnly:true});
    const baseline={raw_rgba_sha256:v1Hash,savedV1LineHoldFramebufferIdentity:true,
     width:measureWidth(v1Draw.bytes,v1Core.bytes,baselineStyle),
     contrast:measureContrast(v1Draw.bytes,baselineStyle,'V1_NATIVE_BOUNDARY_STYLE','BASELINE'),
     terrainCoverage:area(v1Draw.bytes,baselineStyle)};
    const palette=[];
    // Keep complete measurements available even when a later acceptance
    // assertion rejects selection. The Node driver saves this immutable
    // diagnostic result rather than losing the readings with the exception.
    window.eventVisualMeasurement={nativeBaseFramebufferIdentity:true,nativeBaseRawRgbaSha256:baseHash,
     savedV1LineHoldFramebufferIdentity:true,baseline,candidates:palette,
     actualPrimaryCoreSampleCount:centerPixels.length,actualUnoccludedCrossSectionCount:profilePoints.length,
     nativeSafeArea};
    let selectedBytes=null;
    for(const candidate of EVENT_LINE_COLOR_CANDIDATES_SRGB){
     const style={width:expectedStyle.width,glowRadius:expectedStyle.glowRadius,glowGain:expectedStyle.glowGain,
      coreColor:[...candidate.rgb,expectedStyle.coreColor[3]],glowColor:[...candidate.rgb,1]};
     const full=draw(style),core=draw(style,{coreOnly:true});
     const row={...measureContrast(full.bytes,style,candidate.name,candidate.family),
      raw_rgba_sha256:await digest(full.bytes),width:measureWidth(full.bytes,core.bytes,style),
      terrainCoverage:area(full.bytes,style)};
     palette.push(row);
     if(candidate.name===expectedStyle.selection.selectedName)selectedBytes=full.bytes;
    }
    fail(selectedBytes!==null,'RUNTIME_PALETTE_SELECTION_NOT_MEASURED');
    fail(await digest(selectedBytes)===runtimeRow.raw_rgba_sha256,'MEASURED_SELECTED_STYLE_DIFFERS_FROM_RUNTIME');
    const observedWinner=palette.reduce((best,row)=>row.score>best.score?row:best);
    const selected=palette.find(row=>row.name===expectedStyle.selection.selectedName);
    const independentSelector=selectEventLineStyle({role,theme:regional.theme,primaryMaterialColor:regional.theme.primary,
     backgroundSamples:centerPixels.map(([x,y])=>rgb(base,x,y))});
    const baselineComparison={luminanceP10RatioImproved:selected.luminanceContrast.p10>baseline.contrast.luminanceContrast.p10,
     actualChromaticP10DistanceImproved:selected.OKLabChromaticDistance.p10>baseline.contrast.OKLabChromaticDistance.p10,
     actualCompositeScoreImproved:selected.score>baseline.contrast.score};
    Object.assign(window.eventVisualMeasurement,{selection:{runtimeName:selected.name,
     actualRenderedWinner:observedWinner.name,sameWinner:observedWinner.name===selected.name,
     primaryOnlyIndependentSelectorWinner:independentSelector.selection.selectedName,
     runtimeScore:selected.score,actualWinnerScore:observedWinner.score,
     independentPrimaryOnlyModel:independentSelector.selection},baselineComparison,
     selected:{name:selected.name,style:expectedStyle,width:selected.width,terrainCoverage:selected.terrainCoverage,
      luminanceContrast:selected.luminanceContrast,OKLabDistance:selected.OKLabDistance,
      OKLabChromaticDistance:selected.OKLabChromaticDistance}});
    fail(observedWinner.name===selected.name,'ACTUAL_RENDERED_PALETTE_WINNER_DIFFERS_FROM_AUTOMATIC_SELECTION');
    fail(independentSelector.selection.selectedName===selected.name,'PRIMARY_ONLY_BACKGROUND_SELECTOR_WINNER_DIFFERS');
    fail(selected.width.coreFwhmPixels.median>baseline.width.coreFwhmPixels.median,
     'ACTUAL_RENDERED_LINE_DID_NOT_BECOME_THICKER');
    fail(baselineComparison.actualCompositeScoreImproved,'ACTUAL_PRIMARY_BACKGROUND_COMPOSITE_SCORE_DID_NOT_IMPROVE');
    fail(baselineComparison.actualChromaticP10DistanceImproved,
     'ACTUAL_PRIMARY_BACKGROUND_CHROMATIC_CONTRAST_DID_NOT_IMPROVE');
    fail(frozenInputs===JSON.stringify({regional,continent,input,fixture}),'MEASUREMENT_MUTATED_FROZEN_INPUT');
    fail(await digest(native())===baseHash,'NATIVE_BASE_NOT_RESTORED_AFTER_MEASUREMENT');
    return {nativeBaseFramebufferIdentity:true,nativeBaseRawRgbaSha256:baseHash,
     geometryIdentity:true,primaryMaterialColor:regional.theme.primary,backgroundsUnmodified:true,
     method:{output:'Actual 1080x1920 production native RGBA readback at pinned V5 camera frame249',
      sampleSelection:'Native PRIMARY coverage>=254/255, outside every protected box and native Boundary/Glow pixel; perpendicular production-segment profiles excluding nearby nonadjacent segments and vertices',
      width:'Paired actual native terrain + core-only Event draws. Recover compositing alpha from RGB; integrate perpendicular profiles and interpolate half configured alpha crossings. Full finite halo measured separately.',
      widthClarification:'Configured width is not reported as measured width. Core FWHM is raster AA width; halo support is not core width.',
      alphaInversion:'dot(rendered-background, coreRGB-background)/squaredNorm(coreRGB-background), clamped0..1; same nativebackground at samepixel',
      color:'8-bit actual rendered core and unchanged background from identical raster pixels; decode display sRGB once to linear sRGB for WCAG luminance ratio and D65 OKLab analysis.',
      contrastScore:expectedStyle.selection.scoreFormula,
      unchangedPass:'The native Event raster pass, geographic primitive and typed Marker occlusions are reused without shader or native Renderer edits.'},
     baseline,baselineComparison,candidates:palette,selection:{runtimeName:selected.name,actualRenderedWinner:observedWinner.name,
      sameWinner:true,primaryOnlyIndependentSelectorWinner:independentSelector.selection.selectedName,
      runtimeScore:selected.score,runnerUpScore:palette.filter(row=>row.name!==selected.name).reduce((a,b)=>Math.max(a,b.score),-Infinity)},
     selected:{name:selected.name,style:expectedStyle,width:selected.width,terrainCoverage:selected.terrainCoverage,
      luminanceContrast:selected.luminanceContrast,OKLabDistance:selected.OKLabDistance,
      OKLabChromaticDistance:selected.OKLabChromaticDistance},
     actualPrimaryCoreSampleCount:centerPixels.length,actualUnoccludedCrossSectionCount:profilePoints.length,
     nativeSafeArea,glError:gl.getError()};
   }finally{graphics?.dispose();factory?.dispose();renderer.dispose();canvas.remove();}
  },{fixture,clean,runtimeRow:actualRuntime,v1Expected:v1.frames.find(row=>row.eventFrame===74)});
  Object.assign(report,measured);
  assert.equal(measured.glError,0);assert.equal(session.errors.length,0);
  assert.deepEqual(await inventory(),inputs,'Source/assets changed during native measurement');
  report.status='PASS';report.command.exit_code=0;
 }catch(error){
  report.status='FAIL';report.command.exit_code=1;report.errors.push(String(error.stack??error));
  if(session){
   const partial=await session.page.evaluate(()=>window.eventVisualMeasurement??null).catch(()=>null);
   if(partial)report.partialMeasurements=partial;
  }
  throw error;
 }
 finally{
  try{await session?.close();}finally{
   report.completed_at_utc=new Date().toISOString();await writeJson(path.join(out,'REPORT.json'),report);
  }
 }
 console.log(JSON.stringify({phase:report.phase,status:report.status,report:path.join(out,'REPORT.json'),
  selected:report.selected.name,coreMedianPixels:report.selected.width.coreFwhmPixels.median,event_final:false}));
}
main().catch(error=>{console.error(String(error.stack??error));process.exitCode=1;});
