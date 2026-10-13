/** Event-owned open wave-front presentation over the frozen native Area/V5 graph. */
import {createAreaNativeBridge} from './area_native_bridge_v3.mjs';
import {assertAreaPlan} from './area_core_v3.mjs';
import {createAreaOverlayPass} from './area_overlay_pass_v3.mjs';
import {selectAreaStyle} from './area_style_v3.mjs';
import {geometryBounds} from './scale_contract.mjs';
import {evaluateWaveVisualFrame} from './wave_visual_v3.mjs';

export const WAVE_GPU_ADAPTER_V3_VERSION='OPEN_WAVE_GPU_ADAPTER_V3';
const inside=(x,y,box)=>x+.5>=box[0]&&x+.5<=box[2]&&y+.5>=box[1]&&y+.5<=box[3];
const copy=value=>structuredClone(value);

/** The only pixels this adapter adds are open fronts, one birth pulse, local coast contact and the existing measured date label. */
export async function createWaveGpuAdapter({canvas,plans,cameraPlan,scene,heightSource=null,
 contextTerrain=null,areaPlan,presentation,wavePlan}={}){
 const plan=assertAreaPlan(areaPlan);
 if(!wavePlan||typeof wavePlan!=='object')throw Error('WAVE_COMPILED_VISUAL_PLAN_REQUIRED');
 const native=await createAreaNativeBridge({canvas,plans,cameraPlan,scene,heightSource,contextTerrain});
 const gl=canvas.getContext('webgl2'),safeArea=plans.REGIONAL.layout.safe;
 const selected=selectAreaStyle({primaryMaterialColor:plans.REGIONAL.theme.primary});
 // Automatic event contrast is reused. A small finite halo makes the wave front
 // legible at native mobile output without changing any native material style.
 const waveStyle={...copy(selected),
  PROPAGATION:{...copy(selected.PROPAGATION),width:5.2,glowRadius:2.4,glowGain:.105},
  FRONT:{...copy(selected.IMPACT),fillColor:[0,0,0,0],width:5.8,glowRadius:3.8,glowGain:.14}};
 const overlay=createAreaOverlayPass({canvas,style:waveStyle});
 let annotation=null;
 try{
  if(presentation.annotations?.length){
   const {createAreaAnnotation}=await import('./area_annotation_v3.mjs');
   annotation=await createAreaAnnotation({renderer:native.renderer,labels:presentation.annotations,
    dataMode:plan.intent.data_mode,geographicAnchor:plan.intent.origin,safeArea,width:1080,height:1920});
  }
 }catch(error){overlay.dispose();native.dispose();throw error;}
 let last=null,disposed=false;
 const pixels=()=>{
  const data=new Uint8Array(1080*1920*4);
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);gl.readPixels(0,0,1080,1920,gl.RGBA,gl.UNSIGNED_BYTE,data);return data;
 };
 function drawFrame(frame,{waveEnabled=true,areaEnabled=undefined,protect=false}={}){
  if(disposed)throw Error('WAVE_GPU_DISPOSED');
  if(!Number.isSafeInteger(frame)||frame<0)throw Error('WAVE_NATIVE_FRAME_REQUIRED');
  // areaEnabled is only an OFF-regression alias for inherited capture tooling.
  const enabled=areaEnabled===undefined?waveEnabled:waveEnabled&&areaEnabled;
  const nativeFrame=native.drawNative((presentation.cameraStartFrame??0)+frame);
  const active=enabled&&frame>=presentation.eventStartFrame;
  if(active&&!nativeFrame.cameraLocked)throw Error('WAVE_REQUIRES_NATIVE_DETAIL_LOCK');
  gl.finish();const before=protect?pixels():null;
  let controls=null,wave=null,main=null,coast=null,text=null,rois=[];
  if(active){
   wave=evaluateWaveVisualFrame(wavePlan,frame-presentation.eventStartFrame,{project:native.project});
   const waveFronts=[...wave.fronts,...(wave.originPulse?.front?[wave.originPulse.front]:[])];
   // Never draw the parent demonstration's closed propagation ring or broad
   // coastal polygon. The immutable parent plan is used only for source facts.
   controls={areas:[],impacts:[],fronts:[],propagations:waveFronts,origin:wave.origin,
    stateId:wave.stateId,state:wave.stateId,timeLabel:wave.timeLabel,hold:wave.hold,physicalSimulation:false};
   if(annotation){
    const anchor=native.project(wave.origin),middle=[(safeArea[0]+safeArea[2])/2,(safeArea[1]+safeArea[3])/2];
    const placed=annotation.place({anchor,anchorCandidates:[middle,[middle[0],safeArea[1]+180],
     [middle[0],safeArea[3]-240],[safeArea[2]-260,middle[1]],[safeArea[0]+260,middle[1]]],
     safeArea,protectedGraphics:nativeFrame.protectedGraphics,boundarySegments:nativeFrame.boundarySegments});
    const selectedLabel=presentation.annotations.find(label=>label.id===wave.stateId)??presentation.annotations[0];
    text={id:selectedLabel.id,placement:placed,reservation:placed.reservation,roi:placed.reservation.box,
     visibleFraction:1};
   }
   const reservations=[...nativeFrame.protectedGraphics,...(text?.reservation?[text.reservation]:[])];
   const bounds=nativeFrame.camera.flatBounds;
   const land=plans.REGIONAL.geometries.filter(record=>{
    const box=geometryBounds(record);return box[0]<bounds[2]&&box[2]>bounds[0]&&box[1]<bounds[3]&&box[3]>bounds[1];
   }).map(record=>({type:record.geometry_type,coordinates:record.coordinates}));
   main=overlay.draw({controls,project:native.project,safeArea,protectedGraphics:reservations,
    primaryMaterialColor:plans.REGIONAL.theme.primary,boundarySegments:nativeFrame.boundarySegments,
    propagationExclusionGeometries:land});
   // The user requested a brief local coastline glow. These are supplied exact
   // coast-contact intervals, not the country's whole boundary. Native Boundary
   // and Glow sources, style and renderer remain unchanged underneath the accent.
   const coastControls={areas:[],impacts:[],propagations:[],fronts:wave.coastfrontHighlights??[]};
   coast=overlay.draw({controls:coastControls,project:native.project,safeArea,
    protectedGraphics:reservations,primaryMaterialColor:plans.REGIONAL.theme.primary,boundarySegments:[]});
   rois=[...main.rois,...coast.rois];
   if(text){text={...text,...annotation.draw(text)};if(text.roi)rois.push(text.roi);}
  }
  gl.finish();const after=pixels();
  const protection={changedPixels:0,protectedChangedPixels:0,markerChangedPixels:0,
   outsideRoiChangedPixels:0,safeAreaChangedPixels:0};
  if(protect){
   const a=new Uint32Array(before.buffer),b=new Uint32Array(after.buffer);
   for(let index=0;index<b.length;index++)if(a[index]!==b[index]){
    const x=index%1080,y=1919-Math.floor(index/1080);protection.changedPixels++;
    if(!rois.some(box=>inside(x,y,box)))protection.outsideRoiChangedPixels++;
    if(!inside(x,y,safeArea))protection.safeAreaChangedPixels++;
    if(nativeFrame.protectedGraphics.some(record=>inside(x,y,record.box)))protection.protectedChangedPixels++;
    if(nativeFrame.protectedGraphics.some(record=>record.kind==='MARKER'&&inside(x,y,record.box)))protection.markerChangedPixels++;
   }
   if(protection.protectedChangedPixels||protection.markerChangedPixels||protection.outsideRoiChangedPixels||protection.safeAreaChangedPixels)
    throw Error('WAVE_PIXEL_PROTECTION_FAILED '+JSON.stringify(protection));
  }
  const glError=gl.getError();if(glError)throw Error('WAVE_GPU_GL_ERROR_'+glError);
  const {boundarySegments,...cameraDiagnostic}=nativeFrame;
  cameraDiagnostic.boundaryProtection={segmentCount:boundarySegments.length,
   source:'ACTUAL_NATIVE_PRIMARY_SECONDARY_RING_PROJECTION',finiteGlowSupport:true,
   eventContactAccent:'SUPPLIED_SHORT_COAST_INTERVALS_ONLY'};
  const graphics=main?{...main,coastContact:coast,rois,
   fronts:[...main.propagations,...coast.fronts]}:null;
  const detail={enabled:active,controls,graphics,annotation:text,protection,
   geometryUnchanged:true,diagnostics:wave?.diagnostics??null,
   originPulse:wave?.originPulse??null,closedPropagationRing:false,
   coastContactSequential:true,nativeSourceUnchanged:true};
  last={frame,state:wave?.stateId??nativeFrame.state,camera:cameraDiagnostic,
   wave:detail,area:detail,glError:0,width:1080,height:1920};
  return last;
 }
 return{drawFrame,project:native.project,readPixels:pixels,png:()=>canvas.toDataURL('image/png'),
  get diagnostic(){return last;},evidence:{version:WAVE_GPU_ADAPTER_V3_VERSION,
   parent:'EVENT_FEATURE_BUNDLE_V3_AREA_CANDIDATE',cameraOwnership:'UNCHANGED_V5',
   projection:'ACTUAL_NATIVE_FACTORY_SCREEN',finishedFrameBlit:false,
   closedRing:false,polygonCoreMutation:false,landClip:'UNCHANGED_NATIVE_COUNTRY_POLYGONS',
   contactAccent:'SHORT_EXACT_SUPPLIED_COAST_INTERVALS_IN_EVENT_OWNED_PASS',
   native:native.evidence,overlay:overlay.evidence,style:waveStyle},
  dispose(){if(disposed)return;annotation?.dispose();overlay.dispose();native.dispose();disposed=true;}};
}
