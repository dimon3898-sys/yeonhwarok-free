/**
 * Chapter-wide reservations for the unchanged measured Area annotation owner.
 * This is CPU layout admission, never a draw/GPU or visual-quality certificate.
 * The caller must supply every actual projected frame before allowing a draw.
 */
import {chooseMetricPlacement} from '/modules/event_layout_adapter_v1.mjs';
import {freezeEventData} from '/modules/event_contract_v1.mjs';
import {productionAnnotationAnchors} from '/production-v3/production_visual_profile.mjs';

export const STABLE_ANNOTATION_VERSION = 'STUDIO_STABLE_ANNOTATION_V1';
const owners = new WeakMap();
const MAX_FRAMES = 18_000, MAX_LABELS = 8, MAX_FRAME_BOXES = 8192, MAX_UNIQUE_BOXES = 250_000,
 MAX_PROJECTED_BOX_RECORDS = 600_000;
const sha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const copy = value => JSON.parse(JSON.stringify(value));
const overlap = (a,b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const contains = (a,b) => b[0] >= a[0] && b[1] >= a[1] && b[2] <= a[2] && b[3] <= a[3];
function fail(code) { throw Error(`STABLE_ANNOTATION_${code}`); }
function rectangle(value) {
 if (!Array.isArray(value) || value.length !== 4 || !value.every(Number.isFinite)
  || !(value[0] < value[2] && value[1] < value[3])) fail('RECTANGLE_REQUIRED');
 return value.map(x => Object.is(x,-0) ? 0 : x);
}
function point(value) {
 if (!Array.isArray(value) || value.length !== 2 || !value.every(Number.isFinite)) fail('POINT_REQUIRED');
 return [...value];
}
function identifier(value) {
 if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)) fail('IDENTIFIER_REQUIRED');
 return value;
}
function normalizeBinding(binding) {
 if (!binding || !['sceneSHA256','cameraSHA256','layoutSHA256','codeSHA256'].every(key => sha(binding[key])))
  fail('SOURCE_BINDING_REQUIRED');
 // Exact fields deliberately exclude arbitrary user-authored authority flags.
 return Object.fromEntries(['sceneSHA256','cameraSHA256','layoutSHA256','codeSHA256'].map(key => [key,binding[key]]));
}
function sortedBoxes(boxes) {
 const unique = new Map(boxes.map(box => [JSON.stringify(box),box]));
 return [...unique.values()].sort((a,b) => {
  for (let i=0;i<4;i++) if (a[i] !== b[i]) return a[i]-b[i];
  return 0;
 });
}
/** Mirrors the existing Area owner: native reservations plus boundary AABBs. */
function exclusions(frame) {
 if (!Array.isArray(frame?.protectedGraphics) || !Array.isArray(frame?.boundarySegments))
  fail('COMPLETE_PROJECTED_CONTEXT_REQUIRED');
 if (frame.protectedGraphics.length + frame.boundarySegments.length > MAX_FRAME_BOXES) fail('CONTEXT_BUDGET_EXCEEDED');
 const boxes = frame.protectedGraphics.map(row => {
  if (!row || !['TEXT','MARKER','PANEL'].includes(row.kind)) fail('NATIVE_RESERVATION_KIND_REQUIRED');
  // Already reserved by the native graphics owner; no outline is shrunk here.
  return rectangle(row.box);
 });
 for (const row of frame.boundarySegments) {
  const a=point(row?.a),b=point(row?.b),r=row?.radiusPx;
  if (!Number.isFinite(r) || r <= 0) fail('BOUNDARY_RADIUS_REQUIRED');
  boxes.push(rectangle([Math.min(a[0],b[0])-r,Math.min(a[1],b[1])-r,
   Math.max(a[0],b[0])+r,Math.max(a[1],b[1])+r]));
 }
 return sortedBoxes(boxes);
}
function labelInput(label,safe) {
 const id=identifier(label?.id),atlas=label?.atlasEnvelope;
 if (!Array.isArray(atlas) || atlas.length !== 2 || !atlas.every(x => Number.isSafeInteger(x) && x>0))
  fail('MEASURED_ATLAS_REQUIRED');
 const preferredAnchor=point(label.preferredAnchor),markerSize=label.markerSize ?? 40,gap=label.gap ?? 18;
 if (!Number.isFinite(markerSize) || markerSize<=0 || !Number.isFinite(gap) || gap<0) fail('SPACING_REQUIRED');
 if (preferredAnchor[0]<safe[0] || preferredAnchor[0]>safe[2] || preferredAnchor[1]<safe[1] || preferredAnchor[1]>safe[3])
  fail('ANCHOR_OUTSIDE_SAFE_AREA');
 return {id,atlasEnvelope:[...atlas],preferredAnchor,markerSize,gap};
}
function blocked(reason,details={}) {
 return freezeEventData({version:STABLE_ANNOTATION_VERSION,status:'BLOCKED',reason,...details,
  renderAllowed:false,nvidiaHardwareVerified:false,visualQualityApproved:false});
}

/**
 * All frames are mandatory, ordered, and half-open [startFrame,endFrame).
 * No history cache, temporal sampling, moving fallback or hardcoded screen row.
 * READY permits layout consumption only; G1/G2 remain the caller's own gates.
 */
export function compileStableAnnotationChapter(input={}) {
 let chapterId;
 try {
  if (!input || typeof input!=='object' || Array.isArray(input)) fail('CHAPTER_INPUT_REQUIRED');
  chapterId=identifier(input.chapterId);
  const {startFrame,endFrame}=input,count=endFrame-startFrame,safeArea=rectangle(input.safeArea),
   binding=normalizeBinding(input.binding);
  if (![startFrame,endFrame].every(Number.isSafeInteger) || startFrame<0 || count<1 || count>MAX_FRAMES)
   fail('HALF_OPEN_CHAPTER_RANGE_REQUIRED');
  if (!Array.isArray(input.frames) || input.frames.length!==count) fail('ALL_CHAPTER_FRAMES_REQUIRED');
  if (!Array.isArray(input.labels) || input.labels.length<1 || input.labels.length>MAX_LABELS) fail('LABELS_REQUIRED');
  const labels=input.labels.map(label=>labelInput(label,safeArea));
  if (new Set(labels.map(label=>label.id)).size!==labels.length) fail('DUPLICATE_LABEL');
  const frameKeys=[],union=new Map();let projectedBoxRecords=0;
  for (let i=0;i<count;i++) {
   const frame=input.frames[i];
   if (frame?.globalFrame!==startFrame+i) fail('EXACT_FRAME_SEQUENCE_REQUIRED');
   if (frame.safeArea!==undefined && JSON.stringify(rectangle(frame.safeArea))!==JSON.stringify(safeArea)) fail('SAFE_AREA_DRIFT');
   const boxes=exclusions(frame);projectedBoxRecords+=boxes.length;
   if (projectedBoxRecords>MAX_PROJECTED_BOX_RECORDS) fail('CONTEXT_BUDGET_EXCEEDED');
   frameKeys.push(JSON.stringify(boxes));
   for (const box of boxes) {
    union.set(JSON.stringify(box),box);
    if (union.size>MAX_UNIQUE_BOXES) fail('CONTEXT_BUDGET_EXCEEDED');
   }
  }
  const nativeBoxes=sortedBoxes([...union.values()]),reserved=[...nativeBoxes],placements={};
  for (const label of labels) {
   const {atlasEnvelope,preferredAnchor,markerSize,gap}=label;
   if (atlasEnvelope[0]>safeArea[2]-safeArea[0] || atlasEnvelope[1]>safeArea[3]-safeArea[1])
    return blocked('STABLE_ANNOTATION_ATLAS_EXCEEDS_SAFE_AREA',{chapterId,labelId:label.id});
   const anchors=[preferredAnchor,...productionAnnotationAnchors({atlasEnvelope,safeArea,preferredAnchor,
    protectedGraphics:reserved.map(box=>({kind:'PANEL',box})),boundarySegments:[],markerSize,gap})];
   let chosen=null;
   for (const anchor of anchors) {
    try { chosen=chooseMetricPlacement({anchor,measurement:{atlasDimensions:atlasEnvelope},safeArea,
     protectedBoxes:reserved,markerSize,gap});break; }
    catch(error) {
     if (!['EVENT_METRIC_LAYOUT_BLOCKED','EVENT_LAYOUT_ANCHOR_OUTSIDE_SAFE_AREA'].includes(error.message)) throw error;
    }
   }
   if (!chosen) return blocked('STABLE_ANNOTATION_NO_CHAPTER_WIDE_SLOT',{chapterId,labelId:label.id,
    checkedFrames:count,uniqueNativeExclusions:nativeBoxes.length});
   placements[label.id]=freezeEventData({version:'AREA_ANNOTATION_V3',placement:chosen,
    reservation:{kind:'TEXT',role:'AREA_ANNOTATION',box:[...chosen.roi]},atlasEnvelope:[...atlasEnvelope],
    attempts:[],nativeGraphicsMoved:false});
   reserved.push([...chosen.roi]);
  }
  const plan=freezeEventData({version:STABLE_ANNOTATION_VERSION,status:'READY',chapterId,startFrame,endFrame,
   safeArea,binding,labels:labels.map(x=>({id:x.id,atlasEnvelope:x.atlasEnvelope})),placements,
   checkedFrames:count,uniqueNativeExclusions:nativeBoxes.length,
   placementPolicy:'ONE_MEASURED_RESERVATION_PER_LABEL_OVER_ENTIRE_CHAPTER',
   boundaryProtection:'UNCHANGED_NATIVE_RADIUS_AABB_UNION_OVER_ALL_FRAMES',
   renderingNotPerformed:true,nvidiaHardwareVerified:false,visualQualityApproved:false});
  // Mutable input cannot mutate a plan. Private snapshots cannot be replaced by
  // a deserialized READY flag or by previous-frame state after random seeking.
  owners.set(plan,{frameKeys,bindingKey:JSON.stringify(binding),labelKey:JSON.stringify(plan.labels)});
  return plan;
 } catch(error) {
  if (typeof error?.message==='string' && error.message.startsWith('STABLE_ANNOTATION_'))
   return blocked(error.message,{...(chapterId ? {chapterId} : {})});
  throw error;
 }
}

/** Stateless, per-draw validation; drift invalidates the whole admitted plan. */
export function evaluateStableAnnotationFrame(plan,input={}) {
 const state=owners.get(plan);
 if (!state || plan?.status!=='READY') fail('COMPILED_PLAN_REQUIRED');
 const {globalFrame}=input;
 if (!Number.isSafeInteger(globalFrame) || globalFrame<plan.startFrame || globalFrame>=plan.endFrame)
  fail('FRAME_OUTSIDE_CHAPTER');
 if (JSON.stringify(normalizeBinding(input.binding))!==state.bindingKey) fail('SOURCE_BINDING_DRIFT');
 if (!Array.isArray(input.labels)) fail('DRAW_MEASURED_ATLASES_REQUIRED');
 const labels=input.labels.map(row=>({id:row?.id,atlasEnvelope:row?.atlasEnvelope}));
 if (JSON.stringify(labels)!==state.labelKey) fail('DRAW_MEASURED_ATLAS_DRIFT');
 if (input.safeArea!==undefined && JSON.stringify(rectangle(input.safeArea))!==JSON.stringify(plan.safeArea)) fail('SAFE_AREA_DRIFT');
 const boxes=exclusions(input);
 if (JSON.stringify(boxes)!==state.frameKeys[globalFrame-plan.startFrame]) fail('PROJECTED_CONTEXT_DRIFT');
 const active=[];
 for (const label of plan.labels) {
  const selected=plan.placements[label.id],roi=selected.reservation.box;
  if (!contains(plan.safeArea,roi) || [...boxes,...active].some(box=>overlap(roi,box))) fail('RESERVATION_COLLISION');
  active.push(roi);
 }
 return freezeEventData({version:STABLE_ANNOTATION_VERSION,status:'LAYOUT_VALIDATED',chapterId:plan.chapterId,
  globalFrame,placements:plan.placements,independentOfSeekHistory:true,nativeGraphicsMoved:false,
  nvidiaHardwareVerified:false,visualQualityApproved:false});
}

/** Compact JSON receipt, not a serialized authority token for future draws. */
export function stableAnnotationReceipt(plan) {
 if (!owners.has(plan) || plan.status!=='READY') fail('COMPILED_PLAN_REQUIRED');
 return freezeEventData({version:plan.version,chapterId:plan.chapterId,startFrame:plan.startFrame,endFrame:plan.endFrame,
  binding:copy(plan.binding),checkedFrames:plan.checkedFrames,
  reservations:plan.labels.map(label=>({id:label.id,atlasEnvelope:[...label.atlasEnvelope],
   roi:[...plan.placements[label.id].reservation.box]})),
  uniqueNativeExclusions:plan.uniqueNativeExclusions,renderingNotPerformed:true,
  nvidiaHardwareVerified:false,visualQualityApproved:false});
}
