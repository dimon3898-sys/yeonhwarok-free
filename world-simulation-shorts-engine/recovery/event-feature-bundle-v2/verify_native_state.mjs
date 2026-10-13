// Focused shared-context protection smoke. No source or native image changes.
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
import {openVisualRuntime,json,engine} from '../event-v1-v3-visual-detail/visual_runtime.mjs';
const root=path.join(engine,'recovery/event-feature-bundle-v2'),out=path.join(root,'evidence/NATIVE_STATE.json');
await mkdir(path.dirname(out),{recursive:true});
const approved=await json(path.join(engine,'recovery/event-v1-v3-visual-detail/fixtures/DETAIL_ADAPTER_PLAN.json'));
const bounds=approved.targetBounds,safeArea=approved.safeArea;
let session;
const report={version:'FLOW_NATIVE_SHARED_STATE_SMOKE_V2',status:'STARTED',output:[1080,1920],
 source:'Unchanged approved V1 native runtime; approved generic adapter target',startedAtUtc:new Date().toISOString()};
try{
 session=await openVisualRuntime();
 await session.page.evaluate(bounds=>window.visualDetail.initialize({targetFraming:{bounds},mode:'STATIC_VISUAL_PROBE'}),bounds);
 Object.assign(report,await session.page.evaluate(async({bounds,safeArea})=>{
  const {createFlowGraphicPass,captureFlowNativeGlState}=await import('/modules/flow_graphic_pass_v2.mjs');
  const {evaluateGeographicLineReveal}=await import('/modules/event_line_v1.mjs');
  const canvas=[...document.querySelectorAll('canvas')].at(-1),gl=canvas.getContext('webgl2');
  const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
  function directPixels(){
   gl.finish();const pixels=new Uint8Array(1080*1920*4);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,pixels);return pixels;
  }
  function stateDifferences(a,b,path='state'){
   if(a===b)return[];
   if(ArrayBuffer.isView(a)&&ArrayBuffer.isView(b))return a.length===b.length?
    [...a].flatMap((v,i)=>Object.is(v,b[i])?[]:[path+'['+i+']']):[path+'.length'];
   if(Array.isArray(a)&&Array.isArray(b))return a.length===b.length?
    a.flatMap((v,i)=>stateDifferences(v,b[i],path+'['+i+']')):[path+'.length'];
   if(a&&b&&Object.getPrototypeOf(a)===Object.prototype&&Object.getPrototypeOf(b)===Object.prototype){
    const keys=[...new Set([...Object.keys(a),...Object.keys(b)])];return keys.flatMap(key=>stateDifferences(a[key],b[key],path+'.'+key));
   }
   return[path];
  }
  const event=(await window.visualDetail.capture({bounds,eventFrame:149,eventEnabled:true,protect:false,png:false})).diagnostic.event;
  await window.visualDetail.capture({bounds,eventEnabled:false,png:false});
  const clean=directPixels(),cleanSha=await digest(clean),stateBefore=captureFlowNativeGlState(gl);
  const pass=createFlowGraphicPass({canvas,style:event.eventStyle});
  const constructorStateDifferences=stateDifferences(stateBefore,captureFlowNativeGlState(gl)),constructorSha=await digest(directPixels());
  const primitive=event.linePrimitive,point=evaluateGeographicLineReveal(primitive,.5).path.at(-1),next=evaluateGeographicLineReveal(primitive,.56).path.at(-1),
   heading=Math.atan2(next[1]-point[1],next[0]-point[0]);
  const controls={routeFraction:1,objectVisible:true,objectPosition:point,heading,objectFraction:.5,
   directionalActive:true,directionalPosition:next,directionalHeading:heading,
   departurePulse:{active:true,anchor:primitive.screenCoordinates[0],progress:.5,radius:22,alpha:.6}};
  const flowIntent={object_role:'GENERIC_TRANSPORT',object_graphic:{width_px:48,height_px:22,polygons:[
   {points:[[-.5,-.35],[.25,-.35],[.5,0],[.25,.35],[-.5,.35]],color:[1,1,1,1]},
   {points:[[-.25,-.18],[.1,-.18],[.1,.18],[-.25,.18]],color:[.03,.1,.13,1]}]}};
  const statePreDraw=captureFlowNativeGlState(gl),flow=pass.draw({primitive,controls,safeArea,protectedGraphics:event.protectedGraphics,flowIntent}),
   drawStateDifferences=stateDifferences(statePreDraw,captureFlowNativeGlState(gl)),actual=directPixels();
  const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3],a=new Uint32Array(clean.buffer),b=new Uint32Array(actual.buffer);
  let changed=0,outside=0,protectedChanged=0,markerChanged=0;
  for(let i=0;i<b.length;i++)if(a[i]!==b[i]){changed++;const x=i%1080,y=1919-Math.floor(i/1080);
   if(!flow.rois.some(r=>inside(x,y,r)))outside++;
   if(event.protectedGraphics.some(r=>inside(x,y,r.box)))protectedChanged++;
   if(event.protectedGraphics.some(r=>r.kind==='MARKER'&&inside(x,y,r.box)))markerChanged++;
  }
  await window.visualDetail.capture({bounds,eventEnabled:false,png:false});const nextNativeSha=await digest(directPixels());
  const statePreDispose=captureFlowNativeGlState(gl);pass.dispose();
  const disposeStateDifferences=stateDifferences(statePreDispose,captureFlowNativeGlState(gl));
  await window.visualDetail.capture({bounds,eventEnabled:false,png:false});const afterDisposeNativeSha=await digest(directPixels());
  return{reads:'DIRECT_NATIVE_GL_READPIXELS; no factory cached pixel read used for comparison',
   native_rgba_sha256:cleanSha,constructor_rgba_sha256:constructorSha,next_native_rgba_sha256:nextNativeSha,
   after_dispose_native_rgba_sha256:afterDisposeNativeSha,constructorNativeFrameBitExact:constructorSha===cleanSha,
   nextNativeFrameBitExact:nextNativeSha===cleanSha,afterDisposeNativeFrameBitExact:afterDisposeNativeSha===cleanSha,
   constructorStateDifferences,drawStateDifferences,disposeStateDifferences,
   nativeState:{parameters:Object.keys(stateBefore.parameters).length,capabilities:Object.keys(stateBefore.capabilities).length,
    pixelStoreParameters:Object.keys(stateBefore.pixelStore).length,textureUnits:stateBefore.textures.length,textureTargetsPerUnit:4,
    vertexAttributes:stateBefore.attributes.length,uniformBufferBindings:stateBefore.uniformBuffers.length,
    transformFeedbackBindings:stateBefore.feedbackBuffers.length},
   changed_pixels:changed,outside_roi_changed_pixels:outside,protected_changed_pixels:protectedChanged,marker_changed_pixels:markerChanged,
   flow,glError:gl.getError()};
 },{bounds,safeArea}));
 for(const key of ['constructorNativeFrameBitExact','nextNativeFrameBitExact','afterDisposeNativeFrameBitExact'])assert.equal(report[key],true,key);
 for(const key of ['constructorStateDifferences','drawStateDifferences','disposeStateDifferences'])assert.deepEqual(report[key],[],key);
 for(const key of ['outside_roi_changed_pixels','protected_changed_pixels','marker_changed_pixels','glError'])assert.equal(report[key],0,key);
 assert.ok(report.changed_pixels>0);assert.deepEqual(session.errors,[]);report.browserErrors=[];report.status='PASS';
 console.log(JSON.stringify({status:report.status,changedPixels:report.changed_pixels,nativeBitExact:true,stateExact:true,protectedPixels:0,markerPixels:0,outsideRoiPixels:0}));
}catch(error){report.status='FAIL';report.error=error.stack??error.message;throw error;}
finally{report.completedAtUtc=new Date().toISOString();await writeFile(out,JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session?.close();}
