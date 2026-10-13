/** Event-only graph. Native camera, terrain, projection and graphics remain their existing owners. */
import {createAreaNativeBridge} from './area_native_bridge_v3.mjs';
import {assertAreaPlan,evaluateAreaFrame} from './area_core_v3.mjs';
import {createAreaOverlayPass} from './area_overlay_pass_v3.mjs';
import {geometryBounds} from './scale_contract.mjs';

const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
export async function createAreaGpuAdapter({canvas,plans,cameraPlan,scene,heightSource,contextTerrain=null,areaPlan,presentation}){
 const plan=assertAreaPlan(areaPlan),native=await createAreaNativeBridge({canvas,plans,cameraPlan,scene,heightSource,contextTerrain});
 const gl=canvas.getContext('webgl2'),overlay=createAreaOverlayPass({canvas}),safeArea=plans.REGIONAL.layout.safe;
 let annotation=null;
 if(presentation.annotations?.length){
  const {createAreaAnnotation}=await import('./area_annotation_v3.mjs');
  annotation=await createAreaAnnotation({renderer:native.renderer,labels:presentation.annotations,dataMode:plan.intent.data_mode,
   geographicAnchor:plan.intent.origin,safeArea,width:1080,height:1920});
 }
 let last;
 const pixels=()=>{const data=new Uint8Array(1080*1920*4);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,data);return data;};
 function drawFrame(frame,{areaEnabled=true,protect=false}={}){
  const cameraFrame=(presentation.cameraStartFrame??0)+frame,nativeFrame=native.drawNative(cameraFrame);
  const active=areaEnabled&&frame>=presentation.eventStartFrame;
  if(active&&!nativeFrame.cameraLocked)throw Error('AREA_REQUIRES_NATIVE_DETAIL_LOCK');
  gl.finish();const before=protect?pixels():null;
  let controls=null,result=null,text=null,rois=[];
  if(active){
   controls=evaluateAreaFrame(plan,plan.startFrame+frame-presentation.eventStartFrame,{project:native.project});
   if(annotation){
    const anchor=native.project(controls.origin),middle=[(safeArea[0]+safeArea[2])/2,(safeArea[1]+safeArea[3])/2];
    const placed=annotation.place({anchor,anchorCandidates:[middle,[middle[0],safeArea[1]+180],
     [middle[0],safeArea[3]-240],[safeArea[2]-260,middle[1]],[safeArea[0]+260,middle[1]]],
     safeArea,protectedGraphics:nativeFrame.protectedGraphics,boundarySegments:nativeFrame.boundarySegments});
    const selected=presentation.annotations.find(label=>label.id===controls.stateId)??presentation.annotations[0];
    text={id:selected.id,placement:placed,reservation:placed.reservation,roi:placed.reservation.box};
   }
   const reservations=[...nativeFrame.protectedGraphics,...(text?.reservation?[text.reservation]:[])];
   const samples=[];
   if(before)for(const point of [controls.origin,...controls.areas.map(a=>a.coverageOrigin)]){
    const [x,y]=native.project(point).map(Math.floor);
    if(x>=0&&x<1080&&y>=0&&y<1920){const i=((1919-y)*1080+x)*4;samples.push([...before.slice(i,i+3)].map(v=>v/255));}
   }
   const bounds=nativeFrame.camera.flatBounds;
   const mediumExclusions=presentation.propagationMedium==='WATER'||presentation.impactMedium==='WATER'?plans.REGIONAL.geometries.filter(record=>{
    const b=geometryBounds(record);return b[0]<bounds[2]&&b[2]>bounds[0]&&b[1]<bounds[3]&&b[3]>bounds[1];
   }).map(record=>({type:record.geometry_type,coordinates:record.coordinates})):[];
   result=overlay.draw({controls,project:native.project,safeArea,protectedGraphics:reservations,
    primaryMaterialColor:plans.REGIONAL.theme.primary,backgroundSamples:samples,boundarySegments:nativeFrame.boundarySegments,
    propagationExclusionGeometries:presentation.propagationMedium==='WATER'?mediumExclusions:[],
    impactExclusionGeometries:presentation.impactMedium==='WATER'?mediumExclusions:[]});
   rois=[...result.rois];
   if(text){text={...text,...annotation.draw(text)};if(text.roi)rois.push(text.roi);}
  }
  gl.finish();const after=pixels(),protection={changedPixels:0,protectedChangedPixels:0,markerChangedPixels:0,outsideRoiChangedPixels:0,safeAreaChangedPixels:0};
  if(protect){
   const a=new Uint32Array(before.buffer),b=new Uint32Array(after.buffer);
   for(let i=0;i<b.length;i++)if(a[i]!==b[i]){
    const x=i%1080,y=1919-Math.floor(i/1080);protection.changedPixels++;
    if(!rois.some(box=>inside(x,y,box)))protection.outsideRoiChangedPixels++;
    if(!inside(x,y,safeArea))protection.safeAreaChangedPixels++;
    if(nativeFrame.protectedGraphics.some(r=>inside(x,y,r.box)))protection.protectedChangedPixels++;
    if(nativeFrame.protectedGraphics.some(r=>r.kind==='MARKER'&&inside(x,y,r.box)))protection.markerChangedPixels++;
   }
   if(protection.protectedChangedPixels||protection.markerChangedPixels||protection.outsideRoiChangedPixels||protection.safeAreaChangedPixels)
    throw Error('AREA_PIXEL_PROTECTION_FAILED '+JSON.stringify(protection));
  }
  const glError=gl.getError();if(glError)throw Error('AREA_GL_ERROR_'+glError);
  const {boundarySegments,...cameraDiagnostic}=nativeFrame;
  cameraDiagnostic.boundaryProtection={segmentCount:boundarySegments.length,source:'ACTUAL_NATIVE_PRIMARY_SECONDARY_RING_PROJECTION',
   finiteGlowSupport:true};
  last={frame,state:controls?.state??nativeFrame.state,camera:cameraDiagnostic,area:{enabled:active,controls,
   graphics:result,annotation:text,protection,geometryUnchanged:true},glError:0,width:1080,height:1920};
  return last;
 }
 return {drawFrame,project:native.project,readPixels:pixels,png:()=>canvas.toDataURL('image/png'),get diagnostic(){return last;},
  evidence:{version:'AREA_GPU_ADAPTER_V3',parent:'EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE',
   cameraOwnership:'UNCHANGED_V5',projection:'ACTUAL_NATIVE_FACTORY_SCREEN',finishedFrameBlit:false,
   native:native.evidence,overlay:overlay.evidence},dispose(){annotation?.dispose();overlay.dispose();native.dispose();}};
}
