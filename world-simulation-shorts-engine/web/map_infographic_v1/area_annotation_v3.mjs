/** Area/time-step labels through the unchanged V1 measured Metric/Glyph and GPU pass. */
import {compileEventIntent,validateEventAnchor,freezeEventData} from './event_contract_v1.mjs';
import {compileMetricAnnotation} from './event_metric_v1.mjs';
import {createEventMetricPass} from './event_metric_pass_v1.mjs';
import {chooseMetricPlacement} from './event_layout_adapter_v1.mjs';

export const AREA_ANNOTATION_V3_VERSION='AREA_ANNOTATION_V3';
const copy=value=>structuredClone(value);
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const rectangle=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)
 &&value[0]<value[2]&&value[1]<value[3];

/** All labels are measured once; their largest atlas reserves one stable native-font slot. */
export function createAreaAnnotation({renderer,labels,dataMode='PRODUCTION',geographicAnchor,
 safeArea=[48,72,1032,1848],width=1080,height=1920,style=null,color=[1,1,1]}={}){
 if(!renderer?.isWebGLRenderer||renderer.autoClear!==false||width!==1080||height!==1920)
  throw Error('AREA_ANNOTATION_CANONICAL_SHARED_GPU_REQUIRED');
 if(!Array.isArray(labels)||!labels.length||new Set(labels.map(label=>label?.id)).size!==labels.length)
  throw Error('AREA_ANNOTATION_UNIQUE_LABELS_REQUIRED');
 if(!rectangle(safeArea))throw Error('AREA_ANNOTATION_SAFE_AREA_REQUIRED');
 const defaults={fontSize:40,minFontSize:40,fontFamily:'Gate1Bold',lineHeight:1.28,outlineRadius:1.4,
  maxWidth:safeArea[2]-safeArea[0]-16,maxLines:1};
 const metricStyle={...defaults,...(style??{})};
 if(metricStyle.fontSize!==40||metricStyle.minFontSize!==40||metricStyle.fontFamily!=='Gate1Bold'
  ||metricStyle.lineHeight!==1.28||metricStyle.outlineRadius!==1.4||metricStyle.maxLines!==1)
  throw Error('AREA_ANNOTATION_EXISTING_40PX_GLYPH_STYLE_REQUIRED');
 const entries=new Map();
 try{
  for(const label of labels){
   if(typeof label?.id!=='string'||!label.id.trim())throw Error('AREA_ANNOTATION_LABEL_ID_REQUIRED');
   const anchor=validateEventAnchor(label.anchor??geographicAnchor,'AREA_ANNOTATION_ANCHOR');
   const intent=compileEventIntent({data_mode:dataMode,metric:{display_value:label.display_value,
    unit:label.unit,source:label.source,anchor}});
   const primitive=compileMetricAnnotation(intent,{style:metricStyle});
   entries.set(label.id,{primitive,pass:createEventMetricPass({renderer,primitive,width,height,color})});
  }
 }catch(error){for(const entry of entries.values())entry.pass.dispose();throw error;}
 const envelope=freezeEventData({atlasDimensions:[Math.max(...[...entries.values()].map(e=>e.primitive.atlasDimensions[0])),
  Math.max(...[...entries.values()].map(e=>e.primitive.atlasDimensions[1]))]});
 let disposed=false,last=null;
 function place({anchor,anchorCandidates=[],protectedGraphics=[],protectedBoxes=[],boundarySegments=[],
  safeArea:currentSafe=safeArea,markerSize=40,gap=18}={}){
  if(disposed)throw Error('AREA_ANNOTATION_DISPOSED');
  if(!point(anchor)||!Array.isArray(anchorCandidates)||anchorCandidates.some(value=>!point(value)))
   throw Error('AREA_ANNOTATION_SCREEN_ANCHORS_REQUIRED');
  if(!Array.isArray(protectedGraphics)||!Array.isArray(protectedBoxes)||!Array.isArray(boundarySegments))
   throw Error('AREA_ANNOTATION_RESERVATIONS_REQUIRED');
  const boxes=[...protectedBoxes.map(box=>{if(!rectangle(box))throw Error('AREA_ANNOTATION_PROTECTED_BOX_REQUIRED');return [...box];}),
   ...protectedGraphics.map(item=>{if(!['MARKER','TEXT','PANEL'].includes(item?.kind)||!rectangle(item.box))
    throw Error('AREA_ANNOTATION_NATIVE_RESERVATION_REQUIRED');return [...item.box];})];
  for(const item of boundarySegments){
   if(!point(item?.a)||!point(item.b)||!Number.isFinite(item.radiusPx)||item.radiusPx<=0)
    throw Error('AREA_ANNOTATION_BOUNDARY_SUPPORT_REQUIRED');
   boxes.push([Math.min(item.a[0],item.b[0])-item.radiusPx,Math.min(item.a[1],item.b[1])-item.radiusPx,
    Math.max(item.a[0],item.b[0])+item.radiusPx,Math.max(item.a[1],item.b[1])+item.radiusPx]);
  }
  const attempts=[];
  for(const candidate of [anchor,...anchorCandidates]){
   try{
    const placement=chooseMetricPlacement({anchor:candidate,measurement:envelope,safeArea:currentSafe,
     protectedBoxes:boxes,markerSize,gap});
    return freezeEventData({version:AREA_ANNOTATION_V3_VERSION,placement,
     reservation:{kind:'TEXT',role:'AREA_ANNOTATION',box:[...placement.roi]},
     atlasEnvelope:[...envelope.atlasDimensions],attempts:copy(attempts),nativeGraphicsMoved:false});
   }catch(error){
    if(!['EVENT_METRIC_LAYOUT_BLOCKED','EVENT_LAYOUT_ANCHOR_OUTSIDE_SAFE_AREA'].includes(error.message))throw error;
    attempts.push({anchor:[...candidate],reason:error.message});
   }
  }
  throw Object.assign(Error('AREA_ANNOTATION_LAYOUT_BLOCKED'),{attempts});
 }
 function draw({id,visibleFraction=1,placement=null,...options}={}){
  if(disposed)throw Error('AREA_ANNOTATION_DISPOSED');
  const entry=entries.get(id);if(!entry)throw Error('AREA_ANNOTATION_UNKNOWN_LABEL');
  const selected=placement??place(options);
  if(selected.version!==AREA_ANNOTATION_V3_VERSION||!rectangle(selected.reservation?.box)
   ||JSON.stringify(selected.atlasEnvelope)!==JSON.stringify(envelope.atlasDimensions))
   throw Error('AREA_ANNOTATION_CURRENT_MEASURED_PLACEMENT_REQUIRED');
  const [left,top,slotWidth,slotHeight]=selected.placement.box,[w,h]=entry.primitive.atlasDimensions;
  const box=[left,top+(slotHeight-h)/2,w,h];
  if(w>slotWidth||h>slotHeight)throw Error('AREA_ANNOTATION_ATLAS_EXCEEDS_RESERVED_SLOT');
  const metricPlacement={...copy(selected.placement),box,roi:[box[0],box[1],box[0]+w,box[1]+h]};
  const frame=entry.pass.draw({visibleFraction,placement:metricPlacement});
  last={version:AREA_ANNOTATION_V3_VERSION,id,text:entry.primitive.text,drawn:frame.drawn,
   visibleFraction,roi:frame.roi,placement:copy(metricPlacement),reservation:copy(selected.reservation),
   atlasDimensions:[...entry.primitive.atlasDimensions],fontSize:40,source:copy(entry.primitive.intent.metric.source),
   nativeGraphicsMoved:false,glyphOwner:'UNCHANGED_METRIC_ANNOTATION_V1'};
  return last;
 }
 return{place,draw,get diagnostic(){return last;},
  evidence:{version:AREA_ANNOTATION_V3_VERSION,renderer:'UNCHANGED_EVENT_METRIC_GPU_PASS_V1',
   glyph:'UNCHANGED_PINNED_MEASURED_GLYPH',layout:'UNCHANGED_CHOOSE_METRIC_PLACEMENT',
   fontSize:40,style:copy(metricStyle),atlasEnvelope:[...envelope.atlasDimensions],
   labels:[...entries].map(([id,e])=>({id,text:e.primitive.text,atlasDimensions:[...e.primitive.atlasDimensions],
    anchor:[...e.primitive.anchor],source:copy(e.primitive.intent.metric.source)})),
   frameClock:'CALLER_SELECTED_EXPLICIT_STATE_ID',nativeGraphicMutation:false},
  dispose(){if(disposed)return;for(const entry of entries.values())entry.pass.dispose();disposed=true;}};
}
