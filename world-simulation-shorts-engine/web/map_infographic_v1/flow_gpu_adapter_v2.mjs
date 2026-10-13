/** Flow extension. The V1 Camera/Renderer/Projection/Line remain read-only owners. */
import {createEventDetailGpuAdapter} from './visual_event_gpu_adapter_v1.mjs';
import {assertCameraDetailApproachPlan,evaluateCameraDetailApproachFrame} from './camera_detail_approach_adapter_v1.mjs';
import {assertFlowPlan,compileFlowRoute,evaluateFlowFrame} from './flow_core_v2.mjs';
import {selectEventLineStyle} from './event_style_v1.mjs';
import {createFlowGraphicPass} from './flow_graphic_pass_v2.mjs';
import {applyFlowVisualProfile} from './flow_visual_profile_v2.mjs';

export const FLOW_GPU_ADAPTER_V2_VERSION='FLOW_GPU_ADAPTER_V2';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const copy=value=>structuredClone(value);
const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];

/** Disabled extension delegates unchanged V1 directly, before any Flow validation. */
export async function createFlowGpuAdapter({canvas,plans,cameraPlan,scene,heightSource,contextTerrain=null,
 flowPlan,detailPlan,approvedEventStyle,approvedMetricStyle,visualProfile=null,extensionEnabled=true,...nativeOptions}={}){
 if(extensionEnabled===false)return createEventDetailGpuAdapter({canvas,plans,cameraPlan,scene,heightSource,
  contextTerrain,approvedEventStyle,approvedMetricStyle,...nativeOptions});
 if(extensionEnabled!==true)throw Error('FLOW_EXPLICIT_EXTENSION_FLAG_REQUIRED');
 const flow=assertFlowPlan(flowPlan),motion=assertCameraDetailApproachPlan(detailPlan);
 if(!same(flow.intent.route_geometry,motion.eventGeometry)||flow.totalFrames!==motion.eventPlan.totalFrames
  ||flow.fps!==motion.fps||flow.intent.direction!==motion.eventPlan.intent.line.direction)
  throw Error('FLOW_NATIVE_CAMERA_GEOMETRY_BINDING_REQUIRED');
 const base=await createEventDetailGpuAdapter({canvas,plans,cameraPlan,scene,heightSource,contextTerrain,
  eventPlan:motion.eventPlan,targetFraming:motion.targetBounds,approvedEventStyle,approvedMetricStyle,
  mode:motion.productionEligible?'VISUAL_DETAIL_ADMITTED':'STATIC_VISUAL_PROBE',certificate:motion.request.certificate});
 const gl=canvas.getContext('webgl2'),width=1080,height=1920,safeArea=copy(motion.safeArea);
 let pass=null,style=null,last=null;
 const pixels=()=>{const bytes=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,bytes);return bytes;};
 function chooseStyle(primitive,reservations,native){
  const samples=[];
  for(let segment=1;segment<primitive.screenCoordinates.length;segment++){
   const a=primitive.screenCoordinates[segment-1],b=primitive.screenCoordinates[segment],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
   const count=Math.max(1,Math.ceil(length/8));
   for(let k=0;k<count;k++){
    const t=(k+.5)/count,x=Math.floor(a[0]+(b[0]-a[0])*t),y=Math.floor(a[1]+(b[1]-a[1])*t);
    if(x<0||x>=width||y<0||y>=height||reservations.some(r=>inside(x,y,r.box)))continue;
    const offset=((height-1-y)*width+x)*4;
    samples.push([native[offset]/255,native[offset+1]/255,native[offset+2]/255]);
   }
  }
  return selectEventLineStyle({role:flow.routeEventPlan.intent.line.style_role,theme:plans.REGIONAL.theme,
   primaryMaterialColor:plans.REGIONAL.theme.primary,backgroundSamples:samples.length?samples:undefined});
 }
 return{evidence:{version:FLOW_GPU_ADAPTER_V2_VERSION,parent:'EVENT_SYSTEM_V1_FINAL_BASELINE',
  cameraOwnership:'UNCHANGED_V5_AND_DETAIL_ADAPTER',projection:'ACTUAL_NATIVE_FACTORY_SCREEN_REUSED',
  routeEngine:'UNCHANGED_V1_GEOGRAPHIC_LINE_AND_GPU_PASS',finishedFrameBlit:false,physics:false},
  drawFrame(frame,{flowEnabled=true,protect=false}={}){
   if(typeof flowEnabled!=='boolean'||typeof protect!=='boolean')throw Error('FLOW_DRAW_BOOLEAN_REQUIRED');
   const scheduled=evaluateCameraDetailApproachFrame(motion,frame),active=flowEnabled&&scheduled.cameraLocked;
   // V1 EVENT_READY exposes the native projection/readiness and draws no Event primitive.
   const native=base.draw({bounds:scheduled.flatBounds,cameraLocked:scheduled.cameraLocked,
    eventEnabled:active,eventFrame:active?0:null,frame});
   gl.finish();const before=active||protect?pixels():null;
   let controls=null,result=null,primitive=null,presentation=null;
   if(active){
    if(native.event.line!==null||native.event.metric!==null||native.event.controls.state!=='EVENT_READY')
     throw Error('FLOW_NATIVE_BINDING_MUST_NOT_DRAW_EVENT');
    const projected=native.event.controls.readiness.projectedGeometry,coordinates=flow.intent.route_geometry.coordinates;
    const lookup=new Map(coordinates.map((point,index)=>[JSON.stringify(point),projected[index]]));
    const project=point=>{const value=lookup.get(JSON.stringify(point));if(!value)throw Error('FLOW_NATIVE_PROJECTION_POINT_UNBOUND');return [...value];};
    primitive=compileFlowRoute(flow.intent,{project});
    controls=evaluateFlowFrame(flow,flow.startFrame+scheduled.eventFrame,{primitive,eventContext:{cameraState:native,
     project,safeArea,scalePlan:plans.REGIONAL,heightSource,protectedBoxes:native.event.protectedBoxes}});
    if(visualProfile)presentation=applyFlowVisualProfile({flowPlan:flow,controls,primitive,profile:visualProfile});
    if(!pass){style=chooseStyle(primitive,native.event.protectedGraphics,before);pass=createFlowGraphicPass({canvas,style});}
    result=pass.draw({primitive,controls:presentation?.controls??controls,safeArea,protectedGraphics:native.event.protectedGraphics,
     flowIntent:presentation?{...flow.intent,object_graphic:presentation.objectGraphic}:flow.intent});
   }
   gl.finish();const after=pixels(),rois=result?.rois??[],protection={changedPixels:0,protectedChangedPixels:0,markerChangedPixels:0,outsideRoiChangedPixels:0};
   if(protect&&before){
    const a=new Uint32Array(before.buffer),b=new Uint32Array(after.buffer);
    for(let i=0;i<b.length;i++)if(a[i]!==b[i]){
     const x=i%width,y=height-1-Math.floor(i/width);protection.changedPixels++;
     if(!rois.some(r=>inside(x,y,r)))protection.outsideRoiChangedPixels++;
     if(native.event.protectedGraphics.some(r=>inside(x,y,r.box)))protection.protectedChangedPixels++;
     if(native.event.protectedGraphics.some(r=>r.kind==='MARKER'&&inside(x,y,r.box)))protection.markerChangedPixels++;
    }
    if(protection.protectedChangedPixels||protection.markerChangedPixels||protection.outsideRoiChangedPixels)
     throw Object.assign(Error('FLOW_NATIVE_PIXEL_PROTECTION_FAILED'),{protection});
   }
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('FLOW_COMPOSITION_GL_ERROR_'+error);
   last={frame,state:controls?.state??scheduled.state,camera:scheduled,native,flow:{enabled:active,controls,
    primitive,graphics:result,style:copy(style),protection,
    ...(presentation?{visualControls:presentation.controls,visualProfile:presentation.metadata}:{})},width,height,glError:0};return last;
  },readPixels:pixels,png:()=>canvas.toDataURL('image/png'),get diagnostic(){return last;},
  dispose(){pass?.dispose();base.dispose();}};
}
